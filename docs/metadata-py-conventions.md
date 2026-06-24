# Authoring Conventions for `metadata_py` Definitions

This is the **contract** that constrains every AI-generated table definition. The typed
models in `framework_power/models.py` are the hard schema; this document is the style +
correctness checklist. `python -m framework_power lint` enforces it offline (no network)
before any `plan`/`deploy`.

## Where definitions live

- One file per table: `metadata_py/tables/<schema_lowercase>.py`
- Each file exposes a module-level `TABLE: Table` (this is how the registry discovers it).
- File-name stem = the definition key used by the CLI (e.g. `new_projectbudget`).

## The pipeline

```
需求 (sources/features/<feature>/01-prd)
  → design-dv-model → Excel design (sources/features/<feature>/02-designs)
  → dv-model-to-python  → metadata_py/tables/<schema>.py   (this is the AI step)
  → framework_power lint          (offline gate)
  → framework_power plan --env    (read-only dry run)
  → framework_power deploy --env  (sync to Dataverse)
```

## Naming (different from the YAML path!)

The YAML path lowercases names (`new_payment_number`). **The Python path uses
Dataverse-standard PascalCase**, and naming is the author's responsibility (the CLI
does **not** silently rewrite names — `lint` validates, `deploy` ships exactly what
you wrote).

| Element | Rule | Example |
|---|---|---|
| Custom table `schema_name` | `{prefix_}{PascalCase}` | `new_ProjectBudget` |
| Custom column `schema_name` | `{prefix_}{PascalCase}` | `new_PaymentNumber` |
| Relationship `schema_name` | `{prefix_}_{Referenced}{Referencing}` | `new_ProjectBudget_Account` |
| Lookup column `schema_name` | `{prefix_}{PascalCase}` ending in `Id` | `new_AccountId` |
| Standard entity (extend) | keep logical name | `account` |

Publisher prefix comes from `config/publishers.yaml` (current publisher). Default `new`.

> Avoid the `*Id` collision trap (dv-metadata): a regular column named `new_FooId` will
> collide if a lookup `new_FooId` is added later. Use `new_SrcFooId` for source-system IDs.

## Labels — always bilingual

Use `Label.bilingual(zh, en)` for `display_name`, `display_collection_name`,
`description`, option labels, and boolean true/false labels. Chinese = language code
`2052`, English = `1033`. If you only have one language, `Label.zh(text)` is accepted
but bilingual is the project standard.

## Structure rules (enforced by lint)

- **Exactly one primary name**: one `String` column with `is_primary_name=True`
  (or set `Table.primary_name_column`). If none is flagged, the first String column is
  auto-picked. Zero String columns is an error (Dataverse requires a primary name).
- **No duplicate column schema names** (case-insensitive).
- **No duplicate picklist option values** within a column.
- **No duplicate relationship schema names**.
- Every custom `schema_name` starts with the publisher prefix.

## Relationships — Referential cascade only

Custom lookups must use Referential cascade (Dataverse allows only one Parental per
entity, and `UserOwned` entities already have one via Owner). Never use `Cascade.Active`.

```python
Relationship(
    schema_name="new_ProjectBudget_Account",
    referenced_entity="account",        # parent (1 side), logical name
    referencing_entity="new_projectbudget",  # this table, logical name
    lookup=LookupColumn("new_AccountId", Label.bilingual("客户","Account"), target_entity="account"),
    cascade=CascadeConfig(delete=Cascade.RemoveLink, assign=Cascade.NoCascade),
)
```

- A 1:N relationship creates its lookup via Deep Insert — never define the lookup as a
  standalone `Column`.
- `lookup.target_entity` must equal `referenced_entity`.
- The referenced entity must already exist in the target environment (deploy checks this).

## Type mapping (Excel → `AttributeType`)

| Excel type | `AttributeType` | Notes |
|---|---|---|
| Text / Email / Phone / URL | `String` | set `format_name` for Email/Phone/Url |
| Multiline Text | `Memo` | `max_length` |
| Whole Number | `Integer` | `min_value`/`max_value` |
| Decimal Number | `Decimal` | `precision` |
| Currency | `Money` | `precision`, `precision_source=2` |
| Floating Point | `Double` | `precision` |
| Yes/No | `Boolean` | `boolean_labels`, `default_value` |
| Choice (local) | `Picklist` | `options=[Option(value, Label...)]` |
| Date and Time | `DateTime` | `date_time_behavior`, `format` |
| Lookup | (via `Relationship`) | not a `Column` |

## Required-level

`RequiredLevel.ApplicationRequired` / `Recommended` / `None_`. Primary-name columns are
typically `ApplicationRequired`.

## After authoring — always run the gate

```bash
python -m framework_power lint new_projectbudget        # offline; must be 0 errors
python -m framework_power plan new_projectbudget --env dev   # read-only diff
python -m framework_power deploy new_projectbudget --env dev # actual sync
```

`lint` is the constraint gate: it must report **0 errors** before you `plan`/`deploy`.
Warnings (e.g. naming style) are advisory but should be fixed.
