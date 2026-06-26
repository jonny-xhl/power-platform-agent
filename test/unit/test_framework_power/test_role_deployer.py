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


class RoleFakeClient:
    """Tracks roleprivilege state so upsert + re-read can be exercised."""

    def __init__(self, role_exists: bool = True, current: Optional[dict[str, int]] = None) -> None:
        self.role_exists = role_exists
        self.role_id = "role-1"
        self._masks: dict[str, int] = dict(current or {})
        self.created: list[dict[str, Any]] = []
        self.updated: list[tuple[str, dict[str, Any]]] = []

    def get_role_by_name(self, name: str) -> Optional[dict[str, Any]]:
        return {"roleid": self.role_id, "name": name} if self.role_exists else None

    def get_entity_schema_name(self, logical: str) -> str:
        return {"new_fpsmokea": "new_FpSmokeA"}.get(logical, logical)

    def get_privilege_by_name(self, name: str) -> Optional[dict[str, Any]]:
        return {"name": name, "privilegeid": "pid:" + name}

    def get_role_privileges(self, role_id: str, privilege_ids: Optional[list[str]] = None):
        out = []
        for pid, mask in self._masks.items():
            if privilege_ids is None or pid in privilege_ids:
                out.append(
                    {"roleprivilegeid": "rp:" + pid, "privilegeid": pid, "privilegedepthmask": mask}
                )
        return out

    def create_role_privilege(self, payload: dict[str, Any]) -> dict[str, Any]:
        pid = payload["privilegeid@odata.bind"].split("(")[-1].rstrip(")")
        self._masks[pid] = payload["privilegedepthmask"]
        self.created.append(payload)
        return {"roleprivilegeid": "rp:" + pid}

    def update_role_privilege(self, roleprivilege_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        pid = roleprivilege_id.split(":", 1)[1]
        self._masks[pid] = patch["privilegedepthmask"]
        self.updated.append((roleprivilege_id, patch))
        return {"updated": True}


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
    assert client.created
    payload = client.created[0]
    assert payload["privilegedepthmask"] == 1
    assert payload["roleid@odata.bind"] == "/roles(role-1)"


def test_deploy_updates_depth_when_differs():
    pid = "pid:prvReadnew_FpSmokeA"
    client = RoleFakeClient(current={pid: 2})  # currently BU
    deploy_role(client, _role(new_fpsmokea={AccessRight.READ: PrivilegeDepth.USER}), prefix="new")
    assert client.updated and client.updated[0][1]["privilegedepthmask"] == 1
    assert not client.created


def test_deploy_skips_when_depth_same():
    pid = "pid:prvReadnew_FpSmokeA"
    client = RoleFakeClient(current={pid: 1})
    deploy_role(client, _role(new_fpsmokea={AccessRight.READ: PrivilegeDepth.USER}), prefix="new")
    assert not client.created and not client.updated


def test_deploy_skips_standard_table():
    client = RoleFakeClient()
    res = deploy_role(client, _role(account={AccessRight.READ: PrivilegeDepth.USER}), prefix="new")
    assert res["tables"][0]["action"] == "skipped_standard"
    assert not client.created


def test_deploy_is_non_destructive_unlisted_right_untouched():
    write_pid = "pid:prvWritenew_FpSmokeA"
    client = RoleFakeClient(current={write_pid: 1})  # WRITE already present
    deploy_role(client, _role(new_fpsmokea={AccessRight.READ: PrivilegeDepth.USER}), prefix="new")
    # WRITE privilege still present and untouched
    assert write_pid in client._masks and client._masks[write_pid] == 1
    assert not client.updated  # READ was created, WRITE not touched


def test_plan_is_read_only():
    client = RoleFakeClient(current={})
    res = plan_role(client, _role(new_fpsmokea={AccessRight.READ: PrivilegeDepth.USER}), prefix="new")
    assert not client.created and not client.updated
    table = res["tables"][0]
    assert table["action"] == "would_sync"
    assert table["rights"][0]["action"] == "would_create"


def test_plan_missing_role_reports_missing():
    res = plan_role(RoleFakeClient(role_exists=False), _role(new_fpsmokea={AccessRight.READ: PrivilegeDepth.USER}), prefix="new")
    assert res["action"] == "missing"
