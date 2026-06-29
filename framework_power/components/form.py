"""
Form (SystemForm) component handler (framework_power Phase 2 Wave 3, refit Phase 5).

Uniform interface consumed by the component registry. ``Form`` is now a STRUCTURED
typed model (Phase 5): ``framework_power.form_xml`` parses FormXml into tabs/libraries/
events and serializes them back. Deploy: create if missing, else PATCH ``formxml`` (now
regenerated from the structured model via ``to_formxml``).
"""

from __future__ import annotations

import dataclasses
from dataclasses import is_dataclass
from typing import Any, Optional

from ..form_xml import parse_formxml, to_formxml
from ..lint import ERROR, WARNING, Issue
from ._common import is_custom
from .models import (
    EDITABLE_FORM_TYPES,
    Form,
    FormType,
)

KEY = "form"
SOLUTION_CODE = 60
MODEL_CLS = Form
DEPENDS_ON: tuple[str, ...] = ("table",)
CODEGEN_IMPORTS: tuple[str, ...] = (
    "Form",
    "FormType",
    "FormTab",
    "FormColumn",
    "FormSection",
    "FormRow",
    "FormCell",
    "FormControl",
    "FormLabel",
    "FormLibrary",
    "FormEvent",
    "FormEventHandler",
)


def serialize(model: Form) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": model.name,
        "objecttypecode": model.entity,
        "formxml": to_formxml(model),
        "type": int(model.form_type),
    }
    if model.description:
        payload["description"] = model.description
    return payload


def exists(client: Any, model: Form) -> bool:
    return client.get_form_by_name(model.entity, model.name, form_type=int(model.form_type)) is not None


def resolve_id(client: Any, model: Form) -> Optional[str]:
    existing = client.get_form_by_name(model.entity, model.name, form_type=int(model.form_type))
    return existing.get("formid") if existing else None


def deploy(client: Any, model: Form, *, prefix: str = "new", config: Any = None) -> dict[str, Any]:
    # Customness is ENTITY-based for forms: an auto-created form (e.g. "Information") on a
    # custom table is ours to edit, even though its generic name lacks the publisher prefix.
    # Forms on standard entities (account/contact/...) are skipped.
    if not is_custom(model.entity, prefix):
        return {"action": "skipped_standard"}
    existing = client.get_form_by_name(model.entity, model.name, form_type=int(model.form_type))
    if existing is None:
        res = client.create_form(serialize(model))
        return {"action": "created", "id": res.get("formid")}
    patch: dict[str, Any] = {"formxml": to_formxml(model)}
    if model.description:
        patch["description"] = model.description
    client.update_form(existing["formid"], patch)
    return {"action": "updated", "id": existing["formid"]}


def plan(client: Any, model: Form, *, prefix: str = "new") -> dict[str, Any]:
    if not is_custom(model.entity, prefix):  # entity-based; see deploy()
        return {"action": "would_skip_standard"}
    existing = client.get_form_by_name(model.entity, model.name, form_type=int(model.form_type))
    return {"action": "would_create"} if existing is None else {"action": "would_update"}


def _safe_form_type(raw: Any) -> FormType:
    try:
        return FormType(int(raw))
    except (TypeError, ValueError):
        return FormType.Main


def reverse(client: Any, ident: str) -> Form:
    data = client.get_form_by_id(ident)
    xml = data.get("formxml") or ""
    if xml:
        tabs, libraries, events, root_attrs, extras_pre, extras_post = parse_formxml(xml)
    else:  # pragma: no cover - a form with no formxml
        tabs, libraries, events, root_attrs, extras_pre, extras_post = [], [], [], {}, "", ""
    return Form(
        name=data.get("name") or "",
        entity=data.get("objecttypecode") or "",
        form_type=_safe_form_type(data.get("type")),
        description=data.get("description"),
        tabs=tabs,
        libraries=libraries,
        events=events,
        root_attrs=root_attrs,
        extras_pre_xml=extras_pre,
        extras_post_xml=extras_post,
    )


def codegen(model: Form) -> str:
    """Emit ``FORM = Form(...)`` Python source that reconstructs the model exactly.

    Uses a recursive dataclass -> nested-literal emitter so reverse snapshots (with full
    attrs + extras) round-trip through ``eval``. All referenced classes are listed in
    :data:`CODEGEN_IMPORTS`.
    """
    return _to_py(model, 0)


def _to_py(value: Any, indent: int) -> str:
    pad = "    " * indent
    inner = "    " * (indent + 1)
    if isinstance(value, FormType):
        return f"FormType.{value.name}"
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


def lint(model: Form, *, prefix: str = "new") -> list[Issue]:
    issues: list[Issue] = []
    # Customness is entity-based (see deploy()): a form on a standard entity is not ours.
    if not is_custom(model.entity, prefix):
        issues.append(Issue(
            WARNING,
            f"Form '{model.name}' is on standard entity '{model.entity}' (no prefix "
            f"'{prefix}_') — skipped on forward sync.",
        ))
    if not model.entity:
        issues.append(Issue(WARNING, f"Form '{model.name}' has no entity (objecttypecode)."))
    if model.form_type not in EDITABLE_FORM_TYPES:
        issues.append(
            Issue(
                WARNING,
                f"Form '{model.name}' type {model.form_type.name} is outside the editable set "
                "(Main/QuickCreate/QuickView); it can be reversed but not authored here.",
            )
        )

    lib_names = {lib.name for lib in model.libraries}
    for ev in model.events:
        for h in ev.handlers:
            if h.internal:
                continue
            if not h.function_name:
                issues.append(Issue(
                    ERROR,
                    f"Form '{model.name}' event '{ev.name}' has a custom handler with no functionName.",
                ))
            if not h.library_name:
                issues.append(Issue(
                    ERROR, f"Form '{model.name}' event '{ev.name}' handler has no libraryName."
                ))
            elif h.library_name not in lib_names:
                issues.append(
                    Issue(
                        WARNING,
                        f"Form '{model.name}' handler '{h.function_name}' references library "
                        f"'{h.library_name}' which is not in formLibraries.",
                    )
                )

    tab_names = [tab.name for tab in model.tabs]
    dup_tabs = {name for name in tab_names if tab_names.count(name) > 1}
    for name in sorted(dup_tabs):
        issues.append(Issue(WARNING, f"Form '{model.name}' has duplicate tab name '{name}'."))

    return issues
