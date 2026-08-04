# CI/CD Pipeline Enhancement Plan (v3 - Sequential ALM Promotion)

> **Status**: Planning (No code changes yet)
> **Date**: 2026-07-23 (v3 — corrected promotion chain)
> **Author**: power-platform-agent team
> **Related**: `pac-cli-overview.md`, `pac-solution-reference.md`, `pac-cli-integration-guide.md`

---

## 0. ALM Model (v3 — Sequential Promotion Chain)

### Correction history

- **v1 (wrong)**: Source code deploys to ALL environments (DEV, UAT, PROD) — anti-pattern
- **v2 (partially wrong)**: DEV exports to both UAT and PROD in parallel — PROD doesn't get the tested artifact
- **v3 (correct)**: Sequential chain — DEV → UAT → PROD. PROD exports from **UAT**, not DEV

### Correct model: sequential promotion

```
Source code ──deploy──▶ DEV (Unmanaged) ──export unmanaged──▶ UAT (Unmanaged)
                                                              │
                                                              └──export managed──▶ PROD (Managed)
```

| Environment | How it receives changes | Solution type | Export source | Tool |
|-------------|------------------------|---------------|---------------|------|
| **DEV** | Source code deployment | Unmanaged | N/A (source of truth) | `framework_power deploy` |
| **UAT** | Export from DEV → import | Unmanaged | DEV | `pac solution export/import` |
| **PROD** | Export from UAT → import | **Managed** | **UAT** (not DEV) | `pac solution export --managed/import` |

### Why PROD exports from UAT, not DEV

| Reason | Explanation |
|--------|-------------|
| **Artifact integrity** | PROD receives the exact solution that was tested and signed off in UAT. If exported from DEV, there's a risk window: DEV may have received new commits between UAT import and PROD export, meaning PROD gets something different from what was validated |
| **Traceability** | Each promotion is traceable: PROD deployment → specific UAT version → specific DEV version + Git commit. No "skip" in the chain |
| **Standard ALM practice** | Mirrors traditional software: build → staging → production. Artifacts flow sequentially, never skip a stage |
| **Approval gate meaning** | UAT sign-off approves a *specific solution version*. Exporting that same version to PROD guarantees the approved artifact is what ships |

### Key principles

1. **Source code only touches DEV** — `framework_power deploy` writes to DEV and only DEV
2. **Solution is the deployment artifact** for UAT and PROD — export/import, never source code
3. **Sequential promotion chain**: DEV → UAT → PROD, never DEV → PROD directly
4. **UAT gets unmanaged** (debuggable), **PROD gets managed** (locked down)
5. **Export source for PROD is UAT**, not DEV — the tested artifact is the shipped artifact
6. **framework_power's job**: get source code INTO DEV (unmanaged)
7. **pac CLI's job**: move solution along the chain DEV → UAT → PROD (export/import)
8. **Git's job**: version control source code + track solution exports

---

## 1. Problem Statement

### Current Pain Points

| # | Pain Point | Impact |
|---|-----------|--------|
| 1 | **Solution content is manually maintained** | Every deployment requires manually adding/removing components in the Dataverse UI |
| 2 | **No branch-to-environment mapping** | No clear rule for which branch deploys to which environment; ad-hoc and error-prone |
| 3 | **No pipeline automation** | DEV deployment is manual (`lint` → `plan` → `deploy` run by hand); UAT/PROD promotion is fully manual export/import in Maker Portal |
| 4 | **Solution drift** | Solution contents in Dataverse diverge from what's in source code |
| 5 | **No environment-specific configuration** | Connection references, environment variables, and solution names differ per env but aren't managed |
| 6 | **No rollback mechanism** | Failed deployments leave partial state; no way to revert |
| 7 | **Manual export/import is error-prone** | UAT/PROD promotion depends on someone manually exporting the right solution version from DEV and importing to target |

### What We Want

```
develop branch push
  → Pipeline: Lint → Build → Compose → Plan → Deploy to DEV (source code)
  → DEV now has the latest unmanaged solution

release/* branch push (or manual trigger)
  → Pipeline: Export from DEV → Import to UAT (pac CLI, unmanaged)

main branch push (or manual trigger + approval)
  → Pipeline: Export managed from UAT → Import to PROD (pac CLI, managed)
  → PROD gets the exact artifact that was tested in UAT
```

---

## 2. Design Principles

1. **Source code is the single source of truth — for DEV only** — Solution contents are derived from the codebase and deployed to DEV
2. **Solution is the deployment artifact — for UAT/PROD** — Environments beyond DEV receive solutions via export/import, not source code
3. **Sequential promotion chain: DEV → UAT → PROD** — Each environment exports from the previous one, never skips a stage
4. **Unmanaged in DEV/UAT, Managed in PROD** — Follows Microsoft ALM best practice
5. **Declarative over imperative** — A YAML pipeline config describes what to deploy, not how
6. **Non-destructive by default** — Aligns with existing `framework_power` principle (create/update only, no delete)
7. **Idempotent** — Running the pipeline multiple times produces the same result
8. **Dry-run first** — Always `plan` before `deploy` to DEV; always `export` before `import` to UAT/PROD
9. **Git-branch driven** — Branch names map to environments and deployment strategies automatically

---

## 3. Architecture Overview (Corrected)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        CI/CD Pipeline Engine                              │
│                                                                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐       │
│  │  Branch      │    │  Pipeline    │    │  Deploy Strategy     │       │
│  │  Detector    │───▶│  Config      │───▶│  Resolver            │       │
│  │  (git)       │    │  (YAML)      │    │  (source|promote)    │       │
│  └──────────────┘    └──────────────┘    └──────────┬───────────┘       │
│                                                      │                    │
│              ┌───────────────────────────────────────┼──────────┐       │
│              │                                       │          │       │
│              ▼                                       ▼          │       │
│  ┌──────────────────────┐          ┌──────────────────────┐    │       │
│  │  SOURCE Mode (DEV)    │          │  PROMOTE Mode (UAT/  │    │       │
│  │                       │          │  PROD)               │    │       │
│  │  1. Lint (offline)    │          │                      │    │       │
│  │  2. Build (.NET)      │          │  1. Export from src  │    │       │
│  │  3. Compose (discover)│          │     (DEV→UAT or      │    │       │
│  │  4. Plan (dry-run)    │          │      UAT→PROD)       │    │       │
│  │  5. Deploy to DEV     │          │  2. (Optional) Check │    │       │
│  │     (framework_power) │          │  3. Import to target │    │       │
│  │  6. Verify            │          │     (pac solution    │    │       │
│  │  7. Publish           │          │      import)         │    │       │
│  └──────────────────────┘          │  4. Verify           │    │       │
│              │                      └──────────────────────┘    │       │
│              │                               │                   │       │
│              ▼                               ▼                   │       │
│  ┌──────────────────────┐          ┌──────────────────────┐    │       │
│  │  Auth Manager        │          │  State Tracker       │    │       │
│  │  (env vars / pac     │          │  (deploy history)    │    │       │
│  │   auth profiles)     │          │                      │    │       │
│  └──────────────────────┘          └──────────────────────┘    │       │
└──────────────────────────────────────────────────────────────────┘       │
         │                    │                      │                     │
         ▼                    ▼                      ▼                     │
   config/environments   config/pipeline.yaml   .pp-local/pipeline-state.json
```

### Key insight: two completely different execution paths

**Source mode** (develop, feature/*, hotfix/* → DEV):
```
Git source code
  → framework_power deploy --env dev
  → DEV environment updated (unmanaged solution)
```

**Promote mode — to UAT** (release/* → UAT):
```
DEV environment (already has latest from source deploy)
  → pac solution export --env dev --name <solution>  (unmanaged)
  → solution zip file
  → pac solution import --env test --path <solution.zip>
  → UAT environment updated (unmanaged)
```

**Promote mode — to PROD** (main → PROD):
```
UAT environment (tested and signed off)
  → pac solution export --env test --name <solution> --managed
  → solution zip file (managed)
  → pac solution import --env production --path <solution.zip>
  → PROD environment updated (managed)
```

---

## 4. Core Configuration: `config/pipeline.yaml`

### 4.1 Full Schema (Corrected)

```yaml
# config/pipeline.yaml
# CI/CD Pipeline Configuration for Power Platform solution management
# Maps Git branches → environments → deployment strategy

# ============================================================
# Branch → Environment → Strategy Mapping
# ============================================================
branches:
  # Development: feature branches + develop
  develop:
    environment: dev
    deploy_strategy: source        # source = deploy from code; promote = export/import
    auto_run: true                 # push to develop triggers full pipeline
    require_approval: false

  feature/*:
    environment: dev
    deploy_strategy: source
    auto_run: false                # feature branches only plan (dry-run)
    plan_only: true
    require_approval: false

  # Release branch → UAT (promote from DEV)
  release/*:
    environment: test
    deploy_strategy: promote       # export from DEV, import to UAT
    source_environment: dev        # where to export from
    managed: false                 # UAT gets unmanaged solution
    auto_run: true
    require_approval: false
    pre_deploy_hooks:
      - run_solution_check         # pac solution check before import
    post_deploy_hooks:
      - verify_components          # verify all components exist in solution

  # Main branch → PROD (promote managed from UAT — sequential chain)
  main:
    environment: production
    deploy_strategy: promote
    source_environment: test         # export from UAT (not DEV!) — the tested artifact
    managed: true                    # PROD gets managed solution
    auto_run: false                  # production requires manual trigger
    require_approval: true
    approvers:
      - "tech-lead@company.com"
    pre_deploy_hooks:
      - run_solution_check
      - backup_solution            # export current PROD solution as backup
    post_deploy_hooks:
      - verify_components
      - notify_team

  # Hotfix → DEV first (source deploy), then cherry-pick to main for PROD
  hotfix/*:
    environment: dev
    deploy_strategy: source
    auto_run: true
    require_approval: false

# ============================================================
# Source Mode: Dynamic Solution Composition (DEV only)
# ============================================================
source_mode:
  # How to discover components from source code
  discovery:
    tables:
      source: "metadata_py/tables/"
      pattern: "*.py"
      exclude: ["__init__.py"]
      filter_custom: true          # skip standard (non-prefixed) reversed snapshots

    optionsets:
      source: "metadata_py/optionsets/"
      pattern: "*.py"
      exclude: ["__init__.py"]

    webresources:
      source: "webresources/"
      sync_all: true

    plugins:
      source: "plugins/"
      detect_by: "plugin_def.py"   # each subdir with this file is a plugin project

    forms:
      source: "metadata_py/forms/"
      pattern: "*.py"
      exclude: ["__init__.py"]

    views:
      source: "metadata_py/views/"
      pattern: "*.py"
      exclude: ["__init__.py"]

    ribbons:
      source: "metadata_py/ribbons/"
      pattern: "*.py"
      exclude: ["__init__.py"]

    roles:
      source: "metadata_py/roles/"
      pattern: "*.py"
      exclude: ["__init__.py"]

  # Solution splitting strategy (same as v1)
  solution_split:
    strategy: "two_solution"       # "single" | "two_solution" | "layered"
    two_solution:
      main_solution:
        contains: ["tables", "optionsets", "webresources", "plugins", "forms", "views", "roles"]
        name_template: "{publisher}_{project}"
      ribbon_solution:
        contains: ["ribbons"]
        name_template: "{publisher}_{project}_Ribbon"

  # Version strategy
  versioning:
    strategy: "git_tags"           # "manual" | "git_tags" | "file_tracking"
    git_tags:
      pattern: "v*"
      default: "1.0.0.0"

# ============================================================
# Promote Mode: Solution Export/Import (UAT/PROD)
# ============================================================
promote_mode:
  # Export configuration
  # Export source is determined by the branch mapping:
  #   - UAT (release/*): export from DEV (source_environment: dev)
  #   - PROD (main):     export from UAT (source_environment: test) — sequential chain
  export:
    # Uses pac solution export
    command: "pac solution export"
    # Where to save exported solution zips
    output_dir: ".pp-local/exports/"
    # Include solution version in filename
    filename_template: "{solution_name}_{version}_{managed_or_unmanaged}.zip"
    # Whether to run solution checker before export
    run_checker: false             # set per-branch in pre_deploy_hooks

  # Import configuration
  import:
    # Import to target environment
    # Uses pac solution import
    command: "pac solution import"
    # Import behavior
    async: true                    # use async import for large solutions
    publish_workflows: true        # activate processes after import
    overwrite_unmanaged_customizations: false  # don't overwrite customizations
    skip_dependency_check: false

  # Post-import: environment-specific configuration
  post_import_config:
    # Connection references and environment variables differ per env
    # These are set AFTER import, via Web API or pac CLI
    config_file: "config/environment_settings.yaml"

# ============================================================
# Pipeline Stages (Source Mode — DEV)
# ============================================================
stages_source:
  lint:
    enabled: true
    fail_on_error: true
    commands:
      - "pp workflow lint"
      - "pp solution lint --all"

  build:
    enabled: true
    fail_on_error: true
    steps:
      - name: "Build Plugins"
        command: "pp plugin build --all"

  compose:
    enabled: true
    command: "pp pipeline compose --branch {branch}"
    save_output: ".pp-local/compositions/{branch}_{timestamp}.json"

  plan:
    enabled: true
    fail_on_error: true
    command: "pp workflow plan --env dev"
    save_output: ".pp-local/plans/{branch}_{timestamp}.json"

  deploy:
    enabled: true
    fail_on_error: true
    command: "pp workflow deploy --env dev"

  verify:
    enabled: true
    fail_on_error: false
    checks:
      - name: "Verify Solution Components"
        command: "pp pipeline verify --env dev"

  publish:
    enabled: true
    command: "pp solution publish --env dev"

# ============================================================
# Pipeline Stages (Promote Mode — UAT/PROD)
# ============================================================
stages_promote:
  pre_check:
    enabled: true
    fail_on_error: true
    checks:
      - name: "Verify source environment solution exists"
        command: "pp pipeline verify --env {source_environment} --solution-exists"
        # source_environment = dev for UAT, test for PROD (resolved from pipeline.yaml)
      - name: "Solution Checker (optional)"
        command: "pac solution check --path {export_path} --geo UnitedStates"
        skip_environments: ["test"]  # only run for production

  export:
    enabled: true
    fail_on_error: true
    command: "pac solution export --env {source_environment} --name {solution_name} --path {export_path} {managed_flag}"
    # source_environment = dev (for UAT), test (for PROD)
    # managed_flag = "--managed" for PROD, "" for UAT

  import:
    enabled: true
    fail_on_error: true
    command: "pac solution import --env {environment} --path {export_path} --async --publish-workflows"

  configure:
    enabled: true
    fail_on_error: false
    # Set environment-specific connection references and env variables
    command: "pp pipeline configure --env {environment}"

  verify:
    enabled: true
    fail_on_error: false
    checks:
      - name: "Verify Solution Components"
        command: "pp pipeline verify --env {environment}"

# ============================================================
# Environment-Specific Settings
# ============================================================
environments:
  dev:
    deploy_on_merge: true
    deploy_strategy: source
    managed: false
    notify_on_success: false
    notify_on_failure: true

  test:
    deploy_on_merge: true
    deploy_strategy: promote
    source_environment: dev
    managed: false                 # UAT: unmanaged (allows debugging)
    notify_on_success: true
    notify_on_failure: true
    require_solution_check: true

  production:
    deploy_on_merge: false         # manual trigger only
    deploy_strategy: promote
    source_environment: test       # export from UAT (sequential: DEV → UAT → PROD)
    managed: true                  # PROD: managed (locked down)
    notify_on_success: true
    notify_on_failure: true
    require_approval: true
    require_solution_check: true
    backup_before_deploy: true
    backup_path: ".pp-local/backups/production/"

# ============================================================
# Rollback Configuration
# ============================================================
rollback:
  enabled: true
  strategy: "solution_reimport"    # re-import previous solution export
  keep_history: 5                  # keep last 5 exports per environment
  auto_rollback: false             # manual rollback by default
  rollback_command: "pp pipeline rollback --env {environment} --to {version}"

# ============================================================
# Notifications
# ============================================================
notifications:
  channels:
    - type: "webhook"
      url: "${PIPELINE_WEBHOOK_URL}"
      events: ["deploy_success", "deploy_failure", "promote_success", "promote_failure"]
      template: "power_platform"
  rules:
    dev:
      on_success: false
      on_failure: true
    test:
      on_success: true
      on_failure: true
    production:
      on_success: true
      on_failure: true
```

### 4.2 Key Design Decisions (Corrected)

| Decision | Rationale |
|----------|-----------|
| `deploy_strategy: source` for DEV | Source code deployment only to DEV |
| `deploy_strategy: promote` for UAT/PROD | Solution export/import, not source code |
| `managed: false` for UAT | Allows debugging and testing in UAT |
| `managed: true` for PROD | Locked down, prevents accidental edits |
| `source_environment: dev` for UAT | First hop: export unmanaged from DEV |
| `source_environment: test` for PROD | Second hop: export managed from **UAT** (the tested artifact) |
| Dynamic composition only in source mode | Auto-discovery is only needed when deploying source code to DEV |
| `solution_reimport` rollback | Re-import previous solution export (works for both managed/unmanaged) |
| `run_checker` before promote | Validate solution before importing to target |
| Sequential promotion (DEV→UAT→PROD) | PROD gets exactly what was tested in UAT, not a fresh export from DEV |

---

## 5. Two Pipeline Execution Flows

### 5.1 Source Mode Flow (develop → DEV)

```
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│  1.     │   │  2.     │   │  3.     │   │  4.     │   │  5.     │   │  6.     │   │  7.     │
│  Lint   │──▶│  Build  │──▶│ Compose │──▶│  Plan   │──▶│ Deploy  │──▶│ Verify  │──▶│ Publish │
│         │   │         │   │         │   │         │   │         │   │         │   │         │
│ Offline │   │ .NET    │   │ Auto-   │   │ Dry-run │   │ Write   │   │ Check   │   │ PubAll  │
│ checks  │   │ build   │   │ discover│   │ network │   │ to DEV  │   │ comps   │   │ Xml     │
└─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘
    │              │             │              │              │             │             │
    ▼              ▼             ▼              ▼              ▼             ▼             ▼
 Pass/Fail     Pass/Fail    Compose JSON   Plan JSON     Deploy JSON   Verify JSON   Publish OK
                                 │
                                 ▼
                         Dynamic Project
                         (auto-discovered
                          components)
```

**Commands executed**:
```bash
# 1. Lint (offline)
pp workflow lint
pp solution lint --all

# 2. Build
pp plugin build --all

# 3. Compose (dynamic discovery — NEW)
pp pipeline compose --branch develop
# Output: JSON with discovered components → generates project_dynamic.py

# 4. Plan (dry-run against DEV)
pp workflow plan --env dev

# 5. Deploy to DEV (source code → unmanaged solution)
pp workflow deploy --env dev

# 6. Verify (check solution components match source)
pp pipeline verify --env dev

# 7. Publish
pp solution publish --env dev
```

### 5.2 Promote Mode Flow (release/* → UAT, main → PROD)

**Two sequential hops**: DEV → UAT → PROD

```
Hop 1: DEV → UAT (release/* branch)
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  1.         │   │  2.         │   │  3.         │   │  4.         │
│  Pre-check  │──▶│  Export     │──▶│  Import     │──▶│  Verify     │
│             │   │  from DEV   │   │  to UAT     │   │             │
│ Verify DEV  │   │ (unmanaged) │   │ (unmanaged) │   │ Check comps │
│ has solution│   │             │   │             │   │ in UAT      │
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘

Hop 2: UAT → PROD (main branch, after UAT sign-off)
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  1.         │   │  2.         │   │  3.         │   │  4.         │   │  5.         │
│  Pre-check  │──▶│  Export     │──▶│  (Approval  │──▶│  Import     │──▶│  Verify     │
│             │   │  from UAT   │   │   gate)     │   │  to PROD    │   │             │
│ Solution    │   │ (managed)   │   │             │   │ (managed)   │   │ Check comps │
│ checker     │   │             │   │             │   │             │   │ in PROD     │
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
```

**Commands executed (UAT example — Hop 1)**:
```bash
# 1. Pre-check: verify DEV solution exists and is up-to-date
pp pipeline verify --env dev --solution-exists

# 2. Export from DEV (unmanaged)
pac solution export \
  --env dev \
  --name "ninebot-auto-create-component" \
  --path ".pp-local/exports/ninebot-auto-create-component_1.0.42_unmanaged.zip"
# Note: no --managed flag for UAT

# 3. Import to UAT
pac solution import \
  --env test \
  --path ".pp-local/exports/ninebot-auto-create-component_1.0.42_unmanaged.zip" \
  --async \
  --publish-workflows

# 4. Verify
pp pipeline verify --env test
```

**Commands executed (PROD example — Hop 2)**:
```bash
# 1. Pre-check: verify UAT solution is tested + solution checker
pp pipeline verify --env test --solution-exists
pac solution check \
  --path ".pp-local/exports/ninebot-auto-create-component_1.0.42_managed.zip" \
  --geo UnitedStates

# 2. Export from UAT (managed — note the --managed flag and --env test)
pac solution export \
  --env test \
  --name "ninebot-auto-create-component" \
  --path ".pp-local/exports/ninebot-auto-create-component_1.0.42_managed.zip" \
  --managed

# 3. Approval gate (wait for manual approval)

# 4. Import to PROD
pac solution import \
  --env production \
  --path ".pp-local/exports/ninebot-auto-create-component_1.0.42_managed.zip" \
  --async \
  --publish-workflows

# 5. Verify
pp pipeline verify --env production
```

### 5.3 Why UAT gets unmanaged and PROD gets managed

| Aspect | UAT (Unmanaged) | PROD (Managed) |
|--------|-----------------|----------------|
| Debugging | Can inspect/modify in Maker Portal | Locked — no edits |
| Rollback | Easy — just re-import previous | Requires managed solution upgrade/stage |
| Testing fidelity | Tests source code accurately | Tests the actual managed package |
| Data loss risk | Lower (can fix in place) | Higher (managed delete removes data) |
| Microsoft recommendation | Unmanaged OK for test | **Must be managed** |

**Alternative**: Some teams prefer managed in UAT too (to test exactly what goes to PROD). This is configurable in `pipeline.yaml`:
```yaml
test:
  managed: true  # set to true if you want to test the managed package in UAT
```

---

## 6. Dynamic Solution Composition (Source Mode Only)

### 6.1 The Core Problem

Currently, `metadata_py/project.py` has **explicit, hardcoded** component lists:

```python
PROJECT = Project(
    main_solution="new_WorkflowSoln",
    tables=["new_projectbudget"],        # must manually add each table
    plugins=["plugins/Smoke"],           # must manually add each plugin
    # ...
)
```

### 6.2 The Solution: Auto-Discovery (DEV only)

The pipeline engine scans source directories and dynamically composes the `Project` — but **only for DEV deployment**. Once deployed to DEV, the solution is exported as-is to UAT/PROD.

```python
# Pseudo-code for dynamic composition (NOT yet implemented)

def compose_project_dynamic(
    pipeline_config: PipelineConfig,
    branch: str,
) -> Project:
    """Compose a Project by auto-discovering components from source."""

    discovery = pipeline_config.source_mode.discovery

    # 1. Discover tables, optionsets, plugins, forms, views, ribbons, roles
    tables = discover_components(discovery.tables, prefix=publisher.prefix)
    optionsets = discover_components(discovery.optionsets)
    plugins = discover_plugin_projects(discovery.plugins)
    # ...

    # 2. Compose Project (solution names from environments.yaml)
    return Project(
        main_solution=env_config.solution.name,
        ribbon_solution=f"{env_config.solution.name}_Ribbon",
        tables=tables,
        optionsets=optionsets,
        plugins=plugins,
        # ...
    )
```

### 6.3 Component Override

Sometimes auto-discovery isn't enough. The pipeline config supports overrides:

```yaml
source_mode:
  discovery:
    # ... auto-discovery rules ...

  overrides:
    include_tables:
      - "account"       # force-include a standard table
    exclude_tables:
      - "new_deprecated_table"
    webresource_files:
      - "js/projectbudget/budgetForm.js"
```

---

## 7. New CLI Commands

### 7.1 Pipeline Commands (New)

```bash
# === Source Mode (DEV) ===

# Compose and show the dynamic project manifest (no network)
pp pipeline compose --branch develop
# Output: JSON with discovered components + resolved solution names

# Run full source pipeline (lint → build → compose → plan → deploy → verify → publish)
pp pipeline run --branch develop
pp pipeline run --branch develop --stage plan  # stop after plan

# === Promote Mode (UAT/PROD) ===

# Export solution from DEV
pp pipeline export --branch release/1.0
# Output: exports solution from DEV to .pp-local/exports/

# Import solution to target environment
pp pipeline import --branch release/1.0
# Output: imports exported solution to UAT

# Full promote (export + import)
#   release/* → exports from DEV (unmanaged) → imports to UAT
#   main      → exports from UAT (managed)   → imports to PROD
pp pipeline promote --branch release/1.0
pp pipeline promote --branch main

# === Shared ===

# Show branch → environment → strategy mapping
pp pipeline map
# Output:
#   develop      → dev         (source,   auto_run=true)
#   feature/*    → dev         (source,   plan_only=true)
#   release/*    → test        (promote,  export_from=dev,   managed=false)
#   main         → production  (promote,  export_from=test,  managed=true,  require_approval=true)

# Verify solution components match source code (source mode)
# or verify solution exists in target (promote mode)
pp pipeline verify --env dev
pp pipeline verify --env test --solution-exists

# Configure environment-specific settings after import
pp pipeline configure --env test
# Sets connection references, environment variables per config/environment_settings.yaml

# Rollback to previous version
pp pipeline rollback --env production --to 1.0.41.0

# Show deployment history
pp pipeline history --env dev
```

### 7.2 Existing Commands (Unchanged)

All existing `framework_power` commands remain unchanged:

```bash
# These still work exactly as before:
pp workflow show
pp workflow lint
pp workflow plan --env dev
pp workflow deploy --env dev
```

---

## 8. Comparison: Current vs. Enhanced Workflow

### Current Workflow (Manual)

```
Developer (DEV):
  1. Write table definition in metadata_py/tables/new_foo.py
  2. Manually edit metadata_py/project.py to add "new_foo" to tables list
  3. Run: pp lint new_foo
  4. Run: pp plan new_foo --env dev
  5. Run: pp deploy new_foo --env dev
  6. Open Dataverse UI → manually add new_foo to solution
  7. Commit + push

Promote to UAT (Manual):
  8. Open Maker Portal in DEV → export solution (unmanaged)
  9. Open Maker Portal in UAT → import solution
  10. Manually configure connection references / env variables

Promote to PROD (Manual):
  11. Open Maker Portal in UAT → export solution (managed)
  12. Open Maker Portal in PROD → import solution
  13. Manually configure connection references / env variables
```

### Enhanced Workflow (Automated)

```
Developer (DEV):
  1. Write table definition in metadata_py/tables/new_foo.py
  2. Commit + push to develop branch

Pipeline (Source Mode → DEV, automatic):
  3. Detect branch: develop → strategy: source → env: dev
  4. Lint: validate all definitions (offline)
  5. Build: compile plugins
  6. Compose: auto-discover new_foo.py → include in solution
  7. Plan: dry-run against dev
  8. Deploy: create table, add to solution, publish — to DEV only
  9. Verify: check solution contains new_foo

Promote to UAT (Pipeline Promote Mode):
  10. Push to release/1.0 branch (or manual trigger)
  11. Pipeline exports solution from DEV (unmanaged)
  12. Pipeline imports to UAT
  13. Pipeline configures env-specific settings
  14. Pipeline verifies

Promote to PROD (Pipeline Promote Mode):
  15. Push to main branch (or manual trigger + approval)
  16. Pipeline exports solution from UAT (managed) — the tested artifact
  17. Approval gate
  18. Pipeline imports to PROD
  19. Pipeline configures env-specific settings
  20. Pipeline verifies
```

---

## 9. Implementation Plan

### Phase 1: Pipeline Config + Source Mode (Core)

**Goal**: Create the pipeline YAML parser and dynamic component discovery for DEV.

**New Files**:
```
framework_power/
├── pipeline/                   # NEW: Pipeline engine
│   ├── __init__.py
│   ├── config.py               # Parse config/pipeline.yaml
│   ├── composer.py             # Dynamic solution composition (auto-discover) — DEV only
│   ├── executor.py             # Stage execution engine (source mode)
│   ├── verifier.py             # Post-deploy verification
│   ├── state.py                # Deployment state tracking
│   └── cli.py                  # CLI commands (pipeline compose/run/verify/...)
config/
└── pipeline.yaml               # NEW: Pipeline configuration
```

**Key Classes**:
- `PipelineConfig` — Parses `config/pipeline.yaml`
- `BranchMapping` — Resolves branch → environment + deploy_strategy
- `SolutionComposer` — Discovers components from source, builds `Project` (DEV only)
- `SourceExecutor` — Runs source-mode stages: lint → build → compose → plan → deploy → verify → publish
- `SolutionVerifier` — Compares expected vs actual solution contents

### Phase 2: Promote Mode (Export/Import)

**Goal**: Implement pac CLI integration for sequential promotion: DEV → UAT → PROD.

**New Classes**:
- `PromoteExecutor` — Runs promote-mode stages: pre-check → export → import → configure → verify
- `PacCliWrapper` — Wraps `pac solution export/import/check` commands
- `SolutionExporter` — Exports solution from source environment (DEV for UAT, UAT for PROD)
- `SolutionImporter` — Imports solution to target environment
- `EnvironmentConfigurator` — Sets connection references and env variables post-import

**Key commands wrapped**:
```bash
# Auth profiles for all environments
pac auth create --name dev --url <dev-url> --applicationId <id> --clientSecret <secret>
pac auth create --name test --url <test-url> --applicationId <id> --clientSecret <secret>
pac auth create --name prod --url <prod-url> --applicationId <id> --clientSecret <secret>

# Hop 1: DEV → UAT (unmanaged)
pac auth select --name dev
pac solution export --name <solution> --path <file.zip>
pac auth select --name test
pac solution import --path <file.zip> --async --publish-workflows

# Hop 2: UAT → PROD (managed) — sequential, exports from UAT not DEV
pac auth select --name test
pac solution export --name <solution> --path <file.zip> --managed
pac auth select --name prod
pac solution import --path <file.zip> --async --publish-workflows

pac solution check --path <file.zip> --geo UnitedStates
```

### Phase 3: Verification + State Tracking

**Goal**: Verify deployed solution matches expectations; track deployment history.

**Capabilities**:
- Query solution components from Dataverse (via Web API)
- Compare with expected components (source mode: from composition; promote mode: from export manifest)
- Track deployment history (version, timestamp, environment, strategy, result)
- `.pp-local/pipeline-state.json` for state persistence

### Phase 4: Rollback

**Goal**: Safe rollback mechanism.

**Capabilities**:
- For source mode (DEV): re-run deploy with previous code version
- For promote mode (UAT/PROD): re-import previous solution export
- Keep last N exports per environment (`.pp-local/exports/` and `.pp-local/backups/`)
- `pipeline rollback --env <env> --to <version>` command

### Phase 5: CI/CD Platform Integration

**Goal**: Integrate with GitHub Actions / Azure DevOps.

**New Files**:
```
scripts/
├── ci/
│   ├── github-actions/
│   │   └── power-platform-pipeline.yml
│   ├── azure-devops/
│   │   └── power-platform-pipeline.yml
│   └── jenkins/
│       └── Jenkinsfile
```

**Example GitHub Actions Workflow**:
```yaml
# .github/workflows/power-platform-pipeline.yml
name: Power Platform Pipeline

on:
  push:
    branches: [develop, main, 'release/*', 'hotfix/*']
  workflow_dispatch:  # manual trigger for PROD promotion

jobs:
  # Source mode: deploy to DEV
  deploy-dev:
    if: startsWith(github.ref_name, 'develop') || startsWith(github.ref_name, 'feature/') || startsWith(github.ref_name, 'hotfix/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Setup .NET
        uses: actions/setup-dotnet@v4
        with:
          dotnet-version: '8.0.x'
      - name: Run Source Pipeline
        env:
          DEV_TENANT_ID: ${{ secrets.DEV_TENANT_ID }}
          DEV_CLIENT_ID: ${{ secrets.DEV_CLIENT_ID }}
          DEV_CLIENT_SECRET: ${{ secrets.DEV_CLIENT_SECRET }}
        run: |
          pp pipeline run --branch ${{ github.ref_name }}

  # Promote mode: export from DEV → import to UAT
  promote-uat:
    if: startsWith(github.ref_name, 'release/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Install pac CLI
        run: dotnet tool install -g Microsoft.PowerApps.CLI.Tool
      - name: Promote to UAT
        env:
          DEV_TENANT_ID: ${{ secrets.DEV_TENANT_ID }}
          DEV_CLIENT_ID: ${{ secrets.DEV_CLIENT_ID }}
          DEV_CLIENT_SECRET: ${{ secrets.DEV_CLIENT_SECRET }}
          TEST_TENANT_ID: ${{ secrets.TEST_TENANT_ID }}
          TEST_CLIENT_ID: ${{ secrets.TEST_CLIENT_ID }}
          TEST_CLIENT_SECRET: ${{ secrets.TEST_CLIENT_SECRET }}
        run: |
          pp pipeline promote --branch ${{ github.ref_name }}

  # Promote mode: export managed from UAT → import to PROD (with approval)
  promote-prod:
    if: github.ref_name == 'main'
    environment: production  # GitHub environment with required reviewers
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Install pac CLI
        run: dotnet tool install -g Microsoft.PowerApps.CLI.Tool
      - name: Promote to PROD (managed, from UAT)
        env:
          # Export from UAT (test) — the tested artifact
          TEST_TENANT_ID: ${{ secrets.TEST_TENANT_ID }}
          TEST_CLIENT_ID: ${{ secrets.TEST_CLIENT_ID }}
          TEST_CLIENT_SECRET: ${{ secrets.TEST_CLIENT_SECRET }}
          # Import to PROD (production)
          PROD_TENANT_ID: ${{ secrets.PROD_TENANT_ID }}
          PROD_CLIENT_ID: ${{ secrets.PROD_CLIENT_ID }}
          PROD_CLIENT_SECRET: ${{ secrets.PROD_CLIENT_SECRET }}
        run: |
          pp pipeline promote --branch main
```

---

## 10. Best Practices Recommendations

### 10.1 Solution Layering Strategy

Instead of one monolithic solution, use layered solutions:

```
Solution Layers (bottom to top):
┌─────────────────────────────────────┐
│  Layer 3: Environment-specific      │  ← connection refs, env vars, config
│  (new_Project_EnvConfig)            │
├─────────────────────────────────────┤
│  Layer 2: Feature-specific          │  ← per-feature: CPQ, SO, PO, Payment
│  (new_Project_CPQ)                  │
│  (new_Project_SalesOrder)           │
├─────────────────────────────────────┤
│  Layer 1: Foundation                │  ← shared tables, optionsets, plugins
│  (new_Project_Foundation)           │
└─────────────────────────────────────┘
```

Each layer is a separate solution in DEV, exported and imported independently.

### 10.2 Git Branch Strategy

```
main ──────────────────────────────────────────────────────▶ PROD (promote managed)
  │                                                          ↑
  │    ┌── release/1.0 ───────────── merge ──┘
  │    │                                       ↑
  │    │    ┌── hotfix/bug-123 ── merge ──┘
  │    │    │
  │    │    │
  ├── develop ──────────────────────────────────────────────▶ DEV (source deploy)
  │    │
  │    ├── feature/CPQ-module ── (plan only) ──▶ DEV (dry-run)
  │    ├── feature/payment ──── (plan only) ──▶ DEV (dry-run)
  │    └── feature/so-model ─── (plan only) ──▶ DEV (dry-run)
```

| Branch | Environment | Strategy | Export Source | Managed | Approval |
|--------|------------|----------|---------------|---------|----------|
| `feature/*` | dev | source (plan only) | N/A | N/A | No |
| `develop` | dev | source (deploy) | N/A | No | No |
| `release/*` | test | promote | **DEV** | No | No |
| `hotfix/*` | dev | source (deploy) | N/A | No | No |
| `main` | production | promote | **UAT** | **Yes** | **Yes** |

### 10.3 Environment Variable Management

Connection references and environment variables differ per environment. These are configured **after import** in promote mode:

```yaml
# config/environment_settings.yaml
environment_variables:
  dev:
    - name: "new_ApiEndpoint"
      value: "https://dev-api.company.com"
  test:
    - name: "new_ApiEndpoint"
      value: "https://test-api.company.com"
  production:
    - name: "new_ApiEndpoint"
      value: "https://api.company.com"

connection_references:
  dev:
    - name: "new_SharePointConnection"
      connector_id: "/providers/Microsoft.PowerApps/apis/shared_sharepointonline"
      connection_id: "<dev-connection-id>"
  test:
    - name: "new_SharePointConnection"
      connector_id: "/providers/Microsoft.PowerApps/apis/shared_sharepointonline"
      connection_id: "<test-connection-id>"
  production:
    - name: "new_SharePointConnection"
      connector_id: "/providers/Microsoft.PowerApps/apis/shared_sharepointonline"
      connection_id: "<prod-connection-id>"
```

### 10.4 PAC CLI Integration Points (Corrected)

| Pipeline Stage | Source Mode (DEV) | Promote Mode — UAT | Promote Mode — PROD |
|---------------|-------------------|---------------------|---------------------|
| Lint | `workflow lint` | N/A | N/A |
| Build | `plugin build` | N/A | N/A |
| Compose | `pipeline compose` (auto-discover) | N/A | N/A |
| Plan | `workflow plan` | N/A | N/A |
| Deploy | `workflow deploy` | N/A | N/A |
| Export | N/A | `pac solution export` (from DEV) | `pac solution export --managed` (from **UAT**) |
| Import | N/A | `pac solution import` (to UAT) | `pac solution import` (to PROD) |
| Configure | N/A | `pipeline configure` (env vars, connection refs) | `pipeline configure` (env vars, connection refs) |
| Verify | `pipeline verify` (source vs solution) | `pipeline verify` (solution exists in UAT) | `pipeline verify` (solution exists in PROD) |
| Check | N/A (optional) | `pac solution check` (optional) | `pac solution check` (required) |
| Publish | `solution publish` | Done automatically by `--publish-workflows` | Done automatically by `--publish-workflows` |
| Rollback | Re-deploy previous code | Re-import previous export | Re-import previous export |
| Auth | Env vars | `pac auth` (DEV + UAT profiles) | `pac auth` (UAT + PROD profiles) |
| Version | `git tags` | `pac solution version` or from git tags | Inherited from UAT export |

---

## 11. Risk Assessment & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Auto-discovery picks up unintended files | Medium | Low | `exclude` patterns + `filter_custom` |
| DEV solution not up-to-date before promote | Medium | High | Pre-check stage verifies DEV solution exists |
| Managed import fails in PROD | Medium | High | Solution checker + backup before import |
| Connection references not set after import | High | Medium | `configure` stage sets them automatically |
| Solution version mismatch between DEV and export | Low | Medium | Version from git tags ensures consistency |
| Pipeline deploys to wrong environment | Low | Critical | Branch mapping validation + approval gate for prod |
| pac CLI auth profile confusion | Medium | High | Named auth profiles per environment |
| Managed solution delete in PROD removes data | Low | Critical | Never auto-delete; import as upgrade, not delete+reinstall |

---

## 12. Migration Path

### Step 1: Create pipeline.yaml (No code changes)
- Create `config/pipeline.yaml` with branch mapping
- Run `pipeline compose --branch develop` to see what dynamic composition would produce
- Compare with existing `project.py` — ensure they match

### Step 2: Implement source mode (DEV automation)
- Implement `framework_power/pipeline/` module with source mode
- Add `pipeline compose`, `pipeline run`, `pipeline verify` commands
- No changes to existing commands — pipeline is additive
- Test: push to develop → auto-deploy to DEV

### Step 3: Implement promote mode (UAT automation)
- Add `PacCliWrapper` for `pac solution export/import`
- Add `pipeline export`, `pipeline import`, `pipeline promote` commands
- Test: push to release/* → auto-export from DEV → import to UAT

### Step 4: Enable PROD promotion (with approval)
- Add approval gate for main branch
- PROD exports from **UAT** (not DEV) — sequential promotion chain
- Test: push to main → export managed from UAT → approval → import to PROD

### Step 5: Deprecate manual project.py editing
- Once dynamic composition is stable, `project.py` becomes auto-generated
- `pipeline compose` writes `metadata_py/project_generated.py`
- `workflow.py` loads from generated file if it exists

### Step 6: CI/CD platform integration
- Add GitHub Actions / Azure DevOps workflow templates
- Connect pipeline to actual CI/CD triggers

---

## 13. Alternative Approaches Considered

### Alternative A: Pure PAC CLI Pipeline (Partially adopted for promote mode)

**Approach**: Use `pac solution pack/unpack/import/export` as the entire pipeline.

**Where it fits**: Promote mode (UAT/PROD) uses `pac solution export/import` exclusively.
**Where it doesn't fit**: Source mode (DEV) still uses `framework_power` because:
- PAC CLI works at the solution-zip level, not the component level
- Loses the type-safe Python models that are this project's key advantage
- PAC doesn't support the project's 9-phase workflow with dependency ordering

### Alternative B: Export from UAT to PROD (Adopted in v3)

**Approach**: Export managed solution from UAT (not DEV) for PROD promotion.

**Why adopted (corrected from v2)**:
- **Artifact integrity**: PROD receives the exact solution that was tested and signed off in UAT. Exporting from DEV risks a gap: DEV may have received new commits between UAT import and PROD export
- **Traceability**: Sequential chain PROD ← UAT ← DEV ← source code, no skipped stages
- **Standard ALM practice**: Mirrors build → staging → production in traditional software
- **Approval semantics**: UAT sign-off approves a *specific solution version*; exporting that version to PROD guarantees the approved artifact ships

**Implementation**: `source_environment: test` in pipeline.yaml for the `main` branch mapping. The `PacCliWrapper` resolves the export source from the branch config, not hardcoded.

**Precondition**: UAT must be kept clean — no manual unmanaged edits in UAT. If testing reveals issues, fixes go back to DEV → re-export → re-import to UAT → re-test → then promote to PROD.

### Alternative C: Use pac solution clone + Git-based source control (Future consideration)

**Approach**: Use `pac solution clone` to unpack solution into source files, store in Git, and `pac solution pack` to rebuild.

**Why future**: This is Microsoft's newer ALM approach, but it requires restructuring the project from Python-first to PAC-YAML-first. Could be considered if the team wants to move away from Python models.

### Alternative D: Power Platform Pipelines (Future consideration)

**Approach**: Use Microsoft's native Power Platform Pipelines feature (now GA).

**Why future**: Provides built-in solution promotion with approval gates, but:
- Less flexible than custom pipeline for complex scenarios
- Doesn't integrate with the project's Python-first source code approach
- Could be used alongside this pipeline for the promote stages

---

## 14. Open Questions

| # | Question | Priority | Notes |
|---|----------|----------|-------|
| 1 | Should UAT use managed or unmanaged solutions? | High | Default: unmanaged (debugging); configurable in pipeline.yaml |
| 2 | Should the pipeline support multiple solutions (layered)? | High | See solution layering strategy in §10.1 |
| 3 | How to handle solution upgrades (not just create/update)? | Medium | `pac solution import` handles upgrade; need to test |
| 4 | Should connection references be in a separate solution? | High | Best practice: yes, separate env-config solution |
| 5 | How to handle canvas apps and Power Pages? | Low | PAC CLI supports these; project doesn't currently manage them |
| 6 | Should the pipeline integrate with Azure Key Vault for secrets? | Medium | Currently using env vars; Key Vault would be more secure |
| 7 | Should we use pac solution clone/unpack for source control? | Medium | Alternative to Python-first models; future consideration |

---

## 15. Summary

This plan (v3, sequential promotion) introduces a **CI/CD pipeline engine** with **two distinct execution modes**:

1. **Source mode** (DEV): `framework_power deploy` from source code → unmanaged solution in DEV
2. **Promote mode — Hop 1** (UAT): `pac solution export` from DEV (unmanaged) → `pac solution import` to UAT
3. **Promote mode — Hop 2** (PROD): `pac solution export --managed` from **UAT** → `pac solution import` to PROD

Key corrections across versions:
- **v1 → v2**: Source code only touches DEV, not all environments. Solution export/import for UAT/PROD
- **v2 → v3**: PROD exports from **UAT** (sequential chain), not from DEV (parallel). The tested artifact is the shipped artifact

**The promotion chain**: `Source code → DEV (unmanaged) → UAT (unmanaged) → PROD (managed)`

The design is **additive** — no existing commands change, and the pipeline can be adopted incrementally.
