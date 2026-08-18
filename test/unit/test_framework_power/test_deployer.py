"""Unit tests for framework_power.deployer (uses a fake client, no network)."""

from typing import Any

import pytest

from framework_power import Column, LookupColumn, Relationship, Table, deploy_table
from framework_power.client.dataverse_client import DataverseClient
from framework_power.deployer import (
    DeployConfig,
    _referenced_global_optionsets,
    ensure_referenced_optionsets,
)
from framework_power.models import (
    AttributeType,
    Cascade,
    CascadeConfig,
    Label,
    Option,
)
from framework_power.serializer import serialize_label

pytestmark = pytest.mark.unit


NO_DELAY = DeployConfig(
    after_entity_create_delay=0.0,
    between_attributes_delay=0.0,
    between_relationships_delay=0.0,
    sleep=lambda _s: None,
)


class FakeResponse:
    """Small requests.Response substitute for client transport tests."""

    def __init__(self, payload: dict[str, Any] | None = None, status_code: int = 200) -> None:
        self._payload = payload or {}
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = "" if status_code == 204 else "json"
        self.headers: dict[str, str] = {}

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


class RecordingSession:
    """Records typed GET and full-definition PUT requests."""

    def __init__(self, metadata: dict[str, Any]) -> None:
        self.metadata = metadata
        self.get_calls: list[tuple[str, dict[str, Any]]] = []
        self.put_calls: list[tuple[str, dict[str, Any], dict[str, str]]] = []
        self.post_calls: list[tuple[str, dict[str, Any]]] = []
        self.patch_calls: list[Any] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.get_calls.append((url, kwargs))
        return FakeResponse(self.metadata)

    def put(
        self,
        url: str,
        *,
        json: dict[str, Any],
        headers: dict[str, str],
    ) -> FakeResponse:
        self.put_calls.append((url, json, headers))
        return FakeResponse(status_code=204)

    def post(self, url: str, *, json: dict[str, Any]) -> FakeResponse:
        self.post_calls.append((url, json))
        if url.endswith("/InsertOptionValue"):
            return FakeResponse({"NewOptionValue": json["Value"]})
        return FakeResponse(status_code=204)

    def patch(self, url: str, **kwargs: Any) -> FakeResponse:
        self.patch_calls.append((url, kwargs))
        return FakeResponse(status_code=405)


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
        typed_attributes: dict[str, dict[str, Any]] | None = None,
        fail_attribute_update: bool = False,
    ) -> None:
        self._table_exists = table_exists
        self._existing_entities = set(existing_entities or {"account"})
        self._existing_attributes = existing_attributes or []
        self._existing_relationships = existing_relationships or []
        self._typed_attributes = typed_attributes or {}
        self._fail_attribute_update = fail_attribute_update
        self.calls: dict[str, list[Any]] = {
            "create_entity": [],
            "update_entity": [],
            "create_attribute": [],
            "update_attribute_by_logical_name": [],
            "get_attribute_metadata": [],
            "insert_option_value": [],
            "update_option_value": [],
            "publish_entity": [],
            "create_relationship_from_json": [],
            "create_entity_key": [],
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

    def update_attribute_by_logical_name(
        self,
        entity: str,
        attr: str,
        changes: dict[str, Any],
        *,
        attribute_type: str | None = None,
        solution: str | None = None,
    ) -> dict[str, Any]:
        self.calls["update_attribute_by_logical_name"].append(
            (entity, attr, changes, attribute_type, solution)
        )
        if self._fail_attribute_update:
            raise RuntimeError("attribute PUT failed")
        return {"status": "updated"}

    def get_attribute_metadata(
        self,
        entity: str,
        attr: str,
        *,
        attribute_type: str | None = None,
    ) -> dict[str, Any]:
        self.calls["get_attribute_metadata"].append((entity, attr, attribute_type))
        return self._typed_attributes.get(attr, {"LogicalName": attr, "OptionSet": {"Options": []}})

    def insert_option_value(
        self,
        entity: str,
        attr: str,
        value: int,
        label: dict[str, Any],
        *,
        solution: str | None = None,
    ) -> dict[str, Any]:
        self.calls["insert_option_value"].append((entity, attr, value, label, solution))
        return {"status": "inserted", "value": value}

    def update_option_value(
        self,
        entity: str,
        attr: str,
        value: int,
        label: dict[str, Any],
        *,
        solution: str | None = None,
    ) -> dict[str, Any]:
        self.calls["update_option_value"].append((entity, attr, value, label, solution))
        return {"status": "updated", "value": value}

    def publish_entity(self, entity: str) -> dict[str, Any]:
        self.calls["publish_entity"].append(entity)
        return {"published": True, "entity": entity}

    def get_relationships(self, name: str) -> list[dict[str, Any]]:
        return list(self._existing_relationships)

    def get_entity_metadata(self, name: str) -> dict[str, Any]:
        return {"PrimaryIdAttribute": f"{name}id", "MetadataId": "fake-id"}

    def create_relationship_from_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls["create_relationship_from_json"].append(payload)
        return {"status": "created"}

    def get_entity_keys(self, name: str) -> list[dict[str, Any]]:
        return []

    def create_entity_key(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls["create_entity_key"].append((name, payload))
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
    entity, attr, changes, attribute_type, solution = (
        client.calls["update_attribute_by_logical_name"][0]
    )
    assert entity == "new_projectbudget" and attr == "new_name"
    assert changes["MaxLength"] == 200
    assert attribute_type == "String"
    assert solution is None


@pytest.mark.parametrize(
    ("attribute_type", "odata_type", "specific"),
    [
        (
            "DateTime",
            "DateTimeAttributeMetadata",
            {
                "Format": "DateOnly",
                "DateTimeBehavior": {"Value": "DateOnly"},
                "ImeMode": "Disabled",
            },
        ),
        (
            "Decimal",
            "DecimalAttributeMetadata",
            {"Precision": 2, "MinValue": -100000000000, "MaxValue": 100000000000},
        ),
    ],
)
def test_client_attribute_update_uses_typed_get_and_full_put(
    attribute_type: str,
    odata_type: str,
    specific: dict[str, Any],
):
    metadata = {
        "@odata.context": "https://example/$metadata#attribute",
        # Typed metadata GETs do not consistently echo @odata.type; the client must
        # restore the discriminator from attribute_type before PUT.
        "MetadataId": "attribute-id",
        "LogicalName": "new_field",
        "SchemaName": "new_Field",
        "AttributeType": attribute_type,
        "AttributeTypeName": {"Value": f"{attribute_type}Type"},
        "DisplayName": serialize_label(Label.bilingual("字段", "Field")),
        "RequiredLevel": {
            "Value": "ApplicationRequired",
            "CanBeChanged": True,
            "ManagedPropertyLogicalName": "canmodifyrequirementlevelsettings",
        },
        "HasChanged": None,
        "CreatedOn": "2026-01-01T00:00:00Z",
        "MinSupportedValue": "1900-01-01T00:00:00Z",
        "MaxSupportedPrecision": 10,
        **specific,
    }
    session = RecordingSession(metadata)
    client = DataverseClient(access_token="token")
    client._base_url = "https://example.crm.dynamics.com"
    client._session = session  # type: ignore[assignment]

    result = client.update_attribute_by_logical_name(
        "new_table",
        "new_field",
        {
            "RequiredLevel": {
                "Value": "None",
                "CanBeChanged": True,
                "ManagedPropertyLogicalName": "canmodifyrequirementlevelsettings",
            }
        },
        attribute_type=attribute_type,
        solution="new_solution",
    )

    assert result["method"] == "PUT"
    assert session.patch_calls == []
    assert len(session.get_calls) == 1
    get_url, get_kwargs = session.get_calls[0]
    assert get_url.endswith(
        f"/Attributes(LogicalName='new_field')/Microsoft.Dynamics.CRM.{odata_type}"
    )
    assert get_kwargs["headers"] == {"Consistency": "Strong"}

    put_url, payload, headers = session.put_calls[0]
    assert put_url.endswith("/Attributes(LogicalName='new_field')")
    assert payload["@odata.type"] == f"Microsoft.Dynamics.CRM.{odata_type}"
    assert payload["RequiredLevel"]["Value"] == "None"
    assert payload["MetadataId"] == "attribute-id"
    assert "@odata.context" not in payload
    assert "HasChanged" not in payload
    assert "CreatedOn" not in payload
    assert "MinSupportedValue" not in payload
    assert "MaxSupportedPrecision" not in payload
    for key, value in specific.items():
        assert payload[key] == value
    assert headers == {
        "MSCRM.MergeLabels": "true",
        "MSCRM.SolutionUniqueName": "new_solution",
    }


def test_client_option_actions_use_supported_payloads():
    session = RecordingSession({})
    client = DataverseClient(access_token="token")
    client._base_url = "https://example.crm.dynamics.com"
    client._session = session  # type: ignore[assignment]
    label = serialize_label(Label.bilingual("已确收", "Revenue Recognized"))

    inserted = client.insert_option_value(
        "new_rollingforecast",
        "new_projectstatus",
        5,
        label,
        solution="new_entity930",
    )
    updated = client.update_option_value(
        "new_rollingforecast",
        "new_projectstatus",
        5,
        label,
        solution="new_entity930",
    )

    assert inserted == {"status": "inserted", "value": 5}
    assert updated == {"status": "updated", "value": 5}
    insert_url, insert_payload = session.post_calls[0]
    assert insert_url.endswith("/InsertOptionValue")
    assert insert_payload == {
        "EntityLogicalName": "new_rollingforecast",
        "AttributeLogicalName": "new_projectstatus",
        "Value": 5,
        "Label": label,
        "SolutionUniqueName": "new_entity930",
    }
    update_url, update_payload = session.post_calls[1]
    assert update_url.endswith("/UpdateOptionValue")
    assert update_payload["MergeLabels"] is True
    assert update_payload["SolutionUniqueName"] == "new_entity930"


def test_deploy_idempotent_noop_on_matching_attributes():
    existing_attrs = [_str_existing("new_name"), _money_existing("new_amount")]
    client = FakeClient(table_exists=True, existing_attributes=existing_attrs)
    deploy_table(client, _basic_table(), config=NO_DELAY)
    assert client.calls["update_attribute_by_logical_name"] == []
    assert client.calls["create_attribute"] == []


def _picklist_table() -> Table:
    return Table(
        schema_name="new_X",
        display_name=Label.zh("X"),
        columns=[
            Column("new_Name", AttributeType.String, display_name=Label.zh("名称")),
            Column(
                "new_Status",
                AttributeType.Picklist,
                display_name=Label.bilingual("状态", "Status"),
                options=[
                    Option(1, Label.bilingual("草稿", "Draft")),
                    Option(2, Label.bilingual("已批准", "Approved")),
                ],
            ),
        ],
    )


def _picklist_existing() -> list[dict[str, Any]]:
    return [{
        "LogicalName": "new_status",
        "RequiredLevel": {"Value": "None"},
        "DisplayName": serialize_label(Label.bilingual("状态", "Status")),
    }]


def test_deploy_picklist_inserts_missing_option_and_publishes():
    typed = {
        "new_status": {
            "LogicalName": "new_status",
            "OptionSet": {
                "IsGlobal": False,
                "Options": [{"Value": 1, "Label": serialize_label(Label.bilingual("草稿", "Draft"))}],
            },
        }
    }
    client = FakeClient(
        table_exists=True,
        existing_attributes=_picklist_existing(),
        typed_attributes=typed,
    )

    result = deploy_table(
        client,
        _picklist_table(),
        config=NO_DELAY,
        fields=["new_Status"],
        solution="new_solution",
    )

    status_entry = result["attributes"][0]
    assert status_entry["action"] == "updated"
    assert status_entry["options"] == [
        {"value": 2, "action": "inserted"},
        {"value": 1, "action": "skipped"},
    ]
    call = client.calls["insert_option_value"][0]
    assert call[:3] == ("new_x", "new_status", 2)
    assert call[4] == "new_solution"
    assert client.calls["update_option_value"] == []
    assert client.calls["publish_entity"] == ["new_x"]
    assert result["publish"]["published"] is True


def test_deploy_picklist_updates_authored_labels_and_retains_remote_only():
    typed = {
        "new_status": {
            "OptionSet": {
                "IsGlobal": False,
                "Options": [
                    {"Value": 1, "Label": serialize_label(Label.bilingual("草案", "Draft"))},
                    {"Value": 2, "Label": serialize_label(Label.bilingual("已批准", "Approved"))},
                    {"Value": 9, "Label": serialize_label(Label.bilingual("远端", "Remote"))},
                ],
            }
        }
    }
    client = FakeClient(
        table_exists=True,
        existing_attributes=_picklist_existing(),
        typed_attributes=typed,
    )

    result = deploy_table(client, _picklist_table(), config=NO_DELAY, fields=["new_Status"])

    entry = result["attributes"][0]
    assert entry["action"] == "updated"
    assert entry["remote_only_options_retained"] == [9]
    update = client.calls["update_option_value"][0]
    assert update[:3] == ("new_x", "new_status", 1)
    assert update[4] is None
    labels = {(x["LanguageCode"], x["Label"]) for x in update[3]["LocalizedLabels"]}
    assert labels == {(2052, "草稿"), (1033, "Draft")}
    assert client.calls["insert_option_value"] == []
    assert client.calls["publish_entity"] == ["new_x"]


def test_deploy_picklist_reports_partial_failure_when_option_commits_but_field_put_fails():
    typed = {
        "new_status": {
            "OptionSet": {
                "IsGlobal": False,
                "Options": [{"Value": 1, "Label": serialize_label(Label.bilingual("草稿", "Draft"))}],
            }
        }
    }
    # RequiredLevel differs, forcing a normal metadata PUT after option insertion.
    existing = _picklist_existing()
    existing[0]["RequiredLevel"] = {"Value": "ApplicationRequired"}
    client = FakeClient(
        table_exists=True,
        existing_attributes=existing,
        typed_attributes=typed,
        fail_attribute_update=True,
    )

    result = deploy_table(client, _picklist_table(), config=NO_DELAY, fields=["new_Status"])

    entry = result["attributes"][0]
    assert entry["action"] == "partial_failed"
    assert "attribute PUT failed" in entry["error"]
    # The successful option action still requires targeted publication.
    assert client.calls["publish_entity"] == ["new_x"]


def test_deploy_picklist_matching_options_is_idempotent_noop():
    typed = {
        "new_status": {
            "OptionSet": {
                "IsGlobal": False,
                "Options": [
                    {"Value": 1, "Label": serialize_label(Label.bilingual("草稿", "Draft"))},
                    {"Value": 2, "Label": serialize_label(Label.bilingual("已批准", "Approved"))},
                ],
            }
        }
    }
    client = FakeClient(
        table_exists=True,
        existing_attributes=_picklist_existing(),
        typed_attributes=typed,
    )

    result = deploy_table(client, _picklist_table(), config=NO_DELAY, fields=["new_Status"])

    assert result["attributes"][0]["action"] == "skipped"
    assert client.calls["insert_option_value"] == []
    assert client.calls["update_option_value"] == []
    assert client.calls["publish_entity"] == []
    assert "publish" not in result


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


def test_deploy_fields_required_level_update_passes_type_and_solution():
    """Existing DateTime fields use the safe typed metadata update path."""
    table = Table(
        schema_name="new_X",
        display_name=Label.zh("X"),
        columns=[
            Column("new_Name", AttributeType.String, display_name=Label.zh("名称")),
            Column(
                "new_ShipmentMonth",
                AttributeType.DateTime,
                display_name=Label.bilingual("发货月份", "Shipment Month"),
                date_time_behavior="DateOnly",
                format="DateOnly",
            ),
        ],
    )
    existing = [{
        "LogicalName": "new_shipmentmonth",
        "DisplayName": serialize_label(Label.bilingual("发货月份", "Shipment Month")),
        "RequiredLevel": {"Value": "ApplicationRequired"},
        "Format": "DateOnly",
        "DateTimeBehavior": {"Value": "DateOnly"},
    }]
    client = FakeClient(table_exists=True, existing_attributes=existing)

    result = deploy_table(
        client,
        table,
        config=NO_DELAY,
        fields=["new_ShipmentMonth"],
        solution="new_entity930",
        solution_clean=True,
    )

    assert result["attributes"][0]["action"] == "updated"
    entity, attr, changes, attribute_type, solution = (
        client.calls["update_attribute_by_logical_name"][0]
    )
    assert (entity, attr) == ("new_x", "new_shipmentmonth")
    assert changes["RequiredLevel"]["Value"] == "None"
    assert attribute_type == "DateTime"
    assert solution == "new_entity930"


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


# ---------------------------------------------------------------------------
# Referenced global optionsets (dependency-first)
# ---------------------------------------------------------------------------


def _global_picklist_table() -> Table:
    """Table mixing a global-optionset Picklist and an inline (entity-bound) Picklist."""
    return Table(
        schema_name="new_SalesTarget",
        display_name=Label.bilingual("销售目标", "Sales Target"),
        columns=[
            Column(
                "new_Name",
                AttributeType.String,
                display_name=Label.bilingual("名称", "Name"),
                is_primary_name=True,
                max_length=100,
            ),
            Column(
                "new_BusinessGroupId",
                AttributeType.Picklist,
                display_name=Label.bilingual("商务组", "Business Group"),
                optionset_name="new_salesgroup",
            ),
            Column(
                "new_RecordType",
                AttributeType.Picklist,
                display_name=Label.bilingual("记录类型", "Record Type"),
                options=[
                    Option(1, Label.bilingual("未签单", "Not Signed")),
                    Option(2, Label.bilingual("已签单", "Signed")),
                ],
            ),
        ],
    )


_SALESGROUP_MODULE = (
    "from framework_power import GlobalOptionSet, Label, Option\n"
    "OPTIONSET = GlobalOptionSet(\n"
    "    name='new_salesgroup',\n"
    "    display_name=Label.bilingual('销售组', 'Sales Group'),\n"
    "    options=[Option(100000001, Label.bilingual('欧美一组', 'Europe and U.S. Group 1'))],\n"
    ")\n"
)


class OptionsetAwareFakeClient(FakeClient):
    """FakeClient + the global optionset API surface (get/create)."""

    def __init__(
        self,
        *,
        existing_optionsets: dict[str, dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._existing_optionsets = dict(existing_optionsets or {})
        self.created_optionsets: list[dict[str, Any]] = []

    def get_global_optionset_by_name(self, name: str) -> dict[str, Any] | None:
        return self._existing_optionsets.get(name)

    def create_global_optionset(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.created_optionsets.append(payload)
        return {"MetadataId": "osid:" + payload["Name"]}


def test_referenced_global_optionsets_collects_only_global():
    assert _referenced_global_optionsets(_global_picklist_table()) == ["new_salesgroup"]
    # Inline (entity-bound) picklists are not references.
    assert _referenced_global_optionsets(_picklist_table()) == []


def test_ensure_referenced_optionsets_creates_from_local_definition(tmp_path):
    (tmp_path / "new_salesgroup.py").write_text(_SALESGROUP_MODULE, encoding="utf-8")
    client = OptionsetAwareFakeClient()
    res = ensure_referenced_optionsets(
        client, _global_picklist_table(), optionsets_dir=tmp_path, config=NO_DELAY
    )
    assert res["missing"] == []
    assert res["optionsets"][0]["deploy"]["action"] == "created"
    assert client.created_optionsets[0]["Name"] == "new_salesgroup"
    assert client.created_optionsets[0]["IsGlobal"] is True


def test_ensure_referenced_optionsets_exists_is_idempotent(tmp_path):
    (tmp_path / "new_salesgroup.py").write_text(_SALESGROUP_MODULE, encoding="utf-8")
    client = OptionsetAwareFakeClient(
        existing_optionsets={
            "new_salesgroup": {
                "MetadataId": "osid:new_salesgroup",
                "Options": [{"Value": 100000001}],
            }
        }
    )
    res = ensure_referenced_optionsets(
        client, _global_picklist_table(), optionsets_dir=tmp_path, config=NO_DELAY
    )
    assert res["optionsets"][0]["deploy"]["action"] == "exists"
    assert client.created_optionsets == []


def test_ensure_referenced_optionsets_missing_local_warns():
    """No local definition + no online presence -> warning, deploy continues."""
    client = OptionsetAwareFakeClient()
    res = ensure_referenced_optionsets(
        client, _global_picklist_table(), optionsets_dir=None, config=NO_DELAY
    )
    assert res["optionsets"] == []
    assert res["missing"][0]["name"] == "new_salesgroup"


def test_ensure_referenced_optionsets_no_references():
    client = OptionsetAwareFakeClient()
    res = ensure_referenced_optionsets(
        client, _basic_table(), optionsets_dir=None, config=NO_DELAY
    )
    assert res == {"optionsets": [], "added": [], "missing": []}


def test_deploy_table_syncs_referenced_optionset_before_entity(tmp_path):
    (tmp_path / "new_salesgroup.py").write_text(_SALESGROUP_MODULE, encoding="utf-8")
    client = OptionsetAwareFakeClient()
    result = deploy_table(
        client,
        _global_picklist_table(),
        config=NO_DELAY,
        optionsets_dir=tmp_path,
        solution="new_entity930",
    )
    # Optionset created and its solution-add (code 9) recorded.
    assert result["optionsets"][0]["deploy"]["action"] == "created"
    assert result["optionsets_missing"] == []
    codes = {code for (_sol, code, _oid, _sub) in client.calls["add_solution_component"]}
    assert 9 in codes
    # Entity still deployed as before.
    assert result["entity"]["action"] == "created"
