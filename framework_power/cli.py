"""
Command-line interface for framework_power.

Drives the 需求 -> definition -> sync pipeline from one entry point:

    python -m framework_power list
    python -m framework_power show new_projectbudget
    python -m framework_power lint new_projectbudget
    python -m framework_power plan new_projectbudget --env dev
    python -m framework_power deploy new_projectbudget --env dev
    python -m framework_power deploy-all --env dev

Definitions are discovered under ``metadata_py/tables/`` (each ``<schema>.py`` exposes
``TABLE``). ``lint`` runs offline (no network); ``plan`` is a read-only dry run;
``deploy``/``deploy-all`` write to Dataverse.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .deployer import deploy_table, plan_table
from .lint import ERROR, INFO, WARNING, has_errors, lint_table
from .registry import DEFAULT_DEFINITIONS_DIR, deploy_order, discover_definitions, get_definition
from .runtime import get_client

PUBLISHERS_CONFIG = "config/publishers.yaml"


def _publisher_prefix(config_path: str = PUBLISHERS_CONFIG) -> str:
    """Read the current publisher prefix from config/publishers.yaml (default 'new')."""
    try:
        import yaml
        from pathlib import Path

        if not Path(config_path).exists():
            return "new"
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        current = data.get("current")
        publishers = data.get("publishers", {})
        if current and current in publishers:
            return publishers[current].get("prefix", "new")
    except Exception:  # noqa: BLE001
        pass
    return "new"


def _print_json(obj: object) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


# ----------------------------------------------------------------- commands


def cmd_list(args: argparse.Namespace) -> int:
    defs = discover_definitions(args.definitions_dir)
    if not defs:
        print(f"No definitions found under '{args.definitions_dir}'.")
        return 0
    print(f"{'name':32} {'schema_name':28} cols rels  source")
    for name, defn in defs.items():
        t = defn.table
        print(
            f"{name:32} {t.schema_name:28} {len(t.columns):4} {len(t.relationships):4}  {defn.source}"
        )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    defn = get_definition(args.name, args.definitions_dir)
    from .serializer import serialize_relationship, serialize_table_for_create

    payload = serialize_table_for_create(defn.table)
    rels = [
        serialize_relationship(r, referenced_attribute=f"{r.referenced_entity}id")
        for r in defn.table.relationships
    ]
    _print_json({"entity": payload, "relationships": rels})
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    prefix = _publisher_prefix()
    if args.name:
        defn = get_definition(args.name, args.definitions_dir)
        targets = {defn.name: defn.table}
    else:
        targets = {n: d.table for n, d in discover_definitions(args.definitions_dir).items()}

    any_errors = False
    for name, table in targets.items():
        issues = lint_table(table, prefix=prefix)
        errors = [i for i in issues if i.severity == ERROR]
        warnings = [i for i in issues if i.severity == WARNING]
        infos = [i for i in issues if i.severity == INFO]
        status = "FAIL" if errors else "ok"
        print(f"[{status}] {name}  ({len(errors)} err, {len(warnings)} warn, {len(infos)} info)")
        for sev in (ERROR, WARNING, INFO):
            for i in [x for x in issues if x.severity == sev]:
                print(f"    {sev}: {i.message}")
        if has_errors(issues):
            any_errors = True
    return 1 if any_errors else 0


def cmd_plan(args: argparse.Namespace) -> int:
    defn = get_definition(args.name, args.definitions_dir)
    client = get_client(args.env)
    _print_json(plan_table(client, defn.table, prefix=_publisher_prefix()))
    return 0


def cmd_deploy(args: argparse.Namespace) -> int:
    defn = get_definition(args.name, args.definitions_dir)
    client = get_client(args.env)
    _print_json(deploy_table(client, defn.table, prefix=_publisher_prefix()))
    return 0


def cmd_deploy_all(args: argparse.Namespace) -> int:
    defs = discover_definitions(args.definitions_dir)
    if not defs:
        print(f"No definitions found under '{args.definitions_dir}'.")
        return 0
    order = deploy_order(defs)
    print(f"Deploy order: {order}")
    client = get_client(args.env)
    prefix = _publisher_prefix()
    summary = []
    for name in order:
        print(f"\n=== deploying {name} ===")
        result = deploy_table(client, defs[name].table, prefix=prefix)
        summary.append({"name": name, "entity": result["entity"].get("action")})
        _print_json(result)
    print("\n=== summary ===")
    _print_json(summary)
    return 0


def cmd_reverse(args: argparse.Namespace) -> int:
    from .codegen import table_to_python_source
    from .reverse import reverse_table

    client = get_client(args.env)
    table = reverse_table(client, args.name)
    out_path = Path(args.output) if args.output else Path(args.definitions_dir) / f"{args.name}.py"
    header = [
        f'"""Reverse-exported from Dataverse ({args.name!r}) by framework_power.',
        "",
        "Full snapshot (custom + standard attributes + relationships) for local reference,",
        "diffing, and AI constraint. Forward `deploy` skips standard (non-custom) items",
        "automatically, so this same file is safe to sync.",
        "",
        "Regenerate: python -m framework_power reverse " + f"{args.name} --env <env>",
        '"""',
    ]
    source = table_to_python_source(table, header=header)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(source, encoding="utf-8")
    print(
        f"[ok] reverse {args.name} -> {out_path} "
        f"({len(table.columns)} cols, {len(table.relationships)} rels)"
    )
    return 0


# ----------------------------------------------------------------- entry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="framework_power",
        description="Deploy Dataverse tables from Python definitions (framework_power).",
    )
    parser.add_argument(
        "--definitions-dir",
        default=DEFAULT_DEFINITIONS_DIR,
        help=f"Definitions directory (default: {DEFAULT_DEFINITIONS_DIR}).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List discovered definitions.").set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="Print the serialized Web API payload (no network).")
    p_show.add_argument("name")
    p_show.set_defaults(func=cmd_show)

    p_lint = sub.add_parser("lint", help="Offline convention check (no network).")
    p_lint.add_argument("name", nargs="?", help="Definition name; omit to lint all.")
    p_lint.set_defaults(func=cmd_lint)

    p_plan = sub.add_parser("plan", help="Read-only dry run against an environment.")
    p_plan.add_argument("name")
    p_plan.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p_plan.set_defaults(func=cmd_plan)

    p_dep = sub.add_parser("deploy", help="Deploy (create/sync) a definition to Dataverse.")
    p_dep.add_argument("name")
    p_dep.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p_dep.set_defaults(func=cmd_deploy)

    p_all = sub.add_parser("deploy-all", help="Deploy all definitions in dependency order.")
    p_all.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p_all.set_defaults(func=cmd_deploy_all)

    p_rev = sub.add_parser(
        "reverse",
        help="Export a table FROM Dataverse into a definition file (full snapshot).",
    )
    p_rev.add_argument("name", help="Logical name of the table to export (e.g. contact).")
    p_rev.add_argument("--env", default=None, help="Source environment (default: config 'current').")
    p_rev.add_argument(
        "-o", "--output", default=None,
        help="Output file (default: <definitions-dir>/<name>.py).",
    )
    p_rev.set_defaults(func=cmd_reverse)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
