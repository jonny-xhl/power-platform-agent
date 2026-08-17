"""Unit tests for framework_power.deployer.plan_table (read-only dry run)."""

from typing import Any

import pytest

from framework_power import Column, Table, plan_table
from framework_power.models import AttributeType, Label, Option
from framework_power.serializer import serialize_label

pytestmark = pytest.mark.unit


class PlanFakeClient:
    def __init__(self, *, exists: bool, attrs=None, rels=None):
        self._exists = exists
        self._attrs = attrs or []
        self._rels = rels or []

    def entity_exists(self, name: str) -> bool:
        return self._exists

    def get_attributes(self, name: str) -> list[dict[str, Any]]:
        return list(self._attrs)

    def get_attribute_metadata(
        self,
        entity: str,
        attr: str,
        *,
        attribute_type: str | None = None,
    ) -> dict[str, Any]:
        for item in self._attrs:
            if item.get("LogicalName") == attr:
                return item
        return {"LogicalName": attr, "OptionSet": {"Options": []}}

    def get_relationships(self, name: str) -> list[dict[str, Any]]:
        return list(self._rels)


def _table() -> Table:
    return Table(
        schema_name="new_ProjectBudget",
        display_name=Label.bilingual("项目预算", "Project Budget"),
        columns=[
            Column("new_Name", AttributeType.String, display_name=Label.bilingual("名称", "Name"), max_length=200),
        ],
    )


def test_plan_entity_missing_all_create():
    client = PlanFakeClient(exists=False)
    plan = plan_table(client, _table())
    assert plan["entity"]["action"] == "would_create"
    assert plan["attributes"][0]["action"] == "would_create"


def test_plan_entity_exists_matching_is_skip():
    existing = [{
        "LogicalName": "new_name", "MaxLength": 200, "FormatName": {"Value": "Text"},
        "RequiredLevel": {"Value": "None"}, "DisplayName": serialize_label(Label.bilingual("名称", "Name")),
    }]
    client = PlanFakeClient(exists=True, attrs=existing)
    plan = plan_table(client, _table())
    assert plan["entity"]["action"] == "would_update"
    assert plan["attributes"][0]["action"] == "would_skip"


def test_plan_entity_exists_changed_is_patch():
    existing = [{
        "LogicalName": "new_name", "MaxLength": 100, "FormatName": {"Value": "Text"},
        "RequiredLevel": {"Value": "None"}, "DisplayName": serialize_label(Label.bilingual("名称", "Name")),
    }]
    client = PlanFakeClient(exists=True, attrs=existing)
    plan = plan_table(client, _table())
    entry = plan["attributes"][0]
    assert entry["action"] == "would_patch"
    assert "MaxLength" in entry["fields"]


def test_plan_picklist_reports_insert_update_and_remote_retention():
    table = Table(
        schema_name="new_X",
        display_name=Label.zh("X"),
        columns=[
            Column(
                "new_Status",
                AttributeType.Picklist,
                display_name=Label.bilingual("状态", "Status"),
                options=[
                    Option(1, Label.bilingual("草稿", "Draft")),
                    Option(2, Label.bilingual("已批准", "Approved")),
                ],
            )
        ],
    )
    existing = [{
        "LogicalName": "new_status",
        "RequiredLevel": {"Value": "None"},
        "DisplayName": serialize_label(Label.bilingual("状态", "Status")),
        "OptionSet": {"Options": [
            {"Value": 1, "Label": serialize_label(Label.bilingual("草案", "Draft"))},
            {"Value": 9, "Label": serialize_label(Label.bilingual("远端", "Remote"))},
        ]},
    }]

    entry = plan_table(PlanFakeClient(exists=True, attrs=existing), table)["attributes"][0]

    assert entry["action"] == "would_update"
    assert entry["options"] == {
        "insert": [2],
        "update": [1],
        "remote_only_retained": [9],
    }


def test_plan_new_attribute_is_create():
    table = Table(
        schema_name="new_ProjectBudget",
        display_name=Label.bilingual("项目预算", "Project Budget"),
        columns=[
            Column("new_Name", AttributeType.String, display_name=Label.bilingual("名称", "Name")),
            Column("new_Amount", AttributeType.Money, display_name=Label.bilingual("金额", "Amount")),
        ],
    )
    existing = [{
        "LogicalName": "new_name", "MaxLength": 100, "FormatName": {"Value": "Text"},
        "RequiredLevel": {"Value": "None"}, "DisplayName": serialize_label(Label.bilingual("名称", "Name")),
    }]
    client = PlanFakeClient(exists=True, attrs=existing)
    plan = plan_table(client, table)
    actions = {a["attribute"]: a["action"] for a in plan["attributes"]}
    assert actions["new_Name"] == "would_skip"
    assert actions["new_Amount"] == "would_create"
