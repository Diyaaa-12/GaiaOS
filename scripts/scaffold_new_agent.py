"""CLI tool for scaffolding new domain agents in GaiaOS."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DOMAIN_REGEX = re.compile(r"^[A-Za-z0-9_]+$")
RESERVED_NAMES = {
    "__init__",
    "registry",
    "base",
    "shared",
    "contract_validator",
    "test",
    "tests",
    "orchestrator",
}


def validate_domain_name(name: str) -> str:
    """Validate domain name matches [A-Za-z0-9_] and prevents path traversal."""
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Domain name cannot be empty.")
    if ".." in clean_name or "/" in clean_name or "\\" in clean_name:
        raise ValueError(f"Path traversal sequence detected in domain name: {name!r}")
    if not DOMAIN_REGEX.match(clean_name):
        raise ValueError(
            f"Invalid domain name: {name!r}. Must contain only letters, numbers, and "
            "underscores ([A-Za-z0-9_])."
        )
    if clean_name.lower() in RESERVED_NAMES:
        raise ValueError(f"Domain name {name!r} is reserved.")
    return clean_name


def scaffold_agent(domain_name: str, root_dir: Path | None = None) -> dict[str, Path]:
    """Generate agent scaffold directory and files from templates."""
    clean_domain = validate_domain_name(domain_name)
    base_dir = root_dir.resolve() if root_dir else Path.cwd()

    domain_title = clean_domain.replace("_", " ").title().replace(" ", "")
    template_dir = base_dir / "scripts" / "new_agent_template"

    target_agent_dir = base_dir / "orchestrator" / "agents" / clean_domain
    target_test_file = base_dir / "tests" / f"test_{clean_domain}_agent.py"

    if target_agent_dir.exists():
        raise FileExistsError(f"Agent directory already exists: {target_agent_dir}")
    if target_test_file.exists():
        raise FileExistsError(f"Agent test file already exists: {target_test_file}")

    replacements = {
        "${domain_name}": clean_domain,
        "${DomainTitle}": domain_title,
    }

    def render(template_path: Path) -> str:
        content = template_path.read_text(encoding="utf-8")
        for key, val in replacements.items():
            content = content.replace(key, val)
        return content

    target_agent_dir.mkdir(parents=True, exist_ok=True)

    init_file = target_agent_dir / "__init__.py"
    init_file.write_text(render(template_dir / "__init__.py.template"), encoding="utf-8")

    agent_file = target_agent_dir / "agent.py"
    agent_file.write_text(render(template_dir / "agent.py.template"), encoding="utf-8")

    target_test_file.parent.mkdir(parents=True, exist_ok=True)
    target_test_file.write_text(render(template_dir / "test_agent.py.template"), encoding="utf-8")

    return {
        "init": init_file,
        "agent": agent_file,
        "test": target_test_file,
    }


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
