"""
Model -> Dataverse Web API JSON serializer (framework_power).

Pure functions (no client, no I/O) so they are trivially unit-testable. They mirror
the proven per-type branches of the legacy ``framework/utils/dataverse_client.py``
``_convert_*`` methods, generalized for multi-language labels and full type coverage,
and aligned with the Microsoft Dataverse Web API create payloads shown in the
``dv-metadata`` skill.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .models import (
    AttributeType,
    BooleanLabels,
    CascadeConfig,
    Column,
    Label,
    Relationship,
    RequiredLevel,
    Table,
)

logger = logging.getLogger(__name__)


# ============================================================ labels


def serialize_label(label: "Label | Any") -> Optional[dict[str, Any]]:
    """Build a Dataverse ``Label`` object from a multi-language ``Label``.

    Accepts a ``Label``, ``LocalizedLabel``, ``str`` (zh-only), ``(zh, en)`` tuple,
    or ``None``. Returns ``None`` for empty/``None`` input.
    """
    lbl = Label.parse(label)
    if lbl is None or not lbl.localized:
        return None
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.Label",
        "LocalizedLabels": [
            {
                "@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel",
                "Label": ll.text,
                "LanguageCode": ll.language_code,
            }
            for ll in lbl.localized
        ],
    }


def _label_set(label_dict: dict[str, Any]) -> set[tuple[int, str]]:
    """Reduce a Dataverse Label dict to a set of (LanguageCode, Label) pairs."""
    pairs: set[tuple[int, str]] = set()
    for ll in label_dict.get("LocalizedLabels", []) or []:
        lc = ll.get("LanguageCode")
        text = ll.get("Label")
        if lc is not None and text is not None:
            pairs.add((lc, text))
    return pairs


def serialize_required_level(level: RequiredLevel) -> dict[str, Any]:
    """Build a Dataverse ``RequiredLevel`` managed-property object."""
    return {
        "Value": level.value,
        "CanBeChanged": True,
        "ManagedPropertyLogicalName": "canmodifyrequirementlevelsettings",
    }


# ============================================================ attributes

_ODATA_TYPE: dict[AttributeType, str] = {
    AttributeType.String: "Microsoft.Dynamics.CRM.StringAttributeMetadata",
    AttributeType.Integer: "Microsoft.Dynamics.CRM.IntegerAttributeMetadata",
    AttributeType.BigInt: "Microsoft.Dynamics.CRM.BigIntAttributeMetadata",
    AttributeType.Money: "Microsoft.Dynamics.CRM.MoneyAttributeMetadata",
    AttributeType.Decimal: "Microsoft.Dynamics.CRM.DecimalAttributeMetadata",
    AttributeType.Double: "Microsoft.Dynamics.CRM.DoubleAttributeMetadata",
    AttributeType.Picklist: "Microsoft.Dynamics.CRM.PicklistAttributeMetadata",
    AttributeType.Boolean: "Microsoft.Dynamics.CRM.BooleanAttributeMetadata",
    AttributeType.Memo: "Microsoft.Dynamics.CRM.MemoAttributeMetadata",
    AttributeType.DateTime: "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata",
    AttributeType.File: "Microsoft.Dynamics.CRM.FileAttributeMetadata",
}

# Per-type JSON keys that are legal to PATCH (the rest are read-only / create-only).
_UPDATABLE_BY_TYPE: dict[AttributeType, set[str]] = {
    AttributeType.String: {"DisplayName", "Description", "MaxLength", "FormatName", "RequiredLevel", "ImeMode"},
    AttributeType.Memo: {"DisplayName", "Description", "MaxLength", "FormatName", "RequiredLevel", "ImeMode"},
    AttributeType.Integer: {"DisplayName", "Description", "MinValue", "MaxValue", "RequiredLevel"},
    AttributeType.BigInt: {"DisplayName", "Description", "RequiredLevel"},
    AttributeType.Money: {
        "DisplayName", "Description", "Precision", "PrecisionSource",
        "MinValue", "MaxValue", "RequiredLevel",
    },
    AttributeType.Decimal: {"DisplayName", "Description", "Precision", "MinValue", "MaxValue", "RequiredLevel"},
    AttributeType.Double: {"DisplayName", "Description", "Precision", "MinValue", "MaxValue", "RequiredLevel"},
    AttributeType.Picklist: {"DisplayName", "Description", "RequiredLevel"},
    AttributeType.Boolean: {"DisplayName", "Description", "DefaultValue", "RequiredLevel"},
    AttributeType.DateTime: {"DisplayName", "Description", "Format", "DateTimeBehavior", "RequiredLevel"},
    AttributeType.File: {"DisplayName", "Description", "MaxSizeInKB", "RequiredLevel"},
}

# Attribute types whose OptionSet is effectively create-only (cannot be PATCHed
# through the simple attribute endpoint; deployer reports manual update required).
_OPTIONSET_TYPES = {AttributeType.Picklist, AttributeType.Boolean}


def serialize_option(value: int, label: "Label | Any") -> dict[str, Any]:
    """Serialize a picklist option."""
    return {"Value": value, "Label": serialize_label(label)}


def serialize_boolean_optionset(labels: BooleanLabels) -> dict[str, Any]:
    """Serialize a Boolean ``BooleanOptionSetMetadata`` (multi-language True/False)."""
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.BooleanOptionSetMetadata",
        "TrueOption": {"Value": 1, "Label": serialize_label(labels.true_label)},
        "FalseOption": {"Value": 0, "Label": serialize_label(labels.false_label)},
    }


def serialize_column(col: Column, *, is_primary_name: bool = False) -> dict[str, Any]:
    """Serialize a ``Column`` to a Dataverse attribute create payload.

    Args:
        col: The column definition.
        is_primary_name: When True and the column is String, sets ``IsPrimaryName``.
    """
    attr: dict[str, Any] = {
        "@odata.type": _ODATA_TYPE[col.type],
        "SchemaName": col.schema_name,
        "DisplayName": serialize_label(col.display_name),
        "RequiredLevel": serialize_required_level(col.required),
    }
    description = serialize_label(col.description)
    if description:
        attr["Description"] = description
    if col.ime_mode:
        attr["ImeMode"] = col.ime_mode

    t = col.type

    if t == AttributeType.String:
        attr["FormatName"] = {"Value": col.format_name or "Text"}
        attr["MaxLength"] = col.max_length if col.max_length is not None else 100

    elif t == AttributeType.Memo:
        attr["MaxLength"] = col.max_length if col.max_length is not None else 2000

    elif t in (AttributeType.Integer, AttributeType.BigInt):
        if col.min_value is not None:
            attr["MinValue"] = col.min_value
        if col.max_value is not None:
            attr["MaxValue"] = col.max_value

    elif t == AttributeType.Money:
        attr["Precision"] = col.precision if col.precision is not None else 2
        attr["PrecisionSource"] = col.precision_source if col.precision_source is not None else 2
        if col.min_value is not None:
            attr["MinValue"] = col.min_value
        if col.max_value is not None:
            attr["MaxValue"] = col.max_value

    elif t in (AttributeType.Decimal, AttributeType.Double):
        if col.precision is not None:
            attr["Precision"] = col.precision
        if col.min_value is not None:
            attr["MinValue"] = col.min_value
        if col.max_value is not None:
            attr["MaxValue"] = col.max_value

    elif t == AttributeType.Picklist:
        attr["OptionSet"] = {
            "@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata",
            "IsGlobal": False,
            "Options": [serialize_option(o.value, o.label) for o in col.options],
        }

    elif t == AttributeType.Boolean:
        if col.default_value is not None:
            attr["DefaultValue"] = bool(col.default_value)
        labels = col.boolean_labels or BooleanLabels(
            Label.bilingual("是", "Yes"), Label.bilingual("否", "No")
        )
        attr["OptionSet"] = serialize_boolean_optionset(labels)

    elif t == AttributeType.DateTime:
        behavior = col.date_time_behavior
        if col.format:
            attr["Format"] = col.format
        elif behavior == "DateOnly":
            attr["Format"] = "DateOnly"
        else:
            attr["Format"] = "DateAndTime"
        if behavior:
            attr["DateTimeBehavior"] = {"Value": behavior}

    elif t == AttributeType.File:
        if col.max_size_in_kb is not None:
            attr["MaxSizeInKB"] = col.max_size_in_kb

    if is_primary_name:
        if t == AttributeType.String:
            attr["IsPrimaryName"] = True
        else:
            logger.warning(
                f"Column '{col.schema_name}' marked as primary name but is {t.value}; "
                "primary name must be String."
            )

    return {k: v for k, v in attr.items() if v is not None}


# ============================================================ table


def _resolve_primary_name(table: Table) -> Optional[Column]:
    """Determine the primary-name column (explicit > flagged > first String).

    Raises ``ValueError`` if the table has no String column at all.
    """
    strings = [c for c in table.columns if c.type == AttributeType.String]
    if not strings:
        raise ValueError(
            f"Table '{table.schema_name}' has no String column; Dataverse requires a primary name attribute."
        )

    if table.primary_name_column:
        for c in strings:
            if c.schema_name.lower() == table.primary_name_column.lower():
                return c
        logger.warning(
            f"primary_name_column '{table.primary_name_column}' not found among String columns; "
            "auto-picking the first String column."
        )

    flagged = [c for c in strings if c.is_primary_name]
    if flagged:
        if len(flagged) > 1:
            logger.warning(
                f"Multiple columns flagged is_primary_name; using '{flagged[0].schema_name}'."
            )
        return flagged[0]

    logger.info(f"Auto-picking '{strings[0].schema_name}' as primary name for '{table.schema_name}'.")
    return strings[0]


def serialize_table_for_create(table: Table) -> dict[str, Any]:
    """Serialize a ``Table`` to a full EntityDefinitions create payload (entity + Attributes)."""
    display_collection = serialize_label(table.display_collection_name)
    if not display_collection:
        # Default plural from the Chinese/first localized label + "s".
        first_text = table.display_name.localized[0].text if table.display_name.localized else table.schema_name
        display_collection = serialize_label(Label.parse(first_text + "s"))

    entity: dict[str, Any] = {
        "@odata.type": "Microsoft.Dynamics.CRM.EntityMetadata",
        "SchemaName": table.schema_name,
        "DisplayName": serialize_label(table.display_name),
        "DisplayCollectionName": display_collection,
        "Description": serialize_label(table.description),
        "OwnershipType": table.ownership_type,
        "IsActivity": table.has_activities,
        "HasActivities": table.has_activities,
        "HasNotes": table.has_notes,
        "IsQuickCreateEnabled": table.is_quick_create_enabled,
    }

    primary = _resolve_primary_name(table)
    attributes = [
        serialize_column(c, is_primary_name=(primary is not None and c.schema_name == primary.schema_name))
        for c in table.columns
    ]
    if attributes:
        entity["Attributes"] = attributes

    return {k: v for k, v in entity.items() if v is not None}


def serialize_entity_patch(table: Table) -> dict[str, Any]:
    """Serialize only the updatable entity properties for a PATCH."""
    patch: dict[str, Any] = {
        "HasNotes": bool(table.has_notes),
        "IsAuditEnabled": {"Value": bool(table.is_audit_enabled)},
        "IsQuickCreateEnabled": bool(table.is_quick_create_enabled),
    }
    display = serialize_label(table.display_name)
    if display:
        patch["DisplayName"] = display
    collection = serialize_label(table.display_collection_name)
    if collection:
        patch["DisplayCollectionName"] = collection
    description = serialize_label(table.description)
    if description:
        patch["Description"] = description
    return patch


# ============================================================ relationships


def serialize_cascade(cfg: CascadeConfig) -> dict[str, str]:
    """Serialize a ``CascadeConfig`` to Dataverse ``CascadeConfiguration``."""
    return {
        "Assign": cfg.assign.value,
        "Delete": cfg.delete.value,
        "Merge": cfg.merge.value,
        "Reparent": cfg.reparent.value,
        "Share": cfg.share.value,
        "Unshare": cfg.unshare.value,
    }


def serialize_relationship(
    rel: Relationship,
    *,
    referenced_attribute: Optional[str] = None,
) -> dict[str, Any]:
    """Serialize a ``Relationship`` to a RelationshipDefinitions Deep-Insert payload.

    Args:
        rel: The relationship. For 1:N, ``referencing_entity`` is the owning table
            and ``referenced_entity`` is the parent; ``lookup`` is required. For N:N,
            ``referencing_entity`` is the owning table and ``referenced_entity`` the
            related table.
        referenced_attribute: Primary-id logical name of the referenced entity
            (defaults to ``{referenced_entity}id``). The deployer resolves the real
            value via the client for accuracy.
    """
    if rel.type == "ManyToMany":
        e1 = rel.referencing_entity
        e2 = rel.referenced_entity
        if not e1 or not e2:
            raise ValueError("ManyToMany relationship requires referencing_entity and referenced_entity")
        label1 = serialize_label(rel.display_name) or serialize_label(Label.parse(e1))
        label2 = serialize_label(rel.display_name) or serialize_label(Label.parse(e2))
        return {
            "@odata.type": "Microsoft.Dynamics.CRM.ManyToManyRelationshipMetadata",
            "SchemaName": rel.schema_name,
            "Entity1LogicalName": e1,
            "Entity2LogicalName": e2,
            "IntersectEntityName": rel.intersect_entity_name or rel.schema_name.lower(),
            "Entity1AssociatedMenuConfiguration": {
                "Behavior": "UseLabel",
                "Group": "Details",
                "Label": label1,
                "Order": 10000,
            },
            "Entity2AssociatedMenuConfiguration": {
                "Behavior": "UseLabel",
                "Group": "Details",
                "Label": label2,
                "Order": 10000,
            },
        }

    # OneToMany (creates the lookup column via Deep Insert)
    if not rel.referenced_entity or not rel.referencing_entity:
        raise ValueError("OneToMany relationship requires referenced_entity and referencing_entity")
    if not rel.lookup:
        raise ValueError("OneToMany relationship requires a lookup column")

    ref_attr = referenced_attribute or f"{rel.referenced_entity}id"
    relationship: dict[str, Any] = {
        "@odata.type": "Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata",
        "SchemaName": rel.schema_name,
        "ReferencedAttribute": ref_attr,
        "ReferencedEntity": rel.referenced_entity,
        "ReferencingEntity": rel.referencing_entity,
        "AssociatedMenuConfiguration": {
            "Behavior": "UseCollectionName",
            "Group": "Details",
            "Label": serialize_label(rel.display_name)
            or serialize_label(Label.parse(rel.referenced_entity)),
            "Order": 10000,
        },
        "CascadeConfiguration": serialize_cascade(rel.cascade),
    }

    lookup_payload: dict[str, Any] = {
        "@odata.type": "Microsoft.Dynamics.CRM.LookupAttributeMetadata",
        "SchemaName": rel.lookup.schema_name,
        "AttributeTypeName": {"Value": "LookupType"},
        "DisplayName": serialize_label(rel.lookup.display_name),
        "RequiredLevel": serialize_required_level(rel.lookup.required),
        "Targets": [rel.lookup.target_entity],
    }
    lookup_description = serialize_label(rel.lookup.description)
    if lookup_description:
        lookup_payload["Description"] = lookup_description
    relationship["Lookup"] = lookup_payload

    return {k: v for k, v in relationship.items() if v is not None}


# ============================================================ update / diff


def serialize_updatable(col: Column) -> dict[str, Any]:
    """Return only the PATCH-legal desired properties for ``col``'s type."""
    full = serialize_column(col)
    allowed = _UPDATABLE_BY_TYPE.get(col.type, {"DisplayName", "Description", "RequiredLevel"})
    return {k: v for k, v in full.items() if k in allowed and v is not None}


def _values_equal(desired: Any, existing: Any) -> bool:
    """Semantic equality for attribute property values (labels, required-level, scalars)."""
    if isinstance(desired, dict) and isinstance(existing, dict):
        if "LocalizedLabels" in desired or "LocalizedLabels" in existing:
            return _label_set(desired) == _label_set(existing)
        if "Value" in desired and "Value" in existing:
            return desired.get("Value") == existing.get("Value")
    return desired == existing


def optionset_changed(col: Column, existing_attr: dict[str, Any]) -> bool:
    """Return True if the column's OptionSet differs from the existing attribute.

    Only meaningful for Picklist/Boolean. The deployer uses this to report that a
    manual option-set update is required (the Web API can't PATCH options simply).
    """
    if col.type not in _OPTIONSET_TYPES:
        return False
    existing_has_options = bool(existing_attr.get("OptionSet"))
    if col.type == AttributeType.Picklist:
        return existing_has_options and len(col.options) > 0
    return existing_has_options and col.boolean_labels is not None


def build_attribute_patch(
    col: Column,
    existing_attr: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """Build a PATCH payload for ``col`` against its existing attribute JSON.

    Returns ``None`` when no updatable property differs (idempotent no-op).
    """
    desired = serialize_updatable(col)
    patch: dict[str, Any] = {}
    for key, value in desired.items():
        if not _values_equal(value, existing_attr.get(key)):
            patch[key] = value
    return patch or None
