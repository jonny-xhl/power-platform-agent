# ADR-017: Picklist Default Value (`DefaultFormValue`)

## Status
Accepted

## Context

Adding a choice column to the PO table (`new_sparepartscustomerpo`) required a
default value ("非电摩"). The `Column` model has always advertised support for
this — `models.py` documents `default_value: Union[bool, int, str, None]  #
Boolean->bool, Picklist/Integer->int` — and `codegen.emit_column()` emits it, so
local definitions authored it freely (15 picklist columns across 4 tables do).

It never worked. Three places read or wrote the **wrong property name**:

| Layer | Code | Property used | Property Dataverse actually uses |
|---|---|---|---|
| create | `serializer.serialize_column()` | *(nothing emitted)* | `DefaultFormValue` |
| patch | `serializer._UPDATABLE_BY_TYPE[Picklist]` | *(not in the allow-list)* | `DefaultFormValue` |
| reverse | `reverse.py` picklist branch | `DefaultValue` | `DefaultFormValue` |

`DefaultValue` is a **Boolean-only** property (`BooleanAttributeMetadata`). Picklist
attributes expose `DefaultFormValue`, an integer where **`-1` means "no default"**
(Dataverse also echoes `-1` from the polymorphic `/Attributes` endpoint).

**Impact — silent data loss in both directions:**

- On create, the declared default was dropped: the column was created with *no*
  default, and nothing in the output said so (`1 created`, exit 0).
- On reverse, `attr.get("DefaultValue")` returned `None` for every picklist, so
  `default_value` was never captured — the intent could not even be re-discovered
  from the environment.
- On deploy, a drifted/default-less remote could never be brought back in line:
  `DefaultFormValue` was not an updatable key, so `plan` reported `would_skip`.

Live evidence (dev, 2026-09-16) — declared locally but absent in the environment:

```
new_invoiceappliction.new_taxrate   local default_value=2   remote DefaultFormValue=None
```

## Decision

Treat `DefaultFormValue` as the single source of truth for picklist defaults across
all three layers.

### 1. Create — `serializer.serialize_column()`

Emit `DefaultFormValue` on the picklist branch, for **both** local (inline) and
global-bound picklists — the default lives on the attribute, not the optionset:

```python
elif col.default_value is not None:
    attr["DefaultFormValue"] = int(col.default_value)
```

A **`bool`** value is rejected with a warning instead of being coerced. `False`
would become option value `0`, which is rarely a real option (e.g. `new_potype`
uses 1/2) — pushing it risks a default that the option list does not contain.
Garbage in, loud warning out.

### 2. Patch — `serializer._UPDATABLE_BY_TYPE[Picklist]`

Add `DefaultFormValue` to the updatable allow-list so `build_attribute_patch()` and
therefore `plan`/`deploy` can reconcile a drifted default. This is safe because the
**polymorphic `/Attributes` endpoint does return `DefaultFormValue`** (verified live:
`new_potype` → `1`), unlike `OptionSet` data (ADR-010). No typed fetch is required
and there is no false-positive risk.

### 3. Reverse — `reverse.py` picklist branch

Read `DefaultFormValue` and normalise the sentinel:

```python
raw_default = attr.get("DefaultFormValue")
if raw_default is not None and int(raw_default) != -1:
    kwargs["default_value"] = int(raw_default)
```

Mapping `-1 → None` is essential: carrying `-1` through would make the next deploy
push a bogus default of `-1`, and every picklist without a default would show
permanent `would_patch` noise.

## Consequences

### What becomes easier

- **Declared intent is real.** `default_value=N` in a local definition now survives
  create, is visible to `plan`, and can be repaired by `deploy`.
- **Reverse is lossless for picklists.** A reverse→deploy round-trip preserves
  defaults, so new environments (UAT/PROD) get the same data-entry behaviour.
- **Silent divergence is gone.** A default mismatch now surfaces as
  `would_patch` with `fields=['DefaultFormValue']`.

### What becomes harder / needs care

- **Previously-ignored declarations became live.** Any local picklist default that
  was silently dropped will now be pushed on the table's next deploy. Audited
  across all 21 local tables: 15 declared picklist defaults, of which **exactly one
  changes the environment** — `new_invoiceappliction.new_taxrate`
  (local `2`, remote `None`). The other 14 either already match or point at fields
  that do not exist in dev (`new_inquiry.new_status`, `new_projectbudget.new_status`).
  No `bool` defaults were found, so the new guard is pure defence today.
- **`-1` is now meaningful.** Code comparing defaults must treat `-1` as "none",
  never as a value.

### Trade-off

We accept that a full deploy of a table can now change data-entry defaults, in
exchange for the local definition actually describing the environment. The
`bool` guard trades a hard failure (or a bogus default) for a warning.

## Files Changed

- `framework_power/serializer.py` — picklist branch emits `DefaultFormValue` (+ bool guard);
  `_UPDATABLE_BY_TYPE[Picklist]` gains `DefaultFormValue`
- `framework_power/reverse.py` — picklist branch reads `DefaultFormValue`, normalises `-1 → None`
- `test/unit/test_framework_power/test_serializer.py` — 6 new tests
  (emit / global-bound / None / bool-ignored / updatable overlay / patch drift detection)
- `test/unit/test_framework_power/test_reverse.py` — 2 new tests (capture + `-1` sentinel)

## Verification

- Field created end-to-end with the fix in place: `new_sparepartscustomerpo.new_motorcycle_mark`
  read back `DefaultFormValue=2` (had the bug persisted, this would be absent).
- Re-reverse captured 10 previously-lost defaults on the same table
  (`new_potype=1`, `new_postatus=1`, `new_dmsstatus=1`, …), and correctly left
  `new_advance_ratio_met` (remote `-1`) without a default.
- `pp plan new_sparepartscustomerpo` → **109 would_skip / 0 would_patch / 0 would_create**.
- `pytest test/unit` → 523 passed (8 new).

## Known adjacent issue (not fixed here)

`reverse` emits relationships in a **non-deterministic order** — two consecutive
reverses of the same table produced byte-different files with an identical
relationship *set* (41 changed lines, set-equal). It does not affect correctness,
but it makes diffing a re-reverse noisy. Candidate follow-up: sort relationships by
`SchemaName` before emission.
