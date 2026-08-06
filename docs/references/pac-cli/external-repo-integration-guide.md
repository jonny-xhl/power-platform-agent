# External Repository Integration Guide

> How to use `power-platform-agent` as a tooling dependency in separate solution code repositories.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  power-platform-agent (this repo)                   │
│  Role: pip package · CLI tool · pipeline engine     │
│  Contains: framework_power/, CI templates, configs   │
│  Does NOT contain: actual solution source code       │
└──────────────────────┬──────────────────────────────┘
                       │ pip install
                       ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  solution-repo-A │  │  solution-repo-B │  │  solution-repo-C │
│  (e.g. CPQ)      │  │  (e.g. SO)       │  │  (e.g. Payment)  │
│                  │  │                  │  │                  │
│  metadata_py/    │  │  metadata_py/    │  │  metadata_py/    │
│  plugins/        │  │  plugins/        │  │  plugins/        │
│  webresources/   │  │  webresources/   │  │  webresources/   │
│  config/         │  │  config/         │  │  config/         │
│                  │  │                  │  │                  │
│  pipeline.yaml   │  │  pipeline.yaml   │  │  pipeline.yaml   │
│  environments.yaml  │  environments.yaml  │  environments.yaml│
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                     │
         ▼                     ▼                     ▼
    DEV (unmanaged)        DEV (unmanaged)        DEV (unmanaged)
         │                     │                     │
         ▼                     ▼                     ▼
    UAT (unmanaged)        UAT (unmanaged)        UAT (unmanaged)
         │                     │                     │
         ▼                     ▼                     ▼
    PROD (managed)         PROD (managed)         PROD (managed)
```

**Key principle**: `power-platform-agent` is a **tooling library**, not a solution repo. Each solution repo installs it as a dependency and follows the standard directory convention.

---

## 2. Step-by-Step: Setting Up a New Solution Repo

### Step 1: Create the solution repo

```bash
mkdir my-cpq-solution && cd my-cpq-solution
git init
```

### Step 2: Install power-platform-agent as a dependency

Add to `requirements.txt`:

```
# Install from git (recommended for private repos)
git+https://github.com/your-org/power-platform-agent.git@main

# Or install from local path (for development)
# -e ../power-platform-agent
```

Then:

```bash
pip install -r requirements.txt
```

### Step 3: Initialize the workspace (one command scaffolds everything)

```bash
pp workspace init \
  --name my-cpq \
  --publisher contoso \
  --prefix con \
  --main-solution con_CPQ \
  --ribbon-solution con_CPQ_Ribbon
```

This automatically creates:

```
my-cpq-solution/
├── pp-workspace.yaml           # workspace manifest (ANCHOR FILE)
├── .gitignore                  # includes .pp/, __pycache__, .env
├── requirements.txt            # includes power-platform-agent
├── metadata_py/
│   ├── __init__.py
│   ├── tables/                 # one .py per table (exports TABLE)
│   ├── forms/                  # one .py per form (exports FORM)
│   ├── views/                  # one .py per view (exports VIEW)
│   ├── ribbons/                # one .py per entity ribbon
│   ├── roles/                  # one .py per role
│   ├── optionsets/             # one .py per global optionset
│   ├── solutions/              # solution definitions
│   └── project.py              # workflow manifest
├── config/
│   ├── environments.yaml       # Dataverse environment URLs + auth
│   ├── pipeline.yaml           # CI/CD branch→env mapping
│   ├── publishers.yaml         # publisher + naming rules
├── plugins/                    # .NET plugin projects
├── webresources/               # JS/CSS/HTML
├── docs/                        # requirements, design docs, templates, data dictionary
└── .pp/                        # engine-managed state (gitignored)
    ├── state/                  # deployment history
    ├── cache/                  # reverse-export cache
    └── logs/                   # execution logs
```

### Step 4: Edit environment config

Edit `config/environments.yaml` with your Dataverse URLs and set environment variables.

```yaml
environments:
  dev:
    name: "Development"
    url: "https://myorg-dev.crm.dynamics.com"
    client_id: "${DEV_CLIENT_ID}"
    client_secret: "${DEV_CLIENT_SECRET}"
    solution:
      name: "myorg_cpq"           # YOUR solution name
      publisher: "myorg"
      version: "1.0.0.0"

  test:
    name: "Testing"
    url: "https://myorg-test.crm.dynamics.com"
    client_id: "${TEST_CLIENT_ID}"
    client_secret: "${TEST_CLIENT_SECRET}"
    solution:
      name: "myorg_cpq"
      publisher: "myorg"
      version: "1.0.0.0"

  production:
    name: "Production"
    url: "https://myorg.crm.dynamics.com"
    client_id: "${PROD_CLIENT_ID}"
    client_secret: "${PROD_CLIENT_SECRET}"
    solution:
      name: "myorg_cpq"
      publisher: "myorg"
      version: "1.0.0.0"
```

**Edit `config/pipeline.yaml`** — adjust branch patterns if needed (usually keep defaults):

```yaml
branches:
  develop:
    environment: dev
    deploy_strategy: source
    auto_run: true
  # ... (keep the rest from template)
```

### Step 5: Set up CI/CD

#### Option A: GitHub Actions

Copy the template and adjust:

```bash
cp ../power-platform-agent/scripts/ci/github-actions/power-platform-pipeline.yml \
   .github/workflows/deploy.yml
```

The workflow template already handles:
- `develop` push → source deploy to DEV
- `release/*` push → promote to UAT
- `main` push → promote managed to PROD (with approval)

Set these GitHub secrets:

| Secret | Description |
|--------|-------------|
| `DEV_CLIENT_ID` | DEV App Registration client ID |
| `DEV_CLIENT_SECRET` | DEV App Registration client secret |
| `TEST_CLIENT_ID` | UAT App Registration client ID |
| `TEST_CLIENT_SECRET` | UAT App Registration client secret |
| `PROD_CLIENT_ID` | PROD App Registration client ID |
| `PROD_CLIENT_SECRET` | PROD App Registration client secret |

#### Option B: Azure DevOps

```bash
cp ../power-platform-agent/scripts/ci/azure-devops/power-platform-pipeline.yml \
   azure-pipelines.yml
```

### Step 6: Verify setup

After `pip install`, the `pp` command is available (shorter than `pp`):

```bash
# Check branch → environment mapping
pp pipeline map

# Check auto-discovered components
pp pipeline compose --branch develop

# Dry-run (plan only, no changes to Dataverse)
pp pipeline run --branch develop --stage plan
```

> **Note**: `pp` and `pp` are equivalent. Use whichever you prefer.

### Step 7: First deployment to DEV

```bash
# Set environment variables
export DEV_CLIENT_ID="your-client-id"
export DEV_CLIENT_SECRET="your-client-secret"

# Deploy source code to DEV
pp pipeline run --branch develop
```

---

## 3. What power-platform-agent Provides vs What Solution Repo Provides

| Aspect | power-platform-agent (tooling) | Solution repo (source code) |
|--------|-------------------------------|------------------------------|
| `framework_power/` | **Provides** (Python library) | Uses via `pip install` |
| `metadata_py/tables/` | Test/demo tables only | **YOUR actual table definitions** |
| `metadata_py/forms/` | Test/demo forms only | **YOUR actual form definitions** |
| `metadata_py/views/` | Test/demo views only | **YOUR actual view definitions** |
| `plugins/` | Test plugin (Smoke) | **YOUR actual C# plugins** |
| `webresources/` | Test web resources | **YOUR actual JS/CSS/HTML** |
| `config/pipeline.yaml` | Template | **YOUR customized copy** |
| `config/environments.yaml` | Template | **YOUR env URLs + solution names** |
| `scripts/ci/*.yml` | Template | **YOUR CI workflow** (copied) |
| `docs/references/` | Reference docs | Not needed |

---

## 4. Directory Convention (Critical)

The dynamic composer auto-discovers components based on **directory paths**. Solution repos MUST follow this structure:

| Component | Directory | Pattern | Auto-discovery rule |
|-----------|-----------|---------|---------------------|
| Tables | `metadata_py/tables/` | `*.py` | Each file exports `TABLE` |
| Option sets | `metadata_py/optionsets/` | `*.py` | Each file exports `OPTIONSET` |
| Forms | `metadata_py/forms/` | `*.py` | Each file exports `FORM` |
| Views | `metadata_py/views/` | `*.py` | Each file exports `VIEW` |
| Ribbons | `metadata_py/ribbons/` | `*.py` | Each file exports `RIBBON` |
| Roles | `metadata_py/roles/` | `*.py` | Each file exports `ROLE` |
| Plugins | `plugins/*/` | `plugin_def.py` | Each subdir with `plugin_def.py` |
| Web resources | `webresources/` | All files | Sync entire directory |

These paths are configurable in `config/pipeline.yaml` → `source_mode.discovery`, but using the defaults is recommended.

---

## 5. CI/CD Workflow for Solution Repos

### Developer workflow

```
1. Create feature branch:  git checkout -b feature/add-quote-discount
2. Write table/column:     metadata_py/tables/new_quote.py (add discount field)
3. Write form:             metadata_py/forms/new_quote__Main.py (add discount control)
4. Test locally:           pp plan new_quote --env dev
5. Push:                   git push origin feature/add-quote-discount
6. CI runs plan-only:      pp pipeline run --branch feature/add-quote-discount --stage plan
7. Create PR to develop
8. Merge → CI auto-deploys to DEV
```

### Release workflow

```
1. Create release branch:  git checkout -b release/1.2.0
2. CI auto-promotes:        export from DEV → import to UAT (unmanaged)
3. QA tests in UAT
4. If issues found:         fix in develop → re-export → re-import UAT
5. If UAT passes:           merge release/1.2.0 to main
6. Manual approval gate
7. CI promotes:             export managed from UAT → import to PROD
```

---

## 6. Multiple Solution Repos Sharing One Agent

If you have multiple solution repos (CPQ, SO, Payment, etc.):

- Each repo has its own `config/pipeline.yaml` and `config/environments.yaml`
- Each repo has its own solution name in `environments.yaml`
- Each repo deploys to the SAME Dataverse environments (dev/test/prod)
- Solutions are independent — each is exported/imported separately
- The agent tool version can be pinned per-repo via `requirements.txt`

```ini
# requirements.txt in solution-repo-A
git+https://github.com/your-org/power-platform-agent.git@v1.2.0

# requirements.txt in solution-repo-B
git+https://github.com/your-org/power-platform-agent.git@v1.3.0
```

---

## 7. Versioning the Agent Tool

### For the tooling repo (power-platform-agent)

Use git tags for releases:

```bash
# In power-platform-agent repo
git tag v1.0.0
git push origin v1.0.0
```

### For solution repos

Pin to a specific tag in `requirements.txt`:

```
# Pinned to specific version (recommended for production)
git+https://github.com/your-org/power-platform-agent.git@v1.0.0

# Track main branch (for development)
git+https://github.com/your-org/power-platform-agent.git@main
```

---

## 8. Troubleshooting

### "ModuleNotFoundError: No module named 'framework_power'"

The agent is not installed. Run:
```bash
pip install -r requirements.txt
```

### "pipeline.yaml not found"

The pipeline config is looked up at `config/pipeline.yaml` relative to the current working directory. Run commands from the solution repo root.

### "No components discovered"

Check that:
1. `metadata_py/tables/` contains `.py` files (not `.yaml`)
2. Each table file exports a `TABLE` variable
3. File names start with your publisher prefix (e.g. `new_`)

```bash
# Debug: see what the composer finds
pp pipeline compose --branch develop
```

### "pac command not found" (promote mode)

Install the pac CLI:
```bash
dotnet tool install -g Microsoft.PowerApps.CLI.Tool
```

Ensure `~/.dotnet/tools` is in your PATH.
