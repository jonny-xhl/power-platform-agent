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
from .components.models import Solution
from .solution_deployer import (
    _ref_type_code,
    deploy_solution,
    lint_solution,
    plan_solution,
)
from .solution_codegen import solution_to_python_source
from .solution_reverse import reverse_solution
from .role_deployer import deploy_role, plan_role
from .role_reverse import reverse_role
from .role_codegen import role_to_python_source
from .role_registry import (
    DEFAULT_ROLES_DIR,
    discover_role_definitions,
    get_role_definition,
)

PUBLISHERS_CONFIG = "config/publishers.yaml"
DEFAULT_SOLUTIONS_DIR = "metadata_py/solutions"


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


def cmd_delete(args: argparse.Namespace) -> int:
    """Delete a table from Dataverse (destructive; cascades attributes + relationships)."""
    client = get_client(args.env)
    logical = args.name.lower()
    result = client.delete_entity(logical)
    _print_json({"name": logical, **result})
    return 0


# ----------------------------------------------------------------- solutions


def _load_solution_module(path: Path) -> Optional[Solution]:
    """Import a solution-definition module by path and return its ``SOLUTION``."""
    import importlib.util
    import uuid

    module_name = f"framework_power_solution_{path.stem}_{uuid.uuid4().hex[:8]}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception as e:  # noqa: BLE001
        print(f"[warn] failed to load solution '{path}': {e}")
        return None
    sol = getattr(module, "SOLUTION", None)
    return sol if isinstance(sol, Solution) else None


def _get_solution(name: str, solutions_dir: str) -> Solution:
    path = Path(solutions_dir) / f"{name}.py"
    if not path.exists():
        raise SystemExit(f"Solution '{name}' not found under '{solutions_dir}'.")
    sol = _load_solution_module(path)
    if sol is None:
        raise SystemExit(f"Solution '{name}' exists but failed to load (no SOLUTION: Solution?).")
    return sol


def _discover_solutions(solutions_dir: str) -> dict[str, Solution]:
    root = Path(solutions_dir)
    if not root.exists():
        return {}
    out: dict[str, Solution] = {}
    for path in sorted(root.glob("*.py")):
        if path.name == "__init__.py" or path.name.startswith("_"):
            continue
        sol = _load_solution_module(path)
        if sol is not None:
            out[path.stem] = sol
    return out


def cmd_solution_list(args: argparse.Namespace) -> int:
    sols = _discover_solutions(args.solutions_dir)
    if not sols:
        print(f"No solutions found under '{args.solutions_dir}'.")
        return 0
    print(f"{'name':32} {'unique_name':28} version     tables refs  publisher")
    for name, sol in sols.items():
        pub = sol.publisher.name if sol.publisher else (sol.publisher_key or "-")
        print(
            f"{name:32} {sol.unique_name:28} {sol.version:11} {len(sol.tables):6} "
            f"{len(sol.refs):5}  {pub}"
        )
    return 0


def cmd_solution_show(args: argparse.Namespace) -> int:
    sol = _get_solution(args.name, args.solutions_dir)
    _print_json(
        {
            "unique_name": sol.unique_name,
            "friendly_name": sol.friendly_name,
            "version": sol.version,
            "description": sol.description,
            "publisher": sol.publisher.name if sol.publisher else None,
            "publisher_key": sol.publisher_key,
            "tables": sol.tables,
            "refs": [
                {"type": r.type, "name": r.name, "object_id": r.object_id} for r in sol.refs
            ],
            "counts": {
                "tables": len(sol.tables),
                "optionsets": len(sol.optionsets),
                "webresources": len(sol.webresources),
                "forms": len(sol.forms),
                "views": len(sol.views),
                "plugins": len(sol.plugins),
                "refs": len(sol.refs),
            },
        }
    )
    return 0


def cmd_solution_lint(args: argparse.Namespace) -> int:
    prefix = _publisher_prefix()
    if args.name:
        targets = {args.name: _get_solution(args.name, args.solutions_dir)}
    else:
        targets = _discover_solutions(args.solutions_dir)
    any_errors = False
    for name, sol in targets.items():
        issues = lint_solution(sol, prefix=prefix)
        errors = [i for i in issues if i.severity == ERROR]
        warnings = [i for i in issues if i.severity == WARNING]
        status = "FAIL" if errors else "ok"
        print(f"[{status}] {name}  ({len(errors)} err, {len(warnings)} warn)")
        for i in issues:
            print(f"    {i.severity}: {i.message}")
        if has_errors(issues):
            any_errors = True
    return 1 if any_errors else 0


def cmd_solution_plan(args: argparse.Namespace) -> int:
    sol = _get_solution(args.name, args.solutions_dir)
    client = get_client(args.env)
    _print_json(plan_solution(client, sol, definitions_dir=args.definitions_dir, prefix=_publisher_prefix()))
    return 0


def cmd_solution_deploy(args: argparse.Namespace) -> int:
    sol = _get_solution(args.name, args.solutions_dir)
    client = get_client(args.env)
    _print_json(
        deploy_solution(client, sol, definitions_dir=args.definitions_dir, prefix=_publisher_prefix())
    )
    return 0


def cmd_solution_reverse(args: argparse.Namespace) -> int:
    client = get_client(args.env)
    sol = reverse_solution(client, args.name)
    out_path = Path(args.output) if args.output else Path(args.solutions_dir) / f"{args.name}.py"
    header = [
        f'"""Reverse-exported solution {args.name!r} by framework_power.',
        "",
        "Full snapshot (publisher + tables as name refs + other components as refs).",
        "Forward `deploy` skips standard (non-custom) items, so this file is safe to sync.",
        "",
        "Regenerate: python -m framework_power solution reverse " + f"{args.name} --env <env>",
        '"""',
    ]
    source = solution_to_python_source(sol, header=header)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(source, encoding="utf-8")
    print(
        f"[ok] reverse solution {args.name} -> {out_path} "
        f"({len(sol.tables)} tables, {len(sol.refs)} refs)"
    )
    return 0


def cmd_solution_add_component(args: argparse.Namespace) -> int:
    client = get_client(args.env)
    code = _ref_type_code(args.type)
    oid = args.id
    if not oid and args.type == "table" and args.name:
        try:
            oid = client.get_entity_metadata(args.name.lower()).get("MetadataId")
        except Exception as e:  # noqa: BLE001
            _print_json({"error": f"cannot resolve table '{args.name}': {e}"})
            return 1
    if not code or not oid:
        _print_json(
            {"error": f"cannot resolve component: type={args.type} name={args.name} id={args.id}"}
        )
        return 1
    try:
        _print_json(client.add_solution_component(args.solution, int(code), oid))
        return 0
    except Exception as e:  # noqa: BLE001
        _print_json({"error": str(e)})
        return 1


def cmd_solution_publish(args: argparse.Namespace) -> int:
    client = get_client(args.env)
    try:
        _print_json(client.publish_all_xml())
        return 0
    except Exception as e:  # noqa: BLE001
        _print_json({"error": str(e)})
        return 1


# ----------------------------------------------------------------- roles (Phase 3)


def cmd_role_list(args: argparse.Namespace) -> int:
    defs = discover_role_definitions(args.roles_dir)
    if not defs:
        print(f"No role definitions found under '{args.roles_dir}'.")
        return 0
    print(f"{'name':32} {'role':28} tables  source")
    for name, defn in defs.items():
        r = defn.role
        print(f"{name:32} {r.name:28} {len(r.table_privileges):7}  {defn.source}")
    return 0


def cmd_role_show(args: argparse.Namespace) -> int:
    defn = get_role_definition(args.name, args.roles_dir)
    _print_json(
        {
            "name": defn.role.name,
            "tables": [
                {"table": tp.table, "rights": {r.name: d.name for r, d in tp.rights.items()}}
                for tp in defn.role.table_privileges
            ],
        }
    )
    return 0


def cmd_role_lint(args: argparse.Namespace) -> int:
    prefix = _publisher_prefix()
    if args.name:
        targets = {args.name: get_role_definition(args.name, args.roles_dir).role}
    else:
        targets = {n: d.role for n, d in discover_role_definitions(args.roles_dir).items()}
    any_errors = False
    for name, role in targets.items():
        issues = [
            i for i in _role_lint(role, prefix=prefix) if i.severity in (ERROR, WARNING)
        ]
        status = "FAIL" if any(i.severity == ERROR for i in issues) else "ok"
        print(f"[{status}] {name}  ({len(issues)} issues)")
        for i in issues:
            print(f"    {i.severity}: {i.message}")
        if any(i.severity == ERROR for i in issues):
            any_errors = True
    return 1 if any_errors else 0


def cmd_role_plan(args: argparse.Namespace) -> int:
    defn = get_role_definition(args.name, args.roles_dir)
    client = get_client(args.env)
    _print_json(plan_role(client, defn.role, prefix=_publisher_prefix()))
    return 0


def cmd_role_deploy(args: argparse.Namespace) -> int:
    defn = get_role_definition(args.name, args.roles_dir)
    client = get_client(args.env)
    try:
        _print_json(deploy_role(client, defn.role, prefix=_publisher_prefix()))
        return 0
    except ValueError as e:  # role not found
        _print_json({"error": str(e)})
        return 1


def cmd_role_reverse(args: argparse.Namespace) -> int:
    tables = [t.strip() for t in (args.tables or "").split(",") if t.strip()]
    if not tables:
        print("error: --tables is required (refusing to pull every table's privileges).")
        return 2
    client = get_client(args.env)
    try:
        role = reverse_role(client, args.name, tables=tables)
    except ValueError as e:
        _print_json({"error": str(e)})
        return 1
    out_path = Path(args.output) if args.output else Path(args.roles_dir) / f"{args.name}.py"
    header = [
        f'"""Reverse-exported role {args.name!r} by framework_power.',
        "",
        f"Privileges scoped to: {', '.join(tables)}",
        "Regenerate: python -m framework_power role reverse "
        + f"{args.name} --tables {','.join(tables)} --env <env>",
        '"""',
    ]
    source = role_to_python_source(role, header=header)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(source, encoding="utf-8")
    print(
        f"[ok] reverse role {args.name} -> {out_path} "
        f"({len(role.table_privileges)} tables)"
    )
    return 0


def _role_lint(role, *, prefix="new"):
    from .components._common import is_custom
    from .lint import Issue

    issues: list[Issue] = []
    if not role.name:
        issues.append(Issue(ERROR, "role.name is required."))
    for tp in role.table_privileges:
        if not is_custom(tp.table, prefix):
            issues.append(Issue(WARNING, f"role table '{tp.table}' is not custom (no '{prefix}_' prefix)."))
    return issues


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
    parser.add_argument(
        "--solutions-dir",
        default=DEFAULT_SOLUTIONS_DIR,
        help=f"Solutions directory (default: {DEFAULT_SOLUTIONS_DIR}).",
    )
    parser.add_argument(
        "--roles-dir",
        default=DEFAULT_ROLES_DIR,
        help=f"Roles directory (default: {DEFAULT_ROLES_DIR}).",
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

    p_del = sub.add_parser(
        "delete",
        help="Delete a table from Dataverse (destructive; cascades attributes + relationships).",
    )
    p_del.add_argument("name", help="Logical name of the table to delete.")
    p_del.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p_del.set_defaults(func=cmd_delete)

    # --- solution group (Phase 2) ---
    p_sol = sub.add_parser("solution", help="Manage Power Platform solutions.")
    sol_sub = p_sol.add_subparsers(dest="solution_command", required=True)

    sol_sub.add_parser("list", help="List discovered solution definitions.").set_defaults(
        func=cmd_solution_list
    )

    p = sol_sub.add_parser("show", help="Print a solution definition summary (no network).")
    p.add_argument("name")
    p.set_defaults(func=cmd_solution_show)

    p = sol_sub.add_parser("lint", help="Offline convention check on solution definitions.")
    p.add_argument("name", nargs="?")
    p.set_defaults(func=cmd_solution_lint)

    p = sol_sub.add_parser("plan", help="Read-only dry run of a solution against an environment.")
    p.add_argument("name")
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.set_defaults(func=cmd_solution_plan)

    p = sol_sub.add_parser("deploy", help="Deploy (sync) a solution to Dataverse.")
    p.add_argument("name")
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.set_defaults(func=cmd_solution_deploy)

    p = sol_sub.add_parser(
        "reverse", help="Export a solution FROM Dataverse into a definition file (full snapshot)."
    )
    p.add_argument("name", help="Unique name of the solution to export.")
    p.add_argument("--env", default=None, help="Source environment (default: config 'current').")
    p.add_argument(
        "-o", "--output", default=None, help="Output file (default: <solutions-dir>/<name>.py)."
    )
    p.set_defaults(func=cmd_solution_reverse)

    p = sol_sub.add_parser("add-component", help="Add an existing component to a solution.")
    p.add_argument("solution", help="Solution unique name.")
    p.add_argument("--type", required=True, help="Component type key (table/webresource/...) or code.")
    p.add_argument("--name", default=None, help="Component name (resolved for table type).")
    p.add_argument("--id", default=None, help="Component object id (GUID).")
    p.add_argument("--entity", default=None)
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.set_defaults(func=cmd_solution_add_component)

    p = sol_sub.add_parser("publish", help="Publish all customizations (PublishAllXml).")
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.set_defaults(func=cmd_solution_publish)

    # --- role group (Phase 3) ---
    p_role = sub.add_parser("role", help="Manage security-role table privileges.")
    role_sub = p_role.add_subparsers(dest="role_command", required=True)

    role_sub.add_parser("list", help="List discovered role definitions.").set_defaults(
        func=cmd_role_list
    )

    p = role_sub.add_parser("show", help="Print a role definition summary (no network).")
    p.add_argument("name")
    p.set_defaults(func=cmd_role_show)

    p = role_sub.add_parser("lint", help="Offline convention check on role definitions.")
    p.add_argument("name", nargs="?")
    p.set_defaults(func=cmd_role_lint)

    p = role_sub.add_parser("plan", help="Read-only preview of a role's privilege sync.")
    p.add_argument("name")
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.set_defaults(func=cmd_role_plan)

    p = role_sub.add_parser("deploy", help="Upsert a role's table privileges (non-destructive).")
    p.add_argument("name")
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.set_defaults(func=cmd_role_deploy)

    p = role_sub.add_parser(
        "reverse", help="Export a role's privileges FROM Dataverse (scoped to --tables)."
    )
    p.add_argument("name", help="Role name (must already exist).")
    p.add_argument(
        "--tables",
        default=None,
        help="REQUIRED comma-separated table logical names to capture privileges for.",
    )
    p.add_argument("--env", default=None, help="Source environment (default: config 'current').")
    p.add_argument(
        "-o", "--output", default=None, help="Output file (default: <roles-dir>/<name>.py)."
    )
    p.set_defaults(func=cmd_role_reverse)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
