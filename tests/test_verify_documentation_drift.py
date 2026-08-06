"""Unit tests for scripts/verify_documentation_drift.py."""

from __future__ import annotations

from pathlib import Path

from scripts.verify_documentation_drift import (
    parse_pyproject_version,
    verify_documentation_drift,
)


def _setup_mock_repo(
    tmp_path: Path, version: str = "0.6.3", phase: str = "Phase 6"
) -> tuple[Path, Path, Path]:
    pyproject = tmp_path / "pyproject.toml"
    readme = tmp_path / "README.md"
    docs_dir = tmp_path / "docs" / "releases"
    docs_dir.mkdir(parents=True, exist_ok=True)
    versioning = docs_dir / "Versioning.md"

    pyproject.write_text(f'[project]\nversion = "{version}"\n')
    readme.write_text(f"# GaiaOS\n{phase}\nv{version}\nv0.6.0\nv0.6.1\nv0.6.2\nv0.6.3\n")
    versioning.write_text(f"# Release Map\n{phase}\nv{version}\nv0.6.0\nv0.6.1\nv0.6.2\nv0.6.3\n")
    return pyproject, readme, versioning


def test_parse_pyproject_version(tmp_path: Path) -> None:
    """Verify parse_pyproject_version correctly extracts version from pyproject.toml."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.6.3"\n')
    assert parse_pyproject_version(pyproject) == "0.6.3"

    non_existent = tmp_path / "missing.toml"
    assert parse_pyproject_version(non_existent) is None


def test_verify_documentation_drift_success(tmp_path: Path) -> None:
    """Verify that verify_documentation_drift succeeds when files match pyproject.toml version."""
    _setup_mock_repo(tmp_path)
    is_valid, errors = verify_documentation_drift(repo_root=tmp_path)
    assert is_valid is True
    assert errors == []


def test_verify_documentation_drift_readme_missing_latest_release(tmp_path: Path) -> None:
    """Verify failure when README.md is missing latest version reference."""
    _, readme, _ = _setup_mock_repo(tmp_path)
    readme.write_text("# GaiaOS\nPhase 6\nv0.6.0\nv0.6.1\nv0.6.2\n")

    is_valid, errors = verify_documentation_drift(repo_root=tmp_path)
    assert is_valid is False
    assert any("README.md is missing reference to latest tag 'v0.6.3'" in e for e in errors)


def test_verify_documentation_drift_versioning_missing_latest_release(
    tmp_path: Path,
) -> None:
    """Verify failure when Versioning.md is missing expected versions."""
    _, _, versioning = _setup_mock_repo(tmp_path)
    versioning.write_text("# Release Map\nPhase 6\n")

    is_valid, errors = verify_documentation_drift(repo_root=tmp_path)
    assert is_valid is False
    assert any("Versioning.md Release Map is missing entry for version" in e for e in errors)


def test_verify_documentation_drift_phase_mismatch(tmp_path: Path) -> None:
    """Verify failure when phase reference is missing in README or Versioning.md."""
    _, readme, _ = _setup_mock_repo(tmp_path)
    readme.write_text("# GaiaOS\nv0.6.3\nv0.6.0\nv0.6.1\nv0.6.2\n")

    is_valid, errors = verify_documentation_drift(repo_root=tmp_path)
    assert is_valid is False
    assert any("README.md is missing reference to 'Phase 6'" in e for e in errors)


def test_verify_documentation_drift_outdated_status_table(tmp_path: Path) -> None:
    """Verify failure when README.md status table is missing expected version entries."""
    _, readme, _ = _setup_mock_repo(tmp_path)
    readme.write_text("# GaiaOS\nPhase 6\nv0.6.3\n")

    is_valid, errors = verify_documentation_drift(repo_root=tmp_path)
    assert is_valid is False
    assert any("README.md status table is missing entry for version 'v0.6.0'" in e for e in errors)
