"""Plugin discovery, contract validation, and loading mechanism."""

from __future__ import annotations

import importlib
import importlib.metadata
import os
from collections.abc import Awaitable, Callable
from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet

from config.settings import get_settings
from logging_config import get_logger
from orchestrator.__version__ import GAIAOS_VERSION
from orchestrator.schemas.agent_io import AgentOutput
from orchestrator.schemas.plugin_manifest import PluginManifest

_log = get_logger(__name__)


class PluginValidationError(Exception):
    """Raised when a plugin fails load-time validation."""


class IncompatibleVersionError(PluginValidationError):
    """Raised when a plugin is incompatible with the current GaiaOS version."""


class DuplicateDomainError(PluginValidationError):
    """Raised when a plugin attempts to register a domain already owned by another agent."""


def discover_plugins() -> list[tuple[PluginManifest, Any]]:
    """Discover installed plugins via Python entry points (group='gaiaos.agents').

    Returns a list of tuples containing (PluginManifest, entry_point_value).
    """
    settings = get_settings()
    if not settings.plugins_enabled:
        _log.info("plugin_loader.disabled_by_settings")
        return []

    discovered: list[tuple[PluginManifest, Any]] = []

    try:
        eps = importlib.metadata.entry_points(group="gaiaos.agents")
    except Exception as e:
        _log.warning("plugin_loader.entry_point_discovery_failed", error=str(e))
        return []

    for ep in eps:
        try:
            loaded_obj = ep.load()
            # If entry point is a manifest object or module containing MANIFEST
            manifest: PluginManifest | None = None
            runner_callable: Any = None

            if isinstance(loaded_obj, PluginManifest):
                manifest = loaded_obj
            elif hasattr(loaded_obj, "MANIFEST") and isinstance(
                loaded_obj.MANIFEST, PluginManifest
            ):
                manifest = loaded_obj.MANIFEST
                runner_callable = loaded_obj
            elif callable(loaded_obj):
                # Infer manifest if callable provides __manifest__ or fallback
                manifest = getattr(loaded_obj, "__manifest__", None)
                runner_callable = loaded_obj

            if manifest is None:
                _log.warning(
                    "plugin_loader.manifest_missing",
                    entry_point=ep.name,
                    value=str(ep.value),
                )
                continue

            discovered.append((manifest, runner_callable or ep.value))
        except Exception as e:
            _log.error(
                "plugin_loader.load_entry_point_failed",
                entry_point=ep.name,
                error=str(e),
            )
            if settings.strict_plugin_validation:
                raise PluginValidationError(f"Failed to load entry point {ep.name}: {e}") from e

    _log.info("plugin_loader.discovered_count", count=len(discovered))
    return discovered


def validate_plugin_compatibility(manifest: PluginManifest) -> None:
    """Validate that the plugin is compatible with the running GaiaOS framework version."""
    version_range = manifest.gaiaos_version_range.strip()
    if not version_range:
        return

    try:
        specifiers = SpecifierSet(version_range)
    except InvalidSpecifier as e:
        raise IncompatibleVersionError(
            f"Plugin '{manifest.name}' specifies invalid gaiaos_version_range "
            f"'{version_range}': {e}"
        ) from e

    if GAIAOS_VERSION not in specifiers:
        raise IncompatibleVersionError(
            f"Plugin '{manifest.name}' (version {manifest.version}) requires GaiaOS version "
            f"'{version_range}', but running version is '{GAIAOS_VERSION}'."
        )


def validate_required_settings(manifest: PluginManifest) -> None:
    """Validate that all required environment settings for the plugin are available."""
    missing: list[str] = []
    for req in manifest.required_settings:
        if not os.getenv(req):
            missing.append(req)

    if missing:
        missing_str = ", ".join(missing)
        raise PluginValidationError(
            f"Plugin '{manifest.name}' is missing required setting(s): {missing_str}"
        )


def load_and_validate_plugin(
    manifest: PluginManifest, runner_obj: Any
) -> Callable[..., Awaitable[AgentOutput]]:
    """Validate manifest, environment settings, version compatibility, and agent signature.

    Returns the validated async runner callable.
    """
    validate_plugin_compatibility(manifest)
    validate_required_settings(manifest)

    runner_callable: Callable[..., Awaitable[AgentOutput]] | None = None

    if callable(runner_obj):
        runner_callable = runner_obj
    elif isinstance(runner_obj, str):
        # Resolve module:function import path
        module_path, _, func_name = runner_obj.rpartition(":")
        if not module_path or not func_name:
            raise PluginValidationError(
                f"Invalid entry_point string '{runner_obj}' for plugin '{manifest.name}'."
            )
        try:
            mod = importlib.import_module(module_path)
            runner_callable = getattr(mod, func_name)
        except Exception as e:
            raise PluginValidationError(
                f"Failed to import runner '{runner_obj}' for plugin '{manifest.name}': {e}"
            ) from e

    if runner_callable is None or not callable(runner_callable):
        raise PluginValidationError(
            f"Plugin '{manifest.name}' entry point '{runner_obj}' is not callable."
        )

    # Use Phase 4 agent_contract_validator to verify function signature
    from eval.agent_contract_validator import validate_runner_contract

    contract_errors = validate_runner_contract(runner_callable, manifest.domain)
    if contract_errors:
        err_msg = "; ".join(contract_errors)
        raise PluginValidationError(
            f"Plugin '{manifest.name}' runner failed contract validation: {err_msg}"
        )

    # Warn if zero benchmark question coverage declared
    if not manifest.eval_benchmark_question_ids:
        _log.warning(
            "plugin_loader.zero_eval_coverage_warning",
            plugin_name=manifest.name,
            domain=manifest.domain,
            message="Plugin declared zero eval benchmark question IDs.",
        )

    return runner_callable


async def record_installed_plugin_telemetry(
    manifest: PluginManifest,
    status: str = "active",
    error_message: str | None = None,
) -> None:
    """Passively record plugin status snapshot into installed_plugins table for observability.

    NOTE: This is strictly an observational telemetry write. Database records are never read
    to load or register plugins. Failure to write telemetry does not block worker boot.
    """
    await record_installed_plugin_telemetry_batch([(manifest, status, error_message)])


async def record_installed_plugin_telemetry_batch(
    records: list[tuple[PluginManifest, str, str | None]],
) -> None:
    """Passively record plugin status snapshots into installed_plugins table in a single batch.

    NOTE: This is strictly an observational telemetry write. Database records are never read
    to load or register plugins. Failure to write telemetry does not block worker boot.
    """
    settings = get_settings()
    if not settings.database_url or not records:
        return

    try:
        from db.models.installed_plugin import InstalledPluginRow
        from db.session import AsyncSessionLocal

        if AsyncSessionLocal is None:
            return

        async with AsyncSessionLocal() as session:
            for manifest, status, error_message in records:
                row = InstalledPluginRow(
                    name=manifest.name,
                    version=manifest.version,
                    domain=manifest.domain,
                    status=status,
                    error_message=error_message,
                    manifest_json=manifest.model_dump(),
                )
                session.add(row)
            await session.commit()
            _log.info("plugin_loader.batch_telemetry_persisted", count=len(records))
    except Exception as e:
        _log.warning(
            "plugin_loader.batch_telemetry_persist_failed",
            error=str(e),
        )
