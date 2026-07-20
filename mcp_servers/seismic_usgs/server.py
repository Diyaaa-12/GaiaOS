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

import datetime  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

from tools.seismic_usgs.client import USGSSeismicClient  # noqa: E402

mcp = FastMCP("Seismic USGS Server")


@mcp.tool()
async def get_recent_earthquakes(
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: float | None = None,
    min_magnitude: float = 1.0,
    days: int = 7,
) -> str:
    """Fetch recent earthquakes from USGS matching coordinates, radius and magnitude criteria."""
    client = USGSSeismicClient()
    try:
        features = await client.get_recent_earthquakes(
            lat=latitude,
            lon=longitude,
            radius_km=radius_km,
            min_magnitude=min_magnitude,
            days=days,
        )
        if not features:
            return (
                f"No recent earthquakes found matching min_magnitude={min_magnitude} "
                f"near coordinates ({latitude}, {longitude}) with radius_km={radius_km}."
            )

        lines = []
        for feat in features[:10]:
            props = feat.get("properties", {})
            mag = props.get("mag")
            place = props.get("place")
            time_epoch = props.get("time", 0) / 1000.0
            dt = datetime.datetime.fromtimestamp(time_epoch, datetime.UTC)
            lines.append(f"- Magnitude {mag} near '{place}' at {dt.isoformat()}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving earthquakes: {str(e)}"


if __name__ == "__main__":
    mcp.run()
