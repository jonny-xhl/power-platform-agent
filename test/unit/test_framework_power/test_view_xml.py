"""Unit tests for framework_power.view_xml (parse/serialize/builders, Phase 6)."""

import pytest

import framework_power.view_xml as vx
from framework_power import QueryType, View, ViewCondition, ViewFilter

pytestmark = pytest.mark.unit

# Real-shape Public view (mirrors dev new_fpformsmoke "Active" view).
FETCH = (
    '<fetch version="1.0" mapping="logical" savedqueryid="abc">'
    '<entity name="new_fpformsmoke">'
    '<attribute name="new_fpformsmokeid" /><attribute name="new_name" /><attribute name="createdon" />'
    '<order attribute="new_name" descending="false" />'
    '<filter type="and"><condition attribute="statecode" operator="eq" value="0" /></filter>'
    '</entity></fetch>'
)
LAYOUT = (
    '<grid name="resultset" object="11076" jump="new_name" select="1" icon="1" preview="1">'
    '<row name="result" id="new_fpformsmokeid">'
    '<cell name="new_name" width="300" /><cell name="createdon" width="125" />'
    '</row></grid>'
)
# QuickFind-style: two sibling top-level filters (one nested or + isquickfindfields) + an `in` condition.
FETCH_QF = (
    '<fetch version="1.0" mapping="logical"><entity name="new_fpformsmoke">'
    '<attribute name="new_fpformsmokeid" /><attribute name="new_name" />'
    '<order attribute="new_name" descending="false" />'
    '<filter type="and"><condition attribute="statecode" operator="eq" value="0" />'
    '<filter type="or" isquickfindfields="1"><condition attribute="new_name" operator="like" value="{0}" /></filter>'
    '</filter>'
    '<filter type="and"><condition attribute="new_category" operator="in">'
    '<value>1</value><value>2</value></condition></filter>'
    '</entity></fetch>'
)


def _view(fetch, layout):
    return View(name="X", entity="new_fpformsmoke", query_type=QueryType.Public, **vx.parse_view(fetch, layout))


# ----------------------------------------------------------------- round-trip


def test_round_trip_lossless():
    v1 = _view(FETCH, LAYOUT)
    v2 = View(name="X", entity="new_fpformsmoke", query_type=QueryType.Public,
              **vx.parse_view(vx.to_fetchxml(v1), vx.to_layoutxml(v1)))
    assert v1 == v2


def test_parse_captures_structure():
    v = _view(FETCH, LAYOUT)
    assert [(c.name, c.width) for c in v.columns] == [("new_name", 300), ("createdon", 125)]
    assert v.primary_id == "new_fpformsmokeid"
    assert v.object_type_code == 11076
    assert v.orders[0].attribute == "new_name" and v.orders[0].descending is False
    assert v.filters[0].filter_type == "and"
    cond = v.filters[0].conditions[0]
    assert (cond.attribute, cond.operator, cond.value) == ("statecode", "eq", "0")
    assert v.grid_attrs["jump"] == "new_name" and v.row_attrs["name"] == "result"
    assert v.fetch_attrs.get("savedqueryid") == "abc"


def test_round_trip_multifilter_nested_multivalue():
    v1 = _view(FETCH_QF, LAYOUT)
    v2 = View(name="X", entity="new_fpformsmoke", query_type=QueryType.Public,
              **vx.parse_view(vx.to_fetchxml(v1), vx.to_layoutxml(v1)))
    assert v1 == v2
    assert len(v1.filters) == 2  # two sibling top-level filters
    nested = v1.filters[0].filters  # the or-subfilter
    assert nested and nested[0].filter_type == "or" and nested[0].attrs.get("isquickfindfields") == "1"
    in_cond = v1.filters[1].conditions[0]
    assert in_cond.operator == "in" and in_cond.values == ["1", "2"]


# ----------------------------------------------------------------- builders


def test_new_view_scaffold():
    v = vx.new_view("new_Demo", "new_x", primary_id="new_xid", object_type_code=100)
    assert v.primary_id == "new_xid" and v.object_type_code == 100
    assert v.query_type == QueryType.Public
    assert v.grid_attrs["name"] == "resultset"


def test_add_column_drives_fetch_and_layout():
    v = vx.new_view("new_Demo", "new_x", primary_id="new_xid", object_type_code=100)
    v = vx.add_column(v, "new_name", width=200)
    fx, lx = vx.to_fetchxml(v), vx.to_layoutxml(v)
    assert 'attribute name="new_name"' in fx and 'attribute name="new_xid"' in fx
    assert 'cell name="new_name" width="200"' in lx and 'id="new_xid"' in lx


def test_add_order_and_condition():
    v = vx.new_view("new_Demo", "new_x", primary_id="new_xid", object_type_code=100)
    v = vx.add_column(v, "new_name")
    v = vx.add_order(v, "new_name", descending=True)
    v = vx.add_condition(v, "statecode", "eq", value="0")
    fx = vx.to_fetchxml(v)
    assert 'order attribute="new_name" descending="true"' in fx
    assert 'condition attribute="statecode" operator="eq" value="0"' in fx


def test_add_condition_multivalue():
    v = vx.new_view("new_Demo", "new_x", primary_id="new_xid", object_type_code=100)
    v = vx.add_condition(v, "new_cat", "in", values=["1", "2", "3"])
    fx = vx.to_fetchxml(v)
    assert "<value>1</value>" in fx and "<value>3</value>" in fx


def test_set_filter_replaces():
    v = vx.new_view("new_Demo", "new_x", primary_id="new_xid", object_type_code=100)
    v = vx.add_condition(v, "a", "eq", value="1")
    v = vx.set_filter(v, ViewFilter(filter_type="or", conditions=[ViewCondition("b", "ne", value="2")]))
    assert len(v.filters) == 1 and v.filters[0].filter_type == "or"
    assert v.filters[0].conditions[0].attribute == "b"


def test_add_link_entity_and_dotted_column():
    v = vx.new_view("new_Demo", "new_x", primary_id="new_xid", object_type_code=100)
    v = vx.add_link_entity(v, "contact", "contactid", "primarycontactid", alias="c", attributes=["emailaddress1"])
    v = vx.add_column(v, "c.emailaddress1")
    fx = vx.to_fetchxml(v)
    assert 'link-entity name="contact"' in fx and 'alias="c"' in fx
    assert 'attribute name="emailaddress1"' in fx  # the joined attr


def test_reorder_columns():
    v = vx.new_view("new_Demo", "new_x", primary_id="new_xid", object_type_code=100)
    v = vx.add_column(v, "a")
    v = vx.add_column(v, "b")
    v = vx.reorder_columns(v, ["b", "a"])
    assert [c.name for c in v.columns] == ["b", "a"]


def test_builders_copy_on_write():
    v = vx.new_view("new_Demo", "new_x", primary_id="new_xid", object_type_code=100)
    before = len(v.columns)
    vx.add_column(v, "a")  # ignore return
    assert len(v.columns) == before
