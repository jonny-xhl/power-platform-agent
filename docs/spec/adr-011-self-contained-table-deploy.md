# ADR-011: Self-Contained Table Deploy — Auto-Sync Referenced Global OptionSets

## Status
Accepted

## Context

ADR-009 established the optionset reference contract: a Picklist `Column` with
`optionset_name` serializes as `OptionSet.IsGlobal=true + Name` — a **reference**,
not a copy. That fixed the data-dictionary duplication problem, but it left a
deployment gap:

> A table definition that references a global optionset is **not self-contained**.
> Deploying it to a fresh environment fails when the referenced optionset does not
> exist there (attribute create rejects the unknown global OptionSet name).

Concretely, `new_salestarget.new_BusinessGroupId` references `new_salesgroup`
(6 options, 100000001-100000006). The optionset exists online in DEV, but had **no
local authored definition** (`metadata_py/optionsets/` was empty). The engine had
`optionset_sync.py` + `components/optionset.py` (create-only global optionset sync,
Phase 9) — but nothing invoked them from the table-deploy path, and there was no
CLI surface to manage optionsets standalone.

Two options were considered:

| Option | Mechanism | Trade-off |
|--------|-----------|-----------|
| A. Fail-closed | Pre-check every reference; abort deploy when unresolvable | Safe, but blocks DEV iteration on tables whose optionsets were hand-created in the maker portal (common in this org) |
| B. Dependency-first sync (chosen) | Load local definitions, sync them first; degrade to a read-only online check + warning when no local definition exists | Self-contained when authored, non-blocking otherwise; the `optionsets_missing` key surfaces the fresh-env risk without aborting |

## Decision

1. **Local authoring**: Global optionsets referenced by tables are modeled in
   `metadata_py/optionsets/<schema_name>.py`, exporting `OPTIONSET: GlobalOptionSet`
   (same convention as tables). `new_salesgroup` is now authored locally with all 6
   bilingual options. UI colors are intentionally not modeled (not part of the
   semantic contract).

2. **Dependency-first deploy**: `deploy_table(optionsets_dir=…)` collects
   `_referenced_global_optionsets(table)` (Picklist columns with `optionset_name`,
   order-preserving, deduplicated), loads matching local definitions, and syncs them
   via the existing Phase-9 flow (create-only, idempotent, `manual_update_required`
   on drift) **before** entity/attribute creation. When `solution=` is given, each
   synced optionset is added to the same solution (code 9). Results are reported
   under `result["optionsets"]` / `optionsets_added` / `optionsets_missing`.

3. **Degrade, don't block**: with no local definition, `ensure_referenced_optionsets`
   performs a read-only online existence check (guarded with `getattr` for
   minimal fake clients) and records a `missing` entry when the name is absent
   online too. The deploy continues — the warning, not an abort, is the contract.

4. **Plan parity**: `plan_table(optionsets_dir=…)` mirrors the deploy path
   read-only (`would_create` / `would_skip` / `manual_update_required` +
   `optionsets_missing`).

5. **Standalone CLI**: `pp optionset list | plan | deploy [--name] [--solution]`
   makes `optionset_sync.py` directly usable (it was previously library-only dead
   code reachable only through the component registry). Global `--optionsets-dir`
   flag added, workspace-resolved via `_resolve_dir` like the other metadata dirs.

## Consequences

### What becomes easier
- **Fresh-environment bootstrap**: `pp deploy <table> --solution X` now carries its
  optionset dependencies; no silent ordering assumption.
- **Solution completeness**: optionsets join the same solution as the referencing
  table (code 9), so solution export/import covers them.
- **Optionset lifecycle**: `pp optionset deploy` gives create-only sync without a
  table in scope.
- **Drift detection**: an authored optionset whose options differ from online
  reports `manual_update_required` instead of being silently ignored.

### What becomes harder
- **Option updates remain manual**: global optionset options cannot be PATCHed
  (platform constraint); value adds/renames still require `InsertOptionValue` /
  `UpdateOptionValue` or the maker portal. The authored file documents intent;
  the engine only detects drift.
- **One more deploy result key**: consumers parsing deploy JSON see three new keys
  (`optionsets`, `optionsets_added`, `optionsets_missing`). They are additive and
  absent-as-empty-list for tables without references.

### Trade-off
We accept an extra read-only online check per referenced optionset (one GET each,
only when no local definition exists) in exchange for never blocking a deploy on a
documentation-shaped gap. Fail-closed semantics can be layered later by promoting
`optionsets_missing` to an error in the pipeline verifier — deliberately not done
now (reversibility).

## Files Changed

- `ninebot-project/metadata_py/optionsets/new_salesgroup.py` — new authored definition (6 bilingual options)
- `framework_power/deployer.py` — `_referenced_global_optionsets()`,
  `ensure_referenced_optionsets()`, `deploy_table(optionsets_dir=…)`,
  `plan_table(optionsets_dir=…)`
- `framework_power/optionset_sync.py` — `discover_optionsets()`
- `framework_power/cli.py` — `optionsets_dir` wiring in `plan`/`deploy`/`deploy-all`;
  `pp optionset list|plan|deploy` command group; `DEFAULT_OPTIONSETS_DIR`;
  global `--optionsets-dir` flag
- `test/unit/test_framework_power/test_deployer.py` — 6 new tests (collector,
  created/exists/missing/no-ref paths, deploy-with-solution ordering)
- `docs/guides/metadata-deploy.md` — deployment-semantics table updated

## Verification (2026-08-18, dev)

- `pp plan new_salestarget` → `optionsets: [{new_salesgroup: would_skip}]`, `optionsets_missing: []`
- `pp deploy new_salestarget --solution new_entity930 --solution-clean` →
  optionset `exists` (idempotent), **added to `new_entity930` (code 9)**, entity
  `updated (method: put)`, attributes/relationships all `skipped`
- `pp optionset plan/deploy new_salesgroup --solution new_entity930` → `would_skip` / `exists` + `added`
- Unit tests: framework_power subset 467 passed / 5 failed (pre-existing
  `new_projectbudget` fixture issue); full suite delta from my changes: +6 passed, 0 regressions
- `PublishAllXml` → `{"published": true, "scope": "organization"}`
