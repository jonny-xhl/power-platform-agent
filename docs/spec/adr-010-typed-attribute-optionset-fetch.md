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
