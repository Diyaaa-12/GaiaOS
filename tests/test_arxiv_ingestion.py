"""Unit and integration tests for arXiv literature ingestion and cursor progression."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import respx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from ingestion.scheduled.literature_sources.arxiv_open_access import fetch_new_arxiv_papers
from workers.jobs.literature_ingestion_job import _async_run_literature_ingestion_job


class MockSessionContext:
    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def __aenter__(self) -> AsyncSession:
        return self.db_session

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        await self.db_session.__aexit__(exc_type, exc_val, exc_tb)


@pytest.mark.asyncio
async def test_fetch_arxiv_parsing() -> None:
    """Verify XML parsing and mapping to PaperRecord objects from arXiv API response."""
    xml_data = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
        <entry>
            <id>http://arxiv.org/abs/2401.01234v1</id>
            <published>2024-01-01T12:00:00Z</published>
            <updated>2024-01-02T12:00:00Z</updated>
            <title>Atmospheric anomalies and wildfire spread</title>
            <summary>This abstract discusses atmospheric anomalies and wildfire spread.</summary>
            <author><name>Jane Doe</name></author>
            <author><name>John Smith</name></author>
            <link rel="related" type="application/pdf" href="http://arxiv.org/pdf/2401.01234v1"/>
            <arxiv:primary_category term="physics.ao-ph"/>
        </entry>
    </feed>
    """

    settings = get_settings()

    with respx.mock:
        respx.get(settings.arxiv_api_url).respond(
            text=xml_data,
            status_code=200,
        )

        papers = await fetch_new_arxiv_papers(
            since=None,
            categories=["physics.ao-ph", "physics.geo-ph"],
        )

        assert len(papers) == 1
        paper = papers[0]
        assert paper.source_id == "2401.01234v1"
        assert paper.title == "Atmospheric anomalies and wildfire spread"
        assert paper.authors == ["Jane Doe", "John Smith"]
        assert paper.published_date == datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert "wildfire spread" in paper.abstract_and_body
        assert paper.source_url == "http://arxiv.org/pdf/2401.01234v1"
        assert paper.extra_metadata["arxiv_id"] == "2401.01234v1"
        assert paper.extra_metadata["primary_category"] == "physics.ao-ph"


@pytest.mark.asyncio
async def test_arxiv_ingestion_deduplication(db_session: AsyncSession) -> None:
    """Verify that duplicate papers are skipped and not re-inserted."""
    # Seed a pre-existing chunk using raw SQL to avoid computed column issue
    import json
    import uuid
    await db_session.execute(
        text("""
            INSERT INTO literature_chunks (
                id, document_id, source_id, chunk_text, source_url, metadata, created_at
            )
            VALUES (:id, :document_id, :source_id, :chunk_text, :source_url, :metadata, NOW());
        """),
        {
            "id": uuid.uuid4(),
            "document_id": "arxiv_test_dup_123",
            "source_id": "test_dup_123",
            "chunk_text": "Existing paper content",
            "source_url": "http://arxiv.org/pdf/test_dup_123",
            "metadata": json.dumps({"title": "Test Title"}),
        }
    )
    await db_session.commit()

    xml_data = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <id>http://arxiv.org/abs/test_dup_123</id>
            <published>2024-01-01T12:00:00Z</published>
            <title>Test Title</title>
            <summary>Existing paper content</summary>
            <author><name>Author One</name></author>
        </entry>
    </feed>
    """

    settings = get_settings()

    with respx.mock, patch("db.session.AsyncSessionLocal") as mock_session_factory:
        # Mock session local factory to return our test db_session context manager
        mock_session_factory.return_value = MockSessionContext(db_session)

        respx.get(settings.arxiv_api_url).respond(
            text=xml_data,
            status_code=200,
        )

        result = await _async_run_literature_ingestion_job(source="arxiv")
        assert result["status"] == "success"
        # Since it is a duplicate, 0 records should be inserted
        assert result["records_inserted"] == 0


@pytest.mark.asyncio
async def test_arxiv_ingestion_cursor_advancement(db_session: AsyncSession) -> None:
    """Verify cursor advances only to max published_date of successfully ingested papers."""
    # Ensure fresh state
    await db_session.execute(text("DELETE FROM literature_chunks;"))
    await db_session.execute(text("DELETE FROM ingestion_cursors WHERE source = 'arxiv';"))
    await db_session.commit()

    pub_time_1 = datetime.now(UTC) - timedelta(hours=2)
    pub_time_2 = datetime.now(UTC) - timedelta(hours=1)

    xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <id>http://arxiv.org/abs/paper_1</id>
            <published>{pub_time_1.isoformat()}</published>
            <title>Paper 1</title>
            <summary>Abstract 1</summary>
            <author><name>Author A</name></author>
        </entry>
        <entry>
            <id>http://arxiv.org/abs/paper_2</id>
            <published>{pub_time_2.isoformat()}</published>
            <title>Paper 2</title>
            <summary>Abstract 2</summary>
            <author><name>Author B</name></author>
        </entry>
    </feed>
    """

    settings = get_settings()

    with respx.mock, patch("db.session.AsyncSessionLocal") as mock_session_factory:
        mock_session_factory.return_value = MockSessionContext(db_session)

        respx.get(settings.arxiv_api_url).respond(
            text=xml_data,
            status_code=200,
        )

        result = await _async_run_literature_ingestion_job(source="arxiv")
        assert result["status"] == "success"
        assert result["records_inserted"] == 2

        # Verify cursor value matches the maximum published date of successfully ingested papers
        cursor_res = await db_session.execute(
            text("SELECT last_ingested_at FROM ingestion_cursors WHERE source = 'arxiv';")
        )
        cursor_row = cursor_res.fetchone()
        assert cursor_row is not None
        assert abs((cursor_row[0].astimezone(UTC) - pub_time_2).total_seconds()) < 1.0


@pytest.mark.asyncio
async def test_arxiv_ingestion_transactional_cursor_progress(db_session: AsyncSession) -> None:
    """Verify that if database commit fails, cursor does not advance and transaction rolls back."""
    await db_session.execute(text("DELETE FROM literature_chunks;"))
    await db_session.execute(text("DELETE FROM ingestion_cursors WHERE source = 'arxiv';"))
    await db_session.commit()

    pub_time = datetime.now(UTC) - timedelta(hours=1)

    xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <id>http://arxiv.org/abs/transaction_fail_paper</id>
            <published>{pub_time.isoformat()}</published>
            <title>Fail Paper</title>
            <summary>Fail Abstract</summary>
            <author><name>Author Fail</name></author>
        </entry>
    </feed>
    """

    settings = get_settings()

    with respx.mock, patch("db.session.AsyncSessionLocal") as mock_session_factory, patch.object(
        db_session, "commit", AsyncMock(side_effect=RuntimeError("Database error during commit"))
    ):
        mock_session_factory.return_value = MockSessionContext(db_session)

        respx.get(settings.arxiv_api_url).respond(
            text=xml_data,
            status_code=200,
        )

        with pytest.raises(RuntimeError, match="Database error during commit"):
            await _async_run_literature_ingestion_job(source="arxiv")

        chunks_res = await db_session.execute(
            text(
                "SELECT count(*) FROM literature_chunks "
                "WHERE source_id = 'transaction_fail_paper';"
            )
        )
        assert chunks_res.scalar() == 0

        # Verify that the cursor did not advance
        cursor_res = await db_session.execute(
            text("SELECT count(*) FROM ingestion_cursors WHERE source = 'arxiv';")
        )
        assert cursor_res.scalar() == 0
