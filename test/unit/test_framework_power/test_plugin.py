"""Unit tests for framework_power.components.plugin (fake client)."""

import pytest

import framework_power.components.plugin as plugin_mod
from framework_power import CustomAction, IsolationMode, Label, Plugin, PluginStep, SourceType

pytestmark = pytest.mark.unit


def _model() -> Plugin:
    return Plugin(
        name="new_MyPlugin",
        content="YmFzZTY0",
        steps=[PluginStep(name="new_budget on Create", message="Create", entity="new_budget")],
        custom_actions=[CustomAction(schema_name="new_Score", display_name=Label.en("Score"))],
    )


class FakeClient:
    def __init__(self, existing=None, sdk_messages=None) -> None:
        self._existing = existing
        self._sdk = {"Create": "msg-1"} if sdk_messages is None else sdk_messages
        self.created_asm = []
        self.updated_asm = []
        self.created_steps = []

    def get_plugin_assembly_by_name(self, name):
        return dict(self._existing) if self._existing else None

    def create_plugin_assembly(self, payload):
        self.created_asm.append(payload)
        return {"pluginassemblyid": "asm-1", "name": payload["name"]}

    def update_plugin_assembly(self, aid, patch):
        self.updated_asm.append((aid, patch))
        return {"updated": True, "pluginassemblyid": aid}

    def get_sdk_message_id(self, message):
        return self._sdk.get(message)

    def create_plugin_step(self, payload):
        self.created_steps.append(payload)
        return {"sdkmessageprocessingstepid": "step-1", "name": payload["name"]}

    def get_plugin_assembly_by_id(self, aid):
        return {"name": "new_MyPlugin", "content": "Yg==", "version": "1.0.0.0", "isolationmode": 2, "sourcetype": 0}

    def get_steps_by_assembly(self, aid):
        return [
            {
                "name": "s1", "stage": 40, "mode": 0, "supporteddeployment": 0,
                "filteringattributes": "", "description": "", "rank": 1,
                "sdkmessageid@OData.Community.Display.V1.FormattedValue": "Create",
            }
        ]


def test_serialize_keys():
    p = plugin_mod.serialize(_model())
    assert p["name"] == "new_MyPlugin"
    assert p["content"] == "YmFzZTY0"
    assert p["isolationmode"] == 2
    assert p["sourcetype"] == 0


def test_deploy_creates_assembly_and_step_with_add_targets():
    c = FakeClient(existing=None)
    r = plugin_mod.deploy(c, _model(), prefix="new")
    assert r["action"] == "created"
    assert r["assembly_id"] == "asm-1"
    assert c.created_asm and c.created_steps
    codes = {t[0] for t in r["add_targets"]}
    assert 90 in codes and 92 in codes  # assembly + step


def test_deploy_updates_assembly_when_present():
    c = FakeClient(existing={"pluginassemblyid": "asm-9"})
    r = plugin_mod.deploy(c, _model(), prefix="new")
    assert r["action"] == "updated"
    assert c.updated_asm and c.updated_asm[0][0] == "asm-9"


def test_deploy_step_fails_when_message_missing():
    c = FakeClient(existing=None, sdk_messages={})
    r = plugin_mod.deploy(c, _model(), prefix="new")
    assert r["steps"][0]["action"] == "failed"


def test_deploy_custom_action_is_manual_update():
    r = plugin_mod.deploy(FakeClient(), _model(), prefix="new")
    assert r["custom_actions"][0]["action"] == "manual_update_required"


def test_deploy_skips_standard():
    m = Plugin(name="MyPlugin", content="Yg==")
    assert plugin_mod.deploy(FakeClient(), m, prefix="new")["action"] == "skipped_standard"


def test_resolve_id():
    assert plugin_mod.resolve_id(FakeClient(existing={"pluginassemblyid": "asm-1"}), _model()) == "asm-1"


def test_plan():
    assert plugin_mod.plan(FakeClient(existing=None), _model(), prefix="new")["action"] == "would_create"


def test_reverse_folds_steps():
    m = plugin_mod.reverse(FakeClient(), "asm-1")
    assert m.name == "new_MyPlugin"
    assert len(m.steps) == 1
    assert m.steps[0].message == "Create"


def test_codegen_round_trip():
    m = _model()
    src = plugin_mod.codegen(m)
    compile(src, "p", "eval")
    ns = {
        "Plugin": Plugin, "PluginStep": PluginStep, "CustomAction": CustomAction,
        "IsolationMode": IsolationMode, "SourceType": SourceType, "Label": Label,
    }
    assert eval(src, ns) == m


def test_lint_step_needs_message_and_entity():
    m = Plugin(
        name="new_P", content="Yg==",
        steps=[PluginStep(name="bad", message="", entity="")],
    )
    issues = plugin_mod.lint(m, prefix="new")
    assert any("message" in i.message.lower() for i in issues)
