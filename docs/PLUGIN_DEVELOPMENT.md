# GaiaOS Plugin Development Guide

> [!WARNING]
> **FULL-TRUST SECURITY MODEL**: Agent plugins executed by GaiaOS workers run with the **exact same privileges and trust level as core first-party codebase agents**. GaiaOS does **NOT** run plugins inside an isolated sandbox or restricted runtime environment. Plugin packages must only be installed from trusted, verified maintainers and repositories.

---

## Overview

GaiaOS Phase 5 Milestone 6 introduces dynamic agent plugins. Rather than submitting a Pull Request to merge your domain agent directly into the core `orchestrator/agents/` tree, you can package, version, and distribute your domain agent as an independent Python package via `pip install`.

When a GaiaOS worker boots, it dynamically discovers all installed plugins exposed via Python package entry points (`group="gaiaos.agents"`), validates their contracts and version compatibility, and registers them into the active agent routing table.

---

## Creating an Agent Plugin

### 1. Project Directory Structure

```text
gaiaos-volcano-plugin/
├── pyproject.toml
└── gaiaos_volcano/
    ├── __init__.py
    └── agent.py
```

### 2. Implementing the Agent Contract

Your plugin's entry-point callable must conform to the standard GaiaOS `AgentInput -> AgentOutput` contract.

```python
"""Volcanic Activity Domain Agent Plugin."""

from __future__ import annotations

from orchestrator.graph.collaboration_bus import CollaborationBus
from orchestrator.schemas.agent_io import AgentInput, AgentOutput, Evidence
from orchestrator.schemas.plugin_manifest import PluginManifest
from orchestrator.schemas.uncertainty import UncertaintyEstimate

# Declare your Plugin Manifest
MANIFEST = PluginManifest(
    name="gaiaos-volcano-plugin",
    version="1.0.0",
    domain="volcanic_activity",
    entry_point="gaiaos_volcano.agent:run",
    gaiaos_version_range=">=5.0.0",
    required_settings=["VOLCANO_API_KEY"],
    eval_benchmark_question_ids=["eval_q_volcano_001", "eval_q_volcano_002"],
    author="GaiaOS Planetary Intelligence Team",
    description="Monitors active volcanic ash plumes and SO2 emission alerts.",
)


async def run(
    agent_input: AgentInput, bus: CollaborationBus | None = None
) -> AgentOutput:
    """Execute volcanic activity investigation."""
    evidence = [
        Evidence(
            source="Smithsonian Volcanism Program",
            claim=f"Eruption alert active for query '{agent_input.query}'.",
            uncertainty=UncertaintyEstimate(
                point_estimate=0.85, lower_bound=0.75, upper_bound=0.95
            ),
        )
    ]

    return AgentOutput(
        agent_name="volcanic_activity",
        evidence=evidence,
        reasoning_summary="Observed elevated SO2 flux and ash plumes.",
    )
```

### 3. Packaging & Entry Point Declaration (`pyproject.toml`)

Declare your plugin under the `[project.entry-points."gaiaos.agents"]` table in `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "gaiaos-volcano-plugin"
version = "1.0.0"
description = "Volcanic activity domain agent plugin for GaiaOS"
dependencies = [
    "gaiaos>=5.0.0",
]

[project.entry-points."gaiaos.agents"]
volcanic_activity = "gaiaos_volcano.agent:MANIFEST"
```

---

## Plugin Manifest Schema Reference

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `name` | `str` | Yes | Unique package name (e.g. `"gaiaos-volcano-plugin"`). |
| `version` | `str` | Yes | Plugin semver version string (e.g. `"1.0.0"`). |
| `domain` | `str` | Yes | Explicit query routing domain (e.g. `"volcanic_activity"`). |
| `entry_point` | `str` | Yes | Python import path to agent runner callable. |
| `gaiaos_version_range` | `str` | No | Semver specifier range (default: `">=5.0.0"`). |
| `required_settings` | `list[str]` | No | List of required environment variables. |
| `eval_benchmark_question_ids` | `list[str]` | No | Benchmark question IDs declared for eval scoring. |

---

## Startup Validation & Fail-Safe Modes

When a worker boots:
1. **Contract Check**: Reuses `AgentContractValidator` to verify function signature `(AgentInput, bus=None) -> Awaitable[AgentOutput]`.
2. **Version Check**: Validates `gaiaos_version_range` against `GAIAOS_VERSION` (`"5.1.0"`).
3. **Settings Check**: Confirms all `required_settings` exist in environment.
4. **Duplicate Domain Check**: Rejects registration if `domain` collides with a core first-party agent or another plugin.

### Validation Modes
- **Lenient Mode (Default, `STRICT_PLUGIN_VALIDATION=false`)**: If a plugin fails validation, a loud error is logged, the faulty plugin is disabled, and worker boot continues servicing core agents.
- **Strict Mode (`STRICT_PLUGIN_VALIDATION=true`)**: Any plugin validation error immediately aborts worker process boot (`PluginValidationError`).
