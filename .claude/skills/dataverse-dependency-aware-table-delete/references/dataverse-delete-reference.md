# Dataverse Delete Reference

## Component Types

| Component | Code | Use |
|---|---:|---|
| Entity/Table | 1 | `RetrieveDependenciesForDelete` before table deletion |
| Attribute | 2 | Dependency check before deleting an individual field |
| Entity Relationship | 10 | Dependency check before deleting a Lookup relationship |
| View/SavedQuery | 26 | Solution component identification |
| Form/SystemForm | 60 | Solution component identification |
| Web Resource | 61 | Solution component identification |

## Endpoint Patterns

### Table metadata

```text
GET EntityDefinitions(LogicalName='<logical-name>')
DELETE EntityDefinitions(<table-MetadataId>)
```

### Attribute metadata

```text
GET EntityDefinitions(LogicalName='<table>')/Attributes(LogicalName='<field>')
DELETE EntityDefinitions(LogicalName='<table>')/Attributes(LogicalName='<field>')
```

### Relationship metadata

Query through the entity navigation collection:

```text
GET EntityDefinitions(<table-MetadataId>)/ManyToOneRelationships
```

Delete through the top-level collection:

```text
DELETE RelationshipDefinitions(<relationship-MetadataId>)
```

The navigation collection is not contained. DELETE through it produces:

```text
HTTP 405
Delete on Navigation Property is only supported on Contained Metadata Entities.
```

### Native deletion dependency check

```text
GET RetrieveDependenciesForDelete(ObjectId=<MetadataId>,ComponentType=<code>)
```

Interpret `value: []` as no native blockers. Preserve the complete response as evidence.

### Solution membership

```text
GET solutioncomponents?$filter=_solutionid_value eq <solutionid>&$select=componenttype,objectid
```

Use `objectid` plus `componenttype` as the membership key. Do not DELETE `solutioncomponents` records directly.

### Solution export

```text
POST ExportSolution
{
  "SolutionName": "<unique-name>",
  "Managed": false
}
```

Decode `ExportSolutionFile` from base64 and persist the ZIP before destructive metadata changes.

## Verified Ninebot Example

Retired tables:

```text
new_targetversion
new_budgetbaseline
new_forecastversion
```

Initial live state:

| Table | Records | Native dependencies |
|---|---:|---:|
| `new_targetversion` | 3 | 0 |
| `new_budgetbaseline` | 8 | 0 |
| `new_forecastversion` | 2 | 1 |

Blocking graph:

```text
new_rollingforecast.new_versionid
  -> new_RollingForecast_ForecastVersion
  -> new_forecastversion
```

The incoming Lookup was non-null on 13 rolling forecast records. Back up these records before removing the relationship.

Verified safe order:

```text
new_targetversion
-> new_budgetbaseline
-> deploy clean rolling forecast form/Web Resource/source
-> delete new_RollingForecast_ForecastVersion
-> publish new_rollingforecast
-> confirm new_forecastversion dependency count = 0
-> delete new_forecastversion
```

Final verification:

```text
new_targetversion: EntityDefinitions HTTP 404
new_budgetbaseline: EntityDefinitions HTTP 404
new_forecastversion: EntityDefinitions HTTP 404
new_rollingforecast.new_versionid: Attribute HTTP 404
new_RollingForecast_ForecastVersion: zero relationship rows
all three entity MetadataIds absent from new_entity930 component type 1 membership
```

## Failure Modes and Corrections

### Non-transactional partial commit

Symptom: the first table is deleted, a later operation fails, and retry receives HTTP 404 for the first table.

Correction: implement `404 -> already_deleted -> continue`. Query live state before every step.

### Report written only at the end

Symptom: mutations succeed but an exception prevents the execution report from being written.

Correction: persist checkpoints after each mutation or reconstruct the audit trail from current state and backups.

### Relationship DELETE via navigation property

Symptom: HTTP 405.

Correction: delete through `RelationshipDefinitions(<MetadataId>)`.

### UI deployed after metadata deletion

Symptom: form deployment or Web Resource queries fail because they still reference the missing field.

Correction: deploy and publish cleaned dependents before deleting the relationship or attribute.

### Source repository recreates deleted metadata

Symptom: a later full deployment adds the deleted table or Lookup again.

Correction: remove authored definitions, manifests, plugins, tests, and generated docs after live deletion succeeds.

### Wrong dictionary output root

Symptom: generated files appear under `docs/data_dictionary/tables/tables/` and deleted definitions appear to return.

Correction: pass `docs/data_dictionary` as the generator output root, not `docs/data_dictionary/tables`.
