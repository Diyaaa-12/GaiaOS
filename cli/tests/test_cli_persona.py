"""First-time contributor persona test for GaiaOS CLI Wizard (Phase 7 Milestone 4)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from gaiaos_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def test_first_time_contributor_persona_flow(tmp_path: Path) -> None:
    """Verify a new contributor can discover commands via --help and complete key workflows."""
    # Step 1: Contributor runs `gaiaos --help` to discover available command groups
    root_help = runner.invoke(app, ["--help"])
    assert root_help.exit_code == 0
    assert "auth" in root_help.stdout
    assert "investigate" in root_help.stdout
    assert "plugin" in root_help.stdout
    assert "admin" in root_help.stdout

    # Step 2: Contributor checks `gaiaos plugin --help` and `gaiaos plugin scaffold --help`
    plugin_help = runner.invoke(app, ["plugin", "--help"])
    assert plugin_help.exit_code == 0
    assert "scaffold" in plugin_help.stdout

    scaffold_help = runner.invoke(app, ["plugin", "scaffold", "--help"])
    assert scaffold_help.exit_code == 0
    assert "Name of the new domain agent" in scaffold_help.stdout

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
    assert "Successfully scaffolded new domain agent 'volcanology'" in scaffold_res.stdout
    assert tmp_path.joinpath("orchestrator", "agents", "volcanology", "agent.py").exists()

    # Step 4: Contributor checks `gaiaos investigate --help` and `gaiaos investigate submit --help`
    import subprocess

    commit_hash = (
        subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
    )
    print(f"\n--- DIAGNOSTIC: TESTED COMMIT HASH: {commit_hash} ---")

    inv_group_help = runner.invoke(app, ["investigate", "--help"])
    print("\n--- DIAGNOSTIC: inv_group_help.stdout ---")
    print(inv_group_help.stdout.encode("ascii", errors="backslashreplace").decode("ascii"))
    print(f"REPR: {ascii(inv_group_help.stdout)}")

    inv_submit_help = runner.invoke(app, ["investigate", "submit", "--help"])
    print("\n--- DIAGNOSTIC: inv_submit_help.stdout ---")
    print(inv_submit_help.stdout.encode("ascii", errors="backslashreplace").decode("ascii"))
    print(f"REPR: {ascii(inv_submit_help.stdout)}")

    assert inv_group_help.exit_code == 0
    assert "submit" in inv_group_help.stdout

    assert inv_submit_help.exit_code == 0
    assert "--stream" in inv_submit_help.stdout

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
