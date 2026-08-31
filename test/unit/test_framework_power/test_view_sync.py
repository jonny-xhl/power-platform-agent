"""Unit tests for framework_power.view_sync (fake client, no network)."""

from pathlib import Path

import pytest

import framework_power.view_xml as vx
from framework_power.components import view as view_mod
from framework_power.view_sync import plan_views, reverse_views, sync_views

pytestmark = pytest.mark.unit

FETCH = (
    '<fetch version="1.0" mapping="logical"><entity name="new_x">'
    '<attribute name="new_xid" /><attribute name="new_name" />'
    '<order attribute="new_name" descending="false" />'
    '<filter type="and"><condition attribute="statecode" operator="eq" value="0" /></filter>'
    '</entity></fetch>'
)
LAYOUT = (
    '<grid name="resultset" object="100" jump="new_name" select="1" icon="1" preview="1">'
    '<row name="result" id="new_xid"><cell name="new_name" width="200" /></row></grid>'
)


class ViewSyncFakeClient:
    def __init__(self, *, existing=True, fetch=FETCH, layout=LAYOUT, name="new_V", entity="new_x", otc=100):
        self._existing = existing
        self._fetch = fetch
        self._layout = layout
        self._name = name
        self._entity = entity
        self._otc = otc
        self.created = []
        self.updated = []
        self.published_entities = []
        self.added = []

    def get_view_by_name(self, entity, name, *, query_type=None):
        if not self._existing or entity != self._entity or name != self._name:
            return None
        return {"savedqueryid": "vid", "name": name, "returnedtypecode": entity}

    def get_view_by_id(self, sqid):
        return {
            "savedqueryid": sqid, "name": self._name, "returnedtypecode": self._entity,
            "fetchxml": self._fetch, "layoutxml": self._layout, "querytype": 0, "description": "",
        }

    def create_view(self, payload):
        self.created.append(payload)
        return {"savedqueryid": "newid", "name": payload["name"]}

    def update_view(self, sqid, patch):
        self.updated.append((sqid, patch))
        return {"updated": True, "savedqueryid": sqid}

    def publish_entity(self, entity):
        self.published_entities.append(entity)
        return {"published": True, "entity": entity}

    def add_solution_component(self, sol, code, oid):
        self.added.append((sol, code, oid))
        return {"added": True}

    def list_views_by_entity(self, entity):
        return [self.get_view_by_id("vid")] if self._existing and entity == self._entity else []

    def get_object_type_code(self, entity):
        return self._otc


# ----------------------------------------------------------------- plan


def test_plan_would_create_when_absent():
    fake = ViewSyncFakeClient(existing=False)
    authored = vx.new_view("new_V", "new_x", primary_id="new_xid", object_type_code=100)
    res = plan_views(fake, [authored], prefix="new")
    assert res["views"][0]["plan"]["action"] == "would_create"


def test_plan_would_skip_when_unchanged():
    fake = ViewSyncFakeClient()
    live = view_mod.reverse(fake, "vid")
    res = plan_views(fake, [live], prefix="new")
    assert res["views"][0]["plan"]["action"] == "would_skip"


def test_plan_would_update_when_changed():
    fake = ViewSyncFakeClient()
    authored = vx.new_view("new_V", "new_x", primary_id="new_xid", object_type_code=100)  # empty -> differs
    res = plan_views(fake, [authored], prefix="new")
    assert res["views"][0]["plan"]["action"] == "would_update"


# ----------------------------------------------------------------- sync


def test_sync_creates_and_publishes_entity():
    fake = ViewSyncFakeClient(existing=False)
    authored = vx.new_view("new_V", "new_x", primary_id="new_xid", object_type_code=100)
    res = sync_views(fake, [authored], prefix="new", publish=True)
    assert res["synced"][0]["deploy"]["action"] == "created"
    assert fake.created
    assert fake.published_entities == ["new_x"]


def test_sync_noop_when_unchanged():
    fake = ViewSyncFakeClient()
    live = view_mod.reverse(fake, "vid")
    res = sync_views(fake, [live], prefix="new", publish=True)
    assert res["synced"][0]["deploy"]["action"] == "skipped_unchanged"
    assert not fake.updated
    assert fake.published_entities == []


def test_sync_fills_object_type_code():
    fake = ViewSyncFakeClient(existing=False, otc=9999)
    authored = vx.new_view("new_V", "new_x", primary_id="new_xid", object_type_code=0)  # missing
    sync_views(fake, [authored], prefix="new", publish=False)
    assert fake.created[0]["layoutxml"].count('object="9999"') == 1


def test_sync_solution_add_code_26():
    fake = ViewSyncFakeClient(existing=False)
    authored = vx.new_view("new_V", "new_x", primary_id="new_xid", object_type_code=100)
    res = sync_views(fake, [authored], prefix="new", solution="new_Core", publish=False)
    assert res["added"] and res["added"][0]["action"] == "added"
    assert fake.added and fake.added[0][1] == 26


def test_sync_solution_already_in_is_benign():
    fake = ViewSyncFakeClient(existing=False)

    def boom(sol, code, oid):
        raise Exception("The solution component already exists")
    fake.add_solution_component = boom
    authored = vx.new_view("new_V", "new_x", primary_id="new_xid", object_type_code=100)
    res = sync_views(fake, [authored], prefix="new", solution="new_Core", publish=False)
    assert res["added"][0]["action"] == "already_in_solution"


# ----------------------------------------------------------------- reverse


def test_reverse_writes_python_file(tmp_path):
    fake = ViewSyncFakeClient()
    res = reverse_views(fake, "new_x", out_dir=tmp_path, prefix="new")
    assert res["written"]
    path = Path(res["written"][0]["path"])
    assert path.exists() and path.suffix == ".py"
    ns = {}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), ns)
    # compact codegen: file omits rebuildable attrs -> compare normalized
    from framework_power.components.compact import normalize
    assert normalize(ns["VIEW"]) == normalize(view_mod.reverse(fake, "vid"))
