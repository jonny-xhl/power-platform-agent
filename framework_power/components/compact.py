# -*- coding: utf-8 -*-
"""Compact ``attrs`` for reverse codegen (token-lean generated files).

The lossless round-trip contract stores every XML attribute TWICE on reversed
nodes: typed model fields plus a verbatim ``attrs`` dict — that roughly doubles
generated file size. When a node's ``attrs`` consists ONLY of keys the
serializer rebuilds identically from typed fields (its authored-fallback
branch), codegen may emit ``attrs={}`` and serialization stays byte-identical.

Safety rule (exact set): the drop happens ONLY when the attrs key set EXACTLY
equals the set the fallback branch emits (for the node's current field values)
and every value matches. Extra keys (``locklevel``, ``rowspan``) keep the dict
verbatim — several fallback branches emit unconditionally and do not overlay
extras, so both partial drops and missing-key drops would change the XML.

Because compact and verbatim representations are semantically equal but not
dataclass-equal, deploy/plan diffing must compare :func:`normalize`d models on
BOTH sides (live-reversed full-attrs vs file-loaded compact) to keep the
"reversed-unmodified -> skipped_unchanged" idempotency guarantee.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from . import models as M


def _b(value: bool) -> str:
    return "true" if value else "false"


def _mirror(node: Any) -> dict[str, str]:
    """The attrs set the serializer's fallback branch would rebuild for ``node``."""
    if isinstance(node, M.FormControl):
        return {
            "id": node.id or node.datafieldname,
            "classid": node.classid,
            "datafieldname": node.datafieldname,
            "disabled": _b(node.disabled),
        }
    if isinstance(node, M.FormCell):
        return {"id": node.id, "showlabel": _b(node.showlabel), "visible": _b(node.visible)}
    if isinstance(node, M.FormSection):
        return {
            "name": node.name,
            "id": node.id,
            "columns": "1" * max(node.columns, 1),
            "showlabel": _b(node.showlabel),
        }
    if isinstance(node, M.FormColumn):
        return {"width": node.width}
    if isinstance(node, M.FormTab):
        return {
            "name": node.name,
            "id": node.id,
            "showlabel": _b(node.showlabel),
            "expanded": _b(node.expanded),
        }
    if isinstance(node, M.ViewColumn):
        mirror = {"name": node.name, "width": str(node.width)}
        if node.disable_sorting:
            mirror["disableSorting"] = "1"
        if node.hidden:
            mirror["ishidden"] = "1"
        return mirror
    if isinstance(node, M.ViewOrder):
        return {"attribute": node.attribute, "descending": _b(node.descending)}
    if isinstance(node, M.ViewCondition):
        mirror = {"attribute": node.attribute, "operator": node.operator}
        if node.value is not None:
            mirror["value"] = node.value
        return mirror
    if isinstance(node, M.ViewFilter):
        return {"type": node.filter_type}
    if isinstance(node, M.ViewLinkEntity):
        mirror = {"name": node.name}
        if node.from_attr:
            mirror["from"] = node.from_attr
        if node.to_attr:
            mirror["to"] = node.to_attr
        if node.link_type:
            mirror["link-type"] = node.link_type
        if node.alias:
            mirror["alias"] = node.alias
        return mirror
    return {}


def compact_attrs(node: Any) -> dict[str, str]:
    """Attrs dict to emit for ``node``: ``{}`` when fully rebuildable, else verbatim."""
    attrs = getattr(node, "attrs", None)
    if not isinstance(attrs, dict) or not attrs:
        return {}
    mirror = _mirror(node)
    # Exact-set equality: the fallback must neither LOSE an attrs key nor ADD one
    # the original XML lacked (several fallback branches emit unconditionally,
    # e.g. control datafieldname="").
    if set(attrs) == set(mirror) and all(attrs[k] == mirror[k] for k in attrs):
        return {}
    return attrs


def normalize(model: Any) -> Any:
    """Return a copy of ``model`` with every node's attrs compacted.

    Used on BOTH sides of the structured diff (live-reversed vs file-loaded) so
    compact files still compare equal to the live form/view. Deterministic:
    equal fields + equal extra attrs -> equal normalized models.
    """

    def walk(value: Any) -> Any:
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            kwargs = {}
            for f in dataclasses.fields(value):
                item = getattr(value, f.name)
                kwargs[f.name] = compact_attrs(value) if f.name == "attrs" else walk(item)
            return type(value)(**kwargs)
        if isinstance(value, list):
            return [walk(v) for v in value]
        if isinstance(value, tuple):
            return tuple(walk(v) for v in value)
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        return value

    return walk(model)
