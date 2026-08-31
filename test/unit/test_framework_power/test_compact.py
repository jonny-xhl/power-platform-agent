# -*- coding: utf-8 -*-
"""Unit tests for compact-attrs reverse codegen (components/compact.py)."""

import dataclasses

import pytest

from framework_power.components.compact import compact_attrs, normalize
from framework_power.components.models import (
    FormCell,
    FormControl,
    ViewColumn,
)

pytestmark = pytest.mark.unit

VIEW_FETCH = (
    '<fetch version="1.0" mapping="logical"><entity name="new_x">'
    '<attribute name="new_xid" /><attribute name="new_name" />'
    '<order attribute="new_name" descending="false" />'
    '<filter type="and"><condition attribute="statecode" operator="eq" value="0" /></filter>'
    '</entity></fetch>'
)
VIEW_LAYOUT = (
    '<grid name="resultset" object="100" jump="new_name" select="1" icon="1" preview="1">'
    '<row name="result" id="new_xid"><cell name="new_name" width="200" /></row></grid>'
)


def test_compact_attrs_drops_exact_mirror_set():
    ctrl = FormControl(
        datafieldname="new_name",
        classid="{4273EDBD-AC1D-40D3-9FB2-095C621B552D}",
        id="new_name",
        disabled=False,
        attrs={
            "id": "new_name",
            "classid": "{4273EDBD-AC1D-40D3-9FB2-095C621B552D}",
            "datafieldname": "new_name",
            "disabled": "false",
        },
    )
    assert compact_attrs(ctrl) == {}


def test_compact_attrs_keeps_extra_keys_verbatim():
    cell = FormCell(
        id="{abc}",
        showlabel=True,
        visible=True,
        attrs={"id": "{abc}", "showlabel": "true", "visible": "true", "locklevel": "0"},
    )
    assert compact_attrs(cell) == {
        "id": "{abc}", "showlabel": "true", "visible": "true", "locklevel": "0"
    }


def test_compact_attrs_keeps_missing_mirror_keys():
    """Fallback would ADD datafieldname="" — attrs lacking it must stay verbatim."""
    ctrl = FormControl(
        datafieldname="",
        classid="{E7A81278-8635-4d9e-8D4D-59480B391C5B}",
        id="subgrid_lines",
        disabled=False,
        attrs={"id": "subgrid_lines", "classid": "{E7A81278-8635-4d9e-8D4D-59480B391C5B}"},
    )
    assert compact_attrs(ctrl) == {
        "id": "subgrid_lines", "classid": "{E7A81278-8635-4d9e-8D4D-59480B391C5B}"
    }


def test_compact_attrs_value_mismatch_keeps_verbatim():
    col = ViewColumn(
        name="new_name", width=200, disable_sorting=False, hidden=False,
        attrs={"name": "new_name", "width": "300"},
    )
    assert compact_attrs(col) == {"name": "new_name", "width": "300"}


def test_view_codegen_compact_round_trip_byte_identical():
    from framework_power.components import view as view_component
    from framework_power.view_xml import parse_view, to_fetchxml, to_layoutxml

    fields = parse_view(VIEW_FETCH, VIEW_LAYOUT)
    from framework_power.components.models import QueryType, View

    model = View(
        name="V", entity="new_x", primary_id=fields["primary_id"],
        object_type_code=fields["object_type_code"], query_type=QueryType.Public,
        columns=fields["columns"], filters=fields["filters"], orders=fields["orders"],
        link_entities=fields["link_entities"], fetch_attrs=fields["fetch_attrs"],
        grid_attrs=fields["grid_attrs"], row_attrs=fields["row_attrs"],
        extra_attributes=fields["extra_attributes"],
    )
    import framework_power

    ns: dict = {name: getattr(framework_power, name) for name in view_component.CODEGEN_IMPORTS}
    loaded = eval(compile(view_component.codegen(model), "<gen>", "eval"), ns)
    assert to_fetchxml(loaded) == to_fetchxml(model)
    assert to_layoutxml(loaded) == to_layoutxml(model)
    # the compact file must actually be smaller than the verbatim-attrs one
    def _verbatim(value, indent=0):  # noqa: E306
        pad, inner = "    " * indent, "    " * (indent + 1)
        if isinstance(value, bool):
            return "True" if value else "False"
        if isinstance(value, (int, str)) or value is None:
            return repr(value)
        if isinstance(value, list):
            if not value:
                return "[]"
            return "[\n" + ",\n".join(inner + _verbatim(v, indent + 1) for v in value) + "\n" + pad + "]"
        if isinstance(value, dict):
            if not value:
                return "{}"
            return "{\n" + ",\n".join(
                inner + repr(k) + ": " + _verbatim(v, indent + 1) for k, v in value.items()
            ) + "\n" + pad + "}"
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            parts = [inner + f.name + "=" + _verbatim(getattr(value, f.name), indent + 1)
                     for f in dataclasses.fields(value)]
            return type(value).__name__ + "(\n" + ",\n".join(parts) + "\n" + pad + ")"
        return repr(value)

    compact_src = view_component.codegen(model)
    verbatim_src = _verbatim(model)
    assert len(compact_src) < len(verbatim_src)
    # normalized compact model equals normalized verbatim model (deploy diff contract)
    assert normalize(loaded) == normalize(model)
