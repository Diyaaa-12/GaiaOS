"""Investigation subcommands for GaiaOS CLI Wizard."""

from __future__ import annotations

import json

import typer
from gaiaos_sdk.exceptions import GaiaSDKError

from gaiaos_cli.config import get_sdk_client, load_config
from gaiaos_cli.ui import (
    console,
    format_stream_event,
    print_error,
    print_info,
    print_success,
    render_investigation_summary,
    render_trace_graph,
)

app = typer.Typer(name="investigate", help="Submit and manage planetary risk investigations.")


def _run_investigation_submit(
    ctx: typer.Context, query: str, stream: bool, consent_public: bool
) -> None:
    config = load_config()
    client = get_sdk_client(
        config,
        api_url_override=ctx.obj.get("api_url"),
        api_key_override=ctx.obj.get("api_key"),
        token_override=ctx.obj.get("token"),
    )

    try:
        print_info(f"Submitting investigation query: [bold]{query}[/bold]...")
        resp = client.investigations.create(
            query=query, consent_public_research=consent_public
        )
        inv_id = str(getattr(resp, "investigation_id", ""))
        print_success(f"Investigation submitted successfully. ID: [cyan]{inv_id}[/cyan]")

        if stream and inv_id:
            print_info("Streaming real-time SSE execution events...")
            try:
                for evt in client.investigations.stream(inv_id):
                    line = format_stream_event(evt)
                    console.print(line)
            except Exception as stream_err:
                print_error(f"Streaming error: {stream_err}")

            final_status = client.investigations.get(inv_id)
            if ctx.obj.get("json_output"):
                data = getattr(final_status, "to_dict", lambda: {})()
                console.print(json.dumps(data, indent=2, default=str))
            else:
                render_investigation_summary(final_status)
        else:
            status_resp = client.investigations.get(inv_id)
            if ctx.obj.get("json_output"):
                data = getattr(status_resp, "to_dict", lambda: {})()
                console.print(json.dumps(data, indent=2, default=str))
            else:
                render_investigation_summary(status_resp)

    except GaiaSDKError as exc:
        print_error(f"API Error: {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        print_error(f"Failed to submit investigation: {exc}")
        raise typer.Exit(code=1) from exc


@app.command("submit")
@app.command("create")
def submit_query(
    ctx: typer.Context,
    query: str = typer.Argument(
        ...,
        help="Planetary risk query string (e.g. 'Assess seismic risks in Pacific').",
    ),
    stream: bool = typer.Option(
        False, "--stream", "-s", help="Stream real-time execution events via SSE."
    ),
    consent_public: bool = typer.Option(
        False, "--public", help="Consent to anonymous inclusion in public research dataset."
    ),
) -> None:
    """Submit a new planetary risk investigation query."""
    _run_investigation_submit(ctx, query=query, stream=stream, consent_public=consent_public)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    query: str = typer.Option(None, "--query", "-q", help="Planetary risk query string."),
    stream: bool = typer.Option(
        False, "--stream", "-s", help="Stream real-time execution events via SSE."
    ),
    consent_public: bool = typer.Option(
        False, "--public", help="Consent to anonymous inclusion in public research dataset."
    ),
) -> None:
    """Submit and manage planetary risk investigations."""
    if ctx.invoked_subcommand is not None:
        return

    if query:
        _run_investigation_submit(ctx, query=query, stream=stream, consent_public=consent_public)
        return

    console.print(ctx.get_help())


@app.command("get")
def get_investigation(
    ctx: typer.Context,
    investigation_id: str = typer.Argument(..., help="UUID of the investigation to fetch."),
) -> None:
    """Fetch status and findings for an existing investigation."""
    config = load_config()
    client = get_sdk_client(
        config,
        api_url_override=ctx.obj.get("api_url"),
        api_key_override=ctx.obj.get("api_key"),
        token_override=ctx.obj.get("token"),
    )

    try:
        status_resp = client.investigations.get(investigation_id)
        if ctx.obj.get("json_output"):
            data = getattr(status_resp, "to_dict", lambda: {})()
            console.print(json.dumps(data, indent=2, default=str))
        else:
            render_investigation_summary(status_resp)
    except GaiaSDKError as exc:
        print_error(f"API Error: {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        print_error(f"Failed to fetch investigation {investigation_id}: {exc}")
        raise typer.Exit(code=1) from exc


@app.command("trace")
def get_trace(
    ctx: typer.Context,
    investigation_id: str = typer.Argument(..., help="UUID of the investigation trace to fetch."),
) -> None:
    """Fetch node/edge execution trace graph for an investigation."""
    config = load_config()
    client = get_sdk_client(
        config,
        api_url_override=ctx.obj.get("api_url"),
        api_key_override=ctx.obj.get("api_key"),
        token_override=ctx.obj.get("token"),
    )

    try:
        trace_resp = client.investigations.get_trace(investigation_id)
        if ctx.obj.get("json_output"):
            data = getattr(trace_resp, "to_dict", lambda: {})()
            console.print(json.dumps(data, indent=2, default=str))
        else:
            render_trace_graph(trace_resp)
    except GaiaSDKError as exc:
        print_error(f"API Error: {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        print_error(f"Failed to fetch trace for {investigation_id}: {exc}")
        raise typer.Exit(code=1) from exc
