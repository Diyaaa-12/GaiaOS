"""Typed manifest schema for GaiaOS dynamic agent plugins."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PluginManifest(BaseModel):
    """Schema defining an independently packageable GaiaOS agent plugin."""

    name: str = Field(
        description="Unique name of the plugin package (e.g. 'gaiaos-volcano-plugin').",
    )
    version: str = Field(
        description="Semantic version string of the plugin package (e.g. '1.0.0').",
    )
    domain: str = Field(
        description="Explicit domain name for query routing (e.g. 'volcanic_activity').",
    )
    entry_point: str = Field(
        description="Python entry point string pointing to runner callable.",
    )
    gaiaos_version_range: str = Field(
        default=">=0.5.0",
        description="Semver specifier string defining compatible GaiaOS versions.",
    )
    required_settings: list[str] = Field(
        default_factory=list,
        description="List of environment variable setting names required by this plugin.",
    )
    eval_benchmark_question_ids: list[str] = Field(
        default_factory=list,
        description="List of benchmark question IDs against which this plugin should be evaluated.",
    )
    author: str | None = Field(
        default=None,
        description="Optional author or maintainer contact string.",
    )
    description: str | None = Field(
        default=None,
        description="Brief operational description of the plugin's domain scope.",
    )
