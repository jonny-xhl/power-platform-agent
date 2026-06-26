"""
Security-role privilege deployer (framework_power Phase 3).

``deploy_role`` upserts a role's TABLE privileges to match a :class:`SecurityRole`
definition. Roles are NOT created here — the role must already exist in the
environment (looked up by name; raises if missing). The deploy is **non-destructive**:
it adds/updates the privileges the definition *specifies*; unlisted rights are left
untouched (matches the package's deploy philosophy).

Privilege model (verified live):
- A privilege is addressed by name ``prv<Right><EntitySchemaName>`` (e.g.
  ``prvReadnew_FpSmokeA``) → ``privilegeid``.
- A role↔privilege link is a ``roleprivilegescollection`` record carrying the depth as
  the bitmask ``privilegedepthmask`` (USER=1, BUSINESS_UNIT=2, PARENT_CHILD=4, GLOBAL=8).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .components._common import is_custom
from .components.models import AccessRight, PrivilegeDepth, SecurityRole, TablePrivilege

logger = logging.getLogger(__name__)

# AccessRight -> privilege-name prefix.
_RIGHT_PREFIX: dict[AccessRight, str] = {
    AccessRight.READ: "prvRead",
    AccessRight.WRITE: "prvWrite",
    AccessRight.CREATE: "prvCreate",
    AccessRight.DELETE: "prvDelete",
    AccessRight.APPEND: "prvAppend",
    AccessRight.APPEND_TO: "prvAppendTo",
    AccessRight.ASSIGN: "prvAssign",
    AccessRight.SHARE: "prvShare",
}

_DEPTH_BY_MASK: dict[int, PrivilegeDepth] = {
    int(PrivilegeDepth.USER): PrivilegeDepth.USER,
    int(PrivilegeDepth.BUSINESS_UNIT): PrivilegeDepth.BUSINESS_UNIT,
    int(PrivilegeDepth.PARENT_CHILD): PrivilegeDepth.PARENT_CHILD,
    int(PrivilegeDepth.GLOBAL): PrivilegeDepth.GLOBAL,
}


def privilege_name(right: AccessRight, schema_name: str) -> str:
    """``prvReadnew_FpSmokeA`` — privilege names use the entity SchemaName."""
    return f"{_RIGHT_PREFIX[right]}{schema_name}"


def mask_to_depth(mask: Any) -> Optional[PrivilegeDepth]:
    """Map a ``privilegedepthmask`` int to a :class:`PrivilegeDepth`.

    A single-bit mask maps directly. A combined/unknown mask maps to its highest set
    depth (or ``None`` if it carries no recognized depth bit).
    """
    try:
        m = int(mask)
    except (TypeError, ValueError):
        return None
    if m in _DEPTH_BY_MASK:
        return _DEPTH_BY_MASK[m]
    for depth in (
        PrivilegeDepth.GLOBAL,
        PrivilegeDepth.PARENT_CHILD,
        PrivilegeDepth.BUSINESS_UNIT,
        PrivilegeDepth.USER,
    ):
        if m & int(depth):
            return depth
    return None


def _resolve_table_rights(
    client: Any, role_id: str, table_priv: TablePrivilege
) -> tuple[dict[str, tuple[AccessRight, PrivilegeDepth]], dict[str, dict[str, Any]]]:
    """Resolve desired (privilegeid -> (right, depth)) and the current roleprivileges
    (privilegeid -> record) for one table."""
    schema = client.get_entity_schema_name(table_priv.table)
    desired: dict[str, tuple[AccessRight, PrivilegeDepth]] = {}
    for right, depth in table_priv.rights.items():
        priv = client.get_privilege_by_name(privilege_name(right, schema))
        if priv is None:
            logger.warning(
                f"role: privilege not found for {table_priv.table}.{right.name} "
                f"({privilege_name(right, schema)})"
            )
            continue
        desired[priv["privilegeid"]] = (right, depth)
    current = {
        rp["privilegeid"]: rp
        for rp in client.get_role_privileges(role_id, list(desired.keys()))
    }
    return desired, current


def deploy_role(
    client: Any,
    role: SecurityRole,
    *,
    prefix: str = "new",
    config: Any = None,
) -> dict[str, Any]:
    """Upsert a role's table privileges (non-destructive). Raises if the role is missing.

    Returns ``{id, role, tables: [{table, action, rights: [{right, action, depth?}]}]}``.
    """
    existing = client.get_role_by_name(role.name)
    if existing is None:
        raise ValueError(
            f"Role '{role.name}' not found in the environment; create it manually first."
        )
    role_id = existing["roleid"]

    result: dict[str, Any] = {"id": role_id, "role": role.name, "tables": []}
    for table_priv in role.table_privileges:
        if not is_custom(table_priv.table, prefix):
            result["tables"].append(
                {"table": table_priv.table, "action": "skipped_standard"}
            )
            continue
        result["tables"].append(_sync_table(client, role_id, table_priv))
    return result


def _sync_table(client: Any, role_id: str, table_priv: TablePrivilege) -> dict[str, Any]:
    desired, current = _resolve_table_rights(client, role_id, table_priv)
    rights_out: list[dict[str, Any]] = []
    for pid, (right, depth) in desired.items():
        mask = int(depth)
        rec = current.get(pid)
        if rec is not None:
            if rec.get("privilegedepthmask") == mask:
                rights_out.append({"right": right.name, "action": "skipped"})
            else:
                client.update_role_privilege(
                    rec["roleprivilegeid"], {"privilegedepthmask": mask}
                )
                rights_out.append(
                    {"right": right.name, "action": "updated", "depth": depth.name}
                )
        else:
            client.create_role_privilege(
                {
                    "roleid@odata.bind": f"/roles({role_id})",
                    "privilegeid@odata.bind": f"/privileges({pid})",
                    "privilegedepthmask": mask,
                }
            )
            rights_out.append(
                {"right": right.name, "action": "created", "depth": depth.name}
            )
    return {"table": table_priv.table, "action": "synced", "rights": rights_out}


def plan_role(
    client: Any, role: SecurityRole, *, prefix: str = "new"
) -> dict[str, Any]:
    """Read-only preview of ``deploy_role`` (all ``would_*`` actions; no writes)."""
    existing = client.get_role_by_name(role.name)
    if existing is None:
        return {"role": role.name, "action": "missing", "tables": []}
    role_id = existing["roleid"]
    result: dict[str, Any] = {"id": role_id, "role": role.name, "tables": []}
    for table_priv in role.table_privileges:
        if not is_custom(table_priv.table, prefix):
            result["tables"].append({"table": table_priv.table, "action": "would_skip_standard"})
            continue
        desired, current = _resolve_table_rights(client, role_id, table_priv)
        rights_out: list[dict[str, Any]] = []
        for pid, (right, depth) in desired.items():
            rec = current.get(pid)
            if rec is None:
                rights_out.append({"right": right.name, "action": "would_create", "depth": depth.name})
            elif rec.get("privilegedepthmask") != int(depth):
                rights_out.append({"right": right.name, "action": "would_update", "depth": depth.name})
            else:
                rights_out.append({"right": right.name, "action": "would_skip"})
        result["tables"].append({"table": table_priv.table, "action": "would_sync", "rights": rights_out})
    return result
