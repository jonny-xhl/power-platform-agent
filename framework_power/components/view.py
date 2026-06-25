"""
View (SavedQuery) component handler (framework_power Phase 2, Wave 3).

Uniform interface consumed by the component registry. ``fetch_xml`` and
``layout_xml`` are OPAQUE strings — never generated or parsed. Deploy: create if
missing, else PATCH ``fetchxml``/``layoutxml``.
"""

from __future__ import annotations

from typing import Any, Optional

from ..lint import WARNING, Issue
from ._common import is_custom
from .models import QueryType, View

KEY = "view"
SOLUTION_CODE = 26
MODEL_CLS = View
DEPENDS_ON: tuple[str, ...] = ("table",)
CODEGEN_IMPORTS: tuple[str, ...] = ("View", "QueryType")


def serialize(model: View) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": model.name,
        "returnedtypecode": model.entity,
        "fetchxml": model.fetch_xml,
        "layoutxml": model.layout_xml,
        "querytype": int(model.query_type),
    }
    if model.is_default:
        payload["isdefault"] = True
    if model.description:
        payload["description"] = model.description
    return payload


def exists(client: Any, model: View) -> bool:
    return client.get_view_by_name(model.entity, model.name) is not None


def resolve_id(client: Any, model: View) -> Optional[str]:
    existing = client.get_view_by_name(model.entity, model.name)
    return existing.get("savedqueryid") if existing else None


def deploy(client: Any, model: View, *, prefix: str = "new", config: Any = None) -> dict[str, Any]:
    if not is_custom(model.name, prefix):
        return {"action": "skipped_standard"}
    existing = client.get_view_by_name(model.entity, model.name)
    if existing is None:
        client.create_view(serialize(model))
        return {"action": "created"}
    patch: dict[str, Any] = {"fetchxml": model.fetch_xml, "layoutxml": model.layout_xml}
    if model.description:
        patch["description"] = model.description
    client.update_view(existing["savedqueryid"], patch)
    return {"action": "updated"}


def plan(client: Any, model: View, *, prefix: str = "new") -> dict[str, Any]:
    if not is_custom(model.name, prefix):
        return {"action": "would_skip_standard"}
    existing = client.get_view_by_name(model.entity, model.name)
    return {"action": "would_create"} if existing is None else {"action": "would_update"}


def reverse(client: Any, ident: str) -> View:
    data = client.get_view_by_id(ident)
    return View(
        name=data.get("name") or "",
        entity=data.get("returnedtypecode") or "",
        fetch_xml=data.get("fetchxml") or "",
        layout_xml=data.get("layoutxml") or "",
        query_type=QueryType(int(data.get("querytype") or 0)),
        is_default=bool(data.get("isdefault")),
        description=data.get("description"),
    )


def codegen(model: View) -> str:
    parts = [
        f"name={model.name!r}",
        f"entity={model.entity!r}",
        f"fetch_xml={model.fetch_xml!r}",
        f"layout_xml={model.layout_xml!r}",
        f"query_type=QueryType.{model.query_type.name}",
    ]
    if model.is_default:
        parts.append("is_default=True")
    if model.description:
        parts.append(f"description={model.description!r}")
    return "View(" + ", ".join(parts) + ")"


def lint(model: View, *, prefix: str = "new") -> list[Issue]:
    issues: list[Issue] = []
    if not is_custom(model.name, prefix):
        issues.append(Issue(WARNING, f"View '{model.name}' does not start with prefix '{prefix}_'."))
    if not model.entity:
        issues.append(Issue(WARNING, f"View '{model.name}' has no entity (returnedtypecode)."))
    if not model.fetch_xml or not model.layout_xml:
        issues.append(Issue(WARNING, f"View '{model.name}' has empty fetch_xml/layout_xml."))
    return issues
