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
from .models import ContentKind, CustomAction, IsolationMode, Plugin, PluginStep, SourceType, StepImage

KEY = "plugin"
SOLUTION_CODE = 91  # PluginAssembly (90=PluginType, 92=Step); pinned live
PLUGINPACKAGE_SOLUTION_CODE = 10030  # PluginPackage (NuGet) — the solution unit for package plugins;
# adding the assembly(91) of a package-derived plugin returns 405 ("export the Package directly").
MODEL_CLS = Plugin
DEPENDS_ON: tuple[str, ...] = ("table",)
CODEGEN_IMPORTS: tuple[str, ...] = (
    "Plugin",
    "PluginStep",
    "StepImage",
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


def _resolve_plugintype(client: Any, assembly_id: str, plugin_type: str,
                        assembly_name: str = "") -> Optional[dict[str, Any]]:
    """Resolve the PluginType (IPlugin class) for an assembly. ``plugin_type`` matches typename/name; empty
    uses the assembly's single plugintype (None if 0 or >1).

    If the typename is missing from the assembly's plugintype list (a content update does NOT
    re-enumerate types), create the record so the step can bind (verified live)."""
    ptypes = client.get_plugintypes_by_assembly(assembly_id)
    if plugin_type:
        pt = next((p for p in ptypes if plugin_type in (p.get("typename"), p.get("name"))), None)
        if pt is None:
            try:
                created = client.create_plugintype({
                    "typename": plugin_type,
                    "friendlyname": plugin_type.rsplit(".", 1)[-1],
                    "name": plugin_type.rsplit(".", 1)[-1],
                    "pluginassemblyid@odata.bind": f"/pluginassemblies({assembly_id})",
                })
                return {"plugintypeid": created["plugintypeid"], "typename": plugin_type,
                        "name": plugin_type.rsplit(".", 1)[-1], "created": True}
            except Exception:  # noqa: BLE001 — fall through to None; step registration reports it
                return None
        return pt
    return ptypes[0] if len(ptypes) == 1 else None


def _image_payload(image: StepImage, *, step_id: str, message: str) -> dict[str, Any]:
    """Build the sdkmessageprocessingstepimage create payload (pinned live).

    ``imagetype`` 0=Pre, 1=Post; ``attributes`` omitted for all-attributes images (an empty
    string would be rejected). ``messagepropertyname`` is message-dependent (pinned live):
    Create → ``Id`` (Target is rejected 0x8004416b on Create); Update/Delete/others → ``Target``.
    """
    payload: dict[str, Any] = {
        "entityalias": image.alias,
        "imagetype": 0 if image.image_type.lower() == "pre" else 1,
        "messagepropertyname": "Id" if message.lower() == "create" else "Target",
        "sdkmessageprocessingstepid@odata.bind": f"/sdkmessageprocessingsteps({step_id})",
    }
    attrs = (image.attributes or "").strip()
    if attrs and attrs != "*":
        payload["attributes"] = attrs  # the live attribute is 'attributes' (not 'attributes1')
    return payload


def _register_images(client: Any, step: PluginStep, step_id: str) -> list[dict[str, Any]]:
    """Create the step's Pre/Post images; warn-not-block on failure (idempotent by alias)."""
    results: list[dict[str, Any]] = []
    if not step.images:
        return results
    existing = {img.get("entityalias") for img in client.get_step_images(step_id)}
    for image in step.images:
        if image.alias in existing:
            results.append({"alias": image.alias, "action": "exists"})
            continue
        try:
            res = client.create_step_image(_image_payload(image, step_id=step_id, message=step.message))
            results.append({"alias": image.alias, "action": "created",
                            "id": res.get("sdkmessageprocessingstepimageid")})
        except Exception as e:  # noqa: BLE001
            results.append({"alias": image.alias, "action": "failed", "error": str(e)[:200]})
    return results


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
    result = {"name": step.name, "action": "created", "id": res["sdkmessageprocessingstepid"]}
    images = _register_images(client, step, res["sdkmessageprocessingstepid"])
    if images:
        result["images"] = images
    return result


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


def _strip_publisher_prefix(schema_name: str) -> str:
    """``new_Interface_X`` → ``Interface_X`` — the workflow ``uniquename`` has no publisher prefix
    (pinned live: the SDK message carries the prefix, the workflow record does not)."""
    _, _, rest = schema_name.partition("_")
    return rest or schema_name


def _deploy_custom_action(client: Any, action: CustomAction, *, assembly_id: str,
                          languagecode: int = 2052) -> dict[str, Any]:
    """Create the Action definition via workflows (category=3) + activate + register a step on its SDK
    message. Activation is what provisions the SDK message — without it the action is not callable.
    Idempotent: an existing workflow (by uniquename) is reused, not duplicated."""
    uniquename = action.uniquename or _strip_publisher_prefix(action.schema_name)
    name = _label_text(action.display_name, languagecode) or action.schema_name
    result: dict[str, Any] = {"schema_name": action.schema_name, "workflow_uniquename": uniquename}

    wf = client.get_workflow_by_uniquename(uniquename)
    wf_id: Optional[str] = None
    if wf is not None:
        wf_id = wf.get("workflowid")
        result["workflow"] = "exists"
    else:
        payload = {
            "name": name,
            "category": 3,  # Action
            "type": 1,  # Definition
            "uniquename": uniquename,
            "primaryentity": action.entity or "none",
            "languagecode": languagecode,
            "scope": 4,  # Organization
        }
        # NOTE: triggeroncreate/triggeronupdate do not exist on this entity version (pinned live:
        # 400 "property does not exist"); triggeroncreateattributelist is the modern equivalent.
        if action.xaml:
            payload["xaml"] = action.xaml  # XAML w/ x:Members declares the In/Out arguments (jsondata/msg)
        try:
            res = client.create_custom_action(payload)
            wf_id = res.get("workflowid")
            result["workflow"] = "created"
        except Exception as e:  # noqa: BLE001
            result.update({"action": "manual_update_required", "reason": _MANUAL_ACTION_NOTE,
                           "error": str(e)[:200]})
            return result

    if wf is not None and wf.get("statecode") != 1 and wf.get("type") == 1:
        # Existing draft definition (type=1) → activate so the SDK message exists
        try:
            client.activate_workflow(wf_id)
            result["workflow"] = "activated"
        except Exception as e:  # noqa: BLE001
            result.update({"action": "manual_update_required",
                           "reason": "Action definition exists but activation failed (maker portal).",
                           "error": str(e)[:200]})
            return result
    elif wf is None:
        # Newly created definitions start as draft → activate
        try:
            client.activate_workflow(wf_id)
            result["workflow"] = "created+activated"
        except Exception as e:  # noqa: BLE001
            result.update({"action": "manual_update_required",
                           "reason": "Action created but activation failed — SDK message not provisioned.",
                           "error": str(e)[:200]})
            return result

    sdkmessage_id = client.get_sdk_message_id(action.schema_name)
    if not sdkmessage_id:
        result.update({"action": "manual_update_required",
                       "reason": "Action created+activated but its SDK message is not resolvable yet."})
        return result

    # PRT step-name convention for action steps: "{typename}: {message} of any Entity" (pinned live)
    handler = _resolve_plugintype(client, assembly_id, action.plugin_type)
    handler_typename = (handler or {}).get("typename") or action.plugin_type or action.schema_name
    step = PluginStep(
        name=f"{handler_typename}: {action.schema_name} of any Entity",
        message=action.schema_name, entity="", stage=40, mode=0,
        plugin_type=action.plugin_type)
    # idempotency: a step with this name already exists → reuse (deploy is re-runnable)
    existing = {s.get("name"): s.get("sdkmessageprocessingstepid")
                for s in client.get_steps_by_assembly(assembly_id)}
    if step.name in existing:
        result["step"] = {"name": step.name, "action": "exists", "id": existing[step.name]}
        result["action"] = "created"
        result["add_target"] = (29, wf_id, name)  # Workflow — for solution management
        result["add_target_step"] = (92, existing[step.name], step.name)
        return result
    res = _register_step(client, step, assembly_id)
    result["step"] = res
    if res.get("id"):
        result["action"] = "created"
        result["workflow_created"] = True
        result["add_target"] = (29, wf_id, name)  # Workflow — for solution management
        result["add_target_step"] = (92, res["id"], step.name)
        return result
    result.update({"action": "manual_update_required", "reason": _MANUAL_ACTION_NOTE,
                   "error": res.get("error", "")[:200]})
    return result


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
            entry: dict[str, Any] = {"name": step.name, "action": "exists", "id": sid}
            images = _register_images(client, step, sid)  # backfill images on pre-existing steps
            if images:
                entry["images"] = images
            steps_result.append(entry)
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
    for a_res in actions_result:
        if a_res.get("add_target"):
            add_targets.append(a_res.pop("add_target"))  # Workflow (29) — solution management
        if a_res.get("add_target_step"):
            add_targets.append(a_res.pop("add_target_step"))  # the action's Invoke step (92)

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
    steps = []
    for s in steps_raw:
        images: tuple[StepImage, ...] = ()
        try:
            images = tuple(
                StepImage(
                    alias=img.get("entityalias") or "",
                    image_type="Pre" if int(img.get("imagetype") or 1) == 0 else "Post",
                    attributes=img.get("attributes") or "",
                )
                for img in client.get_step_images(s.get("sdkmessageprocessingstepid"))
            )
        except Exception:  # noqa: BLE001 — images are supplementary; never block reverse
            pass
        steps.append(PluginStep(
            name=s.get("name") or "",
            message=_step_message(s),
            entity="",
            stage=int(s.get("stage") or 40),
            mode=int(s.get("mode") or 0),
            deployment=int(s.get("supporteddeployment") or 0),
            filtering_attributes=s.get("filteringattributes") or "",
            description=s.get("description") or "",
            rank=int(s.get("rank") or 1),
            images=images,
        ))
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
    if step.images:
        imgs = ", ".join(
            f"StepImage(alias={img.alias!r}, image_type={img.image_type!r}, attributes={img.attributes!r})"
            for img in step.images
        )
        parts.append(f"images=({imgs},)")
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
