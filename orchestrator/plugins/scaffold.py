"""Agent plugin scaffolding module for GaiaOS (Phase 5 M6 & Phase 7 M4)."""

from __future__ import annotations

import re
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


def scaffold_agent(domain_name: str, root_dir: Path | str | None = None) -> dict[str, Path]:
    """Generate agent scaffold directory and files from templates.

    Args:
        domain_name: Snake_case name for the new domain agent (e.g. 'hydrology').
        root_dir: Root workspace directory. Defaults to current working directory.

    Returns:
        Dict mapping label to created file Path objects.

    Raises:
        ValueError: If domain_name is not a valid identifier.
        FileExistsError: If target agent directory or test file already exists.
    """
    clean_domain = validate_domain_name(domain_name)
    base_dir = Path(root_dir).resolve() if root_dir else Path.cwd()

    domain_title = clean_domain.replace("_", " ").title().replace(" ", "")
    template_dir = base_dir / "scripts" / "new_agent_template"
    if not template_dir.exists():
        template_dir = Path(__file__).parents[2] / "scripts" / "new_agent_template"

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
