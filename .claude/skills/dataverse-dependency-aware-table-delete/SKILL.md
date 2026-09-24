---
name: dataverse-dependency-aware-table-delete
description: This skill should be used when permanently deleting one or more Dataverse tables from an environment and unmanaged solution, especially when Lookup relationships, forms, views, Web Resources, plugins, historical records, or retry after partial failure must be handled safely.
agent_created: true
---

# Dataverse Dependency-Aware Table Delete

## Purpose

Delete Dataverse tables without orphaning component references or losing the ability to recover. Treat table deletion as a non-transactional, dependency-ordered workflow rather than a single DELETE request.

## Safety Contract

Enforce all gates before destructive mutation:

1. Confirm target environment, solution unique name, and exact logical table names.
2. Search workspace and business source for table, relationship, Lookup, OData, form, view, plugin, workflow, and documentation references.
3. Query live MetadataIds, entity sets, record counts, relationships, solution membership, forms, views, and relevant Web Resources.
4. Call `RetrieveDependenciesForDelete` with component type `1` for each table.
5. Back up records, entity/attribute/relationship metadata, forms, views, Web Resources, solution components, and an unmanaged solution ZIP.
6. Stop when a required backup is missing or empty.
7. Remove incoming business dependencies before deleting referenced tables.
8. Re-run native dependency checks immediately before every delete.
9. Execute in reverse topological order: referencing leaves before referenced roots.
10. Verify HTTP 404, absence from solution membership, and removal of stale source definitions.

Never infer success from a previous command's exit status alone. Read the actual Dataverse state after every mutation.

## Workflow

### 1. Discover the Dependency Graph

Map edges as:

```text
referencing component --depends on--> required component
```

Include both metadata and runtime references:

- `relationships[].lookup` definitions;
- `new_<lookup>@odata.bind` writes;
- `_<lookup>_value` reads;
- form controls and view columns/FetchXml;
- Web Resources and tests;
- C# Plugins, Custom Actions, Jobs, and API queries;
- workflow/project manifests;
- feature documents and generated data dictionaries;
- app modules, dashboards, charts, business process flows, plugin steps, and solution components where applicable.

Derive a topological order, then reverse it for deletion. Do not use the order in the user request unless the graph proves it safe.

### 2. Audit Live State

For each table:

- retrieve `EntityDefinitions(LogicalName='<logical>')`;
- record `MetadataId`, `EntitySetName`, `PrimaryIdAttribute`, `IsManaged`, and record count;
- list `OneToManyRelationships`, `ManyToOneRelationships`, and `ManyToManyRelationships`;
- record solution membership from `solutioncomponents` with component type `1`;
- call:

```text
GET RetrieveDependenciesForDelete(ObjectId=<MetadataId>,ComponentType=1)
```

For each incoming Lookup, count non-null values and back up the referencing record IDs plus raw and formatted Lookup values.

Treat system-generated relationships as part of the table unless `RetrieveDependenciesForDelete` reports them as external blockers. Prioritize published custom dependencies returned by the native API.

### 3. Create Recovery Backups

Store backups under a dated `.pp-local/<operation>/` directory:

```text
records/<table>.json
metadata/<table>.entity.json
metadata/<table>.attributes.json
metadata/<table>.relationships.json
components/<table>.forms.json
components/<table>.views.json
components/<webresource>.json
solution/components.json
solution/<solution>.zip
local-source/
business-source/
manifest.json
```

Export the unmanaged solution before changing membership or metadata. Preserve local and business-source files that will be edited or deleted.

### 4. Remove External References

Apply dependency changes outside-in:

1. remove UI controls, view columns, Web Resource reads/writes, plugin mappings, and workflow references;
2. deploy and publish the updated components;
3. verify the remote form XML and Web Resource content no longer contain the Lookup logical name;
4. call `RetrieveDependenciesForDelete` for the relationship with component type `10`;
5. delete the relationship only when its dependency list is empty;
6. publish the referencing entity;
7. re-check the referenced table's delete dependencies.

Delete relationship metadata through the top-level endpoint:

```text
DELETE RelationshipDefinitions(<relationship-MetadataId>)
```

Do not DELETE through:

```text
EntityDefinitions(<id>)/ManyToOneRelationships(<relationship-id>)
```

That navigation property can be queried but is not a contained metadata collection; DELETE returns HTTP 405.

### 5. Delete Tables

For each table in reverse topological order:

1. query current state directly;
2. treat HTTP 404 as `already_deleted`;
3. retrieve the latest MetadataId when the table exists;
4. require a zero-length `RetrieveDependenciesForDelete` response;
5. call the explicit table delete operation;
6. publish affected surviving entities as needed;
7. persist step evidence before advancing where practical.

Deleting an unmanaged table removes the table and its solution membership. Removing a component from an unmanaged solution alone does not delete the table from the environment.

### 6. Recover from Partial Failure

Implement the executor as a state machine:

```text
exists + zero dependencies -> delete
404 -> already_deleted -> continue
exists + dependencies -> stop and report
relationship absent -> already_removed -> continue
```

Expect partial commits because Dataverse metadata operations are separate Web API requests. On retry, inspect current state rather than replaying assumptions.

Persist progress after each successful mutation or reconstruct it from the environment before continuing. A script that performs multiple deletes but writes its report only at the end is insufficient.

### 7. Clean Source and Documentation

After live deletion succeeds:

- remove retired table definitions;
- remove their authored forms and views;
- remove relationship definitions from surviving tables;
- remove plugin/action and Web Resource references;
- update solution manifests and comments;
- remove generated table and local optionset documents;
- regenerate the data dictionary from the correct output root;
- remove stale `__pycache__` files that contain retired component names;
- keep a retirement record in feature documentation.

Verify that no executable source contains the retired table or Lookup names. Historical documentation may retain the names when clearly marked as deleted.

### 8. Verify Completion

Require all of the following:

- each target `EntityDefinitions(LogicalName='...')` returns HTTP 404;
- each removed Lookup attribute returns HTTP 404;
- removed custom relationship queries return zero rows;
- target MetadataIds are absent from solution component type `1` membership;
- surviving forms and Web Resources contain no retired field reference;
- workspace definitions cannot recreate deleted tables;
- data dictionary excludes deleted tables and relationships;
- applicable tests and linters pass.

Record the deletion order, dependency counts, record counts, backup path, failures encountered, recovery behavior, and final verification in the completion report.

## Component Type Reference

Read `references/dataverse-delete-reference.md` for endpoint forms, component type codes, failure modes, and the verified Ninebot example.
