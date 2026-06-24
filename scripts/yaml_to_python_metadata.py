#!/usr/bin/env python3
"""
Migrate legacy table YAML (metadata/tables/*.yaml) -> framework_power Python
definitions (metadata_py/tables/*.py).

This is the Phase 2 migration tool: it moves existing table definitions from the YAML
toolchain into the Python source-of-truth home so ``framework_power`` can deploy them.

Behavior notes:
- Schema names are preserved EXACTLY (legacy entities already exist in Dataverse with
  lowercase logical names). ``framework_power lint`` will warn about non-PascalCase for
  these -- that is expected and correct for migrated legacy tables.
- Labels become Chinese-only (``Label.zh``); the YAML carries no English display names.
  Add ``Label.bilingual`` later where English names are known.
- Lookup attributes are folded into their Relationship (Deep Insert), matching the
  framework_power model.

Usage:
    python scripts/yaml_to_python_metadata.py metadata/tables/payment_recognition.yaml
    python scripts/yaml_to_python_metadata.py --all            # all metadata/tables/*.yaml
    python scripts/yaml_to_python_metadata.py --all -o metadata_py/tables
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

# YAML attribute type -> framework_power AttributeType member name.
TYPE_MAP: dict[str, str] = {
    "String": "String",
    "Integer": "Integer",
    "BigInt": "BigInt",
    "Money": "Money",
    "Decimal": "Decimal",
    "Double": "Double",
    "Picklist": "Picklist",
    "Boolean": "Boolean",
    "Memo": "Memo",
    "DateTime": "DateTime",
    "File": "File",
}
# Types that are not emitted as Columns (auto-created or handled via relationships).
SKIP_TYPES = {"Lookup", "Uniqueidentifier", "Customer", "Owner", "PartyList"}

# YAML cascade value -> Cascade enum member name.
CASCADE_MEMBER: dict[str, str] = {
    "Active": "Active",
    "Cascade": "Cascade_",
    "NoCascade": "NoCascade",
    "RemoveLink": "RemoveLink",
    "Restrict": "Restrict",
}


def _prec_source(val: Any) -> int | None:
    """Normalize YAML precision_source ('transactioncurrency' -> 2)."""
    if val is None:
        return None
    if isinstance(val, int):
        return val
    if str(val).lower() in ("transactioncurrency", "currency"):
        return 2
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _cascade_attr(yval: Any) -> str:
    if yval is None:
        return "Cascade.NoCascade"
    return "Cascade." + CASCADE_MEMBER.get(str(yval), "NoCascade")


def _label_zh(text: str | None) -> str:
    return f"Label.zh({text!r})" if text else "None"


def gen_column(a: dict[str, Any]) -> str | None:
    """Generate a Column(...) call string from a YAML attribute, or None to skip."""
    ytype = a.get("type", "String")
    if ytype in SKIP_TYPES:
        return None
    member = TYPE_MAP.get(ytype)
    if member is None:
        # Unknown type -> emit a TODO comment so it is visible, skip the column.
        return f"# TODO skipped '{a.get('schema_name')}': unsupported type {ytype!r}"

    parts: list[str] = [f"{a['schema_name']!r}", f"AttributeType.{member}"]
    kwargs: list[str] = [f"display_name={_label_zh(a.get('display_name'))}"]
    if a.get("description"):
        kwargs.append(f"description={_label_zh(a.get('description'))}")
    kwargs.append(
        "required=RequiredLevel.ApplicationRequired" if a.get("required") else "required=RequiredLevel.None_"
    )
    if a.get("is_primary_name"):
        kwargs.append("is_primary_name=True")
    if a.get("max_length") is not None:
        kwargs.append(f"max_length={a['max_length']!r}")
    if a.get("precision") is not None:
        kwargs.append(f"precision={a['precision']!r}")
    ps = _prec_source(a.get("precision_source"))
    if ps is not None:
        kwargs.append(f"precision_source={ps}")
    if a.get("min_value") is not None:
        kwargs.append(f"min_value={a['min_value']!r}")
    if a.get("max_value") is not None:
        kwargs.append(f"max_value={a['max_value']!r}")

    if member == "DateTime":
        if a.get("date_only"):
            kwargs.extend(['date_time_behavior="DateOnly"', 'format="DateOnly"'])
        elif a.get("behavior"):
            b = a["behavior"]
            fmt = "DateOnly" if b == "DateOnly" else "DateAndTime"
            kwargs.extend([f"date_time_behavior={b!r}", f"format={fmt!r}"])

    if member == "Picklist" and a.get("options"):
        opts = ", ".join(f"Option({o['value']}, Label.zh({o['label']!r}))" for o in a["options"])
        kwargs.append(f"options=[{opts}]")
        if a.get("default_value") is not None:
            kwargs.append(f"default_value={a['default_value']!r}")

    if member == "Boolean":
        if a.get("default_value") is not None:
            kwargs.append(f"default_value={bool(a['default_value'])!r}")
        kwargs.append("boolean_labels=BooleanLabels(Label.zh('是'), Label.zh('否'))")

    return "Column(" + ", ".join(parts + kwargs) + ")"


def gen_relationship(r: dict[str, Any], lookups: dict[str, dict], logical: str) -> str:
    """Generate a Relationship(...) call string from a YAML relationship."""
    schema_name = r["schema_name"]
    rel_type = r.get("relationship_type", "ManyToOne")

    if rel_type == "ManyToMany":
        kwargs = [
            f"schema_name={schema_name!r}",
            'type="ManyToMany"',
            f"referencing_entity={logical!r}",
            f"referenced_entity={r['related_entity']!r}",
        ]
        if r.get("display_name"):
            kwargs.append(f"display_name={_label_zh(r['display_name'])}")
        return "Relationship(" + ", ".join(kwargs) + ")"

    # 1:N (ManyToOne / OneToMany) -- current entity holds the lookup (mirrors legacy behavior).
    ref_attr = r.get("referencing_attribute")
    la = lookups.get(ref_attr, {})
    cascade = (
        "CascadeConfig("
        f"assign={_cascade_attr(r.get('cascade_assign'))}, "
        f"delete={_cascade_attr(r.get('cascade_delete'))}, "
        f"reparent={_cascade_attr(r.get('cascade_reparent'))}, "
        f"share={_cascade_attr(r.get('cascade_share'))}, "
        f"unshare={_cascade_attr(r.get('cascade_unshare'))})"
    )
    lookup = "None"
    if la:
        lookup_parts = [
            f"{la['schema_name']!r}",
            f"display_name={_label_zh(la.get('display_name'))}",
            f"target_entity={la.get('target')!r}",
        ]
        if la.get("description"):
            lookup_parts.append(f"description={_label_zh(la.get('description'))}")
        lookup_parts.append(
            "required=RequiredLevel.ApplicationRequired" if la.get("required") else "required=RequiredLevel.None_"
        )
        lookup = "LookupColumn(" + ", ".join(lookup_parts) + ")"
    else:
        # No matching lookup_attribute: a 1:N relationship needs one. Comment the whole
        # entry out (rather than emitting invalid Python) so it is visible for manual fix.
        return (
            f"# TODO: relationship {schema_name!r} (1:N) has no lookup_attribute in YAML; "
            "define its LookupColumn manually"
        )

    kwargs = [
        f"schema_name={schema_name!r}",
        f"referenced_entity={r['related_entity']!r}",
        f"referencing_entity={logical!r}",
        f"lookup={lookup}",
        f"cascade={cascade}",
    ]
    return "Relationship(" + ", ".join(kwargs) + ")"


def gen_table_source(yaml_dict: dict[str, Any], source_name: str) -> str:
    """Generate the full Python definition file text from a parsed YAML table dict."""
    schema = yaml_dict.get("schema") or {}
    logical = schema.get("schema_name")
    if not logical:
        raise ValueError(f"{source_name}: missing schema.schema_name")

    attrs = yaml_dict.get("attributes") or []
    lookups = {la["schema_name"]: la for la in (yaml_dict.get("lookup_attributes") or [])}
    rels = yaml_dict.get("relationships") or []
    options = schema.get("options") or {}

    lines: list[str] = []
    lines.append(f'"""Migrated from metadata/tables/{source_name} -> framework_power definition.')
    lines.append('')
    lines.append('Schema names are preserved as-is (legacy lowercase). Add Label.bilingual +')
    lines.append('English names where known. Regenerate via scripts/yaml_to_python_metadata.py.')
    lines.append('"""')
    lines.append("")
    lines.append("from framework_power import Column, LookupColumn, Relationship, Table")
    lines.append(
        "from framework_power.models import ("
        "AttributeType, BooleanLabels, Cascade, CascadeConfig, Label, Option, RequiredLevel)"
    )
    lines.append("")
    lines.append("TABLE: Table = Table(")
    lines.append(f"    schema_name={logical!r},")
    lines.append(f"    display_name={_label_zh(schema.get('display_name'))},")
    if schema.get("description"):
        lines.append(f"    description={_label_zh(schema.get('description'))},")
    if schema.get("ownership_type"):
        lines.append(f"    ownership_type={schema['ownership_type']!r},")
    if schema.get("has_activities"):
        lines.append("    has_activities=True,")
    if schema.get("has_notes"):
        lines.append("    has_notes=True,")
    if schema.get("is_audit_enabled"):
        lines.append("    is_audit_enabled=True,")
    if options.get("enable_quick_create"):
        lines.append("    is_quick_create_enabled=True,")

    lines.append("    columns=[")
    for a in attrs:
        col = gen_column(a)
        if col is None:
            continue
        lines.append(f"        {col},")
    lines.append("    ],")

    if rels:
        lines.append("    relationships=[")
        for r in rels:
            lines.append(f"        {gen_relationship(r, lookups, logical)},")
        lines.append("    ],")

    lines.append(")")
    return "\n".join(lines) + "\n"


def convert_file(yaml_path: Path, out_dir: Path) -> Path | None:
    """Convert one YAML file; return the written output path, or None if skipped."""
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    attrs = data.get("attributes") or []
    has_string = any(a.get("type") == "String" for a in attrs)
    if not has_string:
        # framework_power requires a String primary-name column; stub YAMLs without one
        # cannot be deployed meaningfully and would fail lint. Skip with a clear notice.
        print(f"[skip] {yaml_path}: no String column (no primary name) -- needs manual definition")
        return None
    source = gen_table_source(data, yaml_path.name)
    logical = (data.get("schema") or {}).get("schema_name", yaml_path.stem)
    out_path = out_dir / f"{logical}.py"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(source)
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate table YAML -> framework_power Python definitions.")
    parser.add_argument("yaml", nargs="?", help="Path to a single table YAML.")
    parser.add_argument("--all", action="store_true", help="Convert all metadata/tables/*.yaml.")
    parser.add_argument("-o", "--output", default="metadata_py/tables", help="Output directory.")
    parser.add_argument("--input-dir", default="metadata/tables", help="Input directory for --all.")
    args = parser.parse_args(argv)

    if not args.all and not args.yaml:
        parser.error("Provide a YAML path or --all.")

    out_dir = Path(args.output)
    targets: list[Path] = (
        sorted(Path(args.input_dir).glob("*.yaml")) if args.all else [Path(args.yaml)]
    )

    failures = 0
    for yaml_path in targets:
        try:
            out_path = convert_file(yaml_path, out_dir)
            if out_path:
                print(f"[ok] {yaml_path} -> {out_path}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"[FAIL] {yaml_path}: {e}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
