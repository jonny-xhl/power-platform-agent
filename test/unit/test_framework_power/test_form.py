"""Unit tests for framework_power.components.form (fake client)."""

import pytest

import framework_power.components.form as form_mod
from framework_power import Form, FormType

pytestmark = pytest.mark.unit

FORMXML = "<forms><form><tabs/></form></forms>"


def _model() -> Form:
    return Form(
        name="new_Budget Main",
        entity="new_budget",
        form_xml=FORMXML,
        form_type=FormType.Main,
        description="main form",
    )


class FakeClient:
    def __init__(self, existing=None) -> None:
        self._existing = existing
        self.created = []
        self.updated = []

    def get_form_by_name(self, entity, name):
        return dict(self._existing) if self._existing else None

    def create_form(self, payload):
        self.created.append(payload)
        return {"formid": "f-id", "name": payload["name"]}

    def update_form(self, form_id, patch):
        self.updated.append((form_id, patch))
        return {"updated": True, "formid": form_id}


def test_serialize_keys():
    p = form_mod.serialize(_model())
    assert p["name"] == "new_Budget Main"
    assert p["objecttypecode"] == "new_budget"
    assert p["formxml"] == FORMXML
    assert p["type"] == 2
    assert p["description"] == "main form"


def test_deploy_creates_when_absent():
    c = FakeClient(existing=None)
    assert form_mod.deploy(c, _model(), prefix="new")["action"] == "created"
    assert c.created


def test_deploy_updates_when_present():
    c = FakeClient(existing={"formid": "f-id"})
    assert form_mod.deploy(c, _model(), prefix="new")["action"] == "updated"
    assert c.updated and c.updated[0][1]["formxml"] == FORMXML


def test_deploy_skips_standard():
    m = Form(name="Information", entity="account", form_xml=FORMXML)
    assert form_mod.deploy(FakeClient(), m, prefix="new")["action"] == "skipped_standard"


def test_resolve_id():
    assert form_mod.resolve_id(FakeClient(existing={"formid": "f-id"}), _model()) == "f-id"


def test_plan():
    assert form_mod.plan(FakeClient(existing=None), _model(), prefix="new")["action"] == "would_create"
    assert form_mod.plan(FakeClient(existing={"formid": "f-id"}), _model(), prefix="new")["action"] == "would_update"


def test_reverse_preserves_opaque_xml():
    class C:
        def get_form_by_id(self, oid):
            return {
                "name": "new_Budget Main", "objecttypecode": "new_budget",
                "formxml": FORMXML, "type": 2, "description": "d",
            }

    m = form_mod.reverse(C(), "f-id")
    assert m.form_xml == FORMXML
    assert m.entity == "new_budget"
    assert m.form_type == FormType.Main


def test_codegen_round_trip():
    m = _model()
    src = form_mod.codegen(m)
    compile(src, "f", "eval")
    ns = {"Form": Form, "FormType": FormType}
    assert eval(src, ns) == m


def test_lint_flags_missing_entity():
    m = Form(name="new_X", entity="", form_xml=FORMXML)
    issues = form_mod.lint(m, prefix="new")
    assert any("entity" in i.message.lower() for i in issues)
