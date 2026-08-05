"""Version manager helper for calibration config files."""

from __future__ import annotations

from pathlib import Path


def next_parameter_version(model_name: str, config_dir: Path) -> int:
    """Scan config_dir for existing versioned config files and return the next version index."""
    highest_ver = 0
    if config_dir.is_dir():
        for path in config_dir.glob(f"{model_name}_v*.yaml"):
            try:
                parts = path.name.split("_v")
                if len(parts) >= 2:
                    ver_str = parts[-1].replace(".yaml", "")
                    ver = int(ver_str)
                    if ver > highest_ver:
                        highest_ver = ver
            except ValueError:
                pass
    return highest_ver + 1
