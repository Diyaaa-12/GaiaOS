"""Unit tests for dependency range drift checker (scripts/check_requirements_drift.py)."""

from __future__ import annotations

from pathlib import Path

from scripts.check_requirements_drift import check_requirements_drift, main


def test_valid_requirements_pair(tmp_path: Path) -> None:
    """Valid requirements pair where all locked versions satisfy declared ranges."""
    txt_file = tmp_path / "base.txt"
    lock_file = tmp_path / "base.lock"

    txt_file.write_text("pydantic>=2.7,<3\nfastapi>=0.111,<1\n", encoding="utf-8")
    lock_file.write_text("pydantic==2.10.0\nfastapi==0.115.0\n", encoding="utf-8")

    errors = check_requirements_drift(txt_file, lock_file)
    assert errors == []


def test_version_drift_detection(tmp_path: Path) -> None:
    """Version drift detected when locked version falls outside declared range."""
    txt_file = tmp_path / "base.txt"
    lock_file = tmp_path / "base.lock"

    txt_file.write_text("pydantic>=2.7,<3\n", encoding="utf-8")
    lock_file.write_text("pydantic==3.1.0\n", encoding="utf-8")

    errors = check_requirements_drift(txt_file, lock_file)
    assert len(errors) == 1
    assert "pydantic" in errors[0]
    assert "3.1.0" in errors[0]


def test_missing_locked_dependency(tmp_path: Path) -> None:
    """Missing dependency detected when declared package is absent from lock file."""
    txt_file = tmp_path / "base.txt"
    lock_file = tmp_path / "base.lock"

    txt_file.write_text("pydantic>=2.7,<3\nfastapi>=0.111,<1\n", encoding="utf-8")
    lock_file.write_text("pydantic==2.10.0\n", encoding="utf-8")

    errors = check_requirements_drift(txt_file, lock_file)
    assert len(errors) == 1
    assert "fastapi" in errors[0]
    assert "missing" in errors[0].lower()


def test_additional_transitive_packages_must_pass(tmp_path: Path) -> None:
    """Extra packages in lock file (transitive dependencies) are ignored and pass."""
    txt_file = tmp_path / "base.txt"
    lock_file = tmp_path / "base.lock"

    txt_file.write_text("fastapi>=0.111,<1\n", encoding="utf-8")
    lock_file.write_text(
        "fastapi==0.115.0\nstarlette==0.38.0\nanyio==4.4.0\ntyping-extensions==4.12.0\n",
        encoding="utf-8",
    )

    errors = check_requirements_drift(txt_file, lock_file)
    assert errors == []


def test_helpful_error_messages(tmp_path: Path) -> None:
    """Failure messages identify package, declared range, and locked version."""
    txt_file = tmp_path / "base.txt"
    lock_file = tmp_path / "base.lock"

    txt_file.write_text("langgraph>=0.2.0,<0.3.0\n", encoding="utf-8")
    lock_file.write_text("langgraph==1.0.10\n", encoding="utf-8")

    errors = check_requirements_drift(txt_file, lock_file)
    assert len(errors) == 1
    msg = errors[0]
    assert "langgraph" in msg
    assert "1.0.10" in msg
    assert "0.2.0" in msg or "0.3.0" in msg


def test_main_cli_success(tmp_path: Path, monkeypatch) -> None:
    """CLI main entry point returns exit code 0 on valid pair."""
    txt_file = tmp_path / "base.txt"
    lock_file = tmp_path / "base.lock"

    txt_file.write_text("pydantic>=2.7,<3\n", encoding="utf-8")
    lock_file.write_text("pydantic==2.10.0\n", encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["check_requirements_drift.py", str(txt_file), str(lock_file)])
    assert main() == 0


def test_main_cli_failure(tmp_path: Path, monkeypatch) -> None:
    """CLI main entry point returns exit code 1 on drift failure."""
    txt_file = tmp_path / "base.txt"
    lock_file = tmp_path / "base.lock"

    txt_file.write_text("pydantic>=2.7,<3\n", encoding="utf-8")
    lock_file.write_text("pydantic==3.0.0\n", encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["check_requirements_drift.py", str(txt_file), str(lock_file)])
    assert main() == 1
