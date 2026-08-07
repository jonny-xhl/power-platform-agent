# ADR-008: Picklist Global Option Set Resolution in Reverse Path

## Status
Superseded by ADR-009

## Context

The Dataverse Web API endpoint `EntityDefinitions({metadata_id})/Attributes` returns
attribute metadata for all columns of a table. For **Picklist** attributes, the response
includes an `OptionSet` property containing the option set reference.

However, there is a critical distinction:

- **Local (inline) option sets**: The `Options` array is populated inline in the attribute
  response. The code in `_attr_to_column()` correctly parses these.
- **Global option sets** (the common pattern for custom Picklist fields): The attribute
  response only contains a *reference* — `OptionSet.Name`, `OptionSet.IsGlobal`, etc. — but
  the `Options` array is **empty or absent**. The actual option values must be fetched
  separately via `GlobalOptionSetDefinitions(Name='<name>')`.

**Impact**: All reverse-exported data dictionary Markdown files had empty "选项集" columns
for Picklist fields that used global option sets (which is the majority of custom Picklist
fields). This violated the `docs/data_dictionary/CLAUDE.md` specification which requires
the option set reference column to contain `标签:值; 标签:值; ...` for every Picklist.

Evidence: the reverse-exported `new_spare_salesorder.py` had 30+ Picklist columns, none
with `options=[...]`, while manually authored files (e.g., `account.py`) had options
populated because they were hand-written.

## Decision

Implement a **post-processing pass** in `reverse_table()` that resolves global option sets
for Picklist columns whose options are still empty after the initial attribute parse.

### Implementation: `_resolve_picklist_options()`

A new function in `reverse.py` that:

1. **Maps** `schema_name → optionset_name` from the raw attribute data (the `OptionSet.Name`
   field), since the `Column` model does not store the option set name.
2. **Batch-fetches** each unique global option set via `client.get_global_optionset_by_name(name)`,
   with **caching** to avoid duplicate API calls when multiple columns share the same global
   option set (common for status/priority fields).
3. **Updates** `Column.options` in-place for any Picklist column that was missing options.

### Design constraints

- **Best-effort**: Failures are logged and swallowed — a missing option set must not break
  the reverse export. The column's options simply remain empty.
- **Caching**: A local dict cache `{name: [Option]}` prevents re-fetching the same option
  set. For N columns sharing K unique option sets, only K API calls are made (not N).
- **No model change**: The `Column` dataclass does not gain an `optionset_name` field.
  The mapping is derived from raw `attrs` data, keeping the model clean.

### Format alignment

Additionally, `_format_options()` in `data_dictionary.py` was updated to match the
`CLAUDE.md` specification:

| Before | After |
|--------|-------|
| `草稿(1), 已批准(2)` | `草稿:1; 已批准:2` |
| Comma-separated, parentheses | Semicolon-separated, colon |
| Truncated at 5 options with `... (N total)` | All options shown (no truncation) |

## Consequences

### What becomes easier
- Data dictionary Markdown files now show Picklist option values inline, as the spec requires.
- Reverse-exported Python files will also include `options=[...]` for Picklist columns,
  making them more useful for reference and re-deployment.
- The cached batch-fetch approach means the performance cost is O(K) API calls where K is
  the number of unique global option sets, not O(N) where N is the number of Picklist columns.

### What becomes harder
- `reverse_table()` now makes additional API calls for global option sets, adding latency
  proportional to the number of unique option sets. For a table with 30 Picklist columns
  sharing 15 option sets, this adds ~15 calls.
- The `_resolve_picklist_options()` function is tightly coupled to the Dataverse API's
  behavior of not inlining global option set options. If Microsoft changes this behavior
  (unlikely but possible), the function becomes a no-op.

### Trade-off: model cleanliness vs. convenience
We chose NOT to add an `optionset_name` field to the `Column` dataclass, deriving the
mapping from raw attribute data instead. This keeps the model clean but means the
resolution logic is Dataverse-specific and lives in `reverse.py` rather than in the model.
If other paths (e.g., import from Excel) also need option set resolution, a model field
would be preferable.
