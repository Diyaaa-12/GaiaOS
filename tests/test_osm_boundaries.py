"""Unit tests for OpenStreetMap Nominatim boundary resolution client."""

from __future__ import annotations

import pytest
import respx

from tools.osm_boundaries.client import resolve_boundary


@pytest.mark.asyncio
async def test_resolve_boundary_success() -> None:
    """Test successful boundary resolution via respx mock Nominatim endpoint."""
    import uuid
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_row = (uuid.uuid4(), "relation/7444", "Paris", 8)
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.fetchone.return_value = mock_row
    mock_session.execute.return_value = mock_res

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session

    with respx.mock, patch("tools.osm_boundaries.client.AsyncSessionLocal", mock_factory):
        respx.get("https://nominatim.openstreetmap.org/reverse").respond(
            json={
                "osm_type": "relation",
                "osm_id": 7444,
                "name": "Paris",
                "place_rank": 8,
                "geojson": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [2.224, 48.815],
                            [2.47, 48.815],
                            [2.47, 48.902],
                            [2.224, 48.902],
                            [2.224, 48.815],
                        ]
                    ],
                },
            },
            status_code=200,
        )

        result = await resolve_boundary(48.8566, 2.3522)
        assert result is not None
        assert result["name"] == "Paris"
        assert result["osm_id"] == "relation/7444"


@pytest.mark.asyncio
async def test_resolve_boundary_resilience_fallback() -> None:
    """Test boundary resolution fallback when Nominatim returns 500 error."""
    with respx.mock:
        respx.get("https://nominatim.openstreetmap.org/reverse").respond(
            status_code=500,
        )

        # Should fall back to DB lookup or return None cleanly without raising unhandled exception
        result = await resolve_boundary(48.8566, 2.3522)
        assert result is None or isinstance(result, dict)
