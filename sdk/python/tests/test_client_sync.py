"""Unit tests for synchronous GaiaClient calls."""

import respx
from gaiaos_sdk import GaiaClient
from httpx import Response


@respx.mock
def test_investigation_create_sync() -> None:
    """GaiaClient.investigations.create submits query and returns typed response."""
    respx.post("http://localhost:8000/api/v1/investigations").mock(
        return_value=Response(
            202,
            json={
                "investigation_id": "12345678-1234-5678-1234-567812345678",
                "status": "accepted",
                "message": "Investigation enqueued successfully.",
                "poll_url": "/api/v1/investigations/12345678-1234-5678-1234-567812345678",
                "stream_url": "/api/v1/investigations/12345678-1234-5678-1234-567812345678/stream",
            },
        )
    )

    with GaiaClient(base_url="http://localhost:8000", api_key="test_key") as client:
        resp = client.investigations.create(query="Assess wildfire risk in Oregon")
        assert str(resp.investigation_id) == "12345678-1234-5678-1234-567812345678"
        assert resp.status == "accepted"


@respx.mock
def test_investigation_get_trace_sync() -> None:
    """GaiaClient.investigations.get_trace returns structured trace graph."""
    respx.get(
        "http://localhost:8000/api/v1/investigations/12345678-1234-5678-1234-567812345678/trace"
    ).mock(
        return_value=Response(
            200,
            json={
                "investigation_id": "12345678-1234-5678-1234-567812345678",
                "query": "Assess wildfire risk",
                "nodes": [
                    {
                        "id": "node-1",
                        "type": "agent_started",
                        "event_type": "agent_started",
                        "label": "Agent Started",
                        "agent_id": "causal_agent",
                        "details": {},
                    }
                ],
                "edges": [],
                "summary": {
                    "total_nodes": 1,
                    "total_edges": 0,
                    "event_counts": {"agent_started": 1},
                    "agents_involved": ["causal_agent"],
                    "has_replan_events": False,
                    "has_collaboration_events": False,
                    "has_uncertainty_warnings": False,
                },
                "metadata": {
                    "investigation_id": "12345678-1234-5678-1234-567812345678",
                    "status": "completed",
                    "created_at": "2026-08-08T00:00:00Z",
                    "completed_at": None,
                    "duration_seconds": 1.5,
                    "checkpoint_count": 1,
                    "total_tokens_used": 150,
                },
            },
        )
    )

    with GaiaClient(base_url="http://localhost:8000") as client:
        trace = client.investigations.get_trace("12345678-1234-5678-1234-567812345678")
        assert str(trace.investigation_id) == "12345678-1234-5678-1234-567812345678"
        assert len(trace.nodes) == 1
        assert trace.nodes[0].type_ == "agent_started"
