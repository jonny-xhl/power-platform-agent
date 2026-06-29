"""
Form sync standalone flow (framework_power Phase 5).

A standalone flow that treats **authored ``Form`` models** as the source of truth and
reconciles them against Dataverse system forms — covering the two real workflows:
(a) edit an existing form's page layout / bind events, (b) author a brand-new form.

Flows:
- ``plan_forms``   — read-only: per-form ``would_create`` / ``would_update`` /
  ``would_skip`` (unchanged) / ``would_skip_standard``. Diff is on the STRUCTURED model,
  so a reverse->forward round-trip of an unedited form is a no-op (never rewrites a real
  form with a lossy regenerated formxml).
- ``sync_forms``   — create/update each (reuses the Phase-2 ``components.form`` handler)
  only when the model changed, optional add to a solution (code 60; idempotent), optional
  **entity-scoped** ``PublishXml`` (forms publish per-entity, not per-form).
- ``reverse_forms`` — env -> local: parse each form's formxml into a ``Form`` and write a
  codegen'd Python file (one per form) under ``metadata_py/forms/``.

Non-destructive: ``sync`` only creates/updates (never deletes); the structured-model
diff additionally skips unchanged forms. Forms are authored as Python, not scanned.
"""

from __future__ import annotations

import importlib.util
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from .components import form as form_component
from .components._common import is_custom
from .components.models import Form
from .deployer import _is_already_exists

logger = logging.getLogger(__name__)


def load_form(path: Any) -> Form:
    """Load a ``Form`` from a Python module file that exports ``FORM``.

    The file does ``from framework_power import Form, FormType, ...`` and defines
    ``FORM: Form = Form(...)`` (typical output of ``form reverse`` or AI authoring).
    """
    path = Path(path)
    spec = importlib.util.spec_from_file_location(f"_form_def_{path.stem}", str(path))
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load form definition file: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    form = getattr(mod, "FORM", None)
    if not isinstance(form, Form):
        raise ValueError(f"{path} does not export a Form as `FORM`")
    return form


@dataclass
class FormSyncConfig:
    """Tunables for inter-operation sleeps (metadata propagation)."""

    after_change_delay: float = 0.5
    between_adds_delay: float = 0.3
    sleep: Callable[[float], None] = time.sleep


# ----------------------------------------------------------------- reverse helper


def _reverse_live(client: Any, form: Form) -> Optional[Form]:
    """Reverse the live form matching ``(entity, name, form_type)``; ``None`` if absent.

    ``form_type`` is included because Dataverse auto-creates several forms all named
    "Information" (Main/QuickView/Card) — a name-only lookup is ambiguous.
    """
    existing = client.get_form_by_name(form.entity, form.name, form_type=int(form.form_type))
    if not existing:
        return None
    return form_component.reverse(client, existing["formid"])


def _existing_id(client: Any, form: Form) -> Optional[str]:
    existing = client.get_form_by_name(form.entity, form.name, form_type=int(form.form_type))
    return existing.get("formid") if existing else None


# ----------------------------------------------------------------- plan


def plan_forms(client: Any, forms: list[Form], *, prefix: str = "new") -> dict[str, Any]:
    """Read-only dry run over authored forms.

    Actions: ``would_create`` / ``would_update`` (model changed) / ``would_skip`` (model
    unchanged vs live) / ``would_skip_standard`` (non-custom name).
    """
    entries: list[dict[str, Any]] = []
    for form in forms:
        # Customness is ENTITY-based (an auto-created form like "Information" on a custom
        # table is editable; forms on standard entities are skipped).
        if not is_custom(form.entity, prefix):
            entries.append(
                {"name": form.name, "entity": form.entity, "plan": {"action": "would_skip_standard"}}
            )
            continue
        try:
            live = _reverse_live(client, form)
        except Exception as e:  # noqa: BLE001
            entries.append(
                {"name": form.name, "entity": form.entity, "plan": {"action": "failed", "error": str(e)}}
            )
            continue
        if live is None:
            action = "would_create"
        elif live == form:
            action = "would_skip"
        else:
            action = "would_update"
        entries.append({"name": form.name, "entity": form.entity, "plan": {"action": action}})
    return {"forms": entries}


# ----------------------------------------------------------------- sync


def sync_forms(
    client: Any,
    forms: list[Form],
    *,
    prefix: str = "new",
    solution: Optional[str] = None,
    publish: bool = True,
    config: Optional[FormSyncConfig] = None,
) -> dict[str, Any]:
    """Sync authored forms to Dataverse (non-destructive, idempotent).

    Skips unchanged forms (structured-model diff). When ``solution`` is given, adds every
    changed form to that solution (code 60; idempotent). When ``publish`` is true, runs an
    entity-scoped ``PublishXml`` per distinct changed entity (forms publish per-entity).
    """
    cfg = config or FormSyncConfig()
    result: dict[str, Any] = {"synced": [], "added": [], "publish": {}}

    changed: list[tuple[Form, str]] = []  # (form, id) of forms actually written
    changed_entities: set[str] = set()

    for form in forms:
        if not is_custom(form.entity, prefix):  # entity-based; see plan_forms()
            result["synced"].append({"name": form.name, "deploy": {"action": "skipped_standard"}})
            continue
        try:
            live = _reverse_live(client, form)
        except Exception as e:  # noqa: BLE001
            result["synced"].append({"name": form.name, "deploy": {"action": "failed", "error": str(e)}})
            continue
        if live is not None and live == form:
            # Unchanged: leave the live formxml untouched (non-destructive).
            result["synced"].append(
                {"name": form.name, "deploy": {"action": "skipped_unchanged", "id": _existing_id(client, form)}}
            )
            continue
        try:
            deploy_entry = form_component.deploy(client, form, prefix=prefix)
        except Exception as e:  # noqa: BLE001
            result["synced"].append({"name": form.name, "deploy": {"action": "failed", "error": str(e)}})
            continue
        result["synced"].append({"name": form.name, "deploy": deploy_entry})
        oid = deploy_entry.get("id") if isinstance(deploy_entry, dict) else None
        if oid:
            changed.append((form, str(oid)))
            changed_entities.add(form.entity)
        cfg.sleep(cfg.after_change_delay)

    # Optional: add each changed form to the solution (code 60; idempotent).
    if solution and changed:
        for _form, oid in changed:
            try:
                client.add_solution_component(solution, form_component.SOLUTION_CODE, oid)
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

    # Optional: entity-scoped publish of the changed entities.
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
    """Filesystem-safe slug from a form name (keeps unicode letters/digits)."""
    slug = re.sub(r"[^\w]+", "_", name, flags=re.UNICODE).strip("_")
    return slug or "form"


def _form_file_source(form: Form) -> str:
    """Emit a full Python module exporting ``FORM`` for a reversed form."""
    imports = ", ".join(form_component.CODEGEN_IMPORTS)
    literal = form_component.codegen(form)
    header = (
        '"""Auto-generated by framework_power form reverse (Phase 5).\n\n'
        "Edit the typed Form model below (or regenerate); re-deploy with\n"
        "framework_power form deploy.\n"
        '"""\n\n'
    )
    return header + f"from framework_power import {imports}\n\nFORM: Form = {literal}\n"


def reverse_forms(
    client: Any,
    entity: str,
    *,
    out_dir: Any,
    prefix: str = "new",
) -> dict[str, Any]:
    """Pull every system form for ``entity`` into codegen'd Python files (one per form).

    Each form's ``formxml`` is parsed into a structured :class:`Form` and written to
    ``<out_dir>/{entity}__{slug(form_name)}.py`` exporting ``FORM``.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    records = client.list_forms_by_entity(entity)
    written: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    used_names: set[str] = set()
    for rec in records:
        formid = rec.get("formid") or ""
        try:
            form = form_component.reverse(client, formid)
        except Exception as e:  # noqa: BLE001
            skipped.append({"name": rec.get("name"), "reason": f"parse failed: {e}"})
            continue
        base = f"{entity}__{_slug(form.name)}"
        fname = base + ".py"
        i = 2
        while fname in used_names:
            fname = f"{base}_{i}.py"
            i += 1
        used_names.add(fname)
        path = out / fname
        path.write_text(_form_file_source(form), encoding="utf-8")
        written.append(
            {"name": form.name, "type": form.form_type.name, "form_type": int(form.form_type), "path": str(path)}
        )
    return {"entity": entity, "out_dir": str(out), "written": written, "skipped": skipped}
