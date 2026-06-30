"""RibbonDiffXml serialize / parse / builders (framework_power Phase 7).

A ribbon customization is a ``<RibbonDiffXml>`` fragment. ``RibbonDefinition`` (see ``components.models``)
is the typed model; this module is the XML <-> model boundary, using ONLY stdlib ``xml.etree.ElementTree``.

Conventions (research-pinned, see framework_power/CLAUDE.md §9.6):
- Show/hide UNIFORMLY via ``<CustomRule>`` (JS returns bool) inside ``<DisplayRule>`` (show/hide) and
  ``<EnableRule>`` (enable/disable); one JS function can power many rules.
- Buttons reference commands (``Command``) + localized labels (``$LocLabels:<id>``); commands/actions
  reference JS via ``Library="$webresource:new_/js/..."``.
- Hide OOB: default ``command_override`` (reversible) = a ``<CommandDefinition>`` override with the
  mutually-exclusive ``Mscrm.HideOnModern`` + ``Mscrm.ShowOnlyOnModern`` DisplayRules; ``hide_custom_action``
  emits ``<HideCustomAction>`` (sticky).
- A ``<RibbonDiffXml>`` always carries ``<Templates><RibbonTemplates Id="Mscrm.Templates"/></Templates>``.
"""

from __future__ import annotations

import copy
from typing import Optional, Union
from xml.etree import ElementTree as ET

from .components.models import (
    RibbonButton,
    RibbonCommand,
    RibbonCommandOverride,
    RibbonCustomRule,
    RibbonDefinition,
    RibbonDisplayRule,
    RibbonEnableRule,
    RibbonHideOob,
    RibbonLocLabel,
    RibbonScope,
)

LANGUAGE_EN = 1033
LANGUAGE_ZH = 2052
DEFAULT_LANGUAGE = LANGUAGE_ZH  # matches the org (zh-CN)

# Observed OOB command rules, for ``customise_command``'s ``preserve_*`` defaults. The tool CANNOT read the
# compiled ribbon over the Web API (RetrieveEntityRibbon is SOAP-only and 404s), so these are the rule ids
# Ribbon Workbench surfaces on "Customise Command" — CONFIRM COMPLETENESS for your org (a missing rule changes
# behaviour). Keyed by the OOB command SUFFIX (the last segment of ``Mscrm.{scope}.{entity}.{suffix}``).
# Value = (display_rule_ids, enable_rule_ids).
OOB_COMMAND_RULES: dict[str, tuple[list[str], list[str]]] = {
    "Deactivate": (
        ["Mscrm.CanWritePrimary", "Mscrm.PrimaryIsActive", "Mscrm.PrimaryEntityHasStatecode"],
        [],
    ),
}

# Default injectable GROUP per scope. The button's Location is built as
# ``Mscrm.{scope}.{entity}.{area}.Controls._children`` (entity scopes) — i.e. ``area`` is the group path
# and ``.Controls._children`` injects the button INTO that existing group's controls. Pinning a REAL
# group (not an invented one) is what makes the button render — a non-existent group orphans the button.
# Pinned from real RibbonDiffXml examples (see framework_power/CLAUDE.md §9.6): form groups include
# Save/Actions/Collaborate; grid groups include Management/Actions.
DEFAULT_AREA_BY_SCOPE = {
    RibbonScope.Form: "MainTab.Save",
    RibbonScope.HomepageGrid: "MainTab.Management",
    RibbonScope.SubGrid: "MainTab.Management",
    RibbonScope.Application: "GlobalTab.New",
}


def _default_crm_params(scope: RibbonScope) -> list[str]:
    """Default ``<CrmParameter Value>`` list for a button's JS, by scope.

    Form ribbon → ``PrimaryControl`` (the JS receives the **formContext**); HomepageGrid/SubGrid →
    ``SelectedControl`` (the JS receives the **gridContext**). See the dv-ribbon-python skill's
    "ribbon JS 参数接收" table for the full CrmParameter → JS-arg mapping.
    """
    if scope in (RibbonScope.HomepageGrid, RibbonScope.SubGrid):
        return ["SelectedControl"]
    return ["PrimaryControl"]


# ============================================================ serialize


def to_ribbondiff(ribbon: RibbonDefinition) -> str:
    """Serialize a :class:`RibbonDefinition` to a ``<RibbonDiffXml>…</RibbonDiffXml> fragment string."""
    root = ET.Element("RibbonDiffXml")
    # CustomActions: buttons (as CustomAction+Button) + hide_custom_action hide_oobs
    ca = ET.SubElement(root, "CustomActions")
    for btn in ribbon.buttons:
        ca.append(_serialize_button_action(btn, ribbon.entity))
    for hide in ribbon.hide_oobs:
        if hide.method == "hide_custom_action":
            h = ET.SubElement(ca, "HideCustomAction")
            h.set("HideActionId", hide.attrs.get("HideActionId") or _hide_action_id(hide, ribbon.entity))
            h.set("Location", hide.oob_command_id)
    tmpl = ET.SubElement(root, "Templates")
    ET.SubElement(tmpl, "RibbonTemplates").set("Id", "Mscrm.Templates")
    # CommandDefinitions: authored commands + command_override hide_oobs + "customise" overrides
    cd = ET.SubElement(root, "CommandDefinitions")
    for cmd in ribbon.commands:
        cd.append(_serialize_command(cmd))
    for hide in ribbon.hide_oobs:
        if hide.method == "command_override":
            cd.append(_serialize_hide_override(hide))
    for override in ribbon.command_overrides:
        cd.append(_serialize_command_override(override))
    # RuleDefinitions
    rd = ET.SubElement(root, "RuleDefinitions")
    ET.SubElement(rd, "TabDisplayRules")
    dr = ET.SubElement(rd, "DisplayRules")
    for rule in ribbon.display_rules:
        dr.append(_serialize_display_rule(rule))
    er = ET.SubElement(rd, "EnableRules")
    for er_rule in ribbon.enable_rules:
        er.append(_serialize_enable_rule(er_rule))
    # LocLabels
    ll = ET.SubElement(root, "LocLabels")
    for loc in ribbon.loclabels:
        ll.append(_serialize_loclabel(loc))
    return ET.tostring(root, encoding="unicode")


def _button_location(btn: RibbonButton, entity: Optional[str]) -> str:
    """Location = ``Mscrm.{scope}.{entity}.{area}.Controls._children`` (entity scope) or
    ``Mscrm.{area}.Controls._children`` (Application scope).

    ``area`` is the group path (e.g. ``MainTab.Save``); ``.Controls._children`` injects the button INTO
    that existing group's controls collection (the only valid way to add a control — a bare group id, or a
    non-existent group, orphans the button so it never renders). See DEFAULT_AREA_BY_SCOPE.
    """
    if btn.scope == RibbonScope.Application or entity is None:
        return f"Mscrm.{btn.area}.Controls._children"
    return f"Mscrm.{btn.scope.value}.{entity}.{btn.area}.Controls._children"


def _button_custom_action_id(btn: RibbonButton) -> str:
    return btn.attrs.get("Id") or f"{btn.id}.CustomAction"


def _hide_action_id(hide: RibbonHideOob, entity: Optional[str]) -> str:
    ent = entity or "application"
    return f"new.{ent}.Hide.{hide.oob_command_id.replace('.', '_')}.HideAction"


def _serialize_button_action(btn: RibbonButton, entity: Optional[str]) -> ET.Element:
    ca = ET.Element("CustomAction")
    # attrs-first: a reversed button (attrs populated) keeps its exact Id/Location/Sequence; an authored
    # button (empty attrs) generates them. This makes parse->serialize lossless (Location carries the entity).
    ca.set("Id", btn.attrs.get("Id") or _button_custom_action_id(btn))
    ca.set("Location", btn.attrs.get("Location") or _button_location(btn, entity))
    ca.set("Sequence", btn.attrs.get("Sequence") or str(btn.sequence))
    cui = ET.SubElement(ca, "CommandUIDefinition")
    button = ET.SubElement(cui, "Button")
    button.set("Id", f"{btn.id}.Button")
    button.set("Command", btn.command)
    button.set("Sequence", str(btn.sequence))
    if btn.label_loclabel_id:
        button.set("LabelText", f"$LocLabels:{btn.label_loclabel_id}")
        button.set("ToolTipTitle", f"$LocLabels:{btn.label_loclabel_id}")
    if btn.tooltip_loclabel_id:
        button.set("ToolTipDescription", f"$LocLabels:{btn.tooltip_loclabel_id}")
    button.set("TemplateAlias", btn.template_alias)
    if btn.image16:
        button.set("Image16by16", f"$webresource:{btn.image16}")
    if btn.image32:
        button.set("Image32by32", f"$webresource:{btn.image32}")
    return ca


def _serialize_command(cmd: RibbonCommand) -> ET.Element:
    el = ET.Element("CommandDefinition")
    el.set("Id", cmd.id)
    er = ET.SubElement(el, "EnableRules")
    for rid in cmd.enable_rules:
        ET.SubElement(er, "EnableRule").set("Id", rid)
    dr = ET.SubElement(el, "DisplayRules")
    for rid in cmd.display_rules:
        ET.SubElement(dr, "DisplayRule").set("Id", rid)
    actions = ET.SubElement(el, "Actions")
    if cmd.function_name and cmd.library:
        js = ET.SubElement(actions, "JavaScriptFunction")
        js.set("Library", cmd.library if cmd.library.startswith("$") else f"$webresource:{cmd.library}")
        js.set("FunctionName", cmd.function_name)
        for p in cmd.params:
            ET.SubElement(js, "CrmParameter").set("Value", p)
    return el


def _serialize_hide_override(hide: RibbonHideOob) -> ET.Element:
    """A <CommandDefinition Id=<OOB id>> with mutually-exclusive DisplayRules -> always false (hidden)."""
    el = ET.Element("CommandDefinition")
    el.set("Id", hide.oob_command_id)
    ET.SubElement(el, "EnableRules")
    dr = ET.SubElement(el, "DisplayRules")
    ET.SubElement(dr, "DisplayRule").set("Id", "Mscrm.HideOnModern")
    ET.SubElement(dr, "DisplayRule").set("Id", "Mscrm.ShowOnlyOnModern")
    ET.SubElement(el, "Actions")
    return el


def _serialize_command_override(override: RibbonCommandOverride) -> ET.Element:
    """A "Customise Command" override: preserve the OOB command's rules + add CustomRule hide/disable.

    The override REPLACES the OOB CommandDefinition, so to keep the button working we must (a) list the OOB
    rules we want to keep and (b) include the OOB ``<Actions>`` (``actions_xml``) so the click still fires.
    Added CustomRules go in ``<EnableRules>`` (per MS Learn, ``<CustomRule>`` is documented only under
    ``<EnableRule>``; command bar treats disabled as hidden → controls visibility).
    """
    el = ET.Element("CommandDefinition")
    el.set("Id", override.oob_command_id)
    er = ET.SubElement(el, "EnableRules")
    for rid in override.preserve_enable_rules:
        ET.SubElement(er, "EnableRule").set("Id", rid)
    for rid in override.added_rule_ids:
        ET.SubElement(er, "EnableRule").set("Id", rid)
    dr = ET.SubElement(el, "DisplayRules")
    for rid in override.preserve_display_rules:
        ET.SubElement(dr, "DisplayRule").set("Id", rid)
    if override.actions_xml.strip():
        actions = ET.fromstring(override.actions_xml.strip())
        el.append(actions)
    else:
        ET.SubElement(el, "Actions")
    return el


def _serialize_display_rule(rule: RibbonDisplayRule) -> ET.Element:
    el = ET.Element("DisplayRule")
    el.set("Id", rule.id)
    if rule.custom_rule is not None:
        el.append(_serialize_custom_rule(rule.custom_rule))
    return el


def _serialize_enable_rule(rule: RibbonEnableRule) -> ET.Element:
    el = ET.Element("EnableRule")
    el.set("Id", rule.id)
    if rule.custom_rule is not None:
        el.append(_serialize_custom_rule(rule.custom_rule))
    return el


def _serialize_custom_rule(cr: RibbonCustomRule) -> ET.Element:
    el = ET.Element("CustomRule")
    el.set("FunctionName", cr.function_name)
    el.set("Library", cr.library if cr.library.startswith("$") else f"$webresource:{cr.library}")
    el.set("Default", "true" if cr.default else "false")
    for p in cr.params:
        ET.SubElement(el, "CrmParameter").set("Value", p)
    return el


def _serialize_loclabel(loc: RibbonLocLabel) -> ET.Element:
    el = ET.Element("LocLabel")
    el.set("Id", loc.id)
    titles = ET.SubElement(el, "Titles")
    for lang, text in loc.titles.items():
        t = ET.SubElement(titles, "Title")
        t.set("languagecode", str(lang))
        t.set("description", text)
    return el


# ============================================================ parse


def parse_ribbondiff(xml: str) -> RibbonDefinition:
    """Parse a ``<RibbonDiffXml>`` fragment into a :class:`RibbonDefinition` (for reverse)."""
    root = ET.fromstring(xml)
    buttons: list[RibbonButton] = []
    commands: list[RibbonCommand] = []
    hide_oobs: list[RibbonHideOob] = []
    command_overrides: list[RibbonCommandOverride] = []
    for ca in root.findall("CustomActions/CustomAction"):
        btn_el = ca.find("CommandUIDefinition/Button")
        if btn_el is not None:
            buttons.append(_parse_button(ca, btn_el))
    for hide in root.findall("CustomActions/HideCustomAction"):
        hide_oobs.append(RibbonHideOob(
            oob_command_id=hide.get("Location", ""),
            method="hide_custom_action",
            attrs=dict(hide.attrib),
        ))
    for cd in root.findall("CommandDefinitions/CommandDefinition"):
        cid = cd.get("Id", "")
        dr_ids = [d.get("Id", "") for d in cd.findall("DisplayRules/DisplayRule")]
        er_ids = [e.get("Id", "") for e in cd.findall("EnableRules/EnableRule")]
        # detect hide-override (Mscrm.HideOnModern + Mscrm.ShowOnlyOnModern, empty Actions)
        if "Mscrm.HideOnModern" in dr_ids and "Mscrm.ShowOnlyOnModern" in dr_ids and cid.startswith("Mscrm."):
            hide_oobs.append(RibbonHideOob(oob_command_id=cid, method="command_override", attrs=dict(cd.attrib)))
            continue
        # detect "customise" override (OOB Mscrm.* command overridden to preserve rules + add CustomRule)
        if cid.startswith("Mscrm."):
            actions_el = cd.find("Actions")
            actions_xml = ET.tostring(actions_el, encoding="unicode") if actions_el is not None else ""
            command_overrides.append(RibbonCommandOverride(
                oob_command_id=cid,
                preserve_display_rules=[r for r in dr_ids if r.startswith("Mscrm.")],
                preserve_enable_rules=[r for r in er_ids if r.startswith("Mscrm.")],
                added_rule_ids=[r for r in er_ids if not r.startswith("Mscrm.")],
                actions_xml=actions_xml,
                attrs=dict(cd.attrib),
            ))
            continue
        commands.append(_parse_command(cd))
    display_rules = [_parse_display_rule(d) for d in root.findall("RuleDefinitions/DisplayRules/DisplayRule")]
    enable_rules = [_parse_enable_rule(e) for e in root.findall("RuleDefinitions/EnableRules/EnableRule")]
    loclabels = [_parse_loclabel(loc) for loc in root.findall("LocLabels/LocLabel")]
    return RibbonDefinition(
        entity=None, buttons=buttons, commands=commands, display_rules=display_rules,
        enable_rules=enable_rules, hide_oobs=hide_oobs, command_overrides=command_overrides, loclabels=loclabels,
    )


def _strip_loclabel(val: Optional[str]) -> str:
    if val and val.startswith("$LocLabels:"):
        return val[len("$LocLabels:"):]
    return val or ""


def _parse_button(ca: ET.Element, btn_el: ET.Element) -> RibbonButton:
    scope = RibbonScope.Application
    loc = ca.get("Location", "")
    for s in RibbonScope:
        if loc.startswith(f"Mscrm.{s.value}."):
            scope = s
            break
    return RibbonButton(
        id=(btn_el.get("Id", "") or "").removesuffix(".Button"),
        scope=scope,
        command=btn_el.get("Command", ""),
        sequence=int(btn_el.get("Sequence", "10") or 10),
        label_loclabel_id=_strip_loclabel(btn_el.get("LabelText")),
        tooltip_loclabel_id=_strip_loclabel(btn_el.get("ToolTipDescription")),
        template_alias=btn_el.get("TemplateAlias", "o1"),
        image16=_strip_webresource(btn_el.get("Image16by16")),
        image32=_strip_webresource(btn_el.get("Image32by32")),
        attrs=dict(ca.attrib),
    )


def _strip_webresource(val: Optional[str]) -> str:
    if val and val.startswith("$webresource:"):
        return val[len("$webresource:"):]
    return val or ""


def _parse_command(cd: ET.Element) -> RibbonCommand:
    js = cd.find("Actions/JavaScriptFunction")
    params = [p.get("Value", "") for p in cd.findall("Actions/JavaScriptFunction/CrmParameter")]
    return RibbonCommand(
        id=cd.get("Id", ""),
        function_name=js.get("FunctionName", "") if js is not None else "",
        library=_strip_webresource(js.get("Library")) if js is not None else "",
        params=params,
        enable_rules=[e.get("Id", "") for e in cd.findall("EnableRules/EnableRule")],
        display_rules=[d.get("Id", "") for d in cd.findall("DisplayRules/DisplayRule")],
        attrs=dict(cd.attrib),
    )


def _parse_display_rule(el: ET.Element) -> RibbonDisplayRule:
    cr = el.find("CustomRule")
    return RibbonDisplayRule(id=el.get("Id", ""), custom_rule=_parse_custom_rule(cr) if cr is not None else None,
                             attrs=dict(el.attrib))


def _parse_enable_rule(el: ET.Element) -> RibbonEnableRule:
    cr = el.find("CustomRule")
    return RibbonEnableRule(id=el.get("Id", ""), custom_rule=_parse_custom_rule(cr) if cr is not None else None,
                            attrs=dict(el.attrib))


def _parse_custom_rule(el: ET.Element) -> RibbonCustomRule:
    return RibbonCustomRule(
        function_name=el.get("FunctionName", ""),
        library=_strip_webresource(el.get("Library")),
        default=(el.get("Default", "false").lower() == "true"),
        params=[p.get("Value", "") for p in el.findall("CrmParameter")],
        attrs=dict(el.attrib),
    )


def _parse_loclabel(el: ET.Element) -> RibbonLocLabel:
    titles: dict[int, str] = {}
    for t in el.findall("Titles/Title"):
        try:
            titles[int(t.get("languagecode", "0"))] = t.get("description", "")
        except ValueError:
            pass
    return RibbonLocLabel(id=el.get("Id", ""), titles=titles)


# ============================================================ builders (copy-on-write)


def _clone(ribbon: RibbonDefinition) -> RibbonDefinition:
    return copy.deepcopy(ribbon)


def new_ribbon(entity: Optional[str] = None) -> RibbonDefinition:
    """Scaffold an empty ribbon definition. ``entity=None`` for the application (global) ribbon."""
    return RibbonDefinition(entity=entity)


def add_loclabel(ribbon: RibbonDefinition, loclabel_id: str, titles: Union[str, dict[int, str]]) -> RibbonDefinition:
    """Add a localized label. ``titles`` is a string (default language) or languagecode->text dict."""
    ribbon = _clone(ribbon)
    if isinstance(titles, str):
        titles = {DEFAULT_LANGUAGE: titles}
    ribbon.loclabels.append(RibbonLocLabel(id=loclabel_id, titles=dict(titles)))
    return ribbon


def add_command(
    ribbon: RibbonDefinition,
    command_id: str,
    *,
    function_name: str,
    library: str,
    params: Optional[list[str]] = None,
) -> RibbonDefinition:
    """Add a command whose <Actions> call ``function_name`` in ``library`` ($webresource:...)."""
    ribbon = _clone(ribbon)
    ribbon.commands.append(
        RibbonCommand(id=command_id, function_name=function_name, library=library,
                      params=list(params or ["PrimaryControl"]))
    )
    return ribbon


def add_button(
    ribbon: RibbonDefinition,
    button_id: str,
    *,
    scope: RibbonScope,
    label: Union[str, dict[int, str]],
    library: str,
    on_click_fn: Optional[str] = None,
    command: Optional[str] = None,
    tooltip: Optional[Union[str, dict[int, str]]] = None,
    sequence: int = 10,
    area: Optional[str] = None,
    image16: Optional[str] = None,
    image32: Optional[str] = None,
    show_fn: Optional[str] = None,
    enable_fn: Optional[str] = None,
    params: Optional[list[str]] = None,
    rule_params: Optional[list[str]] = None,
) -> RibbonDefinition:
    """Add a fully-wired button: label LocLabel + (auto) command + (optional) CustomRule show/enable rules.

    Either pass an existing ``command`` id, or ``on_click_fn`` (auto-creates ``{button_id}.Command``).
    ``show_fn``/``enable_fn`` (JS function names in ``library``) auto-create ``<CustomRule>``-based EnableRules
    and wire them into the command — the project-wide "show/hide via CustomRule" rule.

    ``params`` / ``rule_params`` override the ``<CrmParameter Value>`` list for the click handler / the
    CustomRules; default is scope-aware (Form→``PrimaryControl``=formContext, Grid→``SelectedControl``=gridContext).
    The JS receives them POSITIONALLY in declaration order — see the dv-ribbon-python skill's
    "ribbon JS 参数接收" table.

    ``area`` (default None) picks a sensible existing GROUP for the scope (Form→``MainTab.Save``,
    HomepageGrid/SubGrid→``MainTab.Management``, Application→``GlobalTab.New``); override to place the
    button in a different real group (e.g. ``MainTab.Actions``). The Location is
    ``Mscrm.{scope}.{entity}.{area}.Controls._children`` — a real group is required for the button to render.
    """
    ribbon = _clone(ribbon)  # ONE clone; mutate this object only (no intermediate clones below)
    area = area or DEFAULT_AREA_BY_SCOPE[scope]
    default_params = _default_crm_params(scope)
    click_params = list(params) if params is not None else default_params
    cmd_id = command or f"{button_id}.Command"
    cmd = next((c for c in ribbon.commands if c.id == cmd_id), None)
    if cmd is None:
        cmd = RibbonCommand(id=cmd_id, function_name=on_click_fn or "", library=library,
                            params=(click_params if on_click_fn else []))
        ribbon.commands.append(cmd)
    # label + tooltip loclabels (mutate this ribbon directly)
    label_titles = {DEFAULT_LANGUAGE: label} if isinstance(label, str) else dict(label)
    label_id = f"{button_id}.LabelText"
    ribbon.loclabels.append(RibbonLocLabel(id=label_id, titles=label_titles))
    tooltip_id = ""
    if tooltip is not None:
        tip_titles = {DEFAULT_LANGUAGE: tooltip} if isinstance(tooltip, str) else dict(tooltip)
        tooltip_id = f"{button_id}.ToolTip"
        ribbon.loclabels.append(RibbonLocLabel(id=tooltip_id, titles=tip_titles))
    # JS-controlled visibility/enable via CustomRule. Per MS Learn, <CustomRule> is documented ONLY under
    # <EnableRule> (the <DisplayRule> enumeration does not include it), and in the command bar disabled==hidden
    # — so BOTH show_fn (visibility) and enable_fn produce EnableRule+CustomRule. Default is fail-CLOSED for
    # custom buttons (hide if JS fails to load).
    rule_p = list(rule_params) if rule_params is not None else default_params
    if show_fn:
        rule_id = f"{button_id}.ShowRule"
        ribbon.enable_rules.append(RibbonEnableRule(
            id=rule_id,
            custom_rule=RibbonCustomRule(function_name=show_fn, library=library, default=False, params=rule_p),
        ))
        if rule_id not in cmd.enable_rules:
            cmd.enable_rules.append(rule_id)
    if enable_fn:
        rule_id = f"{button_id}.EnableRule"
        ribbon.enable_rules.append(RibbonEnableRule(
            id=rule_id,
            custom_rule=RibbonCustomRule(function_name=enable_fn, library=library, default=False, params=rule_p),
        ))
        if rule_id not in cmd.enable_rules:
            cmd.enable_rules.append(rule_id)
    ribbon.buttons.append(RibbonButton(
        id=button_id, scope=scope, command=cmd_id, sequence=sequence,
        label_loclabel_id=label_id, tooltip_loclabel_id=tooltip_id, area=area, image16=image16, image32=image32,
    ))
    return ribbon


def hide_oob(ribbon: RibbonDefinition, oob_command_id: str, *, method: str = "command_override") -> RibbonDefinition:
    """Hide/override an OOB button. ``method`` = ``command_override`` (reversible, default) or
    ``hide_custom_action`` (sticky)."""
    ribbon = _clone(ribbon)
    ribbon.hide_oobs.append(RibbonHideOob(oob_command_id=oob_command_id, method=method))
    return ribbon


def _customise_rule_base(oob_command_id: str) -> str:
    """A non-``Mscrm.``-prefixed base id for an OOB command's added rules.

    ``Mscrm.Form.new_fpformsmoke.Deactivate`` -> ``new_fpformsmoke.Deactivate`` (drops the ``Mscrm.`` + scope
    prefix). Non-Mscrm prefix keeps added rules distinguishable from preserved OOB rules on parse.
    """
    parts = oob_command_id.split(".")
    return ".".join(parts[2:]) if len(parts) > 2 else oob_command_id.replace("Mscrm.", "")


def customise_command(
    ribbon: RibbonDefinition,
    oob_command_id: str,
    *,
    library: str,
    show_fn: Optional[str] = None,
    enable_fn: Optional[str] = None,
    preserve_display_rules: Optional[list[str]] = None,
    preserve_enable_rules: Optional[list[str]] = None,
    actions_xml: str = "",
    rule_params: Optional[list[str]] = None,
) -> RibbonDefinition:
    """Override an OOB command the Ribbon Workbench "Customise Command" way: PRESERVE its rules + ADD a
    ``<CustomRule>`` so the button hides/disables CONDITIONALLY on data state (JS returns bool).

    Unlike :func:`hide_oob` (force-hide by nuking the command's rules), this keeps the OOB command's original
    behaviour when the JS says "show/enable", and only hides/disables it under the condition you encode.

    - ``show_fn``/``enable_fn``: JS function names in ``library``. ``show_fn`` true=show / false=hide;
      ``enable_fn`` true=enable / false=disable. **Both emit ``EnableRule``+``<CustomRule>``** (per MS Learn,
      ``<CustomRule>`` is documented only under ``<EnableRule>``; the command bar treats disabled as hidden, so
      an EnableRule controls visibility). **Default is fail-OPEN (``Default="true"``)** for OOB commands — if
      the JS fails to load, the OOB button keeps its normal behaviour (do not accidentally hide a working
      button). This differs from :func:`add_button` (fail-closed) on purpose.
    - ``preserve_display_rules``/``preserve_enable_rules``: the OOB rule ids to keep. ``None`` looks up
      :data:`OOB_COMMAND_RULES` by the command suffix (e.g. ``Deactivate``); pass explicitly for unseeded
      commands. ⚠️ The tool cannot read the compiled ribbon, so confirm completeness in RW — a missing rule
      changes behaviour.
    - ``actions_xml``: the OOB command's original ``<Actions>…</Actions>`` (paste from RW). The override
      REPLACES the OOB ``<CommandDefinition>``, so to keep the click working you MUST supply this; ``""``
      emits empty ``<Actions/>`` (verify the click still fires).
    """
    ribbon = _clone(ribbon)
    suffix = oob_command_id.rsplit(".", 1)[-1]
    disp_default, en_default = OOB_COMMAND_RULES.get(suffix, ([], []))
    preserve_display_rules = list(preserve_display_rules if preserve_display_rules is not None else disp_default)
    preserve_enable_rules = list(preserve_enable_rules if preserve_enable_rules is not None else en_default)
    base = _customise_rule_base(oob_command_id)
    params = list(rule_params or ["PrimaryControl"])
    added_rule_ids: list[str] = []
    # Per MS Learn <CustomRule> is documented ONLY under <EnableRule> (command bar: disabled==hidden), so both
    # show_fn (visibility) and enable_fn produce EnableRule+CustomRule. Default is fail-OPEN for OOB commands.
    if show_fn:
        rid = f"{base}.ShowRule"
        ribbon.enable_rules.append(RibbonEnableRule(
            id=rid,
            custom_rule=RibbonCustomRule(function_name=show_fn, library=library, default=True, params=params),
        ))
        added_rule_ids.append(rid)
    if enable_fn:
        rid = f"{base}.EnableRule"
        ribbon.enable_rules.append(RibbonEnableRule(
            id=rid,
            custom_rule=RibbonCustomRule(function_name=enable_fn, library=library, default=True, params=params),
        ))
        added_rule_ids.append(rid)
    ribbon.command_overrides.append(RibbonCommandOverride(
        oob_command_id=oob_command_id,
        preserve_display_rules=preserve_display_rules,
        preserve_enable_rules=preserve_enable_rules,
        added_rule_ids=added_rule_ids,
        actions_xml=actions_xml,
    ))
    return ribbon
