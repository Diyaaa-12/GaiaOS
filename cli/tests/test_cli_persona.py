"""First-time contributor persona test for GaiaOS CLI Wizard (Phase 7 Milestone 4)."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from gaiaos_cli.main import app
from typer.testing import CliRunner


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


runner = CliRunner()


def test_first_time_contributor_persona_flow(tmp_path: Path) -> None:
    """Verify a new contributor can discover commands via --help and complete key workflows."""
    # Step 1: Contributor runs `gaiaos --help` to discover available command groups
    root_help = runner.invoke(app, ["--help"])
    assert root_help.exit_code == 0
    clean_root = strip_ansi(root_help.stdout)
    assert "auth" in clean_root
    assert "investigate" in clean_root
    assert "plugin" in clean_root
    assert "admin" in clean_root

    # Step 2: Contributor checks `gaiaos plugin --help` and `gaiaos plugin scaffold --help`
    plugin_help = runner.invoke(app, ["plugin", "--help"])
    assert plugin_help.exit_code == 0
    assert "scaffold" in strip_ansi(plugin_help.stdout)

    scaffold_help = runner.invoke(app, ["plugin", "scaffold", "--help"])
    assert scaffold_help.exit_code == 0
    assert "Name of the new domain agent" in strip_ansi(scaffold_help.stdout)

    # Step 3: Contributor scaffolds a new agent plugin using `--target-dir`
    template_src = Path.cwd() / "scripts" / "new_agent_template"
    template_dst = tmp_path / "scripts" / "new_agent_template"
    template_dst.mkdir(parents=True, exist_ok=True)
    for item in template_src.iterdir():
        if item.is_file():
            content = item.read_text(encoding="utf-8")
            template_dst.joinpath(item.name).write_text(content, encoding="utf-8")

    scaffold_res = runner.invoke(
        app, ["plugin", "scaffold", "volcanology", "--target-dir", str(tmp_path)]
    )
    assert scaffold_res.exit_code == 0
    clean_scaffold = strip_ansi(scaffold_res.stdout)
    assert "Successfully scaffolded new domain agent 'volcanology'" in clean_scaffold
    assert tmp_path.joinpath("orchestrator", "agents", "volcanology", "agent.py").exists()

    # Step 4: Contributor checks `gaiaos investigate --help` and `gaiaos investigate submit --help`
    inv_group_help = runner.invoke(app, ["investigate", "--help"])
    assert inv_group_help.exit_code == 0
    assert "submit" in strip_ansi(inv_group_help.stdout)

    inv_submit_help = runner.invoke(app, ["investigate", "submit", "--help"])
    assert inv_submit_help.exit_code == 0
    assert "--stream" in strip_ansi(inv_submit_help.stdout)

    with patch("gaiaos_cli.commands.investigate.get_sdk_client") as mock_sdk:
        mock_client = MagicMock()
        mock_sdk.return_value = mock_client

        create_resp = MagicMock()
        create_resp.investigation_id = "persona-inv-100"
        mock_client.investigations.create.return_value = create_resp

        status_resp = MagicMock()
        status_resp.investigation_id = "persona-inv-100"
        status_resp.query = "Evaluate volcanic eruption indicators"
        status_resp.status = "complete"
        status_resp.findings = []
        mock_client.investigations.get.return_value = status_resp

        inv_res = runner.invoke(
            app, ["investigate", "submit", "Evaluate volcanic eruption indicators"]
        )
        assert inv_res.exit_code == 0
        assert "persona-inv-100" in inv_res.stdout
