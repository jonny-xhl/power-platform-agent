"""Unit tests for framework_power.solution_deployer (fake client, no network)."""

from typing import Any, Optional

import pytest

from framework_power.components.models import ComponentRef, Solution
from framework_power.solution_deployer import (
    SolutionDeployConfig,
    deploy_solution,
    lint_solution,
    plan_solution,
)

pytestmark = pytest.mark.unit

NO_DELAY = SolutionDeployConfig(
    after_publisher_create_delay=0.0,
    after_solution_create_delay=0.0,
    after_component_create_delay=0.0,
    between_adds_delay=0.0,
    sleep=lambda _s: None,
)


class SolutionFakeClient:
    """Records solution/publisher/table calls; returns canned responses."""

    def __init__(
        self,
        *,
        existing_publisher: bool = True,
        existing_solution: Optional[dict[str, Any]] = None,
        table_exists: bool = True,
    ) -> None:
        self._existing_publisher = existing_publisher
        self._existing_solution = existing_solution
        self.table_exists = table_exists
        self._optionsets: dict[str, dict[str, Any]] = {}
        self._webresources: dict[str, dict[str, Any]] = {}
        self._forms: dict[tuple[str, str], dict[str, Any]] = {}
        self._views: dict[tuple[str, str], dict[str, Any]] = {}
        self.calls: dict[str, list[Any]] = {
            "create_publisher": [],
            "create_solution": [],
            "update_solution_version": [],
            "add_solution_component": [],
            "publish_all_xml": [],
            "create_entity": [],
            "update_entity": [],
            "create_global_optionset": [],
            "create_webresource": [],
        }

    # publisher
    def get_publisher_by_name(self, name: str) -> Optional[dict[str, Any]]:
        if self._existing_publisher:
            return {"publisherid": "pub-id", "uniquename": name}
        return None

    def create_publisher(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls["create_publisher"].append(payload)
        return {"publisherid": "pub-id-new", "uniquename": payload["uniquename"]}

    def ensure_publisher_exists(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = payload.get("uniquename")
        existing = self.get_publisher_by_name(name)
        if existing:
            return {"created": False, "publisherid": existing["publisherid"], "uniquename": name}
        return {"created": True, **self.create_publisher(payload)}

    # solution
    def get_solution_by_name(self, unique_name: str) -> Optional[dict[str, Any]]:
        return dict(self._existing_solution) if self._existing_solution else None

    def create_solution(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls["create_solution"].append(payload)
        return {"solutionid": "sol-id", "uniquename": payload["uniquename"]}

    def update_solution_version(self, unique_name: str, version: str) -> dict[str, Any]:
        self.calls["update_solution_version"].append((unique_name, version))
        return {"updated": True}

    def get_solution_components(self, unique_name: str) -> list[dict[str, Any]]:
        return []

    def add_solution_component(self, unique_name: str, code: int, oid: str, add_required: bool = False):
        self.calls["add_solution_component"].append((unique_name, code, oid))
        return {"added": True}

    def publish_all_xml(self) -> dict[str, Any]:
        self.calls["publish_all_xml"].append(True)
        return {"published": True}

    # table-deploy surface (delegated to by deploy_table via the table adapter)
    def entity_exists(self, name: str) -> bool:
        return self.table_exists

    def create_entity(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls["create_entity"].append(payload)
        return {"MetadataId": "tbl-id"}

    def update_entity(self, name: str, patch: dict[str, Any]) -> dict[str, Any]:
        self.calls["update_entity"].append((name, patch))
        return {"status": "updated"}

    def get_attributes(self, name: str) -> list[dict[str, Any]]:
        return []

    def get_relationships(self, name: str) -> list[dict[str, Any]]:
        return []

    def create_attribute(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"status": "created"}

    def update_attribute_by_logical_name(self, e: str, a: str, patch: dict[str, Any]) -> dict[str, Any]:
        return {"status": "updated"}

    def create_relationship_from_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"status": "created"}

    def get_entity_metadata(self, name: str) -> dict[str, Any]:
        return {
            "MetadataId": "tbl-id",
            "LogicalName": name,
            "SchemaName": name,
            "PrimaryIdAttribute": f"{name}id",
        }

    # optionset / webresource (Wave 2)
    def get_global_optionset_by_name(self, name: str) -> Optional[dict[str, Any]]:
        return dict(self._optionsets[name]) if name in self._optionsets else None

    def create_global_optionset(self, payload: dict[str, Any]) -> dict[str, Any]:
        rec = {"MetadataId": "os-id", "Name": payload["Name"]}
        self._optionsets[payload["Name"]] = rec
        self.calls["create_global_optionset"].append(payload)
        return rec

    def get_webresource_by_name(self, name: str) -> Optional[dict[str, Any]]:
        return dict(self._webresources[name]) if name in self._webresources else None

    def create_webresource(self, payload: dict[str, Any]) -> dict[str, Any]:
        rec = {"webresourceid": "wr-id", "name": payload["name"]}
        self._webresources[payload["name"]] = rec
        self.calls["create_webresource"].append(payload)
        return rec

    def update_webresource(self, webresourceid: str, patch: dict[str, Any]) -> dict[str, Any]:
        return {"updated": True, "webresourceid": webresourceid}

    # forms / views (Wave 3)
    def get_form_by_name(self, entity: str, name: str, *, form_type: Optional[int] = None) -> Optional[dict[str, Any]]:
        rec = self._forms.get((entity, name))
        return dict(rec) if rec else None

    def create_form(self, payload: dict[str, Any]) -> dict[str, Any]:
        rec = {"formid": "f-id", "name": payload["name"]}
        self._forms[(payload["objecttypecode"], payload["name"])] = rec
        self.calls.setdefault("create_form", []).append(payload)
        return rec

    def update_form(self, form_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        return {"updated": True, "formid": form_id}

    def get_view_by_name(self, entity: str, name: str, *, query_type: Optional[int] = None) -> Optional[dict[str, Any]]:
        rec = self._views.get((entity, name))
        return dict(rec) if rec else None

    def create_view(self, payload: dict[str, Any]) -> dict[str, Any]:
        rec = {"savedqueryid": "v-id", "name": payload["name"]}
        self._views[(payload["returnedtypecode"], payload["name"])] = rec
        self.calls.setdefault("create_view", []).append(payload)
        return rec

    def update_view(self, savedquery_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        return {"updated": True, "savedqueryid": savedquery_id}

    # plugins (Wave 4)
    def get_plugin_assembly_by_name(self, name: str) -> Optional[dict[str, Any]]:
        return None

    def create_plugin_assembly(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.setdefault("create_plugin_assembly", []).append(payload)
        return {"pluginassemblyid": "asm-1", "name": payload["name"]}

    def update_plugin_assembly(self, pluginassemblyid: str, patch: dict[str, Any]) -> dict[str, Any]:
        return {"updated": True, "pluginassemblyid": pluginassemblyid}

    def get_sdk_message_id(self, message: str) -> Optional[str]:
        return "msg-1"

    def get_plugintypes_by_assembly(self, pluginassemblyid: str) -> list[dict[str, Any]]:
        return [{"plugintypeid": "pt-1", "name": "MyPlugin", "typename": "new_MyPlugin.MyPlugin"}]

    def get_sdk_message_filter(self, sdkmessageid: str, entity: str) -> Optional[str]:
        return "filter-1"

    def create_sdk_message_filter(self, sdkmessageid: str, entity: str) -> str:
        return "filter-new"

    def get_steps_by_assembly(self, pluginassemblyid: str) -> list[dict[str, Any]]:
        return []

    def create_plugin_step(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.setdefault("create_plugin_step", []).append(payload)
        return {"sdkmessageprocessingstepid": "step-1", "name": payload["name"]}

    # roles (Phase 3b)
    def get_role_by_name(self, name: str) -> Optional[dict[str, Any]]:
        return {"roleid": "role-1", "name": name}


def _solution(**kwargs: Any) -> Solution:
    return Solution(unique_name="new_Core", friendly_name="Core", publisher_key="default", **kwargs)


def test_deploy_creates_publisher_and_solution_when_absent():
    client = SolutionFakeClient(existing_publisher=False, existing_solution=None)
    result = deploy_solution(client, _solution(), prefix="new", config=NO_DELAY)
    assert client.calls["create_publisher"]
    assert client.calls["create_solution"]
    assert "publisherid@odata.bind" in client.calls["create_solution"][0]
    assert client.calls["publish_all_xml"]
    assert result["solution_object"]["action"] == "created"


def test_deploy_idempotent_when_publisher_and_solution_exist():
    client = SolutionFakeClient(
        existing_publisher=True, existing_solution={"version": "1.0.0.0"}
    )
    result = deploy_solution(client, _solution(), prefix="new", config=NO_DELAY)
    assert not client.calls["create_publisher"]
    assert not client.calls["create_solution"]
    assert result["solution_object"]["action"] == "exists"
    assert client.calls["publish_all_xml"]  # publish still runs


def test_deploy_updates_version_when_changed():
    client = SolutionFakeClient(existing_solution={"version": "0.9.0.0"})
    result = deploy_solution(
        client, _solution(version="1.0.0.0"), prefix="new", config=NO_DELAY
    )
    assert client.calls["update_solution_version"] == [("new_Core", "1.0.0.0")]
    assert result["solution_object"]["action"] == "updated"


def _write_table_def(dir_path, stem: str, schema: str) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / f"{stem}.py").write_text(
        "from framework_power import Table\n"
        "from framework_power.models import Label\n"
        f"TABLE = Table(schema_name={schema!r}, display_name=Label.en('Budget'))\n",
        encoding="utf-8",
    )


def test_deploy_with_custom_table_adds_to_solution(tmp_path):
    _write_table_def(tmp_path, "new_budget", "new_Budget")
    client = SolutionFakeClient(table_exists=True)
    deploy_solution(
        client, _solution(tables=["new_budget"]), definitions_dir=str(tmp_path),
        prefix="new", config=NO_DELAY,
    )
    assert ("new_Core", 1, "tbl-id") in client.calls["add_solution_component"]
    assert client.calls["publish_all_xml"]
    # the custom table was deployed (table_exists -> update path)
    assert client.calls["update_entity"]


def test_deploy_skips_standard_table_without_definition(tmp_path):
    client = SolutionFakeClient(table_exists=True)
    result = deploy_solution(
        client, _solution(tables=["contact"]), definitions_dir=str(tmp_path),
        prefix="new", config=NO_DELAY,
    )
    # contact is standard + has no local def -> skipped, never deployed or added
    table_adds = [c for c in client.calls["add_solution_component"] if c[1] == 1]
    assert table_adds == []
    assert any(
        c.get("deploy", {}).get("action") == "skipped_standard" for c in result["components"]
    )


def test_deploy_ref_by_numeric_code_added():
    client = SolutionFakeClient()
    sol = _solution(refs=[ComponentRef(type="61", object_id="wr-guid")])
    deploy_solution(client, sol, prefix="new", config=NO_DELAY)
    assert ("new_Core", 61, "wr-guid") in client.calls["add_solution_component"]


def test_deploy_ref_by_table_name_resolved():
    client = SolutionFakeClient()
    sol = _solution(refs=[ComponentRef(type="table", name="new_budget")])
    deploy_solution(client, sol, prefix="new", config=NO_DELAY)
    assert ("new_Core", 1, "tbl-id") in client.calls["add_solution_component"]


def test_deploy_unresolved_ref_skipped():
    client = SolutionFakeClient()
    sol = _solution(refs=[ComponentRef(type="webresource", name="some.js")])  # no id, not table
    result = deploy_solution(client, sol, prefix="new", config=NO_DELAY)
    assert any(a.get("action") == "skipped" for a in result["added"])


def test_lint_solution_flags_bad_version_and_missing_publisher():
    bad = Solution(unique_name="new_X", friendly_name="X", version="1.0")
    issues = lint_solution(bad, prefix="new")
    assert any("version" in i.message for i in issues)
    assert any("publisher" in i.message for i in issues)


def test_lint_solution_flags_duplicate_table_ref():
    sol = Solution(
        unique_name="new_X", friendly_name="X", publisher_key="default",
        tables=["new_budget", "new_budget"],
    )
    issues = lint_solution(sol, prefix="new")
    assert any("Duplicate" in i.message for i in issues)


def test_plan_is_read_only():
    client = SolutionFakeClient(existing_solution={"version": "1.0.0.0"})
    result = plan_solution(client, _solution(tables=["contact"]), prefix="new")
    assert not client.calls["create_solution"]
    assert not client.calls["add_solution_component"]
    assert not client.calls["publish_all_xml"]
    assert result["solution_object"]["action"] == "exists"
    assert result["publish"]["action"] == "would_publish"


def test_deploy_solution_deploys_and_adds_optionset_and_webresource():
    from framework_power import GlobalOptionSet, Label, Option, WebResource, WebResourceType

    sol = _solution(
        optionsets=[
            GlobalOptionSet(
                name="new_Priority", display_name=Label.en("Priority"),
                options=[Option(1, Label.en("Low"))],
            )
        ],
        webresources=[
            WebResource(
                name="new_/js/x.js", display_name="X", content="YmFzZTY0",
                webresource_type=WebResourceType.JScript,
            )
        ],
    )
    client = SolutionFakeClient()
    result = deploy_solution(client, sol, prefix="new", config=NO_DELAY)
    assert client.calls["create_global_optionset"]
    assert client.calls["create_webresource"]
    # both added to the solution (optionset code 9, webresource code 61)
    codes = {c[1] for c in client.calls["add_solution_component"]}
    assert 9 in codes and 61 in codes
    assert client.calls["publish_all_xml"]
    # standard optionset name would be skipped — sanity on the custom path
    assert all(c["deploy"]["action"] == "created" for c in result["components"])


def test_deploy_solution_deploys_and_adds_form_and_view():
    from framework_power import Form, FormType, QueryType, View

    sol = _solution(
        forms=[Form(name="new_Budget Main", entity="new_budget", form_type=FormType.Main)],
        views=[
            View(
                name="new_Active Budgets", entity="new_budget", query_type=QueryType.Public,
                primary_id="new_budgetid", object_type_code=10000,
            )
        ],
    )
    client = SolutionFakeClient()
    deploy_solution(client, sol, prefix="new", config=NO_DELAY)
    assert client.calls["create_form"]
    assert client.calls["create_view"]
    codes = {c[1] for c in client.calls["add_solution_component"]}
    assert 60 in codes and 26 in codes  # form + view add codes


def test_deploy_solution_plugin_multi_part_add():
    from framework_power import Plugin, PluginStep

    sol = _solution(
        plugins=[
            Plugin(
                name="new_MyPlugin", content="Yg==",
                steps=[PluginStep(name="on Create", message="Create", entity="new_budget")],
            )
        ]
    )
    client = SolutionFakeClient()
    deploy_solution(client, sol, prefix="new", config=NO_DELAY)
    assert client.calls["create_plugin_assembly"]
    assert client.calls["create_plugin_step"]
    codes = {c[1] for c in client.calls["add_solution_component"]}
    assert 91 in codes and 92 in codes  # PluginAssembly(91) + Step(92) multi-part add


def test_deploy_solution_adds_roles_to_solution():
    """Phase 3b: roles listed in a solution are added to it (existing roles, by name)."""
    sol = _solution(roles=["Basic User", "System Customizer"])
    client = SolutionFakeClient()
    deploy_solution(client, sol, prefix="new", config=NO_DELAY)
    # both roles added with the role solution-component code (20)
    added_role_ids = {c[2] for c in client.calls["add_solution_component"] if c[1] == 20}
    assert "role-1" in added_role_ids
    assert client.calls["publish_all_xml"]


def test_deploy_solution_role_not_found_recorded():
    sol = _solution(roles=["Ghost Role"])
    client = SolutionFakeClient()

    class NoRoleClient(SolutionFakeClient):
        def get_role_by_name(self, name):
            return None

    result = deploy_solution(NoRoleClient(), sol, prefix="new", config=NO_DELAY)
    assert any(a.get("type") == "role" and a.get("action") == "failed" for a in result["added"])


def test_deploy_solution_uses_deploy_result_id_not_relookup():
    """Regression: the create->resolve propagation race. A freshly-created optionset
    is not yet visible to a name lookup (get_global_optionset_by_name -> None), so
    deploy_solution must add using the id the deploy returned, not a re-lookup."""
    from framework_power import GlobalOptionSet, Label, Option

    class RaceClient(SolutionFakeClient):
        def get_global_optionset_by_name(self, name):
            return None  # never visible by name (simulates post-create propagation delay)

        def create_global_optionset(self, payload):
            self.calls["create_global_optionset"].append(payload)
            return {"MetadataId": "os-race-id", "Name": payload["Name"]}

    sol = _solution(
        optionsets=[GlobalOptionSet(name="new_P", display_name=Label.en("P"), options=[Option(1, Label.en("a"))])]
    )
    client = RaceClient()
    deploy_solution(client, sol, prefix="new", config=NO_DELAY)
    # Despite resolve-by-name returning None, the optionset was added via the returned id
    assert ("new_Core", 9, "os-race-id") in client.calls["add_solution_component"]
