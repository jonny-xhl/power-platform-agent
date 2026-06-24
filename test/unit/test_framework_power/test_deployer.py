"""Unit tests for framework_power.deployer (uses a fake client, no network)."""

from typing import Any

import pytest

from framework_power import Column, LookupColumn, Relationship, Table, deploy_table
from framework_power.deployer import DeployConfig
from framework_power.models import (
    AttributeType,
    BooleanLabels,
    Cascade,
    CascadeConfig,
    Label,
    Option,
    RequiredLevel,
)
from framework_power.serializer import serialize_label

pytestmark = pytest.mark.unit


NO_DELAY = DeployConfig(
    after_entity_create_delay=0.0,
    between_attributes_delay=0.0,
    between_relationships_delay=0.0,
    sleep=lambda _s: None,
)


class FakeClient:
    """Records calls and returns canned responses for the deployer.

    ``entity_exists`` is name-aware: referenced entities in ``existing_entities``
    (default: the standard ``account``) report True; the deployed table reports
    ``table_exists``.
    """

    def __init__(
        self,
        *,
        table_exists: bool = False,
        existing_entities: set[str] | None = None,
        existing_attributes: list[dict[str, Any]] | None = None,
        existing_relationships: list[dict[str, Any]] | None = None,
    ) -> None:
        self._table_exists = table_exists
        self._existing_entities = set(existing_entities or {"account"})
        self._existing_attributes = existing_attributes or []
        self._existing_relationships = existing_relationships or []
        self.calls: dict[str, list[Any]] = {
            "create_entity": [],
            "update_entity": [],
            "create_attribute": [],
            "update_attribute_by_logical_name": [],
            "create_relationship_from_json": [],
        }

    def entity_exists(self, name: str) -> bool:
        if name in self._existing_entities:
            return True
        return self._table_exists

    def create_entity(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls["create_entity"].append(payload)
        return {"MetadataId": "fake-id", "status": "created"}

    def update_entity(self, name: str, patch: dict[str, Any]) -> dict[str, Any]:
        self.calls["update_entity"].append((name, patch))
        return {"status": "updated"}

    def get_attributes(self, name: str) -> list[dict[str, Any]]:
        return list(self._existing_attributes)

    def create_attribute(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls["create_attribute"].append((name, payload))
        return {"status": "created"}

    def update_attribute_by_logical_name(self, entity: str, attr: str, patch: dict[str, Any]) -> dict[str, Any]:
        self.calls["update_attribute_by_logical_name"].append((entity, attr, patch))
        return {"status": "updated"}

    def get_relationships(self, name: str) -> list[dict[str, Any]]:
        return list(self._existing_relationships)

    def get_entity_metadata(self, name: str) -> dict[str, Any]:
        return {"PrimaryIdAttribute": f"{name}id", "MetadataId": "fake-id"}

    def create_relationship_from_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls["create_relationship_from_json"].append(payload)
        return {"status": "created"}


def _str_existing(name: str, *, max_length: int = 200, display: Label | None = None) -> dict[str, Any]:
    """A realistic existing String attribute JSON that matches the desired defaults."""
    return {
        "LogicalName": name,
        "MaxLength": max_length,
        "FormatName": {"Value": "Text"},
        "RequiredLevel": {"Value": "None"},
        "DisplayName": serialize_label(display or Label.bilingual("名称", "Name")),
    }


def _money_existing(name: str, zh: str = "金额", en: str = "Amount") -> dict[str, Any]:
    return {
        "LogicalName": name,
        "Precision": 2,
        "PrecisionSource": 2,
        "RequiredLevel": {"Value": "None"},
        "DisplayName": serialize_label(Label.bilingual(zh, en)),
    }


def _basic_table() -> Table:
    return Table(
        schema_name="new_ProjectBudget",
        display_name=Label.bilingual("项目预算", "Project Budget"),
        columns=[
            Column("new_Name", AttributeType.String, display_name=Label.bilingual("名称", "Name"),
                   is_primary_name=True, max_length=200),
            Column("new_Amount", AttributeType.Money, display_name=Label.bilingual("金额", "Amount")),
        ],
        relationships=[
            Relationship(
                schema_name="new_ProjectBudget_Account",
                referenced_entity="account",
                referencing_entity="new_projectbudget",
                lookup=LookupColumn("new_AccountId", display_name=Label.bilingual("客户", "Account"), target_entity="account"),
                cascade=CascadeConfig(delete=Cascade.RemoveLink),
            ),
        ],
    )


def test_deploy_creates_entity_and_relationships():
    client = FakeClient(table_exists=False)
    result = deploy_table(client, _basic_table(), config=NO_DELAY)

    assert result["entity"]["action"] == "created"
    assert len(client.calls["create_entity"]) == 1
    # Attributes ride along inside the create payload, so no separate create_attribute calls.
    assert client.calls["create_attribute"] == []
    # Relationship created (referenced 'account' exists by default).
    assert len(client.calls["create_relationship_from_json"]) == 1
    assert result["relationships"][0]["action"] == "created"


def test_deploy_updates_entity_and_syncs_attribute():
    existing_attrs = [_str_existing("new_name")]  # new_name matches -> skipped
    client = FakeClient(table_exists=True, existing_attributes=existing_attrs)
    result = deploy_table(client, _basic_table(), config=NO_DELAY)

    assert result["entity"]["action"] == "updated"
    assert len(client.calls["update_entity"]) == 1
    actions = {a["attribute"]: a["action"] for a in result["attributes"]}
    assert actions["new_Name"] == "skipped"
    assert actions["new_Amount"] == "created"
    assert len(client.calls["create_attribute"]) == 1
    assert client.calls["update_attribute_by_logical_name"] == []


def test_deploy_patches_changed_attribute():
    existing_attrs = [_str_existing("new_name", max_length=100)]  # differs from desired 200
    client = FakeClient(table_exists=True, existing_attributes=existing_attrs)
    result = deploy_table(client, _basic_table(), config=NO_DELAY)

    name_entry = next(a for a in result["attributes"] if a["attribute"] == "new_Name")
    assert name_entry["action"] == "updated"
    assert len(client.calls["update_attribute_by_logical_name"]) == 1
    entity, attr, patch = client.calls["update_attribute_by_logical_name"][0]
    assert entity == "new_projectbudget" and attr == "new_name"
    assert patch["MaxLength"] == 200


def test_deploy_idempotent_noop_on_matching_attributes():
    existing_attrs = [_str_existing("new_name"), _money_existing("new_amount")]
    client = FakeClient(table_exists=True, existing_attributes=existing_attrs)
    deploy_table(client, _basic_table(), config=NO_DELAY)
    assert client.calls["update_attribute_by_logical_name"] == []
    assert client.calls["create_attribute"] == []


def test_deploy_picklist_options_reports_manual_update():
    table = Table(
        schema_name="new_X",
        display_name=Label.zh("X"),
        columns=[
            Column("new_Name", AttributeType.String, display_name=Label.zh("名称")),
            Column("new_Status", AttributeType.Picklist, display_name=Label.zh("状态"),
                   options=[Option(1, Label.zh("草稿")), Option(2, Label.zh("已批准"))]),
        ],
    )
    existing_attrs = [
        _str_existing("new_name", max_length=100, display=Label.zh("名称")),
        {
            "LogicalName": "new_status",
            "RequiredLevel": {"Value": "None"},
            "DisplayName": serialize_label(Label.zh("状态")),
            "OptionSet": {"Options": [{"Value": 1}]},  # differs -> manual update required
        },
    ]
    client = FakeClient(table_exists=True, existing_attributes=existing_attrs)
    result = deploy_table(client, table, config=NO_DELAY)
    status_entry = next(a for a in result["attributes"] if a["attribute"] == "new_Status")
    assert status_entry["action"] == "manual_update_required"
    assert client.calls["update_attribute_by_logical_name"] == []


def test_deploy_relationship_skipped_when_present():
    rels = [{"SchemaName": "new_ProjectBudget_Account"}]
    client = FakeClient(table_exists=False, existing_relationships=rels)
    result = deploy_table(client, _basic_table(), config=NO_DELAY)
    assert result["relationships"][0]["action"] == "skipped"
    assert client.calls["create_relationship_from_json"] == []


def test_deploy_relationship_referenced_entity_missing_fails():
    table = Table(
        schema_name="new_X",
        display_name=Label.zh("X"),
        columns=[Column("new_Name", AttributeType.String, display_name=Label.zh("名称"))],
        relationships=[
            Relationship(
                schema_name="new_X_Ghost",
                referenced_entity="new_ghost",  # not in existing_entities
                referencing_entity="new_x",
                lookup=LookupColumn("new_GhostId", display_name=Label.zh("幽灵"), target_entity="new_ghost"),
            ),
        ],
    )
    client = FakeClient(table_exists=False)
    result = deploy_table(client, table, config=NO_DELAY)
    entry = result["relationships"][0]
    assert entry["action"] == "failed"
    assert "new_ghost" in entry["error"]


def test_deploy_no_string_column_raises():
    table = Table(
        schema_name="new_NoString",
        display_name=Label.zh("无字符串"),
        columns=[Column("new_Amount", AttributeType.Money, display_name=Label.zh("金额"))],
    )
    client = FakeClient(table_exists=False)
    with pytest.raises(ValueError):
        deploy_table(client, table, config=NO_DELAY)


def test_deploy_skips_standard_columns_and_relationships():
    """A reverse-style snapshot: standard (non-prefixed) items are skipped on forward sync."""
    table = Table(
        schema_name="new_X",
        display_name=Label.zh("X"),
        columns=[
            Column("new_Name", AttributeType.String, display_name=Label.zh("名")),  # custom
            Column("firstname", AttributeType.String, display_name=Label.zh("名")),  # standard
        ],
        relationships=[
            Relationship(schema_name="new_X_Account", referenced_entity="account",
                         referencing_entity="new_x",
                         lookup=LookupColumn("new_AccountId", Label.zh("客户"), target_entity="account")),
            Relationship(schema_name="standard_rel", referenced_entity="account",
                         referencing_entity="new_x",
                         lookup=LookupColumn("new_A", Label.zh("x"), target_entity="account")),
        ],
    )
    existing_attrs = [{
        "LogicalName": "new_name", "MaxLength": 100, "FormatName": {"Value": "Text"},
        "RequiredLevel": {"Value": "None"}, "DisplayName": serialize_label(Label.zh("名")),
    }]
    client = FakeClient(table_exists=True, existing_attributes=existing_attrs)
    result = deploy_table(client, table, config=NO_DELAY)

    attr_actions = {a["attribute"]: a["action"] for a in result["attributes"]}
    assert attr_actions["new_Name"] == "skipped"
    assert attr_actions["firstname"] == "skipped_standard"

    rel_actions = {r["relationship"]: r["action"] for r in result["relationships"]}
    assert rel_actions["new_X_Account"] == "created"
    assert rel_actions["standard_rel"] == "skipped_standard"
