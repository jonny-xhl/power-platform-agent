# Picklist Global Option Set Resolution Fix

## What was done

Fixed a bug where Picklist fields in reverse-exported data dictionary Markdown files showed empty option values, violating the `docs/data_dictionary/CLAUDE.md` specification.

## Root cause

Dataverse Web API's `/Attributes` endpoint returns `OptionSet` metadata for Picklist attributes, but for **global option sets** (the common pattern for custom fields), the `Options` array is **not inlined** — only a name reference is returned. The actual options must be fetched separately via `GlobalOptionSetDefinitions(Name='...')`.

The reverse path (`reverse_table()` in `reverse.py`) parsed the inline `Options` but never followed the global option set reference, so all global-Picklist columns ended up with empty options.

## Changes

### 1. `framework_power/reverse.py` — `_resolve_picklist_options()`
New post-processing function called after columns are built:
- Maps `schema_name → optionset_name` from raw attribute data
- Batch-fetches unique global option sets via `client.get_global_optionset_by_name()` with caching (dedup)
- Updates `Column.options` in-place for Picklist columns missing options
- Best-effort: failures logged, not fatal

### 2. `framework_power/data_dictionary.py` — `_format_options()`
Format aligned to CLAUDE.md spec:
- Before: `草稿(1), 已批准(2), ... (5 total)` (comma, parens, truncated at 5)
- After: `草稿:1; 已批准:2` (semicolon, colon, no truncation)

### 3. Tests — 9 new (70 total pass)
- `test_reverse.py`: local options preserved, global options resolved, dedup for shared option sets, not-found keeps empty, dictionary markdown includes options
- `test_data_dictionary.py`: new format assertions, empty options, no truncation

### 4. ADR-008
`docs/spec/adr-008-picklist-global-optionset-resolution.md`

## Trade-off
`reverse_table()` now makes additional API calls (O(K) where K = unique option sets, not O(N) Picklist columns). The `Column` model was NOT changed — option set name is derived from raw attribute data, keeping the model clean.
