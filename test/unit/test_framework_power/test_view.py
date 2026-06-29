"""Unit tests for framework_power.components.view (structured View model, Phase 6)."""

import pytest

import framework_power.components.view as view_mod
import framework_power.view_xml as vx
from framework_power import QueryType, View

pytestmark = pytest.mark.unit


def _model() -> View:
    """A representative custom Public view with columns, a sort, and a filter."""
    v = vx.new_view("new_Active Budgets", "new_budget",
                    primary_id="new_budgetid", object_type_code=10000, description="active")
    v = vx.add_column(v, "new_name", width=200)
    v = vx.add_column(v, "new_amount")
    v = vx.add_order(v, "new_name")
    v = vx.add_condition(v, "statecode", "eq", value="0")
    return v


class FakeClient:
    def __init__(self, existing=None) -> None:
        self._existing = existing
        self.created = []
        self.updated = []

    def get_view_by_name(self, entity, name, *, query_type=None):
        return dict(self._existing) if self._existing else None

    def create_view(self, payload):
        self.created.append(payload)
        return {"savedqueryid": "v-id", "name": payload["name"]}

    def update_view(self, savedquery_id, patch):
        self.updated.append((savedquery_id, patch))
        return {"updated": True, "savedqueryid": savedquery_id}


def test_serialize_uses_structured_xml():
    p = view_mod.serialize(_model())
    assert p["name"] == "new_Active Budgets"
    assert p["returnedtypecode"] == "new_budget"
    assert p["querytype"] == 0
    assert 'attribute name="new_name"' in p["fetchxml"]
    assert 'attribute name="new_budgetid"' in p["fetchxml"]
    assert 'condition attribute="statecode"' in p["fetchxml"]
    assert 'cell name="new_name" width="200"' in p["layoutxml"]
    assert 'object="10000"' in p["layoutxml"]


def test_deploy_creates_when_absent():
    c = FakeClient(existing=None)
    assert view_mod.deploy(c, _model(), prefix="new")["action"] == "created"
    assert c.created


def test_deploy_updates_when_present():
    c = FakeClient(existing={"savedqueryid": "v-id"})
    out = view_mod.deploy(c, _model(), prefix="new")
    assert out["action"] == "updated"
    assert c.updated and "fetchxml" in c.updated[0][1] and "layoutxml" in c.updated[0][1]


def test_deploy_skips_standard_entity():
    v = vx.new_view("Active Accounts", "account", primary_id="accountid", object_type_code=1)
    assert view_mod.deploy(FakeClient(), v, prefix="new")["action"] == "skipped_standard"


def test_resolve_id():
    assert view_mod.resolve_id(FakeClient(existing={"savedqueryid": "v-id"}), _model()) == "v-id"


def test_plan():
    assert view_mod.plan(FakeClient(existing=None), _model(), prefix="new")["action"] == "would_create"
    assert (
        view_mod.plan(FakeClient(existing={"savedqueryid": "v-id"}), _model(), prefix="new")["action"]
        == "would_update"
    )


def test_reverse_parses_xml():
    class C:
        def get_view_by_id(self, oid):
            m = _model()
            return {
                "name": "new_Active Budgets", "returnedtypecode": "new_budget",
                "fetchxml": vx.to_fetchxml(m), "layoutxml": vx.to_layoutxml(m),
                "querytype": 0, "description": "d", "isdefault": False,
            }

    m = view_mod.reverse(C(), "v-id")
    assert m.name == "new_Active Budgets"
    assert m.entity == "new_budget"
    assert m.query_type == QueryType.Public
    assert m.primary_id == "new_budgetid"
    assert m.object_type_code == 10000
    assert [c.name for c in m.columns] == ["new_name", "new_amount"]


def test_codegen_round_trip():
    import framework_power.components.models as M

    m = _model()
    src = view_mod.codegen(m)
    compile(src, "v", "eval")
    ns = {name: getattr(M, name) for name in view_mod.CODEGEN_IMPORTS}
    assert eval(src, ns) == m


def test_lint_flags_missing_primary_id():
    v = View(name="new_X", entity="new_budget", object_type_code=10000)
    issues = view_mod.lint(v, prefix="new")
    assert any("primary_id" in i.message for i in issues)


def test_lint_flags_dotted_column_unknown_alias():
    v = vx.new_view("new_X", "new_budget", primary_id="new_budgetid", object_type_code=10000)
    v = vx.add_column(v, "unknown_alias.field")
    issues = view_mod.lint(v, prefix="new")
    assert any("unknown link-entity alias" in i.message for i in issues)
