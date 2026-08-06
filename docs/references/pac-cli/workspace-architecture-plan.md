# Workspace Architecture Plan

> Introducing the **workspace** concept to separate the engine (pip package) from per-project data, so each Power Platform solution repo gets an independent, self-contained workspace.

**Version**: v1.0
**Date**: 2026-07-24
**Status**: Planning

---

## 1. Problem Statement

### Current State

This repo (`power-platform-agent`) conflates two concerns:

| Concern | Current Location | Should Be |
|---------|-----------------|-----------|
| **Engine** (CLI, deployer, pipeline, MCP) | `framework_power/`, `framework/` | Stays in pip package |
| **Workspace data** (tables, forms, configs) | `metadata_py/`, `config/`, `plugins/`, `webresources/`, `docs/` | Per-project repo |

All default paths are **relative to CWD** with no workspace abstraction:

```python
# cli.py — hardcoded relative paths
DEFAULT_DEFINITIONS_DIR = "metadata_py/tables"
PUBLISHERS_CONFIG = "config/publishers.yaml"
DEFAULT_PIPELINE_CONFIG = "config/pipeline.yaml"
CONFIG_PATH = "config/environments.yaml"  # runtime.py
```

### Pain Points

1. **External repos must clone this repo** — they get 200+ docs, 329 tests, sample plugins, and sample web resources they don't need.
2. **No workspace boundary** — the CLI can't tell "which project am I operating on?" It just assumes CWD has the right directories.
3. **No scaffolding** — each new project must manually create the directory structure and copy config templates.
4. **No workspace validation** — missing directories or configs fail at runtime with cryptic errors instead of upfront.
5. **No multi-workspace support** — can't manage multiple Power Platform projects from the same machine without `cd`-ing between them.

---

## 2. Architecture: Engine + Workspace Separation

```
┌──────────────────────────────────────────────────────────────┐
│  power-platform-agent (pip package — THE ENGINE)             │
│                                                              │
│  framework_power/     ← CLI, deployer, pipeline, models      │
│  framework/           ← MCP server (legacy)                  │
│  templates/           ← workspace scaffolding templates      │
│  setup.py             ← entry point: pp                      │
│                                                              │
│  Does NOT contain: metadata_py/, config/, plugins/, etc.    │
└──────────────────────────┬───────────────────────────────────┘
                           │ pip install power-platform-agent
                           ▼
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│  cpq-workspace     │  │  so-workspace      │  │  payment-workspace │
│                    │  │                    │  │                    │
│  pp-workspace.yaml │  │  pp-workspace.yaml │  │  pp-workspace.yaml │
│  metadata_py/      │  │  metadata_py/      │  │  metadata_py/      │
│  config/           │  │  config/           │  │  config/           │
│  plugins/          │  │  plugins/          │  │  plugins/          │
│  webresources/     │  │  webresources/     │  │  webresources/     │
│  docs/             │  │  docs/             │  │  docs/             │
│  .pp/ (state)      │  │  .pp/ (state)      │  │  .pp/ (state)      │
└─────────┬──────────┘  └─────────┬──────────┘  └─────────┬──────────┘
          │ pp deploy                │ pp deploy                │ pp deploy
          ▼                          ▼                          ▼
     DEV (unmanaged)            DEV (unmanaged)            DEV (unmanaged)
          │                          │                          │
          ▼                          ▼                          ▼
     UAT (unmanaged)            UAT (unmanaged)            UAT (unmanaged)
          │                          │                          │
          ▼                          ▼                          ▼
     PROD (managed)             PROD (managed)             PROD (managed)
```

**Key principle**: The engine is a **tool provider** (like `git`, `docker`, `kubectl`). It operates ON workspaces but does not contain workspace data. Each workspace is a self-contained project repo.

---

## 3. Workspace Design

### 3.1 Workspace Manifest: `pp-workspace.yaml`

The **anchor file** at the workspace root. Its presence tells the engine "this is a workspace."

```yaml
# pp-workspace.yaml — Power Platform Agent Workspace Manifest
# This file is the workspace root marker. The engine discovers it
# by searching from CWD upward (like .git directory).

# --- Identity ---
name: my-cpq-project           # workspace name (used in logs, state files)
description: "CPQ solution for Contoso"

# --- Publisher ---
publisher: contoso             # publisher unique name
publisher_prefix: con          # schema name prefix (e.g. con_quote)
publisher_display_name: "Contoso Solutions"

# --- Solutions ---
main_solution: con_CPQ         # unmanaged solution for tables/forms/views/etc.
ribbon_solution: con_CPQ_Ribbon # dedicated ribbon solution
version: "1.0.0.0"

# --- Directory layout (all relative to this file; optional overrides) ---
# If omitted, engine uses standard defaults (see 3.2).
dirs:
  tables: metadata_py/tables
  forms: metadata_py/forms
  views: metadata_py/views
  ribbons: metadata_py/ribbons
  roles: metadata_py/roles
  optionsets: metadata_py/optionsets
  solutions: metadata_py/solutions
  project: metadata_py/project.py
  webresources: webresources
  plugins: plugins
  config: config
  sources: sources

# --- Engine-managed (auto-created, gitignored) ---
state_dir: .pp/state
cache_dir: .pp/cache
```

### 3.2 Standard Directory Structure

```
my-project/                     # workspace root (= external repo root)
├── pp-workspace.yaml           # workspace manifest (ANCHOR FILE)
├── .gitignore                  # must include .pp/
│
├── metadata_py/                # Python metadata definitions
│   ├── __init__.py
│   ├── tables/                 # one .py per table (exports TABLE)
│   │   ├── __init__.py
│   │   └── con_quote.py
│   ├── forms/                  # one .py per form (exports FORM)
│   ├── views/                  # one .py per view (exports VIEW)
│   ├── ribbons/                # one .py per entity ribbon (exports RIBBON)
│   ├── roles/                  # one .py per role (exports ROLE)
│   ├── optionsets/             # one .py per global optionset (exports OPTIONSET)
│   ├── solutions/              # one .py per solution definition (exports SOLUTION)
│   └── project.py              # workflow manifest (exports PROJECT)
│
├── config/                     # environment + pipeline configs
│   ├── environments.yaml       # Dataverse environment URLs + auth
│   ├── publishers.yaml         # publisher registry
│   ├── pipeline.yaml           # CI/CD branch→env mapping
│   ├── environment_settings.yaml  # per-env connection refs/vars
│   └── environment_settings.yaml  # per-env connection refs/vars
│
├── plugins/                    # .NET plugin projects
│   └── MyPlugin/
│       ├── MyPlugin.csproj
│       ├── plugin_def.py       # plugin definition (steps, targets)
│       └── *.cs
│
├── webresources/               # JS/CSS/HTML web resources
│   ├── js/
│   ├── css/
│   └── html/
│
├── docs/                        # requirements, design docs, templates, data dictionary
│   ├── features/
│   ├── templates/
│   └── data_dictionary/
│
├── .pp/                        # engine-managed state (gitignored)
│   ├── state/                  # deployment history JSON
│   ├── cache/                  # reverse-export cache
│   └── logs/                   # execution logs
│
├── requirements.txt            # pip install power-platform-agent
└── README.md                   # project-specific docs
```

### 3.3 Workspace Discovery

The engine discovers the workspace by searching for `pp-workspace.yaml`:

```
1. --workspace <path>           (explicit CLI flag, highest priority)
2. PP_WORKSPACE env var          (for CI/CD pipelines)
3. CWD/pp-workspace.yaml         (current directory)
4. Walk up from CWD              (search parent dirs, like git)
5. Error: "Not in a Power Platform workspace"
```

```python
# framework_power/workspace.py (pseudo-code)

class Workspace:
    """Resolved workspace with all paths and manifest data."""

    root: Path                    # workspace root directory
    manifest: WorkspaceManifest   # parsed pp-workspace.yaml

    # resolved paths (absolute)
    tables_dir: Path
    forms_dir: Path
    views_dir: Path
    # ... etc

    @classmethod
    def discover(cls, explicit_path: Optional[str] = None) -> "Workspace":
        """Find and load the workspace."""
        path = explicit_path or os.environ.get("PP_WORKSPACE")
        if path:
            return cls._load(Path(path))

        # search from CWD upward
        cwd = Path.cwd()
        for d in [cwd, *cwd.parents]:
            manifest_path = d / "pp-workspace.yaml"
            if manifest_path.exists():
                return cls._load(d)

        raise WorkspaceNotFoundError(
            "Not in a Power Platform workspace. "
            "Run 'pp workspace init' to create one, "
            "or use --workspace <path>."
        )
```

### 3.4 `.pp/` — Engine-Managed State

The `.pp/` directory is engine-managed and should be in `.gitignore`:

```gitignore
# .gitignore (auto-generated by pp workspace init)
.pp/
```

Contents:
- `.pp/state/deployments.json` — deployment history (from pipeline state tracker)
- `.pp/state/pipeline_state.json` — current pipeline state per environment
- `.pp/cache/reverse/` — reverse-export cache (tables, forms, views)
- `.pp/logs/` — execution logs

---

## 4. Engine Changes

### 4.1 New Module: `framework_power/workspace.py`

```python
"""
Workspace discovery and path resolution.

A workspace is a directory containing pp-workspace.yaml. The engine
discovers it automatically (search from CWD upward) or via explicit
--workspace flag. All default paths (metadata_py/tables, config/, etc.)
are resolved relative to the workspace root, not CWD.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml

MANIFEST_FILENAME = "pp-workspace.yaml"

# Standard default dirs (relative to workspace root)
DEFAULT_DIRS = {
    "tables": "metadata_py/tables",
    "forms": "metadata_py/forms",
    "views": "metadata_py/views",
    "ribbons": "metadata_py/ribbons",
    "roles": "metadata_py/roles",
    "optionsets": "metadata_py/optionsets",
    "solutions": "metadata_py/solutions",
    "project": "metadata_py/project.py",
    "webresources": "webresources",
    "plugins": "plugins",
    "config": "config",
    "sources": "sources",
    "state": ".pp/state",
    "cache": ".pp/cache",
}


@dataclass
class WorkspaceManifest:
    """Parsed pp-workspace.yaml content."""
    name: str
    description: str = ""
    publisher: str = "new"
    publisher_prefix: str = "new"
    publisher_display_name: str = ""
    main_solution: str = ""
    ribbon_solution: str = ""
    version: str = "1.0.0.0"
    dirs: dict[str, str] = field(default_factory=dict)


@dataclass
class Workspace:
    """A resolved workspace with absolute paths."""
    root: Path
    manifest: WorkspaceManifest

    # Cached resolved paths
    _paths: dict[str, Path] = field(default_factory=dict, repr=False)

    @classmethod
    def discover(cls, explicit_path: Optional[str] = None) -> "Workspace":
        path = explicit_path or os.environ.get("PP_WORKSPACE")
        if path:
            root = Path(path).resolve()
            if not (root / MANIFEST_FILENAME).exists():
                raise FileNotFoundError(
                    f"No {MANIFEST_FILENAME} found at {root}"
                )
            return cls._load(root)

        cwd = Path.cwd()
        for d in [cwd, *cwd.parents]:
            if (d / MANIFEST_FILENAME).exists():
                return cls._load(d)

        raise NotInWorkspaceError(
            "Not in a Power Platform workspace.\n"
            "  - Run 'pp workspace init' to create one\n"
            "  - Or use --workspace <path> to specify explicitly\n"
            "  - Or set PP_WORKSPACE env var"
        )

    @classmethod
    def _load(cls, root: Path) -> "Workspace":
        manifest_path = root / MANIFEST_FILENAME
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        manifest = WorkspaceManifest(
            name=data.get("name", root.name),
            description=data.get("description", ""),
            publisher=data.get("publisher", "new"),
            publisher_prefix=data.get("publisher_prefix", "new"),
            publisher_display_name=data.get("publisher_display_name", ""),
            main_solution=data.get("main_solution", ""),
            ribbon_solution=data.get("ribbon_solution", ""),
            version=data.get("version", "1.0.0.0"),
            dirs=data.get("dirs", {}),
        )
        ws = cls(root=root, manifest=manifest)
        ws._resolve_paths()
        return ws

    def _resolve_paths(self) -> None:
        """Resolve all directory paths to absolute."""
        for key, default in DEFAULT_DIRS.items():
            override = self.manifest.dirs.get(key, default)
            self._paths[key] = (self.root / override).resolve()

    def path(self, key: str) -> Path:
        """Get an absolute path for a known directory key."""
        if key not in self._paths:
            raise KeyError(f"Unknown workspace path key: {key}")
        return self._paths[key]

    @property
    def tables_dir(self) -> Path: return self.path("tables")
    @property
    def forms_dir(self) -> Path: return self.path("forms")
    @property
    def views_dir(self) -> Path: return self.path("views")
    @property
    def ribbons_dir(self) -> Path: return self.path("ribbons")
    @property
    def roles_dir(self) -> Path: return self.path("roles")
    @property
    def optionsets_dir(self) -> Path: return self.path("optionsets")
    @property
    def solutions_dir(self) -> Path: return self.path("solutions")
    @property
    def project_path(self) -> Path: return self.path("project")
    @property
    def webresources_root(self) -> Path: return self.path("webresources")
    @property
    def plugins_dir(self) -> Path: return self.path("plugins")
    @property
    def config_dir(self) -> Path: return self.path("config")
    @property
    def state_dir(self) -> Path: return self.path("state")
    @property
    def cache_dir(self) -> Path: return self.path("cache")

    # Config file paths (convenience)
    @property
    def environments_config(self) -> Path:
        return self.config_dir / "environments.yaml"

    @property
    def publishers_config(self) -> Path:
        return self.config_dir / "publishers.yaml"

    @property
    def pipeline_config(self) -> Path:
        return self.config_dir / "pipeline.yaml"

    @property
    def environment_settings_config(self) -> Path:
        return self.config_dir / "environment_settings.yaml"

    @property
    def publishers_config(self) -> Path:
        return self.config_dir / "publishers.yaml"

    def ensure_dirs(self) -> None:
        """Create all standard directories if missing."""
        for key in ("tables", "forms", "views", "ribbons", "roles",
                     "optionsets", "solutions", "webresources", "plugins",
                     "config", "sources", "state", "cache"):
            self.path(key).mkdir(parents=True, exist_ok=True)

    def validate(self) -> list[str]:
        """Check workspace structure; return list of issue messages (empty = valid)."""
        issues = []
        for key in ("tables", "forms", "views", "ribbons", "roles",
                     "optionsets", "solutions", "config"):
            p = self.path(key)
            if not p.exists():
                issues.append(f"Missing directory: {p.relative_to(self.root)}")
        if not self.environments_config.exists():
            issues.append(f"Missing config: environments.yaml")
        if not self.manifest.name:
            issues.append("pp-workspace.yaml: 'name' is required")
        if not self.manifest.main_solution:
            issues.append("pp-workspace.yaml: 'main_solution' is required")
        return issues

    def to_dict(self) -> dict:
        return {
            "root": str(self.root),
            "name": self.manifest.name,
            "description": self.manifest.description,
            "publisher": self.manifest.publisher,
            "publisher_prefix": self.manifest.publisher_prefix,
            "main_solution": self.manifest.main_solution,
            "ribbon_solution": self.manifest.ribbon_solution,
            "version": self.manifest.version,
            "paths": {k: str(v) for k, v in self._paths.items()},
        }


class NotInWorkspaceError(Exception):
    """Raised when no workspace is found."""
    pass
```

### 4.2 CLI Changes: `framework_power/cli.py`

#### 4.2.1 New `workspace` Command Group

```python
# --- workspace group ---

def cmd_workspace_init(args: argparse.Namespace) -> int:
    """Initialize a new workspace in the current directory."""
    target = Path(args.path or ".").resolve()
    target.mkdir(parents=True, exist_ok=True)

    manifest_path = target / "pp-workspace.yaml"
    if manifest_path.exists() and not args.force:
        print(f"Error: workspace already exists at {target}")
        print("  Use --force to overwrite.")
        return 1

    # Generate manifest
    manifest = {
        "name": args.name or target.name,
        "description": args.description or "",
        "publisher": args.publisher or "new",
        "publisher_prefix": args.prefix or "new",
        "publisher_display_name": args.publisher_display or "",
        "main_solution": args.main_solution or f"{args.prefix or 'new'}_{args.name or target.name}",
        "ribbon_solution": args.ribbon_solution or f"{args.prefix or 'new'}_{args.name or target.name}_Ribbon",
        "version": "1.0.0.0",
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(_manifest_template(manifest))

    # Create standard directories
    ws = Workspace._load(target)
    ws.ensure_dirs()

    # Generate config templates
    _generate_config_templates(ws)

    # Generate .gitignore
    gitignore = target / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(".pp/\n*.pyc\n__pycache__/\n.env\n", encoding="utf-8")

    # Generate requirements.txt
    req = target / "requirements.txt"
    if not req.exists():
        req.write_text("power-platform-agent\n", encoding="utf-8")

    print(f"[ok] workspace initialized at {target}")
    print(f"  name: {manifest['name']}")
    print(f"  publisher: {manifest['publisher']} ({manifest['publisher_prefix']})")
    print(f"  main_solution: {manifest['main_solution']}")
    print(f"\nNext steps:")
    print(f"  1. Edit {target}/config/environments.yaml with your Dataverse URLs")
    print(f"  2. Set environment variables: DEV_TENANT_ID, DEV_CLIENT_ID, DEV_CLIENT_SECRET")
    print(f"  3. Create table definitions in {target}/metadata_py/tables/")
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
    return 0
```

#### 4.2.2 Global `--workspace` Flag

Add to the top-level parser:

```python
parser.add_argument(
    "--workspace", default=None,
    help="Workspace root path (auto-discovered from CWD if omitted).",
)
```

#### 4.2.3 All Existing Commands Become Workspace-Aware

**Before** (current):
```python
DEFAULT_DEFINITIONS_DIR = "metadata_py/tables"  # relative to CWD

def cmd_list(args):
    defs = discover_definitions(args.definitions_dir)  # uses default if not overridden
```

**After** (workspace-aware):
```python
def cmd_list(args):
    ws = _get_workspace(args)  # auto-discover or use --workspace
    defs = discover_definitions(str(ws.tables_dir))
```

**Helper function** in cli.py:

```python
_workspace_cache: Optional[Workspace] = None

def _get_workspace(args: argparse.Namespace) -> Workspace:
    """Get or discover the workspace (cached per invocation)."""
    global _workspace_cache
    if _workspace_cache is not None:
        return _workspace_cache
    explicit = getattr(args, "workspace", None)
    _workspace_cache = Workspace.discover(explicit)
    return _workspace_cache


def _publisher_prefix(ws: Workspace) -> str:
    """Read publisher prefix from workspace manifest (not config file)."""
    return ws.manifest.publisher_prefix


def _get_client(ws: Workspace, env: Optional[str] = None):
    """Build an authenticated client using workspace config."""
    return get_client(env, config_path=str(ws.environments_config))
```

### 4.3 `runtime.py` Changes

```python
# Before:
CONFIG_PATH = "config/environments.yaml"

def get_client(environment=None, config_path=CONFIG_PATH):
    ...

# After: add workspace-aware overload
def get_client_from_workspace(ws: Workspace, environment: Optional[str] = None):
    """Build client using workspace's environments config."""
    return get_client(environment, config_path=str(ws.environments_config))
```

### 4.4 `pipeline/config.py` Changes

```python
# Before:
DEFAULT_PIPELINE_CONFIG = "config/pipeline.yaml"

def load_pipeline_config(path=DEFAULT_PIPELINE_CONFIG, project_root="."):
    ...

# After: add workspace-aware loader
def load_pipeline_config_from_workspace(ws: Workspace):
    return load_pipeline_config(
        path=str(ws.pipeline_config),
        project_root=str(ws.root),
    )
```

### 4.5 `workflow.py` Changes

The `Project` dataclass stays the same, but the CLI resolves paths through the workspace:

```python
# cli.py — before:
def cmd_workflow_deploy(args):
    project = load_project(args.project)  # default: "metadata_py/project.py"

# cli.py — after:
def cmd_workflow_deploy(args):
    ws = _get_workspace(args)
    project_path = args.project or str(ws.project_path)
    project = load_project(project_path)
```

### 4.6 `setup.py` Changes

Exclude workspace data from the pip package:

```python
# Before:
packages=find_packages(exclude=["tests*", "docs*", ".pp-local*", "metadata*", "config*", "plugins*"]),

# After — cleaner exclusion:
packages=find_packages(exclude=[
    "tests*", "test*", "docs*", "metadata*", "metadata_py*",
    "config*", "plugins*", "webresources*", "sources*",
    "scripts*", "transformers*",
]),
```

Add `templates/` to package data for scaffolding:

```python
package_data={
    "": ["*.yaml", "*.md", "*.json"],
    "framework_power": ["templates/*"],
},
```

---

## 5. Workspace Scaffolding Templates

### 5.1 `templates/pp-workspace.yaml.template`

```yaml
# Power Platform Agent Workspace Manifest
# This file marks the workspace root. The engine discovers it automatically.

name: __WORKSPACE_NAME__
description: ""

publisher: __PUBLISHER__
publisher_prefix: __PREFIX__
publisher_display_name: ""

main_solution: __MAIN_SOLUTION__
ribbon_solution: __RIBBON_SOLUTION__
version: "1.0.0.0"
```

### 5.2 `templates/environments.yaml.template`

```yaml
# Dataverse environments configuration
# Replace URLs with your actual environment URLs

current: dev

environments:
  dev:
    url: "https://YOUR-ORG.crm.dynamics.com"
    auth_type: client_credentials
    # Credentials from env vars:
    tenant_id: ${DEV_TENANT_ID}
    client_id: ${DEV_CLIENT_ID}
    client_secret: ${DEV_CLIENT_SECRET}

  test:
    url: "https://YOUR-ORG-UAT.crm.dynamics.com"
    auth_type: client_credentials
    tenant_id: ${TEST_TENANT_ID}
    client_id: ${TEST_CLIENT_ID}
    client_secret: ${TEST_CLIENT_SECRET}

  production:
    url: "https://YOUR-ORG-PROD.crm.dynamics.com"
    auth_type: client_credentials
    tenant_id: ${PROD_TENANT_ID}
    client_id: ${PROD_CLIENT_ID}
    client_secret: ${PROD_CLIENT_SECRET}
```

### 5.3 `templates/pipeline.yaml.template`

```yaml
# CI/CD pipeline configuration
# Maps git branches to environments and deployment strategies

branches:
  develop:
    environment: dev
    deploy_strategy: source
    auto_run: true

  "release/*":
    environment: test
    deploy_strategy: promote
    source_environment: dev
    managed: false
    require_approval: true

  main:
    environment: production
    deploy_strategy: promote
    source_environment: test
    managed: true
    require_approval: true

# Solution naming
solution:
  main_template: "{publisher}_{project}"
  ribbon_template: "{publisher}_{project}_Ribbon"
```

### 5.4 `templates/publishers.yaml.template`

```yaml
current: __PUBLISHER__

publishers:
  __PUBLISHER__:
    display_name: __PUBLISHER_DISPLAY__
    prefix: __PREFIX__
```

---

## 6. New CLI Command Reference

### `pp workspace init`

```bash
# Interactive (prompts for missing values)
pp workspace init

# Non-interactive (all flags)
pp workspace init \
  --name my-cpq \
  --publisher contoso \
  --prefix con \
  --main-solution con_CPQ \
  --ribbon-solution con_CPQ_Ribbon

# Specify target directory
pp workspace init --path ./my-project

# Force overwrite existing
pp workspace init --force
```

Creates:
- `pp-workspace.yaml`
- `metadata_py/` with all subdirectories + `__init__.py`
- `config/` with template YAML files
- `webresources/`, `plugins/`, `docs/` directories
- `.gitignore` (includes `.pp/`)
- `requirements.txt` (includes `power-platform-agent`)

### `pp workspace info`

```bash
pp workspace info
pp workspace info --workspace /path/to/project
```

Output:
```json
{
  "root": "/Users/me/projects/my-cpq",
  "name": "my-cpq",
  "publisher": "contoso",
  "publisher_prefix": "con",
  "main_solution": "con_CPQ",
  "ribbon_solution": "con_CPQ_Ribbon",
  "version": "1.0.0.0",
  "paths": {
    "tables": "/Users/me/projects/my-cpq/metadata_py/tables",
    "forms": "/Users/me/projects/my-cpq/metadata_py/forms",
    ...
  }
}
```

### `pp workspace validate`

```bash
pp workspace validate
```

Checks:
- All required directories exist
- `config/environments.yaml` exists
- `pp-workspace.yaml` has required fields
- `metadata_py/project.py` exists (if workflow is used)

### All existing commands (workspace-aware)

```bash
# All these auto-discover the workspace from CWD:
pp list                          # lists tables from ws.tables_dir
pp deploy con_quote --env dev    # deploys using ws config
pp workflow deploy --env dev     # uses ws.project_path
pp pipeline run --branch develop # uses ws.pipeline_config
pp pipeline map                  # uses ws.pipeline_config
pp webresource sync              # uses ws.webresources_root
pp form deploy metadata_py/forms/con_quote_form.py  # still works with explicit paths
```

---

## 7. Migration Strategy for This Repo

### Phase 1: Add Workspace Module (non-breaking)

1. Create `framework_power/workspace.py` with the `Workspace` class
2. Add `workspace` command group to `cli.py`
3. Add `--workspace` global flag
4. Add workspace-aware helper functions (`_get_workspace`, `_publisher_prefix`)
5. Add `templates/` directory with scaffolding files
6. Update `setup.py` package exclusions

**Non-breaking**: All existing commands still work with CWD-relative paths as fallback. The workspace module is additive.

### Phase 2: Make Existing Commands Workspace-Aware (backward compatible)

1. Update each command handler to try workspace discovery first
2. If workspace found → use workspace paths
3. If no workspace found → fall back to CWD-relative paths (current behavior)

```python
def cmd_list(args):
    try:
        ws = _get_workspace(args)
        defs = discover_definitions(str(ws.tables_dir))
    except NotInWorkspaceError:
        # Fallback: use CWD-relative path (legacy behavior)
        defs = discover_definitions(args.definitions_dir)
```

**Backward compatible**: This repo continues to work as-is because it will have a `pp-workspace.yaml` at the root. External repos that haven't migrated yet still work with `--definitions-dir` overrides.

### Phase 3: Convert This Repo to a Reference Workspace

1. Create `pp-workspace.yaml` at this repo's root (so it becomes its own workspace)
2. Move `test/` data that depends on workspace structure to a `test/fixtures/` sub-workspace
3. Update tests to use workspace discovery or explicit workspace paths
4. The `metadata_py/`, `config/`, `plugins/`, `webresources/`, `docs/` stay in this repo as a **reference/example workspace** — they demonstrate the standard structure

### Phase 4: Clean Up Engine Package

1. Final `setup.py` excludes all workspace data from pip package
2. `pip install power-platform-agent` gives only the engine + templates
3. External repos use `pp workspace init` to scaffold their workspace
4. This repo's root `pp-workspace.yaml` serves as the reference/example

---

## 8. Benefits

| Benefit | Description |
|---------|-------------|
| **No more cloning** | External repos `pip install power-platform-agent` + `pp workspace init` |
| **Clear boundary** | `pp-workspace.yaml` marks the workspace root; engine knows exactly what it's operating on |
| **Scaffolding** | `pp workspace init` creates the full directory structure + config templates in seconds |
| **Validation** | `pp workspace validate` catches missing dirs/configs before runtime failures |
| **Multi-workspace** | Each project repo is independent; `cd` between them and the engine auto-discovers |
| **Explicit identity** | Workspace manifest carries publisher, solution names, version — no more reading from scattered config files |
| **CI/CD friendly** | `PP_WORKSPACE` env var or `--workspace` flag for pipeline runners |
| **Backward compatible** | Existing CWD-relative path overrides still work; migration is gradual |

---

## 9. File Impact Summary

### New Files

| File | Purpose |
|------|---------|
| `framework_power/workspace.py` | Workspace discovery, manifest, path resolution (~200 lines) |
| `templates/pp-workspace.yaml.template` | Workspace manifest scaffold |
| `templates/environments.yaml.template` | Environments config scaffold |
| `templates/pipeline.yaml.template` | Pipeline config scaffold |
| `templates/publishers.yaml.template` | Publishers config scaffold |
| `templates/.gitignore.template` | .gitignore scaffold |

### Modified Files

| File | Change |
|------|--------|
| `framework_power/cli.py` | Add `workspace` command group, `--workspace` flag, workspace-aware helpers, update all command handlers |
| `framework_power/runtime.py` | Add `get_client_from_workspace()` |
| `framework_power/pipeline/config.py` | Add `load_pipeline_config_from_workspace()` |
| `setup.py` | Update package exclusions, add templates to package_data |
| `docs/references/pac-cli/external-repo-integration-guide.md` | Update to use `pp workspace init` workflow |

### New at Repo Root (this repo becomes a reference workspace)

| File | Purpose |
|------|---------|
| `pp-workspace.yaml` | This repo's own workspace manifest (reference example) |

---

## 10. Implementation Order

```
Step 1: Create framework_power/workspace.py
        ↓
Step 2: Add templates/ directory with scaffolding files
        ↓
Step 3: Add workspace command group to cli.py (init/info/validate)
        ↓
Step 4: Add --workspace global flag + _get_workspace helper
        ↓
Step 5: Update all command handlers to be workspace-aware (with fallback)
        ↓
Step 6: Update runtime.py + pipeline/config.py with workspace-aware loaders
        ↓
Step 7: Create pp-workspace.yaml at this repo's root
        ↓
Step 8: Update setup.py package exclusions
        ↓
Step 9: Update external-repo-integration-guide.md
        ↓
Step 10: Run tests to verify backward compatibility
```

---

## 11. Open Questions

1. **Workspace manifest location**: `pp-workspace.yaml` at root (like `package.json`) vs `.pp/workspace.yaml` in a subdirectory (like `.git/`)?
   - **Recommendation**: Root-level `pp-workspace.yaml` — more visible, easier to find, follows `package.json` / `Cargo.toml` convention.

2. **Should `project.py` (workflow manifest) be merged into `pp-workspace.yaml`?**
   - **Recommendation**: Keep them separate. `pp-workspace.yaml` is identity + structure (static); `project.py` is component list (changes frequently during development). Different change cadence = different files.

3. **Publisher config**: Should `pp-workspace.yaml` carry publisher info directly, or still read from `config/publishers.yaml`?
   - **Recommendation**: `pp-workspace.yaml` carries the active publisher (single project = single publisher). `config/publishers.yaml` can remain for multi-publisher scenarios but is optional.

4. **Template customization**: Should `pp workspace init` support custom templates (e.g., `--template cpq`)?
   - **Recommendation**: Future enhancement. For now, `pp workspace init` creates the standard structure. Templates can be added later.
