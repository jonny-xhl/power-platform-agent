"""
Command-line interface for framework_power.

Drives the 需求 -> definition -> sync pipeline from one entry point:

    pp list
    pp show new_projectbudget
    pp lint new_projectbudget
    pp plan new_projectbudget --env dev
    pp deploy new_projectbudget --env dev
    pp deploy-all --env dev

**Workspace-aware**: The CLI auto-discovers the workspace root by searching
for ``pp-workspace.yaml`` from CWD upward. All directory paths (tables,
forms, config, etc.) resolve relative to the workspace root, not CWD.
Use ``--workspace <path>`` to override, or set ``PP_WORKSPACE`` env var.

    pp workspace init           # scaffold a new workspace
    pp workspace info           # show resolved workspace paths
    pp workspace validate       # check workspace structure

Definitions are discovered under ``metadata_py/tables/`` (each ``<schema>.py`` exposes
``TABLE``). ``lint`` runs offline (no network); ``plan`` is a read-only dry run;
``deploy``/``deploy-all`` write to Dataverse.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Optional

from .deployer import deploy_table, plan_table
from .lint import ERROR, INFO, WARNING, has_errors, lint_table
from .registry import DEFAULT_DEFINITIONS_DIR, deploy_order, discover_definitions, get_definition
from .runtime import get_client
from .components.models import Solution
from .workspace import (
    NotInWorkspaceError,
    Workspace,
    WorkspaceManifest,
    get_cached_workspace,
    reset_cache,
)
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
from .webresource_sync import (
    plan_webresources,
    reverse_webresources,
    scan_webresources,
    sync_webresources,
)
from .form_sync import (
    load_form,
    plan_forms,
    reverse_forms,
    sync_forms,
)
from .view_sync import (
    load_view,
    plan_views,
    reverse_views,
    sync_views,
)
from .ribbon_sync import (
    codegen_ribbon,
    lint_ribbon,
    load_ribbon,
    plan_ribbons,
    reverse_ribbons,
    sync_ribbons,
)
from .ribbon_xml import to_ribbondiff
from .plugin_sync import deploy_plugin, list_plugins, reverse_plugin
from .workflow import (
    DEFAULT_PROJECT_PATH,
    deploy_workflow,
    lint_workflow,
    load_project,
    plan_workflow,
)

PUBLISHERS_CONFIG = "config/publishers.yaml"
DEFAULT_SOLUTIONS_DIR = "metadata_py/solutions"
DEFAULT_WEBRESOURCES_ROOT = "webresources"
DEFAULT_FORMS_DIR = "metadata_py/forms"
DEFAULT_VIEWS_DIR = "metadata_py/views"
DEFAULT_RIBBONS_DIR = "metadata_py/ribbons"
DEFAULT_RIBBON_SOLUTION = "new_RibbonSoln"
DEFAULT_PLUGIN_SOLUTION = "new_PluginSoln"


# ----------------------------------------------------------------- workspace helpers

# Process-wide flag: emit the "not in workspace" hint at most once per invocation.
_warned_no_workspace: bool = False


def _try_workspace(args: argparse.Namespace) -> Optional[Workspace]:
    """Try to discover the workspace from args or CWD; return None if not in a workspace.

    This is non-fatal — callers fall back to CWD-relative paths (legacy behavior)
    when no workspace is found. Used for backward compatibility.

    When no workspace is found, a hint is printed to stderr (once per process) so
    users are aware they are operating in legacy CWD-fallback mode.
    """
    global _warned_no_workspace
    explicit = getattr(args, "workspace", None)
    try:
        return get_cached_workspace(explicit)
    except NotInWorkspaceError:
        if not _warned_no_workspace:
            _warned_no_workspace = True
            print(
                "[hint] Not in a Power Platform workspace. "
                "Run 'pp workspace init' to create one, or use --workspace <path>.\n"
                "       Falling back to CWD-relative paths (legacy mode).",
                file=sys.stderr,
            )
        return None


def _reset_no_workspace_warning() -> None:
    """Reset the once-per-process "not in workspace" warning flag (for tests)."""
    global _warned_no_workspace
    _warned_no_workspace = False


def _workspace_prefix(ws: Optional[Workspace]) -> str:
    """Read publisher prefix from workspace manifest, or fall back to config file."""
    if ws is not None:
        return ws.manifest.publisher_prefix
    return _publisher_prefix()


def _workspace_dir(args: argparse.Namespace, attr: str, fallback: str) -> str:
    """Resolve a directory path: workspace-aware with CWD fallback.

    If a workspace is discovered, use ``ws.<attr>`` (absolute path).
    Otherwise, fall back to the legacy CWD-relative default.
    """
    ws = _try_workspace(args)
    if ws is not None:
        return str(getattr(ws, attr))
    return fallback


def _resolve_dir(args: argparse.Namespace, attr: str, current: str, default: str) -> str:
    """Resolve a directory path, but only use workspace resolution when the user
    did NOT explicitly override (i.e. ``current == default``).

    This preserves backward compatibility: if the user passes ``--definitions-dir /foo``
    or a positional ``root=/foo``, that explicit value is honored.
    """
    if current != default:
        return current  # user explicitly provided a path
    return _workspace_dir(args, attr, current)


def _get_client_ws(args: argparse.Namespace, env: Optional[str] = None):
    """Build authenticated client using workspace config or CWD fallback."""
    ws = _try_workspace(args)
    if ws is not None:
        return get_client(env, config_path=str(ws.environments_config))
    return get_client(env)


def _effective_prefix(args: argparse.Namespace) -> str:
    """Get publisher prefix from workspace manifest or config file."""
    ws = _try_workspace(args)
    return _workspace_prefix(ws)


def _publisher_prefix(config_path: str = PUBLISHERS_CONFIG) -> str:
    """Read the current publisher prefix from config/publishers.yaml (default 'new')."""
    try:
        import yaml

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


# ----------------------------------------------------------------- workspace commands


_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _render_template(filename: str, replacements: dict[str, str]) -> str:
    """Read a template file and apply ``__KEY__`` → value replacements."""
    template_path = _TEMPLATES_DIR / filename
    content = template_path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        content = content.replace(f"__{key}__", value)
    return content


def cmd_workspace_init(args: argparse.Namespace) -> int:
    """Initialize a new workspace in the current (or specified) directory."""
    target = Path(args.path or ".").resolve()
    target.mkdir(parents=True, exist_ok=True)

    manifest_path = target / "pp-workspace.yaml"
    if manifest_path.exists() and not args.force:
        print(f"Error: workspace already exists at {target}")
        print("  Use --force to overwrite.")
        return 1

    name = args.name or target.name
    publisher = args.publisher or "new"
    prefix = args.prefix or "new"
    main_sol = args.main_solution or f"{prefix}_{name}"
    ribbon_sol = args.ribbon_solution or f"{main_sol}_Ribbon"

    # Create workspace via the Workspace API
    ws = Workspace.create_from_template(
        target,
        name=name,
        publisher=publisher,
        publisher_prefix=prefix,
        publisher_display_name=args.publisher_display or "",
        main_solution=main_sol,
        ribbon_solution=ribbon_sol,
        description=args.description or "",
    )
    ws.write_manifest()

    # Generate config templates
    replacements = {
        "WORKSPACE_NAME": name,
        "PUBLISHER": publisher,
        "PREFIX": prefix,
        "PUBLISHER_DISPLAY": args.publisher_display or publisher,
        "MAIN_SOLUTION": main_sol,
        "RIBBON_SOLUTION": ribbon_sol,
    }

    config_dir = ws.config_dir
    config_dir.mkdir(parents=True, exist_ok=True)

    # environments.yaml
    env_path = config_dir / "environments.yaml"
    if not env_path.exists() or args.force:
        env_path.write_text(
            _render_template("environments.yaml", replacements), encoding="utf-8"
        )

    # pipeline.yaml
    pipe_path = config_dir / "pipeline.yaml"
    if not pipe_path.exists() or args.force:
        pipe_path.write_text(
            _render_template("pipeline.yaml", replacements), encoding="utf-8"
        )

    # publishers.yaml
    pub_path = config_dir / "publishers.yaml"
    if not pub_path.exists() or args.force:
        pub_path.write_text(
            _render_template("publishers.yaml", replacements), encoding="utf-8"
        )

    # naming_rules.yaml
    naming_path = config_dir / "naming_rules.yaml"
    if not naming_path.exists() or args.force:
        naming_path.write_text(
            _render_template("naming_rules.yaml", replacements), encoding="utf-8"
        )

    # .gitignore
    gitignore = target / ".gitignore"
    if not gitignore.exists() or args.force:
        gitignore.write_text(
            (_TEMPLATES_DIR / ".gitignore").read_text(encoding="utf-8"), encoding="utf-8"
        )

    # requirements.txt
    req_path = target / "requirements.txt"
    if not req_path.exists() or args.force:
        req_path.write_text(
            (_TEMPLATES_DIR / "requirements.txt").read_text(encoding="utf-8"), encoding="utf-8"
        )

    # metadata_py __init__.py files
    for subdir in ("tables", "forms", "views", "ribbons", "roles", "optionsets", "solutions"):
        init_path = ws.path(subdir) / "__init__.py"
        if not init_path.exists():
            init_path.write_text("", encoding="utf-8")

    print(f"[ok] workspace initialized at {target}")
    print(f"  name:           {name}")
    print(f"  publisher:      {publisher} ({prefix})")
    print(f"  main_solution:  {main_sol}")
    print(f"  ribbon_solution: {ribbon_sol}")
    print(f"\nNext steps:")
    print(f"  1. Edit {target / 'config' / 'environments.yaml'} with your Dataverse URLs")
    print(f"  2. Set env vars: DEV_TENANT_ID, DEV_CLIENT_ID, DEV_CLIENT_SECRET")
    print(f"  3. Create table definitions in {ws.tables_dir}")
    print(f"  4. Run: pp list")
    return 0


def cmd_workspace_info(args: argparse.Namespace) -> int:
    """Show current workspace info."""
    ws = Workspace.discover(args.workspace)
    _print_json(ws.to_dict())
    return 0


def cmd_workspace_validate(args: argparse.Namespace) -> int:
    """Validate workspace structure."""
    ws = Workspace.discover(args.workspace)
    issues = ws.validate()
    if issues:
        print(f"[FAIL] {len(issues)} issue(s):")
        for i in issues:
            print(f"  - {i}")
        return 1
    print(f"[ok] workspace '{ws.manifest.name}' is valid")
    print(f"  root: {ws.root}")
    print(f"  publisher: {ws.manifest.publisher} ({ws.manifest.publisher_prefix})")
    print(f"  main_solution: {ws.manifest.main_solution}")
    return 0


# ----------------------------------------------------------------- commands


def cmd_list(args: argparse.Namespace) -> int:
    tables_dir = _resolve_dir(args, "tables_dir", args.definitions_dir, DEFAULT_DEFINITIONS_DIR)
    defs = discover_definitions(tables_dir)
    if not defs:
        print(f"No definitions found under '{tables_dir}'.")
        return 0
    print(f"{'name':32} {'schema_name':28} cols rels  source")
    for name, defn in defs.items():
        t = defn.table
        print(
            f"{name:32} {t.schema_name:28} {len(t.columns):4} {len(t.relationships):4}  {defn.source}"
        )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    tables_dir = _resolve_dir(args, "tables_dir", args.definitions_dir, DEFAULT_DEFINITIONS_DIR)
    defn = get_definition(args.name, tables_dir)
    from .serializer import serialize_relationship, serialize_table_for_create

    payload = serialize_table_for_create(defn.table)
    rels = [
        serialize_relationship(r, referenced_attribute=f"{r.referenced_entity}id")
        for r in defn.table.relationships
    ]
    _print_json({"entity": payload, "relationships": rels})
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    prefix = _effective_prefix(args)
    tables_dir = _resolve_dir(args, "tables_dir", args.definitions_dir, DEFAULT_DEFINITIONS_DIR)
    if args.name:
        defn = get_definition(args.name, tables_dir)
        targets = {defn.name: defn.table}
    else:
        targets = {n: d.table for n, d in discover_definitions(tables_dir).items()}

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
    tables_dir = _resolve_dir(args, "tables_dir", args.definitions_dir, DEFAULT_DEFINITIONS_DIR)
    defn = get_definition(args.name, tables_dir)
    client = _get_client_ws(args, args.env)
    _print_json(plan_table(client, defn.table, prefix=_effective_prefix(args)))
    return 0


def cmd_deploy(args: argparse.Namespace) -> int:
    tables_dir = _resolve_dir(args, "tables_dir", args.definitions_dir, DEFAULT_DEFINITIONS_DIR)
    defn = get_definition(args.name, tables_dir)
    client = _get_client_ws(args, args.env)
    _print_json(
        deploy_table(
            client,
            defn.table,
            prefix=_effective_prefix(args),
            solution=args.solution,
            solution_clean=args.solution_clean,
        )
    )
    return 0


def cmd_deploy_all(args: argparse.Namespace) -> int:
    tables_dir = _resolve_dir(args, "tables_dir", args.definitions_dir, DEFAULT_DEFINITIONS_DIR)
    defs = discover_definitions(tables_dir)
    if not defs:
        print(f"No definitions found under '{tables_dir}'.")
        return 0
    order = deploy_order(defs)
    print(f"Deploy order: {order}")
    client = _get_client_ws(args, args.env)
    prefix = _effective_prefix(args)
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

    tables_dir = _resolve_dir(args, "tables_dir", args.definitions_dir, DEFAULT_DEFINITIONS_DIR)
    client = _get_client_ws(args, args.env)
    table = reverse_table(client, args.name)

    if getattr(args, "dictionary", False):
        # --dictionary: generate data dictionary Markdown instead of .py
        return _reverse_to_dictionary(args, table, tables_dir)

    out_path = Path(args.output) if args.output else Path(tables_dir) / f"{args.name}.py"
    header = [
        f'"""Reverse-exported from Dataverse ({args.name!r}) by framework_power.',
        "",
        "Full snapshot (custom + standard attributes + relationships) for local reference,",
        "diffing, and AI constraint. Forward `deploy` skips standard (non-custom) items",
        "automatically, so this same file is safe to sync.",
        "",
        "Regenerate: pp reverse " + f"{args.name} --env <env>",
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


def _reverse_to_dictionary(args: argparse.Namespace, table, tables_dir: str) -> int:
    """Write a single table's data dictionary Markdown (from a reversed Table)."""
    from .data_dictionary import DEFAULT_DICTIONARY_DIR, table_to_markdown

    dict_dir = DEFAULT_DICTIONARY_DIR
    # When in a workspace, resolve dict_dir relative to workspace root
    ws = _try_workspace(args)
    if ws is not None and not Path(dict_dir).is_absolute():
        dict_dir = str(ws.root / dict_dir)

    out_path = Path(args.output) if args.output else Path(dict_dir) / "tables" / f"{table.schema_name}.md"
    md = table_to_markdown(table, source_name=None)  # no source file (reversed from Dataverse)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"[ok] reverse {args.name} --dictionary -> {out_path}")
    return 0


def cmd_dictionary(args: argparse.Namespace) -> int:
    """Generate data dictionary Markdown from local metadata_py/ definitions.

    No Dataverse connection required — reads from the Python definitions.
    """
    from .data_dictionary import DEFAULT_DICTIONARY_DIR, generate_table_docs

    tables_dir = _resolve_dir(args, "tables_dir", DEFAULT_DEFINITIONS_DIR, DEFAULT_DEFINITIONS_DIR)
    dict_dir = args.output or DEFAULT_DICTIONARY_DIR

    # When in a workspace, resolve dict_dir relative to workspace root
    ws = _try_workspace(args)
    if ws is not None and not Path(dict_dir).is_absolute():
        dict_dir = str(ws.root / dict_dir)

    defs = discover_definitions(tables_dir)
    if not defs:
        print(f"[warn] No table definitions found in {tables_dir}/")
        return 1

    # Pass a relative source_dir for clean Markdown links
    source_dir = DEFAULT_DEFINITIONS_DIR
    if ws is not None:
        try:
            source_dir = str(Path(tables_dir).relative_to(ws.root)).replace("\\", "/")
        except ValueError:
            source_dir = tables_dir

    written = generate_table_docs(defs, output_dir=dict_dir, source_dir=source_dir)
    for p in written:
        print(f"  [ok] {p}")
    print(f"\n[ok] dictionary: {len(defs)} tables -> {dict_dir}/")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """Delete a table from Dataverse (destructive; cascades attributes + relationships)."""
    client = _get_client_ws(args, args.env)
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
    sols_dir = _resolve_dir(args, "solutions_dir", args.solutions_dir, DEFAULT_SOLUTIONS_DIR)
    sols = _discover_solutions(sols_dir)
    if not sols:
        print(f"No solutions found under '{sols_dir}'.")
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
    sols_dir = _resolve_dir(args, "solutions_dir", args.solutions_dir, DEFAULT_SOLUTIONS_DIR)
    sol = _get_solution(args.name, sols_dir)
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
    prefix = _effective_prefix(args)
    sols_dir = _resolve_dir(args, "solutions_dir", args.solutions_dir, DEFAULT_SOLUTIONS_DIR)
    if args.name:
        targets = {args.name: _get_solution(args.name, sols_dir)}
    else:
        targets = _discover_solutions(sols_dir)
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
    sols_dir = _resolve_dir(args, "solutions_dir", args.solutions_dir, DEFAULT_SOLUTIONS_DIR)
    tables_dir = _resolve_dir(args, "tables_dir", args.definitions_dir, DEFAULT_DEFINITIONS_DIR)
    sol = _get_solution(args.name, sols_dir)
    client = _get_client_ws(args, args.env)
    _print_json(plan_solution(client, sol, definitions_dir=tables_dir, prefix=_effective_prefix(args)))
    return 0


def cmd_solution_deploy(args: argparse.Namespace) -> int:
    sols_dir = _resolve_dir(args, "solutions_dir", args.solutions_dir, DEFAULT_SOLUTIONS_DIR)
    tables_dir = _resolve_dir(args, "tables_dir", args.definitions_dir, DEFAULT_DEFINITIONS_DIR)
    sol = _get_solution(args.name, sols_dir)
    client = _get_client_ws(args, args.env)
    _print_json(
        deploy_solution(client, sol, definitions_dir=tables_dir, prefix=_effective_prefix(args))
    )
    return 0


def cmd_solution_reverse(args: argparse.Namespace) -> int:
    sols_dir = _resolve_dir(args, "solutions_dir", args.solutions_dir, DEFAULT_SOLUTIONS_DIR)
    client = _get_client_ws(args, args.env)
    sol = reverse_solution(client, args.name)
    out_path = Path(args.output) if args.output else Path(sols_dir) / f"{args.name}.py"
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
    client = _get_client_ws(args, args.env)
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
    client = _get_client_ws(args, args.env)
    try:
        _print_json(client.publish_all_xml())
        return 0
    except Exception as e:  # noqa: BLE001
        _print_json({"error": str(e)})
        return 1


def cmd_solution_delete(args: argparse.Namespace) -> int:
    client = _get_client_ws(args, args.env)
    try:
        _print_json(client.delete_solution(args.solution))
        return 0
    except Exception as e:  # noqa: BLE001
        _print_json({"error": str(e)})
        return 1


# ----------------------------------------------------------------- roles (Phase 3)


def cmd_role_list(args: argparse.Namespace) -> int:
    roles_dir = _resolve_dir(args, "roles_dir", args.roles_dir, DEFAULT_ROLES_DIR)
    defs = discover_role_definitions(roles_dir)
    if not defs:
        print(f"No role definitions found under '{roles_dir}'.")
        return 0
    print(f"{'name':32} {'role':28} tables  source")
    for name, defn in defs.items():
        r = defn.role
        print(f"{name:32} {r.name:28} {len(r.table_privileges):7}  {defn.source}")
    return 0


def cmd_role_show(args: argparse.Namespace) -> int:
    roles_dir = _resolve_dir(args, "roles_dir", args.roles_dir, DEFAULT_ROLES_DIR)
    defn = get_role_definition(args.name, roles_dir)
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
    prefix = _effective_prefix(args)
    roles_dir = _resolve_dir(args, "roles_dir", args.roles_dir, DEFAULT_ROLES_DIR)
    if args.name:
        targets = {args.name: get_role_definition(args.name, roles_dir).role}
    else:
        targets = {n: d.role for n, d in discover_role_definitions(roles_dir).items()}
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
    roles_dir = _resolve_dir(args, "roles_dir", args.roles_dir, DEFAULT_ROLES_DIR)
    defn = get_role_definition(args.name, roles_dir)
    client = _get_client_ws(args, args.env)
    _print_json(plan_role(client, defn.role, prefix=_effective_prefix(args)))
    return 0


def cmd_role_deploy(args: argparse.Namespace) -> int:
    roles_dir = _resolve_dir(args, "roles_dir", args.roles_dir, DEFAULT_ROLES_DIR)
    defn = get_role_definition(args.name, roles_dir)
    client = _get_client_ws(args, args.env)
    try:
        _print_json(deploy_role(client, defn.role, prefix=_effective_prefix(args)))
        return 0
    except ValueError as e:  # role not found
        _print_json({"error": str(e)})
        return 1


def cmd_role_reverse(args: argparse.Namespace) -> int:
    roles_dir = _resolve_dir(args, "roles_dir", args.roles_dir, DEFAULT_ROLES_DIR)
    tables = [t.strip() for t in (args.tables or "").split(",") if t.strip()]
    if not tables:
        print("error: --tables is required (refusing to pull every table's privileges).")
        return 2
    client = _get_client_ws(args, args.env)
    try:
        role = reverse_role(client, args.name, tables=tables)
    except ValueError as e:
        _print_json({"error": str(e)})
        return 1
    out_path = Path(args.output) if args.output else Path(roles_dir) / f"{args.name}.py"
    header = [
        f'"""Reverse-exported role {args.name!r} by framework_power.',
        "",
        f"Privileges scoped to: {', '.join(tables)}",
        "Regenerate: pp role reverse "
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


# ----------------------------------------------------------------- web resources (Phase 4)


def cmd_webresource_scan(args: argparse.Namespace) -> int:
    wr_root = _resolve_dir(args, "webresources_root", args.root, DEFAULT_WEBRESOURCES_ROOT)
    models, warnings = scan_webresources(Path(wr_root), _effective_prefix(args))
    files = [{"name": m.name, "type": m.webresource_type.name} for m in models]
    print(f"[scan] {len(files)} web resource(s) under '{wr_root}'")
    for f in files:
        print(f"  {f['type']:11} {f['name']}")
    for w in warnings:
        print(f"  [warn] {w}")
    return 0


def cmd_webresource_plan(args: argparse.Namespace) -> int:
    wr_root = _resolve_dir(args, "webresources_root", args.root, DEFAULT_WEBRESOURCES_ROOT)
    client = _get_client_ws(args, args.env)
    _print_json(
        plan_webresources(client, Path(wr_root), prefix=_effective_prefix(args), include=args.include)
    )
    return 0


def cmd_webresource_sync(args: argparse.Namespace) -> int:
    wr_root = _resolve_dir(args, "webresources_root", args.root, DEFAULT_WEBRESOURCES_ROOT)
    client = _get_client_ws(args, args.env)
    try:
        _print_json(
            sync_webresources(
                client,
                Path(wr_root),
                prefix=_effective_prefix(args),
                solution=args.solution,
                publish=not args.no_publish,
                include=args.include,
            )
        )
        return 0
    except Exception as e:  # noqa: BLE001
        _print_json({"error": str(e)})
        return 1


def cmd_webresource_reverse(args: argparse.Namespace) -> int:
    wr_root = _resolve_dir(args, "webresources_root", args.root, DEFAULT_WEBRESOURCES_ROOT)
    client = _get_client_ws(args, args.env)
    try:
        result = reverse_webresources(
            client, Path(wr_root), prefix=_effective_prefix(args), name_prefix=args.name_prefix
        )
    except Exception as e:  # noqa: BLE001
        _print_json({"error": str(e)})
        return 1
    _print_json(result)
    return 0


def cmd_webresource_publish(args: argparse.Namespace) -> int:
    client = _get_client_ws(args, args.env)
    ids: list[str] = []
    missing: list[str] = []
    for name in args.names:
        existing = client.get_webresource_by_name(name)
        if existing is None:
            missing.append(name)
            continue
        ids.append(str(existing["webresourceid"]))
    if missing:
        _print_json({"error": "web resource(s) not found", "missing": missing})
        return 1
    try:
        _print_json(client.publish_webresources(ids))
        return 0
    except Exception as e:  # noqa: BLE001
        _print_json({"error": str(e)})
        return 1


# ----------------------------------------------------------------- forms (Phase 5)


def cmd_form_list(args: argparse.Namespace) -> int:
    client = _get_client_ws(args, args.env)
    forms = client.list_forms_by_entity(args.entity)
    print(f"[list] {len(forms)} form(s) on '{args.entity}'")
    for f in forms:
        name = f.get("name")
        print(
            f"  type={f.get('type')} active={f.get('formactivationstate')} "
            f"name={name!r} id={f.get('formid')}"
        )
    return 0


def cmd_form_show(args: argparse.Namespace) -> int:
    form = load_form(args.file)
    print(f"[show] {form.name!r} (entity={form.entity}, type={form.form_type.name})")
    for tab in form.tabs:
        print(f"  tab {tab.name!r}: {len(tab.sections)} section(s)")
    if form.libraries:
        print(f"  libraries: {[lib.name for lib in form.libraries]}")
    for ev in form.events:
        custom = [h for h in ev.handlers if not h.internal]
        if custom:
            print(f"  event {ev.name!r}: {[(h.function_name, h.library_name) for h in custom]}")
    return 0


def cmd_form_lint(args: argparse.Namespace) -> int:
    from .components import form as form_component

    form = load_form(args.file)
    issues = form_component.lint(form, prefix=_effective_prefix(args))
    for issue in issues:
        print(f"  [{issue.severity}] {issue.message}")
    print(f"[lint] {form.name!r}: {len(issues)} issue(s), {sum(i.is_error for i in issues)} error(s)")
    return 1 if any(i.is_error for i in issues) else 0


def cmd_form_plan(args: argparse.Namespace) -> int:
    client = _get_client_ws(args, args.env)
    form = load_form(args.file)
    _print_json(plan_forms(client, [form], prefix=_effective_prefix(args)))
    return 0


def cmd_form_deploy(args: argparse.Namespace) -> int:
    client = _get_client_ws(args, args.env)
    form = load_form(args.file)
    try:
        _print_json(
            sync_forms(
                client,
                [form],
                prefix=_effective_prefix(args),
                solution=args.solution,
                publish=not args.no_publish,
            )
        )
        return 0
    except Exception as e:  # noqa: BLE001
        _print_json({"error": str(e)})
        return 1


def cmd_form_reverse(args: argparse.Namespace) -> int:
    forms_dir = _resolve_dir(args, "forms_dir", args.forms_dir, DEFAULT_FORMS_DIR)
    client = _get_client_ws(args, args.env)
    try:
        result = reverse_forms(client, args.entity, out_dir=forms_dir, prefix=_effective_prefix(args))
    except Exception as e:  # noqa: BLE001
        _print_json({"error": str(e)})
        return 1
    _print_json(result)
    return 0


# ----------------------------------------------------------------- views (Phase 6)


def cmd_view_list(args: argparse.Namespace) -> int:
    client = _get_client_ws(args, args.env)
    views = client.list_views_by_entity(args.entity)
    print(f"[list] {len(views)} view(s) on '{args.entity}'")
    for v in views:
        name = v.get("name")
        print(f"  querytype={v.get('querytype')} default={v.get('isdefault')} name={name!r}")
    return 0


def cmd_view_show(args: argparse.Namespace) -> int:
    view = load_view(args.file)
    print(f"[show] {view.name!r} (entity={view.entity}, query_type={view.query_type.name})")
    print(f"  primary_id={view.primary_id} object_type_code={view.object_type_code}")
    print(f"  columns: {[c.name for c in view.columns]}")
    print(f"  orders: {[(o.attribute, o.descending) for o in view.orders]}")
    print(f"  filters: {len(view.filters)} link_entities: {[le.alias for le in view.link_entities]}")
    return 0


def cmd_view_lint(args: argparse.Namespace) -> int:
    from .components import view as view_component

    view = load_view(args.file)
    issues = view_component.lint(view, prefix=_effective_prefix(args))
    for issue in issues:
        print(f"  [{issue.severity}] {issue.message}")
    print(f"[lint] {view.name!r}: {len(issues)} issue(s), {sum(i.is_error for i in issues)} error(s)")
    return 1 if any(i.is_error for i in issues) else 0


def cmd_view_plan(args: argparse.Namespace) -> int:
    client = _get_client_ws(args, args.env)
    view = load_view(args.file)
    _print_json(plan_views(client, [view], prefix=_effective_prefix(args)))
    return 0


def cmd_view_deploy(args: argparse.Namespace) -> int:
    client = _get_client_ws(args, args.env)
    view = load_view(args.file)
    try:
        _print_json(
            sync_views(
                client,
                [view],
                prefix=_effective_prefix(args),
                solution=args.solution,
                publish=not args.no_publish,
            )
        )
        return 0
    except Exception as e:  # noqa: BLE001
        _print_json({"error": str(e)})
        return 1


def cmd_view_reverse(args: argparse.Namespace) -> int:
    views_dir = _resolve_dir(args, "views_dir", args.views_dir, DEFAULT_VIEWS_DIR)
    client = _get_client_ws(args, args.env)
    try:
        result = reverse_views(client, args.entity, out_dir=views_dir, prefix=_effective_prefix(args))
    except Exception as e:  # noqa: BLE001
        _print_json({"error": str(e)})
        return 1
    _print_json(result)
    return 0


# ----------------------------------------------------------------- ribbon (Phase 7)


def cmd_ribbon_build(args: argparse.Namespace) -> int:
    print(to_ribbondiff(load_ribbon(args.file)))
    return 0


def cmd_ribbon_show(args: argparse.Namespace) -> int:
    ribbon = load_ribbon(args.file)
    scope = "application" if ribbon.entity is None else ribbon.entity
    print(f"[show] ribbon for {scope!r}: {len(ribbon.buttons)} button(s), "
          f"{len(ribbon.commands)} command(s), {len(ribbon.hide_oobs)} hide-oob(s)")
    for b in ribbon.buttons:
        print(f"  button {b.id!r} scope={b.scope.value} command={b.command!r}")
    for h in ribbon.hide_oobs:
        print(f"  hide_oob {h.oob_command_id!r} method={h.method}")
    return 0


def cmd_ribbon_lint(args: argparse.Namespace) -> int:
    issues = lint_ribbon(load_ribbon(args.file), prefix=_effective_prefix(args))
    for issue in issues:
        print(f"  [{issue.severity}] {issue.message}")
    print(f"[lint] {len(issues)} issue(s), {sum(i.is_error for i in issues)} error(s)")
    return 1 if any(i.is_error for i in issues) else 0


def cmd_ribbon_plan(args: argparse.Namespace) -> int:
    client = _get_client_ws(args, args.env)
    _print_json(plan_ribbons(client, [load_ribbon(args.file)], prefix=_effective_prefix(args),
                             solution=args.ribbon_solution))
    return 0


def cmd_ribbon_deploy(args: argparse.Namespace) -> int:
    client = _get_client_ws(args, args.env)
    try:
        _print_json(sync_ribbons(client, [load_ribbon(args.file)], prefix=_effective_prefix(args),
                                 solution=args.ribbon_solution, publish=not args.no_publish))
        return 0
    except Exception as e:  # noqa: BLE001
        _print_json({"error": str(e)})
        return 1


def cmd_ribbon_reverse(args: argparse.Namespace) -> int:
    ribbons_dir = _resolve_dir(args, "ribbons_dir", args.ribbons_dir, DEFAULT_RIBBONS_DIR)
    client = _get_client_ws(args, args.env)
    entity = None if args.application else args.entity
    try:
        ribbon = reverse_ribbons(client, entity, solution=args.ribbon_solution)
    except Exception as e:  # noqa: BLE001
        _print_json({"error": str(e)})
        return 1
    out_dir = Path(ribbons_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = "application" if entity is None else entity
    path = out_dir / f"{name}.py"
    imports = "from framework_power import RibbonDefinition, RibbonScope\n"
    path.write_text(imports + "\nRIBBON: RibbonDefinition = " + codegen_ribbon(ribbon) + "\n", encoding="utf-8")
    _print_json({"entity": name, "buttons": len(ribbon.buttons), "path": str(path)})
    return 0


# ----------------------------------------------------------------- plugin (Phase 8)


def cmd_plugin_build(args: argparse.Namespace) -> int:
    from .client.plugin_build import build_plugin_project, load_plugin_project
    try:
        cfg = load_plugin_project(args.def_file)
        plugin = build_plugin_project(args.project_dir, config=cfg)
        _print_json({"name": plugin.name, "package_name": plugin.package_name,
                     "content_kind": plugin.content_kind.value, "target_framework": plugin.target_framework,
                     "version": plugin.version, "content_len": len(plugin.content),
                     "steps": len(plugin.steps), "custom_actions": len(plugin.custom_actions)})
        return 0
    except Exception as e:  # noqa: BLE001
        _print_json({"error": str(e)})
        return 1


def cmd_plugin_deploy(args: argparse.Namespace) -> int:
    client = _get_client_ws(args, args.env)
    try:
        _print_json(deploy_plugin(
            client, args.project_dir, def_path=args.def_file, prefix=_effective_prefix(args),
            solution=args.plugin_solution))
        return 0
    except Exception as e:  # noqa: BLE001
        _print_json({"error": str(e)})
        return 1


def cmd_plugin_list(args: argparse.Namespace) -> int:
    client = _get_client_ws(args, args.env)
    try:
        _print_json(list_plugins(client, include_system=args.include_system))
        return 0
    except Exception as e:  # noqa: BLE001
        _print_json({"error": str(e)})
        return 1


def cmd_plugin_reverse(args: argparse.Namespace) -> int:
    client = _get_client_ws(args, args.env)
    try:
        plugin = reverse_plugin(client, args.name)
    except Exception as e:  # noqa: BLE001
        _print_json({"error": str(e)})
        return 1
    _print_json({"name": plugin.name, "version": plugin.version,
                 "steps": [s.name for s in plugin.steps]})
    return 0


# ----------------------------------------------------------------- entry


# ----------------------------------------------------------------- workflow (Phase 9)


def _stage_set(value: Optional[str]) -> Optional[set[str]]:
    """Parse a comma-separated ``--only``/``--skip`` value into a set (or None)."""
    if not value:
        return None
    return {s.strip() for s in value.split(",") if s.strip()}


def cmd_workflow_show(args: argparse.Namespace) -> int:
    project = load_project(args.project)
    _print_json(
        {
            "main_solution": project.main_solution,
            "ribbon_solution": project.ribbon_solution,
            "version": project.version,
            "publisher": project.publisher.name if project.publisher else None,
            "webresources": project.webresources,
            "counts": {
                "optionsets": len(project.optionsets),
                "tables": len(project.tables),
                "plugins": len(project.plugins),
                "forms": len(project.forms),
                "views": len(project.views),
                "ribbons": len(project.ribbons),
                "roles": len(project.roles),
            },
            "optionsets": project.optionsets,
            "tables": project.tables,
            "plugins": project.plugins,
            "forms": project.forms,
            "views": project.views,
            "ribbons": project.ribbons,
            "roles": project.roles,
        }
    )
    return 0


def _resolve_project_path(args: argparse.Namespace) -> str:
    """Resolve project.py path: workspace-aware with explicit override support."""
    if args.project != DEFAULT_PROJECT_PATH:
        return args.project  # explicit override
    ws = _try_workspace(args)
    if ws is not None:
        return str(ws.root / DEFAULT_PROJECT_PATH)
    return args.project  # CWD fallback


def cmd_workflow_lint(args: argparse.Namespace) -> int:
    project_path = _resolve_project_path(args)
    project = load_project(project_path)
    issues = lint_workflow(project, prefix=_effective_prefix(args))
    errors = [i for i in issues if i.severity == ERROR]
    warnings = [i for i in issues if i.severity == WARNING]
    status = "FAIL" if errors else "ok"
    print(f"[{status}] {project_path}  ({len(errors)} err, {len(warnings)} warn)")
    for i in issues:
        print(f"    {i.severity}: {i.message}")
    return 1 if has_errors(issues) else 0


def cmd_workflow_plan(args: argparse.Namespace) -> int:
    project_path = _resolve_project_path(args)
    project = load_project(project_path)
    client = _get_client_ws(args, args.env)
    _print_json(
        plan_workflow(
            client,
            project,
            prefix=_effective_prefix(args),
            include_roles=args.include_roles,
            skip=_stage_set(args.skip),
            only=_stage_set(args.only),
        )
    )
    return 0


def cmd_workflow_deploy(args: argparse.Namespace) -> int:
    project_path = _resolve_project_path(args)
    project = load_project(project_path)
    client = _get_client_ws(args, args.env)
    _print_json(
        deploy_workflow(
            client,
            project,
            prefix=_effective_prefix(args),
            include_roles=args.include_roles,
            skip=_stage_set(args.skip),
            only=_stage_set(args.only),
            publish=not args.no_publish,
        )
    )
    return 0


# ----------------------------------------------------------------- pipeline (Phase 10: CI/CD)


DEFAULT_PIPELINE_CONFIG = "config/pipeline.yaml"


def _load_pipeline_config(args: argparse.Namespace):
    """Load pipeline config from the --pipeline-config argument or workspace."""
    from .pipeline.config import load_pipeline_config
    config_path = getattr(args, "pipeline_config", DEFAULT_PIPELINE_CONFIG)

    # If in a workspace and using default path, resolve via workspace
    ws = _try_workspace(args)
    if ws is not None and config_path == DEFAULT_PIPELINE_CONFIG:
        config_path = str(ws.pipeline_config)
        project_root = str(ws.root)
    else:
        project_root = "."
    return load_pipeline_config(config_path, project_root=project_root)


def cmd_pipeline_map(args: argparse.Namespace) -> int:
    """Show branch → environment → strategy mapping."""
    config = _load_pipeline_config(args)
    print(f"{'Branch':20} {'Environment':15} {'Strategy':10} {'Export From':15} {'Managed':8} {'Approval':10} {'Auto Run':10}")
    print("-" * 98)
    for pattern, mapping in config.branches.items():
        print(
            f"{pattern:20} {mapping.environment:15} {mapping.deploy_strategy:10} "
            f"{(mapping.source_environment or 'N/A'):15} "
            f"{'Yes' if mapping.managed else 'No':8} "
            f"{'Yes' if mapping.require_approval else 'No':10} "
            f"{'Yes' if mapping.auto_run else 'No':10}"
        )
    return 0


def cmd_pipeline_compose(args: argparse.Namespace) -> int:
    """Auto-discover components and show dynamic Project (DEV only)."""
    config = _load_pipeline_config(args)
    from .pipeline.composer import SolutionComposer

    composer = SolutionComposer(config, publisher_prefix=_effective_prefix(args))
    result = composer.compose(args.branch)
    _print_json(result.to_dict())
    return 0


def cmd_pipeline_run(args: argparse.Namespace) -> int:
    """Run source-mode pipeline (lint→build→compose→plan→deploy→verify→publish)."""
    config = _load_pipeline_config(args)
    from .pipeline.source_executor import SourceExecutor
    from .pipeline.state import PipelineState

    skip_stages = _stage_set(args.skip) if args.skip else None
    executor = SourceExecutor(config, publisher_prefix=_effective_prefix(args))
    result = executor.run(
        args.branch,
        stop_after=args.stage,
        skip_stages=skip_stages,
    )

    # record in state tracker
    if result.compose_result is not None:
        state = PipelineState(config)
        state.record_source(result)

    _print_json(result.to_dict())
    return 0 if result.success else 1


def cmd_pipeline_promote(args: argparse.Namespace) -> int:
    """Run promote-mode pipeline (export from source env → import to target)."""
    config = _load_pipeline_config(args)
    from .pipeline.promote_executor import PromoteExecutor

    executor = PromoteExecutor(config, publisher_prefix=_effective_prefix(args))
    result = executor.run(args.branch)
    _print_json(result.to_dict())
    return 0 if result.success else 1


def cmd_pipeline_verify(args: argparse.Namespace) -> int:
    """Verify solution components match expectations."""
    config = _load_pipeline_config(args)
    from .pipeline.verifier import SolutionVerifier

    env = args.env
    if not env and args.branch:
        mapping = config.resolve_branch(args.branch)
        if mapping:
            env = mapping.environment

    if not env:
        print("error: --env or --branch is required for pipeline verify.")
        return 2

    verifier = SolutionVerifier(config, publisher_prefix=_effective_prefix(args))

    if args.solution_exists:
        # promote-mode: just check solution exists
        solution_name = config.get_solution_name(env)
        result = verifier.verify_promote(env, solution_name)
    else:
        # source-mode: need compose result
        from .pipeline.composer import SolutionComposer
        composer = SolutionComposer(config, publisher_prefix=_effective_prefix(args))
        branch = args.branch or "develop"
        compose_result = composer.compose(branch)
        result = verifier.verify_source(env, compose_result)

    _print_json(result.to_dict())
    return 0 if result.success else 1


def cmd_pipeline_configure(args: argparse.Namespace) -> int:
    """Configure env-specific settings (connection refs, env variables)."""
    config = _load_pipeline_config(args)
    from .pipeline.promote_executor import PromoteExecutor

    # use PromoteExecutor's configure stage
    executor = PromoteExecutor(config, publisher_prefix=_effective_prefix(args))
    # create a minimal result for the configure stage
    from .pipeline.promote_executor import PromoteResult
    result = PromoteResult(environment=args.env)
    output = executor._stage_configure(
        branch_mapping=config.resolve_branch("main") or config.branches.get("main"),
        result=result,
    )
    _print_json(output)
    return 0


def cmd_pipeline_rollback(args: argparse.Namespace) -> int:
    """Rollback to a previous solution version."""
    config = _load_pipeline_config(args)
    from .pipeline.state import PipelineState
    from .pipeline.pac_cli import PacCliWrapper

    state = PipelineState(config)
    target = state.get_rollback_target(args.env, version=args.to)
    if target is None:
        _print_json({"error": f"No rollback target found for env '{args.env}'" + (f", version '{args.to}'" if args.to else "")})
        return 1

    # for promote-mode rollback: re-import previous export
    export_path = target.get("export_path")
    if export_path and Path(export_path).exists():
        pac = PacCliWrapper(project_root=config.project_root)
        import_result = pac.import_solution(args.env, export_path)
        _print_json({
            "rollback_target": target,
            "import_result": import_result.to_dict(),
        })
        return 0 if import_result.success else 1
    else:
        _print_json({
            "error": "Rollback not possible: no export zip found for the target version",
            "target": target,
        })
        return 1


def cmd_pipeline_history(args: argparse.Namespace) -> int:
    """Show deployment history."""
    config = _load_pipeline_config(args)
    from .pipeline.state import PipelineState

    state = PipelineState(config)
    history = state.get_history(environment=args.env, limit=args.limit)
    _print_json({"deployments": history, "count": len(history)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pp",
        description="Power Platform Agent CLI — deploy Dataverse metadata from Python definitions.",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Workspace root path (auto-discovered from CWD if omitted).",
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
    parser.add_argument(
        "--forms-dir",
        default=DEFAULT_FORMS_DIR,
        help=f"Forms directory (default: {DEFAULT_FORMS_DIR}).",
    )
    parser.add_argument(
        "--views-dir",
        default=DEFAULT_VIEWS_DIR,
        help=f"Views directory (default: {DEFAULT_VIEWS_DIR}).",
    )
    parser.add_argument(
        "--ribbons-dir",
        default=DEFAULT_RIBBONS_DIR,
        help=f"Ribbons directory (default: {DEFAULT_RIBBONS_DIR}).",
    )
    parser.add_argument(
        "--ribbon-solution",
        default=DEFAULT_RIBBON_SOLUTION,
        help=f"Dedicated ribbon solution (default: {DEFAULT_RIBBON_SOLUTION}).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List discovered definitions.").set_defaults(func=cmd_list)

    # --- workspace group ---
    p_ws = sub.add_parser("workspace", help="Manage Power Platform workspaces (init/info/validate).")
    ws_sub = p_ws.add_subparsers(dest="workspace_command", required=True)

    p = ws_sub.add_parser("init", help="Initialize a new workspace (scaffold directories + configs).")
    p.add_argument("--path", default=None, help="Target directory (default: current directory).")
    p.add_argument("--name", default=None, help="Workspace name (default: directory name).")
    p.add_argument("--publisher", default=None, help="Publisher unique name (default: 'new').")
    p.add_argument("--prefix", default=None, help="Publisher prefix (default: 'new').")
    p.add_argument("--publisher-display", default=None, help="Publisher display name.")
    p.add_argument("--main-solution", default=None, help="Main solution unique name.")
    p.add_argument("--ribbon-solution", default=None, help="Ribbon solution unique name.")
    p.add_argument("--description", default=None, help="Workspace description.")
    p.add_argument("--force", action="store_true", help="Overwrite existing workspace files.")
    p.set_defaults(func=cmd_workspace_init)

    p = ws_sub.add_parser("info", help="Show resolved workspace paths and manifest.")
    p.set_defaults(func=cmd_workspace_info)

    p = ws_sub.add_parser("validate", help="Check workspace structure completeness.")
    p.set_defaults(func=cmd_workspace_validate)

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
    p_dep.add_argument(
        "--solution",
        default=None,
        help="Also add the entity (code 1) to this solution after deploy (idempotent).",
    )
    p_dep.add_argument(
        "--solution-clean",
        action="store_true",
        help="With --solution: add the entity as a SHELL + only its custom fields (code 2), "
        "not all OOB sub-components — keeps the solution portable (only self-authored content).",
    )
    p_dep.set_defaults(func=cmd_deploy)

    p_all = sub.add_parser("deploy-all", help="Deploy all definitions in dependency order.")
    p_all.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p_all.set_defaults(func=cmd_deploy_all)

    p_rev = sub.add_parser(
        "reverse",
        help="Export a table FROM Dataverse into a definition file or data dictionary.",
    )
    p_rev.add_argument("name", help="Logical name of the table to export (e.g. contact).")
    p_rev.add_argument("--env", default=None, help="Source environment (default: config 'current').")
    p_rev.add_argument(
        "-o", "--output", default=None,
        help="Output file (default: <definitions-dir>/<name>.py or <dict-dir>/tables/<schema>.md).",
    )
    p_rev.add_argument(
        "--dictionary", action="store_true", default=False,
        help="Generate a data dictionary Markdown doc instead of a .py definition file.",
    )
    p_rev.set_defaults(func=cmd_reverse)

    p_dict = sub.add_parser(
        "dictionary",
        help="Generate data dictionary Markdown from local metadata_py/ definitions.",
    )
    p_dict.add_argument(
        "--all", action="store_true", default=True,
        help="Generate docs for all discovered tables (default behavior).",
    )
    p_dict.add_argument(
        "-o", "--output", default=None,
        help="Output directory (default: <workspace>/docs/data_dictionary).",
    )
    p_dict.set_defaults(func=cmd_dictionary)

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

    p = sol_sub.add_parser(
        "delete", help="Delete an unmanaged solution (container teardown; components remain)."
    )
    p.add_argument("solution", help="Solution unique name.")
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.set_defaults(func=cmd_solution_delete)

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

    # --- webresource group (Phase 4) ---
    p_wr = sub.add_parser("webresource", help="Sync/publish a directory of web resources.")
    wr_sub = p_wr.add_subparsers(dest="webresource_command", required=True)

    p = wr_sub.add_parser("scan", help="List local files -> web resource names (offline).")
    p.add_argument("root", nargs="?", default=DEFAULT_WEBRESOURCES_ROOT, help="Local root dir.")
    p.set_defaults(func=cmd_webresource_scan)

    p = wr_sub.add_parser("plan", help="Read-only dry run of a web resource directory.")
    p.add_argument("root", nargs="?", default=DEFAULT_WEBRESOURCES_ROOT, help="Local root dir.")
    p.add_argument(
        "--include", nargs="+", default=None, metavar="GLOB",
        help="Only plan files whose relpath matches these fnmatch globs (e.g. 'js/order/*.js').",
    )
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.set_defaults(func=cmd_webresource_plan)

    p = wr_sub.add_parser("sync", help="Sync a web resource directory to Dataverse + publish.")
    p.add_argument("root", nargs="?", default=DEFAULT_WEBRESOURCES_ROOT, help="Local root dir.")
    p.add_argument("--solution", default=None, help="Add synced resources to this solution.")
    p.add_argument(
        "--include", nargs="+", default=None, metavar="GLOB",
        help="Only sync files whose relpath matches these fnmatch globs (e.g. 'js/order/*.js').",
    )
    p.add_argument(
        "--no-publish", action="store_true", help="Skip the targeted PublishXml after sync."
    )
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.set_defaults(func=cmd_webresource_sync)

    p = wr_sub.add_parser(
        "reverse", help="Pull web resources FROM Dataverse into a local directory (scoped)."
    )
    p.add_argument("root", nargs="?", default=DEFAULT_WEBRESOURCES_ROOT, help="Local root dir.")
    p.add_argument(
        "--name-prefix",
        default=None,
        help="Name prefix filter (default: '{prefix}_/' — only this publisher).",
    )
    p.add_argument("--env", default=None, help="Source environment (default: config 'current').")
    p.set_defaults(func=cmd_webresource_reverse)

    p = wr_sub.add_parser(
        "publish", help="Targeted-publish existing web resources by name (PublishXml)."
    )
    p.add_argument("names", nargs="+", help="Web resource name(s).")
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.set_defaults(func=cmd_webresource_publish)

    # --- form group (Phase 5) ---
    p_form = sub.add_parser("form", help="Author/sync/reverse structured model-driven forms.")
    form_sub = p_form.add_subparsers(dest="form_command", required=True)

    p = form_sub.add_parser("list", help="List forms for an entity (live).")
    p.add_argument("entity", help="Entity logical name (objecttypecode).")
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.set_defaults(func=cmd_form_list)

    p = form_sub.add_parser("show", help="Print a form model summary from a file (offline).")
    p.add_argument("file", help="Python form definition file exporting FORM.")
    p.set_defaults(func=cmd_form_show)

    p = form_sub.add_parser("lint", help="Offline convention check on a form file.")
    p.add_argument("file", help="Python form definition file exporting FORM.")
    p.set_defaults(func=cmd_form_lint)

    p = form_sub.add_parser("plan", help="Read-only dry run of one authored form.")
    p.add_argument("file", help="Python form definition file exporting FORM.")
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.set_defaults(func=cmd_form_plan)

    p = form_sub.add_parser("deploy", help="Deploy one authored form to Dataverse + publish.")
    p.add_argument("file", help="Python form definition file exporting FORM.")
    p.add_argument("--solution", default=None, help="Add the form to this solution (code 60).")
    p.add_argument(
        "--no-publish", action="store_true", help="Skip the entity-scoped PublishXml after deploy."
    )
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.set_defaults(func=cmd_form_deploy)

    p = form_sub.add_parser(
        "reverse", help="Pull every form for an entity FROM Dataverse into Python files."
    )
    p.add_argument("entity", help="Entity logical name (objecttypecode).")
    p.add_argument(
        "--forms-dir", default=DEFAULT_FORMS_DIR, help=f"Output dir (default: {DEFAULT_FORMS_DIR})."
    )
    p.add_argument("--env", default=None, help="Source environment (default: config 'current').")
    p.set_defaults(func=cmd_form_reverse)

    # --- view group (Phase 6) ---
    p_view = sub.add_parser("view", help="Author/sync/reverse structured model-driven views.")
    view_sub = p_view.add_subparsers(dest="view_command", required=True)

    p = view_sub.add_parser("list", help="List views for an entity (live).")
    p.add_argument("entity", help="Entity logical name (returnedtypecode).")
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.set_defaults(func=cmd_view_list)

    p = view_sub.add_parser("show", help="Print a view model summary from a file (offline).")
    p.add_argument("file", help="Python view definition file exporting VIEW.")
    p.set_defaults(func=cmd_view_show)

    p = view_sub.add_parser("lint", help="Offline convention check on a view file.")
    p.add_argument("file", help="Python view definition file exporting VIEW.")
    p.set_defaults(func=cmd_view_lint)

    p = view_sub.add_parser("plan", help="Read-only dry run of one authored view.")
    p.add_argument("file", help="Python view definition file exporting VIEW.")
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.set_defaults(func=cmd_view_plan)

    p = view_sub.add_parser("deploy", help="Deploy one authored view to Dataverse + publish.")
    p.add_argument("file", help="Python view definition file exporting VIEW.")
    p.add_argument("--solution", default=None, help="Add the view to this solution (code 26).")
    p.add_argument(
        "--no-publish", action="store_true", help="Skip the entity-scoped PublishXml after deploy."
    )
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.set_defaults(func=cmd_view_deploy)

    p = view_sub.add_parser(
        "reverse", help="Pull every view for an entity FROM Dataverse into Python files."
    )
    p.add_argument("entity", help="Entity logical name (returnedtypecode).")
    p.add_argument(
        "--views-dir", default=DEFAULT_VIEWS_DIR, help=f"Output dir (default: {DEFAULT_VIEWS_DIR})."
    )
    p.add_argument("--env", default=None, help="Source environment (default: config 'current').")
    p.set_defaults(func=cmd_view_reverse)

    # --- ribbon group (Phase 7) ---
    p_rib = sub.add_parser("ribbon", help="Author/deploy ribbon customizations (via dedicated solution).")
    rib_sub = p_rib.add_subparsers(dest="ribbon_command", required=True)

    p = rib_sub.add_parser("build", help="Print the RibbonDiffXml fragment from a file (offline).")
    p.add_argument("file", help="Python ribbon definition file exporting RIBBON.")
    p.set_defaults(func=cmd_ribbon_build)

    p = rib_sub.add_parser("show", help="Print a ribbon model summary from a file (offline).")
    p.add_argument("file", help="Python ribbon definition file exporting RIBBON.")
    p.set_defaults(func=cmd_ribbon_show)

    p = rib_sub.add_parser("lint", help="Offline convention check on a ribbon file.")
    p.add_argument("file", help="Python ribbon definition file exporting RIBBON.")
    p.set_defaults(func=cmd_ribbon_lint)

    p = rib_sub.add_parser("plan", help="Read-only dry run of one authored ribbon.")
    p.add_argument("file", help="Python ribbon definition file exporting RIBBON.")
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.set_defaults(func=cmd_ribbon_plan)

    p = rib_sub.add_parser("deploy", help="Deploy a ribbon via the dedicated solution (export->import->publish).")
    p.add_argument("file", help="Python ribbon definition file exporting RIBBON.")
    p.add_argument(
        "--no-publish", action="store_true", help="Skip the targeted PublishXml after import."
    )
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.set_defaults(func=cmd_ribbon_deploy)

    p = rib_sub.add_parser("reverse", help="Pull an entity's (or application) ribbon FROM the dedicated solution.")
    p.add_argument("entity", nargs="?", help="Entity logical name (omit with --application for the global ribbon).")
    p.add_argument("--application", action="store_true", help="Reverse the global Application Ribbon.")
    p.add_argument("--env", default=None, help="Source environment (default: config 'current').")
    p.set_defaults(func=cmd_ribbon_reverse)

    # --- plugin group (Phase 8) ---
    p_plg = sub.add_parser("plugin", help="Build + deploy .NET plugins (NuGet package preferred).")
    plg_sub = p_plg.add_subparsers(dest="plugin_command", required=True)

    p = plg_sub.add_parser("build", help="Build a plugin project (offline; no deploy).")
    p.add_argument("project_dir", help=".NET plugin project directory (contains the .csproj).")
    p.add_argument("def_file", help="Python plugin definition file exporting PROJECT (e.g. plugin_def.py).")
    p.set_defaults(func=cmd_plugin_build)

    p = plg_sub.add_parser("deploy", help="Build + deploy a plugin (register assembly + steps).")
    p.add_argument("project_dir", help=".NET plugin project directory (contains the .csproj).")
    p.add_argument("def_file", help="Python plugin definition file exporting PROJECT (e.g. plugin_def.py).")
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.add_argument("--plugin-solution", default=DEFAULT_PLUGIN_SOLUTION,
                   help=f"Solution to add the plugin to (default: {DEFAULT_PLUGIN_SOLUTION}).")
    p.set_defaults(func=cmd_plugin_deploy)

    p = plg_sub.add_parser("list", help="List plugin assemblies + packages in the environment.")
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.add_argument("--include-system", action="store_true", help="Include Microsoft.* system assemblies.")
    p.set_defaults(func=cmd_plugin_list)

    p = plg_sub.add_parser("reverse", help="Reverse a plugin assembly (+ its steps) into a model summary.")
    p.add_argument("name", help="Plugin assembly name.")
    p.add_argument("--env", default=None, help="Source environment (default: config 'current').")
    p.set_defaults(func=cmd_plugin_reverse)

    # --- workflow group (Phase 9) ---
    p_wf = sub.add_parser(
        "workflow",
        help="Run the full dev chain across two solutions (main + dedicated ribbon).",
    )
    wf_sub = p_wf.add_subparsers(dest="workflow_command", required=True)

    p = wf_sub.add_parser("show", help="Print the resolved project manifest (no network).")
    p.add_argument(
        "--project", default=DEFAULT_PROJECT_PATH, help=f"Project manifest (default: {DEFAULT_PROJECT_PATH})."
    )
    p.set_defaults(func=cmd_workflow_show)

    p = wf_sub.add_parser("lint", help="Offline manifest checks (no network).")
    p.add_argument(
        "--project", default=DEFAULT_PROJECT_PATH, help=f"Project manifest (default: {DEFAULT_PROJECT_PATH})."
    )
    p.set_defaults(func=cmd_workflow_lint)

    p = wf_sub.add_parser("plan", help="Read-only dry run of the whole chain.")
    p.add_argument(
        "--project", default=DEFAULT_PROJECT_PATH, help=f"Project manifest (default: {DEFAULT_PROJECT_PATH})."
    )
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.add_argument("--only", default=None, help="Comma-separated stages to run (default: all content stages).")
    p.add_argument("--skip", default=None, help="Comma-separated stages to skip.")
    p.add_argument(
        "--include-roles", action="store_true", help="Include the role-privilege-sync stage (default off)."
    )
    p.set_defaults(func=cmd_workflow_plan)

    p = wf_sub.add_parser("deploy", help="Run the full chain (ensure solutions -> stages -> publish).")
    p.add_argument(
        "--project", default=DEFAULT_PROJECT_PATH, help=f"Project manifest (default: {DEFAULT_PROJECT_PATH})."
    )
    p.add_argument("--env", default=None, help="Target environment (default: config 'current').")
    p.add_argument("--only", default=None, help="Comma-separated stages to run (default: all content stages).")
    p.add_argument(
        "--skip",
        default=None,
        help="Comma-separated stages to skip (e.g. 'plugins' to skip the .NET build).",
    )
    p.add_argument(
        "--include-roles", action="store_true", help="Include the role-privilege-sync stage (default off)."
    )
    p.add_argument("--no-publish", action="store_true", help="Skip the final PublishAllXml.")
    p.set_defaults(func=cmd_workflow_deploy)

    # --- pipeline group (Phase 10: CI/CD) ---
    p_pipe = sub.add_parser(
        "pipeline",
        help="CI/CD pipeline engine: source deploy (DEV) + promote (UAT/PROD).",
    )
    pipe_sub = p_pipe.add_subparsers(dest="pipeline_command", required=True)

    # pipeline map — show branch→env→strategy mapping
    p = pipe_sub.add_parser("map", help="Show branch → environment → strategy mapping.")
    p.add_argument(
        "--pipeline-config", default="config/pipeline.yaml",
        help="Pipeline config path (default: config/pipeline.yaml).",
    )
    p.set_defaults(func=cmd_pipeline_map)

    # pipeline compose — dynamic discovery (DEV only)
    p = pipe_sub.add_parser("compose", help="Auto-discover components and show dynamic Project (DEV only).")
    p.add_argument("--branch", required=True, help="Git branch name (e.g. develop, feature/CPQ).")
    p.add_argument(
        "--pipeline-config", default="config/pipeline.yaml",
        help="Pipeline config path (default: config/pipeline.yaml).",
    )
    p.set_defaults(func=cmd_pipeline_compose)

    # pipeline run — source mode (lint→build→compose→plan→deploy→verify→publish)
    p = pipe_sub.add_parser("run", help="Run source-mode pipeline (deploy source code to DEV).")
    p.add_argument("--branch", required=True, help="Git branch name (e.g. develop).")
    p.add_argument(
        "--stage", default=None,
        help="Stop after this stage (e.g. 'plan' for dry-run).",
    )
    p.add_argument(
        "--skip", default=None,
        help="Comma-separated stages to skip (e.g. 'build,plugins').",
    )
    p.add_argument(
        "--pipeline-config", default="config/pipeline.yaml",
        help="Pipeline config path (default: config/pipeline.yaml).",
    )
    p.set_defaults(func=cmd_pipeline_run)

    # pipeline promote — promote mode (export→import for UAT/PROD)
    p = pipe_sub.add_parser("promote", help="Run promote-mode pipeline (export from source env → import to target).")
    p.add_argument("--branch", required=True, help="Git branch name (e.g. release/1.0, main).")
    p.add_argument(
        "--pipeline-config", default="config/pipeline.yaml",
        help="Pipeline config path (default: config/pipeline.yaml).",
    )
    p.set_defaults(func=cmd_pipeline_promote)

    # pipeline verify — verify solution components
    p = pipe_sub.add_parser("verify", help="Verify solution components match expectations.")
    p.add_argument("--env", default=None, help="Environment to verify.")
    p.add_argument("--branch", default=None, help="Branch (to resolve environment).")
    p.add_argument("--solution-exists", action="store_true", help="Only check if solution exists.")
    p.add_argument(
        "--pipeline-config", default="config/pipeline.yaml",
        help="Pipeline config path (default: config/pipeline.yaml).",
    )
    p.set_defaults(func=cmd_pipeline_verify)

    # pipeline configure — set env-specific settings after import
    p = pipe_sub.add_parser("configure", help="Configure env-specific settings (connection refs, env variables).")
    p.add_argument("--env", required=True, help="Target environment.")
    p.add_argument(
        "--pipeline-config", default="config/pipeline.yaml",
        help="Pipeline config path (default: config/pipeline.yaml).",
    )
    p.set_defaults(func=cmd_pipeline_configure)

    # pipeline rollback — rollback to previous version
    p = pipe_sub.add_parser("rollback", help="Rollback to a previous solution version.")
    p.add_argument("--env", required=True, help="Target environment.")
    p.add_argument("--to", default=None, help="Version to rollback to (default: previous successful).")
    p.add_argument(
        "--pipeline-config", default="config/pipeline.yaml",
        help="Pipeline config path (default: config/pipeline.yaml).",
    )
    p.set_defaults(func=cmd_pipeline_rollback)

    # pipeline history — show deployment history
    p = pipe_sub.add_parser("history", help="Show deployment history.")
    p.add_argument("--env", default=None, help="Filter by environment.")
    p.add_argument("--limit", type=int, default=20, help="Max records to show (default: 20).")
    p.add_argument(
        "--pipeline-config", default="config/pipeline.yaml",
        help="Pipeline config path (default: config/pipeline.yaml).",
    )
    p.set_defaults(func=cmd_pipeline_history)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
