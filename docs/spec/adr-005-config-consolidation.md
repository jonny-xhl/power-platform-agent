# ADR-005: Workspace Config Consolidation — 9→5 Files

## Status
Accepted (2026-08-04)

## Context

The workspace `config/` directory contained 9 YAML files, many of which were:

1. **Dead code** — `settings.yaml`, `extensions.yaml`, `documentation_rules.yaml` had zero engine code references (framework_power/ or framework/). They described aspirational features (extension system, auto-documentation) that were never implemented.

2. **Overlapping** — `naming_rules.yaml` and `publishers.yaml` both defined publisher prefix and naming conventions. `NamingConverter` had to load two separate files and reconcile them.

3. **Redundant** — `hermes_profile.yaml` duplicated Dataverse environment URLs already in `environments.yaml`.

This added maintenance burden: every config file is a place where a contributor might put something and expect it to work. Dead configs are "configuration debt."

## Decision

**Reduce workspace config from 9 files to 5 files:**

### Removed (4 files)

| File | Reason |
|------|--------|
| `settings.yaml` | Zero code references. Overlapped with `environments.yaml` (timeout/retry) and `hermes_profile.yaml` (logging). |
| `extensions.yaml` | Zero code references. Described an extension/hook/middleware system that was never built. |
| `documentation_rules.yaml` | Zero code references. Auto-doc monitoring rules with no implementation. |
| `naming_rules.yaml` | **Consolidated into `publishers.yaml`** under a new `naming:` top-level key. |

### Retained (5 files)

| File | Status |
|------|--------|
| `environments.yaml` | Active — auth, DataverseClient, pipeline, workspace.validate() |
| `publishers.yaml` | Active — **now includes `naming:` section** (schema_name style, standard_entities, webresource rules, validation) |
| `pipeline.yaml` | Active — CI/CD branch→env mapping, source/promote mode |
| `environment_settings.yaml` | Active — post-import connection refs and env variables |
| `hermes_profile.yaml` | Retained for legacy `framework/` compatibility. Will be removed when `framework/` is fully retired. |

### Code Changes

| Component | Change |
|-----------|--------|
| `framework/utils/naming_converter.py` | Simplified: single-file loading from `config/publishers.yaml`. Removed `_publishers_config` and double-file loading. `prefix` always reads from `publishers` section. |
| `framework/utils/env_config.py` | Replaced `naming_rules.yaml` with `publishers.yaml` in config file lists. |
| `framework_power/workspace.py` | Removed `naming_rules_config` property. |
| `framework_power/cli.py` | Removed `naming_rules.yaml` scaffolding in `workspace init`. |
| `framework_power/templates/` | Removed `naming_rules.yaml` template. Updated `publishers.yaml` template with `naming` section. |

## Consequences

### Easier
- **Onboarding**: 5 configs to understand instead of 9. One file (`publishers.yaml`) for all publishing + naming concerns.
- **Naming configuration**: Single source of truth. No more reconciling `naming_rules.prefix` vs `publishers.current.prefix`.
- **Maintenance**: Dead config files can't mislead contributors or accumulate garbage.

### Harder
- `hermes_profile.yaml` still duplicates environment URLs from `environments.yaml`. This is acknowledged tech debt — will be resolved when `framework/` is retired.
- The `naming:` section in `publishers.yaml` adds ~90 lines to the file, making it somewhat large. But a single 140-line file is better than two files with overlapping concerns.

### Risk
- **Low risk**: `naming_rules.yaml` was only read by `framework/` (legacy) code. The engine (`framework_power/`) never read it directly (publisher prefix was already read from `publishers.yaml`). The migration is transparent to engine operation.

## Supersedes
- Partially supersedes the config structure described in ADR-002 (engine-workspace separation).
