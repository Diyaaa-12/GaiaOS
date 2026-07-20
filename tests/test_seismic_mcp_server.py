"""Integration tests for the Seismic USGS MCP Server using stdio transport."""

from __future__ import annotations

import http.server
import json
import os
import sys
import threading
from collections.abc import Generator

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MockUSGSRequestHandler(http.server.BaseHTTPRequestHandler):
    """Simple HTTP Request Handler to serve mock earthquake data to the MCP server subprocess."""

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        # Returns a mock GeoJSON response matching expected properties
        response = {
            "features": [
                {
                    "properties": {
                        "mag": 6.8,
                        "place": "Near Coast of Honshu, Japan",
                        "time": 1782000000000,
                    }
                }
            ]
        }
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def log_message(self, format: str, *args: any) -> None:
        # Suppress request logging to keep pytest output clean
        pass


@pytest.fixture
def mock_usgs_server() -> Generator[str, None, None]:
    """Starts a local HTTP server in a background thread to mock USGS API."""
    server = http.server.HTTPServer(("127.0.0.1", 0), MockUSGSRequestHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}/"
    server.shutdown()
    server.server_close()


class TestSeismicMCPServer:
    """Verifies Seismic MCP server initialization, tool listing, and execution."""

    async def test_mcp_server_tools_and_execution(self, mock_usgs_server: str) -> None:
        server_path = os.path.join("mcp_servers", "seismic_usgs", "server.py")

        # Stdio connection parameters for running our server script
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()
        # Direct the subprocess to query our local mock HTTP server instead of USGS
        env["USGS_API_URL"] = mock_usgs_server

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
                assert tools[0].name == "get_recent_earthquakes"

                # 2. Invoke tool
                result = await session.call_tool(
                    name="get_recent_earthquakes",
                    arguments={
                        "latitude": 35.6762,
                        "longitude": 139.6503,
                        "radius_km": 100.0,
                        "min_magnitude": 1.0,
                    },
                )

                content = result.content
                assert len(content) == 1
                assert "Magnitude 6.8" in content[0].text
                assert "Honshu" in content[0].text
