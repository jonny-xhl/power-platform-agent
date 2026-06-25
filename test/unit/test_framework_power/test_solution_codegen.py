"""Unit tests for framework_power.solution_codegen (round-trip)."""

import pytest

from framework_power.components.models import ComponentRef, Publisher, Solution
from framework_power.solution_codegen import solution_to_python_source

pytestmark = pytest.mark.unit


def _round_trip(sol: Solution) -> Solution:
    src = solution_to_python_source(sol)
    compile(src, "sol.py", "exec")
    ns: dict = {}
    exec(src, ns)
    return ns["SOLUTION"]


def test_round_trip_publisher_tables_refs():
    sol = Solution(
        unique_name="new_Core",
        friendly_name="Core",
        version="1.2.0.0",
        description="core",
        publisher=Publisher(name="Pub", display_name="Pub", prefix="new", description="d"),
        tables=["new_budget", "contact"],
        refs=[ComponentRef(type="61", object_id="wr-guid"), ComponentRef(type="table", name="x")],
    )
    assert _round_trip(sol) == sol


def test_round_trip_publisher_key_default_version():
    sol = Solution(unique_name="new_Core", friendly_name="Core", publisher_key="default")
    sol2 = _round_trip(sol)
    assert sol2 == sol
    assert sol2.version == "1.0.0.0"  # default omitted on emit, restored on import


def test_emit_uses_publisher_key_when_no_inline_publisher():
    sol = Solution(unique_name="new_Core", friendly_name="Core", publisher_key="default")
    src = solution_to_python_source(sol)
    assert "publisher_key='default'" in src
    assert "publisher=Publisher(" not in src


def test_emit_includes_tables_and_refs_lists():
    sol = Solution(
        unique_name="new_Core",
        friendly_name="Core",
        tables=["a", "b"],
        refs=[ComponentRef(type="61", object_id="g")],
    )
    src = solution_to_python_source(sol)
    assert "tables=['a', 'b']" in src
    assert "ComponentRef(" in src


def test_round_trip_with_optionsets_and_webresources():
    from framework_power import (
        GlobalOptionSet,
        Label,
        Option,
        WebResource,
        WebResourceType,
    )

    sol = Solution(
        unique_name="new_Core",
        friendly_name="Core",
        publisher_key="default",
        tables=["new_budget"],
        optionsets=[
            GlobalOptionSet(
                name="new_Priority",
                display_name=Label.bilingual("优先级", "Priority"),
                options=[Option(1, Label.en("Low"))],
            )
        ],
        webresources=[
            WebResource(
                name="new_/js/x.js", display_name="X", content="YmFzZTY0",
                webresource_type=WebResourceType.JScript,
            )
        ],
    )
    sol2 = _round_trip(sol)
    assert sol2 == sol
    assert sol2.optionsets[0].name == "new_Priority"
    assert sol2.webresources[0].webresource_type == WebResourceType.JScript


def test_emit_imports_only_needed_names():
    sol = Solution(unique_name="new_Core", friendly_name="Core", tables=["a"])
    src = solution_to_python_source(sol)
    # no inline publisher/refs/typed lists -> only Solution imported
    assert "from framework_power import (\n    Solution,\n)" in src


def test_round_trip_with_forms_and_views():
    from framework_power import Form, FormType, QueryType, View

    sol = Solution(
        unique_name="new_Core",
        friendly_name="Core",
        tables=["new_budget"],
        forms=[
            Form(
                name="new_Budget Main", entity="new_budget",
                form_xml="<forms><form/></forms>", form_type=FormType.Main,
            )
        ],
        views=[
            View(
                name="new_Active", entity="new_budget", fetch_xml="<fetch/>",
                layout_xml="<grid/>", query_type=QueryType.Public, is_default=True,
            )
        ],
    )
    sol2 = _round_trip(sol)
    assert sol2 == sol
    assert sol2.forms[0].form_xml == "<forms><form/></forms>"
    assert sol2.views[0].query_type == QueryType.Public
