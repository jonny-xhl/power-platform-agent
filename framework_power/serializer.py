"""
Model -> Dataverse Web API JSON serializer (framework_power).

Pure functions (no client, no I/O) so they are trivially unit-testable. They mirror
the proven per-type update branches (originally from the removed legacy framework)
``_convert_*`` methods, generalized for multi-language labels and full type coverage,
and aligned with the Microsoft Dataverse Web API create payloads shown in the
``dv-metadata`` skill.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .models import (
    AlternateKey,
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

# Per-type mutable keys eligible for the desired-state overlay.
# Transport is a full concrete metadata PUT, not an attribute PATCH.
_COMMON_UPDATABLE = {"IsAuditEnabled", "IsValidForAdvancedFind"}
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
    AttributeType.Picklist: {"DisplayName", "Description", "DefaultFormValue", "RequiredLevel"},
    AttributeType.Boolean: {"DisplayName", "Description", "DefaultValue", "RequiredLevel"},
    AttributeType.DateTime: {"DisplayName", "Description", "Format", "DateTimeBehavior", "RequiredLevel"},
    AttributeType.File: {"DisplayName", "Description", "MaxSizeInKB", "RequiredLevel"},
}

# Attribute types whose OptionSet values are not reconciled by the generic metadata
# update path; deployer reports that option-specific operations are required.
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


def serialize_column(
    col: Column,
    *,
    is_primary_name: bool = False,
    global_optionset_ids: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Serialize a ``Column`` to a Dataverse attribute create payload.

    Args:
        col: The column definition.
        is_primary_name: When True and the column is String, sets ``IsPrimaryName``.
        global_optionset_ids: Resolved ``{optionset_name: MetadataId}`` for referenced
            global optionsets (ADR-014). When a Picklist column's ``optionset_name``
            is present here the payload binds the existing global optionset via
            ``GlobalOptionSet@odata.bind`` — attribute-create endpoints reject an
            inline ``OptionSet`` reference block with ``0x80048403`` (inline blocks
            only accept Local optionsets). Unresolvable names fall back to the legacy
            inline block, preserving the pre-ADR-014 failure surface.
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
    if col.is_audit_enabled is not None:
        attr["IsAuditEnabled"] = {"Value": col.is_audit_enabled}
    if col.is_searchable is not None:
        attr["IsValidForAdvancedFind"] = {"Value": col.is_searchable}

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
        if col.optionset_name:
            # Reference an existing global optionset instead of declaring inline
            # local options. The global optionset itself is managed via the
            # optionsets stage; only the field-to-optionset link is authored here.
            # ADR-014: attribute CREATE must bind the resolved global optionset by
            # MetadataId — inline OptionSet blocks only accept Local optionsets and
            # global references are rejected with 0x80048403. The inline block below
            # is a fallback for unresolved names (e.g. minimal fakes without the
            # optionset API).
            gos_id = (global_optionset_ids or {}).get(col.optionset_name)
            if gos_id:
                attr["GlobalOptionSet@odata.bind"] = f"/GlobalOptionSetDefinitions({gos_id})"
            else:
                attr["OptionSet"] = {
                    "@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata",
                    "IsGlobal": True,
                    "Name": col.optionset_name,
                }
        else:
            attr["OptionSet"] = {
                "@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata",
                "IsGlobal": False,
                "Options": [serialize_option(o.value, o.label) for o in col.options],
            }
        # Dataverse keeps a picklist's default in ``DefaultFormValue`` and uses
        # ``-1`` for "no default".  ``DefaultValue`` is a *Boolean*-only property, so
        # reading or writing that name silently dropped every declared picklist
        # default (ADR-017).  A ``bool`` here is an authoring mistake for a picklist
        # (``False`` coerces to option value 0, which is rarely a real option) — skip
        # it loudly instead of pushing a value the option list may not contain.
        if isinstance(col.default_value, bool):
            logger.warning(
                "Column '%s' is a Picklist with boolean default_value=%r; ignoring it. "
                "Use the integer option value (or remove the default) instead.",
                col.schema_name,
                col.default_value,
            )
        elif col.default_value is not None:
            attr["DefaultFormValue"] = int(col.default_value)

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


def serialize_table_for_create(
    table: Table,
    *,
    global_optionset_ids: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Serialize a ``Table`` to a full EntityDefinitions create payload (entity + Attributes).

    ``global_optionset_ids`` (ADR-014) is passed through to each attribute payload so
    Picklist columns referencing global optionsets bind them by MetadataId.
    """
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
        "IsAuditEnabled": {"Value": bool(table.is_audit_enabled)},
    }

    primary = _resolve_primary_name(table)
    attributes = [
        serialize_column(
            c,
            is_primary_name=(primary is not None and c.schema_name == primary.schema_name),
            global_optionset_ids=global_optionset_ids,
        )
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


def serialize_alternate_key(key: AlternateKey) -> dict[str, Any]:
    """Serialize an alternate key for the EntityDefinitions(...)/Keys collection."""
    payload: dict[str, Any] = {
        "@odata.type": "Microsoft.Dynamics.CRM.EntityKeyMetadata",
        "SchemaName": key.schema_name,
        "KeyAttributes": key.columns,
    }
    display = serialize_label(key.display_name)
    if display:
        payload["DisplayName"] = display
    return payload


def serialize_updatable(col: Column) -> dict[str, Any]:
    """Return mutable desired properties eligible for the metadata PUT overlay."""
    full = serialize_column(col)
    allowed = _UPDATABLE_BY_TYPE.get(
        col.type, {"DisplayName", "Description", "RequiredLevel"}
    ) | _COMMON_UPDATABLE
    return {k: v for k, v in full.items() if k in allowed and v is not None}


def _values_equal(desired: Any, existing: Any) -> bool:
    """Semantic equality for attribute property values (labels, required-level, scalars)."""
    if isinstance(desired, dict) and isinstance(existing, dict):
        if "LocalizedLabels" in desired or "LocalizedLabels" in existing:
            return _label_set(desired) == _label_set(existing)
        if "Value" in desired and "Value" in existing:
            return desired.get("Value") == existing.get("Value")
    return desired == existing


def _localized_label_map(label_dict: dict[str, Any] | None) -> dict[int, str]:
    """Reduce a Dataverse Label object to ``LanguageCode -> text``.

    Typed metadata normally exposes ``LocalizedLabels``. ``UserLocalizedLabel`` is
    accepted as a fallback for reduced test doubles and tenant-specific responses.
    """
    if not label_dict:
        return {}
    labels = list(label_dict.get("LocalizedLabels") or [])
    user_label = label_dict.get("UserLocalizedLabel")
    if user_label:
        labels.append(user_label)
    result: dict[int, str] = {}
    for item in labels:
        code = item.get("LanguageCode")
        text = item.get("Label")
        if code is not None and text is not None:
            result[int(code)] = str(text)
    return result


def build_picklist_option_diff(
    col: Column,
    existing_attr: dict[str, Any],
) -> dict[str, Any]:
    """Compute a non-destructive local-Picklist option diff.

    Desired values missing online are returned under ``insert``. Existing values whose
    authored language labels differ are returned under ``update``. Online-only values
    are reported under ``remote_only`` and deliberately retained: removing option values
    can invalidate existing records and therefore requires an explicit destructive flow.

    Only authored languages participate in label comparison. This means an English +
    Chinese definition can update those labels without erasing an additional Japanese
    label already present online.
    """
    if col.type != AttributeType.Picklist:
        return {"insert": [], "update": [], "unchanged": [], "remote_only": []}

    desired_values = [option.value for option in col.options]
    duplicates = sorted({value for value in desired_values if desired_values.count(value) > 1})
    if duplicates:
        raise ValueError(
            f"Picklist '{col.schema_name}' has duplicate option values: {duplicates}."
        )

    option_set = existing_attr.get("OptionSet") or {}
    if option_set.get("IsGlobal") is True:
        raise ValueError(
            f"Picklist '{col.schema_name}' is global online; local option actions are unsafe."
        )
    existing_options = {
        option.get("Value"): option
        for option in (option_set.get("Options") or [])
        if option.get("Value") is not None
    }
    desired_set = set(desired_values)
    result: dict[str, Any] = {
        "insert": [],
        "update": [],
        "unchanged": [],
        "remote_only": sorted(value for value in existing_options if value not in desired_set),
    }

    for option in col.options:
        label = serialize_label(option.label)
        desired_labels = _localized_label_map(label)
        existing = existing_options.get(option.value)
        if existing is None:
            result["insert"].append(
                {
                    "value": option.value,
                    "label": label,
                    "languages": sorted(desired_labels),
                }
            )
            continue

        current_labels = _localized_label_map(existing.get("Label"))
        changed_languages = sorted(
            code for code, text in desired_labels.items() if current_labels.get(code) != text
        )
        if changed_languages:
            result["update"].append(
                {
                    "value": option.value,
                    "label": label,
                    "languages": changed_languages,
                }
            )
        else:
            result["unchanged"].append(option.value)
    return result


def optionset_changed(col: Column, existing_attr: dict[str, Any]) -> bool:
    """Backward-compatible coarse OptionSet change predicate.

    Local Picklists now use :func:`build_picklist_option_diff` for actionable inserts
    and label updates. Boolean label updates remain outside the generic metadata PUT path.
    """
    if col.type == AttributeType.Picklist:
        diff = build_picklist_option_diff(col, existing_attr)
        return bool(diff["insert"] or diff["update"])
    if col.type == AttributeType.Boolean:
        return bool(existing_attr.get("OptionSet")) and col.boolean_labels is not None
    return False


def build_attribute_patch(
    col: Column,
    existing_attr: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """Build the mutable-property overlay for an existing attribute.

    The historical function name is retained for API compatibility. The returned mapping
    is not sent as an HTTP PATCH: the client overlays it on typed current metadata and sends
    the complete concrete definition with PUT. Returns ``None`` for an idempotent no-op.
    """
    desired = serialize_updatable(col)
    patch: dict[str, Any] = {}
    for key, value in desired.items():
        if not _values_equal(value, existing_attr.get(key)):
            patch[key] = value
    return patch or None
