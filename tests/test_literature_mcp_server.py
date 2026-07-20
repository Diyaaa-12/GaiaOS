"""Integration tests for the Literature Search MCP Server using stdio transport."""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from orchestrator.schemas.agent_io import Evidence


class TestLiteratureMCPServer:
    """Verifies Literature MCP server startup, tool listing, and function execution."""

    async def test_mcp_server_tool_discovery_subprocess(self) -> None:
        """Starts the MCP server in a subprocess and verifies tool discovery via stdio."""
        server_path = os.path.join("mcp_servers", "literature_search", "server.py")

        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[server_path],
            env=env,
        )

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize session
                await session.initialize()

                # 1. Discover tools
                tools_resp = await session.list_tools()
                tools = tools_resp.tools

                assert len(tools) == 1
                assert tools[0].name == "hybrid_search"
                assert "Perform hybrid" in tools[0].description

    @pytest.mark.asyncio
    async def test_mcp_server_tool_execution(self) -> None:
        """Directly invokes the hybrid_search tool handler with mocked repository."""
        # Direct import of the server tool handler in-process to allow mocking
        from mcp_servers.literature_search.server import hybrid_search

        mock_evidence = [
            Evidence(
                source="test_doc",
                claim="Seismic activity is increasing.",
                confidence=0.8876,
                document_id="test_doc",
                chunk_id=1,
                title="Fault Line Studies",
                source_url="http://earthquake.org",
            )
        ]

        with patch("mcp_servers.literature_search.server.AsyncSessionLocal", MagicMock()):
            with patch(
                "db.repository.LiteratureRepository.hybrid_search", new_callable=AsyncMock
            ) as mock_hybrid:
                mock_hybrid.return_value = mock_evidence

                result = await hybrid_search(query="earthquakes")

                assert "Claim: Seismic activity is increasing." in result
                assert "Confidence: 0.8876" in result
                assert "Doc ID: test_doc | Chunk ID: 1" in result
                assert "Title: Fault Line Studies" in result
                assert "URL: http://earthquake.org" in result

    @pytest.mark.asyncio
    async def test_mcp_server_tool_execution_empty_results(self) -> None:
        """Directly invokes the hybrid_search tool handler with empty database results."""
        from mcp_servers.literature_search.server import hybrid_search

        with patch("mcp_servers.literature_search.server.AsyncSessionLocal", MagicMock()):
            with patch(
                "db.repository.LiteratureRepository.hybrid_search", new_callable=AsyncMock
            ) as mock_hybrid:
                mock_hybrid.return_value = []

                result = await hybrid_search(query="unmatched query")

                assert "No matching literature documents found." in result
