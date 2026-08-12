"""Unit tests for scripts/verify_documentation_drift.py."""

from __future__ import annotations

from pathlib import Path

from scripts.verify_documentation_drift import (
    get_git_tags,
    parse_pyproject_version,
    verify_documentation_drift,
)


def _setup_mock_repo(
    tmp_path: Path, version: str = "0.7.3", phase: str = "Phase 7"
) -> tuple[Path, Path, Path, Path]:
    pyproject = tmp_path / "pyproject.toml"
    readme = tmp_path / "README.md"
    docs_dir = tmp_path / "docs" / "releases"
    docs_dir.mkdir(parents=True, exist_ok=True)
    versioning = docs_dir / "Versioning.md"
    architecture = tmp_path / "docs" / "Architecture.md"

    pyproject.write_text(f'[project]\nversion = "{version}"\n')
    readme.write_text(f"# GaiaOS\n{phase}\nv{version}\nv0.7.0\nv0.7.1\nv0.7.2\nv0.7.3\n")
    versioning.write_text(f"# Release Map\n{phase}\nv{version}\nv0.7.0\nv0.7.1\nv0.7.2\nv0.7.3\n")
    architecture.write_text(f"# GaiaOS Architecture\n{phase}\nSection 13\n")
    return pyproject, readme, versioning, architecture


def test_parse_pyproject_version(tmp_path: Path) -> None:
    """Verify parse_pyproject_version correctly extracts version from pyproject.toml."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.7.3"\n')
    assert parse_pyproject_version(pyproject) == "0.7.3"

    non_existent = tmp_path / "missing.toml"
    assert parse_pyproject_version(non_existent) is None


def test_get_git_tags_degrades_gracefully_without_git_dir(tmp_path: Path) -> None:
    """Verify get_git_tags returns None when .git directory is not present."""
    assert get_git_tags(tmp_path) is None


def test_verify_documentation_drift_success(tmp_path: Path) -> None:
    """Verify that verify_documentation_drift succeeds when files match pyproject.toml version."""
    _setup_mock_repo(tmp_path)
    is_valid, errors = verify_documentation_drift(repo_root=tmp_path)
    assert is_valid is True
    assert errors == []


def test_verify_documentation_drift_readme_missing_latest_release(tmp_path: Path) -> None:
    """Verify failure when README.md is missing latest version reference."""
    _, readme, _, _ = _setup_mock_repo(tmp_path)
    readme.write_text("# GaiaOS\nPhase 7\nv0.7.0\nv0.7.1\nv0.7.2\n")

    is_valid, errors = verify_documentation_drift(repo_root=tmp_path)
    assert is_valid is False
    assert any("README.md is missing reference to latest tag 'v0.7.3'" in e for e in errors)


def test_verify_documentation_drift_architecture_missing_phase(tmp_path: Path) -> None:
    """Verify failure when Architecture.md is missing phase reference."""
    _, _, _, architecture = _setup_mock_repo(tmp_path)
    architecture.write_text("# GaiaOS Architecture\nOld text without phase reference\n")

    is_valid, errors = verify_documentation_drift(repo_root=tmp_path)
    assert is_valid is False
    assert any("Architecture.md is missing reference to 'Phase 7'" in e for e in errors)


def test_verify_documentation_drift_versioning_missing_latest_release(
    tmp_path: Path,
) -> None:
    """Verify failure when Versioning.md is missing expected versions."""
    _, _, versioning, _ = _setup_mock_repo(tmp_path)
    versioning.write_text("# Release Map\nPhase 7\n")

    is_valid, errors = verify_documentation_drift(repo_root=tmp_path)
    assert is_valid is False
    assert any("Versioning.md Release Map is missing entry for version" in e for e in errors)


def test_verify_documentation_drift_phase_mismatch(tmp_path: Path) -> None:
    """Verify failure when phase reference is missing in README or Versioning.md."""
    _, readme, _, _ = _setup_mock_repo(tmp_path)
    readme.write_text("# GaiaOS\nv0.7.3\nv0.7.0\nv0.7.1\nv0.7.2\n")

    is_valid, errors = verify_documentation_drift(repo_root=tmp_path)
    assert is_valid is False
    assert any("README.md is missing reference to 'Phase 7'" in e for e in errors)


def test_verify_documentation_drift_outdated_status_table(tmp_path: Path) -> None:
    """Verify failure when README.md status table is missing expected version entries."""
    _, readme, _, _ = _setup_mock_repo(tmp_path)
    readme.write_text("# GaiaOS\nPhase 7\nv0.7.3\n")

    is_valid, errors = verify_documentation_drift(repo_root=tmp_path)
    assert is_valid is False
    assert any("README.md status table is missing entry for version 'v0.7.0'" in e for e in errors)
