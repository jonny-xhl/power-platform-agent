"""
Ribbon sync standalone flow (framework_power Phase 7).

Ribbon customization has no Web API write path — it deploys via ``ExportSolution`` → edit
``customizations.xml`` (RibbonDiffXml) → ``ImportSolution``. This flow wraps that round-trip around a
typed :class:`RibbonDefinition` (see ``components.models``), using a **dedicated small ribbon solution**
+ targeted ``PublishXml`` so deployment is fast and backup-free (unlike full-solution Ribbon Workbench
re-imports).

Flows:
- ``plan_ribbons``  — read-only: report what would be deployed (no export/import).
- ``sync_ribbons``  — for each ribbon: ensure the entity (or Application Ribbons) is in the dedicated
  solution → export → inject RibbonDiffXml → import → targeted publish.
- ``reverse_ribbons`` — export the dedicated solution → extract the entity's RibbonDiffXml → parse to a
  model (the AUTHORING diff, not RetrieveEntityRibbon's compiled ribbon).
- ``lint_ribbon`` / ``codegen_ribbon`` / ``load_ribbon``.

Non-destructive: the authored ``RibbonDefinition`` is the source of truth for that entity's ribbon diff;
re-import replaces only the ``<RibbonDiffXml>`` region (forms/views preserved byte-for-byte).
"""

from __future__ import annotations

import dataclasses
import importlib.util
import logging
from dataclasses import is_dataclass
from pathlib import Path
from typing import Any, Optional

from . import solution_zip
from .components.models import RibbonDefinition, RibbonScope
from .deployer import _is_already_exists
from .ribbon_xml import parse_ribbondiff, to_ribbondiff

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------- load


def load_ribbon(path: Any) -> RibbonDefinition:
    """Load a ``RibbonDefinition`` from a Python module file that exports ``RIBBON``."""
    path = Path(path)
    spec = importlib.util.spec_from_file_location(f"_ribbon_def_{path.stem}", str(path))
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load ribbon definition file: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    ribbon = getattr(mod, "RIBBON", None)
    if not isinstance(ribbon, RibbonDefinition):
        raise ValueError(f"{path} does not export a RibbonDefinition as `RIBBON`")
    return ribbon


# ----------------------------------------------------------------- solution helpers


def _ensure_solution(client: Any, solution_name: str, prefix: str) -> None:
    """Create the dedicated ribbon solution if it doesn't exist (uses the publisher matching ``prefix``)."""
    if client.get_solution_by_name(solution_name) is not None:
        return
    pubs = client.session.get(
        client.get_api_url("publishers?$select=uniquename,publisherid,customizationprefix&$top=50")
    ).json().get("value", [])
    pub = next((p for p in pubs if p.get("customizationprefix") == prefix), None)
    if pub is None:
        raise RuntimeError(f"no publisher with prefix '{prefix}' to create solution '{solution_name}'")
    client.create_solution({
        "uniquename": solution_name,
        "friendlyname": solution_name,
        "version": "1.0.0.0",
        "publisherid@odata.bind": f"/publishers({pub['publisherid']})",
    })


def _ensure_entity_in_solution(client: Any, solution_name: str, entity: str) -> None:
    """Add the entity (code 1) SHELL to the dedicated solution if not already present (idempotent).

    ``DoNotIncludeSubcomponents=True`` is mandatory: adding the entity with its sub-components (forms/views/
    attributes) bloats the solution and Ribbon Workbench refuses to load it ("solution contains Entities
    that have all their sub-components included"). The shell still carries the entity's ``<RibbonDiffXml>``,
    which is the only thing this flow edits. NOTE: if the entity was previously added WITH sub-components,
    it must be removed and re-added (or the solution recreated) for the shell-only behavior to take effect.
    """
    meta = client.get_entity_metadata(entity)
    mid = meta.get("MetadataId")
    if not mid:
        raise RuntimeError(f"no MetadataId for entity '{entity}'")
    try:
        client.add_solution_component(solution_name, 1, mid, do_not_include_subcomponents=True)
    except Exception as e:  # noqa: BLE001
        if not _is_already_exists(e):
            raise


def _ensure_application_ribbons_in_solution(client: Any, solution_name: str) -> None:
    """Add the 'Application Ribbons' component to the dedicated solution (best-effort; verify the component
    code in your env). ComponentType 960 is the conventional ribbon component type."""
    # The Application Ribbons is added as a solution component; the exact code can vary by org/version.
    # We try component type 960 (ribbon) with a well-known sentinel id; failures (already-added) are benign.
    try:
        client.add_solution_component(solution_name, 960, "00000000-0000-0000-0000-000000000000")
    except Exception as e:  # noqa: BLE001
        if not _is_already_exists(e):
            logger.warning(f"could not add Application Ribbons to '{solution_name}': {e}")


# ----------------------------------------------------------------- plan


def plan_ribbons(client: Any, ribbons: list[RibbonDefinition], *, prefix: str = "new",
                 solution: Optional[str] = None) -> dict[str, Any]:
    """Read-only: report what each ribbon would deploy (no export/import)."""
    entries: list[dict[str, Any]] = []
    for ribbon in ribbons:
        schema = None
        if ribbon.entity:
            try:
                schema = client.get_entity_metadata(ribbon.entity).get("SchemaName") or ribbon.entity
            except Exception as e:  # noqa: BLE001
                entries.append({"entity": ribbon.entity, "plan": {"action": "failed", "error": str(e)}})
                continue
        entries.append({
            "entity": ribbon.entity or "application",
            "solution": solution,
            "plan": {"action": "would_import", "buttons": len(ribbon.buttons),
                     "hide_oobs": len(ribbon.hide_oobs), "schema": schema},
        })
    return {"ribbons": entries}


# ----------------------------------------------------------------- sync


def sync_ribbons(
    client: Any,
    ribbons: list[RibbonDefinition],
    *,
    prefix: str = "new",
    solution: str,
    publish: bool = True,
) -> dict[str, Any]:
    """Deploy ribbons via the dedicated-solution round-trip (export → inject → import → publish)."""
    _ensure_solution(client, solution, prefix)
    result: dict[str, Any] = {"synced": [], "publish": {}}
    changed_entities: set[str] = set()
    changed_application = False

    for ribbon in ribbons:
        schema: Optional[str] = None
        if ribbon.entity:
            schema = client.get_entity_metadata(ribbon.entity).get("SchemaName") or ribbon.entity
            _ensure_entity_in_solution(client, solution, ribbon.entity)
        else:
            _ensure_application_ribbons_in_solution(client, solution)
        try:
            zip_bytes = client.export_solution(solution)
            xml = solution_zip.read_customizations_xml(zip_bytes)
            diff = to_ribbondiff(ribbon)
            if schema:
                new_xml = solution_zip.inject_entity_ribbondiff(xml, schema, diff)
                if ribbon.entity:
                    changed_entities.add(ribbon.entity)
            else:
                new_xml = solution_zip.inject_application_ribbondiff(xml, diff)
                changed_application = True
            new_zip = solution_zip.write_customizations_xml(zip_bytes, new_xml)
            job = client.import_solution(new_zip)
        except Exception as e:  # noqa: BLE001
            result["synced"].append({"entity": ribbon.entity or "application", "action": "failed", "error": str(e)})
            continue
        result["synced"].append({
            "entity": ribbon.entity or "application", "action": "imported", "import": job,
            "buttons": len(ribbon.buttons), "hide_oobs": len(ribbon.hide_oobs),
        })

    pubs: list[dict[str, Any]] = []
    if publish:
        for ent in sorted(e for e in changed_entities if e):
            try:
                client.publish_entity(ent)
                pubs.append({"entity": ent, "published": True})
            except Exception as e:  # noqa: BLE001
                pubs.append({"entity": ent, "published": False, "error": str(e)})
        if changed_application:
            try:
                client.publish_application_ribbon()
                pubs.append({"application_ribbon": True, "published": True})
            except Exception as e:  # noqa: BLE001
                pubs.append({"application_ribbon": True, "published": False, "error": str(e)})
    result["publish"] = pubs
    return result


# ----------------------------------------------------------------- reverse


def reverse_ribbons(client: Any, entity: Optional[str], *, solution: str) -> RibbonDefinition:
    """Export the dedicated solution and parse the entity's (or Application) RibbonDiffXml into a model.

    ``entity=None`` reverses the Application Ribbon block. This reads the AUTHORING diff (what was
    imported), not RetrieveEntityRibbon's compiled ribbon.
    """
    zip_bytes = client.export_solution(solution)
    xml = solution_zip.read_customizations_xml(zip_bytes)
    if entity:
        schema = client.get_entity_metadata(entity).get("SchemaName") or entity
        fragment = solution_zip.extract_ribbondiff(xml, schema)
        ribbon = parse_ribbondiff(fragment) if fragment else RibbonDefinition(entity=entity)
        ribbon.entity = entity
        return ribbon
    # application: extract the root-level RibbonDiffXml (region after </Entities>)
    split_idx = xml.find("</Entities>")
    tail = xml[split_idx:] if split_idx >= 0 else xml
    m = (solution_zip.SELF_CLOSED_RIBBON_RE.search(tail) or solution_zip.OPEN_RIBBON_RE.search(tail))
    return parse_ribbondiff(m.group(0)) if m else RibbonDefinition(entity=None)


# ----------------------------------------------------------------- lint + codegen


def lint_ribbon(ribbon: RibbonDefinition, *, prefix: str = "new") -> list:
    """Offline convention checks (returns ``lint.Issue``-like dicts; uses ERROR/WARNING severities)."""
    from .lint import ERROR, WARNING, Issue

    issues = []
    cmd_ids = {c.id for c in ribbon.commands}
    loc_ids = {loc.id for loc in ribbon.loclabels}
    for btn in ribbon.buttons:
        if btn.command and btn.command not in cmd_ids:
            issues.append(Issue(ERROR, f"Button '{btn.id}' references unknown command '{btn.command}'."))
        if btn.label_loclabel_id and btn.label_loclabel_id not in loc_ids:
            issues.append(Issue(ERROR, f"Button '{btn.id}' references unknown LocLabel '{btn.label_loclabel_id}'."))
    for cmd in ribbon.commands:
        if not cmd.library:
            issues.append(Issue(ERROR, f"Command '{cmd.id}' has no JS library ($webresource:new_/js/...)."))
        else:
            issues.append(Issue(  # noqa: PERF401-style advisory
                WARNING,
                f"Command '{cmd.id}' library '{cmd.library}' — ensure the JS webresource is synced+published first.",
            ))
    for hide in ribbon.hide_oobs:
        if not hide.oob_command_id.startswith("Mscrm."):
            issues.append(Issue(WARNING, f"hide_oob '{hide.oob_command_id}' doesn't look like an OOB id (Mscrm.…)."))
    for ov in ribbon.command_overrides:
        if not ov.oob_command_id.startswith("Mscrm."):
            issues.append(Issue(
                WARNING, f"customise_command '{ov.oob_command_id}' doesn't look like an OOB id (Mscrm.…)."))
        if not ov.added_rule_ids:
            issues.append(Issue(WARNING, f"customise_command '{ov.oob_command_id}' has no show_fn/enable_fn — it just "
                                         "re-writes the command with the preserved rules (rarely intended)."))
        if not ov.actions_xml.strip():
            issues.append(Issue(WARNING, f"customise_command '{ov.oob_command_id}' has no actions_xml — the override "
                                         "REPLACES the OOB <CommandDefinition>, so an empty <Actions/> may stop the "
                                         "click. Paste the OOB <Actions> from Ribbon Workbench."))
        if not ov.preserve_display_rules and not ov.preserve_enable_rules:
            issues.append(Issue(WARNING, f"customise_command '{ov.oob_command_id}' preserves no OOB rules — the "
                                         "button will show solely on your CustomRule (original permission/state "
                                         "gating lost). Pass preserve_display_rules=… (see RW)."))
    return issues


def codegen_ribbon(ribbon: RibbonDefinition) -> str:
    """Emit ``RIBBON = RibbonDefinition(...)`` Python source that reconstructs the model (recursive)."""
    return _to_py(ribbon, 0)


def _to_py(value: Any, indent: int) -> str:
    pad = "    " * indent
    inner = "    " * (indent + 1)
    if isinstance(value, RibbonScope):
        return f"RibbonScope.{value.name}"
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
        items = [inner + _to_py(k, indent + 1) + ": " + _to_py(v, indent + 1) for k, v in value.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if is_dataclass(value) and not isinstance(value, type):
        parts = [
            inner + f.name + "=" + _to_py(getattr(value, f.name), indent + 1)
            for f in dataclasses.fields(value)
        ]
        return type(value).__name__ + "(\n" + ",\n".join(parts) + "\n" + pad + ")"
    return repr(value)


__all__ = ["load_ribbon", "plan_ribbons", "sync_ribbons", "reverse_ribbons", "lint_ribbon", "codegen_ribbon"]
