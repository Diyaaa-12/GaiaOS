"""Plugin subcommands for GaiaOS CLI Wizard."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from gaiaos_cli.ui import console, print_error, print_info, print_success


def _get_scaffold_agent_func():
    try:
        from orchestrator.plugins.scaffold import scaffold_agent

        return scaffold_agent
    except ImportError as err:
        for p in [Path.cwd(), *Path.cwd().parents]:
            if str(p) not in sys.path:
                sys.path.insert(0, str(p))
            try:
                from orchestrator.plugins.scaffold import scaffold_agent

                return scaffold_agent
            except ImportError:
                continue
        msg = (
            "Could not locate 'orchestrator.plugins.scaffold'. "
            "Please run 'gaiaos plugin scaffold' within a GaiaOS workspace root."
        )
        raise ImportError(msg) from err


app = typer.Typer(name="plugin", help="Scaffold and manage domain agent plugins.")


@app.command("scaffold")
def scaffold(
    ctx: typer.Context,
    domain_name: str = typer.Argument(
        ..., help="Name of the new domain agent to scaffold (e.g. 'hydrology')."
    ),
    target_dir: Path = typer.Option(
        None, "--target-dir", "-d", help="Optional root workspace directory for scaffolding."
    ),
) -> None:
    """Scaffold a new domain agent plugin directory, agent implementation, and test suite."""
    try:
        scaffold_fn = _get_scaffold_agent_func()
        print_info(f"Scaffolding new domain agent plugin '[bold]{domain_name}[/bold]'...")
        paths = scaffold_fn(domain_name=domain_name, root_dir=target_dir)

        print_success(f"Successfully scaffolded new domain agent '{domain_name}':")
        for key, p in paths.items():
            console.print(f"  • Created [cyan]{key}[/cyan]: {p}")

        console.print("\n[bold yellow]Next steps to complete plugin registration:[/bold yellow]")
        console.print("1. Register agent runner in [bold]orchestrator/agents/registry.py[/bold]:")
        imp = f"from orchestrator.agents.{domain_name}.agent import run as run_{domain_name}"
        reg = f"agent_registry.register('{domain_name}', run_{domain_name})"
        console.print(f"     [dim]{imp}[/dim]\n     [dim]{reg}[/dim]")
        console.print(
            "2. Add at least one domain evaluation question in "
            "[bold]eval/benchmarks/questions.json[/bold]."
        )
        console.print(
            "3. Run contract validator: [bold]python -m eval.agent_contract_validator[/bold]"
        )

    except FileExistsError as exc:
        print_error(f"Directory or test file already exists: {exc}")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        print_error(f"Invalid domain name: {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        print_error(f"Failed to scaffold agent: {exc}")
        raise typer.Exit(code=1) from exc
