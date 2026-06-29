"""
View (SavedQuery) component handler (framework_power Phase 2 Wave 3, refit Phase 6).

Uniform interface consumed by the component registry. ``View`` is now a STRUCTURED typed model
(Phase 6): ``framework_power.view_xml`` parses FetchXml+LayoutXml into columns/filters/orders/
link_entities and serializes them back. Deploy: create if missing (Public only), else PATCH
``fetchxml``/``layoutxml``.
"""

from __future__ import annotations

import dataclasses
from dataclasses import is_dataclass
from typing import Any, Optional

from ..lint import ERROR, WARNING, Issue
from ..view_xml import parse_view, to_fetchxml, to_layoutxml
from ._common import is_custom
from .models import (
    QueryType,
    UPDATABLE_VIEW_TYPES,
    View,
)

KEY = "view"
SOLUTION_CODE = 26
MODEL_CLS = View
DEPENDS_ON: tuple[str, ...] = ("table",)
CODEGEN_IMPORTS: tuple[str, ...] = (
    "View",
    "QueryType",
    "ViewColumn",
    "ViewOrder",
    "ViewCondition",
    "ViewFilter",
    "ViewLinkEntity",
)


def serialize(model: View) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": model.name,
        "returnedtypecode": model.entity,
        "querytype": int(model.query_type),
        "fetchxml": to_fetchxml(model),
        "layoutxml": to_layoutxml(model),
    }
    if model.is_default:
        payload["isdefault"] = True
    if model.description:
        payload["description"] = model.description
    return payload


def exists(client: Any, model: View) -> bool:
    return client.get_view_by_name(model.entity, model.name, query_type=int(model.query_type)) is not None


def resolve_id(client: Any, model: View) -> Optional[str]:
    existing = client.get_view_by_name(model.entity, model.name, query_type=int(model.query_type))
    return existing.get("savedqueryid") if existing else None


def deploy(client: Any, model: View, *, prefix: str = "new", config: Any = None) -> dict[str, Any]:
    # Customness is ENTITY-based (a view on a custom table is ours, even with a generic name).
    if not is_custom(model.entity, prefix):
        return {"action": "skipped_standard"}
    existing = client.get_view_by_name(model.entity, model.name, query_type=int(model.query_type))
    if existing is None:
        if model.query_type != QueryType.Public:
            return {
                "action": "skipped_standard",
                "note": "only Public views can be created; system views are update-only",
            }
        res = client.create_view(serialize(model))
        return {"action": "created", "id": res.get("savedqueryid")}
    patch: dict[str, Any] = {"fetchxml": to_fetchxml(model), "layoutxml": to_layoutxml(model)}
    if model.description:
        patch["description"] = model.description
    client.update_view(existing["savedqueryid"], patch)
    return {"action": "updated", "id": existing["savedqueryid"]}


def plan(client: Any, model: View, *, prefix: str = "new") -> dict[str, Any]:
    if not is_custom(model.entity, prefix):  # entity-based; see deploy()
        return {"action": "would_skip_standard"}
    existing = client.get_view_by_name(model.entity, model.name, query_type=int(model.query_type))
    if existing is None and model.query_type != QueryType.Public:
        return {"action": "would_skip_standard", "note": "system views are update-only"}
    return {"action": "would_create"} if existing is None else {"action": "would_update"}


def _safe_query_type(raw: Any) -> QueryType:
    try:
        return QueryType(int(raw))
    except (TypeError, ValueError):
        return QueryType.Public


def reverse(client: Any, ident: str) -> View:
    data = client.get_view_by_id(ident)
    parsed = parse_view(data.get("fetchxml") or "", data.get("layoutxml") or "")
    return View(
        name=data.get("name") or "",
        entity=data.get("returnedtypecode") or "",
        query_type=_safe_query_type(data.get("querytype")),
        is_default=bool(data.get("isdefault")),
        description=data.get("description"),
        **parsed,
    )


def codegen(model: View) -> str:
    """Emit ``View(...)`` Python source that reconstructs the model exactly (recursive)."""
    return _to_py(model, 0)


def _to_py(value: Any, indent: int) -> str:
    pad = "    " * indent
    inner = "    " * (indent + 1)
    if isinstance(value, QueryType):
        return f"QueryType.{value.name}"
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return "None"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        items = [inner + _to_py(v, indent + 1) for v in value]
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = [inner + repr(k) + ": " + _to_py(v, indent + 1) for k, v in value.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if is_dataclass(value) and not isinstance(value, type):
        parts = [
            inner + f.name + "=" + _to_py(getattr(value, f.name), indent + 1)
            for f in dataclasses.fields(value)
        ]
        return type(value).__name__ + "(\n" + ",\n".join(parts) + "\n" + pad + ")"
    return repr(value)


def lint(model: View, *, prefix: str = "new") -> list[Issue]:
    issues: list[Issue] = []
    if not is_custom(model.entity, prefix):
        issues.append(Issue(WARNING, f"View '{model.name}' is on standard entity '{model.entity}'."))
    if not model.entity:
        issues.append(Issue(WARNING, f"View '{model.name}' has no entity (returnedtypecode)."))
    if model.query_type not in UPDATABLE_VIEW_TYPES:
        issues.append(
            Issue(
                WARNING,
                f"View '{model.name}' querytype {model.query_type.name} is outside the updatable set "
                "(Public/QuickFind/Lookup/Associated/AdvancedFind).",
            )
        )
    if not model.primary_id:
        issues.append(Issue(ERROR, f"View '{model.name}' has no primary_id (<row id>)."))
    if not model.object_type_code:
        issues.append(Issue(ERROR, f"View '{model.name}' has no object_type_code (<grid object>)."))
    # dotted column names must reference a known link-entity alias
    aliases = {le.alias for le in model.link_entities if le.alias}
    for col in model.columns:
        if "." in col.name:
            alias = col.name.split(".", 1)[0]
            if alias not in aliases:
                issues.append(
                    Issue(
                        ERROR,
                        f"View '{model.name}' column '{col.name}' references unknown link-entity alias "
                        f"'{alias}'.",
                    )
                )
    if model.is_default:
        issues.append(
            Issue(
                WARNING,
                f"View '{model.name}' is_default=True; exclusivity among active Public views is manual.",
            )
        )
    return issues
