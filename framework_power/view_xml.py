"""FetchXml + LayoutXml parse / serialize / builder helpers (framework_power Phase 6).

A view (SavedQuery) carries TWO paired XML payloads — FetchXml (query) and LayoutXml (grid) — kept
1:1 (every layout ``<cell>`` matches a fetch attribute; cell order = display order). ``View`` is a
structured typed model (see ``components.models``); this module is the XML <-> model boundary. It uses
ONLY the stdlib ``xml.etree.ElementTree`` (no deps).

Fidelity strategy (mirrors Phase-5 ``form_xml.py``, verified live on dev new_fpformsmoke):
- Each node carries a full ``attrs`` dict = the COMPLETE attribute set of its element. The serializer is
  attrs-FIRST: a reversed node (populated attrs) emits verbatim -> parse->serialize->parse is idempotent;
  an authored node (empty attrs) emits typed defaults.
- ``View.fetch_attrs`` / ``grid_attrs`` / ``row_attrs`` hold the remaining root-attribute sets verbatim
  (fetch version/mapping/savedqueryid/output-format; grid name/jump/select/icon/preview; row name) so a
  reverse snapshot round-trips lossless. ``object_type_code`` (-> ``<grid object=>``) and ``primary_id``
  (-> ``<row id=>``) are first-class typed fields.
- Condition ``<value>`` children (for in/between) are modeled as ``ViewCondition.values`` and always
  re-emitted; operators are passed through as strings (no enum).

Verified-live facts pinned here:
- querytype: Public=0, AdvancedFind=1, Associated=2, QuickFind=4, Lookup=64.
- LayoutXml ``<grid object="11076">`` uses the INTEGER ObjectTypeCode (lookup via
  ``get_entity_metadata.ObjectTypeCode``); ``<row id>`` = primary-id attribute (also a fetch ``<attribute>``);
  cells = non-primary columns in display order.
- Auto-created views' fetch root attrs: ``version="1.0" mapping="logical" savedqueryid="..."`` (no
  output-format/distinct); these vary per view, hence captured via ``fetch_attrs``.
"""

from __future__ import annotations

import copy
from typing import Any, Optional
from xml.etree import ElementTree as ET

from .components.models import (
    View,
    ViewColumn,
    ViewCondition,
    ViewFilter,
    ViewLinkEntity,
    ViewOrder,
)

# ============================================================ parse


def parse_view(fetch_xml: str, layout_xml: str) -> dict[str, Any]:
    """Parse a FetchXml + LayoutXml pair into the structured-view field values.

    Returns a dict with keys: ``columns, filter, orders, link_entities, primary_id,
    object_type_code, fetch_attrs, grid_attrs, row_attrs, extra_attributes``. The caller
    (``components.view.reverse``) fills in name/entity/query_type/description from the record.
    """
    columns, primary_id, object_type_code, grid_attrs, row_attrs = _parse_layoutxml(layout_xml or "")
    fetch_attrs, orders, filters, link_entities, fetch_top_attrs = _parse_fetchxml(fetch_xml or "")
    column_names = {c.name for c in columns}
    extras = [a for a in fetch_top_attrs if a and a != primary_id and a not in column_names]
    return {
        "columns": columns,
        "filters": filters,
        "orders": orders,
        "link_entities": link_entities,
        "primary_id": primary_id,
        "object_type_code": object_type_code,
        "fetch_attrs": fetch_attrs,
        "grid_attrs": grid_attrs,
        "row_attrs": row_attrs,
        "extra_attributes": extras,
    }


def _parse_layoutxml(xml: str):
    if not xml.strip():
        return [], "", 0, {}, {}
    grid = ET.fromstring(xml)
    grid_attrs = {k: v for k, v in grid.attrib.items() if k != "object"}
    try:
        object_type_code = int(grid.attrib.get("object", "0"))
    except ValueError:
        object_type_code = 0
    row = grid.find("row")
    if row is not None:
        row_attrs = {k: v for k, v in row.attrib.items() if k != "id"}
        primary_id = row.attrib.get("id", "")
        columns = [_parse_column(c) for c in row.findall("cell")]
    else:
        row_attrs, primary_id, columns = {}, "", []
    return columns, primary_id, object_type_code, grid_attrs, row_attrs


def _parse_fetchxml(xml: str):
    if not xml.strip():
        return {}, [], None, [], []
    root = ET.fromstring(xml)
    fetch_attrs = dict(root.attrib)
    entity = root.find("entity")
    if entity is None:
        return fetch_attrs, [], None, [], []
    orders = [_parse_order(o) for o in entity.findall("order")]
    # An <entity> may have MULTIPLE sibling <filter> elements (implicitly ANDed) — capture all.
    filters = [_parse_filter(f) for f in entity.findall("filter")]
    link_entities = [_parse_link_entity(le) for le in entity.findall("link-entity")]
    fetch_top_attrs = [a.attrib.get("name", "") for a in entity.findall("attribute")]
    return fetch_attrs, orders, filters, link_entities, fetch_top_attrs


def _parse_column(el: ET.Element) -> ViewColumn:
    attrs = dict(el.attrib)
    try:
        width = int(attrs.get("width", "150"))
    except ValueError:
        width = 150
    return ViewColumn(
        name=attrs.get("name", ""),
        width=width,
        disable_sorting=attrs.get("disableSorting") == "1",
        hidden=attrs.get("ishidden") == "1",
        attrs=attrs,
    )


def _parse_order(el: ET.Element) -> ViewOrder:
    attrs = dict(el.attrib)
    return ViewOrder(
        attribute=attrs.get("attribute", ""),
        descending=attrs.get("descending") == "true",
        attrs=attrs,
    )


def _parse_condition(el: ET.Element) -> ViewCondition:
    attrs = dict(el.attrib)
    values = [(v.text or "") for v in el.findall("value")]
    return ViewCondition(
        attribute=attrs.get("attribute", ""),
        operator=attrs.get("operator", ""),
        value=attrs.get("value"),
        values=values,
        attrs=attrs,
    )


def _parse_filter(el: ET.Element) -> ViewFilter:
    flt = ViewFilter(filter_type=el.attrib.get("type", "and"), attrs=dict(el.attrib))
    for c in el.findall("condition"):
        flt.conditions.append(_parse_condition(c))
    for sub in el.findall("filter"):
        flt.filters.append(_parse_filter(sub))
    return flt


def _parse_link_entity(el: ET.Element) -> ViewLinkEntity:
    attrs = dict(el.attrib)
    filt_el = el.find("filter")
    return ViewLinkEntity(
        name=attrs.get("name", ""),
        from_attr=attrs.get("from", ""),
        to_attr=attrs.get("to", ""),
        link_type=attrs.get("link-type", "inner"),
        alias=attrs.get("alias", ""),
        attributes=[a.attrib.get("name", "") for a in el.findall("attribute")],
        filter=_parse_filter(filt_el) if filt_el is not None else None,
        attrs=attrs,
    )


# ============================================================ serialize


def to_fetchxml(view: View) -> str:
    """Serialize the query half of a :class:`View` to FetchXml."""
    root = ET.Element("fetch")
    fa = dict(view.fetch_attrs) if view.fetch_attrs else {"version": "1.0", "mapping": "logical"}
    for k, v in fa.items():
        root.set(k, v)
    entity = ET.SubElement(root, "entity")
    entity.set("name", view.entity)
    # attributes: primary_id, then non-dotted columns, then extras (dotted columns live on link-entities)
    seen: set[str] = set()
    for name in [view.primary_id] + [c.name for c in view.columns if "." not in c.name] + list(view.extra_attributes):
        if name and name not in seen:
            ET.SubElement(entity, "attribute").set("name", name)
            seen.add(name)
    for order in view.orders:
        entity.append(_serialize_order(order))
    for flt in view.filters:
        entity.append(_serialize_filter(flt))
    for le in view.link_entities:
        entity.append(_serialize_link_entity(le))
    return ET.tostring(root, encoding="unicode")


def to_layoutxml(view: View) -> str:
    """Serialize the grid half of a :class:`View` to LayoutXml."""
    grid = ET.Element("grid")
    grid.set("object", str(view.object_type_code))
    for k, v in view.grid_attrs.items():
        if k != "object":
            grid.set(k, v)
    row = ET.SubElement(grid, "row")
    row.set("id", view.primary_id)
    for k, v in view.row_attrs.items():
        if k != "id":
            row.set(k, v)
    for col in view.columns:
        row.append(_serialize_cell(col))
    return ET.tostring(grid, encoding="unicode")


def _serialize_order(order: ViewOrder) -> ET.Element:
    el = ET.Element("order")
    if order.attrs:
        for k, v in order.attrs.items():
            el.set(k, v)
    else:
        el.set("attribute", order.attribute)
        el.set("descending", "true" if order.descending else "false")
    return el


def _serialize_condition(c: ViewCondition) -> ET.Element:
    el = ET.Element("condition")
    if c.attrs:
        for k, v in c.attrs.items():
            el.set(k, v)
    else:
        el.set("attribute", c.attribute)
        el.set("operator", c.operator)
        if c.value is not None:
            el.set("value", c.value)
    # <value> children (in/between) are always re-emitted from the model
    for v in c.values:
        ET.SubElement(el, "value").text = v
    return el


def _serialize_filter(flt: ViewFilter) -> ET.Element:
    el = ET.Element("filter")
    if flt.attrs:
        for k, v in flt.attrs.items():
            el.set(k, v)
    else:
        el.set("type", flt.filter_type)
    for c in flt.conditions:
        el.append(_serialize_condition(c))
    for sub in flt.filters:
        el.append(_serialize_filter(sub))
    return el


def _serialize_link_entity(le: ViewLinkEntity) -> ET.Element:
    el = ET.Element("link-entity")
    if le.attrs:
        for k, v in le.attrs.items():
            el.set(k, v)
    else:
        el.set("name", le.name)
        if le.from_attr:
            el.set("from", le.from_attr)
        if le.to_attr:
            el.set("to", le.to_attr)
        el.set("link-type", le.link_type)
        if le.alias:
            el.set("alias", le.alias)
    for attr in le.attributes:
        a = ET.SubElement(el, "attribute")
        a.set("name", attr)
    if le.filter is not None:
        el.append(_serialize_filter(le.filter))
    return el


def _serialize_cell(col: ViewColumn) -> ET.Element:
    el = ET.Element("cell")
    if col.attrs:
        for k, v in col.attrs.items():
            el.set(k, v)
    else:
        el.set("name", col.name)
        el.set("width", str(col.width))
        if col.disable_sorting:
            el.set("disableSorting", "1")
        if col.hidden:
            el.set("ishidden", "1")
    return el


# ============================================================ builders (copy-on-write)


def _clone(view: View) -> View:
    return copy.deepcopy(view)


def new_view(
    name: str,
    entity: str,
    *,
    primary_id: str,
    object_type_code: int,
    query_type: Any = None,
    description: Optional[str] = None,
) -> View:
    """Scaffold a minimal new Public view with conventional grid/row/fetch defaults.

    ``primary_id`` and ``object_type_code`` are required (the row id and the integer ObjectTypeCode).
    Use :func:`framework_power.client.get_object_type_code` to look up the latter for a custom table.
    """
    from .components.models import QueryType  # local import avoids a module-load cycle

    return View(
        name=name,
        entity=entity,
        primary_id=primary_id,
        object_type_code=object_type_code,
        query_type=query_type if query_type is not None else QueryType.Public,
        description=description,
        fetch_attrs={"version": "1.0", "mapping": "logical"},
        grid_attrs={"name": "resultset", "jump": "", "select": "1", "icon": "1", "preview": "1"},
        row_attrs={"name": "result"},
    )


def add_column(view: View, name: str, *, width: int = 150, disable_sorting: bool = False) -> View:
    """Append a display column (drives both a fetch ``<attribute>`` and a layout ``<cell>``).

    For a joined column use ``name="alias.attr"`` and ensure a matching :class:`ViewLinkEntity`
    (via :func:`add_link_entity`) declares that alias + attribute.
    """
    view = _clone(view)
    if any(c.name == name for c in view.columns):
        return view
    view.columns.append(ViewColumn(name=name, width=width, disable_sorting=disable_sorting))
    return view


def remove_column(view: View, name: str) -> View:
    view = _clone(view)
    view.columns = [c for c in view.columns if c.name != name]
    return view


def reorder_columns(view: View, names_in_order: list[str]) -> View:
    """Reorder display columns to match ``names_in_order`` (must list every current column)."""
    view = _clone(view)
    by_name = {c.name: c for c in view.columns}
    if set(by_name) != set(names_in_order):
        raise ValueError(
            f"reorder_columns: names {set(names_in_order)} must equal current columns {set(by_name)}"
        )
    view.columns = [by_name[n] for n in names_in_order]
    return view


def add_order(view: View, attribute: str, *, descending: bool = False) -> View:
    view = _clone(view)
    view.orders = [o for o in view.orders if o.attribute != attribute]
    view.orders.append(ViewOrder(attribute=attribute, descending=descending))
    return view


def set_filter(view: View, flt: ViewFilter) -> View:
    view = _clone(view)
    view.filters = [flt]
    return view


def add_condition(
    view: View,
    attribute: str,
    operator: str,
    *,
    value: Optional[str] = None,
    values: Optional[list[str]] = None,
    filter_type: str = "and",
) -> View:
    """Add a condition; creates a top-level filter (``filter_type``) if the view has none."""
    view = _clone(view)
    if not view.filters:
        view.filters = [ViewFilter(filter_type=filter_type)]
    view.filters[-1].conditions.append(
        ViewCondition(attribute=attribute, operator=operator, value=value, values=list(values or []))
    )
    return view


def add_link_entity(
    view: View,
    name: str,
    from_attr: str,
    to_attr: str,
    *,
    alias: str,
    link_type: str = "inner",
    attributes: Optional[list[str]] = None,
) -> View:
    """Add a joined entity (its attributes are referenced by ``alias.attr`` column names)."""
    view = _clone(view)
    if any(le.alias == alias for le in view.link_entities):
        return view
    view.link_entities.append(
        ViewLinkEntity(
            name=name, from_attr=from_attr, to_attr=to_attr, alias=alias,
            link_type=link_type, attributes=list(attributes or []),
        )
    )
    return view
