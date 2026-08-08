"""Unit tests for GaiaOS CLI Wizard subcommands and options."""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

from gaiaos_cli.main import app
from typer.testing import CliRunner


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


runner = CliRunner()


def test_cli_version() -> None:
    """Verify gaiaos --version displays version information."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    clean_out = strip_ansi(result.stdout)
    assert "gaiaos-cli version:" in clean_out
    assert "gaiaos-sdk version:" in clean_out


@patch("gaiaos_cli.commands.auth.get_sdk_client")
@patch("gaiaos_cli.commands.auth.save_config")
def test_auth_login(mock_save_config: MagicMock, mock_get_sdk_client: MagicMock) -> None:
    """Verify gaiaos auth login authenticates and saves token."""
    mock_client = MagicMock()
    mock_get_sdk_client.return_value = mock_client
    mock_token = MagicMock()
    mock_token.access_token = "test_bearer_jwt_token"
    mock_client.auth.login.return_value = mock_token

    result = runner.invoke(app, ["auth", "login", "-u", "testuser@gaiaos.io", "-p", "secret123"])
    assert result.exit_code == 0
    assert "Successfully authenticated as 'testuser@gaiaos.io'" in strip_ansi(result.stdout)
    mock_client.auth.login.assert_called_once_with(
        username="testuser@gaiaos.io", password="secret123"
    )
    mock_save_config.assert_called_once()


@patch("gaiaos_cli.commands.auth.load_config")
def test_auth_status(mock_load_config: MagicMock) -> None:
    """Verify gaiaos auth status displays active session information."""
    mock_cfg = MagicMock()
    mock_cfg.api_url = "http://localhost:8000"
    mock_cfg.bearer_token = "valid_token"
    mock_cfg.username = "operator"
    mock_load_config.return_value = mock_cfg

    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0
    assert "Logged in as operator" in strip_ansi(result.stdout)


@patch("gaiaos_cli.commands.auth.save_config")
@patch("gaiaos_cli.commands.auth.load_config")
def test_auth_logout(mock_load_config: MagicMock, mock_save_config: MagicMock) -> None:
    """Verify gaiaos auth logout clears local credentials."""
    mock_cfg = MagicMock()
    mock_load_config.return_value = mock_cfg

    result = runner.invoke(app, ["auth", "logout"])
    assert result.exit_code == 0
    assert "Successfully logged out" in strip_ansi(result.stdout)
    assert mock_cfg.bearer_token is None
    mock_save_config.assert_called_once_with(mock_cfg)


@patch("gaiaos_cli.commands.investigate.get_sdk_client")
def test_investigate_create(mock_get_sdk_client: MagicMock) -> None:
    """Verify gaiaos investigate query submits an investigation."""
    mock_client = MagicMock()
    mock_get_sdk_client.return_value = mock_client

    create_resp = MagicMock()
    create_resp.investigation_id = "inv-12345"
    mock_client.investigations.create.return_value = create_resp

    status_resp = MagicMock()
    status_resp.investigation_id = "inv-12345"
    status_resp.query = "Test query"
    status_resp.status = "complete"
    status_resp.findings = []
    mock_client.investigations.get.return_value = status_resp

    result = runner.invoke(app, ["investigate", "submit", "Test seismic hazard query"])
    assert result.exit_code == 0
    assert "Investigation submitted successfully" in strip_ansi(result.stdout)
    mock_client.investigations.create.assert_called_once_with(
        query="Test seismic hazard query", consent_public_research=False
    )


@patch("gaiaos_cli.commands.investigate.get_sdk_client")
def test_investigate_get(mock_get_sdk_client: MagicMock) -> None:
    """Verify gaiaos investigate get fetches investigation status."""
    mock_client = MagicMock()
    mock_get_sdk_client.return_value = mock_client

    status_resp = MagicMock()
    status_resp.investigation_id = "inv-9999"
    status_resp.query = "Check ocean temperature anomaly"
    status_resp.status = "complete"
    status_resp.findings = []
    mock_client.investigations.get.return_value = status_resp

    result = runner.invoke(app, ["investigate", "get", "inv-9999"])
    assert result.exit_code == 0
    assert "inv-9999" in strip_ansi(result.stdout)
    mock_client.investigations.get.assert_called_once_with("inv-9999")


@patch("gaiaos_cli.commands.investigate.get_sdk_client")
def test_investigate_trace(mock_get_sdk_client: MagicMock) -> None:
    """Verify gaiaos investigate trace fetches execution graph."""
    mock_client = MagicMock()
    mock_get_sdk_client.return_value = mock_client

    trace_resp = MagicMock()
    trace_resp.investigation_id = "inv-9999"
    trace_resp.nodes = []
    trace_resp.edges = []
    mock_client.investigations.get_trace.return_value = trace_resp

    result = runner.invoke(app, ["investigate", "trace", "inv-9999"])
    assert result.exit_code == 0
    assert "Execution Trace Graph" in strip_ansi(result.stdout)
    mock_client.investigations.get_trace.assert_called_once_with("inv-9999")


@patch("gaiaos_cli.commands.admin.get_sdk_client")
def test_admin_api_keys_create(mock_get_sdk_client: MagicMock) -> None:
    """Verify gaiaos admin api-keys create generates a new key."""
    mock_client = MagicMock()
    mock_get_sdk_client.return_value = mock_client

    created_resp = MagicMock()
    created_resp.key_id = "key-555"
    created_resp.api_key = "gaia_secret_key_123"
    mock_client.auth.create_api_key.return_value = created_resp

    result = runner.invoke(app, ["admin", "api-keys", "create", "-n", "CI Test Key"])
    assert result.exit_code == 0
    clean_out = strip_ansi(result.stdout)
    assert "API Key 'CI Test Key' created successfully" in clean_out
    assert "gaia_secret_key_123" in clean_out
    mock_client.auth.create_api_key.assert_called_once_with(
        name="CI Test Key", expires_in_days=None
    )


@patch("gaiaos_cli.commands.admin.get_sdk_client")
def test_admin_api_keys_list(mock_get_sdk_client: MagicMock) -> None:
    """Verify gaiaos admin api-keys list displays active key table."""
    mock_client = MagicMock()
    mock_get_sdk_client.return_value = mock_client

    key1 = MagicMock()
    key1.key_id = "k-1"
    key1.name = "Prod Key"
    key1.prefix = "gaia_live"
    key1.created_at = "2026-08-08"

    mock_client.auth.list_api_keys.return_value = [key1]

    result = runner.invoke(app, ["admin", "api-keys", "list"])
    assert result.exit_code == 0
    clean_out = strip_ansi(result.stdout)
    assert "Active API Keys" in clean_out
    assert "Prod Key" in clean_out
    mock_client.auth.list_api_keys.assert_called_once()


@patch("gaiaos_cli.commands.admin.get_sdk_client")
def test_admin_api_keys_revoke(mock_get_sdk_client: MagicMock) -> None:
    """Verify gaiaos admin api-keys revoke deletes a key."""
    mock_client = MagicMock()
    mock_get_sdk_client.return_value = mock_client

    result = runner.invoke(app, ["admin", "api-keys", "revoke", "k-1", "--force"])
    assert result.exit_code == 0
    assert "API Key 'k-1' successfully revoked" in strip_ansi(result.stdout)
    mock_client.auth.revoke_api_key.assert_called_once_with("k-1")
