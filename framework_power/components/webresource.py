"""
Web Resource component handler (framework_power Phase 2, Wave 2).

Uniform interface consumed by the component registry. Web resources are plain
records: create if missing, else PATCH the base64 ``content`` (and display name).
``content`` is an opaque base64 string — the library never encodes/decodes it.
"""

from __future__ import annotations

from typing import Any, Optional

from ..lint import WARNING, Issue
from ._common import is_custom
from .models import WebResource, WebResourceType

KEY = "webresource"
SOLUTION_CODE = 61
MODEL_CLS = WebResource
DEPENDS_ON: tuple[str, ...] = ()
CODEGEN_IMPORTS: tuple[str, ...] = ("WebResource", "WebResourceType")


def serialize(model: WebResource) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": model.name,
        "displayname": model.display_name,
        "content": model.content,
        "webresourcetype": int(model.webresource_type),
    }
    if model.description:
        payload["description"] = model.description
    return payload


def exists(client: Any, model: WebResource) -> bool:
    return client.get_webresource_by_name(model.name) is not None


def resolve_id(client: Any, model: WebResource) -> Optional[str]:
    existing = client.get_webresource_by_name(model.name)
    return existing.get("webresourceid") if existing else None


def deploy(
    client: Any, model: WebResource, *, prefix: str = "new", config: Any = None
) -> dict[str, Any]:
    if not is_custom(model.name, prefix):
        return {"action": "skipped_standard"}
    payload = serialize(model)
    existing = client.get_webresource_by_name(model.name)
    if existing is None:
        res = client.create_webresource(payload)
        return {"action": "created", "id": res.get("webresourceid")}
    client.update_webresource(
        existing["webresourceid"],
        {"content": payload["content"], "displayname": payload["displayname"]},
    )
    return {"action": "updated", "id": existing["webresourceid"]}


def plan(client: Any, model: WebResource, *, prefix: str = "new") -> dict[str, Any]:
    if not is_custom(model.name, prefix):
        return {"action": "would_skip_standard"}
    existing = client.get_webresource_by_name(model.name)
    return {"action": "would_create"} if existing is None else {"action": "would_update"}


def reverse(client: Any, ident: str) -> WebResource:
    data = client.get_webresource_by_id(ident)
    wrtype = int(data.get("webresourcetype") or 3)
    return WebResource(
        name=data.get("name") or "",
        display_name=data.get("displayname") or data.get("name") or "",
        content=data.get("content") or "",
        webresource_type=WebResourceType(wrtype),
        description=data.get("description"),
    )


def codegen(model: WebResource) -> str:
    parts = [
        f"name={model.name!r}",
        f"display_name={model.display_name!r}",
        f"content={model.content!r}",
        f"webresource_type=WebResourceType.{model.webresource_type.name}",
    ]
    if model.description:
        parts.append(f"description={model.description!r}")
    return "WebResource(" + ", ".join(parts) + ")"


def lint(model: WebResource, *, prefix: str = "new") -> list[Issue]:
    issues: list[Issue] = []
    if not is_custom(model.name, prefix):
        issues.append(Issue(WARNING, f"WebResource '{model.name}' does not start with prefix '{prefix}_'."))
    if not model.content:
        issues.append(Issue(WARNING, f"WebResource '{model.name}' has empty content."))
    return issues
