# Dataverse Row Data Reference

## Scope

Use the Dataverse Web API for table rows only. Use `framework_power` metadata components and CLI commands for tables, columns, relationships, forms, views, roles, solutions, plug-in registration, and Web resources.

## Authentication

Run from the workspace root so the runtime finds `config/environments.yaml` and `.env`:

```python
from framework_power.runtime import get_client

client = get_client("dev")
```

`get_client` resolves the configured environment, loads environment variables, obtains or reuses a client-credentials token, and returns an authenticated `DataverseClient`.

Never log `Authorization`, access tokens, client secrets, or `.env` content.

## Metadata-first discovery

### Entity metadata

Retrieve at least:

- `LogicalName`
- `SchemaName`
- `EntitySetName`
- `PrimaryIdAttribute`
- `PrimaryNameAttribute`

The table logical name and entity-set name are not interchangeable. Metadata uses a logical name such as `new_rollingforecast`; row URLs use the entity set such as `new_rollingforecasts`.

### Writable attributes

Inspect live attributes and retain only fields where `IsValidForCreate` or `IsValidForUpdate` is true. Check:

- `LogicalName`
- `SchemaName`
- `AttributeType`
- `RequiredLevel`
- `MaxLength`
- number precision/range where applicable
- date behavior/format where applicable

Do not assume the local model is already deployed or current.

### Choice values

Get live typed Picklist metadata with `OptionSet` expanded. A Choice payload uses an integer, never a display label:

```json
{
  "new_confidencelevel": 1
}
```

Match labels by `UserLocalizedLabel`, falling back to `LocalizedLabels`. Stop if the desired label is absent or ambiguous.

Boolean fields use JSON `true`/`false`, not the localized Yes/No labels.

### Lookup navigation properties

For a many-to-one relationship, inspect:

- `ReferencingEntity`
- `ReferencingAttribute`
- `ReferencingEntityNavigationPropertyName`
- `ReferencedEntity`

Then resolve the referenced entity’s `EntitySetName`.

Payload example:

```json
{
  "new_AccountId@odata.bind": "/accounts(<account-guid>)"
}
```

The bind key is the navigation property, not necessarily the logical Lookup attribute. The bind value uses the target entity set and an existing GUID.

To clear a Lookup during update, use the relationship `$ref` delete endpoint or a supported null-binding pattern only after verifying the table behavior. Do not guess.

## Query construction

Pass OData parameters through the HTTP library instead of concatenating unescaped user values:

```python
response = client.session.get(
    client.get_api_url("accounts"),
    params={
        "$select": "accountid,name",
        "$filter": "statecode eq 0",
        "$orderby": "name asc",
        "$top": "20",
    },
)
```

Escape single quotes in OData string literals by doubling them:

```python
def odata_string(value: str) -> str:
    return value.replace("'", "''")
```

Use broad queries plus Python-side filtering when shell quoting becomes fragile, but keep result limits reasonable. Avoid interpolating untrusted user text into `$filter` without validation.

Useful response fields for Lookup verification are named like:

```text
_<lookup logical name>_value
```

For example, a Lookup `new_accountid` is commonly returned as `_new_accountid_value`.

## Create

Use `Prefer: return=representation` so the response contains the created row:

```python
headers = {"Prefer": "return=representation"}
response = client.session.post(
    client.get_api_url(entity_set),
    json=payload,
    headers=headers,
)
response.raise_for_status()
row = response.json()
```

When the user explicitly requires plug-in bypass:

```python
headers["MSCRM.BypassCustomPluginExecution"] = "true"
```

If Dataverse rejects bypass because the caller lacks the required privilege, stop and report the error. Never remove the header and retry silently.

## Idempotent create-or-reuse

Choose a stable natural key that is unique for the dataset, such as a primary-name value prefixed with `DEMO-`.

Algorithm:

1. Query by the natural key with `$top=2`.
2. If no row exists, create it.
3. If one row exists, reuse it or explicitly update it according to the requested semantics.
4. If more than one row exists, stop because the key is not unique.
5. Read the row back and verify it.

Do not call a check-then-create operation transactionally safe under concurrency. For concurrent loaders, define and use a Dataverse alternate key and PATCH through that key.

## Update

Use PATCH against the entity-set row URL:

```python
response = client.session.patch(
    client.get_api_url(f"{entity_set}({row_id})"),
    json=payload,
    headers=headers,
)
response.raise_for_status()
```

For optimistic concurrency, first retrieve the ETag and send `If-Match`. Use this when avoiding lost updates matters.

Verify the updated row with a GET. A `204 No Content` response alone does not prove business correctness.

## Delete and cleanup

Deleting affects shared state and requires explicit confirmation immediately before execution.

Before deletion:

1. Query the exact rows.
2. Show IDs and primary names.
3. Confirm the target environment.
4. Obtain explicit user approval.
5. Delete children/dependents before parents.
6. Verify each row now returns `404` or no longer appears in the selection.

Never implement a broad delete based only on an unreviewed prefix or a filter supplied from an untrusted source.

## Verification checklist

After a create or update, retrieve by GUID and verify:

- primary ID and primary name
- every business-critical scalar field
- Choice integer values
- Lookup GUIDs
- parent-child relationship links
- expected created/updated count
- uniqueness of natural keys
- rerun behavior for idempotent loaders

For demo data, also verify scenario coherence, such as:

- sum of child shipment quantities equals the parent forecast quantity when intended
- shipped quantity does not exceed planned quantity unless demonstrating an exception
- amounts match quantity and unit price where required
- dates and statuses are internally consistent

## Dependency ordering

Create in this order:

1. Version/reference rows created by this load
2. Other master/reference rows
3. Parent business rows
4. Child/dependent rows
5. Relationship/junction rows

Delete in reverse order.

## Error handling

- `400`: inspect logical names, payload types, required fields, length limits, Choice integers, and Lookup navigation properties.
- `401`: refresh or correct authentication; do not expose credentials.
- `403`: report missing privilege. If bypass was requested, do not retry without bypass.
- `404`: distinguish a wrong entity set from a missing row.
- `409` or alternate-key conflict: query and reuse the existing row after verifying its identity.
- `412`: ETag/optimistic concurrency failure; reread and reconcile rather than overwriting blindly.
- `429` or transient `5xx`: honor retry behavior and server guidance. Ensure retrying the operation is idempotent.

## Bulk operations

For small demo datasets, sequential dependency-ordered requests are clearer and safer. For large loads, use `$batch` only after validating the same payloads individually. Group independent rows and retain enough identifiers to map responses to source records.

Do not hide partial success. Report created, reused, updated, failed, and verified counts separately.
