"""Unit tests for framework_power.cli (offline subcommands only)."""

from pathlib import Path

import pytest

from framework_power.cli import main

pytestmark = pytest.mark.unit

PROJECT_ROOT = Path(__file__).parents[3]
DEFS_DIR = str(PROJECT_ROOT / "metadata_py" / "tables")


def _argv(*cmd: str) -> list[str]:
    return ["--definitions-dir", DEFS_DIR, *cmd]


def test_cli_list(capsys):
    rc = main(_argv("list"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "new_projectbudget" in out
    assert "new_ProjectBudget" in out


def test_cli_show(capsys):
    rc = main(_argv("show", "new_projectbudget"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "Microsoft.Dynamics.CRM.EntityMetadata" in out


def test_cli_lint_one_passes(capsys):
    rc = main(_argv("lint", "new_projectbudget"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "[ok]" in out


def test_cli_lint_all_passes(capsys):
    rc = main(_argv("lint"))
    assert rc == 0


# ----------------------------------------------------------------- solution


def _write_solution(sdir: Path) -> None:
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "new_core.py").write_text(
        "from framework_power import Solution\n"
        "SOLUTION: Solution = Solution(\n"
        "    unique_name='new_Core', friendly_name='Core', publisher_key='default',\n"
        "    tables=['new_budget'],\n"
        ")\n",
        encoding="utf-8",
    )


def test_cli_solution_list_show_lint(tmp_path, capsys):
    sdir = tmp_path / "solutions"
    _write_solution(sdir)

    rc = main(["--solutions-dir", str(sdir), "solution", "list"])
    assert rc == 0
    assert "new_core" in capsys.readouterr().out

    rc = main(["--solutions-dir", str(sdir), "solution", "show", "new_core"])
    assert rc == 0
    assert "new_Core" in capsys.readouterr().out

    rc = main(["--solutions-dir", str(sdir), "solution", "lint", "new_core"])
    assert rc == 0
    assert "[ok]" in capsys.readouterr().out


def test_cli_solution_deploy_uses_client(tmp_path, capsys, monkeypatch):
    sdir = tmp_path / "solutions"
    _write_solution(sdir)

    class FakeClient:
        def __init__(self) -> None:
            self.published = False
            self.added: list = []

        def get_publisher_by_name(self, n):
            return {"publisherid": "p"}

        def ensure_publisher_exists(self, p):
            return {"created": False, "publisherid": "p", "uniquename": p["uniquename"]}

        def get_solution_by_name(self, n):
            return {"version": "1.0.0.0"}

        def create_solution(self, p):
            return {"solutionid": "s"}

        def update_solution_version(self, n, v):
            return {}

        def get_solution_components(self, n):
            return []

        def add_solution_component(self, *a, **k):
            self.added.append(a)
            return {"added": True}

        def publish_all_xml(self):
            self.published = True
            return {"published": True}

    fake = FakeClient()
    monkeypatch.setattr("framework_power.cli.get_client", lambda env: fake)
    monkeypatch.setattr("framework_power.cli._publisher_prefix", lambda *a, **k: "new")

    rc = main(["--solutions-dir", str(sdir), "solution", "deploy", "new_core", "--env", "dev"])
    out = capsys.readouterr().out
    assert rc == 0
    assert fake.published
    assert "new_Core" in out


def test_cli_solution_publish_calls_client(monkeypatch, capsys):
    class FakeClient:
        def __init__(self) -> None:
            self.published = False

        def publish_all_xml(self):
            self.published = True
            return {"published": True}

    fake = FakeClient()
    monkeypatch.setattr("framework_power.cli.get_client", lambda env: fake)
    rc = main(["solution", "publish", "--env", "dev"])
    assert rc == 0 and fake.published


def test_cli_solution_delete_calls_client(monkeypatch, capsys):
    class FakeClient:
        def __init__(self) -> None:
            self.deleted = None

        def delete_solution(self, name):
            self.deleted = name
            return {"status": "deleted", "uniquename": name}

    fake = FakeClient()
    monkeypatch.setattr("framework_power.cli.get_client", lambda env: fake)
    rc = main(["solution", "delete", "new_FpSmoke", "--env", "dev"])
    out = capsys.readouterr().out
    assert rc == 0 and fake.deleted == "new_FpSmoke"
    assert "deleted" in out


# ----------------------------------------------------------------- role (Phase 3)

_ROLE_PY = (
    "from framework_power import AccessRight, PrivilegeDepth, SecurityRole, TablePrivilege\n"
    "ROLE: SecurityRole = SecurityRole(\n"
    "    name='Test Role',\n"
    "    table_privileges=[TablePrivilege(table='new_fpsmokea', rights={AccessRight.READ: PrivilegeDepth.USER})],\n"
    ")\n"
)


def test_cli_role_list_show(tmp_path, capsys):
    rdir = tmp_path / "roles"
    rdir.mkdir()
    (rdir / "test_role.py").write_text(_ROLE_PY, encoding="utf-8")
    rc = main(["--roles-dir", str(rdir), "role", "list"])
    assert rc == 0 and "test_role" in capsys.readouterr().out
    rc = main(["--roles-dir", str(rdir), "role", "show", "test_role"])
    assert rc == 0 and "Test Role" in capsys.readouterr().out


def test_cli_role_reverse_requires_tables(tmp_path, monkeypatch, capsys):
    rdir = tmp_path / "roles"
    rdir.mkdir()
    (rdir / "test_role.py").write_text(_ROLE_PY, encoding="utf-8")
    monkeypatch.setattr("framework_power.cli.get_client", lambda env: object())
    rc = main(["--roles-dir", str(rdir), "role", "reverse", "test_role", "--env", "dev"])
    out = capsys.readouterr().out
    assert rc == 2 and "--tables" in out


def test_cli_role_deploy_uses_client(tmp_path, monkeypatch, capsys):
    rdir = tmp_path / "roles"
    rdir.mkdir()
    (rdir / "test_role.py").write_text(_ROLE_PY, encoding="utf-8")

    class FakeClient:
        def __init__(self) -> None:
            self.added = []

        def get_role_by_name(self, name):
            return {"roleid": "role-1", "name": name}

        def get_entity_schema_name(self, logical):
            return "new_FpSmokeA"

        def get_privilege_by_name(self, name):
            return {"name": name, "privilegeid": "pid:" + name}

        def get_role_privileges(self, role_id, privilege_ids=None):
            return []

        def add_privileges_to_role(self, role_id, privileges):
            self.added.append(privileges)
            return {"synced": True, "count": len(privileges)}

    fake = FakeClient()
    monkeypatch.setattr("framework_power.cli.get_client", lambda env: fake)
    monkeypatch.setattr("framework_power.cli._publisher_prefix", lambda *a, **k: "new")
    rc = main(["--roles-dir", str(rdir), "role", "deploy", "test_role", "--env", "dev"])
    out = capsys.readouterr().out
    assert rc == 0
    assert fake.added and fake.added[0][0]["Depth"] == "Basic"
    assert "Test Role" in out


# ----------------------------------------------------------------- webresource (Phase 4)


class _WRFakeClient:
    def __init__(self) -> None:
        self.created = []
        self.published = None
        self.by_prefix = []

    def get_webresource_by_name(self, name):
        return None

    def create_webresource(self, payload):
        self.created.append(payload)
        wid = "wr-" + payload["name"].replace("/", "_")
        return {"webresourceid": wid, "name": payload["name"]}

    def update_webresource(self, webresourceid, patch):
        return {"updated": True, "webresourceid": webresourceid}

    def publish_webresources(self, ids):
        self.published = list(ids)
        return {"published": True, "count": len(ids), "ids": list(ids)}

    def list_webresources_by_prefix(self, name_prefix, *, select=""):
        return list(self.by_prefix)


def test_cli_webresource_scan_offline(tmp_path, capsys):
    (tmp_path / "js" / "order").mkdir(parents=True)
    (tmp_path / "js" / "order" / "test.js").write_bytes(b"console.log(1)")
    rc = main(["webresource", "scan", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "new_/js/order/test.js" in out


def test_cli_webresource_sync_uses_client(tmp_path, monkeypatch, capsys):
    (tmp_path / "js").mkdir()
    (tmp_path / "js" / "a.js").write_bytes(b"a")
    fake = _WRFakeClient()
    monkeypatch.setattr("framework_power.cli.get_client", lambda env: fake)
    monkeypatch.setattr("framework_power.cli._publisher_prefix", lambda *a, **k: "new")
    rc = main(["webresource", "sync", str(tmp_path), "--env", "dev"])
    out = capsys.readouterr().out
    assert rc == 0
    assert fake.created and fake.created[0]["name"] == "new_/js/a.js"
    assert fake.published and len(fake.published) == 1
    assert "new_/js/a.js" in out


def test_cli_webresource_sync_no_publish(tmp_path, monkeypatch, capsys):
    (tmp_path / "js").mkdir()
    (tmp_path / "js" / "a.js").write_bytes(b"a")
    fake = _WRFakeClient()
    monkeypatch.setattr("framework_power.cli.get_client", lambda env: fake)
    monkeypatch.setattr("framework_power.cli._publisher_prefix", lambda *a, **k: "new")
    rc = main(["webresource", "sync", str(tmp_path), "--no-publish", "--env", "dev"])
    assert rc == 0
    assert fake.published is None


def test_cli_webresource_publish_resolves_names(tmp_path, monkeypatch, capsys):
    class C:
        def __init__(self):
            self.published = None

        def get_webresource_by_name(self, name):
            return {"webresourceid": "wr-" + name, "name": name}

        def publish_webresources(self, ids):
            self.published = ids
            return {"published": True, "count": len(ids), "ids": ids}

    fake = C()
    monkeypatch.setattr("framework_power.cli.get_client", lambda env: fake)
    rc = main(["webresource", "publish", "new_/js/a.js", "--env", "dev"])
    assert rc == 0
    assert fake.published == ["wr-new_/js/a.js"]


# ----------------------------------------------------------------- form (Phase 5)


_FORM_PY = (
    "from framework_power import Form, FormType\n"
    "from framework_power.form_xml import new_form\n"
    "FORM: Form = new_form('new_CliDemo', 'new_clidemo')\n"
)


def test_cli_form_show_offline(tmp_path, capsys):
    f = tmp_path / "clidemo.py"
    f.write_text(_FORM_PY, encoding="utf-8")
    rc = main(["form", "show", str(f)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "new_CliDemo" in out and "GENERAL_TAB" in out


def test_cli_form_lint_passes(tmp_path, capsys):
    f = tmp_path / "clidemo.py"
    f.write_text(_FORM_PY, encoding="utf-8")
    rc = main(["form", "lint", str(f)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[lint]" in out


def test_cli_form_deploy_uses_client(tmp_path, monkeypatch, capsys):
    f = tmp_path / "clidemo.py"
    f.write_text(_FORM_PY, encoding="utf-8")

    class FakeClient:
        def __init__(self):
            self.published = []

        def get_form_by_name(self, entity, name, *, form_type=None):
            return None

        def get_form_by_id(self, fid):
            return {}

        def create_form(self, payload):
            return {"formid": "fid", "name": payload["name"]}

        def update_form(self, fid, patch):
            return {}

        def publish_entity(self, entity):
            self.published.append(entity)
            return {"published": True, "entity": entity}

    fake = FakeClient()
    monkeypatch.setattr("framework_power.cli.get_client", lambda env: fake)
    monkeypatch.setattr("framework_power.cli._publisher_prefix", lambda *a, **k: "new")
    rc = main(["form", "deploy", str(f), "--env", "dev"])
    out = capsys.readouterr().out
    assert rc == 0
    assert fake.published == ["new_clidemo"]
    assert "created" in out


def test_cli_form_reverse_writes_file(tmp_path, monkeypatch, capsys):
    class FakeClient:
        def list_forms_by_entity(self, entity):
            return [{
                "formid": "fid", "name": "new_CliDemo", "objecttypecode": "new_clidemo",
                "formxml": "<form><tabs/></form>", "type": 2, "description": "",
            }]

        def get_form_by_id(self, fid):
            return self.list_forms_by_entity("x")[0]

    fake = FakeClient()
    monkeypatch.setattr("framework_power.cli.get_client", lambda env: fake)
    out_dir = tmp_path / "forms"
    rc = main(["form", "reverse", "new_clidemo", "--forms-dir", str(out_dir), "--env", "dev"])
    assert rc == 0
    written = list(out_dir.glob("*.py"))
    assert written and "FORM" in written[0].read_text(encoding="utf-8")


# ----------------------------------------------------------------- view (Phase 6)


_VIEW_PY = (
    "from framework_power import View, QueryType\n"
    "from framework_power.view_xml import new_view, add_column\n"
    "VIEW: View = add_column(\n"
    "    new_view('new_CliView', 'new_cliview', primary_id='new_cliviewid', object_type_code=100),\n"
    "    'new_name',\n"
    ")\n"
)


def test_cli_view_show_offline(tmp_path, capsys):
    f = tmp_path / "v.py"
    f.write_text(_VIEW_PY, encoding="utf-8")
    rc = main(["view", "show", str(f)])
    out = capsys.readouterr().out
    assert rc == 0 and "new_CliView" in out and "new_name" in out


def test_cli_view_lint_passes(tmp_path, capsys):
    f = tmp_path / "v.py"
    f.write_text(_VIEW_PY, encoding="utf-8")
    rc = main(["view", "lint", str(f)])
    out = capsys.readouterr().out
    assert rc == 0 and "[lint]" in out


def test_cli_view_deploy_uses_client(tmp_path, monkeypatch, capsys):
    f = tmp_path / "v.py"
    f.write_text(_VIEW_PY, encoding="utf-8")

    class FakeClient:
        def __init__(self):
            self.published = []

        def get_view_by_name(self, entity, name, *, query_type=None):
            return None

        def get_view_by_id(self, sqid):
            return {}

        def get_object_type_code(self, entity):
            return 100

        def create_view(self, payload):
            return {"savedqueryid": "vid", "name": payload["name"]}

        def update_view(self, sqid, patch):
            return {}

        def publish_entity(self, entity):
            self.published.append(entity)
            return {"published": True, "entity": entity}

    fake = FakeClient()
    monkeypatch.setattr("framework_power.cli.get_client", lambda env: fake)
    monkeypatch.setattr("framework_power.cli._publisher_prefix", lambda *a, **k: "new")
    rc = main(["view", "deploy", str(f), "--env", "dev"])
    out = capsys.readouterr().out
    assert rc == 0 and fake.published == ["new_cliview"] and "created" in out


def test_cli_view_reverse_writes_file(tmp_path, monkeypatch, capsys):
    class FakeClient:
        def list_views_by_entity(self, entity):
            return [{
                "savedqueryid": "vid", "name": "new_CliView", "returnedtypecode": "new_cliview",
                "querytype": 0, "fetchxml": "<fetch><entity name='new_cliview'>"
                "<attribute name='new_cliviewid'/></entity></fetch>",
                "layoutxml": "<grid object='100'><row id='new_cliviewid'/></grid>", "description": "",
            }]

        def get_view_by_id(self, sqid):
            return self.list_views_by_entity("x")[0]

    fake = FakeClient()
    monkeypatch.setattr("framework_power.cli.get_client", lambda env: fake)
    out_dir = tmp_path / "views"
    rc = main(["view", "reverse", "new_cliview", "--views-dir", str(out_dir), "--env", "dev"])
    assert rc == 0
    written = list(out_dir.glob("*.py"))
    assert written and "VIEW" in written[0].read_text(encoding="utf-8")
