---
name: dv-data
description: Safely query, create, update, upsert, verify, and delete Microsoft Dataverse table rows through the framework_power authenticated Web API client. Use when a request mentions Dataverse records, row data, demo or seed data, Lookup/@odata.bind values, Choice values, plug-in bypass, idempotent loading, record cleanup, or Web API CRUD. Do not use this skill for table, column, form, view, solution, or other metadata deployment.
agent_created: true
---

# Dataverse Row Data

Use this skill for Dataverse **row data**, not metadata deployment.

## Mandatory operating rules

1. Confirm the target environment and table before writing.
2. Acquire the authenticated client with `framework_power.runtime.get_client(environment)`; never construct an unauthenticated client or expose credentials.
3. Inspect live entity, attribute, Choice, and relationship metadata before composing a payload.
4. Query existing target records before binding Lookups. Never invent a GUID or Choice integer.
5. Treat reads as safe. Treat creates and updates as shared-environment mutations requiring clear user intent. Ask for explicit confirmation immediately before deletes, bulk cleanup, or another destructive operation.
6. Use `MSCRM.BypassCustomPluginExecution: true` only when the user requires plug-in bypass. If Dataverse rejects bypass, stop; never retry the write without the header.
7. Make repeatable loaders idempotent with a stable natural key or alternate key. Prefix disposable demo identifiers consistently, such as `DEMO-`.
8. Create records in dependency order: referenced/master rows, parent rows, then child rows.
9. Read every created or updated row back and verify scalar fields, Choice integers, Lookup GUIDs, and parent-child relationships.
10. Never print tokens, client secrets, or the contents of `.env`.

## Standard workflow

### 1. Establish scope

Capture:

- Environment (`dev`, `test`, or `production`)
- Table logical name
- Intended action and expected record count
- Natural key for idempotency
- Whether plug-in bypass is explicitly required
- Cleanup/rollback identifier strategy

Do not default a destructive action to production.

### 2. Discover live metadata

Run from the workspace root:

```bash
python .claude/skills/dv-data/scripts/dv_data.py metadata \
  --env dev \
  --table new_rollingforecast
```

Use the report to obtain:

- `EntitySetName`
- `PrimaryIdAttribute`
- `PrimaryNameAttribute`
- writable attributes and their types
- live Choice integer values and labels
- Lookup `ReferencingAttribute`
- exact `ReferencingEntityNavigationPropertyName`
- referenced table and target entity set

Read `references/dataverse-row-data.md` when handling payload construction, Lookups, Choices, plug-in bypass, batching, or troubleshooting.

### 3. Inspect live candidate rows

Query candidate master data before selecting Lookup values:

```bash
python .claude/skills/dv-data/scripts/dv_data.py query \
  --env dev \
  --table account \
  --select accountid,name \
  --filter "statecode eq 0" \
  --top 20
```

Resolve records by stable business attributes. If multiple candidates remain, show them and ask the user to choose.

### 4. Prepare a payload file

Use logical attribute names for scalar fields and the exact relationship navigation property for Lookups:

```json
{
  "new_name": "DEMO-ROW-001",
  "new_confidencelevel": 1,
  "new_AccountId@odata.bind": "/accounts(00000000-0000-0000-0000-000000000000)"
}
```

Do not use the lookup attribute name blindly. The bind key must match the live navigation property.

### 5. Preview and execute writes

All helper write commands are dry-run unless `--execute` is present.

Create once:

```bash
python .claude/skills/dv-data/scripts/dv_data.py create \
  --env dev \
  --table new_rollingforecast \
  --payload payload.json \
  --bypass-plugins \
  --execute
```

Idempotent create-or-reuse by natural key:

```bash
python .claude/skills/dv-data/scripts/dv_data.py upsert \
  --env dev \
  --table new_rollingforecast \
  --key-field new_name \
  --payload payload.json \
  --bypass-plugins \
  --execute
```

Update by GUID:

```bash
python .claude/skills/dv-data/scripts/dv_data.py update \
  --env dev \
  --table new_rollingforecast \
  --id 00000000-0000-0000-0000-000000000000 \
  --payload payload.json \
  --bypass-plugins \
  --execute
```

The helper validates payload keys and Choice integers against live metadata, refuses writes without `--execute`, and reads successful writes back.

### 6. Verify business invariants

Do not rely only on HTTP success. Verify:

- expected count and stable identifiers
- natural-key uniqueness
- exact Choice integer values
- Lookup GUID fields such as `_<lookup logical name>_value`
- parent Lookup GUIDs on child rows
- totals, dates, currencies, and status combinations
- absence of duplicate rows after rerunning an idempotent loader

### 7. Cleanup only after confirmation

First query and show the exact rows selected for deletion. Obtain explicit confirmation, then require both `--execute` and the row GUID repeated in `--confirm-delete`:

```bash
python .claude/skills/dv-data/scripts/dv_data.py delete \
  --env dev \
  --table new_rollingforecast \
  --id 00000000-0000-0000-0000-000000000000 \
  --confirm-delete 00000000-0000-0000-0000-000000000000 \
  --bypass-plugins \
  --execute
```

Delete dependents before parents. Stop on any unexpected selection or API response.

## Reusable implementation guidance

For a feature-specific loader, import the helper functions rather than embedding credentials or raw URL assembly:

```python
from framework_power.runtime import get_client

client = get_client("dev")
```

Keep scenario data separate from transport logic. Use stable identifiers, dependency-ordered creation, explicit Lookup maps, and a final verification summary.

## Resources

- `scripts/dv_data.py` — guarded metadata discovery and CRUD CLI
- `references/dataverse-row-data.md` — Web API payload, Lookup, Choice, bypass, verification, and troubleshooting details
