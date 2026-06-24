"""
Definitions registry (framework_power).

Discovers table-definition modules in a directory (default ``metadata_py/tables``).
Each module exposes the desired table as a module-level ``TABLE: Table`` (preferred)
or a ``build_table() -> Table`` callable. The registry imports them by file path so
the file name (stem) is the canonical definition key, mirroring ``metadata/tables/*.yaml``.
"""

from __future__ import annotations

import importlib.util
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import Table

logger = logging.getLogger(__name__)

DEFAULT_DEFINITIONS_DIR = "metadata_py/tables"


@dataclass(frozen=True)
class Definition:
    """A discovered table definition."""

    name: str  # file stem, e.g. "new_projectbudget"
    table: Table
    source: Path


def _load_table_from_module(module_path: Path) -> Optional[Table]:
    """Import a definition module by path and return its ``Table`` (or None)."""
    module_name = f"framework_power_def_{module_path.stem}_{uuid.uuid4().hex[:8]}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        logger.warning(f"Cannot load definition module: {module_path}")
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error importing definition '{module_path}': {e}")
        return None

    table = getattr(module, "TABLE", None)
    if isinstance(table, Table):
        return table

    builder = getattr(module, "build_table", None)
    if callable(builder):
        result = builder()
        if isinstance(result, Table):
            return result

    logger.warning(
        f"Definition '{module_path}' exposes neither TABLE: Table nor build_table() -> Table."
    )
    return None


def discover_definitions(directory: str | Path = DEFAULT_DEFINITIONS_DIR) -> dict[str, Definition]:
    """Discover all table definitions in ``directory``.

    Args:
        directory: Directory containing ``<schema>.py`` definition files.

    Returns:
        Mapping of definition name (file stem) -> :class:`Definition`.
    """
    root = Path(directory)
    if not root.exists():
        return {}

    definitions: dict[str, Definition] = {}
    for path in sorted(root.glob("*.py")):
        if path.name == "__init__.py" or path.name.startswith("_"):
            continue
        table = _load_table_from_module(path)
        if table is not None:
            definitions[path.stem] = Definition(name=path.stem, table=table, source=path)
    return definitions


def get_definition(
    name: str,
    directory: str | Path = DEFAULT_DEFINITIONS_DIR,
) -> Definition:
    """Load a single definition by name (file stem).

    Raises:
        KeyError: If the definition does not exist.
    """
    path = Path(directory) / f"{name}.py"
    if not path.exists():
        available = list(discover_definitions(directory).keys())
        raise KeyError(f"Definition '{name}' not found in '{directory}'. Available: {available}")
    table = _load_table_from_module(path)
    if table is None:
        raise KeyError(f"Definition '{name}' exists but failed to load.")
    return Definition(name=name, table=table, source=path)


def deploy_order(definitions: dict[str, Definition]) -> list[str]:
    """Topologically order definition names so referenced entities deploy first.

    A table that references another registered table (1:N ``referenced_entity``) is
    deployed after its referent. Unknown references (e.g. standard ``account``) impose
    no ordering constraint. Cycles fall back to discovery order.
    """
    names = set(definitions)
    # Build adjacency: deps[name] = set of registered names it depends on.
    deps: dict[str, set[str]] = {}
    for name, defn in definitions.items():
        d: set[str] = set()
        for rel in defn.table.relationships:
            ref = rel.referenced_entity
            if ref and ref.lower() in names and ref.lower() != defn.table.logical_name:
                d.add(ref.lower())
        deps[name] = d

    ordered: list[str] = []
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(n: str) -> None:
        if n in visited:
            return
        if n in visiting:  # cycle -> break
            return
        visiting.add(n)
        for dep in sorted(deps.get(n, ())):
            visit(dep)
        visiting.discard(n)
        visited.add(n)
        ordered.append(n)

    for n in sorted(definitions):
        visit(n)
    return ordered
