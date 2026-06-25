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

