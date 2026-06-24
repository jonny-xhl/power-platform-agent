# Metadata Deploy (`framework_power`)

A self-contained, **Python-first** library for deploying Dataverse tables. Instead of
authoring YAML and converting it to Web API JSON, you define a table as **typed Python
models** — the model definition *is* the single source of truth — and reconcile it
against an environment with `deploy_table()`.

This package is intentionally **isolated** from the legacy `framework/` YAML toolchain:
it does not import from or modify `framework/`. Reused transport/auth/config/retry code
lives as copies under `framework_power/client/`.

## Why

- One executable source of truth per table (no separate YAML + converter).
- Full attribute-type coverage (String, Integer, BigInt, Money, Decimal, Double,
  Picklist, Boolean, Memo, DateTime, File) with MaxLength / Precision / ranges.
- Multi-language labels (zh-CN `2052` + en-US `1033`, or any languages).
- Create **and** update (PATCH sync of updatable properties) **and** relationships.
- No new dependencies (`requests` + `msal` already in the project).

## Quick start

```python
from framework_power import Table, Column, deploy_table, get_client
from framework_power.models import AttributeType, Label, RequiredLevel

table = Table(
    schema_name="new_ProjectBudget",
    display_name=Label.bilingual("项目预算", "Project Budget"),
    columns=[
        Column("new_Name", AttributeType.String,
               display_name=Label.bilingual("名称", "Name"),
               is_primary_name=True, required=RequiredLevel.ApplicationRequired, max_length=200),
    ],
)
print(deploy_table(get_client("dev"), table))
```

A complete reference script covering every column type + a 1:N relationship lives at
`framework_power/examples/setup_projectbudget.py`:

```bash
python -m framework_power.examples.setup_projectbudget --env dev
```

## Defining & deploying tables (the CLI workflow)

The intended pipeline is **需求 → definition → sync**, with definitions living in
`metadata_py/tables/` (one `<schema>.py` per table, each exposing `TABLE`). Drive it
through one CLI:

```bash
python -m framework_power list                           # discover metadata_py/tables/*.py
python -m framework_power show new_projectbudget         # print the serialized payload (offline)
python -m framework_power lint new_projectbudget         # offline convention gate (0 errors required)
python -m framework_power lint                           # lint ALL definitions
python -m framework_power plan new_projectbudget --env dev   # read-only dry run
python -m framework_power deploy new_projectbudget --env dev # sync to Dataverse
python -m framework_power deploy-all --env dev           # deploy all, referenced entities first
```

- **Requirement → definition**: the `dv-model-to-python` skill converts an Excel design
  (from `design-dv-model`) into `metadata_py/tables/<schema>.py`, constrained by
  [`docs/metadata-py-conventions.md`](metadata-py-conventions.md) and the typed models.
- **Triggering**: `framework_power` is a plain library (not MCP tools), so the AI runs
  the CLI above via Bash — no MCP round-trip.
- **`lint` is the constraint gate**: it enforces the authoring contract offline (prefix,
  PascalCase, single primary-name, duplicate checks) so generation is bounded before any
  environment access. Unlike the YAML path, names are **validated, not auto-rewritten**.

A canonical definition lives at `metadata_py/tables/new_projectbudget.py`; a thin
programmatic runner is at `framework_power/examples/setup_projectbudget.py`.

## Deploy semantics

`deploy_table(client, table)` is **idempotent and never destructive**:

| Object | Behavior |
| --- | --- |
| Entity | Create if missing; otherwise PATCH updatable props (DisplayName, Description, HasNotes, IsAuditEnabled, IsQuickCreateEnabled). |
| Attribute | On first entity create, columns ride along inline. On an existing entity: POST if missing; otherwise PATCH only the updatable, differing properties. No-op when nothing differs. |
| Relationship | Create-only (Dataverse cannot PATCH relationship definitions). Skipped if present. |

**Picklist/Boolean option sets are create-only** via the attribute endpoint. If a script
changes options on an existing column, the deploy reports `manual_update_required`
(update via the maker portal or `InsertOptionValue`/`UpdateOptionValue` actions).

## Metadata propagation & retries

Dataverse needs 3–30s after each create for index build / cache propagation. The
deployer waits between phases and retries transient signals from the `dv-metadata`
skill (`0x80040216`, `0x80060891`, "another customization operation is running",
MetadataCache misses) with backoff. Tune delays via `DeployConfig`:

```python
from framework_power import deploy_table, DeployConfig
deploy_table(client, table, config=DeployConfig(after_entity_create_delay=8.0))
```

## Labels

`Label` carries one or more `(text, language_code)` pairs. Helpers:

```python
Label.zh("名称")                 # zh-CN only (legacy default)
Label.en("Name")                 # en-US only
Label.bilingual("名称", "Name")   # zh-CN + en-US
Label.parse("名称")               # str -> zh-only; accepts Label/LocalizedLabel/(zh,en)
```

## Auth

`get_client(environment)` reads `config/environments.yaml` (expanding `${DEV_*}` from
`.env`) and acquires a token via the client-credentials flow (cache-first, refresh on
expiry). Tokens are persisted under `.pp-local/state/tokens.json`.

## Type reference

See `framework_power/models.py` for the full dataclass surface (`Table`, `Column`,
`LookupColumn`, `Relationship`, `CascadeConfig`, `Option`, `BooleanLabels`, `Label`,
enums). For Dataverse Web API type/format details, consult the `dataverse:dv-metadata`
skill.
