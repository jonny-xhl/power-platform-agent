"""
Idempotent table deployer (framework_power).

``deploy_table`` reconciles a desired ``Table`` against the live Dataverse environment:
create-or-update the entity, create-or-update each attribute (full-definition metadata
PUT for changed properties), and create-only relationships. It is never destructive.

Delays + retry absorb Dataverse metadata propagation / lock contention per the
``dv-metadata`` skill. Each item is handled independently so one failure does not
abort the whole deploy; ``already exists`` is treated as a skip, making re-runs safe.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .models import AttributeType, Column, Relationship, Table
from .serializer import (
    build_attribute_patch,
    build_picklist_option_diff,
    optionset_changed,
    serialize_column,
    serialize_entity_patch,
    serialize_relationship,
    serialize_table_for_create,
)

logger = logging.getLogger(__name__)


@dataclass
class DeployConfig:
    """Tunables for metadata propagation waits and the sleep primitive."""

    after_entity_create_delay: float = 5.0
    between_attributes_delay: float = 0.5
    between_relationships_delay: float = 3.0
    sleep: Callable[[float], None] = time.sleep


_ALREADY_EXISTS_MARKERS = ("already exists", "0x80040237", "cannot create duplicate", "duplicate")


def _is_already_exists(error: Exception) -> bool:
    msg = str(error).lower()
    return any(marker in msg for marker in _ALREADY_EXISTS_MARKERS)


def _is_custom(schema_name: str | None, prefix: str) -> bool:
    """True if ``schema_name`` carries the publisher prefix (project-owned / deployable)."""
    if not schema_name:
        return False
    return schema_name.lower().startswith(f"{prefix}_")


def _resolve_fields(table: Table, fields: list[str]) -> dict[str, Any]:
    """Resolve user-supplied field names to the actual Column / Relationship objects.

    A field name may refer to either a plain ``Column`` (in ``table.columns``) or a
    ``Relationship.lookup`` (a LookupColumn stored inside a relationship).  Both paths
    are checked independently so ``--fields new_LookupId`` behaves the same regardless
    of how the column is stored in the table model.

    Returns:
        ``{"regular": [Column, …], "lookups": [Relationship, …], "unknown": [str, …]}``.
        If ``unknown`` is non-empty the caller SHOULD bail before any API writes.
    """
    col_map: dict[str, Column] = {c.schema_name.lower(): c for c in table.columns}  # type: ignore[assignment]
    rel_map: dict[str, Relationship] = {}  # type: ignore[assignment]
    for rel in table.relationships:
        if rel.lookup:
            rel_map[rel.lookup.schema_name.lower()] = rel

    regular: list[Column] = []  # type: ignore[assignment]
    lookups: list[Relationship] = []  # type: ignore[assignment]
    unknown: list[str] = []

    for f in fields:
        key = f.strip().lower()
        if key in col_map:
            regular.append(col_map[key])
        elif key in rel_map:
            lookups.append(rel_map[key])
        else:
            unknown.append(f)

    return {"regular": regular, "lookups": lookups, "unknown": unknown}


def deploy_table(
    client: Any,
    table: Table,
    *,
    config: DeployConfig | None = None,
    prefix: str = "new",
    solution: str | None = None,
    solution_clean: bool = False,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    """Deploy (create or sync) a ``Table`` to Dataverse.

    Standard/system columns and relationships (those without the publisher ``prefix``) are
    **skipped** — they are reference-only (e.g. from a reverse snapshot) and left to the
    environment. Only custom (prefixed) items are created/synced.

    **Incremental mode** (``fields`` is not ``None``):
    Only the named fields are deployed. A field may be a plain column or a Lookup (resolved
    from both ``table.columns`` and ``table.relationships[].lookup``).  When the entity does
    not yet exist an *empty shell* entity is created first (no attributes) so that subsequent
    attribute/relationship creation works identically to the entity-already-exists path.

    Args:
        client: A ``DataverseClient`` (authenticated).
        table: The desired table definition.
        config: Optional :class:`DeployConfig` for delay/sleep tuning (tests inject
            zero-delay configs).
        prefix: Publisher prefix used to identify custom (deployable) components.
        solution: Optional solution unique name; when set, the entity is added to it (code 1,
            idempotent) after deploy — mirrors ``deploy_plugin(solution=…)``. Default ``None``
            preserves the legacy no-membership behavior.
        solution_clean: Membership MODE when ``solution`` is set. ``False`` (default, backward-
            compatible) adds the entity WITH sub-components (Dataverse default — drags in all OOB
            forms/views/fields). ``True`` adds the entity as a SHELL plus only its CUSTOM columns
            as individual attributes (code 2), so the solution holds only self-authored content
            (portable/regressable). Select per the solution portability principle.
        fields: Optional list of schema names to deploy incrementally.  When provided the
            entity-level sync (DisplayName, HasNotes, …) is skipped, other columns and
            relationships are left untouched, and only the named fields are deployed.

    Returns:
        A result dict with ``entity``/``attributes``/``relationships`` action summaries, plus an
        optional ``solution`` key when ``solution`` was given.
    """
    cfg = config or DeployConfig()
    logical = table.logical_name
    result: dict[str, Any] = {
        "schema_name": table.schema_name,
        "logical_name": logical,
        "entity": {},
        "attributes": [],
        "relationships": [],
    }

    # -- resolve incremental fields ------------------------------------------------
    resolved: dict[str, Any] | None = None
    if fields:
        resolved = _resolve_fields(table, fields)
        unknown = resolved["unknown"]
        if unknown:
            raise ValueError(
                f"Unknown field(s): {', '.join(unknown)}. "
                f"Available: {', '.join(c.schema_name for c in table.columns)}"
                + (
                    f", {', '.join(r.lookup.schema_name for r in table.relationships if r.lookup)}"
                    if any(r.lookup for r in table.relationships)
                    else ""
                )
            )

    # -- entity -------------------------------------------------------------------
    entity_created = _deploy_entity(
        client,
        table,
        logical,
        cfg,
        result,
        prefix,
        empty_shell=resolved is not None,
    )

    # -- attributes ----------------------------------------------------------------
    if resolved is not None:
        # Incremental: always run the attribute loop (even when entity was just
        # created as an empty shell).  The entity has no attributes yet.
        options_changed = _deploy_attributes(
            client,
            table,
            logical,
            False,
            result,
            prefix,
            columns=resolved["regular"],
            solution=solution,
        )
    else:
        options_changed = _deploy_attributes(
            client,
            table,
            logical,
            entity_created,
            result,
            prefix,
            solution=solution,
        )

    # -- relationships -------------------------------------------------------------
    if resolved is not None:
        _deploy_relationships(client, table, logical, cfg, result, prefix,
                              relationships=resolved["lookups"])
    else:
        _deploy_relationships(client, table, logical, cfg, result, prefix)

    # -- solution membership -------------------------------------------------------
    if solution:
        result["solution"] = _add_entity_to_solution(
            client, solution, logical, clean=solution_clean, table=table, prefix=prefix,
            field_names=fields,
        )

    # Option actions are separate metadata mutations. Publish only when at least one
    # InsertOptionValue/UpdateOptionValue succeeded; idempotent retries remain read-only.
    if options_changed:
        try:
            result["publish"] = client.publish_entity(logical)
        except Exception as e:  # noqa: BLE001
            result["publish"] = {"action": "failed", "error": str(e)}

    return result


def _add_entity_to_solution(
    client: Any,
    solution: str,
    logical: str,
    *,
    clean: bool = False,
    table: Optional[Table] = None,
    prefix: str = "new",
    field_names: list[str] | None = None,
) -> dict[str, Any]:
    """Add the entity (code 1) to ``solution`` (idempotent). Assumes the solution exists.

    ``clean=False`` (default) adds the entity WITH sub-components (Dataverse default — drags in
    every OOB form/view/field). ``clean=True`` adds the entity as a SHELL
    (``do_not_include_subcomponents``) plus only its CUSTOM columns as individual attributes
    (code 2), so the solution carries only self-authored content.

    When ``field_names`` is provided with ``clean=True``, only those named fields are added
    as individual solution members (code 2) instead of the full set of custom columns.
    """
    try:
        mid = client.get_entity_metadata(logical).get("MetadataId")
    except Exception as e:  # noqa: BLE001
        return {"name": solution, "action": "failed", "error": f"resolve MetadataId: {e}"}
    if not mid:
        return {"name": solution, "action": "skipped", "note": "no MetadataId (standard entity?)"}

    result: dict[str, Any] = {
        "name": solution,
        "object_id": mid,
        "mode": "clean" if clean else "subcomponents",
        "members": [],
    }
    try:
        client.add_solution_component(solution, 1, mid, do_not_include_subcomponents=clean)
        result["action"] = "added"
    except Exception as e:  # noqa: BLE001
        if _is_already_exists(e):
            result["action"] = "already_in_solution"
        else:
            result["action"] = "failed"
            result["error"] = str(e)
            return result

    # Clean mode: add only the self-authored (custom) attributes as individual members.
    if clean and table:
        try:
            attr_ids = {a.get("LogicalName"): a.get("MetadataId") for a in client.get_attributes(logical)}
        except Exception as e:  # noqa: BLE001
            result["members"].append({"action": "failed", "error": f"get_attributes: {e}"})
            return result
        # Custom attributes = plain columns + lookup columns from custom relationships.
        if field_names:
            # Incremental: only the requested fields.
            custom_attrs: list[str] = [f for f in field_names if _is_custom(f, prefix)]
        else:
            custom_attrs = [c.schema_name for c in table.columns if _is_custom(c.schema_name, prefix)]
            for rel in table.relationships:
                if rel.lookup and _is_custom(rel.lookup.schema_name, prefix):
                    custom_attrs.append(rel.lookup.schema_name)
        for schema in custom_attrs:
            aid = attr_ids.get(schema.lower())
            entry: dict[str, Any] = {"attribute": schema}
            if not aid:
                entry["action"] = "skipped"
                entry["note"] = "no MetadataId"
                result["members"].append(entry)
                continue
            try:
                client.add_solution_component(solution, 2, aid)
                entry["action"] = "added"
            except Exception as e:  # noqa: BLE001
                entry["action"] = "already_in_solution" if _is_already_exists(e) else "failed"
                if entry["action"] == "failed":
                    entry["error"] = str(e)
            result["members"].append(entry)
    return result


def plan_table(
    client: Any,
    table: Table,
    *,
    prefix: str = "new",
) -> dict[str, Any]:
    """Read-only dry run: compute what ``deploy_table`` would do, with NO API writes.

    Returns a plan dict using ``would_create`` / ``would_update`` / ``would_patch`` /
    ``would_skip`` / ``would_skip_standard`` / ``manual_update_required`` actions.
    Local Picklists include per-value insert/update and remote-only-retention details.
    Standard (non-prefixed) items report ``would_skip_standard``.
    """
    logical = table.logical_name
    result: dict[str, Any] = {
        "schema_name": table.schema_name,
        "logical_name": logical,
        "entity": {},
        "attributes": [],
        "relationships": [],
    }

    def col_action_create(col_schema: str) -> str:
        return "would_create" if _is_custom(col_schema, prefix) else "would_skip_standard"

    if not client.entity_exists(logical):
        # Fresh create: entity + inline attributes + relationships all created together.
        result["entity"] = {"action": "would_create"}
        for col in table.columns:
            result["attributes"].append(
                {"attribute": col.schema_name, "action": col_action_create(col.schema_name)}
            )
        for rel in table.relationships:
            result["relationships"].append(
                {"relationship": rel.schema_name, "action": col_action_create(rel.schema_name)}
            )
        return result

    result["entity"] = {
        "action": "would_update",
        "fields": list(serialize_entity_patch(table).keys()),
    }

    existing_attrs = {a.get("LogicalName"): a for a in client.get_attributes(logical)}
    for col in table.columns:
        if not _is_custom(col.schema_name, prefix):
            result["attributes"].append({"attribute": col.schema_name, "action": "would_skip_standard"})
            continue
        cl = col.schema_name.lower()
        if cl not in existing_attrs:
            result["attributes"].append({"attribute": col.schema_name, "action": "would_create"})
            continue
        existing = existing_attrs[cl]
        option_plan: dict[str, Any] | None = None
        if col.type == AttributeType.Picklist and not col.optionset_name:
            typed = client.get_attribute_metadata(
                logical,
                cl,
                attribute_type=AttributeType.Picklist.value,
            )
            option_diff = build_picklist_option_diff(col, typed)
            option_plan = {
                "insert": [item["value"] for item in option_diff["insert"]],
                "update": [item["value"] for item in option_diff["update"]],
                "remote_only_retained": option_diff["remote_only"],
            }
        elif optionset_changed(col, existing):
            result["attributes"].append(
                {"attribute": col.schema_name, "action": "manual_update_required"}
            )
            continue
        patch = build_attribute_patch(col, existing)
        has_option_changes = bool(
            option_plan and (option_plan["insert"] or option_plan["update"])
        )
        result["attributes"].append(
            {
                "attribute": col.schema_name,
                "action": (
                    "would_update"
                    if has_option_changes
                    else "would_patch"
                    if patch
                    else "would_skip"
                ),
                "fields": list(patch.keys()) if patch else [],
                **({"options": option_plan} if option_plan is not None else {}),
            }
        )

    existing_names = {r.get("SchemaName") for r in client.get_relationships(logical)}
    for rel in table.relationships:
        if not _is_custom(rel.schema_name, prefix):
            result["relationships"].append({"relationship": rel.schema_name, "action": "would_skip_standard"})
            continue
        action = "would_skip" if rel.schema_name in existing_names else "would_create"
        result["relationships"].append({"relationship": rel.schema_name, "action": action})

    return result


def _deploy_entity(
    client: Any,
    table: Table,
    logical: str,
    cfg: DeployConfig,
    result: dict[str, Any],
    prefix: str,
    *,
    empty_shell: bool = False,
) -> bool:
    """Create the entity if missing, else PATCH updatable entity props.

    When ``empty_shell=True`` (incremental deploy): create an entity body WITHOUT any
    attributes so that the calling code can deploy only the requested fields through
    the normal attribute/relationship paths — identical to the entity-already-exists
    code path.  Entity-level property sync (DisplayName, HasNotes, …) is also skipped;
    the entity shell carries only the schema name.
    """
    if not client.entity_exists(logical):
        try:
            payload = serialize_table_for_create(table)
            if empty_shell:
                # Strip all attributes — the caller will create only the requested fields.
                payload.pop("Attributes", None)
            else:
                # Fresh create only sends custom (prefixed) attributes; system ones are auto-created.
                payload["Attributes"] = [
                    a for a in payload.get("Attributes", []) if _is_custom(a.get("SchemaName"), prefix)
                ]
            client.create_entity(payload)
            result["entity"] = {
                "action": "created",
                **({"mode": "shell"} if empty_shell else {}),
            }
            cfg.sleep(cfg.after_entity_create_delay)  # propagation wait per dv-metadata
            return True
        except Exception as e:  # noqa: BLE001
            if _is_already_exists(e):
                result["entity"] = {"action": "already_exists"}
                return False
            result["entity"] = {"action": "failed", "error": str(e)}
            raise

    # Entity already exists.
    if empty_shell:
        result["entity"] = {"action": "already_exists"}
        return False

    # Entity exists -> sync entity-level properties.
    try:
        client.update_entity(logical, serialize_entity_patch(table))
        result["entity"] = {"action": "updated"}
    except Exception as e:  # noqa: BLE001
        msg = str(e).lower()
        # 0x80060888 "Operation not supported on EntityMetadata": some tenants/auths reject
        # entity-property PATCH via Web API while allowing create + attribute updates. The
        # entity already exists (and for a reverse snapshot its props already match), so
        # treat this as a benign skip rather than a hard failure.
        if "0x80060888" in msg or "operation not supported on entitymetadata" in msg:
            result["entity"] = {
                "action": "skipped",
                "note": "entity-property update not supported via Web API in this environment",
            }
        else:
            result["entity"] = {"action": "update_failed", "error": str(e)}
            logger.warning(f"Entity property sync failed for '{logical}': {e}")
    return False


def _deploy_attributes(
    client: Any,
    table: Table,
    logical: str,
    entity_created_or_result: Any,  # backwards-compat: bool | dict
    result: dict[str, Any],
    prefix: str,
    *,
    columns: list[Column] | None = None,  # type: ignore[valid-type]
    solution: str | None = None,
) -> bool:
    """Create missing attributes and safely update changed mutable properties.

    Existing attributes use Dataverse's retrieve-modify-PUT metadata contract; the
    client preserves the complete concrete type definition around the computed diff.
    Existing local Picklists additionally reconcile authored options through
    ``InsertOptionValue`` / ``UpdateOptionValue``. Remote-only values are retained.
    When ``columns`` is specified (incremental deploy) only those columns are processed
    and the ``entity_created`` skip is ignored — the entity may be a fresh empty shell.

    Returns ``True`` when at least one option action succeeded and targeted entity
    publication is required.
    """
    options_changed = False
    if columns is not None:
        # Incremental mode: always process the specified columns.
        pass
    elif isinstance(entity_created_or_result, bool) and entity_created_or_result:
        # Full mode: Attributes rode along inside the entity create payload.
        return False

    try:
        existing_attrs = {a.get("LogicalName"): a for a in client.get_attributes(logical)}
    except Exception as e:  # noqa: BLE001
        result["attributes"].append({"action": "failed", "error": f"get_attributes: {e}"})
        return False

    iter_cols = columns if columns is not None else table.columns
    for col in iter_cols:
        if not _is_custom(col.schema_name, prefix):
            # Standard/system column (e.g. from a reverse snapshot) -> reference-only, skip.
            result["attributes"].append(
                {"attribute": col.schema_name, "type": col.type.value, "action": "skipped_standard"}
            )
            continue
        col_logical = col.schema_name.lower()
        entry: dict[str, Any] = {"attribute": col.schema_name, "type": col.type.value}

        if col_logical not in existing_attrs:
            try:
                client.create_attribute(logical, serialize_column(col, is_primary_name=col.is_primary_name))
                entry["action"] = "created"
            except Exception as e:  # noqa: BLE001
                entry["action"] = "skipped" if _is_already_exists(e) else "failed"
                if entry["action"] == "failed":
                    entry["error"] = str(e)
        else:
            existing = existing_attrs[col_logical]
            option_results: list[dict[str, Any]] = []
            option_failed = False

            if col.type == AttributeType.Picklist and not col.optionset_name:
                try:
                    typed = client.get_attribute_metadata(
                        logical,
                        col_logical,
                        attribute_type=AttributeType.Picklist.value,
                    )
                    option_diff = build_picklist_option_diff(col, typed)
                    for item in option_diff["insert"]:
                        option_entry = {"value": item["value"], "action": "inserted"}
                        try:
                            client.insert_option_value(
                                logical,
                                col_logical,
                                item["value"],
                                item["label"],
                                solution=solution,
                            )
                            options_changed = True
                        except Exception as e:  # noqa: BLE001
                            if _is_already_exists(e):
                                # A previous timed-out/retried action may already have committed.
                                option_entry["action"] = "already_exists"
                                options_changed = True
                            else:
                                option_entry["action"] = "failed"
                                option_entry["error"] = str(e)
                                option_failed = True
                        option_results.append(option_entry)
                    for item in option_diff["update"]:
                        option_entry = {
                            "value": item["value"],
                            "action": "updated",
                            "languages": item["languages"],
                        }
                        try:
                            client.update_option_value(
                                logical,
                                col_logical,
                                item["value"],
                                item["label"],
                                solution=solution,
                            )
                            options_changed = True
                        except Exception as e:  # noqa: BLE001
                            option_entry["action"] = "failed"
                            option_entry["error"] = str(e)
                            option_failed = True
                        option_results.append(option_entry)
                    option_results.extend(
                        {"value": value, "action": "skipped"}
                        for value in option_diff["unchanged"]
                    )
                    if option_diff["remote_only"]:
                        entry["remote_only_options_retained"] = option_diff["remote_only"]
                except Exception as e:  # noqa: BLE001
                    option_failed = True
                    entry["option_error"] = str(e)
            elif optionset_changed(col, existing):
                entry["action"] = "manual_update_required"
                entry["reason"] = (
                    "Boolean OptionSet label changes require an option-specific workflow."
                )
                result["attributes"].append(entry)
                continue

            patch = build_attribute_patch(col, existing)
            patch_updated = False
            patch_failed = False
            if patch:
                try:
                    client.update_attribute_by_logical_name(
                        logical,
                        col_logical,
                        patch,
                        attribute_type=col.type.value,
                        solution=solution,
                    )
                    patch_updated = True
                    entry["patch"] = list(patch.keys())
                except Exception as e:  # noqa: BLE001
                    patch_failed = True
                    entry["error"] = str(e)

            if option_results:
                entry["options"] = option_results
            has_option_mutation = any(
                item["action"] in {"inserted", "updated", "already_exists"}
                for item in option_results
            )
            if option_failed or patch_failed:
                entry["action"] = (
                    "partial_failed" if (patch_updated or has_option_mutation) else "failed"
                )
            elif patch_updated or has_option_mutation:
                entry["action"] = "updated"
            else:
                entry["action"] = "skipped"

        result["attributes"].append(entry)

    return options_changed


def _deploy_relationships(
    client: Any,
    table: Table,
    logical: str,
    cfg: DeployConfig,
    result: dict[str, Any],
    prefix: str,
    *,
    relationships: list[Relationship] | None = None,  # type: ignore[valid-type]
) -> None:
    """Create relationships (create-only; skip if already present or standard).

    When ``relationships`` is specified (incremental deploy) only those relationships
    are processed.
    """
    iter_rels = relationships if relationships is not None else table.relationships
    if not iter_rels:
        return

    try:
        existing_rels = client.get_relationships(logical)
    except Exception as e:  # noqa: BLE001
        result["relationships"].append({"action": "failed", "error": f"get_relationships: {e}"})
        return

    existing_names = {r.get("SchemaName") for r in existing_rels}

    for rel in iter_rels:
        entry: dict[str, Any] = {"relationship": rel.schema_name, "type": rel.type}

        if not _is_custom(rel.schema_name, prefix):
            # Standard/system relationship -> reference-only, skip.
            entry["action"] = "skipped_standard"
            result["relationships"].append(entry)
            continue

        if rel.schema_name in existing_names:
            entry["action"] = "skipped"
            result["relationships"].append(entry)
            continue

        referenced = rel.referenced_entity
        if referenced and not client.entity_exists(referenced):
            entry["action"] = "failed"
            entry["error"] = f"Referenced entity '{referenced}' does not exist; create it first."
            result["relationships"].append(entry)
            continue

        referenced_attribute = None
        if rel.type != "ManyToMany" and referenced:
            try:
                meta = client.get_entity_metadata(referenced)
                referenced_attribute = meta.get("PrimaryIdAttribute")
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Could not resolve PrimaryIdAttribute for '{referenced}': {e}")

        payload = serialize_relationship(rel, referenced_attribute=referenced_attribute)
        try:
            client.create_relationship_from_json(payload)
            entry["action"] = "created"
            cfg.sleep(cfg.between_relationships_delay)  # spaced to avoid lock contention
        except Exception as e:  # noqa: BLE001
            entry["action"] = "skipped" if _is_already_exists(e) else "failed"
            if entry["action"] == "failed":
                entry["error"] = str(e)

        result["relationships"].append(entry)
