# PAC CLI Integration Guide for power-platform-agent

> **Purpose**: Map PAC CLI capabilities to existing framework_power features and define integration strategy
> **Last Updated**: 2026-07-23
> **Prerequisites**: Read `pac-cli-overview.md`, `pac-solution-reference.md`, and `pac-cli-cheatsheet.md`

---

## 1. Current Architecture Overview

```
power-platform-agent/
├── framework_power/          # Python-first CLI (recommended path)
│   ├── cli.py                # CLI entry point (click + rich)
│   ├── deployer.py            # Idempotent table deploy/plan
│   ├── reverse.py             # Environment → Python reverse
│   ├── codegen.py             # Table → Python source generation
│   ├── lint.py                # Offline convention checks
│   ├── workflow.py            # Phase 9: cross-phase orchestration
│   ├── solution_deployer.py   # Solution deploy/reverse
│   ├── solution_zip.py        # Solution zip operations
│   ├── solution_codegen.py    # Solution → Python codegen
│   ├── plugin_sync.py         # Plugin (NuGet) deploy
│   ├── webresource_sync.py    # Web resource sync
│   ├── form_sync.py           # Form deploy/sync
│   ├── view_sync.py           # View deploy/sync
│   ├── ribbon_sync.py         # Ribbon deploy/sync
│   ├── role_deployer.py       # Security role deploy
│   ├── role_reverse.py        # Security role reverse
│   ├── optionset_sync.py      # Global optionset deploy
│   └── components/            # Solution component registry
│       ├── form.py
│       ├── view.py
│       ├── plugin.py
│       ├── optionset.py
│       ├── webresource.py
│       └── models.py          # Publisher, Solution models
├── metadata_py/              # Python metadata definitions
│   ├── tables/               # Per-table .py (exports TABLE)
│   ├── forms/                # Structured form definitions
│   ├── views/                # Structured view definitions
│   ├── solutions/            # Solution manifests
│   └── project.py            # Workflow orchestration manifest
├── framework/                # MCP Server (Legacy path)
│   ├── mcp_serve.py          # MCP server entry
│   ├── agents/               # Agent routing
│   └── utils/                # DataverseClient, naming, YAML parser
├── metadata/                 # YAML metadata (Legacy path)
├── config/                   # Configuration
├── plugins/                  # .NET plugin source
└── webresources/             # Web resource files (JS/CSS/HTML)
```

### Current 9 Phases (framework_power)

| # | Phase | Python Module | Key Functions |
|---|-------|---------------|---------------|
| 1 | Table Management | `deployer.py`, `reverse.py`, `codegen.py` | `deploy_table`, `plan_table`, `reverse_table` |
| 2 | Solution | `solution_deployer.py`, `solution_zip.py` | `deploy_solution`, `reverse_solution` |
| 3 | Security Roles | `role_deployer.py`, `role_reverse.py` | `deploy_role`, `plan_role` |
| 4 | Web Resources | `webresource_sync.py` | `sync_webresources`, `plan_webresources` |
| 5 | Forms | `form_sync.py`, `form_xml.py` | `sync_forms`, `plan_forms` |
| 6 | Views | `view_sync.py`, `view_xml.py` | `sync_views`, `plan_views` |
| 7 | Ribbon | `ribbon_sync.py`, `ribbon_xml.py` | `sync_ribbons`, `plan_ribbons` |
| 8 | Plugins | `plugin_sync.py` | `deploy_plugin` |
| 9 | Workflow Orchestration | `workflow.py` | `deploy_workflow`, `plan_workflow` |

---

## 2. Capability Mapping: PAC CLI vs framework_power

### 2.1 Solution Operations

| Capability | PAC CLI | framework_power | Gap / Opportunity |
|-----------|---------|-----------------|-------------------|
| Initialize solution | `pac solution init` | `solution_codegen.py` (codegen) | PAC creates .cdsproj; project uses Python models |
| Export solution | `pac solution export` | `solution_reverse.py` | PAC handles managed/unmanaged zip; project reverses to Python |
| Import solution | `pac solution import` | `solution_deployer.py` | PAC handles settings files, async; project deploys components individually |
| Pack/unpack | `pac solution pack/unpack` | `solution_zip.py` | PAC supports YAML format (v2.4.1+); project uses Python models directly |
| Clone | `pac solution clone` | `reverse.py` (reverse_table) | PAC creates .cdsproj + references; project creates .py files |
| Sync | `pac solution sync` | `workflow.py` (plan_workflow) | PAC syncs entire solution; project orchestrates per-phase |
| Version | `pac solution version` | `solution_deployer.py` (_validate_version) | PAC supports GitTags/FileTracking strategies |
| Check | `pac solution check` | (none) | **NEW CAPABILITY**: Power Apps Checker integration |
| Upgrade | `pac solution upgrade` | (none) | **NEW CAPABILITY**: Solution upgrade workflow |
| Publish | `pac solution publish` | `workflow.py` (PublishAllXml) | Equivalent, but PAC supports async |
| Delete | `pac solution delete` | (none) | **NEW CAPABILITY**: Solution deletion |
| Add license | `pac solution add-license` | (none) | **NEW CAPABILITY**: ISV license management |
| Create settings | `pac solution create-settings` | (none) | **NEW CAPABILITY**: Deployment settings generation |
| Add component | `pac solution add-solution-component` | `components/*.py` (ensure_solution_component) | PAC adds by type ID; project adds per component type |

### 2.2 Authentication

| Capability | PAC CLI | framework_power | Gap / Opportunity |
|-----------|---------|-----------------|-------------------|
| Auth profiles | `pac auth create/list/select` | `framework/utils/DataverseClient` (env vars) | PAC provides multi-profile management; project uses env vars |
| Multi-tenant | Multiple auth profiles | Multiple env configs | PAC is more ergonomic for switching |
| Cloud targeting | `--cloud` parameter | `config/environments.yaml` | PAC supports sovereign clouds explicitly |
| Non-interactive | `--deviceCode` | Environment variables | PAC better for CI/CD Codespaces |

### 2.3 Other PAC CLI Command Groups (No Current Equivalent)

| PAC CLI Group | Description | Integration Value |
|---------------|-------------|-------------------|
| `pac admin` | Environment lifecycle (create/delete/reset environments) | High - enables full environment provisioning |
| `pac data` | Data import/export (Windows only) | Medium - useful for seed data, test data |
| `pac code` | Early-bound type generation from Dataverse metadata | Medium - complements reverse.py |
| `pac canvas` | Canvas app source export/import | Medium - ALM for canvas apps |
| `pac connector` | Custom connector management | Low - if project doesn't use custom connectors |
| `pac package` | Package deploy (Windows only) | Low - package deployer for ISV scenarios |
| `pac paportal` | Power Pages operations | Low - if project doesn't use Power Pages |
| `pac pcfx` | PCF component operations | Medium - if project uses code components |
| `pac test` | Test engine | Medium - automated testing for Dataverse |
| `pac catalog` | Power Platform catalog | Low - AppSource publishing scenarios |

---

## 3. Integration Strategy

### Phase 1: Solution Pack/Unpack Wrapper (Low Risk)

**Goal**: Wrap PAC CLI's pack/unpack as an alternative solution serialization path.

**Rationale**: The project currently uses `solution_zip.py` for solution zip operations. PAC CLI's `pack/unpack` provides:
- YAML source control format support (v2.4.1+)
- Native Git integration compatibility
- Managed/unmanaged dual-pack
- SolutionPackager equivalence

**Implementation**:

```python
# framework_power/pac_wrapper.py (new module)

import subprocess
import shutil
from pathlib import Path
from typing import Optional

class PacCliWrapper:
    """Thin wrapper around pac CLI solution commands."""

    def __init__(self, pac_path: str = "pac"):
        self.pac_path = pac_path
        self._ensure_pac_available()

    def _ensure_pac_available(self) -> None:
        if not shutil.which(self.pac_path):
            raise RuntimeError(
                f"PAC CLI not found at '{self.pac_path}'. "
                "Install via: dotnet tool install -g Microsoft.PowerApps.CLI"
            )

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        result = subprocess.run(
            [self.pac_path, *args],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"pac {' '.join(args)} failed:\n{result.stderr}"
            )
        return result

    # --- Solution Pack/Unpack ---

    def pack(
        self,
        source_folder: str,
        output_zip: str,
        packagetype: str = "Both",
        localize: bool = False,
    ) -> None:
        """Pack solution folder to zip using SolutionPackager."""
        args = [
            "solution", "pack",
            "--folder", source_folder,
            "--zipfile", output_zip,
            "--packagetype", packagetype,
        ]
        if localize:
            args.append("--localize")
        self._run(*args)

    def unpack(
        self,
        source_zip: str,
        output_folder: str,
        packagetype: str = "Both",
        localize: bool = False,
    ) -> None:
        """Unpack solution zip to folder using SolutionPackager."""
        args = [
            "solution", "unpack",
            "--zipfile", source_zip,
            "--folder", output_folder,
            "--packagetype", packagetype,
        ]
        if localize:
            args.append("--localize")
        self._run(*args)

    # --- Solution Import/Export ---

    def export(
        self,
        solution_name: str,
        output_path: str,
        managed: bool = False,
        environment: Optional[str] = None,
        include_settings: Optional[list[str]] = None,
    ) -> None:
        """Export solution from Dataverse."""
        args = [
            "solution", "export",
            "--name", solution_name,
            "--path", output_path,
            "--managed", str(managed).lower(),
        ]
        if environment:
            args.extend(["--environment", environment])
        if include_settings:
            args.extend(["--include", ",".join(include_settings)])
        self._run(*args)

    def import_solution(
        self,
        zip_path: str,
        environment: Optional[str] = None,
        publish_changes: bool = False,
        force_overwrite: bool = False,
        activate_plugins: bool = False,
        async_import: bool = False,
    ) -> None:
        """Import solution to Dataverse."""
        args = ["solution", "import", "--path", zip_path]
        if environment:
            args.extend(["--environment", environment])
        if publish_changes:
            args.append("--publish-changes")
        if force_overwrite:
            args.append("--force-overwrite")
        if activate_plugins:
            args.append("--activate-plugins")
        if async_import:
            args.append("--async")
        self._run(*args)

    # --- Solution Check (NEW CAPABILITY) ---

    def check(
        self,
        solution_path: str,
        output_dir: str,
        geo: str = "UnitedStates",
        environment: Optional[str] = None,
    ) -> str:
        """Run Power Apps Checker on solution."""
        args = [
            "solution", "check",
            "--path", solution_path,
            "--outputDirectory", output_dir,
            "--geo", geo,
        ]
        if environment:
            args.extend(["--environment", environment])
        result = self._run(*args)
        return result.stdout

    # --- Auth (Optional: replace env-var auth) ---

    def auth_create(
        self,
        environment: str,
        device_code: bool = False,
        cloud: str = "Public",
    ) -> None:
        """Create auth profile."""
        args = ["auth", "create", "--environment", environment, "--cloud", cloud]
        if device_code:
            args.append("--deviceCode")
        self._run(*args)

    def auth_list(self) -> str:
        """List auth profiles."""
        return self._run("auth", "list").stdout

    def auth_select(self, index: int) -> None:
        """Select auth profile by index."""
        self._run("auth", "select", "--index", str(index))
```

### Phase 2: Solution Checker Integration (New Feature)

**Goal**: Add `framework_power check` command that runs Power Apps Checker.

```python
# In cli.py, add new command:

@click.command()
@click.argument("solution_name")
@click.option("--env", default="dev", help="Target environment")
@click.option("--geo", default="UnitedStates", help="Checker geo")
@click.option("--output-dir", default="check-results", help="Output directory")
def check(solution_name, env, geo, output_dir):
    """Run Power Apps Checker on a solution."""
    pac = PacCliWrapper()

    # Export solution to temp zip
    temp_zip = f"/tmp/{solution_name}.zip"
    pac.export(solution_name, temp_zip, managed=False, environment=env_url)

    # Run checker
    results = pac.check(temp_zip, output_dir, geo=geo, environment=env_url)
    click.echo(results)

    # Parse and display results
    # ...
```

### Phase 3: Auth Profile Integration (Auth Modernization)

**Goal**: Allow `pac auth` profiles as an alternative to environment variables.

```python
# In framework_power/client/ (modify auth flow)

class PacAuthProvider:
    """Use pac auth profiles for Dataverse authentication."""

    def __init__(self, profile_index: Optional[int] = None):
        self.pac = PacCliWrapper()
        self.profile_index = profile_index

    def get_credentials(self) -> dict:
        """Extract credentials from active pac auth profile."""
        if self.profile_index:
            self.pac.auth_select(self.profile_index)
        # Parse pac auth list output to get URL, user, etc.
        profiles = self.pac.auth_list()
        active = self._parse_active_profile(profiles)
        return {
            "url": active["url"],
            "user": active["user"],
            # PAC stores tokens internally; use pac org commands
            # or extract from ~/.powerplatform-cli/ profiles
        }
```

### Phase 4: Solution Version Strategy (CI/CD Enhancement)

**Goal**: Integrate PAC versioning strategies into the workflow.

```python
# In workflow.py or cli.py:

@click.command()
@click.option("--strategy", type=click.Choice(["None", "GitTags", "FileTracking", "Solution"]),
              default="Solution")
@click.option("--build", type=int, help="Build version")
@click.option("--revision", type=int, help="Revision version")
def version(strategy, build, revision):
    """Update solution version using PAC strategies."""
    pac = PacCliWrapper()

    if build is not None:
        pac._run("solution", "version", "--buildversion", str(build))
    if revision is not None:
        pac._run("solution", "version", "--revisionversion", str(revision))
    if strategy != "None":
        pac._run("solution", "version", "--strategy", strategy)
```

---

## 4. Hybrid Architecture Decision Matrix

| Scenario | Use framework_power (Python) | Use PAC CLI | Use Both |
|----------|---------------------------|-------------|----------|
| Define table schema in code | Yes (type-safe Python models) | No | - |
| Deploy individual components | Yes (idempotent deploy) | No | - |
| Pack/unpack solution zip | Possible (`solution_zip.py`) | Yes (YAML format support) | Both: Python for define, PAC for serialize |
| Run solution checker | No | Yes | - |
| CI/CD pipeline auth | Env vars (works) | `pac auth` (better ergonomics) | Both: fallback from PAC to env vars |
| Environment lifecycle | No | Yes (`pac admin`) | - |
| Reverse engineer existing solution | Yes (to Python .py) | Yes (to XML/YAML) | Both: PAC for raw, Python for type-safe |
| Canvas app source control | No | Yes (`pac canvas`) | - |
| Data import/export | No | Yes (`pac data`, Windows only) | - |
| Plugin NuGet deploy | Yes (`plugin_sync.py`) | Possible (`pac plugin`) | Prefer Python (more control) |
| Solution upgrade | No | Yes (`pac solution upgrade`) | - |

---

## 5. Recommended File Structure After Integration

```
framework_power/
├── pac_wrapper.py          # NEW: PAC CLI subprocess wrapper
├── pac_checker.py          # NEW: Solution checker integration
├── pac_auth.py             # NEW: PAC auth profile integration
├── pac_version.py          # NEW: PAC version strategy integration
├── cli.py                  # MODIFIED: Add `check`, `version`, `auth` commands
├── deployer.py             # UNCHANGED
├── reverse.py              # UNCHANGED (PAC reverse is complementary)
├── solution_zip.py         # MAY DEPRECATE: Replace with PAC pack/unpack
├── workflow.py             # MODIFIED: Add check phase to workflow
└── ...
```

---

## 6. PAC CLI Installation Requirements

### For Development Machines

```bash
# Option 1: .NET Tool (cross-platform, recommended)
dotnet tool install -g Microsoft.PowerApps.CLI

# Option 2: VS Code Extension (Windows/Linux/macOS)
# Install from VS Code marketplace: "Power Platform Tools"

# Option 3: Windows MSI (Windows only, full features including pac data)
# Download from: https://aka.ms/PowerAppsCLI
```

### For CI/CD Pipelines

```yaml
# GitHub Actions example
- name: Install PAC CLI
  run: dotnet tool install -g Microsoft.PowerApps.CLI

- name: Add PAC to PATH
  run: echo "$HOME/.dotnet/tools" >> $GITHUB_PATH

# Azure DevOps: Use built-in PowerPlatformTool task
- task: PowerPlatformToolInstaller@2
  inputs:
    DefaultVersion: true
```

### Verification

```bash
pac --version
# Expected: Microsoft PowerPlatform CLI / Version: 1.30.x+
```

---

## 7. Dependency & Compatibility Notes

| Concern | Detail |
|---------|--------|
| **PAC CLI version** | YAML source control format requires **2.4.1+** |
| **OS compatibility** | `pac data`, `pac package deploy/show` are **Windows only** |
| **Auth coexistence** | PAC auth profiles and env-var auth can coexist; PAC profiles take precedence when active |
| **Solution format** | PAC YAML format vs framework_power Python models — different paradigms, not interchangeable |
| **Plugin deployment** | framework_power uses NuGet PluginPackage API directly; PAC uses `pac plugin` — both work, prefer Python for control |
| **Non-destructive principle** | framework_power is non-destructive (create/update only, no delete); PAC `delete` commands are destructive — use with caution |

---

## 8. Migration Considerations

### What NOT to Replace

1. **`deployer.py` (table deploy)** — Python type-safe models are superior to PAC's XML/YAML for table definitions
2. **`lint.py`** — Custom convention checks specific to this project
3. **`codegen.py`** — Python source generation is project-specific
4. **`workflow.py` orchestration** — Project manifest drives the chain; PAC doesn't orchestrate phases

### What to Augment with PAC

1. **Solution checker** — `pac solution check` (no current equivalent)
2. **Solution upgrade** — `pac solution upgrade` (no current equivalent)
3. **Solution version strategies** — `pac solution version --strategy gittags`
4. **Auth profile management** — `pac auth` (better than env vars for multi-tenant)
5. **Environment lifecycle** — `pac admin` (no current equivalent)
6. **Canvas app ALM** — `pac canvas` (no current equivalent)

### What to Consider Replacing

1. **`solution_zip.py`** — Could be replaced by `pac solution pack/unpack` (better format support)
2. **MSAL auth in `DataverseClient`** — Could delegate to `pac auth` profiles
3. **`solution_reverse.py`** — Could use `pac solution sync` for raw extraction, then convert to Python

---

## 9. Sample Integration: Adding Solution Check to Workflow

```python
# Example: Extending workflow.py to include a check phase

from .pac_wrapper import PacCliWrapper

def check_workflow(
    project: Project,
    env_url: str,
    geo: str = "UnitedStates",
) -> list[Issue]:
    """
    Phase 9.5: Run Power Apps Checker on the solution.

    Executes after deploy, before final publish.
    """
    pac = PacCliWrapper()
    issues: list[Issue] = []

    for solution in project.solutions:
        try:
            # Export solution to temp zip
            temp_zip = f"/tmp/{solution.unique_name}_check.zip"
            pac.export(solution.unique_name, temp_zip, managed=False, environment=env_url)

            # Run checker
            output_dir = f"check-results/{solution.unique_name}"
            pac.check(temp_zip, output_dir, geo=geo, environment=env_url)

            # Parse results (SARIF format)
            issues.extend(_parse_sarif_results(output_dir))

        except RuntimeError as e:
            issues.append(Issue(
                level=ERROR,
                message=f"Solution check failed for {solution.unique_name}: {e}"
            ))

    return issues
```

---

## 10. Future Exploration: PAC CLI Command Groups to Evaluate

| Command Group | Priority | Use Case in This Project |
|--------------|----------|--------------------------|
| `pac admin` | High | Environment provisioning in CI/CD |
| `pac code` | Medium | Early-bound type generation for plugin development |
| `pac test` | Medium | Automated testing framework for Dataverse solutions |
| `pac data` | Medium | Seed data deployment (Windows only) |
| `pac canvas` | Low | Canvas app source control (if project extends to canvas apps) |
| `pac connector` | Low | Custom connector management (if needed) |
| `pac pcfx` | Low | PCF component development (if project uses code components) |
