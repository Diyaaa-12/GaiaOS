"""Tests for GaiaOS version resolution logic."""

from __future__ import annotations

import importlib.metadata
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

import orchestrator.__version__ as version_mod
from orchestrator.__version__ import GAIAOS_VERSION, __version__, _get_version


def test_version_matches_pyproject_toml() -> None:
    """Verify that __version__ matches the project version in pyproject.toml."""
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    expected_version = data["project"]["version"]

    assert __version__ == expected_version
    assert GAIAOS_VERSION == expected_version


def test_get_version_metadata_primary() -> None:
    """When importlib.metadata finds the package, return that version."""
    with patch("importlib.metadata.version", return_value="0.7.4"):
        assert _get_version() == "0.7.4"


def test_get_version_fallback_to_pyproject() -> None:
    """When importlib.metadata raises PackageNotFoundError, fallback to pyproject.toml."""
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    expected_version = data["project"]["version"]

    with patch("importlib.metadata.version", side_effect=importlib.metadata.PackageNotFoundError):
        assert _get_version() == expected_version


def test_get_version_raises_when_neither_available(tmp_path: Path) -> None:
    """When package is not installed and pyproject.toml does not exist, raise RuntimeError."""
    fake_version_file = tmp_path / "orchestrator" / "__version__.py"
    fake_version_file.parent.mkdir(parents=True, exist_ok=True)

    with (
        patch("importlib.metadata.version", side_effect=importlib.metadata.PackageNotFoundError),
        patch.object(version_mod, "Path") as mock_path,
    ):
        mock_path.return_value.resolve.return_value.parent.parent.__truediv__.return_value = (
            tmp_path / "nonexistent_pyproject.toml"
        )
        with pytest.raises(RuntimeError, match="Unable to determine GaiaOS version"):
            _get_version()
