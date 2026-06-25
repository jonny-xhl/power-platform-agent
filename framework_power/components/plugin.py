"""
Plugin component handler (framework_power Phase 2, Wave 4).

A plugin = assembly (base64 DLL) + SDK message processing steps + custom actions.
Deploy: create/update the assembly, register each step (resolving the SDK message),
and report ``manual_update_required`` for custom actions (a brand-new SDK-message-
backed action cannot be created purely via the ``sdkmessages`` endpoint — it needs a
Workflow). Because a plugin maps to several solution components, ``deploy`` returns
an ``add_targets`` list (assembly 90 + each step 92 + each action 91) so the solution
deployer adds all of them.

The DLL ``content`` is an opaque base64 string. Building it from a .NET project is
the separate concern of ``framework_power/client/plugin_build.py``.
"""

from __future__ import annotations

from typing import Any, Optional

from ..codegen import emit_label
from ..lint import ERROR, WARNING, Issue
from ._common import is_custom
from .models import CustomAction, IsolationMode, Plugin, PluginStep, SourceType

KEY = "plugin"
SOLUTION_CODE = 90  # assembly; steps=92, actions=91 returned via add_targets
MODEL_CLS = Plugin
DEPENDS_ON: tuple[str, ...] = ("table",)
CODEGEN_IMPORTS: tuple[str, ...] = (
    "Plugin",
    "PluginStep",
    "CustomAction",
    "IsolationMode",
    "SourceType",
    "Label",
)

_MANUAL_ACTION_NOTE = (
    "Custom actions cannot be created via the sdkmessages endpoint alone (a Workflow "
    "is required); create via maker portal and add the resulting SDK message id."
)


def serialize(model: Plugin) -> dict[str, Any]:
    return {
        "name": model.name,
        "content": model.content,
        "version": model.version,
        "isolationmode": int(model.isolation_mode),
        "sourcetype": int(model.source_type),
    }


def exists(client: Any, model: Plugin) -> bool:
    return client.get_plugin_assembly_by_name(model.name) is not None


def resolve_id(client: Any, model: Plugin) -> Optional[str]:
    existing = client.get_plugin_assembly_by_name(model.name)
    return existing.get("pluginassemblyid") if existing else None


def _step_payload(step: PluginStep, assembly_id: str, sdkmessage_id: str) -> dict[str, Any]:
    return {
        "name": step.name,
        "sdkmessageid@odata.bind": f"/sdkmessages({sdkmessage_id})",
        "pluginassemblyid@odata.bind": f"/pluginassemblies({assembly_id})",
        "stage": step.stage,
        "mode": step.mode,
        "rank": step.rank,
        "filteringattributes": step.filtering_attributes,
        "description": step.description,
        "supporteddeployment": step.deployment,
    }


def deploy(
    client: Any, model: Plugin, *, prefix: str = "new", config: Any = None
) -> dict[str, Any]:
    if not is_custom(model.name, prefix):
        return {"action": "skipped_standard"}

    existing = client.get_plugin_assembly_by_name(model.name)
    if existing is None:
        created = client.create_plugin_assembly(serialize(model))
        assembly_id = created["pluginassemblyid"]
        action = "created"
    else:
        assembly_id = existing["pluginassemblyid"]
        client.update_plugin_assembly(
            assembly_id, {"content": model.content, "version": model.version}
        )
        action = "updated"

    add_targets: list[tuple[int, str, str]] = [(90, assembly_id, model.name)]
    steps_result: list[dict[str, Any]] = []
    for step in model.steps:
        sdkmessage_id = client.get_sdk_message_id(step.message)
        if not sdkmessage_id:
            steps_result.append(
                {"name": step.name, "action": "failed", "error": f"SDK message '{step.message}' not found"}
            )
            continue
        try:
            res = client.create_plugin_step(_step_payload(step, assembly_id, sdkmessage_id))
            step_id = res["sdkmessageprocessingstepid"]
            steps_result.append({"name": step.name, "action": "created", "id": step_id})
            add_targets.append((92, step_id, step.name))
        except Exception as e:  # noqa: BLE001
            steps_result.append({"name": step.name, "action": "failed", "error": str(e)})

    actions_result = [
        {"schema_name": a.schema_name, "action": "manual_update_required", "reason": _MANUAL_ACTION_NOTE}
        for a in model.custom_actions
    ]
    # Custom-action SDK messages (type 91) are only addable when they already exist;
    # none are resolvable here, so they are not added automatically.

    return {
        "action": action,
        "assembly_id": assembly_id,
        "steps": steps_result,
        "custom_actions": actions_result,
        "add_targets": add_targets,
    }


def plan(client: Any, model: Plugin, *, prefix: str = "new") -> dict[str, Any]:
    if not is_custom(model.name, prefix):
        return {"action": "would_skip_standard"}
    existing = client.get_plugin_assembly_by_name(model.name)
    action = "would_create" if existing is None else "would_update"
    return {
        "action": action,
        "steps": len(model.steps),
        "custom_actions": len(model.custom_actions),
    }


def reverse(client: Any, ident: str) -> Plugin:
    asm = client.get_plugin_assembly_by_id(ident)
    steps_raw = client.get_steps_by_assembly(ident)
    steps = [
        PluginStep(
            name=s.get("name") or "",
            message=_step_message(s),
            entity="",
            stage=int(s.get("stage") or 40),
            mode=int(s.get("mode") or 0),
            deployment=int(s.get("supporteddeployment") or 0),
            filtering_attributes=s.get("filteringattributes") or "",
            description=s.get("description") or "",
            rank=int(s.get("rank") or 1),
        )
        for s in steps_raw
    ]
    return Plugin(
        name=asm.get("name") or "",
        content=asm.get("content") or "",
        version=asm.get("version") or "1.0.0.0",
        isolation_mode=IsolationMode(int(asm.get("isolationmode") or 2)),
        source_type=SourceType(int(asm.get("sourcetype") or 0)),
        steps=steps,
    )


def _step_message(step: dict[str, Any]) -> str:
    """Best-effort SDK message name for a step (formatted value, else id)."""
    formatted = step.get("sdkmessageid@OData.Community.Display.V1.FormattedValue")
    if formatted:
        return str(formatted)
    mid = step.get("_sdkmessageid_value")
    return str(mid) if mid else ""


def _emit_step(step: PluginStep) -> str:
    parts = [
        f"name={step.name!r}",
        f"message={step.message!r}",
        f"entity={step.entity!r}",
        f"stage={step.stage}",
        f"mode={step.mode}",
        f"deployment={step.deployment}",
    ]
    if step.filtering_attributes:
        parts.append(f"filtering_attributes={step.filtering_attributes!r}")
    if step.description:
        parts.append(f"description={step.description!r}")
    if step.rank != 1:
        parts.append(f"rank={step.rank}")
    return "PluginStep(" + ", ".join(parts) + ")"


def _emit_action(action: CustomAction) -> str:
    parts = [
        f"schema_name={action.schema_name!r}",
        f"display_name={emit_label(action.display_name)}",
    ]
    if action.entity:
        parts.append(f"entity={action.entity!r}")
    if action.description is not None:
        parts.append(f"description={emit_label(action.description)}")
    return "CustomAction(" + ", ".join(parts) + ")"


def codegen(model: Plugin) -> str:
    parts = [
        f"name={model.name!r}",
        f"content={model.content!r}",
        f"version={model.version!r}",
        f"isolation_mode=IsolationMode.{model.isolation_mode.name}",
        f"source_type=SourceType.{model.source_type.name}",
    ]
    if model.steps:
        parts.append("steps=[" + ", ".join(_emit_step(s) for s in model.steps) + "]")
    if model.custom_actions:
        parts.append("custom_actions=[" + ", ".join(_emit_action(a) for a in model.custom_actions) + "]")
    return "Plugin(" + ", ".join(parts) + ")"


def lint(model: Plugin, *, prefix: str = "new") -> list[Issue]:
    issues: list[Issue] = []
    if not is_custom(model.name, prefix):
        issues.append(Issue(WARNING, f"Plugin '{model.name}' does not start with prefix '{prefix}_'."))
    if not model.content:
        issues.append(Issue(WARNING, f"Plugin '{model.name}' has empty content (base64 DLL)."))
    for step in model.steps:
        if not step.message or not step.entity:
            issues.append(Issue(ERROR, f"Plugin step '{step.name}' needs message and entity."))
    return issues
