"""Unit tests for framework_power.reverse (env metadata -> Table)."""

from typing import Any

import pytest

from framework_power import Cascade, reverse_table
from framework_power.models import AttributeType

pytestmark = pytest.mark.unit


class ReverseFakeClient:
    def __init__(self, entity: dict, attrs: list[dict], rels: list[dict]) -> None:
        self._entity = entity
        self._attrs = attrs
        self._rels = rels
        self._global_optionsets: dict[str, dict] = {}
        self._optionset_attrs: dict[str, dict] = {}

    def get_entity_metadata(self, name: str) -> dict[str, Any]:
        return self._entity

    def get_attributes(self, name: str) -> list[dict[str, Any]]:
        return list(self._attrs)

    def get_relationships(self, name: str) -> list[dict[str, Any]]:
        return list(self._rels)

    def get_optionset_attributes(self, name: str) -> dict[str, dict[str, Any]]:
        """Mock for typed Picklist/Boolean attribute queries (returns registered data).

        In the real client, this queries PicklistAttributeMetadata/BooleanAttributeMetadata
        typed collections with $expand=OptionSet. For tests, register the expected
        OptionSet data via ``set_optionset_for_attr()``.
        """
        return dict(self._optionset_attrs)

    def set_optionset_for_attr(self, logical_name: str, optionset_data: dict) -> None:
        """Register OptionSet data for an attribute (simulating typed query results)."""
        self._optionset_attrs[logical_name] = {"OptionSet": optionset_data}

    def get_global_optionset_by_name(self, name: str) -> dict[str, Any] | None:
        """Mock for global optionset lookup (returns the registered raw dict)."""
        return self._global_optionsets.get(name.lower())

    def add_global_optionset(self, name: str, options: list[dict]) -> None:
        """Register a global optionset that get_global_optionset_by_name will return."""
        self._global_optionsets[name.lower()] = {"Name": name, "Options": options}


_ENTITY = {
    "SchemaName": "Contact",
    "LogicalName": "contact",
    "PrimaryNameAttribute": "fullname",
    "OwnershipType": "UserOwned",
    "HasActivities": True,
    "DisplayName": {"LocalizedLabels": [{"Label": "Contact", "LanguageCode": 1033}]},
}

_ATTRIBUTES = [
    {"LogicalName": "firstname", "SchemaName": "FirstName", "AttributeType": "String",
     "DisplayName": {"LocalizedLabels": [{"Label": "First Name", "LanguageCode": 1033}]}, "MaxLength": 50},
    {"LogicalName": "new_custom", "SchemaName": "new_Custom", "AttributeType": "String",
     "DisplayName": {"LocalizedLabels": [{"Label": "Custom", "LanguageCode": 1033}]}, "MaxLength": 100},
    {"LogicalName": "fullname", "SchemaName": "FullName", "AttributeType": "String", "IsComputed": True},
    {"LogicalName": "contactid", "SchemaName": "ContactId", "AttributeType": "Uniqueidentifier", "IsPrimaryId": True},
    {"LogicalName": "creditlimit_base", "SchemaName": "CreditLimit_Base", "AttributeType": "Money"},
    {"LogicalName": "creditlimit", "SchemaName": "CreditLimit", "AttributeType": "Money",
     "Precision": 2, "PrecisionSource": 2},
    {"LogicalName": "parentcustomerid", "SchemaName": "ParentCustomerId", "AttributeType": "Lookup",
     "DisplayName": {"LocalizedLabels": [{"Label": "Company Name", "LanguageCode": 1033}]},
     "Targets": ["account", "contact"], "RequiredLevel": {"Value": "Recommended"}},
]

_RELATIONSHIPS = [
    {"@odata.type": "Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata",
     "SchemaName": "contact_customer_parent_customer",
     "ReferencedEntity": "account", "ReferencingEntity": "contact",
     "ReferencingAttribute": "parentcustomerid",
     "CascadeConfiguration": {"Assign": "NoCascade", "Delete": "RemoveLink"}},
    # contact is the REFERENCED (parent) side here -> must be skipped (lookup on account).
    {"@odata.type": "Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata",
     "SchemaName": "contact_as_primary_contact",
     "ReferencedEntity": "contact", "ReferencingEntity": "account",
     "ReferencingAttribute": "primarycontactid"},
]


def test_reverse_keeps_standard_skips_virtual_pk_base():
    client = ReverseFakeClient(_ENTITY, _ATTRIBUTES, _RELATIONSHIPS)
    table = reverse_table(client, "contact")

    assert table.schema_name == "Contact"
    names = {c.schema_name for c in table.columns}
    # Kept: standard firstname, custom new_Custom, money CreditLimit.
    assert {"FirstName", "new_Custom", "CreditLimit"} <= names
    # Skipped: computed fullname, PK contactid, *_base, lookup parentcustomerid.
    assert "FullName" not in names
    assert "ContactId" not in names
    assert "CreditLimit_Base" not in names
    assert "ParentCustomerId" not in names
    credit = next(c for c in table.columns if c.schema_name == "CreditLimit")
    assert credit.type == AttributeType.Money and credit.precision == 2


def test_reverse_file_column_resolved_via_odata():
    # File columns report AttributeType "Virtual"; reverse must resolve via @odata.type.
    entity = {"SchemaName": "Contact", "LogicalName": "contact", "PrimaryNameAttribute": "firstname",
              "DisplayName": {"LocalizedLabels": [{"Label": "Contact", "LanguageCode": 1033}]}}
    attrs = [
        {"LogicalName": "firstname", "SchemaName": "FirstName", "AttributeType": "String",
         "DisplayName": {"LocalizedLabels": [{"Label": "First", "LanguageCode": 1033}]}},
        {"LogicalName": "new_doc", "SchemaName": "new_Doc", "AttributeType": "Virtual",
         "@odata.type": "#Microsoft.Dynamics.CRM.FileAttributeMetadata",
         "DisplayName": {"LocalizedLabels": [{"Label": "Doc", "LanguageCode": 1033}]}, "MaxSizeInKB": 2048},
    ]
    client = ReverseFakeClient(entity, attrs, [])
    table = reverse_table(client, "contact")

    doc = next((c for c in table.columns if c.schema_name == "new_Doc"), None)
    assert doc is not None
    assert doc.type == AttributeType.File
    assert doc.max_size_in_kb == 2048


def test_reverse_lookup_becomes_relationship():
    client = ReverseFakeClient(_ENTITY, _ATTRIBUTES, _RELATIONSHIPS)
    table = reverse_table(client, "contact")

    assert len(table.relationships) == 1
    rel = table.relationships[0]
    assert rel.schema_name == "contact_customer_parent_customer"
    assert rel.referenced_entity == "account"
    assert rel.referencing_entity == "contact"
    assert rel.lookup is not None
    assert rel.lookup.schema_name == "ParentCustomerId"
    assert rel.lookup.target_entity == "account"  # Targets[0]
    assert rel.cascade.delete == Cascade.RemoveLink


def test_reverse_codegen_round_trip():
    """reverse -> source -> import yields a Table with the same shape (deployable file)."""
    from framework_power import table_to_python_source

    client = ReverseFakeClient(_ENTITY, _ATTRIBUTES, _RELATIONSHIPS)
    table = reverse_table(client, "contact")
    src = table_to_python_source(table)
    compile(src, "contact.py", "exec")
    ns: dict = {}
    exec(src, ns)
    t2 = ns["TABLE"]
    assert t2.schema_name == "Contact"
    assert {c.schema_name for c in t2.columns} == {c.schema_name for c in table.columns}
    assert len(t2.relationships) == len(table.relationships)


# ----------------------------------------------------------------- Picklist optionset handling tests

_PICKLIST_ENTITY = {
    "SchemaName": "new_TestPicklist",
    "LogicalName": "new_testpicklist",
    "PrimaryNameAttribute": "new_name",
    "OwnershipType": "UserOwned",
    "DisplayName": {"LocalizedLabels": [{"Label": "Test Picklist", "LanguageCode": 1033}]},
}

_PICKLIST_ATTRS = [
    {"LogicalName": "new_name", "SchemaName": "new_Name", "AttributeType": "String",
     "DisplayName": {"LocalizedLabels": [{"Label": "Name", "LanguageCode": 1033}]}, "MaxLength": 100},
    # Local option set — Options inline in attribute response. Real Dataverse also
    # gives it a non-empty Name ("{entity}_{field}") and IsGlobal=False; the name
    # alone must NOT classify it as a global reference.
    {"LogicalName": "new_localstatus", "SchemaName": "new_LocalStatus", "AttributeType": "Picklist",
     "DisplayName": {"LocalizedLabels": [{"Label": "Local Status", "LanguageCode": 1033}]},
     "OptionSet": {
         "Name": "new_testpicklist_new_localstatus",
         "IsGlobal": False,
         "Options": [
             {"Value": 1, "Label": {"LocalizedLabels": [{"Label": "草稿", "LanguageCode": 2052},
                                                        {"Label": "Draft", "LanguageCode": 1033}]}},
             {"Value": 2, "Label": {"LocalizedLabels": [{"Label": "已提交", "LanguageCode": 2052},
                                                        {"Label": "Submitted", "LanguageCode": 1033}]}},
         ],
     }},
    # Global option set — base /Attributes query does NOT include OptionSet key.
    # The typed PicklistAttributeMetadata?$expand=OptionSet query provides it.
    {"LogicalName": "new_orderstatus", "SchemaName": "new_OrderStatus", "AttributeType": "Picklist",
     "DisplayName": {"LocalizedLabels": [{"Label": "Order Status", "LanguageCode": 1033}]}},
    # Another global option set.
    {"LogicalName": "new_priority", "SchemaName": "new_Priority", "AttributeType": "Picklist",
     "DisplayName": {"LocalizedLabels": [{"Label": "Priority", "LanguageCode": 1033}]}},
    # Entity-bound optionset — base response has no OptionSet key; the typed
    # PicklistAttributeMetadata query returns Name + IsGlobal=False + Options.
    # (Live regression: new_salesproject_new_project_type was misclassified as
    # global purely because Name was non-empty, creating a bogus optionsets/ doc.)
    {"LogicalName": "new_projecttype", "SchemaName": "new_ProjectType", "AttributeType": "Picklist",
     "DisplayName": {"LocalizedLabels": [{"Label": "Project Type", "LanguageCode": 1033}]}},
]

# OptionSet data that the typed PicklistAttributeMetadata query would return.
# This simulates what get_optionset_attributes() provides in the real client.
_PICKLIST_OPTIONSET_DATA = {
    "new_orderstatus": {
        "Name": "new_orderstatus",
        "IsGlobal": True,
        "Options": [
            {"Value": 1, "Label": {"LocalizedLabels": [{"Label": "草稿", "LanguageCode": 2052},
                                                        {"Label": "Draft", "LanguageCode": 1033}]}},
            {"Value": 2, "Label": {"LocalizedLabels": [{"Label": "已确认", "LanguageCode": 2052},
                                                        {"Label": "Confirmed", "LanguageCode": 1033}]}},
        ],
    },
    "new_priority": {
        "Name": "new_priority",
        "IsGlobal": True,
        "Options": [
            {"Value": 1, "Label": {"LocalizedLabels": [{"Label": "低", "LanguageCode": 2052},
                                                        {"Label": "Low", "LanguageCode": 1033}]}},
            {"Value": 2, "Label": {"LocalizedLabels": [{"Label": "高", "LanguageCode": 2052},
                                                        {"Label": "High", "LanguageCode": 1033}]}},
        ],
    },
    # Entity-bound (local) optionset from the typed query — real Dataverse shape:
    # auto-named "{entity}_{field}" with IsGlobal=False.
    "new_projecttype": {
        "Name": "new_testpicklist_new_projecttype",
        "IsGlobal": False,
        "Options": [
            {"Value": 1, "Label": {"LocalizedLabels": [
                {"Label": "资本项目", "LanguageCode": 2052},
                {"Label": "Capital", "LanguageCode": 1033},
            ]}},
            {"Value": 2, "Label": {"LocalizedLabels": [
                {"Label": "租赁项目", "LanguageCode": 2052},
                {"Label": "Leasing", "LanguageCode": 1033},
            ]}},
        ],
    },
}


def _make_picklist_client() -> ReverseFakeClient:
    """Create a ReverseFakeClient with optionset data registered (simulating typed query)."""
    client = ReverseFakeClient(_PICKLIST_ENTITY, _PICKLIST_ATTRS, [])
    for logical_name, os_data in _PICKLIST_OPTIONSET_DATA.items():
        client.set_optionset_for_attr(logical_name, os_data)
    return client


def test_reverse_picklist_local_options_preserved():
    """Local (inline) Picklist options are captured into Column.options.

    Real Dataverse names local optionsets "{entity}_{field}" (non-empty Name,
    IsGlobal=False) — the name alone must NOT classify it as a global reference.
    """
    client = ReverseFakeClient(_PICKLIST_ENTITY, _PICKLIST_ATTRS, [])
    table = reverse_table(client, "new_testpicklist")

    col = next((c for c in table.columns if c.schema_name == "new_LocalStatus"), None)
    assert col is not None
    assert len(col.options) == 2
    assert col.options[0].value == 1
    assert col.options[1].value == 2
    assert col.optionset_name is None  # local, not global


def test_reverse_picklist_global_captures_name_and_options():
    """Global Picklist stores optionset_name AND options (for optionset doc generation).

    The data dictionary still renders a document link (not inline) when
    optionset_name is set — see _format_picklist_note. But the options data
    is captured so build_prefetched_optionsets() can generate the optionset docs.
    """
    client = _make_picklist_client()
    table = reverse_table(client, "new_testpicklist")

    col = next((c for c in table.columns if c.schema_name == "new_OrderStatus"), None)
    assert col is not None
    assert col.optionset_name == "new_orderstatus"
    assert len(col.options) == 2  # options captured from typed query
    assert col.options[0].value == 1


def test_reverse_picklist_global_both_captured():
    """Multiple global optionsets each capture their respective names and options."""
    client = _make_picklist_client()
    table = reverse_table(client, "new_testpicklist")

    order_col = next((c for c in table.columns if c.schema_name == "new_OrderStatus"), None)
    prio_col = next((c for c in table.columns if c.schema_name == "new_Priority"), None)
    assert order_col is not None and prio_col is not None
    assert order_col.optionset_name == "new_orderstatus"
    assert prio_col.optionset_name == "new_priority"
    assert len(order_col.options) == 2
    assert len(prio_col.options) == 2


def test_reverse_picklist_local_in_dictionary():
    """Verify local Picklist options appear inline in the 说明 column."""
    from framework_power.data_dictionary import table_to_markdown as dd_markdown

    client = ReverseFakeClient(_PICKLIST_ENTITY, _PICKLIST_ATTRS, [])
    table = reverse_table(client, "new_testpicklist")
    md = dd_markdown(table, source_name=None)

    # Local options should be listed inline in the 说明 column.
    assert "草稿:1" in md
    assert "已提交:2" in md


def test_reverse_picklist_global_in_dictionary_link():
    """Verify global Picklist renders as a link to optionsets/ in the 说明 column."""
    from framework_power.data_dictionary import table_to_markdown as dd_markdown

    client = _make_picklist_client()
    table = reverse_table(client, "new_testpicklist")
    md = dd_markdown(table, source_name=None)

    # Global optionsets should have links, NOT inline options.
    assert "[选项集: new_orderstatus](../optionsets/new_orderstatus.md)" in md
    assert "[选项集: new_priority](../optionsets/new_priority.md)" in md


def test_reverse_picklist_entitybound_not_global():
    """Entity-bound optionset (typed query, IsGlobal=False) must NOT become a global ref.

    Live regression (ADR-010): the typed PicklistAttributeMetadata query returns
    OptionSet data for EVERY picklist, including entity-bound ones whose Name is
    the auto-generated "{entity}_{field}". Classifying by Name alone misfiled
    them as global → bogus optionsets/<entity>_<field>.md docs were generated.
    """
    client = _make_picklist_client()
    table = reverse_table(client, "new_testpicklist")

    col = next((c for c in table.columns if c.schema_name == "new_ProjectType"), None)
    assert col is not None
    assert col.optionset_name is None  # entity-bound → inline, not a global reference
    assert len(col.options) == 2  # options still captured inline


def test_reverse_picklist_entitybound_in_dictionary_inline():
    """Entity-bound optionset renders inline in the 说明 column, no optionsets/ link."""
    from framework_power.data_dictionary import (
        build_prefetched_optionsets,
        table_to_markdown as dd_markdown,
    )

    client = _make_picklist_client()
    table = reverse_table(client, "new_testpicklist")
    md = dd_markdown(table, source_name=None)

    # Inline options, NOT a doc link.
    assert "资本项目:1" in md
    assert "租赁项目:2" in md
    assert "new_testpicklist_new_projecttype.md" not in md

    # And it must not feed optionset doc generation.
    prefetched = build_prefetched_optionsets([table])
    assert "new_testpicklist_new_projecttype" not in prefetched
    assert set(prefetched) == {"new_orderstatus", "new_priority"}
