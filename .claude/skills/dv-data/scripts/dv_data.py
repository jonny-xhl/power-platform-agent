#!/usr/bin/env python
"""Guarded Dataverse row-data discovery and CRUD helper."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple


def find_repository_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "framework_power" / "runtime.py").is_file():
            return candidate
    raise RuntimeError("Cannot locate the repository root containing framework_power")


REPOSITORY_ROOT = find_repository_root(Path(__file__).resolve().parent)
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def get_client(environment: str) -> Any:
    try:
        from framework_power.runtime import get_client as runtime_get_client
    except ModuleNotFoundError as error:
        raise RuntimeError(
            f"Missing project dependency {error.name!r}; install requirements.txt "
            "in the Python environment used to run this command"
        ) from error
    return runtime_get_client(environment)

GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def normalize_guid(value: str) -> str:
    candidate = value.strip().strip("{}")
    if not GUID_RE.fullmatch(candidate):
        raise ValueError(f"Invalid Dataverse row GUID: {value!r}")
    return candidate.lower()


def load_payload(path: str) -> Dict[str, Any]:
    payload_path = Path(path)
    with payload_path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("Payload file must contain one JSON object")
    return value


def request_json(response: Any, operation: str) -> Dict[str, Any]:
    if not response.ok:
        raise RuntimeError(
            f"{operation} failed: HTTP {response.status_code}: {response.text}"
        )
    if not response.content:
        return {}
    value = response.json()
    if not isinstance(value, dict):
        raise RuntimeError(f"{operation} returned a non-object JSON response")
    return value


def entity_context(client: Any, table: str) -> Dict[str, Any]:
    entity = client.get_entity_metadata(table)
    required = ("LogicalName", "EntitySetName", "PrimaryIdAttribute")
    missing = [name for name in required if not entity.get(name)]
    if missing:
        raise RuntimeError(
            f"Entity metadata for {table!r} is missing: {', '.join(missing)}"
        )
    return entity


def option_label(option: Mapping[str, Any]) -> Optional[str]:
    label = option.get("Label") or {}
    user_label = label.get("UserLocalizedLabel") or {}
    if user_label.get("Label"):
        return str(user_label["Label"])
    localized = label.get("LocalizedLabels") or []
    if localized and localized[0].get("Label"):
        return str(localized[0]["Label"])
    return None


def choice_values(option_metadata: Mapping[str, Any]) -> List[Dict[str, Any]]:
    option_set = option_metadata.get("OptionSet") or {}
    options = option_set.get("Options") or []
    result = []
    for option in options:
        if "Value" in option:
            result.append({"value": option.get("Value"), "label": option_label(option)})
    for name in ("TrueOption", "FalseOption"):
        option = option_set.get(name)
        if option and "Value" in option:
            result.append({"value": option.get("Value"), "label": option_label(option)})
    return result


def metadata_snapshot(client: Any, table: str) -> Dict[str, Any]:
    entity = entity_context(client, table)
    attributes = client.get_attributes(table)
    options = client.get_optionset_attributes(table)
    relationships = client.get_relationships(table)

    writable = []
    for attribute in attributes:
        if not (attribute.get("IsValidForCreate") or attribute.get("IsValidForUpdate")):
            continue
        logical_name = attribute.get("LogicalName")
        item = {
            "logical_name": logical_name,
            "schema_name": attribute.get("SchemaName"),
            "type": attribute.get("AttributeType"),
            "required_level": (attribute.get("RequiredLevel") or {}).get("Value"),
            "valid_for_create": attribute.get("IsValidForCreate"),
            "valid_for_update": attribute.get("IsValidForUpdate"),
            "max_length": attribute.get("MaxLength"),
            "precision": attribute.get("Precision"),
            "targets": attribute.get("Targets"),
        }
        if logical_name in options:
            item["choices"] = choice_values(options[logical_name])
        writable.append(item)

    lookup_relationships = []
    for relationship in relationships:
        if relationship.get("ReferencingEntity") != entity["LogicalName"]:
            continue
        navigation = relationship.get("ReferencingEntityNavigationPropertyName")
        attribute = relationship.get("ReferencingAttribute")
        referenced = relationship.get("ReferencedEntity")
        if not navigation or not attribute or not referenced:
            continue
        referenced_metadata = entity_context(client, referenced)
        lookup_relationships.append(
            {
                "referencing_attribute": attribute,
                "navigation_property": navigation,
                "referenced_table": referenced,
                "referenced_entity_set": referenced_metadata["EntitySetName"],
                "referenced_primary_id": referenced_metadata["PrimaryIdAttribute"],
                "referenced_primary_name": referenced_metadata.get("PrimaryNameAttribute"),
            }
        )

    return {
        "entity": {
            "logical_name": entity["LogicalName"],
            "schema_name": entity.get("SchemaName"),
            "entity_set": entity["EntitySetName"],
            "primary_id": entity["PrimaryIdAttribute"],
            "primary_name": entity.get("PrimaryNameAttribute"),
        },
        "writable_attributes": sorted(
            writable, key=lambda item: str(item.get("logical_name") or "")
        ),
        "lookup_relationships": sorted(
            lookup_relationships,
            key=lambda item: str(item.get("navigation_property") or ""),
        ),
    }


def metadata_maps(
    client: Any, table: str
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]], Set[str], Dict[str, Set[Any]]]:
    entity = entity_context(client, table)
    attributes = {
        attribute["LogicalName"]: attribute
        for attribute in client.get_attributes(table)
        if attribute.get("LogicalName")
    }
    navigation_properties = {
        relationship["ReferencingEntityNavigationPropertyName"]
        for relationship in client.get_relationships(table)
        if relationship.get("ReferencingEntity") == entity["LogicalName"]
        and relationship.get("ReferencingEntityNavigationPropertyName")
    }
    option_metadata = client.get_optionset_attributes(table)
    allowed_choices = {
        logical_name: {item["value"] for item in choice_values(metadata)}
        for logical_name, metadata in option_metadata.items()
    }
    return entity, attributes, navigation_properties, allowed_choices


def validate_payload(
    client: Any, table: str, payload: Mapping[str, Any], operation: str
) -> Dict[str, Any]:
    entity, attributes, navigation_properties, allowed_choices = metadata_maps(
        client, table
    )
    errors = []

    for key, value in payload.items():
        if key.endswith("@odata.bind"):
            navigation = key[: -len("@odata.bind")]
            if navigation not in navigation_properties:
                errors.append(f"Unknown Lookup navigation property: {navigation}")
            if value is not None and not isinstance(value, str):
                errors.append(f"Lookup binding {key} must be a string or null")
            continue

        attribute = attributes.get(key)
        if attribute is None:
            errors.append(f"Unknown attribute: {key}")
            continue
        valid_flag = (
            attribute.get("IsValidForCreate")
            if operation == "create"
            else attribute.get("IsValidForUpdate")
        )
        if not valid_flag:
            errors.append(f"Attribute {key} is not valid for {operation}")
        if key in allowed_choices and value is not None:
            if value not in allowed_choices[key]:
                values = sorted(allowed_choices[key], key=lambda item: str(item))
                errors.append(f"Invalid Choice value for {key}: {value!r}; allowed: {values}")

    if errors:
        raise ValueError("Payload validation failed:\n- " + "\n- ".join(errors))
    return entity


def write_headers(bypass_plugins: bool, representation: bool = False) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if representation:
        headers["Prefer"] = "return=representation"
    if bypass_plugins:
        headers["MSCRM.BypassCustomPluginExecution"] = "true"
    return headers


def selected_fields(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    fields = [item.strip() for item in value.split(",") if item.strip()]
    return ",".join(fields) or None


def query_rows(
    client: Any,
    entity_set: str,
    select: Optional[str] = None,
    filter_expression: Optional[str] = None,
    order_by: Optional[str] = None,
    top: int = 20,
) -> List[Dict[str, Any]]:
    params: Dict[str, str] = {"$top": str(top)}
    if select:
        params["$select"] = select
    if filter_expression:
        params["$filter"] = filter_expression
    if order_by:
        params["$orderby"] = order_by
    response = client.session.get(client.get_api_url(entity_set), params=params)
    body = request_json(response, f"Query {entity_set}")
    rows = body.get("value", [])
    if not isinstance(rows, list):
        raise RuntimeError("Dataverse query response has no value array")
    return rows


def get_row(client: Any, entity_set: str, row_id: str) -> Dict[str, Any]:
    response = client.session.get(client.get_api_url(f"{entity_set}({row_id})"))
    return request_json(response, f"Read {entity_set}({row_id})")


def odata_literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if value is None:
        return "null"
    return "'" + str(value).replace("'", "''") + "'"


def id_from_create(response: Any, row: Mapping[str, Any], primary_id: str) -> str:
    if row.get(primary_id):
        return normalize_guid(str(row[primary_id]))
    entity_id = response.headers.get("OData-EntityId", "")
    match = re.search(r"\(([0-9a-fA-F-]{36})\)$", entity_id)
    if match:
        return normalize_guid(match.group(1))
    raise RuntimeError("Create succeeded but Dataverse returned no row GUID")


def dry_run(action: str, args: argparse.Namespace, details: Mapping[str, Any]) -> int:
    print_json(
        {
            "status": "dry-run",
            "action": action,
            "environment": args.env,
            "table": args.table,
            "bypass_plugins": bool(getattr(args, "bypass_plugins", False)),
            "details": details,
            "next_step": "Review the target and rerun with --execute to write.",
        }
    )
    return 0


def command_metadata(args: argparse.Namespace) -> int:
    client = get_client(args.env)
    print_json(metadata_snapshot(client, args.table))
    return 0


def command_query(args: argparse.Namespace) -> int:
    client = get_client(args.env)
    entity = entity_context(client, args.table)
    rows = query_rows(
        client,
        entity["EntitySetName"],
        selected_fields(args.select),
        args.filter,
        args.order_by,
        args.top,
    )
    print_json({"count": len(rows), "rows": rows})
    return 0


def command_create(args: argparse.Namespace) -> int:
    client = get_client(args.env)
    payload = load_payload(args.payload)
    entity = validate_payload(client, args.table, payload, "create")
    if not args.execute:
        return dry_run("create", args, {"payload": payload})

    response = client.session.post(
        client.get_api_url(entity["EntitySetName"]),
        json=payload,
        headers=write_headers(args.bypass_plugins, representation=True),
    )
    row = request_json(response, f"Create {entity['EntitySetName']}")
    row_id = id_from_create(response, row, entity["PrimaryIdAttribute"])
    verified = get_row(client, entity["EntitySetName"], row_id)
    print_json({"status": "created", "id": row_id, "verified_row": verified})
    return 0


def command_upsert(args: argparse.Namespace) -> int:
    client = get_client(args.env)
    payload = load_payload(args.payload)
    entity = validate_payload(client, args.table, payload, "create")
    if args.key_field not in payload:
        raise ValueError(f"Payload does not contain key field {args.key_field!r}")
    key_value = payload[args.key_field]
    rows = query_rows(
        client,
        entity["EntitySetName"],
        filter_expression=f"{args.key_field} eq {odata_literal(key_value)}",
        top=2,
    )
    if len(rows) > 1:
        raise RuntimeError(
            f"Natural key is not unique: {args.key_field}={key_value!r} matched {len(rows)} rows"
        )
    if rows:
        print_json({"status": "reused", "row": rows[0]})
        return 0
    if not args.execute:
        return dry_run(
            "upsert-create",
            args,
            {"key_field": args.key_field, "key_value": key_value, "payload": payload},
        )

    response = client.session.post(
        client.get_api_url(entity["EntitySetName"]),
        json=payload,
        headers=write_headers(args.bypass_plugins, representation=True),
    )
    row = request_json(response, f"Create {entity['EntitySetName']}")
    row_id = id_from_create(response, row, entity["PrimaryIdAttribute"])
    verified = get_row(client, entity["EntitySetName"], row_id)
    print_json({"status": "created", "id": row_id, "verified_row": verified})
    return 0


def command_update(args: argparse.Namespace) -> int:
    client = get_client(args.env)
    row_id = normalize_guid(args.id)
    payload = load_payload(args.payload)
    entity = validate_payload(client, args.table, payload, "update")
    if not args.execute:
        return dry_run("update", args, {"id": row_id, "payload": payload})

    response = client.session.patch(
        client.get_api_url(f"{entity['EntitySetName']}({row_id})"),
        json=payload,
        headers=write_headers(args.bypass_plugins),
    )
    if not response.ok:
        raise RuntimeError(
            f"Update {entity['EntitySetName']}({row_id}) failed: "
            f"HTTP {response.status_code}: {response.text}"
        )
    verified = get_row(client, entity["EntitySetName"], row_id)
    print_json({"status": "updated", "id": row_id, "verified_row": verified})
    return 0


def command_delete(args: argparse.Namespace) -> int:
    client = get_client(args.env)
    row_id = normalize_guid(args.id)
    confirmation = normalize_guid(args.confirm_delete)
    if confirmation != row_id:
        raise ValueError("--confirm-delete must exactly match --id")
    entity = entity_context(client, args.table)
    current = get_row(client, entity["EntitySetName"], row_id)
    if not args.execute:
        return dry_run("delete", args, {"id": row_id, "current_row": current})

    response = client.session.delete(
        client.get_api_url(f"{entity['EntitySetName']}({row_id})"),
        headers=write_headers(args.bypass_plugins),
    )
    if not response.ok:
        raise RuntimeError(
            f"Delete {entity['EntitySetName']}({row_id}) failed: "
            f"HTTP {response.status_code}: {response.text}"
        )
    verify = client.session.get(
        client.get_api_url(f"{entity['EntitySetName']}({row_id})")
    )
    if verify.status_code != 404:
        raise RuntimeError(
            f"Delete verification failed: expected HTTP 404, got {verify.status_code}"
        )
    print_json({"status": "deleted", "id": row_id, "verified_absent": True})
    return 0


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--env", default="dev", help="Configured environment name")
    parser.add_argument("--table", required=True, help="Table logical name")


def add_write_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--bypass-plugins",
        action="store_true",
        help="Send MSCRM.BypassCustomPluginExecution=true; never silently falls back",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the mutation after reviewing the command; otherwise dry-run",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Metadata-first Dataverse row discovery and guarded CRUD"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    metadata = subparsers.add_parser("metadata", help="Show writable fields, Choices, and Lookups")
    add_common(metadata)
    metadata.set_defaults(handler=command_metadata)

    query = subparsers.add_parser("query", help="Query table rows")
    add_common(query)
    query.add_argument("--select", help="Comma-separated logical field names")
    query.add_argument("--filter", help="OData filter expression")
    query.add_argument("--order-by", help="OData order-by expression")
    query.add_argument("--top", type=int, default=20, choices=range(1, 501))
    query.set_defaults(handler=command_query)

    create = subparsers.add_parser("create", help="Validate and create one row")
    add_common(create)
    create.add_argument("--payload", required=True, help="Path to a JSON object")
    add_write_options(create)
    create.set_defaults(handler=command_create)

    upsert = subparsers.add_parser("upsert", help="Create or reuse one row by natural key")
    add_common(upsert)
    upsert.add_argument("--payload", required=True, help="Path to a JSON object")
    upsert.add_argument("--key-field", required=True, help="Stable logical field in the payload")
    add_write_options(upsert)
    upsert.set_defaults(handler=command_upsert)

    update = subparsers.add_parser("update", help="Validate and update one row by GUID")
    add_common(update)
    update.add_argument("--id", required=True, help="Dataverse row GUID")
    update.add_argument("--payload", required=True, help="Path to a JSON object")
    add_write_options(update)
    update.set_defaults(handler=command_update)

    delete = subparsers.add_parser("delete", help="Delete one reviewed row by GUID")
    add_common(delete)
    delete.add_argument("--id", required=True, help="Dataverse row GUID")
    delete.add_argument(
        "--confirm-delete",
        required=True,
        help="Repeat the same GUID after explicit user confirmation",
    )
    add_write_options(delete)
    delete.set_defaults(handler=command_delete)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
