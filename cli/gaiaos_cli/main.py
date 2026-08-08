"""Main entry point for GaiaOS CLI Wizard."""

from __future__ import annotations

import warnings

import typer
from gaiaos_sdk import __version__ as sdk_version
from gaiaos_sdk.exceptions import IncompatibleServerError

from gaiaos_cli import __version__
from gaiaos_cli.commands import admin, auth, investigate, plugin
from gaiaos_cli.config import get_sdk_client, load_config
from gaiaos_cli.ui import console, print_error, print_info, print_success, print_warning

app = typer.Typer(
    name="gaiaos",
    help="GaiaOS CLI Wizard — Agentic Planetary Risk Intelligence Platform Command-Line Interface.",
    no_args_is_help=True,
)

app.add_typer(auth.app, name="auth")
app.add_typer(investigate.app, name="investigate")
app.add_typer(plugin.app, name="plugin")
app.add_typer(admin.app, name="admin")


def version_callback(value: bool) -> None:
    """Print CLI and SDK version info instantaneously."""
    if value:
        console.print(f"gaiaos-cli version: [bold cyan]{__version__}[/bold cyan]")
        console.print(f"gaiaos-sdk version: [dim]{sdk_version}[/dim]")
        raise typer.Exit()


@app.command("version")
def version_command(
    ctx: typer.Context,
    check: bool = typer.Option(
        False, "--check", "-c", help="Validate live server version compatibility."
    ),
) -> None:
    """Show CLI version and optionally check server compatibility."""
    console.print(f"gaiaos-cli version: [bold cyan]{__version__}[/bold cyan]")
    console.print(f"gaiaos-sdk version: [dim]{sdk_version}[/dim]")

    if check:
        config = load_config()
        client = get_sdk_client(
            config,
            api_url_override=ctx.obj.get("api_url") if ctx.obj else None,
            api_key_override=ctx.obj.get("api_key") if ctx.obj else None,
            token_override=ctx.obj.get("token") if ctx.obj else None,
        )
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                status = client.validate_server()
                server_ver = status.get("version", "unknown")
                print_success(f"Connected to GaiaOS server (version: [green]{server_ver}[/green]).")
                for warning_item in w:
                    print_warning(str(warning_item.message))
        except IncompatibleServerError as err:
            print_error(f"Server version incompatible: {err}")
        except Exception as err:
            print_info(f"Server offline or unreachable ({err}).")


@app.callback()
def main(
    ctx: typer.Context,
    api_url: str | None = typer.Option(
        None, "--api-url", envvar="GAIAOS_API_URL", help="Override GaiaOS API URL."
    ),
    api_key: str | None = typer.Option(
        None, "--api-key", envvar="GAIAOS_API_KEY", help="Override API Key."
    ),
    token: str | None = typer.Option(
        None, "--token", envvar="GAIAOS_BEARER_TOKEN", help="Override Bearer JWT token."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output raw structured JSON responses."
    ),
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show local CLI and SDK version strings.",
    ),
) -> None:
    """GaiaOS CLI Wizard global entry point and options."""
    ctx.ensure_object(dict)
    ctx.obj["api_url"] = api_url
    ctx.obj["api_key"] = api_key
    ctx.obj["token"] = token
    ctx.obj["json_output"] = json_output


if __name__ == "__main__":
    app()
