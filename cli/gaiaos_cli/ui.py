"""Rich terminal UI helpers and formatted rendering functions."""

from __future__ import annotations

from gaiaos_sdk import StreamEvent
from gaiaos_sdk._generated.models import (
    ApiKeyResponse,
    InvestigationStatusResponse,
    InvestigationTraceResponse,
)
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

console = Console()
err_console = Console(stderr=True)


def print_success(msg: str) -> None:
    """Print success message with green checkmark."""
    console.print(f"[bold green]✓[/bold green] {msg}")


def print_error(msg: str) -> None:
    """Print error message to stderr with red cross."""
    err_console.print(f"[bold red]✗[/bold red] {msg}")


def print_warning(msg: str) -> None:
    """Print warning message with yellow alert icon."""
    console.print(f"[bold yellow]![/bold yellow] {msg}")


def print_info(msg: str) -> None:
    """Print info message with blue indicator."""
    console.print(f"[bold blue]i[/bold blue] {msg}")


def format_stream_event(event: StreamEvent) -> str:
    """Format single SSE StreamEvent into colorized console line."""
    evt_type = event.event_type
    node = event.node or "orchestrator"
    msg = event.message or str(event.payload)

    if evt_type == "job_started":
        color = "bold cyan"
    elif evt_type in ("step_started", "agent_started"):
        color = "cyan"
    elif evt_type in ("step_completed", "agent_completed"):
        color = "green"
    elif evt_type in ("job_completed", "completed"):
        color = "bold green"
    elif evt_type in ("error", "job_failed"):
        color = "bold red"
    else:
        color = "white"

    return f"[{color}][{evt_type}][/{color}] [dim]{node}:[/dim] {msg}"


def render_investigation_summary(inv: InvestigationStatusResponse) -> None:
    """Render investigation status and findings in a Rich Panel and Table."""
    status = str(getattr(inv, "status", "unknown"))
    status_color = "green" if status == "complete" else "yellow" if status == "running" else "red"

    inv_id = str(getattr(inv, "investigation_id", ""))
    query = str(getattr(inv, "query", ""))

    content = (
        f"[bold]ID:[/bold] {inv_id}\n"
        f"[bold]Query:[/bold] {query}\n"
        f"[bold]Status:[/bold] [{status_color}]{status}[/{status_color}]"
    )
    console.print(Panel(content, title="Investigation Summary", expand=False))

    findings = getattr(inv, "findings", []) or []
    if findings:
        table = Table(title="Findings", show_header=True, header_style="bold magenta")
        table.add_column("Domain / Category", style="cyan")
        table.add_column("Finding Summary", style="white")
        table.add_column("Confidence / Lift", style="green")

        for f in findings:
            domain = str(getattr(f, "domain", getattr(f, "category", "general")))
            summary = str(getattr(f, "summary", getattr(f, "description", str(f))))
            conf = getattr(f, "confidence", getattr(f, "statistical_confidence", None))
            conf_str = f"{conf:.2f}" if isinstance(conf, (int, float)) else "N/A"
            table.add_row(domain, summary, conf_str)

        console.print(table)


def render_trace_graph(trace: InvestigationTraceResponse) -> None:
    """Render execution graph nodes and edges as a Rich Tree."""
    inv_id = str(getattr(trace, "investigation_id", ""))
    tree = Tree(f"[bold cyan]Execution Trace Graph[/bold cyan] ({inv_id})")

    nodes = getattr(trace, "nodes", []) or []
    edges = getattr(trace, "edges", []) or []

    nodes_branch = tree.add("[bold yellow]Nodes[/bold yellow]")
    for n in nodes:
        node_id = str(getattr(n, "node_id", getattr(n, "id", str(n))))
        node_type = str(getattr(n, "node_type", getattr(n, "type", "")))
        nodes_branch.add(f"[green]{node_id}[/green] [dim]({node_type})[/dim]")

    if edges:
        edges_branch = tree.add("[bold yellow]Edges / Dependencies[/bold yellow]")
        for e in edges:
            src = str(getattr(e, "source", getattr(e, "from_node", "")))
            tgt = str(getattr(e, "target", getattr(e, "to_node", "")))
            edges_branch.add(f"{src} ──▶ {tgt}")

    console.print(tree)


def render_api_keys_table(keys: list[ApiKeyResponse]) -> None:
    """Render list of active API keys in a formatted Rich Table."""
    if not keys:
        print_info("No active API keys found.")
        return

    table = Table(title="Active API Keys", show_header=True, header_style="bold blue")
    table.add_column("Key ID", style="dim")
    table.add_column("Name", style="bold white")
    table.add_column("Prefix", style="cyan")
    table.add_column("Created At", style="magenta")

    for k in keys:
        key_id = str(getattr(k, "key_id", getattr(k, "id", "")))
        name = str(getattr(k, "name", ""))
        prefix = str(getattr(k, "prefix", getattr(k, "key_prefix", "****")))
        created_at = str(getattr(k, "created_at", ""))
        table.add_row(key_id, name, prefix, created_at)

    console.print(table)
