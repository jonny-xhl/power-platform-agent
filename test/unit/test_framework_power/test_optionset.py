"""Unit tests for framework_power.components.optionset (fake client)."""

import pytest

import framework_power.components.optionset as opt
from framework_power import GlobalOptionSet, Label, Option

pytestmark = pytest.mark.unit


def _model() -> GlobalOptionSet:
    return GlobalOptionSet(
        name="new_Priority",
        display_name=Label.bilingual("优先级", "Priority"),
        options=[Option(1, Label.en("Low")), Option(2, Label.en("High"))],
    )


class FakeClient:
    def __init__(self, existing=None) -> None:
        self._existing = existing
        self.created = []

    def get_global_optionset_by_name(self, name):
        return dict(self._existing) if self._existing else None

    def create_global_optionset(self, payload):
        self.created.append(payload)
        return {"MetadataId": "os-id", "Name": payload["Name"]}


def test_serialize_keys():
    p = opt.serialize(_model())
    assert p["@odata.type"] == "Microsoft.Dynamics.CRM.OptionSetMetadata"
    assert p["Name"] == "new_Priority"
    assert p["IsGlobal"] is True
    assert [o["Value"] for o in p["Options"]] == [1, 2]


def test_deploy_creates_when_absent():
    c = FakeClient(existing=None)
    assert opt.deploy(c, _model(), prefix="new")["action"] == "created"
    assert c.created


def test_deploy_exists_when_same_options():
    existing = {"MetadataId": "os-id", "Options": [{"Value": 1}, {"Value": 2}]}
    assert opt.deploy(FakeClient(existing=existing), _model(), prefix="new")["action"] == "exists"


def test_deploy_manual_update_when_options_differ():
    existing = {"MetadataId": "os-id", "Options": [{"Value": 1}, {"Value": 9}]}
    r = opt.deploy(FakeClient(existing=existing), _model(), prefix="new")
    assert r["action"] == "manual_update_required"


def test_deploy_skips_standard():
    m = GlobalOptionSet(name="priority", display_name=Label.en("P"), options=[])
    assert opt.deploy(FakeClient(), m, prefix="new")["action"] == "skipped_standard"


def test_resolve_id():
    assert opt.resolve_id(FakeClient(existing={"MetadataId": "os-id"}), _model()) == "os-id"


def test_plan_would_create():
    assert opt.plan(FakeClient(existing=None), _model(), prefix="new")["action"] == "would_create"


def test_reverse():
    class C:
        def get_global_optionset_by_id(self, oid):
            return {
                "Name": "new_Priority",
                "DisplayName": {"LocalizedLabels": [{"Label": "P", "LanguageCode": 1033}]},
                "Options": [
                    {"Value": 1, "Label": {"LocalizedLabels": [{"Label": "Low", "LanguageCode": 1033}]}}
                ],
            }

    m = opt.reverse(C(), "os-id")
    assert m.name == "new_Priority"
    assert [o.value for o in m.options] == [1]


def test_codegen_round_trip():
    m = _model()
    src = opt.codegen(m)
    compile(src, "o", "eval")
    ns = {"GlobalOptionSet": GlobalOptionSet, "Label": Label, "Option": Option}
    assert eval(src, ns) == m


def test_lint_flags_duplicate_values():
    m = GlobalOptionSet(
        name="new_X", display_name=Label.en("X"),
        options=[Option(1, Label.en("a")), Option(1, Label.en("b"))],
    )
    issues = opt.lint(m, prefix="new")
    assert any("duplicate" in i.message.lower() for i in issues)
