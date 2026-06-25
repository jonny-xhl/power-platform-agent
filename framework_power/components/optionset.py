"""
Global OptionSet component handler (framework_power Phase 2, Wave 2).

Uniform interface consumed by the component registry (``serialize``/``deploy``/
``plan``/``reverse``/``codegen``/``exists``/``resolve_id``/``lint``). Global
optionsets are create-only: option values cannot be PATCHed, so a differing
existing optionset reports ``manual_update_required`` (use InsertOptionValue /
UpdateOptionValue or the maker portal).
"""

from __future__ import annotations

from typing import Any, Optional

from ..codegen import emit_label
from ..lint import ERROR, WARNING, Issue
from ..models import Label, Option
from ..serializer import serialize_label
from ._common import extract_label, is_custom
from .models import GlobalOptionSet

KEY = "optionset"
SOLUTION_CODE = 9  # global optionset component type
MODEL_CLS = GlobalOptionSet
DEPENDS_ON: tuple[str, ...] = ()
# Names this type's codegen references (all re-exported by framework_power).
CODEGEN_IMPORTS: tuple[str, ...] = ("GlobalOptionSet", "Option", "Label")


def serialize(model: GlobalOptionSet) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata",
        "Name": model.name,
        "IsGlobal": True,
        "DisplayName": serialize_label(model.display_name),
        "Options": [
            {"Value": o.value, "Label": serialize_label(o.label)} for o in model.options
        ],
    }
    if model.description is not None:
        payload["Description"] = serialize_label(model.description)
    return payload


def _options_differ(model: GlobalOptionSet, existing: dict[str, Any]) -> bool:
    existing_vals = {o.get("Value") for o in (existing.get("Options") or [])}
    model_vals = {o.value for o in model.options}
    return existing_vals != model_vals


def exists(client: Any, model: GlobalOptionSet) -> bool:
    return client.get_global_optionset_by_name(model.name) is not None


def resolve_id(client: Any, model: GlobalOptionSet) -> Optional[str]:
    existing = client.get_global_optionset_by_name(model.name)
    return existing.get("MetadataId") if existing else None


def deploy(
    client: Any, model: GlobalOptionSet, *, prefix: str = "new", config: Any = None
) -> dict[str, Any]:
    if not is_custom(model.name, prefix):
        return {"action": "skipped_standard"}
    existing = client.get_global_optionset_by_name(model.name)
    if existing is not None:
        if _options_differ(model, existing):
            return {
                "action": "manual_update_required",
                "reason": "global optionset options cannot be PATCHed; use "
                "InsertOptionValue/UpdateOptionValue or the maker portal.",
            }
        return {"action": "exists", "id": existing.get("MetadataId")}
    res = client.create_global_optionset(serialize(model))
    return {"action": "created", "id": res.get("MetadataId")}


def plan(client: Any, model: GlobalOptionSet, *, prefix: str = "new") -> dict[str, Any]:
    if not is_custom(model.name, prefix):
        return {"action": "would_skip_standard"}
    existing = client.get_global_optionset_by_name(model.name)
    if existing is None:
        return {"action": "would_create"}
    if _options_differ(model, existing):
        return {"action": "manual_update_required"}
    return {"action": "would_skip"}


def reverse(client: Any, ident: str) -> GlobalOptionSet:
    data = client.get_global_optionset_by_id(ident)
    options = [
        Option(o.get("Value"), extract_label(o.get("Label")) or Label.en(str(o.get("Value"))))
        for o in (data.get("Options") or [])
    ]
    return GlobalOptionSet(
        name=data.get("Name") or "",
        display_name=extract_label(data.get("DisplayName")) or Label.en(data.get("Name") or "optionset"),
        options=options,
        description=extract_label(data.get("Description")),
    )


def codegen(model: GlobalOptionSet) -> str:
    opts = ", ".join(
        f"Option({o.value}, {emit_label(o.label)})" for o in model.options
    )
    parts = [
        f"name={model.name!r}",
        f"display_name={emit_label(model.display_name)}",
    ]
    if model.description is not None:
        parts.append(f"description={emit_label(model.description)}")
    parts.append(f"options=[{opts}]")
    return "GlobalOptionSet(" + ", ".join(parts) + ")"


def lint(model: GlobalOptionSet, *, prefix: str = "new") -> list[Issue]:
    issues: list[Issue] = []
    if not is_custom(model.name, prefix):
        issues.append(Issue(WARNING, f"OptionSet '{model.name}' does not start with prefix '{prefix}_'."))
    values = [o.value for o in model.options]
    dupes = {v for v in values if values.count(v) > 1}
    if dupes:
        issues.append(Issue(ERROR, f"OptionSet '{model.name}' has duplicate option values: {sorted(dupes)}."))
    return issues
