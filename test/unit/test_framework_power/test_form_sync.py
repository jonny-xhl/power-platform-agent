"""Unit tests for framework_power.form_sync (fake client, no network)."""

from pathlib import Path

import pytest

import framework_power.form_xml as fx
from framework_power.components import form as form_mod
from framework_power.form_sync import plan_forms, reverse_forms, sync_forms

pytestmark = pytest.mark.unit

SAMPLE_XML = (
    '<form showImage="true"><tabs><tab name="T1" id="{t1}" showlabel="true" expanded="true">'
    '<labels><label description="信息" languagecode="2052" /></labels>'
    '<columns><column width="100%"><sections><section name="S1" id="{s1}" columns="1" showlabel="true">'
    '<labels><label description="基本信息" languagecode="2052" /></labels>'
    '<rows><row><cell id="{c1}" showlabel="true">'
    '<labels><label description="名称" languagecode="2052" /></labels>'
    '<control id="name" classid="{4273EDBD-AC1D-40d3-9FB2-095C621B552D}" '
    'datafieldname="name" disabled="false" />'
    '</cell></row></rows></section></sections></column></columns></tab></tabs>'
    '<formLibraries><Library name="new_lib.js" libraryUniqueId="{lib1}" /></formLibraries>'
    '<events><event name="onload" application="true" active="true">'
    '<Handlers><Handler functionName="Onload" libraryName="new_lib.js" handlerUniqueId="{h1}" '
    'enabled="true" parameters="" passExecutionContext="true" /></Handlers>'
    '</event></events></form>'
)


class FormSyncFakeClient:
    def __init__(self, *, existing=True, formxml=SAMPLE_XML, name="new_X", entity="new_x"):
        self._existing = existing
        self._formxml = formxml
        self._name = name
        self._entity = entity
        self.created = []
        self.updated = []
        self.published_entities = []
        self.added = []

    def get_form_by_name(self, entity, name, *, form_type=None):
        if not self._existing or entity != self._entity or name != self._name:
            return None
        return {"formid": "fid", "name": name, "objecttypecode": entity}

    def get_form_by_id(self, fid):
        return {
            "formid": fid, "name": self._name, "objecttypecode": self._entity,
            "formxml": self._formxml, "type": 2, "description": "",
        }

    def create_form(self, payload):
        self.created.append(payload)
        return {"formid": "newid", "name": payload["name"]}

    def update_form(self, fid, patch):
        self.updated.append((fid, patch))
        return {"updated": True, "formid": fid}

    def publish_entity(self, entity):
        self.published_entities.append(entity)
        return {"published": True, "entity": entity}

    def add_solution_component(self, sol, code, oid):
        self.added.append((sol, code, oid))
        return {"added": True}

    def list_forms_by_entity(self, entity):
        return [self.get_form_by_id("fid")] if self._existing and entity == self._entity else []


# ----------------------------------------------------------------- plan


def test_plan_would_create_when_absent():
    fake = FormSyncFakeClient(existing=False)
    authored = fx.new_form("new_X", "new_x")
    res = plan_forms(fake, [authored], prefix="new")
    assert res["forms"][0]["plan"]["action"] == "would_create"


def test_plan_would_skip_when_unchanged():
    fake = FormSyncFakeClient()  # live form with SAMPLE_XML
    live = form_mod.reverse(fake, "fid")  # the exact model currently live
    res = plan_forms(fake, [live], prefix="new")
    assert res["forms"][0]["plan"]["action"] == "would_skip"


def test_plan_would_update_when_changed():
    fake = FormSyncFakeClient()  # live has rich SAMPLE_XML
    authored = fx.new_form("new_X", "new_x")  # different (empty) -> changed
    res = plan_forms(fake, [authored], prefix="new")
    assert res["forms"][0]["plan"]["action"] == "would_update"


# ----------------------------------------------------------------- sync


def test_sync_creates_and_publishes_entity():
    fake = FormSyncFakeClient(existing=False)
    authored = fx.new_form("new_X", "new_x")
    res = sync_forms(fake, [authored], prefix="new", publish=True)
    assert res["synced"][0]["deploy"]["action"] == "created"
    assert fake.created
    assert fake.published_entities == ["new_x"]  # entity-scoped publish


def test_sync_noop_when_unchanged():
    fake = FormSyncFakeClient()
    live = form_mod.reverse(fake, "fid")
    res = sync_forms(fake, [live], prefix="new", publish=True)
    assert res["synced"][0]["deploy"]["action"] == "skipped_unchanged"
    assert not fake.updated            # never PATCHed
    assert fake.published_entities == []  # nothing changed -> no publish


def test_sync_no_publish_flag():
    fake = FormSyncFakeClient(existing=False)
    authored = fx.new_form("new_X", "new_x")
    res = sync_forms(fake, [authored], prefix="new", publish=False)
    assert res["synced"][0]["deploy"]["action"] == "created"
    assert fake.published_entities == []


def test_sync_solution_add_code_60():
    fake = FormSyncFakeClient(existing=False)
    authored = fx.new_form("new_X", "new_x")
    res = sync_forms(fake, [authored], prefix="new", solution="new_Core", publish=False)
    assert res["added"] and res["added"][0]["action"] == "added"
    assert fake.added and fake.added[0][1] == 60


def test_sync_solution_already_in_is_benign():
    fake = FormSyncFakeClient(existing=False)

    def boom(sol, code, oid):
        raise Exception("The solution component already exists")
    fake.add_solution_component = boom
    authored = fx.new_form("new_X", "new_x")
    res = sync_forms(fake, [authored], prefix="new", solution="new_Core", publish=False)
    assert res["added"][0]["action"] == "already_in_solution"


# ----------------------------------------------------------------- reverse


def test_reverse_writes_python_file(tmp_path):
    fake = FormSyncFakeClient()
    res = reverse_forms(fake, "new_x", out_dir=tmp_path, prefix="new")
    assert res["written"]
    path = Path(res["written"][0]["path"])
    assert path.exists() and path.suffix == ".py"
    # the written file re-imports to a Form equal to the live model
    ns = {}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), ns)
    written_form = ns["FORM"]
    assert written_form == form_mod.reverse(fake, "fid")
