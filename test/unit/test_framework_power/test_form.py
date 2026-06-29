"""Unit tests for framework_power.components.form (structured Form model, Phase 5)."""

import pytest

import framework_power.components.form as form_mod
import framework_power.form_xml as fx
from framework_power import Form, FormType, Label
from framework_power.models import AttributeType, Column

pytestmark = pytest.mark.unit


def _model() -> Form:
    """A representative custom Main form with a field, a library, and an onload handler."""
    form = fx.new_form("new_Budget Main", "new_budget", description="main form")
    form = fx.add_field(
        form,
        Column(schema_name="new_Name", type=AttributeType.String, display_name=Label.zh("名称")),
        tab_name="GENERAL_TAB",
        section_name="General_Section",
    )
    form = fx.add_library(form, "new_/js/budget.js")
    form = fx.add_event_handler(form, "onload", "Onload", "new_/js/budget.js", pass_execution_context=True)
    return form


class FakeClient:
    def __init__(self, existing=None) -> None:
        self._existing = existing
        self.created = []
        self.updated = []

    def get_form_by_name(self, entity, name, *, form_type=None):
        return dict(self._existing) if self._existing else None

    def create_form(self, payload):
        self.created.append(payload)
        return {"formid": "f-id", "name": payload["name"]}

    def update_form(self, form_id, patch):
        self.updated.append((form_id, patch))
        return {"updated": True, "formid": form_id}


def test_serialize_uses_structured_formxml():
    p = form_mod.serialize(_model())
    assert p["name"] == "new_Budget Main"
    assert p["objecttypecode"] == "new_budget"
    assert p["type"] == 2
    assert p["description"] == "main form"
    # formxml is regenerated from the structured model and contains the field/handler
    assert 'datafieldname="new_name"' in p["formxml"]
    assert 'functionName="Onload"' in p["formxml"]


def test_deploy_creates_when_absent():
    c = FakeClient(existing=None)
    assert form_mod.deploy(c, _model(), prefix="new")["action"] == "created"
    assert c.created


def test_deploy_updates_when_present():
    c = FakeClient(existing={"formid": "f-id"})
    out = form_mod.deploy(c, _model(), prefix="new")
    assert out["action"] == "updated"
    assert c.updated and "formxml" in c.updated[0][1]


def test_deploy_skips_standard():
    form = fx.new_form("Information", "account")
    assert form_mod.deploy(FakeClient(), form, prefix="new")["action"] == "skipped_standard"


def test_deploy_nonprefixed_name_on_custom_entity():
    # An auto-created form ("Information") on a CUSTOM table is editable even though its
    # generic name lacks the publisher prefix (entity-based customness).
    form = fx.new_form("Information", "new_fpformsmoke")
    assert form_mod.deploy(FakeClient(existing=None), form, prefix="new")["action"] == "created"
    assert form_mod.plan(FakeClient(existing={"formid": "f-id"}), form, prefix="new")["action"] == "would_update"


def test_lookup_disambiguates_by_form_type():
    # Auto-created forms share the name "Information" (Main/QuickView/Card); the lookup
    # must filter by type so deploy targets the right one.
    seen = {}

    class C:
        def get_form_by_name(self, entity, name, *, form_type=None):
            seen["form_type"] = form_type
            return {"formid": "main-id"} if form_type == 2 else None

    form = fx.new_form("Information", "new_fpformsmoke")  # Main (type 2)
    assert form_mod.resolve_id(C(), form) == "main-id"
    assert seen["form_type"] == 2


def test_resolve_id():
    assert form_mod.resolve_id(FakeClient(existing={"formid": "f-id"}), _model()) == "f-id"


def test_plan():
    assert form_mod.plan(FakeClient(existing=None), _model(), prefix="new")["action"] == "would_create"
    assert form_mod.plan(FakeClient(existing={"formid": "f-id"}), _model(), prefix="new")["action"] == "would_update"


def test_reverse_parses_formxml():
    class C:
        def get_form_by_id(self, oid):
            return {
                "name": "new_Budget Main", "objecttypecode": "new_budget",
                "formxml": fx.to_formxml(_model()), "type": 2, "description": "d",
            }

    m = form_mod.reverse(C(), "f-id")
    assert m.name == "new_Budget Main"
    assert m.entity == "new_budget"
    assert m.form_type == FormType.Main
    assert m.libraries and m.libraries[0].name == "new_/js/budget.js"
    # the onload handler round-trips (non-internal)
    onload = [h for ev in m.events if ev.name == "onload" for h in ev.handlers if not h.internal]
    assert onload and onload[0].function_name == "Onload"


def test_codegen_round_trip():
    import framework_power.components.models as M

    m = _model()
    src = form_mod.codegen(m)
    compile(src, "f", "eval")
    ns = {name: getattr(M, name) for name in form_mod.CODEGEN_IMPORTS}
    assert eval(src, ns) == m


def test_lint_flags_missing_entity():
    form = fx.new_form("new_X", "")
    issues = form_mod.lint(form, prefix="new")
    assert any("entity" in i.message.lower() for i in issues)


def test_lint_flags_non_editable_type():
    form = fx.new_form("new_Card", "new_x", form_type=FormType.Card)
    issues = form_mod.lint(form, prefix="new")
    assert any("editable" in i.message.lower() for i in issues)
