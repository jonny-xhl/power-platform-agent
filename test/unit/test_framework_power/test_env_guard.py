"""Unit tests for framework_power.components.env_guard (fake client + tmp workspace)."""

import json
from pathlib import Path

import pytest

from framework_power.components import env_guard

pytestmark = pytest.mark.unit


class FakeWorkspace:
    def __init__(self, root: Path) -> None:
        self.root = root


class FakeClient:
    """Supports export_solution + plugin registration reads with canned data."""

    def __init__(self) -> None:
        self.exports: list[str] = []
        # one assembly → 2 types → 2 steps → 1 image on the first step
        self.assemblies = [{
            "pluginassemblyid": "asm-1", "name": "Eden.Ninebot.Plugin.Sales", "version": "1.0.0.0",
        }]
        self.plugintypes = {"asm-1": [
            {"plugintypeid": "pt-1", "typename": "Ns.A", "name": "A"},
            {"plugintypeid": "pt-2", "typename": "Ns.B", "name": "B"},
        ]}
        self.steps = {"asm-1": [
            {"sdkmessageprocessingstepid": "st-1", "name": "Ns.A: Create of new_x", "stage": 40},
            {"sdkmessageprocessingstepid": "st-2", "name": "Ns.B: Update of new_x", "stage": 40},
        ]}
        self.images = {"st-1": [{"entityalias": "PreImage", "imagetype": 0}]}

    def export_solution(self, name, *, managed=False):
        self.exports.append(name)
        return f"ZIPBYTES[{name},managed={managed}]".encode()

    def get_plugin_assemblies(self):
        return self.assemblies

    def get_plugintypes_by_assembly(self, aid):
        return self.plugintypes[aid]

    def get_steps_by_assembly(self, aid):
        return self.steps[aid]

    def get_step_images(self, sid):
        return self.images.get(sid, [])

    def get_step_images_bulk(self, sids):
        return [
            dict(img, _sdkmessageprocessingstepid_value=sid)
            for sid in sids for img in self.images.get(sid, [])
        ]


@pytest.fixture()
def ws(tmp_path):
    return FakeWorkspace(tmp_path)


def test_backup_solution_writes_canonical_zip(ws):
    client = FakeClient()
    res = env_guard.backup_solution(client, "new_plugin930", ws)
    assert res.kind == "solution_zip"
    assert res.rotated_from is None
    out = Path(res.path)
    assert out == ws.root / "docs" / "env_backup" / "new_plugin930.zip"
    assert out.exists()
    assert client.exports == ["new_plugin930"]


def test_backup_solution_rotates_previous(ws):
    client = FakeClient()
    env_guard.backup_solution(client, "sol", ws)
    res2 = env_guard.backup_solution(client, "sol", ws)
    # canonical path always holds the fresh export; history keeps a timestamped copy
    assert res2.rotated_from is not None and ".zip" in res2.rotated_from
    files = list((ws.root / "docs" / "env_backup").glob("*.zip"))
    assert len(files) == 2


def test_snapshot_plugin_registrations_captures_full_graph(ws):
    client = FakeClient()
    res = env_guard.snapshot_plugin_registrations(client, ws)
    data = json.loads(Path(res.path).read_text(encoding="utf-8"))
    assert data["assemblies"][0]["name"] == "Eden.Ninebot.Plugin.Sales"
    assert len(data["assemblies"][0]["plugintypes"]) == 2
    assert len(data["assemblies"][0]["steps"]) == 2
    # images grouped by step id via the bulk query's lookup field
    imgs = data["assemblies"][0]["step_images"]["st-1"]
    assert imgs[0]["entityalias"] == "PreImage" and imgs[0]["imagetype"] == 0
    assert imgs[0]["_sdkmessageprocessingstepid_value"] == "st-1"
    assert res.detail["steps"] == 2
    assert res.detail["images"] == 1


def test_snapshot_filters_assemblies(ws):
    client = FakeClient()
    client.assemblies.append({"pluginassemblyid": "asm-2", "name": "Other", "version": "1"})
    env_guard.snapshot_plugin_registrations(client, ws, assemblies=["Eden.Ninebot.Plugin.Sales"])
    fname = [f for f in (ws.root / "docs" / "env_backup").glob("plugin-registrations*.json")]
    data = json.loads(fname[0].read_text(encoding="utf-8"))
    assert [a["name"] for a in data["assemblies"]] == ["Eden.Ninebot.Plugin.Sales"]


def test_snapshot_skips_system_assemblies_by_default(ws):
    client = FakeClient()
    client.assemblies.append({"pluginassemblyid": "asm-ms", "name": "Microsoft.Crm.Service", "version": "9"})
    client.plugintypes["asm-ms"] = [{"plugintypeid": "pt-ms", "typename": "Ms.T", "name": "T"}]
    client.steps["asm-ms"] = [{"sdkmessageprocessingstepid": "st-ms", "name": "Ms.T: Create of account", "stage": 40}]
    res = env_guard.snapshot_plugin_registrations(client, ws)
    data = json.loads(Path(res.path).read_text(encoding="utf-8"))
    names = [a["name"] for a in data["assemblies"]]
    assert names == ["Eden.Ninebot.Plugin.Sales"]          # system assembly skipped
    assert res.detail["assemblies"] == 1
    # explicit opt-in captures it
    res2 = env_guard.snapshot_plugin_registrations(client, ws, include_system=True)
    data2 = json.loads(Path(res2.path).read_text(encoding="utf-8"))
    assert len(data2["assemblies"]) == 2


def test_journal_append_and_read_roundtrip(ws):
    backups = [env_guard.GuardResult(kind="solution_zip", target="sol", path="/x/sol.zip")]
    env_guard.append_change(ws, env="dev", actor="agent", intent="deploy RF",
                            changes=[{"op": "create", "target": "step:1"}],
                            backups=backups, basis="deploy.py")
    env_guard.append_change(ws, env="dev", actor="human", intent="hotfix",
                            changes=[{"op": "delete", "target": "step:2"}])
    entries = env_guard.read_journal(ws)
    assert len(entries) == 2
    assert "actor=agent" in entries[0]["header"]
    body = "\n".join(entries[1]["lines"])
    assert "NONE ⚠️" in body  # second entry recorded no backups — flagged, not hidden
    tail = env_guard.read_journal(ws, last=1)
    assert len(tail) == 1 and "hotfix" in "\n".join(tail[0]["lines"])


def test_journal_is_append_only_on_disk(ws):
    p = env_guard.append_change(ws, env="dev", actor="a", intent="1st", changes=[])
    before = p.read_text(encoding="utf-8")
    env_guard.append_change(ws, env="dev", actor="a", intent="2nd", changes=[])
    after = p.read_text(encoding="utf-8")
    assert after.startswith(before)  # history preserved verbatim below new entries


def test_list_backups_includes_rotation_history(ws):
    client = FakeClient()
    env_guard.backup_solution(client, "sol", ws)
    env_guard.backup_solution(client, "sol", ws)
    names = [b["file"] for b in env_guard.list_backups(ws)]
    assert "sol.zip" in names
    assert any(n.startswith("sol.") and n.endswith(".zip") for n in names)
