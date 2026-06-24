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

    def get_entity_metadata(self, name: str) -> dict[str, Any]:
        return self._entity

    def get_attributes(self, name: str) -> list[dict[str, Any]]:
        return list(self._attrs)

    def get_relationships(self, name: str) -> list[dict[str, Any]]:
        return list(self._rels)


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
