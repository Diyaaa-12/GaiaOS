"""Automated unit and integration tests for release automation scripts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.generate_release_notes import (
    generate_release_notes_markdown,
    parse_and_categorize_commits,
)
from scripts.generate_sbom import (
    generate_cyclonedx_sbom,
    get_project_version,
    parse_lockfile_packages,
)
from scripts.verify_release_readiness import (
    validate_tag_format,
    verify_release_readiness,
    verify_versioning_doc,
)

_repo_root = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 1. Release Readiness Gate Tests
# ---------------------------------------------------------------------------


def test_validate_tag_format_valid() -> None:
    """Verify valid semver tags pass format validation."""
    project_ver = get_project_version()
    valid_tags = [f"v{project_ver}", "v0.1.0", "v1.0.0", "v0.1.0-rc1", "v0.8.0-rc2"]
    for tag in valid_tags:
        assert validate_tag_format(tag), f"Tag '{tag}' should pass format validation"


def test_validate_tag_format_invalid() -> None:
    """Verify invalid tag formats fail format validation."""
    invalid_tags = ["0.1.0", "v0.7", "v0.1.0.5", "release-1.0", "v0.1.0-alpha_1", "invalid"]
    for tag in invalid_tags:
        assert not validate_tag_format(tag), f"Tag '{tag}' should fail format validation"


def test_verify_versioning_doc_existing_tag() -> None:
    """Verify existing documented tags pass versioning doc verification."""
    project_ver = get_project_version()
    assert verify_versioning_doc(f"v{project_ver}")
    assert verify_versioning_doc("v0.2.0")


def test_verify_versioning_doc_missing_tag(tmp_path: Path) -> None:
    """Verify tags missing from versioning doc fail verification."""
    mock_doc = tmp_path / "Versioning.md"
    mock_doc.write_text("# Versioning Map\n| v0.2.0 | Complete |\n", encoding="utf-8")

    assert not verify_versioning_doc("v0.99.99", mock_doc)


def test_verify_release_readiness_overall_pass() -> None:
    """Verify overall readiness gate passes for valid documented tag."""
    project_ver = get_project_version()
    is_ready, msg = verify_release_readiness(f"v{project_ver}")
    assert is_ready
    assert "[OK]" in msg


def test_verify_release_readiness_overall_fail_invalid_format() -> None:
    """Verify overall readiness gate fails for invalid tag format."""
    is_ready, msg = verify_release_readiness("invalid-tag")
    assert not is_ready
    assert "Invalid release tag format" in msg


# ---------------------------------------------------------------------------
# 2. Conventional Commit Release Notes Tests
# ---------------------------------------------------------------------------


def test_parse_and_categorize_commits() -> None:
    """Verify conventional commit messages are correctly categorized."""
    synthetic_commits = [
        "feat(auth): add MFA support",
        "fix(db): resolve connection pool leak",
        "docs(api): update OpenAPI spec guide",
        "refactor(core): simplify agent execution loop",
        "ci(workflows): add release automation workflow",
        "feat(api)!: breaking change in /api/v1/auth endpoint",
        "random unformatted commit subject",
    ]

    categorized = parse_and_categorize_commits(synthetic_commits)

    assert len(categorized["New Features & Capabilities"]) == 1
    assert "add MFA support" in categorized["New Features & Capabilities"][0]

    assert len(categorized["Bug Fixes & Corrections"]) == 1
    assert "resolve connection pool leak" in categorized["Bug Fixes & Corrections"][0]

    assert len(categorized["Documentation"]) == 1
    assert len(categorized["Performance & Refactoring"]) == 1
    assert len(categorized["Build, CI & Infrastructure"]) == 1
    assert len(categorized["Breaking Changes"]) == 1
    assert len(categorized["Other Changes"]) == 1


def test_generate_release_notes_markdown_structure() -> None:
    """Verify generated release notes markdown contains expected title and headers."""
    project_ver = get_project_version()
    md = generate_release_notes_markdown(tag=f"v{project_ver}")
    assert f"# GaiaOS Release Notes — v{project_ver}" in md


# ---------------------------------------------------------------------------
# 3. CycloneDX v1.6 SBOM Tests
# ---------------------------------------------------------------------------


def test_generate_sbom_schema_validity() -> None:
    """Verify SBOM output conforms to CycloneDX v1.6 JSON schema structure."""
    lockfile = _repo_root / "requirements" / "base.lock"
    project_ver = get_project_version()
    sbom = generate_cyclonedx_sbom(lockfile, app_version=project_ver)

    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.6"
    assert sbom["serialNumber"].startswith("urn:uuid:")
    assert sbom["metadata"]["component"]["version"] == project_ver
    assert isinstance(sbom["components"], list)
    assert len(sbom["components"]) > 0

    for comp in sbom["components"]:
        assert comp["type"] == "library"
        assert "name" in comp
        assert "version" in comp
        assert comp["purl"].startswith(f"pkg:pypi/{comp['name']}@")


def test_generate_sbom_component_coverage() -> None:
    """Verify 100% of packages in base.lock are present in the SBOM components array."""
    lockfile = _repo_root / "requirements" / "base.lock"
    parsed_pkgs = parse_lockfile_packages(lockfile)
    sbom = generate_cyclonedx_sbom(lockfile)

    sbom_names = {c["name"] for c in sbom["components"]}
    lock_names = {p["name"] for p in parsed_pkgs}

    assert lock_names == sbom_names
    assert len(sbom["components"]) == len(parsed_pkgs)


def test_generate_sbom_determinism() -> None:
    """Verify repeated execution generates byte-for-byte identical CycloneDX JSON output."""
    lockfile = _repo_root / "requirements" / "base.lock"

    sbom_1 = generate_cyclonedx_sbom(lockfile)
    sbom_2 = generate_cyclonedx_sbom(lockfile)

    json_1 = json.dumps(sbom_1, indent=2)
    json_2 = json.dumps(sbom_2, indent=2)

    assert json_1 == json_2


def test_generate_sbom_malformed_input_fails(tmp_path: Path) -> None:
    """Verify passing a missing or invalid lockfile raises FileNotFoundError."""
    missing_lockfile = tmp_path / "non_existent.lock"

    with pytest.raises(FileNotFoundError):
        generate_cyclonedx_sbom(missing_lockfile)


def test_get_project_version_missing_file_raises(tmp_path: Path) -> None:
    """Verify missing pyproject.toml raises FileNotFoundError explicitly."""
    missing_toml = tmp_path / "pyproject.toml"
    with pytest.raises(FileNotFoundError):
        get_project_version(missing_toml)


def test_get_project_version_missing_version_field_raises(tmp_path: Path) -> None:
    """Verify pyproject.toml without version field raises ValueError explicitly."""
    invalid_toml = tmp_path / "pyproject.toml"
    invalid_toml.write_text("[project]\nname = 'test'\n", encoding="utf-8")
    with pytest.raises(ValueError):
        get_project_version(invalid_toml)

