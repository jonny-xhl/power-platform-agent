# -*- coding: utf-8 -*-
"""Auto-created view/form name localization (ADR-016, live-verified 2026-08-28).

When an entity is created via the Web API, the platform generates the default
system views ("Active X" / "My X" / ... ) and forms ("Information") and stamps
the BASE-language text into EVERY provisioned language's label slot — the 2052
label exists but contains English text, so Chinese-UI users see English names.

This module heals those names on every ``deploy_table``: views/forms still
bearing a default template name get proper bilingual labels (2052 set from the
table's own display-name labels, 1033 kept as generated). Components renamed
away from the template are never touched (non-destructive), and already-
localized components cost nothing beyond the list calls (idempotent fast path).

Naming follows the org's own convention (mirrors the healthy maker-created
tables, e.g. new_vehiclemodel):

======================  ==============================  ==============================
component               English (1033, platform)       Chinese (2052, this module)
======================  ==============================  ==============================
Public view, default    Active {collection}             活动{collection}
Public view, not dflt   Inactive {collection}           停用{collection}
My view (qt=8192)       My {collection}                 我的{collection}
Quick Find (qt=4)       Quick Find Active {collection}  快速查找活动{collection}
Associated (qt=2)       {singular} Associated View      {singular}关联视图
Lookup (qt=64)          {singular} Lookup View          {singular}查找视图
Advanced Find (qt=1)    {singular} Advanced Find View   {singular}高级查找视图
Forms (type 2/6/11)     Information                     信息
======================  ==============================  ==============================
"""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

from .models import Table

EN = 1033
ZH = 2052

# querytype -> {language: template}; qt=0 (Public) is special-cased via isdefault.
_VIEW_TEMPLATES: dict[int, dict[int, str]] = {
    8192: {EN: "My {c}", ZH: "我的{c}"},
    4: {EN: "Quick Find Active {c}", ZH: "快速查找活动{c}"},
    2: {EN: "{s} Associated View", ZH: "{s}关联视图"},
    64: {EN: "{s} Lookup View", ZH: "{s}查找视图"},
    1: {EN: "{s} Advanced Find View", ZH: "{s}高级查找视图"},
}
_PUBLIC_TEMPLATES: dict[bool, dict[int, str]] = {
    True: {EN: "Active {c}", ZH: "活动{c}"},
    False: {EN: "Inactive {c}", ZH: "停用{c}"},
}
_FORM_TEMPLATES: dict[int, str] = {EN: "Information", ZH: "信息"}
_FORM_TYPES = (2, 6, 11)  # Main / QuickView / Card — the auto-created set.


def _display_names(table: Table) -> dict[int, tuple[str, str]]:
    """``{languagecode: (singular, collection)}`` from the table's display labels."""
    out: dict[int, list[str]] = {}
    for label, slot in ((table.display_name, 0), (table.display_collection_name, 1)):
        if label is None:
            continue
        for loc in label.localized:
            out.setdefault(loc.language_code, ["", ""])[slot] = loc.text
    return {lc: (pair[0], pair[1]) for lc, pair in out.items() if pair[0] and pair[1]}


def _expected_view_name(
    querytype: int, is_default: bool, names: dict[int, tuple[str, str]], lang: int
) -> Optional[str]:
    if querytype == 0:
        template = _PUBLIC_TEMPLATES.get(bool(is_default), {}).get(lang)
    else:
        template = _VIEW_TEMPLATES.get(querytype, {}).get(lang)
    if template is None:
        return None
    singular, collection = names[lang]
    return template.format(s=singular, c=collection)


def _classify(current: Optional[str], expected_en: Optional[str], expected_zh: Optional[str]) -> str:
    """Fast path classification from the caller-language ``name`` value."""
    if current == expected_zh:
        return "localized"
    if current == expected_en:
        return "needs_localization"
    return "custom_name"


# --------------------------------------------------------------------- sync


def sync_auto_component_labels(
    client: Any, table: Table, *, sleep: Callable[[float], None] = time.sleep
) -> dict[str, Any]:
    """Set proper 2052 labels on default-named auto views/forms (non-destructive).

    Writes land in the UNPUBLISHED label layer; the entity is published (with
    verify + one retry) so the names actually reach users. Live-verified quirk:
    publishing immediately after the write can miss the labels (metadata
    propagation), hence the sleep-then-verify loop.

    Returns ``{"views": [...], "forms": [...], "changed": bool, "publish": ...}``.
    """
    names = _display_names(table)
    if EN not in names or ZH not in names:
        return {
            "skipped": "table display_name/display_collection_name must carry both "
            "2052 and 1033 labels to derive view/form name templates",
            "changed": False,
        }

    result: dict[str, Any] = {"views": [], "forms": [], "changed": False}
    written: list[tuple[str, str, str]] = []  # (entity_set, pk, expected_zh)
    logical = table.logical_name

    for v in client.list_views_by_entity(logical, select="savedqueryid,name,querytype,isdefault"):
        querytype = int(v.get("querytype", -1))
        if querytype != 0 and querytype not in _VIEW_TEMPLATES:
            continue  # custom querytype: never ours to name
        expected_en = _expected_view_name(querytype, v.get("isdefault"), names, EN)
        expected_zh = _expected_view_name(querytype, v.get("isdefault"), names, ZH)
        state = _classify(v.get("name"), expected_en, expected_zh)
        if state != "needs_localization" or expected_zh is None:
            result["views"].append({"view": v.get("name"), "action": f"skipped_{state}"})
            continue
        try:
            labels = client.retrieve_loc_labels("savedqueries", v["savedqueryid"], "name")
            if labels.get(ZH) == expected_zh:
                result["views"].append({"view": v.get("name"), "action": "skipped_localized"})
                continue
            labels[ZH] = expected_zh
            client.set_loc_labels("savedqueries", v["savedqueryid"], "name", labels)
            result["views"].append(
                {"view": v.get("name"), "action": "localized", "zh": expected_zh})
            result["changed"] = True
            written.append(("savedqueries", str(v["savedqueryid"]), expected_zh))
        except Exception as e:  # noqa: BLE001
            result["views"].append({"view": v.get("name"), "action": "failed", "error": str(e)[:150]})

    for f in client.list_forms_by_entity(logical, select="formid,name,type"):
        if f.get("type") not in _FORM_TYPES:
            continue
        current = f.get("name")
        if current == _FORM_TEMPLATES[ZH]:
            result["forms"].append({"form": current, "action": "skipped_localized"})
            continue
        if current != _FORM_TEMPLATES[EN]:
            result["forms"].append({"form": current, "action": "skipped_custom_name"})
            continue
        try:
            labels = client.retrieve_loc_labels("systemforms", f["formid"], "name")
            if labels.get(ZH) == _FORM_TEMPLATES[ZH]:
                result["forms"].append({"form": current, "action": "skipped_localized"})
                continue
            labels[ZH] = _FORM_TEMPLATES[ZH]
            client.set_loc_labels("systemforms", f["formid"], "name", labels)
            # Live-verified quirk (2026-08-28): SetLocLabels does NOT dirty the form
            # record, so PublishXml(entity) skips the fresh label. A PATCH of the
            # name (same zh text; 1033 stays untouched) marks the form changed and
            # makes the entity publish flush the pending label.
            client.update_form(str(f["formid"]), {"name": _FORM_TEMPLATES[ZH]})
            result["forms"].append(
                {"form": current, "action": "localized", "zh": _FORM_TEMPLATES[ZH]})
            result["changed"] = True
            written.append(("systemforms", f["formid"], _FORM_TEMPLATES[ZH]))
        except Exception as e:  # noqa: BLE001
            result["forms"].append({"form": current, "action": "failed", "error": str(e)[:150]})

    result["publish"] = _publish_and_verify(client, logical, written, sleep=sleep)
    return result


def _publish_and_verify(
    client: Any,
    logical: str,
    written: list[tuple[str, str, str]],
    *,
    sleep: Callable[[float], None],
) -> dict[str, Any]:
    """Publish the entity until the freshly written labels reach the PUBLISHED layer.

    Label writes are not immediately visible to PublishXml (propagation delay), so
    sleep before each attempt and re-read the published labels to verify; retry
    once. Returns a publish report; never raises.
    """
    if not written:
        return {"action": "skipped_no_changes"}
    for attempt, delay in enumerate((2.0, 5.0), start=1):
        sleep(delay)
        try:
            client.publish_entity(logical)
        except Exception as e:  # noqa: BLE001
            return {"action": "failed", "attempt": attempt, "error": str(e)[:150]}
        stale = []
        for entity_set, pk, zh in written:
            try:
                if client.retrieve_loc_labels(entity_set, pk, "name").get(ZH) != zh:
                    stale.append(pk)
            except Exception:  # noqa: BLE001
                stale.append(pk)
        if not stale:
            return {"action": "published", "attempts": attempt}
    return {"action": "published_pending_labels", "stale_count": len(stale)}


# --------------------------------------------------------------------- plan


def plan_auto_component_labels(client: Any, table: Table) -> dict[str, Any]:
    """Read-only preview of :func:`sync_auto_component_labels`."""
    names = _display_names(table)
    if EN not in names or ZH not in names:
        return {"action": "skipped",
                "reason": "table labels lack 2052/1033 display names"}
    logical = table.logical_name
    if not client.entity_exists(logical):
        return {
            "action": "would_localize",
            "note": "fresh create: platform will stamp base-language text into all "
            "language slots of the auto views/forms; deploy heals them",
            "views": 7,
            "forms": 3,
        }

    views: list[dict[str, Any]] = []
    forms: list[dict[str, Any]] = []
    for v in client.list_views_by_entity(logical, select="savedqueryid,name,querytype,isdefault"):
        querytype = int(v.get("querytype", -1))
        if querytype != 0 and querytype not in _VIEW_TEMPLATES:
            continue
        expected_en = _expected_view_name(querytype, v.get("isdefault"), names, EN)
        expected_zh = _expected_view_name(querytype, v.get("isdefault"), names, ZH)
        state = _classify(v.get("name"), expected_en, expected_zh)
        if state == "custom_name":
            views.append({"view": v.get("name"), "action": "would_skip_custom_name"})
        elif state == "localized":
            views.append({"view": v.get("name"), "action": "would_skip"})
        else:
            views.append({"view": v.get("name"), "action": "would_localize",
                          "zh": expected_zh})
    for f in client.list_forms_by_entity(logical, select="formid,name,type"):
        if f.get("type") not in _FORM_TYPES:
            continue
        if f.get("name") == _FORM_TEMPLATES[ZH]:
            forms.append({"form": f.get("name"), "action": "would_skip"})
        elif f.get("name") == _FORM_TEMPLATES[EN]:
            forms.append({"form": f.get("name"), "action": "would_localize",
                          "zh": _FORM_TEMPLATES[ZH]})
        else:
            forms.append({"form": f.get("name"), "action": "would_skip_custom_name"})
    return {"views": views, "forms": forms}
