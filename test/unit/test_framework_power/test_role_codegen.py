"""Unit tests for framework_power.role_codegen (round-trip)."""

import pytest

from framework_power import AccessRight, PrivilegeDepth, SecurityRole, TablePrivilege
from framework_power.role_codegen import role_to_python_source

pytestmark = pytest.mark.unit


def _round_trip(role: SecurityRole) -> SecurityRole:
    src = role_to_python_source(role)
    compile(src, "role.py", "exec")
    ns: dict = {}
    exec(src, ns)
    return ns["ROLE"]


def test_round_trip_with_privileges():
    role = SecurityRole(
        name="Basic User",
        table_privileges=[
            TablePrivilege(
                table="new_fpsmokea",
                rights={
                    AccessRight.READ: PrivilegeDepth.USER,
                    AccessRight.WRITE: PrivilegeDepth.BUSINESS_UNIT,
                },
            )
        ],
    )
    role2 = _round_trip(role)
    assert role2 == role
    assert role2.table_privileges[0].rights[AccessRight.READ] == PrivilegeDepth.USER


def test_round_trip_empty_role():
    role = SecurityRole(name="Empty Role")
    assert _round_trip(role) == role


def test_emit_contains_expected_constructs():
    role = SecurityRole(
        name="R",
        table_privileges=[TablePrivilege(table="new_x", rights={AccessRight.READ: PrivilegeDepth.GLOBAL})],
    )
    src = role_to_python_source(role)
    assert "AccessRight.READ: PrivilegeDepth.GLOBAL" in src
    assert "TablePrivilege(" in src
    assert "ROLE: SecurityRole" in src
