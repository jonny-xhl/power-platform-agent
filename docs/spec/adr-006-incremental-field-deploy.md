# ADR-006: Incremental Field Deployment (`--fields`)

## Status
Accepted

## Context
The current `pp deploy` operates in **full-sync mode**: it loads the entire table definition
(all columns + all relationships) and reconciles every custom component against the live
Dataverse environment.  This is correct for first-time deployment but **wasteful and risky**
for incremental changes:

1. **Reverse overhead**: To add one field, users must first `pp reverse` the entire entity
   (101+ columns, 34+ relationships) just to get a `.py` definition they can edit.
2. **Full traversal**: The deploy engine iterates over *all* 102 columns, serialising each
   one and building patch diffs even when 101 of them are skipped.
3. **Accidental mutation risk**: Although "already exists" fields are skipped, a bug in
   the patch-diff logic could theoretically mutate existing fields.

For the common scenario of "add one field to a solution", the full pipeline is overkill.

## Decision
Add a `--fields` CLI flag to `pp deploy` that enables **incremental mode**:

```bash
pp deploy new_spare_salesorder --fields new_package_remark,new_LookupId \
    --solution 20260806_fix --solution-clean
```

### Core behaviour

| Aspect | Full mode (default) | Incremental mode (`--fields`) |
|--------|:---:|:---:|
| Entity create/update | ✅ Full entity + attributes | 🐚 Empty shell if new; skip if exists |
| Attribute sync | ✅ All custom columns | ✅ Only named columns |
| Relationship sync | ✅ All custom relationships | ✅ Only relationships for named Lookups |
| Solution membership | ✅ All custom fields | ✅ Only named fields |
| Unknown field names | — | ❌ `ValueError` before any API call |

### Field resolution
A field name is resolved against **both** sources:
- `table.columns` → plain attribute (String, Int, Money, …)
- `table.relationships[].lookup` → Lookup attribute + N:1 relationship (deep insert)

Users don't need to know or care where a field is stored internally — the engine resolves
it transparently.

### Transactional characteristics
The deployment is **not ACID-transactional** (Dataverse Web API has no cross-request
transactions), but it IS **idempotent and retry-safe**:

- Every creation checks "already exists" before/after calling the API.
- Each field is handled independently; one failure doesn't abort the others.
- On retry, created items are skipped, missing items are created.
- Lookup fields have two steps (attribute → relationship); if step 2 fails, retry
  creates only the missing relationship (attribute already exists → skipped).

## Consequences

### What becomes easier
- **One-field additions**: `pp reverse` is unnecessary — edit the `.py` definition
  by hand (or keep a full reverse snapshot), then deploy only the new field.
- **Safety**: Only the specified fields are touched; no risk of accidental mutation
  to other columns.
- **Speed**: Deploy skips entity-level sync, loops over 1–3 fields instead of 100+.
- **Solution portability**: Only the named fields are added to the solution, keeping
  it minimal.

### What becomes harder
- **Definition drift**: The local `.py` definition may not reflect reality for fields
  not included in `--fields`.  A full `pp deploy` (without `--fields`) is still the
  canonical way to ensure complete sync.
- **Entity metadata**: Display name, HasNotes, IsQuickCreateEnabled etc. are NOT synced
  in `--fields` mode.  These require a full deploy.

### Trade-offs
| Dimension | Full deploy | `--fields` |
|-----------|-------------|------------|
| Correctness guarantee | Strong (entire definition = truth) | Weak (only specified fields) |
| Safety (no unintended changes) | Medium (patch-diff on all fields) | High (only specified fields touched) |
| Speed for 1-field change | Slow (100+ fields traversed) | Fast (1-3 fields) |
| Definition maintenance burden | High (keep entire .py in sync) | Low (edit only what changes) |

The two modes are **complementary, not competing**.  Full deploy is for initial
provisioning and periodic audit; incremental deploy is for day-to-day field additions.

## Implementation
- `deployer.py`: `deploy_table(fields=…)`, `_deploy_entity(empty_shell=…)`,
  `_deploy_attributes(columns=…)`, `_deploy_relationships(relationships=…)`,
  `_add_entity_to_solution(field_names=…)`, `_resolve_fields()`
- `cli.py`: `cmd_deploy()` parses `--fields` comma-separated string
- Tests: 7 new test cases covering regular/lookup/mixed/unknown/retry/solution-clean
- ~120 lines changed (70 deployer + 10 CLI + 100 tests)
