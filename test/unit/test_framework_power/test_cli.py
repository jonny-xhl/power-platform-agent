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
