"""Admin subcommands for GaiaOS CLI Wizard."""

from __future__ import annotations

import json

import typer
from gaiaos_sdk.exceptions import GaiaSDKError

from gaiaos_cli.config import get_sdk_client, load_config
from gaiaos_cli.ui import (
    console,
    print_error,
    print_info,
    print_success,
    print_warning,
    render_api_keys_table,
)

app = typer.Typer(name="admin", help="Admin operations and API key management.")
api_keys_app = typer.Typer(name="api-keys", help="Manage account API keys.")
app.add_typer(api_keys_app, name="api-keys")


@api_keys_app.command("create")
def create_key(
    ctx: typer.Context,
    name: str = typer.Option(
        ..., "--name", "-n", prompt="Key Name", help="Name label for the new API key."
    ),
    expires_in_days: int = typer.Option(
        None, "--expires", "-e", help="Optional expiration duration in days."
    ),
) -> None:
    """Create a new API key."""
    config = load_config()
    client = get_sdk_client(
        config,
        api_url_override=ctx.obj.get("api_url"),
        api_key_override=ctx.obj.get("api_key"),
        token_override=ctx.obj.get("token"),
    )

    try:
        resp = client.auth.create_api_key(name=name, expires_in_days=expires_in_days)
        raw_key = str(getattr(resp, "api_key", getattr(resp, "key", "")))
        key_id = str(getattr(resp, "key_id", getattr(resp, "id", "")))

        if ctx.obj.get("json_output"):
            console.print(json.dumps(getattr(resp, "to_dict", lambda: {})(), indent=2, default=str))
        else:
            print_success(f"API Key '[bold]{name}[/bold]' created successfully.")
            print_info(f"Key ID: [cyan]{key_id}[/cyan]")
            print_warning(f"API Key Secret: [bold yellow]{raw_key}[/bold yellow]")
            print_warning("Save this key securely now. It will NOT be displayed again.")
    except GaiaSDKError as exc:
        print_error(f"API Error: {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        print_error(f"Failed to create API key: {exc}")
        raise typer.Exit(code=1) from exc


@api_keys_app.command("list")
def list_keys(ctx: typer.Context) -> None:
    """List active API keys for the current account."""
    config = load_config()
    client = get_sdk_client(
        config,
        api_url_override=ctx.obj.get("api_url"),
        api_key_override=ctx.obj.get("api_key"),
        token_override=ctx.obj.get("token"),
    )

    try:
        keys = client.auth.list_api_keys()
        if ctx.obj.get("json_output"):
            raw_list = [getattr(k, "to_dict", lambda: {})() for k in keys]
            console.print(json.dumps(raw_list, indent=2, default=str))
        else:
            render_api_keys_table(keys)
    except GaiaSDKError as exc:
        print_error(f"API Error: {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        print_error(f"Failed to list API keys: {exc}")
        raise typer.Exit(code=1) from exc


@api_keys_app.command("revoke")
def revoke_key(
    ctx: typer.Context,
    key_id: str = typer.Argument(..., help="UUID of the API key to revoke."),
    force: bool = typer.Option(
        False, "--force", "-f", help="Bypass interactive confirmation prompt."
    ),
) -> None:
    """Revoke an existing API key."""
    if not force:
        confirm = typer.confirm(f"Are you sure you want to revoke API key '{key_id}'?")
        if not confirm:
            print_info("Revocation cancelled.")
            return

    config = load_config()
    client = get_sdk_client(
        config,
        api_url_override=ctx.obj.get("api_url"),
        api_key_override=ctx.obj.get("api_key"),
        token_override=ctx.obj.get("token"),
    )

    try:
        client.auth.revoke_api_key(key_id)
        print_success(f"API Key '[cyan]{key_id}[/cyan]' successfully revoked.")
    except GaiaSDKError as exc:
        print_error(f"API Error: {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        print_error(f"Failed to revoke API key {key_id}: {exc}")
        raise typer.Exit(code=1) from exc
