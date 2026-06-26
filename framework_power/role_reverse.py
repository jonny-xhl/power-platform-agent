"""
Security-role privilege reverse exporter (framework_power Phase 3).

``reverse_role`` reads an EXISTING role's table privileges from the environment into a
:class:`SecurityRole`, **scoped to a provided list of tables**. It never pulls all
tables: for each requested table it resolves that table's 8 privilege ids (by name) and
fetches only those roleprivileges server-side.

``tables`` is REQUIRED — omitting it raises (refuses to pull the whole org).
"""

from __future__ import annotations

import logging
from typing import Any

from .components.models import AccessRight, SecurityRole, TablePrivilege
from .role_deployer import mask_to_depth, privilege_name

logger = logging.getLogger(__name__)


def reverse_role(client: Any, role_name: str, *, tables: list[str]) -> SecurityRole:
    """Build a :class:`SecurityRole` from a role's privileges, scoped to ``tables``.

    Args:
        client: An authenticated ``DataverseClient``.
        role_name: The role's name (must already exist).
        tables: REQUIRED list of table logical names to capture privileges for.

    Raises:
        ValueError: If ``tables`` is empty, or the role is not found.
    """
    if not tables:
        raise ValueError("--tables is required; refusing to pull every table's privileges.")

    existing = client.get_role_by_name(role_name)
    if existing is None:
        raise ValueError(f"Role '{role_name}' not found in the environment.")
    role_id = existing["roleid"]

    table_privileges: list[TablePrivilege] = []
    for table in tables:
        schema = client.get_entity_schema_name(table)
        # Resolve the privilege id for every right on this table.
        pid_by_right: dict[AccessRight, str] = {}
        for right in AccessRight:
            priv = client.get_privilege_by_name(privilege_name(right, schema))
            if priv is not None:
                pid_by_right[right] = priv["privilegeid"]
        if not pid_by_right:
            logger.debug(f"role reverse: no privileges resolved for table '{table}'")
            continue
        current = {
            rp["privilegeid"]: rp
            for rp in client.get_role_privileges(role_id, list(pid_by_right.values()))
        }
        rights = {
            right: depth
            for right, pid in pid_by_right.items()
            if (rp := current.get(pid))
            and (depth := mask_to_depth(rp.get("privilegedepthmask"))) is not None
        }
        if rights:
            table_privileges.append(TablePrivilege(table=table, rights=rights))

    return SecurityRole(name=role_name, table_privileges=table_privileges)
