"""
Reverse exporter: Dataverse environment -> ``Table`` (framework_power).

Builds a FULL snapshot of a table (all non-virtual attributes + relationships) from live
metadata so it can be written to ``metadata_py/tables/<schema>.py`` via :mod:`codegen`.
The same file is then forward-syncable: ``deploy`` skips standard/system (non-custom)
items, acting only on publisher-prefixed ones.

Virtual/system/non-deployable attributes are excluded (they cannot be created and are not
real columns): primary-id, computed/logical/virtual, ``*_base``, and system lookup-like
types (Owner/Customer/PartyList/State/Status/Image/Uniqueidentifier/EntityName).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .models import (
    AlternateKey,
    AttributeType,
    BooleanLabels,
    Cascade,
    CascadeConfig,
    Column,
    Label,
    LocalizedLabel,
    LookupColumn,
    Option,
    Relationship,
    RequiredLevel,
    Table,
)

logger = logging.getLogger(__name__)

TYPE_TO_ENUM: dict[str, AttributeType] = {
    "String": AttributeType.String,
    "Integer": AttributeType.Integer,
    "BigInt": AttributeType.BigInt,
    "Money": AttributeType.Money,
    "Decimal": AttributeType.Decimal,
    "Double": AttributeType.Double,
    "Picklist": AttributeType.Picklist,
    "Boolean": AttributeType.Boolean,
    "Memo": AttributeType.Memo,
    "DateTime": AttributeType.DateTime,
    "File": AttributeType.File,
}

# Attribute types that are not real deployable columns.
_SKIP_TYPES = {
    "Owner", "Customer", "PartyList", "State", "Status", "EntityName", "Image",
    "Uniqueidentifier", "Virtual", "ManagedProperty", "CalendarRules",
}

_CASCADE_MAP: dict[str, Cascade] = {
    "Active": Cascade.Active,
    "Cascade": Cascade.Cascade_,
    "NoCascade": Cascade.NoCascade,
    "RemoveLink": Cascade.RemoveLink,
    "Restrict": Cascade.Restrict,
}

_REQUIRED_MAP: dict[str, RequiredLevel] = {
    "ApplicationRequired": RequiredLevel.ApplicationRequired,
    "Recommended": RequiredLevel.Recommended,
}


def _extract_label(label_obj: Optional[dict[str, Any]]) -> Optional[Label]:
    """Build a Label from a Dataverse Label object (LocalizedLabels or UserLocalizedLabel)."""
    if not label_obj:
        return None
    locs = label_obj.get("LocalizedLabels") or []
    pairs = [(loc.get("Label"), loc.get("LanguageCode")) for loc in locs if loc.get("Label")]
    if not pairs:
        ull = label_obj.get("UserLocalizedLabel")
        if ull and ull.get("Label"):
            pairs = [(ull.get("Label"), ull.get("LanguageCode") or 1033)]
    if not pairs:
        return None
    return Label([LocalizedLabel(text, code or 2052) for text, code in pairs])


def _is_virtual(attr: dict[str, Any]) -> bool:
    """True for computed/logical/virtual/derived attributes (not real deployable columns)."""
    if attr.get("AttributeOf") or attr.get("IsLogical") or attr.get("IsComputed"):
        return True
    if attr.get("AggregateType"):
        return True
    if "Virtual" in (attr.get("@odata.type") or ""):
        return True
    return False


def _required(value: Optional[str]) -> RequiredLevel:
    return _REQUIRED_MAP.get(value or "", RequiredLevel.None_)


def _cascade_from_json(cfg: Optional[dict[str, Any]]) -> CascadeConfig:
    if not cfg:
        return CascadeConfig()

    def m(v: Optional[str]) -> Cascade:
        return _CASCADE_MAP.get(v or "", Cascade.NoCascade)

    return CascadeConfig(
        assign=m(cfg.get("Assign")),
        delete=m(cfg.get("Delete")),
        merge=m(cfg.get("Merge")),
        reparent=m(cfg.get("Reparent")),
        share=m(cfg.get("Share")),
        unshare=m(cfg.get("Unshare")),
    )


def _attr_to_column(
    attr: dict[str, Any],
    primary_name_logical: Optional[str],
) -> tuple[Optional[Column], Optional[dict[str, Any]]]:
    """Map an env attribute to a Column, or return its raw dict if it's a Lookup, or (None,None)."""
    logical = attr.get("LogicalName")
    schema = attr.get("SchemaName") or logical
    atype = attr.get("AttributeType")
    odata = attr.get("@odata.type") or ""

    if atype == "Lookup":
        return None, attr

    # File columns report AttributeType "Virtual" but carry FileAttributeMetadata in
    # @odata.type; resolve them BEFORE the Virtual/Image skip below.
    member: Optional[AttributeType] = None
    if "FileAttributeMetadata" in odata:
        member = AttributeType.File
    elif "ImageAttributeMetadata" in odata:
        return None, None  # Image not supported
    elif atype in _SKIP_TYPES:
        return None, None
    else:
        member = TYPE_TO_ENUM.get(atype or "")

    if _is_virtual(attr) or attr.get("IsPrimaryId"):
        return None, None
    if schema and schema.lower().endswith("_base"):
        return None, None
    if member is None:
        logger.debug(f"reverse: skipping attribute {schema!r} (unsupported type {atype!r})")
        return None, None

    kwargs: dict[str, Any] = {
        "schema_name": schema,
        "type": member,
        "display_name": _extract_label(attr.get("DisplayName")) or Label.zh(schema or ""),
        "required": _required((attr.get("RequiredLevel") or {}).get("Value")),
    }
    audit = attr.get("IsAuditEnabled")
    if audit is not None:
        kwargs["is_audit_enabled"] = bool(audit.get("Value") if isinstance(audit, dict) else audit)
    searchable = attr.get("IsValidForAdvancedFind")
    if searchable is not None:
        kwargs["is_searchable"] = bool(
            searchable.get("Value") if isinstance(searchable, dict) else searchable
        )
    desc = _extract_label(attr.get("Description"))
    if desc:
        kwargs["description"] = desc
    if attr.get("IsPrimaryName") or (primary_name_logical and logical == primary_name_logical):
        kwargs["is_primary_name"] = True
    if attr.get("MaxLength") is not None:
        kwargs["max_length"] = attr.get("MaxLength")
    if attr.get("MaxSizeInKB") is not None:
        kwargs["max_size_in_kb"] = attr.get("MaxSizeInKB")
    fmt_name = (attr.get("FormatName") or {}).get("Value")
    if fmt_name:
        kwargs["format_name"] = fmt_name
    if attr.get("Format"):
        kwargs["format"] = attr.get("Format")
    behavior = (attr.get("DateTimeBehavior") or {}).get("Value")
    if behavior:
        kwargs["date_time_behavior"] = behavior
    if attr.get("Precision") is not None:
        kwargs["precision"] = attr.get("Precision")
    if attr.get("PrecisionSource") is not None:
        kwargs["precision_source"] = attr.get("PrecisionSource")
    if attr.get("MinValue") is not None:
        kwargs["min_value"] = attr.get("MinValue")
    if attr.get("MaxValue") is not None:
        kwargs["max_value"] = attr.get("MaxValue")

    if member is AttributeType.Picklist:
        optionset = attr.get("OptionSet") or {}
        os_name = optionset.get("Name")
        # Only a TRUE global optionset (IsGlobal=True) counts as a reference;
        # entity-bound optionsets also carry a non-empty Name ("{entity}_{field}",
        # auto-generated by Dataverse) but are rendered inline. Name alone is
        # NOT a discriminator — the typed PicklistAttributeMetadata query returns
        # OptionSet data for every picklist (ADR-010).
        is_global = bool(optionset.get("IsGlobal"))
        # Always capture options from the API response (used for optionset doc generation).
        opts = [
            Option(o.get("Value"), _extract_label(o.get("Label")) or Label.zh(str(o.get("Value"))))
            for o in (optionset.get("Options") or [])
        ]
        if os_name and is_global:
            # Global optionset reference — store the name AND the options.
            # _format_picklist_note shows a document link (not inline) when
            # optionset_name is set, preserving ADR-009's DRY design.
            # The options data is needed by build_prefetched_optionsets() to
            # generate the optionset documentation files.
            kwargs["optionset_name"] = os_name
            if opts:
                kwargs["options"] = opts
        else:
            # Local / entity-bound (inline) optionset — populate options directly.
            if opts:
                kwargs["options"] = opts
        # Picklist defaults live in ``DefaultFormValue`` — not ``DefaultValue``, which
        # is a Boolean-only property (ADR-017).  Dataverse reports ``-1`` for "no
        # default", so it must normalise back to ``None``; otherwise the round-trip
        # would push a bogus ``-1`` default onto the next deploy.
        raw_default = attr.get("DefaultFormValue")
        if raw_default is not None and int(raw_default) != -1:
            kwargs["default_value"] = int(raw_default)
    elif member is AttributeType.Boolean:
        optionset = attr.get("OptionSet") or {}
        true_label = _extract_label((optionset.get("TrueOption") or {}).get("Label"))
        false_label = _extract_label((optionset.get("FalseOption") or {}).get("Label"))
        if true_label and false_label:
            kwargs["boolean_labels"] = BooleanLabels(true_label, false_label)
        if attr.get("DefaultValue") is not None:
            kwargs["default_value"] = bool(attr.get("DefaultValue"))

    return Column(**kwargs), None


def _build_relationships(
    rels: list[dict[str, Any]],
    lookups: dict[str, dict[str, Any]],
    logical_name: str,
) -> list[Relationship]:
    """Reconstruct this table's relationships (1:N outbound lookups + N:N)."""
    out: list[Relationship] = []
    seen: set[str] = set()
    for rel in rels:
        odata = rel.get("@odata.type") or ""
        schema_name = rel.get("SchemaName")
        if not schema_name or schema_name in seen:
            continue

        if "ManyToMany" in odata:
            e1 = rel.get("Entity1LogicalName")
            e2 = rel.get("Entity2LogicalName")
            if logical_name not in (e1, e2):
                continue  # not about this table
            other = e2 if e1 == logical_name else e1
            seen.add(schema_name)
            out.append(
                Relationship(
                    schema_name=schema_name,
                    type="ManyToMany",
                    referencing_entity=logical_name,
                    referenced_entity=other,
                    intersect_entity_name=rel.get("IntersectEntityName"),
                )
            )
            continue

        # OneToMany / ManyToOne
        if rel.get("ReferencingEntity") != logical_name:
            continue  # lookup lives on another entity -> not for this file
        referenced = rel.get("ReferencedEntity")
        referencing_attr = str(rel.get("ReferencingAttribute") or "")
        la = lookups.get(referencing_attr)
        if not la:
            logger.debug(f"reverse: skipping relationship {schema_name!r} (no lookup attr)")
            continue
        targets = la.get("Targets") or []
        target = str(targets[0]) if targets else (referenced or logical_name)
        lookup_col = LookupColumn(
            schema_name=str(la.get("SchemaName") or referencing_attr),
            display_name=_extract_label(la.get("DisplayName")) or Label.zh(referenced or ""),
            target_entity=target,
            required=_required((la.get("RequiredLevel") or {}).get("Value")),
        )
        seen.add(schema_name)
        out.append(
            Relationship(
                schema_name=schema_name,
                referenced_entity=referenced,
                referencing_entity=logical_name,
                lookup=lookup_col,
                cascade=_cascade_from_json(rel.get("CascadeConfiguration")),
            )
        )
    return out


def reverse_table(client: Any, logical_name: str) -> Table:
    """Build a full-snapshot ``Table`` from the live Dataverse environment.

    Args:
        client: An authenticated ``DataverseClient``.
        logical_name: The table's logical name (e.g. ``contact``).

    Returns:
        A ``Table`` populated with all non-virtual attributes + this table's relationships.
    """
    entity = client.get_entity_metadata(logical_name)
    attrs = client.get_attributes(logical_name)
    rels = client.get_relationships(logical_name)

    # Fetch OptionSet data for Picklist/Boolean attributes.
    # The polymorphic /Attributes endpoint doesn't include the OptionSet navigation
    # property, so we merge it from typed derived-type queries.
    optionset_map = client.get_optionset_attributes(logical_name)
    for attr in attrs:
        logical = attr.get("LogicalName")
        if logical and logical in optionset_map and "OptionSet" not in attr:
            attr["OptionSet"] = optionset_map[logical]["OptionSet"]

    primary_name_logical = entity.get("PrimaryNameAttribute")

    columns: list[Column] = []
    lookups: dict[str, dict[str, Any]] = {}
    for attr in attrs:
        col, lookup_raw = _attr_to_column(attr, primary_name_logical)
        if col is not None:
            columns.append(col)
        elif lookup_raw is not None:
            logical = lookup_raw.get("LogicalName")
            if logical:
                lookups[logical] = lookup_raw

    relationships = _build_relationships(rels, lookups, logical_name)
    keys = client.get_entity_keys(logical_name)
    alternate_keys = [
        AlternateKey(
            schema_name=key.get("SchemaName") or key.get("LogicalName"),
            columns=list(key.get("KeyAttributes") or []),
            display_name=_extract_label(key.get("DisplayName")),
        )
        for key in keys
        if key.get("SchemaName") or key.get("LogicalName")
    ]

    display = _extract_label(entity.get("DisplayName")) or Label.zh(logical_name)
    return Table(
        schema_name=entity.get("SchemaName") or logical_name,
        display_name=display,
        display_collection_name=_extract_label(entity.get("DisplayCollectionName")),
        description=_extract_label(entity.get("Description")),
        ownership_type=entity.get("OwnershipType") or "UserOwned",
        has_activities=bool(entity.get("HasActivities")),
        has_notes=bool(entity.get("HasNotes")),
        is_audit_enabled=bool((entity.get("IsAuditEnabled") or {}).get("Value")),
        columns=columns,
        relationships=relationships,
        alternate_keys=alternate_keys,
    )
