# ADR-003: .env File Scope Separation (Workspace vs User-Level)

## Status
Accepted

## Context

The root `.env` file mixed two distinct concerns:

1. **Dataverse credentials** (`DEV_CLIENT_ID`, `DEV_CLIENT_SECRET`, `DEV_TENANT_ID`) —
   per-project, each workspace connects to its own Dataverse environments with its own
   Azure App Registration.
2. **LLM API keys** (`ANTHROPIC_API_KEY`, `LLM_PROVIDER`) — per-user, the same person
   uses the same LLM API key across all projects.

After ADR-002 (engine-workspace separation), the root directory is engine-only and
should not contain per-project data. Leaving `.env` at the root violates this principle.

**Risk of not splitting:** If multiple workspaces exist (`ninebot-project/`, `acme-corp/`),
they would all accidentally inherit the root `.env`'s Dataverse credentials through the
parent-directory search in `load_env_file()`. This is both a correctness bug (wrong
credentials) and a security issue (credential leakage across projects).

## Decision

Split `.env` by scope:

| Scope | Location | Contents |
|-------|----------|----------|
| **Workspace-level** | `<workspace>/.env` | Dataverse credentials (`DEV_*`, `TEST_*`, `PROD_*`) |
| **User-level** | `~/.power-platform-agent/.env` | LLM API keys, cross-project settings |
| **Template** | `<engine-root>/.env.example` | Documentation template (no secrets) |

### Loading chain (priority order)

`load_env_file()` is now workspace-aware:

1. **Explicit path** — if `env_file=` is passed, load only that file
2. **Workspace `.env`** — auto-discover via `pp-workspace.yaml` upward search from CWD
3. **User-level `.env`** — `~/.power-platform-agent/.env`
4. **CWD `.env`** — backward compatibility
5. **Parent search** — walk up 3 levels from CWD (legacy fallback)

Later files do NOT override already-set variables (`override=False`), matching
python-dotenv's default semantics. This means the workspace `.env` (loaded first)
takes priority over user-level for any overlapping keys.

### `Workspace.env_file` property

Added `ws.env_file` property returning `ws.root / ".env"`, parallel to
`ws.environments_config` and `ws.pipeline_config`. The CLI's `_get_client_ws()`
uses this to explicitly load the workspace `.env` before building the client.

### MCP Server (legacy `framework/`)

Updated `framework/mcp_serve.py` to use the same workspace-aware loading order,
with legacy fallback to `project_root/.env`.

## Consequences

**Easier:**
- Multi-workspace isolation — each workspace has its own Dataverse credentials
- LLM keys configured once, shared across all workspaces
- Consistent with ADR-002's engine-workspace separation
- Clear documentation in `.env.example` about what goes where

**Harder:**
- Slightly more complex `load_env_file()` (was 15 lines, now 50 with the search chain)
- New users need to set up two locations instead of one
- Migration: existing root `.env` must be split (one-time cost)

**Backward compatibility:**
- CWD `.env` and parent search still work for legacy users
- If no workspace is found, the old behavior is preserved
- `load_env_file(explicit_path)` behavior unchanged

### Root directory does NOT need CLIENT_ID config

After this ADR, the engine root should **not** contain a `.env` file with Dataverse
credentials. The root is engine-only (per ADR-002) and has no `pp-workspace.yaml`,
so it is not a workspace.

**Testing the engine from root against a real Dataverse environment:**

Use the `--workspace` flag to point to the workspace that has the credentials:

```bash
# From engine root — uses ninebot-project's credentials + user-level LLM keys
pp list --workspace ninebot-project
pp deploy --workspace ninebot-project
```

The loading chain works as follows:
1. `_get_client_ws()` discovers the workspace via `--workspace` flag
2. `load_env_file(str(ws.env_file))` loads `ninebot-project/.env` (DEV_CLIENT_ID, etc.)
3. `get_client()` → `load_yaml_with_env()` → `load_env_file()` loads user-level `~/.power-platform-agent/.env` (ANTHROPIC_API_KEY, etc.)
4. `override=False` ensures no conflicts — workspace credentials are preserved

**Verified:** Running from engine root with `--workspace ninebot-project` loads both
workspace-level Dataverse credentials and user-level LLM keys. No root `.env` needed.

**What if someone puts a `.env` at root anyway?**
- It would be picked up by the CWD fallback (step 4 in the loading chain)
- It would NOT be loaded when running inside a workspace (because `_find_workspace_env()`
  returns early when it finds `pp-workspace.yaml`, skipping the CWD/parent search)
- It WOULD be loaded when running from root without `--workspace` — but this is the
  legacy fallback behavior, and users should use `--workspace` instead
