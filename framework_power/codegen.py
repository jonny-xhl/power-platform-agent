"""
Code generator: ``Table`` object -> Python definition source (framework_power).

The inverse of parsing/importing a definition module. Used by the reverse exporter to
write a ``metadata_py/tables/<schema>.py`` that round-trips: ``Table -> source -> import
-> Table`` reconstructs the original. Emitted source is also what ``deploy`` consumes, so a
reverse-generated file is forward-syncable.
"""

from __future__ import annotations

from typing import Optional

from .models import (
    AlternateKey,
    BooleanLabels,
    CascadeConfig,
    Column,
    Label,
    LookupColumn,
    Option,
    Relationship,
    RequiredLevel,
    Table,
)

_LANGUAGE_ZH = 2052
_LANGUAGE_EN = 1033
_DEFAULT_CASCADE = CascadeConfig()
_CASCADE_MEMBERS = ("assign", "delete", "merge", "reparent", "share", "unshare")


def emit_label(label: Optional[Label]) -> str:
    """Emit a Label literal faithful to the languages present."""
    if label is None or not label.localized:
        return "None"
    locs = label.localized
    codes = {ll.language_code for ll in locs}
    if len(locs) == 1:
        only = locs[0]
        if only.language_code == _LANGUAGE_ZH:
            return f"Label.zh({only.text!r})"
        if only.language_code == _LANGUAGE_EN:
            return f"Label.en({only.text!r})"
    if len(locs) == 2 and codes == {_LANGUAGE_ZH, _LANGUAGE_EN}:
        zh = next(ll.text for ll in locs if ll.language_code == _LANGUAGE_ZH)
        en = next(ll.text for ll in locs if ll.language_code == _LANGUAGE_EN)
        return f"Label.bilingual({zh!r}, {en!r})"
    inner = ", ".join(f"LocalizedLabel({ll.text!r}, {ll.language_code})" for ll in locs)
    return f"Label([{inner}])"


def emit_required(level: RequiredLevel) -> str:
    return f"RequiredLevel.{level.name}"


def _emit_option(opt: Option) -> str:
    return f"Option({opt.value}, {emit_label(opt.label)})"


def _emit_boolean_labels(bl: BooleanLabels) -> str:
    return f"BooleanLabels({emit_label(bl.true_label)}, {emit_label(bl.false_label)})"


def _emit_cascade(cfg: CascadeConfig) -> str:
    parts = [
        f"{m}=Cascade.{getattr(cfg, m).name}"
        for m in _CASCADE_MEMBERS
        if getattr(cfg, m) != getattr(_DEFAULT_CASCADE, m)
    ]
    return f"CascadeConfig({', '.join(parts)})"


def emit_column(col: Column) -> str:
    """Emit a Column(...) call string."""
    parts: list[str] = [repr(col.schema_name), f"AttributeType.{col.type.name}"]
    kwargs: list[str] = [f"display_name={emit_label(col.display_name)}"]
    if col.description is not None:
        kwargs.append(f"description={emit_label(col.description)}")
    if col.required != RequiredLevel.None_:
        kwargs.append(f"required={emit_required(col.required)}")
    if col.is_primary_name:
        kwargs.append("is_primary_name=True")
    if col.ime_mode:
        kwargs.append(f"ime_mode={col.ime_mode!r}")
    if col.is_audit_enabled is not None:
        kwargs.append(f"is_audit_enabled={col.is_audit_enabled!r}")
    if col.is_searchable is not None:
        kwargs.append(f"is_searchable={col.is_searchable!r}")
    if col.max_length is not None:
        kwargs.append(f"max_length={col.max_length!r}")
    if col.format_name is not None:
        kwargs.append(f"format_name={col.format_name!r}")
    if col.format is not None:
        kwargs.append(f"format={col.format!r}")
    if col.date_time_behavior is not None:
        kwargs.append(f"date_time_behavior={col.date_time_behavior!r}")
    if col.precision is not None:
        kwargs.append(f"precision={col.precision!r}")
    if col.precision_source is not None:
        kwargs.append(f"precision_source={col.precision_source}")
    if col.min_value is not None:
        kwargs.append(f"min_value={col.min_value!r}")
    if col.max_value is not None:
        kwargs.append(f"max_value={col.max_value!r}")
    if col.default_value is not None:
        kwargs.append(f"default_value={col.default_value!r}")
    # ADR-009/ADR-014: a Picklist bound to a GLOBAL optionset must carry
    # ``optionset_name`` so deploy emits ``GlobalOptionSet@odata.bind``.
    # ``options`` is still emitted (snapshot for data-dictionary generation),
    # but the name is what decides bind-vs-inline semantics. Without this the
    # reversed source silently downgrades a global optionset to a local one
    # and re-deploying to a fresh environment duplicates the optionset.
    if col.optionset_name:
        kwargs.append(f"optionset_name={col.optionset_name!r}")
    if col.options:
        kwargs.append("options=[" + ", ".join(_emit_option(o) for o in col.options) + "]")
    if col.boolean_labels is not None:
        kwargs.append(f"boolean_labels={_emit_boolean_labels(col.boolean_labels)}")
    if col.max_size_in_kb is not None:
        kwargs.append(f"max_size_in_kb={col.max_size_in_kb!r}")
    return "Column(" + ", ".join(parts + kwargs) + ")"


def _emit_lookup(lookup: LookupColumn) -> str:
    kwargs = [
        repr(lookup.schema_name),
        f"display_name={emit_label(lookup.display_name)}",
        f"target_entity={lookup.target_entity!r}",
    ]
    if lookup.description is not None:
        kwargs.append(f"description={emit_label(lookup.description)}")
    if lookup.required != RequiredLevel.None_:
        kwargs.append(f"required={emit_required(lookup.required)}")
    return "LookupColumn(" + ", ".join(kwargs) + ")"


def emit_alternate_key(key: AlternateKey) -> str:
    """Emit an AlternateKey(...) call string."""
    kwargs = [f"schema_name={key.schema_name!r}", f"columns={key.columns!r}"]
    if key.display_name is not None:
        kwargs.append(f"display_name={emit_label(key.display_name)}")
    return "AlternateKey(" + ", ".join(kwargs) + ")"


def emit_relationship(rel: Relationship) -> str:
    """Emit a Relationship(...) call string."""
    if rel.type == "ManyToMany":
        kwargs = [
            f"schema_name={rel.schema_name!r}",
            'type="ManyToMany"',
            f"referencing_entity={rel.referencing_entity!r}",
            f"referenced_entity={rel.referenced_entity!r}",
        ]
        if rel.intersect_entity_name:
            kwargs.append(f"intersect_entity_name={rel.intersect_entity_name!r}")
        if rel.display_name is not None:
            kwargs.append(f"display_name={emit_label(rel.display_name)}")
        return "Relationship(" + ", ".join(kwargs) + ")"

    kwargs = [
        f"schema_name={rel.schema_name!r}",
        f"referenced_entity={rel.referenced_entity!r}",
        f"referencing_entity={rel.referencing_entity!r}",
    ]
    if rel.lookup is not None:
        kwargs.append(f"lookup={_emit_lookup(rel.lookup)}")
    if rel.cascade != _DEFAULT_CASCADE:
        kwargs.append(f"cascade={_emit_cascade(rel.cascade)}")
    if rel.display_name is not None:
        kwargs.append(f"display_name={emit_label(rel.display_name)}")
    return "Relationship(" + ", ".join(kwargs) + ")"


def table_to_python_source(
    table: Table,
    *,
    header: Optional[list[str]] = None,
) -> str:
    """Emit a full ``<schema>.py`` definition module from a Table object."""
    lines: list[str] = []
    if header:
        lines.extend(header)
    else:
        lines.append(f'"""Definition for {table.schema_name} (generated by framework_power)."""')
    lines.append("")
    lines.append("from framework_power import AlternateKey, Column, LookupColumn, Relationship, Table")
    lines.append(
        "from framework_power.models import ("
        "AttributeType, BooleanLabels, Cascade, CascadeConfig, Label, LocalizedLabel, "
        "Option, RequiredLevel)"
    )
    lines.append("")
    lines.append("TABLE: Table = Table(")
    lines.append(f"    schema_name={table.schema_name!r},")
    lines.append(f"    display_name={emit_label(table.display_name)},")
    if table.display_collection_name is not None:
        lines.append(f"    display_collection_name={emit_label(table.display_collection_name)},")
    if table.description is not None:
        lines.append(f"    description={emit_label(table.description)},")
    if table.ownership_type != "UserOwned":
        lines.append(f"    ownership_type={table.ownership_type!r},")
    if table.has_activities:
        lines.append("    has_activities=True,")
    if table.has_notes:
        lines.append("    has_notes=True,")
    if table.is_quick_create_enabled:
        lines.append("    is_quick_create_enabled=True,")
    if table.is_audit_enabled:
        lines.append("    is_audit_enabled=True,")
    if table.primary_name_column:
        lines.append(f"    primary_name_column={table.primary_name_column!r},")

    lines.append("    columns=[")
    for col in table.columns:
        lines.append(f"        {emit_column(col)},")
    lines.append("    ],")

    if table.relationships:
        lines.append("    relationships=[")
        for rel in table.relationships:
            lines.append(f"        {emit_relationship(rel)},")
        lines.append("    ],")

    if table.alternate_keys:
        lines.append("    alternate_keys=[")
        for key in table.alternate_keys:
            lines.append(f"        {emit_alternate_key(key)},")
        lines.append("    ],")

    lines.append(")")
    return "\n".join(lines) + "\n"
