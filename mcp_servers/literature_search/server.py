import logging
import sys

from config.settings import get_settings
from logging_config.setup import configure_logging

# Configure logging to go to stderr so we don't corrupt the MCP stdout transport
settings = get_settings()
configure_logging(settings)

root_logger = logging.getLogger()
for handler in list(root_logger.handlers):
    if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
        handler.stream = sys.stderr

import time  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

from db.repository import LiteratureRepository  # noqa: E402
from db.session import AsyncSessionLocal, init_engine  # noqa: E402
from orchestrator.agents.literature_rag.embedding import get_embedding_provider  # noqa: E402

mcp = FastMCP("Literature Search Server")

# Lazy DB engine initialization tracker
_db_initialized = False


def _ensure_db_initialized() -> None:
    global _db_initialized
    if not _db_initialized:
        try:
            init_engine()
        except Exception as e:
            root_logger.error(f"Failed to initialise database engine: {e}")
        _db_initialized = True


@mcp.tool()
async def hybrid_search(query: str, k: int = 10) -> str:
    """Perform hybrid (vector + BM25 keyword) search over planetary risk literature chunks.

    Returns matching documents with scores and rich metadata details.
    """
    _ensure_db_initialized()

    provider = get_embedding_provider(settings)
    embedding_start = time.perf_counter()
    try:
        query_embedding = await provider.embed_query(query)
        embedding_duration_ms = int((time.perf_counter() - embedding_start) * 1000)
    except Exception as e:
        return f"Error: embedding service unreachable: {str(e)}"

    if AsyncSessionLocal is None:
        return "Error: database connection factory is not initialised."

    try:
        async with AsyncSessionLocal() as session:
            retrieval_start = time.perf_counter()
            evidence_list = await LiteratureRepository.hybrid_search(
                session=session,
                query=query,
                query_embedding=query_embedding,
                k=k,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
                embedding_duration_ms=embedding_duration_ms,
                retrieval_start_time=retrieval_start,
            )

            if not evidence_list:
                return "No matching literature documents found."

            lines = []
            for ev in evidence_list:
                doc_id = getattr(ev, "document_id", ev.source)
                chunk_id = getattr(ev, "chunk_id", "N/A")
                title = getattr(ev, "title", "N/A")
                source_url = getattr(ev, "source_url", "N/A")
                lines.append(
                    f"- Claim: {ev.claim}\n"
                    f"  Confidence: {ev.confidence:.4f}\n"
                    f"  Doc ID: {doc_id} | Chunk ID: {chunk_id}\n"
                    f"  Title: {title}\n"
                    f"  URL: {source_url}\n"
                )
            return "\n".join(lines)
    except Exception as e:
        return f"Error executing hybrid search: {str(e)}"


if __name__ == "__main__":
    mcp.run()
