"""arXiv Open Access literature client wrapped with GaiaOS resilience layer."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from config.settings import get_settings
from ingestion.scheduled.schemas import PaperRecord
from logging_config import get_logger
from resilience.degraded_mode import resilient_call
from tools.http_client import get_shared_client

_log = get_logger(__name__)


async def fetch_new_arxiv_papers(
    since: datetime | None,
    categories: list[str],
) -> list[PaperRecord]:
    """Fetch recent papers from the arXiv API.

    Filters papers in-memory to only return those published after the `since` datetime.
    """
    settings = get_settings()
    base_url = settings.arxiv_api_url.rstrip("/")

    # Build standard search query, e.g. cat:physics.ao-ph OR cat:physics.geo-ph
    query_parts = [f"cat:{cat}" for cat in categories]
    search_query = " OR ".join(query_parts)

    # We fetch the 50 most recent records sorted by last update date
    params = {
        "search_query": search_query,
        "sortBy": "lastUpdatedDate",
        "sortOrder": "descending",
        "max_results": "50",
    }

    cache_key = f"feed:{','.join(sorted(categories))}"

    async def _fetch_arxiv() -> str:
        client = await get_shared_client()
        # Request XML format directly from arXiv
        resp = await client.get(base_url, params=params)
        resp.raise_for_status()
        return resp.text

    result = await resilient_call(
        source="arxiv",
        fn=_fetch_arxiv,
        cache_key=cache_key,
        ttl=settings.arxiv_categories == ["physics.ao-ph", "physics.geo-ph"] and 86400 or 3600,
    )

    if not result.value:
        _log.warning("arxiv.fetch.empty_response")
        return []

    try:
        root = ET.fromstring(result.value)
    except Exception as exc:
        _log.error("arxiv.fetch.xml_parse_failed", error=str(exc))
        return []

    # Namespace map for Atom feed XML parsing
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    papers: list[PaperRecord] = []

    for entry in root.findall("atom:entry", ns):
        id_elem = entry.find("atom:id", ns)
        title_elem = entry.find("atom:title", ns)
        summary_elem = entry.find("atom:summary", ns)
        published_elem = entry.find("atom:published", ns)
        updated_elem = entry.find("atom:updated", ns)

        if id_elem is None or id_elem.text is None:
            continue

        raw_url = id_elem.text.strip()
        # Derive unique arXiv ID from URL (e.g., /abs/2401.01234v1 -> 2401.01234v1)
        arxiv_id = raw_url.split("/abs/")[-1] if "/abs/" in raw_url else raw_url

        title_raw = title_elem.text if title_elem is not None else None
        title = title_raw.strip().replace("\n", " ") if title_raw else "Unknown"

        summary_raw = summary_elem.text if summary_elem is not None else None
        summary = summary_raw.strip() if summary_raw else ""

        # Construct combined abstract and body representation for chunking
        abstract_and_body = f"Title: {title}\nAbstract: {summary}"

        # Extract authors
        authors = []
        for author in entry.findall("atom:author", ns):
            name_elem = author.find("atom:name", ns)
            if name_elem is not None and name_elem.text:
                authors.append(name_elem.text.strip())

        # Parse dates
        pub_date = datetime.now(UTC)
        if published_elem is not None and published_elem.text:
            try:
                date_str = published_elem.text.strip().replace("Z", "+00:00")
                pub_date = datetime.fromisoformat(date_str)
            except Exception:
                pass

        updated_date = pub_date
        if updated_elem is not None and updated_elem.text:
            try:
                date_str = updated_elem.text.strip().replace("Z", "+00:00")
                updated_date = datetime.fromisoformat(date_str)
            except Exception:
                pass

        # Find PDF URL or alternate HTML URL
        pdf_url = raw_url
        for link in entry.findall("atom:link", ns):
            rel = link.attrib.get("rel")
            title_attr = link.attrib.get("title")
            link_type = link.attrib.get("type")
            href = link.attrib.get("href")

            if href and (title_attr == "pdf" or link_type == "application/pdf" or rel == "related"):
                pdf_url = href
                break

        # Extract primary category if available
        primary_cat = "unknown"
        primary_cat_elem = entry.find("arxiv:primary_category", ns)
        if primary_cat_elem is not None:
            primary_cat = primary_cat_elem.attrib.get("term", "unknown")

        # In-memory timestamp filter to return only new papers published after the cursor
        if since is not None and pub_date <= since:
            continue

        # Keep metadata dict for provenance and citations
        extra_metadata = {
            "arxiv_id": arxiv_id,
            "primary_category": primary_cat,
            "updated_date": updated_date.isoformat(),
            "authors": authors,
            "abstract": summary,
        }

        papers.append(
            PaperRecord(
                source_id=arxiv_id,
                title=title,
                authors=authors,
                published_date=pub_date,
                abstract_and_body=abstract_and_body,
                source_url=pdf_url,
                extra_metadata=extra_metadata,
            )
        )

    # Sort ascending so cursor advances logically
    papers.sort(key=lambda p: p.published_date)
    return papers
