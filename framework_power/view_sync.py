"""
View sync standalone flow (framework_power Phase 6).

A standalone flow that treats **authored ``View`` models** as the source of truth and reconciles them
against Dataverse saved queries — covering: author a new Public view, edit an existing view's
columns/sort/filter, and update the auto-created system views (QuickFind/Lookup/Associated/
AdvancedFind) in place.

Flows:
- ``plan_views``   — read-only: per-view ``would_create`` / ``would_update`` / ``would_skip``
  (unchanged) / ``would_skip_standard``. Diff is on the STRUCTURED model, so a reverse->forward
  round-trip of an unedited view is a no-op (never rewrites a real view with a lossy regenerated XML).
- ``sync_views``   — create/update each (reuses the Phase-2 ``components.view`` handler) only when the
  model changed, optional add to a solution (code 26; idempotent), optional **entity-scoped**
  ``PublishXml`` (views publish per-entity). Auto-fills ``object_type_code`` for authored views.
- ``reverse_views`` — env -> local: parse each view's fetchxml+layoutxml into a ``View`` and write a
  codegen'd Python file (one per view) under ``metadata_py/views/``.

Non-destructive: ``sync`` only creates/updates (never deletes); the structured-model diff additionally
skips unchanged views. Views are authored as Python, not scanned.
"""

from __future__ import annotations

import importlib.util
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from .components import view as view_component
from .components.compact import normalize
from .components.models import View
from .deployer import _is_already_exists

logger = logging.getLogger(__name__)


@dataclass
class ViewSyncConfig:
    """Tunables for inter-operation sleeps (metadata propagation)."""

    after_change_delay: float = 0.5
    between_adds_delay: float = 0.3
    sleep: Callable[[float], None] = time.sleep


def load_view(path: Any) -> View:
    """Load a ``View`` from a Python module file that exports ``VIEW``."""
    path = Path(path)
    spec = importlib.util.spec_from_file_location(f"_view_def_{path.stem}", str(path))
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load view definition file: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    view = getattr(mod, "VIEW", None)
    if not isinstance(view, View):
        raise ValueError(f"{path} does not export a View as `VIEW`")
    return view


# ----------------------------------------------------------------- reverse helper


def _models_equal(a: View, b: View) -> bool:
    """Structured equality for the skip-if-unchanged diff (compact-aware)."""
    return normalize(a) == normalize(b)


def _reverse_live(client: Any, view: View) -> Optional[View]:
    """Reverse the live view matching ``(entity, name, query_type)``; ``None`` if absent.

    ``query_type`` is included because the auto-created views share names; it disambiguates.
    """
    existing = client.get_view_by_name(view.entity, view.name, query_type=int(view.query_type))
    if not existing:
        return None
    return view_component.reverse(client, existing["savedqueryid"])


def _existing_id(client: Any, view: View) -> Optional[str]:
    existing = client.get_view_by_name(view.entity, view.name, query_type=int(view.query_type))
    return existing.get("savedqueryid") if existing else None


def _fill_object_type_code(client: Any, view: View) -> View:
    """For authored views missing the integer ObjectTypeCode, look it up (LayoutXml needs it)."""
    if not view.object_type_code:
        try:
            view.object_type_code = client.get_object_type_code(view.entity)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"could not look up ObjectTypeCode for '{view.entity}': {e}")
    return view


# ----------------------------------------------------------------- plan


def plan_views(client: Any, views: list[View], *, prefix: str = "new") -> dict[str, Any]:
    """Read-only dry run over authored views (structured-model diff)."""
    entries: list[dict[str, Any]] = []
    for view in views:
        # Views on standard entities are supported (relaxed; see components/view.deploy).
        try:
            live = _reverse_live(client, view)
        except Exception as e:  # noqa: BLE001
            entries.append(
                {"name": view.name, "entity": view.entity, "plan": {"action": "failed", "error": str(e)}}
            )
            continue
        if live is None:
            action = "would_create"
        elif _models_equal(live, view):
            action = "would_skip"
        else:
            action = "would_update"
        entries.append({"name": view.name, "entity": view.entity, "plan": {"action": action}})
    return {"views": entries}


# ----------------------------------------------------------------- sync


def sync_views(
    client: Any,
    views: list[View],
    *,
    prefix: str = "new",
    solution: Optional[str] = None,
    publish: bool = True,
    config: Optional[ViewSyncConfig] = None,
) -> dict[str, Any]:
    """Sync authored views to Dataverse (non-destructive, idempotent).

    Skips unchanged views (structured-model diff). Fills ``object_type_code`` for authored views.
    When ``solution`` is given, adds every changed view to it (code 26; idempotent). When ``publish``
    is true, runs an entity-scoped ``PublishXml`` per distinct changed entity.
    """
    cfg = config or ViewSyncConfig()
    result: dict[str, Any] = {"synced": [], "added": [], "publish": {}}

    changed: list[tuple[View, str]] = []
    changed_entities: set[str] = set()

    for view in views:
        _fill_object_type_code(client, view)
        try:
            live = _reverse_live(client, view)
        except Exception as e:  # noqa: BLE001
            result["synced"].append({"name": view.name, "deploy": {"action": "failed", "error": str(e)}})
            continue
        if live is not None and _models_equal(live, view):
            result["synced"].append(
                {"name": view.name, "deploy": {"action": "skipped_unchanged", "id": _existing_id(client, view)}}
            )
            continue
        try:
            deploy_entry = view_component.deploy(client, view, prefix=prefix)
        except Exception as e:  # noqa: BLE001
            result["synced"].append({"name": view.name, "deploy": {"action": "failed", "error": str(e)}})
            continue
        result["synced"].append({"name": view.name, "deploy": deploy_entry})
        oid = deploy_entry.get("id") if isinstance(deploy_entry, dict) else None
        if oid:
            changed.append((view, str(oid)))
            changed_entities.add(view.entity)
        cfg.sleep(cfg.after_change_delay)

    if solution and changed:
        for _view, oid in changed:
            try:
                client.add_solution_component(solution, view_component.SOLUTION_CODE, oid)
                result["added"].append({"name": solution, "object_id": oid, "action": "added"})
            except Exception as e:  # noqa: BLE001
                if _is_already_exists(e):
                    result["added"].append(
                        {"name": solution, "object_id": oid, "action": "already_in_solution"}
                    )
                else:
                    result["added"].append(
                        {"name": solution, "object_id": oid, "action": "failed", "error": str(e)}
                    )
            cfg.sleep(cfg.between_adds_delay)

    if publish and changed_entities:
        published = []
        for entity in sorted(changed_entities):
            try:
                client.publish_entity(entity)
                published.append({"entity": entity, "published": True})
            except Exception as e:  # noqa: BLE001
                published.append({"entity": entity, "published": False, "error": str(e)})
                logger.warning(f"PublishXml for entity '{entity}' failed: {e}")
        result["publish"] = {"entities": published}

    return result


# ----------------------------------------------------------------- reverse


def _slug(name: str) -> str:
    slug = re.sub(r"[^\w]+", "_", name, flags=re.UNICODE).strip("_")
    return slug or "view"


def _view_file_source(view: View) -> str:
    imports = ", ".join(view_component.CODEGEN_IMPORTS)
    literal = view_component.codegen(view)
    header = (
        '"""Auto-generated by framework_power view reverse (Phase 6).\n\n'
        "Edit the typed View model below (or regenerate); re-deploy with\n"
        "framework_power view deploy.\n"
        '"""\n\n'
    )
    return header + f"from framework_power import {imports}\n\nVIEW: View = {literal}\n"


def reverse_views(
    client: Any,
    entity: str,
    *,
    out_dir: Any,
    prefix: str = "new",
) -> dict[str, Any]:
    """Pull every saved query for ``entity`` into codegen'd Python files (one per view).

    Each view's fetchxml+layoutxml is parsed into a structured :class:`View` and written to
    ``<out_dir>/{entity}__{slug(name)}.py`` exporting ``VIEW``.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    records = client.list_views_by_entity(entity)
    written: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    used_names: set[str] = set()
    for rec in records:
        sqid = rec.get("savedqueryid") or ""
        try:
            view = view_component.reverse(client, sqid)
        except Exception as e:  # noqa: BLE001
            skipped.append({"name": rec.get("name"), "reason": f"parse failed: {e}"})
            continue
        base = f"{entity}__{_slug(view.name)}"
        fname = base + ".py"
        i = 2
        while fname in used_names:
            fname = f"{base}_{i}.py"
            i += 1
        used_names.add(fname)
        path = out / fname
        path.write_text(_view_file_source(view), encoding="utf-8")
        written.append(
            {"name": view.name, "query_type": view.query_type.name, "querytype": int(view.query_type),
             "path": str(path)}
        )
    return {"entity": entity, "out_dir": str(out), "written": written, "skipped": skipped}


# Re-export QueryType for convenience (the codegen'd files import it from framework_power).
__all__ = ["ViewSyncConfig", "load_view", "plan_views", "sync_views", "reverse_views"]
