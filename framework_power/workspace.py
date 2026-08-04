"""
Workspace discovery and path resolution (framework_power).

A **workspace** is a directory containing ``pp-workspace.yaml``. The engine
discovers it automatically (search from CWD upward, like ``git``) or via an
explicit ``--workspace`` flag / ``PP_WORKSPACE`` env var.

All default paths (``metadata_py/tables``, ``config/``, etc.) are resolved
relative to the **workspace root**, not CWD. This decouples the engine (pip
package) from per-project data (the workspace), so external repos only need::

    pip install power-platform-agent
    pp workspace init

Usage::

    from framework_power.workspace import Workspace

    ws = Workspace.discover()           # auto-discover from CWD
    ws = Workspace.discover("/path/to") # explicit

    tables_dir = ws.tables_dir          # absolute Path
    config_path = ws.environments_config
    prefix = ws.manifest.publisher_prefix
    issues = ws.validate()              # structural checks
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------- constants

MANIFEST_FILENAME = "pp-workspace.yaml"

# Standard default directories (relative to workspace root).
DEFAULT_DIRS: dict[str, str] = {
    "tables": "metadata_py/tables",
    "forms": "metadata_py/forms",
    "views": "metadata_py/views",
    "ribbons": "metadata_py/ribbons",
    "roles": "metadata_py/roles",
    "optionsets": "metadata_py/optionsets",
    "solutions": "metadata_py/solutions",
    "project": "metadata_py/project.py",
    "webresources": "webresources",
    "plugins": "plugins",
    "config": "config",
    "sources": "sources",
    "state": ".pp/state",
    "cache": ".pp/cache",
    "logs": ".pp/logs",
}

# Keys in DEFAULT_DIRS that must point to existing directories for a valid workspace.
REQUIRED_DIR_KEYS: tuple[str, ...] = (
    "tables",
    "forms",
    "views",
    "config",
)


class NotInWorkspaceError(Exception):
    """Raised when no ``pp-workspace.yaml`` is found."""


# ----------------------------------------------------------------- dataclasses


@dataclass
class WorkspaceManifest:
    """Parsed ``pp-workspace.yaml`` content."""

    name: str = ""
    description: str = ""
    publisher: str = "new"
    publisher_prefix: str = "new"
    publisher_display_name: str = ""
    main_solution: str = ""
    ribbon_solution: str = ""
    version: str = "1.0.0.0"
    dirs: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkspaceManifest":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            publisher=data.get("publisher", "new"),
            publisher_prefix=data.get("publisher_prefix", "new"),
            publisher_display_name=data.get("publisher_display_name", ""),
            main_solution=data.get("main_solution", ""),
            ribbon_solution=data.get("ribbon_solution", ""),
            version=data.get("version", "1.0.0.0"),
            dirs=data.get("dirs", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "publisher": self.publisher,
            "publisher_prefix": self.publisher_prefix,
            "publisher_display_name": self.publisher_display_name,
            "main_solution": self.main_solution,
            "ribbon_solution": self.ribbon_solution,
            "version": self.version,
            "dirs": self.dirs,
        }


@dataclass
class Workspace:
    """A resolved workspace with absolute paths.

    Use :meth:`discover` or :meth:`create_temp` to obtain an instance.
    """

    root: Path
    manifest: WorkspaceManifest
    _paths: dict[str, Path] = field(default_factory=dict, repr=False)

    # --------------------------------------------------------- construction

    @classmethod
    def discover(cls, explicit_path: Optional[str] = None) -> "Workspace":
        """Find and load the workspace.

        Resolution order:
        1. ``explicit_path`` (from ``--workspace`` flag)
        2. ``PP_WORKSPACE`` env var
        3. ``CWD / pp-workspace.yaml``
        4. Walk up from CWD (like ``git``)
        5. Raise :class:`NotInWorkspaceError`
        """
        if explicit_path:
            root = Path(explicit_path).resolve()
            manifest_path = root / MANIFEST_FILENAME
            if not manifest_path.exists():
                raise NotInWorkspaceError(
                    f"No {MANIFEST_FILENAME} found at {root}"
                )
            return cls._load(root)

        env_path = os.environ.get("PP_WORKSPACE")
        if env_path:
            root = Path(env_path).resolve()
            if not (root / MANIFEST_FILENAME).exists():
                raise NotInWorkspaceError(
                    f"PP_WORKSPACE points to {root} but no {MANIFEST_FILENAME} found"
                )
            return cls._load(root)

        cwd = Path.cwd()
        for d in [cwd, *cwd.parents]:
            if (d / MANIFEST_FILENAME).exists():
                return cls._load(d)

        raise NotInWorkspaceError(
            "Not in a Power Platform workspace.\n"
            "  - Run 'pp workspace init' to create one\n"
            "  - Or use --workspace <path> to specify explicitly\n"
            "  - Or set PP_WORKSPACE env var"
        )

    @classmethod
    def _load(cls, root: Path) -> "Workspace":
        """Load and resolve a workspace from a directory that contains the manifest."""
        manifest_path = root / MANIFEST_FILENAME
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        manifest = WorkspaceManifest.from_dict(data)
        ws = cls(root=root.resolve(), manifest=manifest)
        ws._resolve_paths()
        return ws

    @classmethod
    def create(
        cls,
        root: Path,
        manifest: WorkspaceManifest,
        *,
        ensure_dirs: bool = True,
    ) -> "Workspace":
        """Create a new workspace on disk: write manifest, create directories.

        Used by ``pp workspace init``.
        """
        root.mkdir(parents=True, exist_ok=True)
        ws = cls(root=root.resolve(), manifest=manifest)
        ws._resolve_paths()
        if ensure_dirs:
            ws.ensure_dirs()
        return ws

    @classmethod
    def create_from_template(
        cls,
        root: Path,
        *,
        name: str,
        publisher: str = "new",
        publisher_prefix: str = "new",
        publisher_display_name: str = "",
        main_solution: Optional[str] = None,
        ribbon_solution: Optional[str] = None,
        description: str = "",
        version: str = "1.0.0.0",
        extra_dirs: Optional[dict[str, str]] = None,
    ) -> "Workspace":
        """Convenience wrapper for ``pp workspace init``: build manifest + create workspace."""
        sol_name = main_solution or f"{publisher_prefix}_{name}"
        rib_name = ribbon_solution or f"{sol_name}_Ribbon"
        manifest = WorkspaceManifest(
            name=name,
            description=description,
            publisher=publisher,
            publisher_prefix=publisher_prefix,
            publisher_display_name=publisher_display_name,
            main_solution=sol_name,
            ribbon_solution=rib_name,
            version=version,
            dirs=extra_dirs or {},
        )
        return cls.create(root, manifest, ensure_dirs=True)

    # --------------------------------------------------------- path resolution

    def _resolve_paths(self) -> None:
        """Resolve all directory paths to absolute Path objects."""
        for key, default in DEFAULT_DIRS.items():
            override = self.manifest.dirs.get(key, default)
            self._paths[key] = (self.root / override).resolve()

    def path(self, key: str) -> Path:
        """Get an absolute :class:`Path` for a known directory key."""
        if key not in self._paths:
            raise KeyError(f"Unknown workspace path key: {key!r}")
        return self._paths[key]

    # --------------------------------------------------------- convenience properties

    @property
    def tables_dir(self) -> Path:
        return self.path("tables")

    @property
    def forms_dir(self) -> Path:
        return self.path("forms")

    @property
    def views_dir(self) -> Path:
        return self.path("views")

    @property
    def ribbons_dir(self) -> Path:
        return self.path("ribbons")

    @property
    def roles_dir(self) -> Path:
        return self.path("roles")

    @property
    def optionsets_dir(self) -> Path:
        return self.path("optionsets")

    @property
    def solutions_dir(self) -> Path:
        return self.path("solutions")

    @property
    def project_path(self) -> Path:
        return self.path("project")

    @property
    def webresources_root(self) -> Path:
        return self.path("webresources")

    @property
    def plugins_dir(self) -> Path:
        return self.path("plugins")

    @property
    def config_dir(self) -> Path:
        return self.path("config")

    @property
    def sources_dir(self) -> Path:
        return self.path("sources")

    @property
    def state_dir(self) -> Path:
        return self.path("state")

    @property
    def cache_dir(self) -> Path:
        return self.path("cache")

    @property
    def logs_dir(self) -> Path:
        return self.path("logs")

    # Config file convenience paths

    @property
    def environments_config(self) -> Path:
        return self.config_dir / "environments.yaml"

    @property
    def publishers_config(self) -> Path:
        return self.config_dir / "publishers.yaml"

    @property
    def pipeline_config(self) -> Path:
        return self.config_dir / "pipeline.yaml"

    @property
    def environment_settings_config(self) -> Path:
        return self.config_dir / "environment_settings.yaml"

    @property
    def naming_rules_config(self) -> Path:
        return self.config_dir / "naming_rules.yaml"

    @property
    def env_file(self) -> Path:
        """Path to the workspace-level ``.env`` file (Dataverse credentials, etc.)."""
        return self.root / ".env"

    @property
    def manifest_path(self) -> Path:
        return self.root / MANIFEST_FILENAME

    # --------------------------------------------------------- lifecycle

    def ensure_dirs(self) -> None:
        """Create all standard directories if missing (idempotent)."""
        for key in DEFAULT_DIRS:
            p = self._paths.get(key)
            if p is not None:
                p.mkdir(parents=True, exist_ok=True)

    def write_manifest(self) -> None:
        """Write the current manifest back to ``pp-workspace.yaml``."""
        lines: list[str] = [
            "# Power Platform Agent Workspace Manifest",
            "# This file marks the workspace root. The engine discovers it automatically.",
            "",
        ]
        data = self.manifest.to_dict()
        yaml_dump = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
        lines.append(yaml_dump.strip())
        self.manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # --------------------------------------------------------- validation

    def validate(self) -> list[str]:
        """Check workspace structure; return list of issue messages (empty = valid)."""
        issues: list[str] = []
        for key in REQUIRED_DIR_KEYS:
            p = self.path(key)
            if not p.exists():
                issues.append(f"Missing directory: {p.relative_to(self.root)}")
        if not self.environments_config.exists():
            issues.append("Missing config file: config/environments.yaml")
        if not self.manifest.name:
            issues.append("pp-workspace.yaml: 'name' is required")
        if not self.manifest.main_solution:
            issues.append("pp-workspace.yaml: 'main_solution' is required")
        if not self.manifest.publisher_prefix:
            issues.append("pp-workspace.yaml: 'publisher_prefix' is required")
        return issues

    # --------------------------------------------------------- serialization

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable summary for ``pp workspace info``."""
        return {
            "root": str(self.root),
            "manifest": self.manifest.to_dict(),
            "paths": {k: str(v) for k, v in sorted(self._paths.items())},
            "validation": self.validate(),
        }


# ----------------------------------------------------------------- init tracker

# Cache for CLI single-invocation reuse (avoids re-discovering on every sub-command).
_discovered_cache: Optional[Workspace] = None


def get_cached_workspace(explicit_path: Optional[str] = None) -> Workspace:
    """Get the workspace, caching the result for the current process.

    On first call, resolves via :meth:`Workspace.discover`.
    Subsequent calls return the cached workspace, ignoring ``explicit_path``
    (which only applies to the first call).
    """
    global _discovered_cache
    if _discovered_cache is not None:
        return _discovered_cache
    _discovered_cache = Workspace.discover(explicit_path)
    return _discovered_cache


def reset_cache() -> None:
    """Reset the process-local workspace cache (mainly for tests)."""
    global _discovered_cache
    _discovered_cache = None


__all__ = [
    "MANIFEST_FILENAME",
    "DEFAULT_DIRS",
    "REQUIRED_DIR_KEYS",
    "NotInWorkspaceError",
    "WorkspaceManifest",
    "Workspace",
    "get_cached_workspace",
    "reset_cache",
]
