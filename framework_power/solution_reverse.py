"""
Solution reverse exporter: Dataverse environment -> ``Solution`` (framework_power).

Builds a FULL snapshot of a solution (publisher + all components) from live metadata
so it can be written to ``metadata_py/solutions/<unique_name>.py`` via
:mod:`solution_codegen`. The same file is forward-syncable: ``deploy_solution``
skips standard (non-custom) items, so re-deploying a snapshot is idempotent/safe.

Dispatch is registry-driven: each component's ``componenttype`` code maps to a
registered :class:`ComponentType` whose ``reverse`` reconstructs the typed model
(tables become name refs via ``get_entity_metadata_by_id``; optionset/webresource/
form/view/plugin reverse in their waves). Anything unresolvable degrades to a
note-carrying :class:`ComponentRef` — nothing is silently dropped, nothing raises.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .components import COMPONENT_TYPES, component_type_for_code
from .components.models import ComponentRef, Publisher, Solution
from .solution_deployer import ROLE_SOLUTION_CODE

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


def _reverse_component(client: Any, code: int, oid: str) -> tuple[str, Any]:
    """Map one solution component to ``(bucket, value)``.

    ``bucket`` is ``"tables"`` (name ref), ``"<type>s"`` (typed model list),
    ``"roles"`` (role name ref), or ``"refs"`` (fallback ComponentRef).
    """
    if code == ROLE_SOLUTION_CODE:  # security role -> name ref
        try:
            role = client.get_role_by_id(oid)
            name = role.get("name")
            if name:
                return ("roles", name)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"reverse: could not read role {oid}: {e}")
        return (
            "refs",
            ComponentRef(type="role", object_id=oid, note=f"reverse: role {oid} unreadable"),
        )

    key = component_type_for_code(code)
    if key is None:
        return (
            "refs",
            ComponentRef(
                type=str(code), object_id=oid, note=f"reverse: unknown type {code} object {oid}"
            ),
        )

    if key == "table":
        try:
            meta = client.get_entity_metadata_by_id(oid)
            logical = meta.get("LogicalName") or (meta.get("SchemaName") or "").lower()
            if logical:
                return ("tables", logical)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"reverse: could not read table {oid}: {e}")
        return (
            "refs",
            ComponentRef(type="table", object_id=oid, note=f"reverse: table {oid} unreadable"),
        )

    ctype = COMPONENT_TYPES[key]
    try:
        return (key + "s", ctype.reverse(client, oid))
    except Exception as e:  # noqa: BLE001
        logger.debug(f"reverse: could not read {key} {oid}: {e}")
        return (
            "refs",
            ComponentRef(type=key, object_id=oid, note=f"reverse: {key} {oid} unreadable: {e}"),
        )


def reverse_solution(client: Any, unique_name: str) -> Solution:
    """Build a full-snapshot :class:`Solution` from the live Dataverse environment.

    Args:
        client: An authenticated ``DataverseClient``.
        unique_name: The solution's unique name.

    Returns:
        A :class:`Solution` populated with publisher + components.

    Raises:
        ValueError: If the solution does not exist.
    """
    sol = client.get_solution_by_name(unique_name)
    if sol is None:
        raise ValueError(f"Solution not found: {unique_name}")

    publisher = _extract_publisher(client, sol)
    components = client.get_solution_components(unique_name)

    tables: list[str] = []
    roles: list[str] = []
    refs: list[ComponentRef] = []
    typed: dict[str, list[Any]] = {}
    for comp in components:
        code = int(comp.get("componenttype") or 0)
        oid = str(comp.get("objectid") or "").strip().strip("{}")
        if not code or not oid:
            continue
        bucket, value = _reverse_component(client, code, oid)
        if bucket == "tables":
            if value not in tables:
                tables.append(value)
        elif bucket == "roles":
            if value not in roles:
                roles.append(value)
        elif bucket == "refs":
            refs.append(value)
        else:
            typed.setdefault(bucket, []).append(value)

    return Solution(
        unique_name=unique_name,
        friendly_name=sol.get("friendlyname") or unique_name,
        version=sol.get("version") or "1.0.0.0",
        description=sol.get("description"),
        publisher=publisher,
        tables=tables,
        roles=roles,
        refs=refs,
        optionsets=typed.get("optionsets", []),
        webresources=typed.get("webresources", []),
        forms=typed.get("forms", []),
        views=typed.get("views", []),
        plugins=typed.get("plugins", []),
    )
