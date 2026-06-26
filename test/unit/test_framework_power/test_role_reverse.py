"""Unit tests for framework_power.role_reverse (fake client, no network)."""

from typing import Any, Optional

import pytest

from framework_power import AccessRight, PrivilegeDepth
from framework_power.role_reverse import reverse_role

pytestmark = pytest.mark.unit


class ReverseFakeClient:
    def __init__(self, role_exists: bool = True, current: Optional[dict[str, int]] = None) -> None:
        self.role_exists = role_exists
        self.role_id = "role-1"
        self._masks: dict[str, int] = dict(current or {})

    def get_role_by_name(self, name: str):
        return {"roleid": self.role_id, "name": name} if self.role_exists else None

    def get_entity_schema_name(self, logical: str) -> str:
        return {"new_fpsmokea": "new_FpSmokeA"}.get(logical, logical)

    def get_privilege_by_name(self, name: str):
        return {"name": name, "privilegeid": "pid:" + name}

    def get_role_privileges(self, role_id: str, privilege_ids: Optional[list[str]] = None):
        out = []
        for pid, mask in self._masks.items():
            if privilege_ids is None or pid in privilege_ids:
                out.append(
                    {"roleprivilegeid": "rp:" + pid, "privilegeid": pid, "privilegedepthmask": mask}
                )
        return out


def test_tables_required_raises():
    with pytest.raises(ValueError):
        reverse_role(ReverseFakeClient(), "Test Role", tables=[])


def test_missing_role_raises():
    with pytest.raises(ValueError):
        reverse_role(ReverseFakeClient(role_exists=False), "Test Role", tables=["new_fpsmokea"])


def test_reverse_captures_scoped_privileges():
    read_pid = "pid:prvReadnew_FpSmokeA"
    write_pid = "pid:prvWritenew_FpSmokeA"
    client = ReverseFakeClient(current={read_pid: 1, write_pid: 2})  # USER read, BU write
    role = reverse_role(client, "Test Role", tables=["new_fpsmokea"])
    assert role.name == "Test Role"
    assert len(role.table_privileges) == 1
    tp = role.table_privileges[0]
    assert tp.table == "new_fpsmokea"
    assert tp.rights[AccessRight.READ] == PrivilegeDepth.USER
    assert tp.rights[AccessRight.WRITE] == PrivilegeDepth.BUSINESS_UNIT


def test_reverse_omits_absent_rights():
    read_pid = "pid:prvReadnew_FpSmokeA"
    client = ReverseFakeClient(current={read_pid: 1})  # only READ granted
    role = reverse_role(client, "Test Role", tables=["new_fpsmokea"])
    rights = role.table_privileges[0].rights
    assert AccessRight.READ in rights
    assert AccessRight.WRITE not in rights  # absent -> not captured


def test_reverse_codegen_round_trip():
    from framework_power.role_codegen import role_to_python_source

    client = ReverseFakeClient(current={"pid:prvReadnew_FpSmokeA": 1})
    role = reverse_role(client, "Test Role", tables=["new_fpsmokea"])
    src = role_to_python_source(role)
    compile(src, "role.py", "exec")
    ns: dict = {}
    exec(src, ns)
    r2 = ns["ROLE"]
    assert r2 == role
