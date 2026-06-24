"""
Idempotent table deployer (framework_power).

``deploy_table`` reconciles a desired ``Table`` against the live Dataverse environment:
create-or-update the entity, create-or-PATCH each attribute (true sync of updatable
properties), and create-only relationships. It is never destructive (no deletes).

Delays + retry absorb Dataverse metadata propagation / lock contention per the
``dv-metadata`` skill. Each item is handled independently so one failure does not
abort the whole deploy; ``already exists`` is treated as a skip, making re-runs safe.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

from .models import Table
from .serializer import (
    build_attribute_patch,
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


def deploy_table(
    client: Any,
    table: Table,
    *,
    config: DeployConfig | None = None,
    prefix: str = "new",
) -> dict[str, Any]:
    """Deploy (create or sync) a ``Table`` to Dataverse.

    Standard/system columns and relationships (those without the publisher ``prefix``) are
    **skipped** — they are reference-only (e.g. from a reverse snapshot) and left to the
    environment. Only custom (prefixed) items are created/synced.

    Args:
        client: A ``DataverseClient`` (authenticated).
        table: The desired table definition.
        config: Optional :class:`DeployConfig` for delay/sleep tuning (tests inject
            zero-delay configs).
        prefix: Publisher prefix used to identify custom (deployable) components.

    Returns:
        A result dict with ``entity``/``attributes``/``relationships`` action summaries.
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

    entity_created = _deploy_entity(client, table, logical, cfg, result, prefix)
    _deploy_attributes(client, table, logical, entity_created, result, prefix)
    _deploy_relationships(client, table, logical, cfg, result, prefix)

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
        if optionset_changed(col, existing):
            result["attributes"].append({"attribute": col.schema_name, "action": "manual_update_required"})
            continue
        patch = build_attribute_patch(col, existing)
        result["attributes"].append(
            {
                "attribute": col.schema_name,
                "action": "would_patch" if patch else "would_skip",
                "fields": list(patch.keys()) if patch else [],
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
) -> bool:
    """Create the entity if missing, else PATCH updatable entity props. Returns entity_created."""
    if not client.entity_exists(logical):
        try:
            payload = serialize_table_for_create(table)
            # Fresh create only sends custom (prefixed) attributes; system ones are auto-created.
            payload["Attributes"] = [
                a for a in payload.get("Attributes", []) if _is_custom(a.get("SchemaName"), prefix)
            ]
            client.create_entity(payload)
            result["entity"] = {"action": "created"}
            cfg.sleep(cfg.after_entity_create_delay)  # propagation wait per dv-metadata
            return True
        except Exception as e:  # noqa: BLE001
            if _is_already_exists(e):
                result["entity"] = {"action": "already_exists"}
                return False
            result["entity"] = {"action": "failed", "error": str(e)}
            raise

    # Entity exists -> sync entity-level properties.
    try:
        client.update_entity(logical, serialize_entity_patch(table))
        result["entity"] = {"action": "updated"}
    except Exception as e:  # noqa: BLE001
        result["entity"] = {"action": "update_failed", "error": str(e)}
        logger.warning(f"Entity property sync failed for '{logical}': {e}")
    return False


def _deploy_attributes(
    client: Any,
    table: Table,
    logical: str,
    entity_created: bool,
    result: dict[str, Any],
    prefix: str,
) -> None:
    """Create missing attributes and PATCH changed updatable props (only when entity pre-existed)."""
    if entity_created:
        # Attributes rode along inside the entity create payload; nothing to sync.
        return

    try:
        existing_attrs = {a.get("LogicalName"): a for a in client.get_attributes(logical)}
    except Exception as e:  # noqa: BLE001
        result["attributes"].append({"action": "failed", "error": f"get_attributes: {e}"})
        return

    for col in table.columns:
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
            if optionset_changed(col, existing):
                entry["action"] = "manual_update_required"
                entry["reason"] = (
                    "OptionSet options cannot be PATCHed via the attribute endpoint; "
                    "update via maker portal or InsertOptionValue/UpdateOptionValue."
                )
                result["attributes"].append(entry)
                continue

            patch = build_attribute_patch(col, existing)
            if patch:
                try:
                    client.update_attribute_by_logical_name(logical, col_logical, patch)
                    entry["action"] = "updated"
                    entry["patch"] = list(patch.keys())
                except Exception as e:  # noqa: BLE001
                    entry["action"] = "update_failed"
                    entry["error"] = str(e)
            else:
                entry["action"] = "skipped"

        result["attributes"].append(entry)


def _deploy_relationships(
    client: Any,
    table: Table,
    logical: str,
    cfg: DeployConfig,
    result: dict[str, Any],
    prefix: str,
) -> None:
    """Create relationships (create-only; skip if already present or standard)."""
    if not table.relationships:
        return

    try:
        existing_rels = client.get_relationships(logical)
    except Exception as e:  # noqa: BLE001
        result["relationships"].append({"action": "failed", "error": f"get_relationships: {e}"})
        return

    existing_names = {r.get("SchemaName") for r in existing_rels}

    for rel in table.relationships:
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
