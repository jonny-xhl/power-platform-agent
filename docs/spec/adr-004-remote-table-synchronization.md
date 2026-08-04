# ADR-004: Remote Table Synchronization Commands

## Status
Accepted

## Context

After ADR-002 (engine-workspace separation), the engine had two table-listing modes: (1) local
`metadata_py/` discovery via `pp list`, and (2) single-table reverse export via
`pp reverse <name>` from Dataverse.  There was **no way to list or batch-export all tables
from a remote Dataverse environment** through the CLI.

This gap was exposed when generating data dictionaries: the user's environment had 157 custom
tables but local `metadata_py/` only defined 6.  The only workaround was a manual Python script
calling the Dataverse API directly.

Additionally, bulk export of 157 tables takes significant time — each `reverse_table()` call
makes 3 API round-trips (entity metadata, attributes, relationships).  We needed to decide
whether parallelization was worth the added complexity.

### Constraints
- Single-team project — no dedicated scaling infrastructure
- Dataverse Web API with OAuth2 MSAL authentication
- Target: 157+ custom tables in a typical environment
- Output: Python definition files or Markdown data dictionaries

## Decision

### 1. Two new CLI capabilities

**`pp list --remote`**
```bash
pp list --remote                     # all custom tables
pp list --remote --prefix "new_"     # filter by prefix
```

Adds `--remote` flag to the existing `list` command.  When present, queries
`EntityDefinitions` from Dataverse instead of scanning `metadata_py/`.  Prefix filtering
is done client-side because Dataverse `startswith()` is not universally supported on
EntityDefinitions endpoint.

**`pp reverse --all`**
```bash
pp reverse --all --dictionary                      # sequential
pp reverse --all --dictionary --parallel auto      # 8 workers
pp reverse --all --dictionary --parallel 4         # 4 workers
pp reverse --all --include "account,contact,systemuser"
```

Adds `--all` flag to the existing `reverse` command.  When present:
1. Queries `list_entities(prefix=<publisher_prefix>_)` to enumerate all custom tables
2. Exports each table via `reverse_table()`
3. Supports `--include` for standard tables (account, contact, etc.)
4. Supports `--parallel N` for concurrent export

### 2. Parallel Export with ThreadPoolExecutor

**Chosen approach: `concurrent.futures.ThreadPoolExecutor`**

Each worker thread:
1. Creates its own `DataverseClient` instance (new `requests.Session` per thread)
2. Shares the pre-authenticated `access_token` (avoids re-authentication)
3. Calls `reverse_table()` independently

**Why not asyncio?** The entire `DataverseClient` is built on `requests` (synchronous).
Rewriting for `aiohttp` would be a full client rewrite — unjustified for a CLI tool.

**Why threads instead of processes?** The bottleneck is I/O (Dataverse API latency), not CPU.
Threads are lighter, share the token, and have no serialization overhead.

### 3. Concurrency Defaults
- **Default: 1 (sequential)** — safe, predictable, no Dataverse throttle risk
- **`--parallel auto`** — `min(cpu_count, 8)` = typically 4-8 workers
- **User controls parallelism** — can tune up/down based on their environment's API limits

## Performance Data

Measured on 20 `new_` tables against a Dataverse DEV environment:

| Mode | Time | Per-table |
|------|------|-----------|
| Sequential | 16.5s | 0.8s |
| Parallel (4 workers) | 8.6s | 0.4s |
| **Speedup** | **1.9x** | |

Projected for full 157-table environment:
- Sequential: ~2 minutes
- Parallel (4): ~1 minute
- Parallel (8): ~30-40 seconds

## Trade-offs

### What we gain
- **Direct environment-to-docs pipeline** — no need for intermediate Python scripts
- **Consistent with existing CLI** — `--remote` extends `list`, `--all` extends `reverse`
- **Graceful degradation** — sequential default works everywhere; parallel is opt-in
- **Worker-per-thread client isolation** — no shared mutable state between workers

### What we give up
- **Output ordering** — parallel mode produces non-deterministic progress order
  (can be fixed with post-hoc sorting if needed)
- **No connection pooling across workers** — each thread gets its own Session
  (negligible for this scale; 8 sessions × connection pool)
- **Token shared across threads** — if one worker's token expires mid-batch, all workers fail
  (unlikely within a 1-2 minute batch window, and MSAL tokens last 60+ minutes)
- **No resume-on-failure** — if export fails at table 100/157, you restart from scratch
  (acceptable — full export takes 1-2 minutes)

## Alternatives Considered

### Option A: No parallelization (always sequential)
Rejected — 2 minutes for 157 tables is borderline painful for an interactive CLI.
Users would naturally ask for parallelization.

### Option B: asyncio + aiohttp full rewrite
Rejected — disproportionate effort for a CLI tool.  The client layer, retry logic,
and all callers would need rewriting.  Thread pools give 80% of the benefit for 5%
of the effort.

### Option C: `multiprocessing.Pool`
Rejected — IPC overhead for table objects is unnecessary when the bottleneck is I/O,
not CPU.  Also complicates token sharing (would need env var or file-based token sharing).

## Migration / Backward Compatibility
- `pp list` without `--remote` — unchanged (local discovery)
- `pp reverse <name>` without `--all` — unchanged (single table)
- All new flags are optional and default to existing behavior
- No breaking changes to existing workflows

## New DataverseClient Method

```python
def list_entities(self, prefix=None, include_system=False) -> list[dict]:
    """List entities with optional client-side prefix filter."""
```

Added to `framework_power/client/dataverse_client.py` as a general-purpose utility.
Paginated (follows `@odata.nextLink`), supports all entities or custom-only.
