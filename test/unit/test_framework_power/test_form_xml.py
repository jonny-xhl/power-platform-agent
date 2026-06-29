"""Unit tests for framework_power.form_xml (parse/serialize/builders, Phase 5)."""

import pytest

import framework_power.form_xml as fx
from framework_power import Form, FormType, Label
from framework_power.models import AttributeType, Column, LookupColumn

pytestmark = pytest.mark.unit


# Representative real-shape Main FormXml (tabs/column/section/row/cells/controls,
# formLibraries, events with InternalHandlers + Handlers, plus pre/post extras).
SAMPLE_XML = (
    '<form showImage="true" headerdensity="HighWithControls">'
    '<ancestor id="{aaa}" />'
    '<hiddencontrols><data id="x" datafieldname="x" '
    'classid="{5546E6CD-394C-4bee-94A8-4425E17EF6C6}" /></hiddencontrols>'
    '<tabs><tab name="T1" id="{t1}" IsUserDefined="0" showlabel="true" expanded="true" locklevel="0">'
    '<labels><label description="信息" languagecode="2052" /></labels>'
    '<columns><column width="67%"><sections><section name="S1" showlabel="true" showbar="false" '
    'id="{s1}" layout="varwidth" columns="11" labelwidth="115" celllabelposition="Left" locklevel="0" '
    'celllabelalignment="Left"><labels><label description="基本信息" languagecode="2052" /></labels>'
    '<rows><row><cell id="{c1}" showlabel="true" colspan="1" rowspan="1" locklevel="0">'
    '<labels><label description="名称" languagecode="2052" /></labels>'
    '<control id="name" classid="{4273EDBD-AC1D-40d3-9FB2-095C621B552D}" datafieldname="name" disabled="false" />'
    '</cell></row></rows></section></sections></column></columns></tab></tabs>'
    '<formLibraries><Library name="new_lib.js" libraryUniqueId="{lib1}" /></formLibraries>'
    '<events><event name="onload" application="true" active="true">'
    '<InternalHandlers><Handler functionName="Sys.fn" libraryName="sys.js" '
    'handlerUniqueId="{ih1}" enabled="true" /></InternalHandlers>'
    '<Handlers><Handler functionName="Onload" libraryName="new_lib.js" '
    'handlerUniqueId="{h1}" enabled="true" parameters="" passExecutionContext="true" /></Handlers>'
    '</event></events>'
    '<formParameters /></form>'
)


def _parse(xml: str) -> Form:
    tabs, libs, events, ra, pre, post = fx.parse_formxml(xml)
    return Form(name="X", entity="account", form_type=FormType.Main, tabs=tabs, libraries=libs,
                events=events, root_attrs=ra, extras_pre_xml=pre, extras_post_xml=post)


# ----------------------------------------------------------------- round-trip


def test_round_trip_lossless():
    f1 = _parse(SAMPLE_XML)
    f2 = _parse(fx.to_formxml(f1))
    assert f1 == f2  # parse -> serialize -> parse is identity on a real-shape form


def test_parse_captures_structure():
    f = _parse(SAMPLE_XML)
    assert len(f.tabs) == 1
    section = f.tabs[0].sections[0]
    assert section.name == "S1"
    assert section.columns == 2  # columns="11" -> 2 columns
    assert section.rows[0].cells[0].control.datafieldname == "name"
    assert f.libraries[0].name == "new_lib.js"
    onload = [ev for ev in f.events if ev.name == "onload"][0]
    internal = [h for h in onload.handlers if h.internal]
    custom = [h for h in onload.handlers if not h.internal]
    assert internal and internal[0].function_name == "Sys.fn"
    assert custom and custom[0].function_name == "Onload"
    assert custom[0].pass_execution_context is True
    assert "hiddencontrols" in f.extras_pre_xml  # pre-tabs extra
    assert "formParameters" in f.extras_post_xml  # post-tabs extra
    assert f.root_attrs.get("showImage") == "true"


# ----------------------------------------------------------------- classid map


def test_classid_for_field_types():
    ftc = fx.FIELD_TYPE_CLASSID
    assert fx.classid_for_field(Column("new_A", AttributeType.String, Label.zh("a"))) == ftc[AttributeType.String]
    assert fx.classid_for_field(Column("new_B", AttributeType.Picklist, Label.zh("b"))) == ftc[AttributeType.Picklist]
    # URL-format string -> url classid
    url_col = Column("new_U", AttributeType.String, Label.zh("u"), format_name="Url")
    assert fx.classid_for_field(url_col) == fx.URL_CLASSID
    # lookup -> lookup classid
    assert fx.classid_for_field(LookupColumn("new_L", Label.zh("l"), target_entity="team")) == fx.LOOKUP_CLASSID


# ----------------------------------------------------------------- builders


def test_new_form_scaffold():
    f = fx.new_form("new_Order Main", "new_order")
    assert f.entity == "new_order"
    assert f.form_type == FormType.Main
    assert len(f.tabs) == 1 and len(f.tabs[0].sections) == 1


def test_add_field_uses_logical_name_and_classid():
    f = fx.new_form("new_X", "new_x")
    f = fx.add_field(f, Column("new_Code", AttributeType.String, Label.zh("代码")),
                     tab_name="GENERAL_TAB", section_name="General_Section")
    xml = fx.to_formxml(f)
    assert 'datafieldname="new_code"' in xml and 'id="new_code"' in xml
    assert fx.FIELD_TYPE_CLASSID[AttributeType.String] in xml


def test_add_library_idempotent():
    f = fx.new_form("new_X", "new_x")
    f = fx.add_library(f, "new_/js/a.js")
    f = fx.add_library(f, "new_/js/a.js")  # duplicate -> no-op
    assert len(f.libraries) == 1


def test_add_event_handler_form_level():
    f = fx.new_form("new_X", "new_x")
    f = fx.add_event_handler(f, "onload", "Onload", "new_/js/a.js", pass_execution_context=True)
    assert any(lib.name == "new_/js/a.js" for lib in f.libraries)  # library auto-added
    onload = [ev for ev in f.events if ev.name == "onload"][0]
    h = [x for x in onload.handlers if not x.internal][0]
    assert h.function_name == "Onload" and h.pass_execution_context is True
    # serialize + re-parse keeps the handler
    f2 = _parse(fx.to_formxml(f))
    h2 = [x for ev in f2.events if ev.name == "onload" for x in ev.handlers if not x.internal][0]
    assert h2.function_name == "Onload"


def test_add_event_handler_control_level():
    f = fx.new_form("new_X", "new_x")
    f = fx.add_event_handler(f, "onchange", "onChange", "new_/js/a.js", control_id="new_code")
    ev = [e for e in f.events if e.name == "onchange"][0]
    assert ev.control_id == "new_code"


def test_remove_event_handler():
    f = fx.new_form("new_X", "new_x")
    f = fx.add_event_handler(f, "onload", "Onload", "new_/js/a.js")
    f = fx.remove_event_handler(f, "onload", "Onload", "new_/js/a.js")
    custom = [h for ev in f.events if ev.name == "onload" for h in ev.handlers if not h.internal]
    assert custom == []


def test_builders_are_copy_on_write():
    f = fx.new_form("new_X", "new_x")
    before = len(f.libraries)
    fx.add_library(f, "new_/js/a.js")  # ignore return -> original not mutated
    assert len(f.libraries) == before


def test_add_field_unknown_section_raises():
    f = fx.new_form("new_X", "new_x")
    with pytest.raises(ValueError):
        fx.add_field(f, Column("new_C", AttributeType.String, Label.zh("c")),
                     tab_name="GENERAL_TAB", section_name="nope")
