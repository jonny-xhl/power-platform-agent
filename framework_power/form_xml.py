"""FormXml parse / serialize / builder helpers (framework_power Phase 5).

``Form`` is a structured typed model (see ``components.models``); this module is the
FormXml <-> model boundary. It uses ONLY the stdlib ``xml.etree.ElementTree`` (no deps).

Fidelity strategy (verified live on the dev account Main form):
- Layout nodes (FormTab/FormColumn/FormSection/FormRow/FormCell/FormControl) carry a
  full ``attrs`` dict = the COMPLETE attribute set of their FormXml element. The
  serializer emits typed-field defaults then overlays ``attrs``, so reverse -> forward is
  lossless even though FormXml is attribute-heavy (IsUserDefined, layout, labelwidth,
  celllabelposition, colspan, rowspan, showbar, labelid, locklevel, ...).
- Unmodeled ``<form>`` children (ancestor, hiddencontrols, formParameters,
  DisplayConditions, ...) are captured verbatim and split by position (pre/post
  ``<tabs>``) so they are re-emitted in their original positions without reordering.
- ``<InternalHandlers>`` (system) and ``<Handlers>`` (custom) are both captured (an
  ``internal`` flag on FormEventHandler); this tool only ever authors ``<Handlers>``.

Verified-live facts pinned here:
- FormType ints: Main=2, QuickView=6, QuickCreate=7, Card=11.
- Control classids: text {4273EDBD-...}, optionset {3EF39988-...}, lookup
  {270BD3DB-...}, datetime {5B773807-...}, integer {C6D124CA-...}, url {71716B6C-...}.
- <Library name>/<Handler libraryName> == the webresource name; libraryUniqueId and
  handlerUniqueId are brace-wrapped GUIDs (generated here if empty); NO
  libraryUniqueIdRaw is used in this org.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any, Optional
from xml.etree import ElementTree as ET

from .components.models import (
    DEFAULT_CONTROL_CLASSID,
    Form,
    FormCell,
    FormControl,
    FormEvent,
    FormEventHandler,
    FormLabel,
    FormLibrary,
    FormColumn,
    FormRow,
    FormSection,
    FormTab,
)
from .models import AttributeType

# ============================================================ classid map

# Verified-live control classids (env dev account Main form). Brace-wrapped to match
# FormXml. Map from a P1 ``AttributeType`` to the control classid.
FIELD_TYPE_CLASSID: dict[AttributeType, str] = {
    AttributeType.String: "{4273EDBD-AC1D-40D3-9FB2-095C621B552D}",  # text
    AttributeType.Memo: "{B0C872A3-3FA8-4D39-87D3-B3DCDA23B145}",  # multiline
    AttributeType.Integer: "{C6D124CA-7EDA-4a60-AEA9-7FB8D318B68F}",  # whole number
    AttributeType.BigInt: "{C6D124CA-7EDA-4a60-AEA9-7FB8D318B68F}",
    AttributeType.Boolean: "{B737D7BB-52C8-4ebd-8F80-EC5D9C63AC57}",  # two options
    AttributeType.Picklist: "{3EF39988-22BB-4f0b-BBBE-64B5A3748AEE}",  # option set
    AttributeType.DateTime: "{5B773807-9FB2-42db-97C3-7A91EFF8ADFF}",  # datetime
}
URL_CLASSID = "{71716B6C-711E-476c-8AB8-5D11542BFB47}"
LOOKUP_CLASSID = "{270BD3DB-D9AF-4782-9025-509E298DEC0A}"


def classid_for_field(column: Any) -> str:
    """Pick a control classid for a P1 ``Column``/``LookupColumn``.

    ``LookupColumn`` -> lookup classid; ``Column`` with String ``format_name='Url'`` ->
    url classid; otherwise the ``FIELD_TYPE_CLASSID`` map, falling back to the default
    (text) control for unmapped types (Money/Decimal/Double/File — override via the
    explicit ``classid`` arg on :func:`add_field`).
    """
    # LookupColumn is detected by duck-typing (target_entity) to avoid an import cycle.
    if getattr(column, "target_entity", None) is not None:
        return LOOKUP_CLASSID
    ftype = getattr(column, "type", None)
    if ftype == AttributeType.String and str(getattr(column, "format_name", "")).lower() == "url":
        return URL_CLASSID
    if ftype in FIELD_TYPE_CLASSID:
        return FIELD_TYPE_CLASSID[ftype]
    return DEFAULT_CONTROL_CLASSID


# ============================================================ small utils


def _as_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("true", "1", "yes")


def _guid(existing: str = "") -> str:
    """Return a brace-wrapped GUID, reusing ``existing`` if it is non-empty."""
    if existing and existing.strip():
        return existing
    return "{" + str(uuid.uuid4()).lower() + "}"


def _attrs(el: ET.Element) -> dict[str, str]:
    return {k: v for k, v in el.attrib.items()}


def _serialize_children(fragment_xml: str, parent: ET.Element) -> None:
    """Parse a fragment of one or more child elements and append them to ``parent``."""
    fragment_xml = (fragment_xml or "").strip()
    if not fragment_xml:
        return
    wrapper = ET.fromstring("<__extras__>" + fragment_xml + "</__extras__>")
    for child in list(wrapper):
        parent.append(child)


# ============================================================ parse


def parse_formxml(
    xml: str,
) -> tuple[list[FormTab], list[FormLibrary], list[FormEvent], dict[str, str], str, str]:
    """Parse a FormXml string into typed nodes.

    Returns ``(tabs, libraries, events, root_attrs, extras_pre_xml, extras_post_xml)``.
    ``extras_pre`` are unmodeled ``<form>`` children before ``<tabs>`` (ancestor,
    hiddencontrols); ``extras_post`` are those after (formParameters, DisplayConditions).
    The systemform columns (name/objecttypecode/type/description) are NOT in FormXml and
    are filled in by the caller (``components.form.reverse``).
    """
    root = ET.fromstring(xml)
    root_attrs = _attrs(root)
    tabs: list[FormTab] = []
    libraries: list[FormLibrary] = []
    events: list[FormEvent] = []
    extras_pre: list[str] = []
    extras_post: list[str] = []
    saw_tabs = False
    for child in root:
        tag = child.tag
        if tag == "tabs":
            saw_tabs = True
            tabs = [_parse_tab(t) for t in child.findall("tab")]
        elif tag == "formLibraries":
            libraries = [_parse_library(lib) for lib in child.findall("Library")]
        elif tag == "events":
            events = [_parse_event(e) for e in child.findall("event")]
        else:
            piece = ET.tostring(child, encoding="unicode")
            (extras_post if saw_tabs else extras_pre).append(piece)
    return tabs, libraries, events, root_attrs, "".join(extras_pre), "".join(extras_post)


def _parse_labels(el: ET.Element) -> list[FormLabel]:
    out: list[FormLabel] = []
    for lbl_el in el.findall("labels/label"):
        out.append(
            FormLabel(
                description=lbl_el.get("description", ""),
                languagecode=lbl_el.get("languagecode", "2052"),
            )
        )
    return out


def _parse_control(el: ET.Element) -> FormControl:
    params: dict[str, str] = {}
    params_el = el.find("parameters")
    if params_el is not None:
        for p in list(params_el):
            params[p.tag] = (p.text or "") if len(list(p)) == 0 else ET.tostring(p, encoding="unicode")
    datafieldname = el.get("datafieldname", "")
    return FormControl(
        datafieldname=datafieldname,
        classid=el.get("classid", DEFAULT_CONTROL_CLASSID),
        id=el.get("id", datafieldname),
        disabled=_as_bool(el.get("disabled", "false")),
        attrs=_attrs(el),
        parameters=params,
    )


def _parse_cell(el: ET.Element) -> FormCell:
    ctrl_el = el.find("control")
    return FormCell(
        control=_parse_control(ctrl_el) if ctrl_el is not None else None,
        id=el.get("id", ""),
        showlabel=_as_bool(el.get("showlabel", "true")),
        visible=_as_bool(el.get("visible", "true")),
        labels=_parse_labels(el),
        attrs=_attrs(el),
    )


def _parse_row(el: ET.Element) -> FormRow:
    return FormRow(cells=[_parse_cell(c) for c in el.findall("cell")], attrs=_attrs(el))


def _parse_section(el: ET.Element) -> FormSection:
    cols_attr = el.get("columns", "1") or "1"
    return FormSection(
        name=el.get("name", ""),
        id=el.get("id", ""),
        columns=len(cols_attr),
        labels=_parse_labels(el),
        rows=[_parse_row(r) for r in el.findall("rows/row")],
        showlabel=_as_bool(el.get("showlabel", "true")),
        attrs=_attrs(el),
    )


def _parse_column(el: ET.Element) -> FormColumn:
    sections = [_parse_section(s) for s in el.findall("sections/section")]
    return FormColumn(width=el.get("width", "100%"), sections=sections, attrs=_attrs(el))


def _parse_tab(el: ET.Element) -> FormTab:
    columns = [_parse_column(c) for c in el.findall("columns/column")]
    return FormTab(
        name=el.get("name", ""),
        id=el.get("id", ""),
        labels=_parse_labels(el),
        columns=columns or [FormColumn("100%")],
        showlabel=_as_bool(el.get("showlabel", "true")),
        expanded=_as_bool(el.get("expanded", "true")),
        attrs=_attrs(el),
    )


def _parse_library(el: ET.Element) -> FormLibrary:
    return FormLibrary(name=el.get("name", ""), library_unique_id=el.get("libraryUniqueId", ""))


def _parse_handler(el: ET.Element, *, internal: bool) -> FormEventHandler:
    return FormEventHandler(
        function_name=el.get("functionName", ""),
        library_name=el.get("libraryName", ""),
        handler_unique_id=el.get("handlerUniqueId", ""),
        enabled=_as_bool(el.get("enabled", "true")),
        parameters=el.get("parameters", ""),
        pass_execution_context=_as_bool(el.get("passExecutionContext", "false")),
        internal=internal,
        attrs=_attrs(el),
    )


def _parse_event(el: ET.Element) -> FormEvent:
    handlers: list[FormEventHandler] = []
    for h in el.findall("InternalHandlers/Handler"):
        handlers.append(_parse_handler(h, internal=True))
    for h in el.findall("Handlers/Handler"):
        handlers.append(_parse_handler(h, internal=False))
    control_id = el.get("control")
    return FormEvent(
        name=el.get("name", ""),
        active=_as_bool(el.get("active", "false")),
        application=_as_bool(el.get("application", "false")),
        handlers=handlers,
        control_id=control_id if control_id else None,
        attrs=_attrs(el),
    )


# ============================================================ serialize


def to_formxml(form: Form) -> str:
    """Serialize a :class:`Form` back to a FormXml string.

    Required GUIDs (libraryUniqueId, handlerUniqueId, cell/section/tab ids) are
    generated for any empty id. Root attributes and pre/post extras are re-emitted in
    their original positions for a lossless round-trip. Control ids are NOT guid-wrapped
    (by Dataverse convention they equal the field logical name).
    """
    root = ET.Element("form")
    for k, v in form.root_attrs.items():
        root.set(k, v)
    _serialize_children(form.extras_pre_xml, root)
    tabs_el = ET.SubElement(root, "tabs")
    for tab in form.tabs:
        tabs_el.append(_serialize_tab(tab))
    # formLibraries/events are only emitted when non-empty — Dataverse rejects an empty
    # <formLibraries> (0x80048425 "incomplete content, expected 'Library'"). A valid form
    # has either >=1 Library or no <formLibraries> element at all, so omitting when empty
    # is correct and preserves the lossless round-trip.
    if form.libraries:
        libs_el = ET.SubElement(root, "formLibraries")
        for lib in form.libraries:
            lib_el = ET.SubElement(libs_el, "Library")
            lib_el.set("name", lib.name)
            lib_el.set("libraryUniqueId", _guid(lib.library_unique_id))
    if form.events:
        events_el = ET.SubElement(root, "events")
        for ev in form.events:
            events_el.append(_serialize_event(ev))
    _serialize_children(form.extras_post_xml, root)
    return ET.tostring(root, encoding="unicode")


def _serialize_labels(labels: list[FormLabel]) -> ET.Element:
    labels_el = ET.Element("labels")
    for lbl in labels:
        lbl_el = ET.SubElement(labels_el, "label")
        lbl_el.set("description", lbl.description)
        lbl_el.set("languagecode", lbl.languagecode)
    return labels_el


def _serialize_control(control: FormControl) -> ET.Element:
    el = ET.Element("control")
    if control.attrs:
        # reversed: emit the verbatim attribute set (idempotent)
        for k, v in control.attrs.items():
            el.set(k, v)
    else:
        # authored: emit from typed fields
        el.set("id", control.id or control.datafieldname)
        el.set("classid", control.classid)
        el.set("datafieldname", control.datafieldname)
        el.set("disabled", "true" if control.disabled else "false")
    if control.parameters:
        params_el = ET.SubElement(el, "parameters")
        for k, v in control.parameters.items():
            ET.SubElement(params_el, k).text = v
    return el


def _serialize_cell(cell: FormCell) -> ET.Element:
    el = ET.Element("cell")
    if cell.attrs:
        for k, v in cell.attrs.items():
            el.set(k, v)
    else:
        el.set("id", _guid(cell.id))
        el.set("showlabel", "true" if cell.showlabel else "false")
        el.set("visible", "true" if cell.visible else "false")
    if cell.labels:
        el.append(_serialize_labels(cell.labels))
    if cell.control is not None:
        el.append(_serialize_control(cell.control))
    return el


def _serialize_section(section: FormSection) -> ET.Element:
    el = ET.Element("section")
    if section.attrs:
        for k, v in section.attrs.items():
            el.set(k, v)
    else:
        el.set("name", section.name)
        el.set("id", _guid(section.id))
        el.set("columns", "1" * max(section.columns, 1))
        el.set("showlabel", "true" if section.showlabel else "false")
    if section.labels:
        el.append(_serialize_labels(section.labels))
    rows_el = ET.SubElement(el, "rows")
    for row in section.rows:
        row_el = ET.SubElement(rows_el, "row")
        for k, v in row.attrs.items():
            row_el.set(k, v)
        for cell in row.cells:
            row_el.append(_serialize_cell(cell))
    return el


def _serialize_column(column: FormColumn) -> ET.Element:
    el = ET.Element("column")
    if column.attrs:
        for k, v in column.attrs.items():
            el.set(k, v)
    else:
        el.set("width", column.width)
    if column.sections:
        sections_el = ET.SubElement(el, "sections")
        for section in column.sections:
            sections_el.append(_serialize_section(section))
    return el


def _serialize_tab(tab: FormTab) -> ET.Element:
    el = ET.Element("tab")
    if tab.attrs:
        for k, v in tab.attrs.items():
            el.set(k, v)
    else:
        el.set("name", tab.name)
        el.set("id", _guid(tab.id))
        el.set("showlabel", "true" if tab.showlabel else "false")
        el.set("expanded", "true" if tab.expanded else "false")
    if tab.labels:
        el.append(_serialize_labels(tab.labels))
    columns_el = ET.SubElement(el, "columns")
    for column in tab.columns:
        columns_el.append(_serialize_column(column))
    return el


def _serialize_event(event: FormEvent) -> ET.Element:
    el = ET.Element("event")
    if event.attrs:
        for k, v in event.attrs.items():
            el.set(k, v)
    else:
        el.set("name", event.name)
        el.set("application", "true" if event.application else "false")
        el.set("active", "true" if event.active else "false")
        if event.control_id:
            el.set("control", event.control_id)
    internal = [h for h in event.handlers if h.internal]
    custom = [h for h in event.handlers if not h.internal]
    if internal:
        ih = ET.SubElement(el, "InternalHandlers")
        for h in internal:
            ih.append(_serialize_handler(h))
    if custom:
        ch = ET.SubElement(el, "Handlers")
        for h in custom:
            ch.append(_serialize_handler(h))
    return el


def _serialize_handler(h: FormEventHandler) -> ET.Element:
    el = ET.Element("Handler")
    if h.attrs:
        for k, v in h.attrs.items():
            el.set(k, v)
    else:
        el.set("functionName", h.function_name)
        el.set("libraryName", h.library_name)
        el.set("handlerUniqueId", _guid(h.handler_unique_id))
        el.set("enabled", "true" if h.enabled else "false")
        el.set("parameters", h.parameters)
        el.set("passExecutionContext", "true" if h.pass_execution_context else "false")
    return el


# ============================================================ builders
#
# Builders deep-copy the form and return the copy (copy-on-write) so the caller's
# original Form is never aliased. Sections are addressed by name across all columns of
# the target tab (the ``FormTab.sections`` flattened view).


def _clone(form: Form) -> Form:
    return copy.deepcopy(form)


def _find_tab(form: Form, tab_name: str) -> Optional[FormTab]:
    for tab in form.tabs:
        if tab.name == tab_name:
            return tab
    return None


def _find_section(form: Form, tab_name: str, section_name: str) -> Optional[FormSection]:
    tab = _find_tab(form, tab_name)
    if tab is None:
        return None
    for section in tab.sections:  # flattened view across the tab's columns
        if section.name == section_name:
            return section
    return None


def new_form(
    name: str,
    entity: str,
    *,
    form_type: Any = None,
    description: Optional[str] = None,
    languagecode: str = "2052",
) -> Form:
    """Scaffold a minimal new form: one tab + one column + one section + no rows.

    The tab/section names are conventional defaults; rename/extend via the builders.
    ``form_type`` defaults to :class:`FormType.Main`.
    """
    from .components.models import FormType  # local import avoids a module-load cycle

    section = FormSection(
        name="General_Section",
        columns=1,
        labels=[FormLabel("常规信息", languagecode)],
        rows=[],
        showlabel=True,
    )
    tab = FormTab(
        name="GENERAL_TAB",
        labels=[FormLabel("常规", languagecode)],
        columns=[FormColumn("100%", sections=[section])],
    )
    return Form(
        name=name,
        entity=entity,
        form_type=form_type if form_type is not None else FormType.Main,
        description=description,
        tabs=[tab],
    )


def add_tab(
    form: Form,
    name: str,
    labels: Optional[list[FormLabel]] = None,
    *,
    expanded: bool = True,
    showlabel: bool = True,
) -> Form:
    """Append a new tab with one 100% column and no sections."""
    form = _clone(form)
    if _find_tab(form, name) is not None:
        raise ValueError(f"Tab '{name}' already exists on form '{form.name}'.")
    form.tabs.append(
        FormTab(
            name=name,
            labels=list(labels or []),
            columns=[FormColumn("100%", sections=[])],
            expanded=expanded,
            showlabel=showlabel,
        )
    )
    return form


def add_section(
    form: Form,
    tab_name: str,
    name: str,
    labels: Optional[list[FormLabel]] = None,
    *,
    columns: int = 1,
) -> Form:
    """Append a new section to the first column of ``tab_name``."""
    form = _clone(form)
    tab = _find_tab(form, tab_name)
    if tab is None:
        raise ValueError(f"Tab '{tab_name}' not found on form '{form.name}'.")
    if not tab.columns:
        tab.columns.append(FormColumn("100%"))
    tab.columns[0].sections.append(
        FormSection(name=name, labels=list(labels or []), columns=columns, rows=[])
    )
    return form


def add_field(
    form: Form,
    field: Any,
    *,
    tab_name: str,
    section_name: str,
    label: Optional[FormLabel] = None,
    classid: Optional[str] = None,
    control_id: Optional[str] = None,
    enabled: bool = True,
) -> Form:
    """Place a field on the form as a new cell/control in ``section_name``.

    ``field`` is a P1 ``Column``/``LookupColumn``; the control ``datafieldname``/``id``
    default to the field logical name (``schema_name.lower()``), and the ``classid`` is
    picked via :func:`classid_for_field` (override with ``classid``). A new row is added
    when the section's last row is full (cells >= section column count).
    """
    form = _clone(form)
    section = _find_section(form, tab_name, section_name)
    if section is None:
        raise ValueError(
            f"Section '{section_name}' not found in tab '{tab_name}' on form '{form.name}'."
        )
    logical = _field_logical_name(field)
    control = FormControl(
        datafieldname=logical,
        classid=classid or classid_for_field(field),
        id=control_id or logical,
        disabled=not enabled,
    )
    cell = FormCell(control=control, labels=[label] if label else [], visible=True)
    ncols = max(section.columns, 1)
    if section.rows and len(section.rows[-1].cells) < ncols:
        section.rows[-1].cells.append(cell)
    else:
        section.rows.append(FormRow(cells=[cell]))
    return form


def add_library(form: Form, webresource_name: str) -> Form:
    """Add a form library (a JS web-resource dependency) if not already present."""
    form = _clone(form)
    if any(lib.name == webresource_name for lib in form.libraries):
        return form
    form.libraries.append(FormLibrary(name=webresource_name))
    return form


def remove_library(form: Form, webresource_name: str) -> Form:
    form = _clone(form)
    form.libraries = [lib for lib in form.libraries if lib.name != webresource_name]
    return form


def add_event_handler(
    form: Form,
    event_name: str,
    function_name: str,
    library_name: str,
    *,
    control_id: Optional[str] = None,
    pass_execution_context: bool = False,
    parameters: str = "",
    enabled: bool = True,
    active: bool = True,
    application: bool = False,
    add_library_if_missing: bool = True,
) -> Form:
    """Bind a JS handler to a form (onload/onsave) or control (onchange) event.

    For a control-level event pass ``control_id`` (the control id). The handler is added
    to the custom ``<Handlers>`` group (never ``<InternalHandlers>``). By default the
    matching form library is added if missing (the webresource must exist in the env).
    """
    form = _clone(form)
    if add_library_if_missing and not any(lib.name == library_name for lib in form.libraries):
        form.libraries.append(FormLibrary(name=library_name))
    event: Optional[FormEvent] = None
    for ev in form.events:
        if ev.name == event_name and ev.control_id == control_id:
            event = ev
            break
    if event is None:
        event = FormEvent(
            name=event_name,
            active=active,
            application=application,
            handlers=[],
            control_id=control_id,
        )
        form.events.append(event)
    event.handlers.append(
        FormEventHandler(
            function_name=function_name,
            library_name=library_name,
            enabled=enabled,
            parameters=parameters,
            pass_execution_context=pass_execution_context,
            internal=False,
        )
    )
    return form


def remove_event_handler(
    form: Form,
    event_name: str,
    function_name: str,
    library_name: str,
    *,
    control_id: Optional[str] = None,
) -> Form:
    """Remove a custom (non-internal) handler matching function+library+event."""
    form = _clone(form)
    for ev in form.events:
        if ev.name == event_name and ev.control_id == control_id:
            ev.handlers = [
                h
                for h in ev.handlers
                if h.internal
                or not (h.function_name == function_name and h.library_name == library_name)
            ]
    return form


def _field_logical_name(field: Any) -> str:
    schema = getattr(field, "schema_name", None)
    if schema:
        return str(schema).lower()
    name = getattr(field, "name", None)
    if name:
        return str(name).lower()
    raise ValueError("Field has no schema_name/name; cannot derive datafieldname.")
