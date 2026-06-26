"""Unit tests for framework_power.role_registry (definition discovery)."""

import pytest

from framework_power.role_registry import (
    DEFAULT_ROLES_DIR,
    discover_role_definitions,
    get_role_definition,
)

pytestmark = pytest.mark.unit

_ROLE_PY = (
    "from framework_power import AccessRight, PrivilegeDepth, SecurityRole, TablePrivilege\n"
    "ROLE: SecurityRole = SecurityRole(\n"
    "    name='Test Role',\n"
    "    table_privileges=[TablePrivilege(table='new_fpsmokea', rights={AccessRight.READ: PrivilegeDepth.USER})],\n"
    ")\n"
)


def test_default_roles_dir():
    assert DEFAULT_ROLES_DIR == "metadata_py/roles"


def test_discover_and_get(tmp_path):
    (tmp_path / "test_role.py").write_text(_ROLE_PY, encoding="utf-8")
    defs = discover_role_definitions(str(tmp_path))
    assert "test_role" in defs
    defn = get_role_definition("test_role", str(tmp_path))
    assert defn.role.name == "Test Role"
    assert defn.role.table_privileges[0].table == "new_fpsmokea"


def test_get_missing_raises(tmp_path):
    with pytest.raises(KeyError):
        get_role_definition("nope", str(tmp_path))


def test_discover_ignores_underscore_files(tmp_path):
    (tmp_path / "_skip.py").write_text(_ROLE_PY, encoding="utf-8")
    (tmp_path / "real.py").write_text(_ROLE_PY, encoding="utf-8")
    defs = discover_role_definitions(str(tmp_path))
    assert "real" in defs and "_skip" not in defs
