# ADR-010: Typed Attribute Query for OptionSet Data

## Status
Accepted

## Context

ADR-009 established the optionset reference design: local optionsets show inline
options in the 说明 column, global optionsets show document links. The implementation
expected that reverse-exporting a table from Dataverse would capture `OptionSet`
data (including `Options` array) for each Picklist and Boolean attribute.

**Problem**: The Dataverse Web API's polymorphic `/Attributes` endpoint does NOT
include the `OptionSet` navigation property in its response. Testing against the
live environment confirmed:

```
EntityDefinitions(metadataId)/Attributes
→ Returns 230 attributes, but NO attribute has the "OptionSet" key
```

Attempting to use `$expand=OptionSet` on this collection breaks the query entirely
(returning 0 results), because the collection is polymorphic — `OptionSet` only
exists on the derived types `PicklistAttributeMetadata` and `BooleanAttributeMetadata`.

Additionally, `GlobalOptionSetDefinitions(Name=...)` only works for true global
optionsets. Entity-bound optionsets (like `new_spare_salesorder_new_approvalstatus`)
cannot be fetched this way, resulting in 20+ 400 errors during data dictionary export.

**Impact**: All Picklist fields showed empty 说明 columns, and optionset docs
were never generated.

## Decision

Use typed derived-type collection queries to fetch OptionSet data in batch.

### 1. New client method: `get_optionset_attributes()`

```python
# Two batched calls — one per derived type
EntityDefinitions(metadataId)/Attributes/Microsoft.Dynamics.CRM.PicklistAttributeMetadata
    ?$expand=OptionSet&$select=LogicalName,OptionSet

EntityDefinitions(metadataId)/Attributes/Microsoft.Dynamics.CRM.BooleanAttributeMetadata
    ?$expand=OptionSet&$select=LogicalName,OptionSet
```

Returns `{logical_name: {"OptionSet": {...}}}` — merged into the base attributes
during `reverse_table()`.

### 2. Reverse captures both `optionset_name` AND `options` for global optionsets

Previously (ADR-009), global optionsets stored only `optionset_name` — no `options`.
Now both are captured. The data dictionary still renders document links (not inline)
when `optionset_name` is set, preserving the DRY design. But the `options` data is
available for `build_prefetched_optionsets()` to generate optionset docs without
redundant API calls.

### 3. Prefetched optionset data passed to `ensure_optionset_docs()`

`build_prefetched_optionsets()` converts Column-level option data into the raw dict
format expected by `optionset_to_markdown()`. This data is passed as `prefetched=`
to `ensure_optionset_docs()`, which uses it directly instead of attempting
`GlobalOptionSetDefinitions(Name=...)` lookups that fail for entity-bound optionsets.

## Consequences

### What becomes easier
- **Optionset docs for entity-bound optionsets**: Previously impossible (400 error),
  now works from data already fetched during reverse.
- **Fewer API calls**: OptionSet data is fetched once during reverse and reused for
  doc generation, instead of re-fetching each optionset individually.
- **Correct data dictionary**: All Picklist fields now show proper optionset links
  or inline options.

### What becomes harder
- **Slightly larger Column objects**: Global optionset columns now carry `options`
  data that was previously omitted. This is a minor memory increase, not a concern.
- **Two API calls instead of one**: `get_optionset_attributes()` adds 2 batched
  calls (Picklist + Boolean) per reverse operation. These are fast (< 200ms each).

### Trade-off
We accept slightly larger Column objects in exchange for correct, self-contained
optionset documentation. The data is available for both inline rendering (local
optionsets) and document generation (global optionsets) without redundant fetches.

## Files Changed

- `framework_power/client/dataverse_client.py` — New `get_optionset_attributes()` method
- `framework_power/reverse.py` — Merge optionset data, capture both name+options for globals
- `framework_power/data_dictionary.py` — New `build_prefetched_optionsets()`, `_option_label_to_raw()`,
  updated `ensure_optionset_docs()` with `prefetched=` parameter
- `framework_power/cli.py` — `_reverse_to_dictionary()` passes prefetched data
- `test/unit/test_framework_power/test_reverse.py` — Updated `ReverseFakeClient`, test data, assertions

## Addendum (2026-09-09): Two downstream round-trip gaps closed

ADR-010 fixed the *fetch* side. Two consumers of that data were still broken and
surfaced during a `reverse` of `new_quote` (客户报价申请):

### Gap 1 — `codegen.emit_column` dropped `optionset_name`

`reverse.py` correctly set `Column.optionset_name` for global optionsets, but
`codegen.emit_column()` only ever emitted `options=` — the name never reached the
generated `.py`. Every reverse export therefore **silently downgraded a global
optionset to a local one**: re-deploying the reversed file to a fresh environment
would create a duplicate local optionset instead of binding the shared global one
(violating ADR-009/ADR-014).

Fix: emit `optionset_name='...'` when set, *and* keep `options=` (needed by
`build_prefetched_optionsets()` for doc generation). The name decides
bind-vs-inline semantics; the options are only a snapshot.

### Gap 2 — `plan` flagged every global-optionset field as `manual_update_required`

Like ADR-010's original bug, `plan_table()` took `existing_attrs` from the
polymorphic `/Attributes` endpoint (no `OptionSet` data) and passed it to
`optionset_changed()`. Local said "3 options", remote said "0" → false positive
on 4 of 4 global-optionset fields.

Fix: gate the `optionset_changed()` branch on `not col.optionset_name`, mirroring
the deploy path (which already did this). Options of a global optionset are owned
by the shared optionset, not by the table — they must not be diffed per-table.

### Verification

After both fixes, `pp plan new_quote --env dev` went from
`14 would_create / 8 rels would_create / 4 manual_update_required` to
**0 creates, 0 manual_update_required** — local definition and environment are
now byte-for-byte in sync.

### Files Changed (addendum)

- `framework_power/codegen.py` — `emit_column()` emits `optionset_name`
- `framework_power/deployer.py` — plan path gates `optionset_changed()` on `not col.optionset_name`
- `test/unit/test_framework_power/test_codegen.py` — 2 new tests (global + local picklist emission)
- `test/unit/test_framework_power/test_plan.py` — 1 new test (global optionset not flagged)
