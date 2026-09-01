"""
Dynamic solution composition (Source Mode only).

Auto-discovers Power Platform components from source directories and composes
a :class:`Project` manifest dynamically — eliminating the need to manually edit
``metadata_py/project.py`` every time a new component is added.

This is ONLY used for DEV deployment (source mode). For UAT/PROD (promote mode),
the solution is exported/imported as a zip, so discovery is not needed.

Discovery rules come from ``config/pipeline.yaml`` -> ``source_mode.discovery``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import PipelineConfig, DiscoveryRule

logger = logging.getLogger(__name__)


@dataclass
class ComposeResult:
    """Result of dynamic composition."""

    tables: list[str] = field(default_factory=list)
    optionsets: list[str] = field(default_factory=list)
    webresources: bool = False
    webresource_files: list[str] = field(default_factory=list)
    plugins: list[str] = field(default_factory=list)
    forms: list[str] = field(default_factory=list)
    views: list[str] = field(default_factory=list)
    ribbons: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    solution_name: str = ""
    ribbon_solution_name: str = ""
    version: str = "1.0.0.0"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tables": self.tables,
            "optionsets": self.optionsets,
            "webresources": self.webresources,
            "webresource_files": self.webresource_files,
            "plugins": self.plugins,
            "forms": self.forms,
            "views": self.views,
            "ribbons": self.ribbons,
            "roles": self.roles,
            "solution_name": self.solution_name,
            "ribbon_solution_name": self.ribbon_solution_name,
            "version": self.version,
            "warnings": self.warnings,
        }


class SolutionComposer:
    """Discovers components from source directories and composes a Project.

    Usage::

        composer = SolutionComposer(config)
        result = composer.compose(branch="develop")
        # result.tables == ["new_projectbudget", "new_foo", ...]
    """

    def __init__(self, config: PipelineConfig, *, publisher_prefix: str = "new"):
        self.config = config
        self.publisher_prefix = publisher_prefix
        self.project_root = Path(config.project_root)

    def compose(self, branch: str) -> ComposeResult:
        """Run full discovery and return a :class:`ComposeResult`."""
        result = ComposeResult()
        result.version = self.config.get_version()

        # discover each component type
        if "tables" in self.config.discovery:
            result.tables = self._discover_py_stems(self.config.discovery["tables"])

        if "optionsets" in self.config.discovery:
            result.optionsets = self._discover_py_stems(self.config.discovery["optionsets"])

        if "forms" in self.config.discovery:
            result.forms = self._discover_py_stems(self.config.discovery["forms"])

        if "views" in self.config.discovery:
            result.views = self._discover_py_stems(self.config.discovery["views"])

        if "ribbons" in self.config.discovery:
            result.ribbons = self._discover_py_stems(self.config.discovery["ribbons"])

        if "roles" in self.config.discovery:
            result.roles = self._discover_py_stems(self.config.discovery["roles"])

        if "webresources" in self.config.discovery:
            wr_rule = self.config.discovery["webresources"]
            if wr_rule.sync_all:
                result.webresources = True
            else:
                result.webresource_files = self._discover_webresource_files(wr_rule)

        if "plugins" in self.config.discovery:
            result.plugins = self._discover_plugins(self.config.discovery["plugins"])

        # apply overrides
        self._apply_overrides(result)

        # resolve solution names from environments.yaml
        branch_mapping = self.config.resolve_branch(branch)
        if branch_mapping:
            env_name = branch_mapping.environment
            result.solution_name = self.config.get_solution_name(env_name)
            # ribbon solution name: append "_Ribbon" if not already set
            if result.solution_name:
                result.ribbon_solution_name = f"{result.solution_name}_Ribbon"
            else:
                # fallback to template
                result.solution_name = self.config.solution_split.main_solution_template.format(
                    publisher=self.publisher_prefix, project="WorkflowSoln"
                )
                result.ribbon_solution_name = self.config.solution_split.ribbon_solution_template.format(
                    publisher=self.publisher_prefix, project="RibbonSoln"
                )

        return result

    def _discover_py_stems(self, rule: DiscoveryRule) -> list[str]:
        """Discover .py file stems from a directory.

        Returns stems (filenames without .py extension), excluding files in
        the exclude list and optionally filtering to only custom (publisher-prefixed) files.
        """
        source_dir = self.project_root / rule.source
        if not source_dir.is_dir():
            return []

        stems: list[str] = []
        for path in sorted(source_dir.glob(rule.pattern)):
            if path.name in rule.exclude or path.name.startswith("_"):
                continue
            stem = path.stem
            if rule.filter_custom and not stem.startswith(f"{self.publisher_prefix}_"):
                # skip standard (non-custom) reversed snapshots
                continue
            stems.append(stem)
        return stems

    def _discover_webresource_files(self, rule: DiscoveryRule) -> list[str]:
        """Discover web resource files (relative paths)."""
        source_dir = self.project_root / rule.source
        if not source_dir.is_dir():
            return []
        files: list[str] = []
        for path in sorted(source_dir.rglob("*")):
            if path.is_file() and not path.name.startswith("."):
                files.append(str(path.relative_to(source_dir)).replace("\\", "/"))
        return files

    def _discover_plugins(self, rule: DiscoveryRule) -> list[str]:
        """Discover plugin project directories.

        Each subdirectory containing ``plugin_def.py`` (or the ``detect_by`` file)
        is considered a plugin project.
        """
        source_dir = self.project_root / rule.source
        if not source_dir.is_dir():
            return []
        detect_file = rule.detect_by or "plugin_def.py"
        plugins: list[str] = []
        for path in sorted(source_dir.iterdir()):
            if path.is_dir() and (path / detect_file).exists():
                plugins.append(str(path.relative_to(self.project_root)).replace("\\", "/"))
        return plugins

    def _apply_overrides(self, result: ComposeResult) -> None:
        """Apply include/exclude overrides from pipeline.yaml."""
        overrides = self.config.source_overrides
        if not overrides:
            return

        # include tables
        for t in overrides.get("include_tables", []):
            if t not in result.tables:
                result.tables.append(t)

        # exclude tables
        for t in overrides.get("exclude_tables", []):
            if t in result.tables:
                result.tables.remove(t)

        # include/exclude for other types
        for comp_type in ("optionsets", "forms", "views", "ribbons", "roles"):
            include_key = f"include_{comp_type}"
            exclude_key = f"exclude_{comp_type}"
            current = getattr(result, comp_type)
            for item in overrides.get(include_key, []):
                if item not in current:
                    current.append(item)
            for item in overrides.get(exclude_key, []):
                if item in current:
                    current.remove(item)

        # webresource files override
        if "webresource_files" in overrides:
            result.webresource_files = overrides["webresource_files"]
            result.webresources = False

    def to_project(self, result: ComposeResult):
        """Convert a ComposeResult to a ``Project`` dataclass (from workflow.py).

        This allows the composed result to be used directly with
        ``deploy_workflow()`` / ``plan_workflow()``.
        """
        from ..workflow import Project
        from ..components.models import Publisher

        publisher = Publisher(
            name=self.publisher_prefix,
            display_name=self.publisher_prefix.upper(),
            prefix=self.publisher_prefix,
        )
        return Project(
            main_solution=result.solution_name,
            ribbon_solution=result.ribbon_solution_name,
            publisher=publisher,
            version=result.version,
            optionsets=result.optionsets,
            tables=result.tables,
            webresources=result.webresources,
            webresource_files=result.webresource_files,
            plugins=result.plugins,
            forms=result.forms,
            views=result.views,
            ribbons=result.ribbons,
            roles=result.roles,
        )
