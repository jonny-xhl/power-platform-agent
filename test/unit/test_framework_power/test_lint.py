"""Unit tests for framework_power.lint (offline convention gate)."""

import pytest

from framework_power import Column, LookupColumn, Relationship, Table
from framework_power.lint import ERROR, WARNING, lint_table
from framework_power.models import AttributeType, Cascade, CascadeConfig, Label, Option, RequiredLevel

pytestmark = pytest.mark.unit


def _good_table() -> Table:
    return Table(
        schema_name="new_ProjectBudget",
        display_name=Label.bilingual("项目预算", "Project Budget"),
        columns=[
            Column("new_Name", AttributeType.String, display_name=Label.bilingual("名称", "Name"),
                   is_primary_name=True, required=RequiredLevel.ApplicationRequired),
            Column("new_Status", AttributeType.Picklist, display_name=Label.bilingual("状态", "Status"),
                   options=[Option(1, Label.bilingual("草稿", "Draft")), Option(2, Label.bilingual("已批准", "Approved"))]),
        ],
        relationships=[
            Relationship(schema_name="new_ProjectBudget_Account", referenced_entity="account",
                         referencing_entity="new_projectbudget",
                         lookup=LookupColumn("new_AccountId", Label.bilingual("客户", "Account"), target_entity="account"),
                         cascade=CascadeConfig(delete=Cascade.RemoveLink)),
        ],
    )


def _errors(table: Table) -> list[str]:
    return [i.message for i in lint_table(table) if i.severity == ERROR]


def _warnings(table: Table) -> list[str]:
    return [i.message for i in lint_table(table) if i.severity == WARNING]


def test_good_table_no_errors():
    assert _errors(_good_table()) == []


def test_no_string_column_is_error():
    t = Table(schema_name="new_X", display_name=Label.zh("X"),
              columns=[Column("new_Amount", AttributeType.Money, display_name=Label.zh("金额"))])
    assert any("primary name" in m for m in _errors(t))


def test_duplicate_columns_is_error():
    t = Table(schema_name="new_X", display_name=Label.zh("X"),
              columns=[Column("new_Name", AttributeType.String, display_name=Label.zh("名")),
                       Column("new_Name", AttributeType.String, display_name=Label.zh("名2"))])
    assert any("Duplicate column" in m for m in _errors(t))


def test_duplicate_option_values_is_error():
    t = Table(schema_name="new_X", display_name=Label.zh("X"),
              columns=[Column("new_Name", AttributeType.String, display_name=Label.zh("名")),
                       Column("new_Status", AttributeType.Picklist, display_name=Label.zh("状态"),
                              options=[Option(1, Label.zh("一")), Option(1, Label.zh("二"))])])
    assert any("duplicate option" in m for m in _errors(t))


def test_duplicate_relationship_is_error():
    t = Table(
        schema_name="new_X", display_name=Label.zh("X"),
        columns=[Column("new_Name", AttributeType.String, display_name=Label.zh("名"))],
        relationships=[
            Relationship(schema_name="new_X_Account", referenced_entity="account", referencing_entity="new_x",
                         lookup=LookupColumn("new_AccountId", Label.zh("客户"), target_entity="account")),
            Relationship(schema_name="new_X_Account", referenced_entity="account", referencing_entity="new_x",
                         lookup=LookupColumn("new_AccountId2", Label.zh("客户"), target_entity="account")),
        ],
    )
    assert any("Duplicate relationship" in m for m in _errors(t))


def test_lowercase_name_is_warning():
    t = Table(schema_name="new_project_budget", display_name=Label.zh("X"),
              columns=[Column("new_name", AttributeType.String, display_name=Label.zh("名"))])
    warns = _warnings(t)
    assert any("PascalCase" in m for m in warns)


def test_relationship_missing_prefix_is_warning():
    t = Table(
        schema_name="new_X", display_name=Label.zh("X"),
        columns=[Column("new_Name", AttributeType.String, display_name=Label.zh("名"))],
        relationships=[
            Relationship(schema_name="X_Account", referenced_entity="account", referencing_entity="new_x",
                         lookup=LookupColumn("new_AccountId", Label.zh("客户"), target_entity="account")),
        ],
    )
    assert any("publisher prefix" in m for m in _warnings(t))


def test_onetomany_without_lookup_is_error():
    t = Table(
        schema_name="new_X", display_name=Label.zh("X"),
        columns=[Column("new_Name", AttributeType.String, display_name=Label.zh("名"))],
        relationships=[
            Relationship(schema_name="new_X_Account", referenced_entity="account", referencing_entity="new_x"),
        ],
    )
    assert any("requires a lookup" in m for m in _errors(t))


def test_lookup_target_mismatch_is_warning():
    t = Table(
        schema_name="new_X", display_name=Label.zh("X"),
        columns=[Column("new_Name", AttributeType.String, display_name=Label.zh("名"))],
        relationships=[
            Relationship(schema_name="new_X_Account", referenced_entity="account", referencing_entity="new_x",
                         lookup=LookupColumn("new_ContactId", Label.zh("联系"), target_entity="contact")),
        ],
    )
    assert any("lookup target" in m for m in _warnings(t))
