"""环境变更守卫（ADR-013）：任何环境写操作前，先备份、留台账。

动机（2026-08-19 事故，见 adr-013）：一次基于"未合并分支本地 DLL"的孤儿清理误删了
13 个 plugin step + 11 个 plugintype，恢复时发现**没有任何可查的备份或操作记录**——
solution ZIP 覆盖不到 org 级注册（不在解决方案里的 step/plugintype 不会导出），
也没有台账说明"何时、谁、改了什么、依据是什么"。

本模块把备份与记录固化为引擎一等能力：

- :func:`backup_solution` — 导出 solution ZIP 到 ``workspace/docs/env_backup/{名称}.zip``；
  已存在时轮转（重命名为带 UTC 时间戳的历史版本），始终保留最新一份 + 全部历史。
- :func:`snapshot_plugin_registrations` — **org 级插件注册快照**（JSON）：环境内全部
  assemblies → plugintypes → steps（含 stage/mode/filteringattributes）→ step images。
  这是 solution ZIP 的盲区补充：org 级注册的组件不进 solution 导出。
- :func:`append_change` / :func:`read_journal` — append-only 变更台账
  （``docs/env_backup/CHANGELOG.md``）：每条记录时间、环境、操作者、意图、
  变更明细、备份文件、依据（脚本/ADR/工单）。**恢复时先查台账。**

典型用法（任何 agent 改环境前的标准动作）::

    from framework_power.workspace import Workspace
    from framework_power.components import env_guard

    ws = Workspace.discover("ninebot-project")
    bak = env_guard.backup_solution(client, "new_plugin930", ws)
    snap = env_guard.snapshot_plugin_registrations(client, ws)
    env_guard.append_change(ws, env="dev", actor="agent", intent="...",
                            changes=[...], backups=[bak, snap])

CLI：``pp env-guard backup|snapshot|log|show``。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# 备份根目录相对 workspace 根：docs/env_backup/（ADR-013 用户指定）
BACKUP_DIRNAME = "docs/env_backup"
JOURNAL_FILENAME = "CHANGELOG.md"
_TIMESTAMP_RE = re.compile(r"\.\d{8}T\d{6}Z\.zip$")
# 系统程序集前缀（org 里数千系统 step；快照默认跳过，live 踩坑：全量遍历 + 逐 step 查询会超时）
SYSTEM_ASSEMBLY_PREFIXES = ("Microsoft.", "System.")


@dataclass
class GuardResult:
    """One backup/snapshot outcome (serializable for reports and the journal)."""
    kind: str                      # "solution_zip" | "plugin_snapshot"
    target: str                    # solution name or "org:<assembly-scope>"
    path: str                      # absolute backup file path
    rotated_from: Optional[str] = None  # previous file renamed away (timestamped history)
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind, "target": self.target, "path": self.path,
            "rotated_from": self.rotated_from, **self.detail,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def backup_dir(ws: Any) -> Path:
    """Resolve (and create) ``<workspace>/docs/env_backup``."""
    d = Path(ws.root) / BACKUP_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _rotate_existing(path: Path) -> Optional[str]:
    """Rename an existing backup to a timestamped sibling; return the old->new path str."""
    if not path.exists():
        return None
    stamped = path.with_name(f"{path.stem}.{_stamp()}{path.suffix}")
    path.rename(stamped)
    return str(stamped)


def backup_solution(client: Any, solution_name: str, ws: Any,
                    *, managed: bool = False) -> GuardResult:
    """Export ``solution_name`` (unmanaged by default) to ``docs/env_backup/{name}.zip``.

    Overwrites are never lost: an existing file rotates to ``{name}.{UTC}.zip`` first.
    The fresh export always lands on the canonical ``{name}.zip`` path so the latest
    state is always obvious during recovery.
    """
    out = backup_dir(ws) / f"{solution_name}.zip"
    rotated = _rotate_existing(out)
    # export BEFORE rotating would risk losing the old file on export failure — we rotate
    # first, then write; on export failure the rotated history still exists.
    zip_bytes = client.export_solution(solution_name, managed=managed)
    out.write_bytes(zip_bytes)
    return GuardResult(
        kind="solution_zip", target=solution_name, path=str(out),
        rotated_from=rotated,
        detail={"size_bytes": len(zip_bytes), "managed": managed},
    )


def snapshot_plugin_registrations(client: Any, ws: Any,
                                  *, assemblies: Optional[list[str]] = None,
                                  include_system: bool = False) -> GuardResult:
    """Capture org-level plugin registrations as JSON (the solution-ZIP blind spot).

    Walks assemblies → plugintypes → steps → step images (images fetched in chunked
    OR-filter bulk queries, NOT one request per step). ``assemblies`` filters by name;
    by default system assemblies (``Microsoft.*`` / ``System.*`` — thousands of system
    steps, the 2026-08-19 timeout pitfall) are skipped; pass ``include_system=True``
    to capture them too. Steps registered OUTSIDE any solution (org-level, like the 88
    surviving steps in the 2026-08-19 incident) are captured here even though a solution
    export never includes them.
    """
    all_assemblies = client.get_plugin_assemblies()
    if assemblies:
        all_assemblies = [a for a in all_assemblies if a.get("name") in set(assemblies)]
    elif not include_system:
        all_assemblies = [
            a for a in all_assemblies
            if not str(a.get("name", "")).startswith(SYSTEM_ASSEMBLY_PREFIXES)
        ]

    payload: dict[str, Any] = {"captured_at": _utc_now(), "assemblies": []}
    for asm in all_assemblies:
        aid = asm.get("pluginassemblyid")
        ptypes = client.get_plugintypes_by_assembly(aid)
        steps = client.get_steps_by_assembly(aid)
        step_ids = [s.get("sdkmessageprocessingstepid") for s in steps]
        images = _images_by_step(client, step_ids)
        payload["assemblies"].append({
            "pluginassemblyid": aid,
            "name": asm.get("name"),
            "version": asm.get("version"),
            "plugintypes": ptypes,
            "steps": steps,
            "step_images": images,
        })

    fname = f"plugin-registrations{_scope_suffix(assemblies)}.json"
    out = backup_dir(ws) / fname
    rotated = _rotate_existing(out)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return GuardResult(
        kind="plugin_snapshot",
        target=f"org:{'+'.join(assemblies)}" if assemblies else "org:custom",
        path=str(out), rotated_from=rotated,
        detail={"assemblies": len(payload["assemblies"]),
                "steps": sum(len(a["steps"]) for a in payload["assemblies"]),
                "images": sum(len(imgs) for a in payload["assemblies"]
                              for imgs in a["step_images"].values())},
    )


def _images_by_step(client: Any, step_ids: list[Any], *, chunk: int = 15) -> dict[str, list]:
    """Fetch step images for many steps, grouped by step id.

    One bulk query per ``chunk`` ids (OR filter) instead of one request per step —
    ~105 custom steps drop from 105 requests to 8.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    ids = [sid for sid in step_ids if sid]
    for i in range(0, len(ids), chunk):
        for img in client.get_step_images_bulk(ids[i:i + chunk]):
            sid = img.get("_sdkmessageprocessingstepid_value")
            if sid:
                grouped.setdefault(sid, []).append(img)
    return grouped


def _scope_suffix(assemblies: Optional[list[str]]) -> str:
    if not assemblies:
        return ""
    slug = "-".join(a.replace(".", "_") for a in assemblies[:3])
    return f"-{slug}" + ("+more" if len(assemblies) > 3 else "")


def journal_path(ws: Any) -> Path:
    return backup_dir(ws) / JOURNAL_FILENAME


_ENTRY_HEADER = "## "


def append_change(ws: Any, *, env: str, actor: str, intent: str,
                  changes: list[dict[str, Any]],
                  backups: Optional[list[GuardResult | dict[str, Any]]] = None,
                  basis: str = "") -> Path:
    """Append one entry to the append-only change journal (CHANGELOG.md).

    ADR-013 contract: every environment write is journaled truthfully — no rewriting
    history; corrections are new entries, not edits. Recovery starts by reading this
    journal.
    """
    lines = [
        f"{_ENTRY_HEADER}{_utc_now()} | env={env} | actor={actor}",
        f"- **intent**: {intent}",
    ]
    if basis:
        lines.append(f"- **basis**: {basis}")  # script / ADR / ticket / manifest reference
    lines.append("- **changes**:")
    for c in changes:
        lines.append(f"  - {json.dumps(c, ensure_ascii=False)}")
    if backups:
        lines.append("- **backups**:")
        for b in backups:
            entry = b.to_dict() if isinstance(b, GuardResult) else b
            lines.append(f"  - {json.dumps(entry, ensure_ascii=False)}")
    else:
        lines.append("- **backups**: NONE ⚠️ (justify in intent, e.g. read-only op)")
    lines.append("")
    p = journal_path(ws)
    with p.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return p


def read_journal(ws: Any, *, last: Optional[int] = None) -> list[dict[str, Any]]:
    """Parse the journal back into structured entries (newest last). ``last=N`` tails."""
    p = journal_path(ws)
    if not p.exists():
        return []
    entries: list[dict[str, Any]] = []
    current: Optional[dict[str, Any]] = None
    for raw in p.read_text(encoding="utf-8").splitlines():
        if raw.startswith(_ENTRY_HEADER):
            current = {"header": raw[len(_ENTRY_HEADER):].strip(), "lines": []}
            entries.append(current)
        elif current is not None:
            current["lines"].append(raw)
    return entries[-last:] if last else entries


def list_backups(ws: Any) -> list[dict[str, Any]]:
    """Inventory of the backup dir (zip/json + rotated history)."""
    d = backup_dir(ws)
    out = []
    for f in sorted(d.iterdir()):
        if not f.is_file():
            continue
        out.append({"file": f.name, "size_bytes": f.stat().st_size,
                    "modified_utc": datetime.fromtimestamp(
                        f.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")})
    return out
