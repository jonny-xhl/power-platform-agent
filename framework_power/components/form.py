"""
Form (SystemForm) component handler (framework_power Phase 2, Wave 3).

Uniform interface consumed by the component registry. ``form_xml`` is an OPAQUE
FormXml string — the library never generates or parses it; the author supplies it
and reverse captures it verbatim. Deploy: create if missing, else PATCH ``formxml``.
"""

from __future__ import annotations

from typing import Any, Optional

from ..lint import WARNING, Issue
from ._common import is_custom
from .models import Form, FormType

KEY = "form"
SOLUTION_CODE = 60
MODEL_CLS = Form
DEPENDS_ON: tuple[str, ...] = ("table",)
CODEGEN_IMPORTS: tuple[str, ...] = ("Form", "FormType")


def serialize(model: Form) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": model.name,
        "objecttypecode": model.entity,
        "formxml": model.form_xml,
        "type": int(model.form_type),
    }
    if model.description:
        payload["description"] = model.description
    return payload


def exists(client: Any, model: Form) -> bool:
    return client.get_form_by_name(model.entity, model.name) is not None


def resolve_id(client: Any, model: Form) -> Optional[str]:
    existing = client.get_form_by_name(model.entity, model.name)
    return existing.get("formid") if existing else None


def deploy(client: Any, model: Form, *, prefix: str = "new", config: Any = None) -> dict[str, Any]:
    if not is_custom(model.name, prefix):
        return {"action": "skipped_standard"}
    existing = client.get_form_by_name(model.entity, model.name)
    if existing is None:
        client.create_form(serialize(model))
        return {"action": "created"}
    patch: dict[str, Any] = {"formxml": model.form_xml}
    if model.description:
        patch["description"] = model.description
    client.update_form(existing["formid"], patch)
    return {"action": "updated"}


def plan(client: Any, model: Form, *, prefix: str = "new") -> dict[str, Any]:
    if not is_custom(model.name, prefix):
        return {"action": "would_skip_standard"}
    existing = client.get_form_by_name(model.entity, model.name)
    return {"action": "would_create"} if existing is None else {"action": "would_update"}


def reverse(client: Any, ident: str) -> Form:
    data = client.get_form_by_id(ident)
    return Form(
        name=data.get("name") or "",
        entity=data.get("objecttypecode") or "",
        form_xml=data.get("formxml") or "",
        form_type=FormType(int(data.get("type") or 2)),
        description=data.get("description"),
    )


def codegen(model: Form) -> str:
    parts = [
        f"name={model.name!r}",
        f"entity={model.entity!r}",
        f"form_xml={model.form_xml!r}",
        f"form_type=FormType.{model.form_type.name}",
    ]
    if model.description:
        parts.append(f"description={model.description!r}")
    return "Form(" + ", ".join(parts) + ")"


def lint(model: Form, *, prefix: str = "new") -> list[Issue]:
    issues: list[Issue] = []
    if not is_custom(model.name, prefix):
        issues.append(Issue(WARNING, f"Form '{model.name}' does not start with prefix '{prefix}_'."))
    if not model.entity:
        issues.append(Issue(WARNING, f"Form '{model.name}' has no entity (objecttypecode)."))
    if not model.form_xml:
        issues.append(Issue(WARNING, f"Form '{model.name}' has empty form_xml."))
    return issues
