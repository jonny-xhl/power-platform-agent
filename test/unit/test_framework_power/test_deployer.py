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
            "add_solution_component": [],
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

    def add_solution_component(
        self,
        solution: str,
        code: int,
        oid: str,
        add_required: bool = False,
        do_not_include_subcomponents: bool = False,
    ) -> dict[str, Any]:
        self.calls["add_solution_component"].append(
            (solution, code, oid, do_not_include_subcomponents)
        )
        return {"status": "added"}

    def remove_solution_component(self, solution: str, code: int, oid: str) -> dict[str, Any]:
        self.calls.setdefault("remove_solution_component", []).append((solution, code, oid))
        return {"status": "removed"}


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


def test_deploy_table_adds_to_solution_when_given():
    """deploy_table(solution=...) self-adds the entity (code 1) — Phase 9 uniformity.

    Default mode adds the entity WITH sub-components (do_not_include_subcomponents=False)."""
    client = FakeClient(table_exists=False)
    result = deploy_table(client, _basic_table(), config=NO_DELAY, solution="new_MainSoln")
    assert result["entity"]["action"] == "created"
    assert result["solution"]["name"] == "new_MainSoln"
    assert result["solution"]["mode"] == "subcomponents"
    assert client.calls["add_solution_component"] == [("new_MainSoln", 1, "fake-id", False)]


def test_deploy_table_solution_clean_adds_shell_and_custom_fields():
    """solution_clean=True adds the entity SHELL + only its custom attributes (code 2) — both
    plain columns AND lookup columns from custom relationships — so the solution holds only
    self-authored content (no OOB sub-components)."""
    attrs = [
        {"LogicalName": "new_name", "MetadataId": "mid-name"},
        {"LogicalName": "new_amount", "MetadataId": "mid-amount"},
        {"LogicalName": "new_accountid", "MetadataId": "mid-accountid"},
    ]
    client = FakeClient(table_exists=False, existing_attributes=attrs)
    result = deploy_table(
        client, _basic_table(), config=NO_DELAY, solution="new_MainSoln", solution_clean=True
    )
    sol = result["solution"]
    assert sol["mode"] == "clean"
    # entity added as a SHELL (do_not_include_subcomponents=True)
    assert ("new_MainSoln", 1, "fake-id", True) in client.calls["add_solution_component"]
    # plain columns + the relationship lookup, all added individually as attributes (code 2)
    member_attrs = {m["attribute"]: m["action"] for m in sol["members"]}
    assert member_attrs == {
        "new_Name": "added",
        "new_Amount": "added",
        "new_AccountId": "added",
    }
    assert {c[1] for c in client.calls["add_solution_component"]} == {1, 2}


def test_deploy_table_no_solution_unchanged():
    """Without solution=, deploy_table behaves exactly as before (no solution key, no add)."""
    client = FakeClient(table_exists=False)
    result = deploy_table(client, _basic_table(), config=NO_DELAY)
    assert "solution" not in result
    assert client.calls["add_solution_component"] == []


# ---------------------------------------------------------------------------
# Incremental (--fields) deploy tests
# ---------------------------------------------------------------------------


def test_deploy_fields_regular_column_entity_exists():
    """Deploy only one regular column when entity already exists."""
    existing_attrs = [_str_existing("new_name")]  # new_name exists
    client = FakeClient(table_exists=True, existing_attributes=existing_attrs)
    result = deploy_table(
        client, _basic_table(), config=NO_DELAY,
        fields=["new_Amount"],
    )
    # Entity sync skipped in fields mode.
    assert result["entity"]["action"] == "already_exists"
    assert client.calls["update_entity"] == []
    # Only new_Amount is deployed (created since it didn't exist).
    actions = {a["attribute"]: a["action"] for a in result["attributes"]}
    assert "new_Name" not in actions
    assert actions["new_Amount"] == "created"
    assert len(client.calls["create_attribute"]) == 1
    # No relationships deployed.
    assert result["relationships"] == []


def test_deploy_fields_regular_column_entity_not_exists():
    """Entity doesn't exist → empty shell created → only the named fields are deployed."""
    client = FakeClient(table_exists=False)
    result = deploy_table(
        client, _basic_table(), config=NO_DELAY,
        fields=["new_Name"],
    )
    # Entity created as empty shell (no attributes).
    assert result["entity"]["action"] == "created"
    assert result["entity"]["mode"] == "shell"
    create_payload = client.calls["create_entity"][0]
    assert "Attributes" not in create_payload  # empty shell
    # Only new_Name is deployed.
    actions = {a["attribute"]: a["action"] for a in result["attributes"]}
    assert "new_Name" in actions
    assert "new_Amount" not in actions
    # One attribute created independently (not via entity payload).
    assert len(client.calls["create_attribute"]) == 1


def test_deploy_fields_lookup():
    """Deploy a Lookup field via --fields."""
    client = FakeClient(table_exists=True)
    result = deploy_table(
        client, _basic_table(), config=NO_DELAY,
        fields=["new_AccountId"],
    )
    # Entity sync skipped.
    assert result["entity"]["action"] == "already_exists"
    # No regular attributes deployed.
    assert result["attributes"] == []
    # Lookup relationship created.
    assert len(result["relationships"]) == 1
    assert result["relationships"][0]["action"] == "created"
    assert len(client.calls["create_relationship_from_json"]) == 1


def test_deploy_fields_mixed_regular_and_lookup():
    """Deploy both a regular column and a Lookup field in one call."""
    client = FakeClient(table_exists=True)
    result = deploy_table(
        client, _basic_table(), config=NO_DELAY,
        fields=["new_Name", "new_AccountId"],
    )
    # Regular attribute deployed.
    attr_actions = {a["attribute"]: a["action"] for a in result["attributes"]}
    assert attr_actions["new_Name"] == "created"
    assert len(client.calls["create_attribute"]) == 1
    # Lookup relationship deployed.
    assert len(result["relationships"]) == 1
    assert result["relationships"][0]["action"] == "created"
    assert len(client.calls["create_relationship_from_json"]) == 1


def test_deploy_fields_unknown_raises():
    """Unknown field name raises ValueError before any API calls."""
    client = FakeClient(table_exists=True)
    with pytest.raises(ValueError, match="Unknown field"):
        deploy_table(
            client, _basic_table(), config=NO_DELAY,
            fields=["new_BogusField"],
        )
    # No API calls were made.
    assert client.calls["create_attribute"] == []
    assert client.calls["create_relationship_from_json"] == []


def test_deploy_fields_solution_clean_adds_only_named_fields():
    """--solution-clean with --fields adds only the named fields to the solution."""
    attrs = [
        {"LogicalName": "new_name", "MetadataId": "mid-name"},
        {"LogicalName": "new_amount", "MetadataId": "mid-amount"},
    ]
    client = FakeClient(table_exists=True, existing_attributes=attrs)
    result = deploy_table(
        client, _basic_table(), config=NO_DELAY,
        fields=["new_Name"],
        solution="new_MainSoln", solution_clean=True,
    )
    sol = result["solution"]
    assert sol["mode"] == "clean"
    # Only new_Name is added as a solution member.
    member_attrs = {m["attribute"]: m["action"] for m in sol["members"]}
    assert member_attrs == {"new_Name": "added"}
    assert "new_Amount" not in member_attrs


def test_deploy_fields_lookup_already_exists_skipped():
    """Lookup field already present → skipped."""
    rels = [{"SchemaName": "new_ProjectBudget_Account"}]
    client = FakeClient(table_exists=True, existing_relationships=rels)
    result = deploy_table(
        client, _basic_table(), config=NO_DELAY,
        fields=["new_AccountId"],
    )
    assert result["relationships"][0]["action"] == "skipped"
    assert client.calls["create_relationship_from_json"] == []


def test_deploy_fields_idempotent_retry():
    """Re-running --fields after a successful deploy skips everything."""
    existing_attrs = [_str_existing("new_name")]
    client = FakeClient(table_exists=True, existing_attributes=existing_attrs)
    # First run: creates new_Amount.
    result1 = deploy_table(
        client, _basic_table(), config=NO_DELAY,
        fields=["new_Amount"],
    )
    assert result1["attributes"][0]["action"] == "created"
    # Second run: new_Amount now exists → skipped.
    # Simulate it existing now.
    client._existing_attributes = [
        _str_existing("new_name"),
        _money_existing("new_amount"),
    ]
    result2 = deploy_table(
        client, _basic_table(), config=NO_DELAY,
        fields=["new_Amount"],
    )
    assert result2["attributes"][0]["action"] == "skipped"
    # No create_attribute calls on second run.
    assert len(client.calls["create_attribute"]) == 1  # only from first run
