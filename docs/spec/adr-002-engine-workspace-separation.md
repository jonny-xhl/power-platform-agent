# ADR-002: Engine-Workspace Separation

## Status
Accepted

## Context

The power-platform-agent repository originally served a **dual purpose**:
1. The engine source code (`framework_power/`, `framework/`)
2. A reference workspace with project metadata (`metadata_py/`, `config/`, `webresources/`, `plugins/`, `sources/`)

A root-level `pp-workspace.yaml` marked the entire repo as a workspace. This created several problems:

- **Conceptual confusion**: The engine repo IS the framework, not a customer project. Mixing engine code with project metadata blurs bounded contexts.
- **Git pollution**: Project-specific metadata (Dataverse URLs, table definitions, web resources) was tracked in the engine repo's git history. This data is project-specific and should NOT be in the engine repo.
- **Misleading workspace discovery**: Running `pp` commands from the repo root accidentally resolved to the engine repo's "workspace" instead of an actual project workspace.
- **Poor test boundary**: Tests had implicit dependencies on root-level metadata directories that were neither test fixtures nor engine code.

The workspace feature (`pp workspace init`) was implemented but could not be properly tested because the repo itself was already (incorrectly) a workspace.

## Decision

**Separate engine source from workspace data.** The repo root is purely engine code. Workspace data lives in a subdirectory initialized via `pp workspace init`.

### Changes Made

1. **Created `ninebot-project/` workspace** via `pp workspace init --path ./ninebot-project --name ninebot-project`
   - Scaffolded by the CLI itself (tests the init flow end-to-end)
   - Contains: `pp-workspace.yaml`, `metadata_py/`, `config/`, `webresources/`, `plugins/`, `sources/`, `.gitignore`

2. **Migrated all workspace data** from root to `ninebot-project/`:
   - `metadata_py/` (table, form, view, solution definitions)
   - `config/` (environments.yaml, pipeline.yaml, publishers.yaml, etc.)
   - `webresources/` (JS, CSS, HTML, images)
   - `plugins/` (C# plugin projects)
   - `sources/` (feature specs, PRDs, templates)

3. **Removed root `pp-workspace.yaml`** — the engine repo is no longer a workspace

4. **Updated root `.gitignore`** — `ninebot-project/` and all root-level workspace data directories (`metadata_py/`, `metadata/`, `config/`, `webresources/`, `plugins/`, `sources/`) are now gitignored

5. **Untracked 80 files** from git index via `git rm --cached` (metadata, config, webresources, plugins, sources — all workspace data)

6. **Kept `metadata/_schema/`** tracked at root — these are engine-level schema definitions (validation schemas for YAML metadata format), not workspace data

## Consequences

### What becomes easier
- **Clear bounded context**: Engine code at root, project data in workspace subdirectories. Each project gets its own `pp workspace init`.
- **Git hygiene**: Engine repo only tracks engine code. Workspace data is excluded from the engine repo's git.
- **Multi-project support**: Multiple workspaces can coexist (`ninebot-project/`, `acme-project/`, etc.) without polluting the engine repo.
- **Workspace init is tested**: The `pp workspace init` flow was exercised end-to-end, proving the CLI scaffolding works correctly.
- **Independent workspace lifecycle**: Each workspace can have its own git repo, CI/CD pipeline, and versioning strategy.

### What becomes harder
- **Two-step workflow**: Developers must `cd ninebot-project/` before running `pp` commands (or use `--workspace ninebot-project/`).
- **Root-level CWD fallback**: The CLI has a backward-compatible CWD fallback that still finds root-level `metadata_py/` files. The root-level data still exists on disk (untracked) and should eventually be cleaned up.
- **Documentation drift**: Existing skills/docs (`.claude/`, `CLAUDE.md`) reference root-level paths. These need updating to reflect the workspace-based structure (follow-up task).

### Trade-offs
| Aspect | Before | After |
|--------|--------|-------|
| Repo identity | Engine + workspace (dual) | Engine only |
| Git tracking | 80 workspace files tracked | 0 (all untracked) |
| Workspace discovery | Root-level (incorrect) | Per-project subdirectory |
| `pp` from root | Works (accidentally) | Falls back to CWD (backward compat) |
| `pp` from workspace | N/A | Works correctly via discovery |

## Validation

- `pp workspace info` from `ninebot-project/` — resolves all paths correctly
- `pp workspace validate` — passes validation
- `pp list` — discovers all 9 table definitions
- `pp dictionary` — generates data dictionary for all tables
- `framework_power` unit tests — 411/411 pass (unaffected by migration)
