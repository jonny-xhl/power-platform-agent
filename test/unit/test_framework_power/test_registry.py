"""Unit tests for framework_power.registry."""

from pathlib import Path

import pytest

from framework_power import Column, LookupColumn, Relationship, Table
from framework_power.models import AttributeType, Label, RequiredLevel
from framework_power.registry import Definition, deploy_order, discover_definitions, get_definition

pytestmark = pytest.mark.unit

PROJECT_ROOT = Path(__file__).parents[3]
DEFS_DIR = PROJECT_ROOT / "metadata_py" / "tables"


def test_discover_finds_canonical_definition():
    defs = discover_definitions(str(DEFS_DIR))
    assert "new_projectbudget" in defs
    assert defs["new_projectbudget"].table.schema_name == "new_ProjectBudget"


def test_get_definition_roundtrip():
    defn = get_definition("new_projectbudget", str(DEFS_DIR))
    assert defn.name == "new_projectbudget"
    assert defn.table.logical_name == "new_projectbudget"


def test_get_definition_missing_raises():
    with pytest.raises(KeyError):
        get_definition("does_not_exist", str(DEFS_DIR))


def _defn(name: str, table: Table) -> Definition:
    return Definition(name=name, table=table, source=Path(f"{name}.py"))


def test_deploy_order_referenced_first():
    # new_child references new_parent (1:N) -> parent must deploy first.
    parent = Table(schema_name="new_Parent", display_name=Label.zh("父"),
                   columns=[Column("new_Name", AttributeType.String, display_name=Label.zh("名"))])
    child = Table(
        schema_name="new_Child", display_name=Label.zh("子"),
        columns=[Column("new_Name", AttributeType.String, display_name=Label.zh("名"))],
        relationships=[
            Relationship(schema_name="new_Parent_Child", referenced_entity="new_parent",
                         referencing_entity="new_child",
                         lookup=LookupColumn("new_ParentId", Label.zh("父"), target_entity="new_parent")),
        ],
    )
    defs = {"new_child": _defn("new_child", child), "new_parent": _defn("new_parent", parent)}
    order = deploy_order(defs)
    assert order.index("new_parent") < order.index("new_child")


def test_deploy_order_unknown_reference_no_constraint():
    # Referencing a standard entity (account) imposes no ordering among registered defs.
    a = Table(schema_name="new_A", display_name=Label.zh("A"),
              columns=[Column("new_Name", AttributeType.String, display_name=Label.zh("名"))],
              relationships=[
                  Relationship(schema_name="new_A_Account", referenced_entity="account",
                               referencing_entity="new_a",
                               lookup=LookupColumn("new_AccountId", Label.zh("客户"), target_entity="account")),
              ])
    defs = {"new_a": _defn("new_a", a)}
    assert deploy_order(defs) == ["new_a"]
