"""Authentication subcommands for GaiaOS CLI Wizard."""

from __future__ import annotations

import json

import typer
from gaiaos_sdk.exceptions import GaiaSDKError

from gaiaos_cli.config import get_sdk_client, load_config, save_config
from gaiaos_cli.ui import console, print_error, print_info, print_success

app = typer.Typer(name="auth", help="Manage authentication and credentials.")


@app.command("register")
def register(
    ctx: typer.Context,
    email: str = typer.Option(None, "--email", "-e", prompt="Email address"),
    password: str = typer.Option(
        None, "--password", "-p", prompt="Password", hide_input=True
    ),
    full_name: str | None = typer.Option(
        None, "--full-name", "-n", help="Optional full name"
    ),
) -> None:
    """Register a new normal user account with GaiaOS server."""
    config = load_config()
    client = get_sdk_client(
        config,
        api_url_override=ctx.obj.get("api_url") if ctx.obj else None,
        api_key_override=ctx.obj.get("api_key") if ctx.obj else None,
        token_override=ctx.obj.get("token") if ctx.obj else None,
    )

    try:
        user_resp = client.auth.register(
            email=email, password=password, full_name=full_name
        )
        registered_email = str(getattr(user_resp, "email", email))
        user_role = str(getattr(user_resp, "role", "user"))

        if ctx.obj and ctx.obj.get("json_output"):
            raw_data = getattr(user_resp, "to_dict", lambda: {})()
            console.print(json.dumps(raw_data, indent=2, default=str))
        else:
            print_success(f"Successfully registered account '{registered_email}' ({user_role}).")
            print_info("Run [bold]gaiaos auth login[/bold] to authenticate with your credentials.")
    except GaiaSDKError as exc:
        print_error(f"Registration failed: {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        print_error(f"Unexpected error during registration: {exc}")
        raise typer.Exit(code=1) from exc


@app.command("login")
def login(
    ctx: typer.Context,
    username: str = typer.Option(None, "--username", "-u", prompt="Username / Email"),
    password: str = typer.Option(
        None, "--password", "-p", prompt="Password", hide_input=True
    ),
) -> None:
    """Authenticate with GaiaOS server and save Bearer token locally."""
    config = load_config()
    client = get_sdk_client(
        config,
        api_url_override=ctx.obj.get("api_url"),
        api_key_override=ctx.obj.get("api_key"),
        token_override=ctx.obj.get("token"),
    )

    try:
        token_resp = client.auth.login(username=username, password=password)
        access_token = str(getattr(token_resp, "access_token", ""))

        config.bearer_token = access_token
        config.username = username
        if ctx.obj.get("api_url"):
            config.api_url = ctx.obj["api_url"]

        save_config(config)
        print_success(
            f"Successfully authenticated as '{username}'. Token saved to ~/.gaiaos/config.json."
        )
    except GaiaSDKError as exc:
        print_error(f"Authentication failed: {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        print_error(f"Unexpected error during login: {exc}")
        raise typer.Exit(code=1) from exc


@app.command("status")
def status(ctx: typer.Context) -> None:
    """Display current authentication status and server settings."""
    config = load_config()
    api_url = ctx.obj.get("api_url") or config.api_url

    print_info(f"Target Server API URL: [cyan]{api_url}[/cyan]")
    if config.bearer_token:
        user_str = f" as [green]{config.username}[/green]" if config.username else ""
        print_success(f"Logged in{user_str} (Bearer token present).")
    elif config.api_key:
        print_success("Authenticated via API Key.")
    else:
        print_info("Not authenticated. Run [bold]gaiaos auth login[/bold] to log in.")


@app.command("logout")
def logout(ctx: typer.Context) -> None:
    """Clear stored local credentials and JWT tokens."""
    config = load_config()
    config.bearer_token = None
    config.username = None
    config.api_key = None
    save_config(config)
    print_success("Successfully logged out and cleared saved credentials.")
