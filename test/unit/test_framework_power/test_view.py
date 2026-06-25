"""Unit tests for framework_power.components.view (fake client)."""

import pytest

import framework_power.components.view as view_mod
from framework_power import QueryType, View

pytestmark = pytest.mark.unit

FETCHXML = "<fetch><entity name='new_budget'/></fetch>"
LAYOUTXML = "<grid><row/></grid>"


def _model() -> View:
    return View(
        name="new_Active Budgets",
        entity="new_budget",
        fetch_xml=FETCHXML,
        layout_xml=LAYOUTXML,
        query_type=QueryType.Public,
        is_default=True,
    )


class FakeClient:
    def __init__(self, existing=None) -> None:
        self._existing = existing
        self.created = []
        self.updated = []

    def get_view_by_name(self, entity, name):
        return dict(self._existing) if self._existing else None

    def create_view(self, payload):
        self.created.append(payload)
        return {"savedqueryid": "v-id", "name": payload["name"]}

    def update_view(self, savedquery_id, patch):
        self.updated.append((savedquery_id, patch))
        return {"updated": True, "savedqueryid": savedquery_id}


def test_serialize_keys():
    p = view_mod.serialize(_model())
    assert p["name"] == "new_Active Budgets"
    assert p["returnedtypecode"] == "new_budget"
    assert p["fetchxml"] == FETCHXML
    assert p["layoutxml"] == LAYOUTXML
    assert p["querytype"] == 0
    assert p["isdefault"] is True


def test_deploy_creates_when_absent():
    c = FakeClient(existing=None)
    assert view_mod.deploy(c, _model(), prefix="new")["action"] == "created"
    assert c.created


def test_deploy_updates_when_present():
    c = FakeClient(existing={"savedqueryid": "v-id"})
    assert view_mod.deploy(c, _model(), prefix="new")["action"] == "updated"
    assert c.updated and c.updated[0][1]["layoutxml"] == LAYOUTXML


def test_deploy_skips_standard():
    m = View(name="Active Accounts", entity="account", fetch_xml=FETCHXML, layout_xml=LAYOUTXML)
    assert view_mod.deploy(FakeClient(), m, prefix="new")["action"] == "skipped_standard"


def test_resolve_id():
    assert view_mod.resolve_id(FakeClient(existing={"savedqueryid": "v-id"}), _model()) == "v-id"


def test_plan():
    assert view_mod.plan(FakeClient(existing=None), _model(), prefix="new")["action"] == "would_create"
    assert view_mod.plan(FakeClient(existing={"savedqueryid": "v-id"}), _model(), prefix="new")["action"] == "would_update"


def test_reverse_preserves_opaque_xml():
    class C:
        def get_view_by_id(self, oid):
            return {
                "name": "new_Active Budgets", "returnedtypecode": "new_budget",
                "fetchxml": FETCHXML, "layoutxml": LAYOUTXML, "querytype": 0,
                "isdefault": True, "description": "d",
            }

    m = view_mod.reverse(C(), "v-id")
    assert m.fetch_xml == FETCHXML
    assert m.layout_xml == LAYOUTXML
    assert m.query_type == QueryType.Public


def test_codegen_round_trip():
    m = _model()
    src = view_mod.codegen(m)
    compile(src, "v", "eval")
    ns = {"View": View, "QueryType": QueryType}
    assert eval(src, ns) == m


def test_lint_flags_empty_xml():
    m = View(name="new_X", entity="new_budget", fetch_xml="", layout_xml="")
    issues = view_mod.lint(m, prefix="new")
    assert any("empty" in i.message.lower() for i in issues)
