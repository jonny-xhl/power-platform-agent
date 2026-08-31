"""Unit tests for framework_power.components.plugin (fake client)."""

import pytest

import framework_power.components.plugin as plugin_mod
from framework_power import CustomAction, IsolationMode, Label, Plugin, PluginStep, SourceType, StepImage

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

    def get_plugintypes_by_assembly(self, aid):
        return [{"plugintypeid": "pt-1", "name": "MyPlugin", "typename": "new_MyPlugin.MyPlugin"}]

    def get_sdk_message_filter(self, mid, entity):
        return "filter-1"

    def create_sdk_message_filter(self, mid, entity):
        return "filter-new"

    def entity_exists(self, name):
        return True

    def get_steps_by_assembly(self, aid):
        return [
            {
                "name": "s1", "stage": 40, "mode": 0, "supporteddeployment": 0,
                "filteringattributes": "", "description": "", "rank": 1,
                "sdkmessageid@OData.Community.Display.V1.FormattedValue": "Create",
            }
        ]

    # custom-action workflow surface (deploy always calls _deploy_custom_action)
    def get_workflow_by_uniquename(self, uniquename):
        return None  # no pre-existing workflows

    def create_custom_action(self, payload):
        raise RuntimeError("workflows POST not available in this fake")  # → manual_update_required


# ---- Pre/Post step images ----


class FakeImageClient(FakeClient):
    """FakeClient + step-image bookkeeping for image registration tests."""

    def __init__(self, existing=None, sdk_messages=None):
        super().__init__(existing=existing,
                         sdk_messages={"Create": "msg-1", "Update": "msg-2"} if sdk_messages is None else sdk_messages)
        self.images: dict[str, list[dict]] = {}  # step_id → [image payloads]

    def get_steps_by_assembly(self, aid):
        return []  # force step creation path (base FakeClient returns a pre-existing step)

    def get_step_images(self, step_id):
        return self.images.get(step_id, [])

    def create_step_image(self, payload):
        step_id = payload["sdkmessageprocessingstepid@odata.bind"].rsplit("(", 1)[1][:-1]
        self.images.setdefault(step_id, []).append(payload)
        return {"sdkmessageprocessingstepimageid": f"img-{len(self.images[step_id])}",
                "entityalias": payload.get("entityalias")}


def test_register_images_created_after_step():
    c = FakeImageClient()
    step = PluginStep(
        name="rf.Update", message="Update", entity="new_salesproject",
        images=(StepImage(alias="PreImage", image_type="Pre"),
                StepImage(alias="PostImage", image_type="Post", attributes="new_a,new_b")),
    )
    r = plugin_mod.deploy(c, Plugin(name="new_P", content="Yg==", steps=[step]), prefix="new")
    assert r["steps"][0]["action"] == "created"
    imgs = r["steps"][0]["images"]
    assert [i["action"] for i in imgs] == ["created", "created"]
    payloads = c.images["step-1"]
    assert payloads[0]["imagetype"] == 0 and "attributes" not in payloads[0]  # Pre + all-attrs
    assert payloads[1]["imagetype"] == 1 and payloads[1]["attributes"] == "new_a,new_b"


def test_register_images_backfills_existing_step_and_is_idempotent():
    c = FakeImageClient()
    step = PluginStep(name="rf.Create", message="Create", entity="new_salesproject",
                      images=(StepImage(alias="PostImage"),))
    m = Plugin(name="new_P", content="Yg==", steps=[step])
    r1 = plugin_mod.deploy(c, m, prefix="new")
    assert r1["steps"][0]["images"] == [{"alias": "PostImage", "action": "created", "id": "img-1"}]
    # simulate the step already existing (deploy #2): image is skipped by alias — idempotent
    c2 = FakeImageClient()
    c2.images["step-1"] = [{"entityalias": "PostImage"}]
    r2 = plugin_mod.deploy(c2, m, prefix="new")
    assert r2["steps"][0]["images"] == [{"alias": "PostImage", "action": "exists"}]


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
    assert 91 in codes and 92 in codes  # PluginAssembly(91) + Step(92)


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


def test_deploy_assembly_path_deploys_unprefixed():
    # Phase 8: the assembly path deploys any authored plugin (no new_ prefix required) — system assemblies
    # are skipped only at reverse/snapshot time, not deploy.
    m = Plugin(name="MyPlugin", content="Yg==")
    assert plugin_mod.deploy(FakeClient(), m, prefix="new")["action"] == "created"


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


# ---- Phase 8: PluginPackage (NuGet) deploy path ----


class FakePackageClient:
    """Fake client for the NuGet package path: uploading a package auto-creates the assembly."""

    def __init__(self, existing_entities=None):
        self.packages = {}
        self.assemblies = {}
        self.steps = []
        self.actions_created = []
        self._existing_entities = (
            set(existing_entities) if existing_entities is not None else {"new_fpformsmoke"}
        )
        self._sdk = {"Update": "msg-Update", "new_SmokeAction": "msg-SmokeAction"}

    def entity_exists(self, name):
        return name in self._existing_entities

    def get_plugin_package_by_name(self, name):
        return self.packages.get(name)

    def create_plugin_package(self, payload):
        pid = f"pkg-{len(self.packages) + 1}"
        self.packages[payload["name"]] = {"pluginpackageid": pid, "name": payload["name"]}
        # auto-create the assembly under the (un-prefixed) assembly name
        asm_name = payload["name"].split("_", 1)[1] if "_" in payload["name"] else payload["name"]
        self.assemblies[asm_name] = {"pluginassemblyid": f"asm-{asm_name}", "name": asm_name}
        return {"pluginpackageid": pid, "name": payload["name"]}

    def update_plugin_package(self, pid, patch):
        return {"updated": True, "pluginpackageid": pid}

    def get_plugin_assembly_by_name(self, name):
        return self.assemblies.get(name)

    def get_plugintypes_by_assembly(self, aid):
        return [{"plugintypeid": "pt-smoke", "name": "SmokePlugin",
                 "typename": "PP.Crm.Plugin.Smoke.SmokePlugin"}]

    def get_sdk_message_filter(self, mid, entity):
        return "filter-smoke"

    def create_sdk_message_filter(self, mid, entity):
        return "filter-smoke-new"

    def get_steps_by_assembly(self, aid):
        return []

    def get_sdk_message_id(self, message):
        return self._sdk.get(message)

    def create_plugin_step(self, payload):
        sid = f"step-{len(self.steps) + 1}"
        self.steps.append(payload)
        return {"sdkmessageprocessingstepid": sid, "name": payload["name"]}

    def create_custom_action(self, payload):
        self.actions_created.append(payload)
        return {"workflowid": "wf-1", "uniquename": payload.get("uniquename")}

    def get_workflow_by_uniquename(self, uniquename):
        for payload in self.actions_created:
            if payload.get("uniquename") == uniquename:
                return {"workflowid": "wf-1", "uniquename": uniquename, "statecode": 1, "type": 2}
        return None

    def activate_workflow(self, workflowid):
        return {"activated": True, "workflowid": workflowid}


def _package_model():
    from framework_power import ContentKind
    return Plugin(
        name="PP.Crm.Plugin.Smoke",
        content="bm9wZw==",
        content_kind=ContentKind.Package,
        prefix="new",
        steps=[PluginStep(name="smoke.Update", message="Update", entity="new_fpformsmoke", stage=40)],
        custom_actions=[CustomAction(schema_name="new_SmokeAction", display_name=Label.en("Smoke Action"))],
    )


def test_deploy_package_uploads_and_resolves_assembly():
    c = FakePackageClient()
    r = plugin_mod.deploy(c, _package_model(), prefix="new")
    assert r["action"] == "created_package"
    assert r["package_name"] == "new_PP.Crm.Plugin.Smoke"  # prefix required by Dataverse
    assert r["assembly_id"] == "asm-PP.Crm.Plugin.Smoke"   # auto-created, resolved by assembly name
    assert c.steps and c.steps[0]["name"] == "smoke.Update"
    codes = {t[0] for t in r["add_targets"]}
    assert 10030 in codes and 92 in codes  # PluginPackage(10030) + Step(92); assembly(91) is un-addable


def test_deploy_package_update_when_present():
    c = FakePackageClient()
    c.packages["new_PP.Crm.Plugin.Smoke"] = {"pluginpackageid": "pkg-existing"}
    c.assemblies["PP.Crm.Plugin.Smoke"] = {"pluginassemblyid": "asm-existing"}
    r = plugin_mod.deploy(c, _package_model(), prefix="new")
    assert r["action"] == "updated_package"


def test_deploy_custom_action_auto_creates_when_workflow_succeeds():
    c = FakePackageClient()
    r = plugin_mod.deploy(c, _package_model(), prefix="new")
    # workflow created + sdk message resolvable → action created (not manual)
    assert r["custom_actions"][0]["action"] == "created"
    assert c.actions_created and c.actions_created[0]["category"] == 3  # Action


def test_deploy_step_fails_clearly_when_target_entity_missing():
    """When a step's target entity doesn't exist, fail fast with a clear root-cause message
    (not the opaque 0x80041102 400 Dataverse returns from the sdkmessagefilters query)."""
    c = FakePackageClient(existing_entities=set())  # new_fpformsmoke absent
    r = plugin_mod.deploy(c, _package_model(), prefix="new")
    step = r["steps"][0]
    assert step["action"] == "failed"
    assert "target entity 'new_fpformsmoke' not found" in step["error"]
    # the entity-scoped step was NOT registered (the custom-action step is separate + unaffected)
    assert all(s["name"] != "smoke.Update" for s in c.steps)
