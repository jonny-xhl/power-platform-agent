"""
Role-definition registry (framework_power Phase 3).

Discovers role-definition modules in a directory (default ``metadata_py/roles``). Each
module exposes the desired role as a module-level ``ROLE: SecurityRole``. Mirrors the
table registry (``framework_power.registry``).
"""

from __future__ import annotations

import importlib.util
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .components.models import SecurityRole

logger = logging.getLogger(__name__)

DEFAULT_ROLES_DIR = "metadata_py/roles"


@dataclass(frozen=True)
class RoleDefinition:
    """A discovered role definition."""

    name: str  # file stem
    role: SecurityRole
    source: Path


def _load_role_from_module(module_path: Path) -> Optional[SecurityRole]:
    module_name = f"framework_power_role_{module_path.stem}_{uuid.uuid4().hex[:8]}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        logger.warning(f"Cannot load role module: {module_path}")
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error importing role '{module_path}': {e}")
        return None
    role = getattr(module, "ROLE", None)
    return role if isinstance(role, SecurityRole) else None


def discover_role_definitions(
    directory: str | Path = DEFAULT_ROLES_DIR,
) -> dict[str, RoleDefinition]:
    """Discover all role definitions in ``directory`` (mapping file stem -> def)."""
    root = Path(directory)
    if not root.exists():
        return {}
    definitions: dict[str, RoleDefinition] = {}
    for path in sorted(root.glob("*.py")):
        if path.name == "__init__.py" or path.name.startswith("_"):
            continue
        role = _load_role_from_module(path)
        if role is not None:
            definitions[path.stem] = RoleDefinition(name=path.stem, role=role, source=path)
    return definitions


def get_role_definition(
    name: str, directory: str | Path = DEFAULT_ROLES_DIR
) -> RoleDefinition:
    """Load a single role definition by name (file stem). Raises KeyError if absent."""
    path = Path(directory) / f"{name}.py"
    if not path.exists():
        available = list(discover_role_definitions(directory).keys())
        raise KeyError(f"Role '{name}' not found in '{directory}'. Available: {available}")
    role = _load_role_from_module(path)
    if role is None:
        raise KeyError(f"Role '{name}' exists but failed to load.")
    return RoleDefinition(name=name, role=role, source=path)
