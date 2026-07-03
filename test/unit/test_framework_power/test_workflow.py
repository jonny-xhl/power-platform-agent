"""Unit tests for framework_power.workflow (fake client / monkeypatched phases, no network)."""

from types import SimpleNamespace
from typing import Any, Optional

import pytest

from framework_power.solution_deployer import SolutionDeployConfig
import framework_power.workflow as workflow
from framework_power.workflow import (
    Project,
    _active_stages,
    _content_stages,
    deploy_workflow,
    lint_workflow,
    load_project,
    plan_workflow,
)

pytestmark = pytest.mark.unit


# Zero-delay deploy config (reused by the solution-ensure + inter-stage sleeps).
_NO_DELAY = SolutionDeployConfig(
    after_publisher_create_delay=0.0,
    after_solution_create_delay=0.0,
    after_component_create_delay=0.0,
    between_adds_delay=0.0,
    sleep=lambda _s: None,
)


class FakeClient:
    """Records solution-ensure + publish; tracks add_solution_component (must stay empty — the
    orchestrator does NO manual adds; stages self-manage)."""

    def __init__(self) -> None:
        self.solutions: dict[str, dict[str, Any]] = {}
        self.solution_adds: list[tuple] = []
        self.published = False
        self.write_methods: list[str] = []

    def ensure_publisher_exists(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.write_methods.append("ensure_publisher_exists")
        return {"publisherid": "pub-1", "created": False}

    def get_solution_by_name(self, name: str) -> Optional[dict[str, Any]]:
        return self.solutions.get(name)

    def create_solution(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.write_methods.append("create_solution")
        self.solutions[payload["uniquename"]] = {"version": payload.get("version")}
        return {"solutionid": "sid:" + payload["uniquename"]}

    def update_solution_version(self, name: str, version: str) -> dict[str, Any]:
        self.write_methods.append("update_solution_version")
        self.solutions[name] = {"version": version}
        return {}

    def publish_all_xml(self) -> dict[str, Any]:
        self.write_methods.append("publish_all_xml")
        self.published = True
        return {"published": True}

    def add_solution_component(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.solution_adds.append((args, kwargs))
        return {"status": "added"}


def _full_project() -> Project:
    return Project(
        main_solution="new_Main",
        ribbon_solution="new_Ribbon",
        version="1.0.0.0",
        optionsets=["new_category"],
        tables=["new_t"],
        webresources=True,
        plugins=["plugins/Smoke"],
        forms=["new_t__Main"],
        views=["new_t__Active"],
        ribbons=["new_t"],
        roles=["SomeRole"],
    )


def _patch_stages(monkeypatch, calls: list[tuple[str, Optional[str]]]) -> None:
    """Replace every stage deploy fn with a recorder capturing (label, solution kwarg)."""

    def bind(label: str):
        def _rec(*args: Any, **kwargs: Any) -> dict[str, Any]:
            calls.append((label, kwargs.get("solution")))
            return {"synced": []}

        return _rec

    monkeypatch.setattr(workflow, "sync_optionsets", bind("optionsets"))
    monkeypatch.setattr(workflow, "deploy_table", bind("tables"))
    monkeypatch.setattr(workflow, "sync_webresources", bind("webresources"))
    monkeypatch.setattr(workflow, "deploy_plugin", bind("plugins"))
    monkeypatch.setattr(workflow, "sync_forms", bind("forms"))
    monkeypatch.setattr(workflow, "sync_views", bind("views"))
    monkeypatch.setattr(workflow, "deploy_role", bind("roles"))
    monkeypatch.setattr(workflow, "sync_ribbons", bind("ribbon"))
    # tables/roles inner loops need defs/roles to fire their deploy_* recorder.
    monkeypatch.setattr(workflow, "get_definition", lambda name, dir=None: SimpleNamespace(table=object()))
    monkeypatch.setattr(workflow, "deploy_order", lambda defs: list(defs.keys()))
    monkeypatch.setattr(workflow, "get_role_definition", lambda name, dir=None: SimpleNamespace(role=object()))


# ----------------------------------------------------------------- selection


def test_project_defaults():
    p = Project(main_solution="new_Main", ribbon_solution="new_Ribbon")
    assert p.version == "1.0.0.0"
    assert p.publisher is None
    assert p.webresources is False
    assert p.optionsets == [] and p.tables == [] and p.roles == []


def test_content_stages_orders_by_chain():
    stages = _content_stages(_full_project())
    assert stages == ["optionsets", "tables", "webresources", "plugins", "forms", "views", "roles", "ribbon"]


def test_active_stages_drops_roles_unless_opt_in():
    p = _full_project()
    assert "roles" not in _active_stages(p, include_roles=False)
    assert "roles" in _active_stages(p, include_roles=True)


def test_active_stages_skip_and_only():
    p = _full_project()
    assert "forms" not in _active_stages(p, include_roles=True, skip={"forms"})
    assert _active_stages(p, include_roles=True, only={"tables", "views"}) == ["tables", "views"]


def test_active_stages_webresource_files():
    # webresource_files (list) triggers the webresources stage even when webresources (bool) is False
    p = Project(main_solution="m", ribbon_solution="r", webresource_files=["js/a.js"])
    assert "webresources" in _content_stages(p)
    assert "webresources" in _active_stages(p, include_roles=False)


def test_deploy_workflow_webresource_files_passes_include(monkeypatch):
    captured: dict = {}

    def _fake_sync(client, root, *, prefix, solution, publish, include=None):
        captured["solution"] = solution
        captured["include"] = include
        return {"synced": []}

    monkeypatch.setattr(workflow, "sync_webresources", _fake_sync)
    project = Project(
        main_solution="new_Main", ribbon_solution="new_Ribbon",
        webresource_files=["js/order/a.js", "js/order/b.js"],
    )
    deploy_workflow(FakeClient(), project, prefix="new", config=_NO_DELAY)
    assert captured["solution"] == "new_Main"
    assert captured["include"] == ["js/order/a.js", "js/order/b.js"]


def test_deploy_workflow_webresources_bool_passes_include_none(monkeypatch):
    captured: dict = {}

    def _fake_sync(client, root, *, prefix, solution, publish, include=None):
        captured["include"] = include
        return {"synced": []}

    monkeypatch.setattr(workflow, "sync_webresources", _fake_sync)
    project = Project(main_solution="new_Main", ribbon_solution="new_Ribbon", webresources=True)
    deploy_workflow(FakeClient(), project, prefix="new", config=_NO_DELAY)
    assert captured["include"] is None  # whole-dir sync (no include filter)


# ----------------------------------------------------------------- load


def test_load_project(tmp_path):
    path = tmp_path / "project.py"
    path.write_text(
        "from framework_power import Project, Publisher\n"
        "PUBLISHER = Publisher(name='new', display_name='PP', prefix='new')\n"
        "PROJECT = Project(main_solution='new_Main', ribbon_solution='new_Ribbon', "
        "publisher=PUBLISHER, tables=['new_x'])\n",
        encoding="utf-8",
    )
    project = load_project(path)
    assert project.main_solution == "new_Main"
    assert project.ribbon_solution == "new_Ribbon"
    assert project.tables == ["new_x"]
    assert project.publisher is not None and project.publisher.name == "new"


def test_load_project_rejects_non_project(tmp_path):
    path = tmp_path / "bad.py"
    path.write_text("PROJECT = 'not a project'\n", encoding="utf-8")
    with pytest.raises(ValueError, match="does not export a Project"):
        load_project(path)


# ----------------------------------------------------------------- deploy


def test_deploy_workflow_stage_order_and_uniform_routing(monkeypatch):
    calls: list[tuple[str, Optional[str]]] = []
    _patch_stages(monkeypatch, calls)
    client = FakeClient()
    result = deploy_workflow(client, _full_project(), prefix="new", include_roles=True, config=_NO_DELAY)

    # Stages run in the canonical chain order.
    labels = [c[0] for c in calls]
    assert labels == [
        "optionsets", "tables", "webresources", "plugins", "forms", "views", "roles", "ribbon"
    ]
    assert list(result["stages"].keys()) == labels

    # Every stage self-manages its solution membership (uniform): main for all, ribbon for ribbon.
    by_stage = dict(calls)
    for stage in ("optionsets", "tables", "webresources", "plugins", "forms", "views", "roles"):
        assert by_stage[stage] == "new_Main", f"{stage} should target the main solution"
    assert by_stage["ribbon"] == "new_Ribbon"

    # The orchestrator itself does NO manual add_solution_component (uniformity contract).
    assert client.solution_adds == []
    # Both solution shells ensured + final org-wide publish ran.
    assert set(client.solutions) == {"new_Main", "new_Ribbon"}
    assert client.published is True


def test_deploy_workflow_skip_and_only(monkeypatch):
    calls: list[tuple[str, Optional[str]]] = []
    _patch_stages(monkeypatch, calls)
    result = deploy_workflow(
        FakeClient(),
        _full_project(),
        prefix="new",
        include_roles=True,
        skip={"plugins", "ribbon"},
        only=None,
        config=_NO_DELAY,
    )
    ran = [c[0] for c in calls]
    assert "plugins" not in ran and "ribbon" not in ran
    assert ran == ["optionsets", "tables", "webresources", "forms", "views", "roles"]
    assert set(result["stages"]) == set(ran)


def test_deploy_workflow_only_restricts(monkeypatch):
    calls: list[tuple[str, Optional[str]]] = []
    _patch_stages(monkeypatch, calls)
    deploy_workflow(
        FakeClient(),
        _full_project(),
        prefix="new",
        only={"tables", "views"},
        config=_NO_DELAY,
    )
    assert [c[0] for c in calls] == ["tables", "views"]


def test_deploy_workflow_roles_opt_in_default_off(monkeypatch):
    calls: list[tuple[str, Optional[str]]] = []
    _patch_stages(monkeypatch, calls)
    deploy_workflow(FakeClient(), _full_project(), prefix="new", config=_NO_DELAY)
    assert "roles" not in [c[0] for c in calls]  # default: roles stage skipped


def test_deploy_workflow_no_publish(monkeypatch):
    calls: list[tuple[str, Optional[str]]] = []
    _patch_stages(monkeypatch, calls)
    client = FakeClient()
    deploy_workflow(FakeClient(), _full_project(), prefix="new", include_roles=True,
                    publish=False, config=_NO_DELAY)
    assert client.published is False


# ----------------------------------------------------------------- plan


def test_plan_workflow_is_read_only(monkeypatch):
    # Monkeypatch plan_* to canned results (no client); assert the orchestrator writes nothing.
    for name in ("plan_optionsets", "plan_webresources", "plan_forms", "plan_views", "plan_ribbons"):
        monkeypatch.setattr(workflow, name, lambda *a, **k: {"read_only": True})
    monkeypatch.setattr(workflow, "plan_table", lambda *a, **k: {"read_only": True})
    monkeypatch.setattr(workflow, "plan_role", lambda *a, **k: {"read_only": True})
    monkeypatch.setattr(workflow, "get_definition", lambda name, dir=None: SimpleNamespace(table=object()))
    monkeypatch.setattr(workflow, "deploy_order", lambda defs: list(defs.keys()))
    monkeypatch.setattr(workflow, "get_role_definition", lambda name, dir=None: SimpleNamespace(role=object()))

    client = FakeClient()
    result = plan_workflow(client, _full_project(), prefix="new", include_roles=True)
    assert set(result["stages"]) == {
        "optionsets", "tables", "webresources", "plugins", "forms", "views", "roles", "ribbon"
    }
    # plan never ensures solutions, adds components, or publishes.
    assert client.solution_adds == []
    assert client.published is False
    assert client.write_methods == []


# ----------------------------------------------------------------- lint


def test_lint_missing_files_and_bad_version(tmp_path):
    # Point dirs at tmp_path so all referenced files are missing.
    p = Project(
        main_solution="new_Main",
        ribbon_solution="new_Ribbon",
        version="bad",
        optionsets=["x"],
        tables=["new_x"],
        forms=["new_x__Main"],
        plugins=["plugins/Nope"],
        optionsets_dir=str(tmp_path),
        tables_dir=str(tmp_path),
        forms_dir=str(tmp_path),
    )
    issues = lint_workflow(p, prefix="new")
    messages = [i.message for i in issues]
    assert any("version must be 'X.Y.Z.W'" in m for m in messages)
    assert any("optionset definition not found" in m for m in messages)
    assert any("table definition not found" in m for m in messages)
    assert any("form definition not found" in m for m in messages)
    assert any("plugin project dir not found" in m for m in messages)


def test_lint_rejects_same_solution():
    p = Project(main_solution="new_S", ribbon_solution="new_S", version="1.0.0.0")
    issues = lint_workflow(p, prefix="new")
    assert any("must differ" in i.message for i in issues)


def test_lint_clean_for_minimal_project():
    issues = lint_workflow(Project(main_solution="new_Main", ribbon_solution="new_Ribbon"), prefix="new")
    # Only the publisher-None warning is expected (no errors).
    assert all(i.severity != "error" for i in issues)
