# ADR-009: Optionset Documentation — Link Instead of Inline

## Status
Accepted — supersedes ADR-008

## Context

ADR-008 introduced `_resolve_picklist_options()` to fetch global optionset data
during reverse and inline the options into every Picklist column's `options` list.
This had three problems:

1. **Data duplication**: If 10 tables reference the same global optionset
   `new_order_status`, its 20+ options are duplicated across 10 data dictionary
   files. When the optionset changes, all 10 files need re-export.

2. **N+1 API calls during reverse**: Each unique global optionset required a
   separate `get_global_optionset_by_name()` call. With dedup caching this was
   manageable, but it's still unnecessary network I/O for a documentation task.

3. **Mixed semantics in the data model**: `Column.options` held both local
   (field-level) options AND resolved global options, with no way to distinguish
   them. This made it impossible to know whether options were the source of truth
   or a cached snapshot.

The user's requirement clarified the right design:
- **Local (field-level) optionset** → list options inline in the 说明 column
- **Global optionset** → link to the optionset's own doc page
- **Missing optionset doc** → auto-export it first

## Decision

### 1. Column model: add `optionset_name`
New field `Column.optionset_name: Optional[str]`:
- `None` → local (inline) optionset, options live in `Column.options`
- `"<name>"` → references global optionset, options are NOT inlined

### 2. Reverse: capture name, don't inline
`_attr_to_column()` checks `OptionSet.Name`:
- Name present → `kwargs["optionset_name"] = name` (skip `Options` entirely)
- Name absent → populate `Column.options` from inline `Options` array

Removed `_resolve_picklist_options()` entirely — no more N+1 fetches during reverse.

### 3. Data dictionary: merge into 说明 column
Removed the separate "选项集 / 布尔值" table column. All optionset/boolean info
now goes into the 说明 (description) column:

| Type | Format in 说明 column |
|------|----------------------|
| Local Picklist | `草稿:1; 已批准:2; 已关闭:3` |
| Global Picklist | `[选项集: new_order_status](../optionsets/new_order_status.md)` |
| Boolean | `True=是, False=否` |

### 4. Auto-generate missing optionset docs
`ensure_optionset_docs()` fetches only referenced optionsets that don't have
a doc on disk yet. Called by both single-table and batch reverse paths.

For batch mode, `_resolve_table_optionsets_from_disk()` scans the already-written
table Markdown files to collect referenced optionset names via regex — no need to
keep in-memory Table objects around across threads.

## Consequences

### What becomes easier
- **Single source of truth**: Global optionset options live in one place
  (`optionsets/<name>.md`). Change the optionset → re-export just that one doc.
- **Fewer API calls**: Reverse no longer fetches optionsets at all. Doc
  generation only fetches optionsets that are missing from disk.
- **Clean data model**: `Column.options` is only populated for local optionsets.
  `Column.optionset_name` is the definitive reference for global optionsets.
- **Incremental**: Re-running batch reverse only writes new optionset docs,
  existing ones are skipped.

### What becomes harder
- **Two-step lookup**: Reading a table doc and wanting option values requires
  following the link to the optionset doc. This is a documentation trade-off
  favoring DRY over self-containment.
- **Offline rendering**: If optionset docs haven't been generated yet, the links
  are dangling. Mitigated by auto-generation during reverse.

### Migration
- ADR-008 is superseded. The `_resolve_picklist_options` approach was never
  released — it was implemented and immediately revised.
- Existing data dictionary files need full re-export to benefit from the new
  format: `pp reverse --all --dictionary --parallel auto`.
