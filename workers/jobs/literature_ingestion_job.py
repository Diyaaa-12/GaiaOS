"""Worker jobs for automated historical literature ingestion from arXiv."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any

from sqlalchemy import text

import db.session as db_session
from config.settings import get_settings
from db.models.literature_chunk import LiteratureChunk
from ingestion.scheduled.literature_sources.arxiv_open_access import fetch_new_arxiv_papers
from logging_config import configure_logging, get_logger
from metrics.collector import emit, persist_metric
from metrics.events import IngestionCompleted
from orchestrator.agents.literature_rag.embedding import get_embedding_provider

_log = get_logger(__name__)


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Slice text into overlapping character-based chunks."""
    if chunk_size <= 0:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
        if start >= len(text) or chunk_size <= chunk_overlap:
            break
    return chunks


async def _async_run_literature_ingestion_job(source: str) -> dict[str, Any]:
    """Internal async implementation of the scheduled literature ingestion worker job."""
    start_time = time.perf_counter()
    source_clean = source.strip().lower()
    settings = get_settings()

    # 1. Feature Flag Check
    if not settings.enable_arxiv_ingestion:
        _log.info("ingestion.literature.disabled", source=source_clean)
        return {"status": "disabled", "source": source_clean, "records_inserted": 0}

    if db_session.AsyncSessionLocal is None:
        db_session.init_engine()
        if db_session.AsyncSessionLocal is None:
            raise RuntimeError("Database session factory is not initialised.")

    async with db_session.AsyncSessionLocal() as session:
        # 2. Get last cursor from PostgreSQL ingestion_cursors
        cursor_res = await session.execute(
            text("SELECT last_ingested_at FROM ingestion_cursors WHERE source = :source;"),
            {"source": source_clean},
        )
        cursor_row = cursor_res.fetchone()
        last_ingested_at: datetime | None = cursor_row[0] if cursor_row else None

        # 3. Fetch new papers from arXiv API
        papers = await fetch_new_arxiv_papers(
            since=last_ingested_at,
            categories=settings.arxiv_categories,
        )

        records_fetched = len(papers)
        records_inserted = 0

        if not papers:
            _log.info("ingestion.literature.no_new_papers", source=source_clean)
            return {
                "status": "success",
                "source": source_clean,
                "records_fetched": 0,
                "records_inserted": 0,
            }

        embedding_provider = get_embedding_provider(settings)
        successfully_ingested_papers = []

        # Process each paper
        for paper in papers:
            # Deduplicate by source_id
            dup_res = await session.execute(
                text("SELECT 1 FROM literature_chunks WHERE source_id = :source_id LIMIT 1;"),
                {"source_id": paper.source_id},
            )
            if dup_res.fetchone() is not None:
                # Already ingested, skip
                continue

            # Split abstract and body into overlapping chunks
            chunks = chunk_text(
                paper.abstract_and_body,
                settings.chunk_size,
                settings.chunk_overlap,
            )

            if not chunks:
                continue

            # Batch embed chunks
            embeddings = await embedding_provider.embed_documents(chunks)

            # Build LiteratureChunk models for this paper
            db_chunks = []
            for idx, (chunk_text_content, emb) in enumerate(zip(chunks, embeddings, strict=True)):
                # Mix paper and extra metadata for provenance and citation
                meta = {
                    "title": paper.title,
                    "chunk_id": idx + 1,
                    "authors": paper.authors,
                    **paper.extra_metadata,
                }
                db_chunk = LiteratureChunk(
                    document_id=f"arxiv_{paper.source_id}",
                    source_id=paper.source_id,
                    chunk_text=chunk_text_content,
                    embedding=emb,
                    source_url=paper.source_url,
                    extra_metadata=meta,
                )
                db_chunks.append(db_chunk)

            # Batched database insert
            session.add_all(db_chunks)
            records_inserted += 1
            successfully_ingested_papers.append(paper)

        # 4. Cursor progression to max successfully ingested published_date
        if successfully_ingested_papers:
            max_published_date = max(p.published_date for p in successfully_ingested_papers)
            upsert_cursor_stmt = text("""
                INSERT INTO ingestion_cursors (source, last_ingested_at, updated_at)
                VALUES (:source, :max_published_date, now())
                ON CONFLICT (source) DO UPDATE
                SET last_ingested_at = EXCLUDED.last_ingested_at,
                    updated_at = now();
            """)
            await session.execute(
                upsert_cursor_stmt,
                {"source": source_clean, "max_published_date": max_published_date},
            )

        await session.commit()

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        _log.info(
            "ingestion.literature.completed",
            source=source_clean,
            records_fetched=records_fetched,
            records_inserted=records_inserted,
            duration_ms=duration_ms,
        )

        # Emit standard IngestionCompleted metric event
        ingestion_event = IngestionCompleted(
            source=source_clean,
            records_fetched=records_fetched,
            records_inserted=records_inserted,
            duration_ms=duration_ms,
            success=True,
        )
        emit(ingestion_event)
        await persist_metric(session, ingestion_event)
        await session.commit()

        return {
            "status": "success",
            "source": source_clean,
            "records_fetched": records_fetched,
            "records_inserted": records_inserted,
            "duration_ms": duration_ms,
        }


def run_literature_ingestion_job(source: str = "arxiv") -> dict[str, Any]:
    """RQ Worker entrypoint function for executing arXiv literature ingestion."""
    settings = get_settings()
    configure_logging(settings)
    return asyncio.run(_async_run_literature_ingestion_job(source))
