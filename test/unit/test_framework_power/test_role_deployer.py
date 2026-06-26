"""Unit tests for framework_power.role_deployer (fake client, no network)."""

from typing import Any, Optional

import pytest

from framework_power import AccessRight, PrivilegeDepth, SecurityRole, TablePrivilege
from framework_power.role_deployer import (
    deploy_role,
    mask_to_depth,
    plan_role,
    privilege_name,
)

pytestmark = pytest.mark.unit


def _role(**tables) -> SecurityRole:
    tps = [TablePrivilege(table=t, rights=r) for t, r in tables.items()]
    return SecurityRole(name="Test Role", table_privileges=tps)


_DEPTH_MASK = {"Basic": 1, "Local": 2, "Deep": 4, "Global": 8}


class RoleFakeClient:
    """Tracks roleprivilege state so upsert + re-read can be exercised."""

    def __init__(self, role_exists: bool = True, current: Optional[dict[str, int]] = None) -> None:
        self.role_exists = role_exists
        self.role_id = "role-1"
        self._masks: dict[str, int] = dict(current or {})
        self.added: list[list[dict[str, Any]]] = []  # add_privileges_to_role calls

    def get_role_by_name(self, name: str) -> Optional[dict[str, Any]]:
        return {"roleid": self.role_id, "name": name} if self.role_exists else None

    def get_entity_schema_name(self, logical: str) -> str:
        return {"new_fpsmokea": "new_FpSmokeA"}.get(logical, logical)

    def get_privilege_by_name(self, name: str) -> Optional[dict[str, Any]]:
        return {"name": name, "privilegeid": "pid:" + name}

    def get_role_privileges(self, role_id: str, privilege_ids: Optional[list[str]] = None):
        return [
            {"roleprivilegeid": "rp:" + pid, "privilegeid": pid, "privilegedepthmask": m}
            for pid, m in self._masks.items()
            if privilege_ids is None or pid in privilege_ids
        ]

    def add_privileges_to_role(self, role_id: str, privileges: list[dict[str, Any]]) -> dict[str, Any]:
        self.added.append(privileges)
        for p in privileges:
            self._masks[p["PrivilegeId"]] = _DEPTH_MASK[p["Depth"]]
        return {"synced": True, "count": len(privileges)}


def test_privilege_name_uses_schema_name():
    assert privilege_name(AccessRight.READ, "new_FpSmokeA") == "prvReadnew_FpSmokeA"
    assert privilege_name(AccessRight.APPEND_TO, "new_FpSmokeA") == "prvAppendTonew_FpSmokeA"


def test_mask_to_depth():
    assert mask_to_depth(1) == PrivilegeDepth.USER
    assert mask_to_depth(2) == PrivilegeDepth.BUSINESS_UNIT
    assert mask_to_depth(4) == PrivilegeDepth.PARENT_CHILD
    assert mask_to_depth(8) == PrivilegeDepth.GLOBAL
    assert mask_to_depth(None) is None


def test_deploy_missing_role_raises():
    client = RoleFakeClient(role_exists=False)
    with pytest.raises(ValueError):
        deploy_role(client, _role(new_fpsmokea={AccessRight.READ: PrivilegeDepth.USER}), prefix="new")


def test_deploy_creates_privilege():
    client = RoleFakeClient(current={})
    res = deploy_role(
        client, _role(new_fpsmokea={AccessRight.READ: PrivilegeDepth.USER}), prefix="new"
    )
    assert res["id"] == "role-1"
    assert client.added  # AddPrivilegesRole was called
    assert client.added[0][0] == {"PrivilegeId": "pid:prvReadnew_FpSmokeA", "Depth": "Basic"}
    # state updated to USER (Basic -> mask 1)
    assert client._masks["pid:prvReadnew_FpSmokeA"] == 1


def test_deploy_updates_depth_when_differs():
    pid = "pid:prvReadnew_FpSmokeA"
    client = RoleFakeClient(current={pid: 2})  # currently BU
    deploy_role(client, _role(new_fpsmokea={AccessRight.READ: PrivilegeDepth.USER}), prefix="new")
    assert client.added  # upsert call
    assert client._masks[pid] == 1  # Basic


def test_deploy_skips_when_depth_same():
    pid = "pid:prvReadnew_FpSmokeA"
    client = RoleFakeClient(current={pid: 1})
    deploy_role(client, _role(new_fpsmokea={AccessRight.READ: PrivilegeDepth.USER}), prefix="new")
    assert not client.added  # no call needed (already USER)


def test_deploy_skips_standard_table():
    client = RoleFakeClient()
    res = deploy_role(client, _role(account={AccessRight.READ: PrivilegeDepth.USER}), prefix="new")
    assert res["tables"][0]["action"] == "skipped_standard"
    assert not client.added


def test_deploy_is_non_destructive_unlisted_right_untouched():
    write_pid = "pid:prvWritenew_FpSmokeA"
    client = RoleFakeClient(current={write_pid: 1})  # WRITE already present
    deploy_role(client, _role(new_fpsmokea={AccessRight.READ: PrivilegeDepth.USER}), prefix="new")
    assert write_pid in client._masks and client._masks[write_pid] == 1  # untouched


def test_plan_is_read_only():
    client = RoleFakeClient(current={})
    res = plan_role(client, _role(new_fpsmokea={AccessRight.READ: PrivilegeDepth.USER}), prefix="new")
    assert not client.added  # plan makes no writes
    table = res["tables"][0]
    assert table["action"] == "would_sync"
    assert table["rights"][0]["action"] == "would_create"


def test_plan_missing_role_reports_missing():
    res = plan_role(RoleFakeClient(role_exists=False), _role(new_fpsmokea={AccessRight.READ: PrivilegeDepth.USER}), prefix="new")
    assert res["action"] == "missing"
