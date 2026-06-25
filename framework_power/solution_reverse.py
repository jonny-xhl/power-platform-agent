"""
Solution reverse exporter: Dataverse environment -> ``Solution`` (framework_power).

Builds a FULL snapshot of a solution (publisher + all components) from live metadata
so it can be written to ``metadata_py/solutions/<unique_name>.py`` via
:mod:`solution_codegen`. The same file is forward-syncable: ``deploy_solution``
skips standard (non-custom) items, so re-deploying a snapshot is idempotent/safe.

Wave 1 reconstructs TABLES as name refs (logical names); other component types are
captured as :class:`ComponentRef` fallbacks (typed reconstruction arrives with the
per-type waves). Nothing is silently dropped and nothing raises on an unresolvable
component — a note-carrying ``ComponentRef`` is recorded instead.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .components import component_type_for_code
from .components.models import ComponentRef, Publisher, Solution

logger = logging.getLogger(__name__)


def _extract_publisher(client: Any, solution_obj: dict[str, Any]) -> Optional[Publisher]:
    """Build a Publisher from a solution's ``_publisherid_value`` lookup."""
    publisher_id = solution_obj.get("_publisherid_value")
    if not publisher_id:
        return None
    try:
        pub = client.get_publisher_by_id(publisher_id)
        return Publisher(
            name=pub.get("uniquename") or "",
            display_name=pub.get("friendlyname") or pub.get("uniquename") or "",
            prefix=pub.get("customizationprefix") or "new",
            description=pub.get("description"),
        )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"reverse: could not read publisher {publisher_id}: {e}")
        return None


def _reverse_component(
    client: Any, code: int, oid: str
) -> tuple[str, Any]:
    """Map one solution component to ``("tables", name)`` or ``("refs", ComponentRef)``.

    Later waves add typed branches (optionset/webresource/form/view/plugin) returning
    ``("<type>s", model)``.
    """
    key = component_type_for_code(code)
    if key == "table":
        try:
            meta = client.get_entity_metadata_by_id(oid)
            logical = meta.get("LogicalName") or (meta.get("SchemaName") or "").lower()
            if logical:
                return ("tables", logical)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"reverse: could not read table {oid}: {e}")
    note = f"reverse: component type {code} ({key or 'unknown'}) object {oid}"
    return ("refs", ComponentRef(type=key or str(code), object_id=oid, note=note))


def reverse_solution(client: Any, unique_name: str) -> Solution:
    """Build a full-snapshot :class:`Solution` from the live Dataverse environment.

    Args:
        client: An authenticated ``DataverseClient``.
        unique_name: The solution's unique name.

    Returns:
        A :class:`Solution` populated with publisher + tables (name refs) + refs.

    Raises:
        ValueError: If the solution does not exist.
    """
    sol = client.get_solution_by_name(unique_name)
    if sol is None:
        raise ValueError(f"Solution not found: {unique_name}")

    publisher = _extract_publisher(client, sol)
    components = client.get_solution_components(unique_name)

    tables: list[str] = []
    refs: list[ComponentRef] = []
    for comp in components:
        code = int(comp.get("componenttype") or 0)
        oid = str(comp.get("objectid") or "").strip().strip("{}")
        if not code or not oid:
            continue
        bucket, value = _reverse_component(client, code, oid)
        if bucket == "tables":
            if value not in tables:
                tables.append(value)
        elif bucket == "refs":
            refs.append(value)

    return Solution(
        unique_name=unique_name,
        friendly_name=sol.get("friendlyname") or unique_name,
        version=sol.get("version") or "1.0.0.0",
        description=sol.get("description"),
        publisher=publisher,
        tables=tables,
        refs=refs,
    )
