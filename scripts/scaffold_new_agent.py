"""CLI script for scaffolding new domain agents in GaiaOS."""

from __future__ import annotations

import argparse
import sys

from orchestrator.plugins.scaffold import scaffold_agent, validate_domain_name

__all__ = ["scaffold_agent", "validate_domain_name"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold a new domain agent for GaiaOS.")
    parser.add_argument("domain_name", help="Name of the new domain agent (e.g. 'hydrology').")
    args = parser.parse_args()

    try:
        paths = scaffold_agent(args.domain_name)
        print(f"Successfully scaffolded new domain agent '{args.domain_name}':")
        for k, p in paths.items():
            print(f"  - Created {k}: {p}")
        print("\nNext steps to complete registration:")
        print("1. Open orchestrator/agents/registry.py and add:")
        print(
            f"     from orchestrator.agents.{args.domain_name}.agent import "
            f"run as run_{args.domain_name}\n"
            f"     agent_registry.register('{args.domain_name}', run_{args.domain_name})"
        )
        print(
            "2. Add at least one benchmark question for this domain in "
            "eval/benchmarks/questions.json."
        )
        print("3. Run contract validator: python -m eval.agent_contract_validator")
    except Exception as exc:
        print(f"Error scaffolding agent: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
