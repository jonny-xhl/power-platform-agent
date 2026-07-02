"""
Plugin component handler (framework_power Phase 2 Wave 4 + Phase 8).

A plugin = assembly/package + SDK message processing steps + custom actions. Phase 8 adds the **NuGet
PluginPackage** deploy path (preferred): upload a ``.nupkg`` via ``pluginpackages`` → Dataverse auto-creates
the ``pluginassembly`` → register steps. The classic ``pluginassemblies`` path (signed/merged DLL) remains as
a fallback. Custom-action definitions are auto-created best-effort via ``workflows`` (category=Action) with a
manual fallback. ``deploy`` returns ``add_targets`` (assembly 90 + steps 92) so the solution deployer adds them.

The ``content`` is an opaque base64 string (``.nupkg`` or ``.dll``); building it from a .NET project is the
separate concern of ``framework_power/client/plugin_build.py``.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from ..codegen import emit_label
from ..lint import ERROR, WARNING, Issue
from ._common import is_custom
from .models import ContentKind, CustomAction, IsolationMode, Plugin, PluginStep, SourceType

KEY = "plugin"
SOLUTION_CODE = 91  # PluginAssembly (90=PluginType, 92=Step); pinned live
PLUGINPACKAGE_SOLUTION_CODE = 10030  # PluginPackage (NuGet) — the solution unit for package plugins;
# adding the assembly(91) of a package-derived plugin returns 405 ("export the Package directly").
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
    "Custom-action definition could not be auto-created via the Web API (workflows/category=Action). Create it "
    "in the maker portal, then re-deploy to register the step that references its SDK message."
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


def _step_payload(step: PluginStep, *, sdkmessage_id: str, plugintype_id: str,
                  filter_id: Optional[str] = None) -> dict[str, Any]:
    """Build the sdkmessageprocessingstep create payload.

    A step targets a **PluginType** (via ``eventhandler@odata.bind``), NOT the assembly, and is entity-scoped
    via ``sdkmessagefilterid`` (omit for global messages). Pinned from a real live step's fields.
    """
    payload = {
        "name": step.name,
        "sdkmessageid@odata.bind": f"/sdkmessages({sdkmessage_id})",
        "eventhandler_plugintype@odata.bind": f"/plugintypes({plugintype_id})",
        "stage": step.stage,
        "mode": step.mode,
        "rank": step.rank,
        "filteringattributes": step.filtering_attributes,
        "description": step.description,
        "supporteddeployment": step.deployment,
    }
    if filter_id:
        payload["sdkmessagefilterid@odata.bind"] = f"/sdkmessagefilters({filter_id})"
    return payload


def _resolve_plugintype(client: Any, assembly_id: str, plugin_type: str) -> Optional[dict[str, Any]]:
    """Resolve the PluginType (IPlugin class) for an assembly. ``plugin_type`` matches typename/name; empty
    uses the assembly's single plugintype (None if 0 or >1)."""
    ptypes = client.get_plugintypes_by_assembly(assembly_id)
    if plugin_type:
        return next((p for p in ptypes if plugin_type in (p.get("typename"), p.get("name"))), None)
    return ptypes[0] if len(ptypes) == 1 else None


def _register_step(client: Any, step: PluginStep, assembly_id: str) -> dict[str, Any]:
    """Resolve plugintype + sdkmessage + sdkmessagefilter, then create the step. Returns a result dict."""
    pt = _resolve_plugintype(client, assembly_id, step.plugin_type)
    if not pt:
        return {"name": step.name, "action": "failed",
                "error": f"plugintype not resolved (plugin_type={step.plugin_type!r})"}
    sdkmessage_id = client.get_sdk_message_id(step.message)
    if not sdkmessage_id:
        return {"name": step.name, "action": "failed", "error": f"SDK message '{step.message}' not found"}
    filter_id: Optional[str] = None
    if step.entity and step.entity != "none":  # entity-scoped step → needs an sdkmessagefilter
        # The step's target entity must exist before a filter/step can be registered on it. Without
        # this check Dataverse returns an opaque 400 (0x80041102 "entity not found in MetadataCache")
        # from the sdkmessagefilters query, so fail fast with a clear root-cause message instead.
        if not client.entity_exists(step.entity):
            return {
                "name": step.name,
                "action": "failed",
                "error": (
                    f"target entity '{step.entity}' not found in env; "
                    f"deploy the table before registering steps on it."
                ),
            }
        filter_id = client.get_sdk_message_filter(sdkmessage_id, step.entity)
        if not filter_id:
            try:
                filter_id = client.create_sdk_message_filter(sdkmessage_id, step.entity)
            except Exception as e:  # noqa: BLE001
                return {"name": step.name, "action": "failed", "error": f"sdkmessagefilter: {str(e)[:160]}"}
    res = client.create_plugin_step(
        _step_payload(step, sdkmessage_id=sdkmessage_id, plugintype_id=pt["plugintypeid"], filter_id=filter_id))
    return {"name": step.name, "action": "created", "id": res["sdkmessageprocessingstepid"]}


def _wait_for_assembly(client: Any, name: str, *, attempts: int = 6, delay: float = 5.0) -> Optional[dict[str, Any]]:
    """Poll for the pluginassembly Dataverse auto-creates from an uploaded package (async)."""
    for _ in range(attempts):
        asm = client.get_plugin_assembly_by_name(name)
        if asm:
            return asm
        time.sleep(delay)
    return None


def _deploy_package(client: Any, model: Plugin) -> tuple[str, dict[str, Any]]:
    """Upload the .nupkg via pluginpackages; return (assembly_id, info). Dataverse auto-creates the assembly."""
    pkg_name = model.package_name  # {prefix}_{name} — Dataverse requires the prefix in the package name
    payload = {"name": pkg_name, "version": model.version, "content": model.content}
    existing = client.get_plugin_package_by_name(pkg_name)
    if existing is None:
        res = client.create_plugin_package(payload)
        pkg_id = res["pluginpackageid"]
        action = "created_package"
    else:
        pkg_id = existing["pluginpackageid"]
        client.update_plugin_package(pkg_id, {"content": model.content, "version": model.version})
        action = "updated_package"
    asm = _wait_for_assembly(client, model.name)
    if asm is None:
        raise RuntimeError(
            f"pluginpackage '{pkg_name}' uploaded but no pluginassembly '{model.name}' was provisioned")
    info = {"action": action, "package_id": pkg_id, "package_name": pkg_name,
            "assembly_id": asm["pluginassemblyid"]}
    return asm["pluginassemblyid"], info


def _deploy_assembly(client: Any, model: Plugin) -> tuple[str, dict[str, Any]]:
    """Classic path: create/update pluginassembly (signed/merged DLL)."""
    existing = client.get_plugin_assembly_by_name(model.name)
    if existing is None:
        created = client.create_plugin_assembly(serialize(model))
        assembly_id = created["pluginassemblyid"]
        action = "created"
    else:
        assembly_id = existing["pluginassemblyid"]
        client.update_plugin_assembly(assembly_id, {"content": model.content, "version": model.version})
        action = "updated"
    return assembly_id, {"action": action, "assembly_id": assembly_id}


def _label_text(label: Any, languagecode: int) -> str:
    """First localized text matching ``languagecode`` (else the first available) from a :class:`Label`."""
    locs = getattr(label, "localized", None)
    if not locs:
        return str(label) if label else ""
    for loc in locs:
        if getattr(loc, "language_code", None) == languagecode:
            return getattr(loc, "text", "")
    return getattr(locs[0], "text", "")


def _deploy_custom_action(client: Any, action: CustomAction, *, assembly_id: str,
                          languagecode: int = 2052) -> dict[str, Any]:
    """Best-effort: create the Action definition via workflows (category=3) + register a step on its SDK
    message. Falls back to ``manual_update_required`` if creation or message resolution fails."""
    name = _label_text(action.display_name, languagecode) or action.schema_name
    payload = {
        "name": name,
        "category": 3,  # Action
        "type": 1,  # Definition
        "uniquename": action.schema_name,
        "primaryentity": action.entity or "none",
        "languagecode": languagecode,
        "scope": 4,  # Organization
        "triggeroncreate": False,
        "triggeronupdate": False,
    }
    try:
        client.create_custom_action(payload)
    except Exception as e:  # noqa: BLE001
        return {"schema_name": action.schema_name, "action": "manual_update_required",
                "reason": _MANUAL_ACTION_NOTE, "error": str(e)[:200]}
    sdkmessage_id = client.get_sdk_message_id(action.schema_name)
    if not sdkmessage_id:
        return {"schema_name": action.schema_name, "action": "manual_update_required",
                "reason": "Action created but its SDK message is not resolvable (may need activation)."}
    step = PluginStep(name=f"{action.schema_name}.Invoke", message=action.schema_name,
                      entity=action.entity or "", stage=40, mode=0)
    res = _register_step(client, step, assembly_id)
    if res.get("id"):
        return {"schema_name": action.schema_name, "action": "created", "workflow_created": True,
                "step_id": res["id"]}
    return {"schema_name": action.schema_name, "action": "manual_update_required",
            "reason": _MANUAL_ACTION_NOTE, "error": res.get("error", "")[:200]}


def deploy(
    client: Any, model: Plugin, *, prefix: str = "new", config: Any = None
) -> dict[str, Any]:
    if model.content_kind == ContentKind.Package:
        assembly_id, info = _deploy_package(client, model)
        # Package plugins: the PACKAGE (10030) is the solution unit — adding the assembly(91) returns 405
        # ("export the Package directly"); the package encapsulates the assembly+plugintypes+steps.
        add_targets: list[tuple[int, str, str]] = [
            (PLUGINPACKAGE_SOLUTION_CODE, info["package_id"], info["package_name"])]
    else:
        assembly_id, info = _deploy_assembly(client, model)
        add_targets = [(SOLUTION_CODE, assembly_id, model.name)]
    steps_result: list[dict[str, Any]] = []
    existing_steps = {s.get("name"): s.get("sdkmessageprocessingstepid")
                      for s in client.get_steps_by_assembly(assembly_id)}  # idempotency: skip existing by name
    for step in model.steps:
        if step.name in existing_steps:
            sid = existing_steps[step.name]
            steps_result.append({"name": step.name, "action": "exists", "id": sid})
            add_targets.append((92, sid, step.name))
            continue
        try:
            res = _register_step(client, step, assembly_id)
            steps_result.append(res)
            if res.get("id"):
                add_targets.append((92, res["id"], step.name))
        except Exception as e:  # noqa: BLE001
            steps_result.append({"name": step.name, "action": "failed", "error": str(e)})

    actions_result = [_deploy_custom_action(client, a, assembly_id=assembly_id) for a in model.custom_actions]

    result: dict[str, Any] = {
        "action": info["action"],
        "assembly_id": assembly_id,
        "steps": steps_result,
        "custom_actions": actions_result,
        "add_targets": add_targets,
    }
    if model.content_kind == ContentKind.Package:
        result["package_id"] = info["package_id"]
        result["package_name"] = info["package_name"]
    return result


def plan(client: Any, model: Plugin, *, prefix: str = "new") -> dict[str, Any]:
    existing = client.get_plugin_assembly_by_name(model.name)
    action = "would_create" if existing is None else "would_update"
    return {
        "action": action,
        "path": model.content_kind.value,
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
    try:
        source_type = SourceType(int(asm.get("sourcetype") or 0))
    except ValueError:
        source_type = SourceType.Database  # package-derived assemblies use sourcetype=4 (not in the enum)
    return Plugin(
        name=asm.get("name") or "",
        content=asm.get("content") or "",
        version=asm.get("version") or "1.0.0.0",
        isolation_mode=IsolationMode(int(asm.get("isolationmode") or 2)),
        source_type=source_type,
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


_PLUGIN_TFMS = ("net462", "net471", "net48")  # env-supported .NET Framework plugin targets (live-pinned)


def lint(model: Plugin, *, prefix: str = "new") -> list[Issue]:
    issues: list[Issue] = []
    if not is_custom(model.name, prefix):
        issues.append(Issue(WARNING, f"Plugin '{model.name}' does not start with prefix '{prefix}_'."))
    if not model.content:
        issues.append(Issue(WARNING, f"Plugin '{model.name}' has empty content (base64 DLL)."))
    if model.target_framework and model.target_framework.lower() not in _PLUGIN_TFMS:
        issues.append(Issue(
            WARNING,
            f"Plugin '{model.name}' target_framework '{model.target_framework}' is not a supported .NET Framework "
            f"plugin TFM {_PLUGIN_TFMS} — this env's plugin runtime rejects net6/net8/netstandard "
            f"(use net462)."))
    for step in model.steps:
        if not step.message or not step.entity:
            issues.append(Issue(ERROR, f"Plugin step '{step.name}' needs message and entity."))
    return issues
