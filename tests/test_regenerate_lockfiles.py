"""Unit and integration tests for scripts/regenerate_lockfiles.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.regenerate_lockfiles import (
    BASE_LOCK_HEADER,
    DEV_LOCK_HEADER,
    is_valid_for_canonical_env,
    main,
    resolve_lockfile_with_pip,
)


def test_is_valid_for_canonical_env() -> None:
    """Platform-neutral marker evaluation filters OS-specific dependencies automatically."""
    from packaging.requirements import Requirement

    win32_req = Requirement("pywin32>=310; sys_platform == 'win32'")
    assert is_valid_for_canonical_env(win32_req) is False

    linux_req = Requirement("asyncpg>=0.29; python_version >= '3.8'")
    assert is_valid_for_canonical_env(linux_req) is True


def test_regenerated_lockfiles_exclude_pywin32(tmp_path: Path) -> None:
    """Regression test: lockfiles generated for base.txt and dev.txt never include pywin32."""
    repo_root = Path(__file__).resolve().parent.parent
    base_txt = repo_root / "requirements" / "base.txt"
    dev_txt = repo_root / "requirements" / "dev.txt"

    base_content = resolve_lockfile_with_pip(base_txt, BASE_LOCK_HEADER)
    dev_content = resolve_lockfile_with_pip(dev_txt, DEV_LOCK_HEADER)

    assert "pywin32" not in base_content.lower()
    assert "pywin32" not in dev_content.lower()


def test_resolve_lockfile_with_pip_real_execution(tmp_path: Path) -> None:
    """Integration test: resolve_lockfile_with_pip executes real pip resolution subprocess."""
    txt_file = tmp_path / "simple.txt"
    txt_file.write_text("packaging>=23.0\n", encoding="utf-8")

    content = resolve_lockfile_with_pip(txt_file, "# Test Header")

    assert "# Test Header" in content
    assert "packaging==" in content


def test_resolve_lockfile_with_pip_returns_formatted_pins(tmp_path: Path) -> None:
    """resolve_lockfile_with_pip produces sorted package==version pins from pip report."""
    txt_file = tmp_path / "base.txt"
    txt_file.write_text("pydantic>=2.7,<3\n", encoding="utf-8")

    mock_report = {
        "install": [
            {"metadata": {"name": "pydantic", "version": "2.10.0"}},
            {"metadata": {"name": "pydantic-core", "version": "2.27.0"}},
        ]
    }

    with (
        patch("subprocess.run") as mock_run,
        patch("json.load", return_value=mock_report),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.unlink"),
    ):
        mock_run.return_value.returncode = 0
        mock_open = MagicMock()
        mock_open.__enter__.return_value = MagicMock()
        with patch("builtins.open", return_value=mock_open):
            content = resolve_lockfile_with_pip(txt_file, "# Header comment")

    assert "# Header comment" in content
    assert "pydantic==2.10.0" in content
    assert "pydantic-core==2.27.0" in content


def test_main_check_mode_success(monkeypatch) -> None:
    """CLI --check returns exit code 0 when lockfiles match pip resolution."""
    with patch("scripts.regenerate_lockfiles.resolve_lockfile_with_pip") as mock_resolve:
        mock_resolve.side_effect = lambda path, header: (
            Path(path).with_suffix(".lock").read_text(encoding="utf-8")
        )
        monkeypatch.setattr("sys.argv", ["regenerate_lockfiles.py", "--check"])
        assert main() == 0


def test_main_check_mode_drift_failure(tmp_path: Path, monkeypatch) -> None:
    """CLI --check returns exit code 1 when lockfile is out of sync."""
    with patch("scripts.regenerate_lockfiles.resolve_lockfile_with_pip") as mock_resolve:
        mock_resolve.return_value = "pydantic==3.0.0\n"
        monkeypatch.setattr("sys.argv", ["regenerate_lockfiles.py", "--check"])
        assert main() == 1
