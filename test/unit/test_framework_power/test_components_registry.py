"""Unit tests for framework_power.components registry + table adapter."""

import pytest

from framework_power import Label, Table
from framework_power.components import (
    COMPONENT_DEPLOY_ORDER,
    COMPONENT_TYPES,
    ComponentType,
    component_type_for_code,
)

pytestmark = pytest.mark.unit


def test_table_registered_with_full_handler():
    assert "table" in COMPONENT_TYPES
    t = COMPONENT_TYPES["table"]
    assert isinstance(t, ComponentType)
    assert t.key == "table"
    assert t.solution_component_type == 1
    assert t.deploy_depends_on == ("optionset",)
    for attr in (
        "serialize",
        "deploy",
        "plan",
        "reverse",
        "codegen",
        "exists",
        "resolve_id",
        "lint",
    ):
        assert callable(getattr(t, attr)), attr


def test_component_type_for_code_round_trip():
    assert component_type_for_code(1) == "table"
    assert component_type_for_code(999) is None


def test_deploy_order_covers_all_future_types():
    assert COMPONENT_DEPLOY_ORDER == (
        "optionset",
        "table",
        "webresource",
        "form",
        "view",
        "sitemap",
        "plugin",
    )


def test_table_adapter_resolve_id_and_exists():
    class FakeClient:
        def get_entity_metadata(self, name):
            return {"MetadataId": "meta-123", "LogicalName": name}

        def entity_exists(self, name):
            return True

    t = COMPONENT_TYPES["table"]
    table = Table(schema_name="new_Budget", display_name=Label.en("Budget"))
    assert t.resolve_id(FakeClient(), table) == "meta-123"
    assert t.exists(FakeClient(), table) is True


def test_table_adapter_codegen_emits_source():
    t = COMPONENT_TYPES["table"]
    table = Table(schema_name="new_Budget", display_name=Label.en("Budget"))
    src = t.codegen(table)
    assert "TABLE: Table" in src and "new_Budget" in src
