"""
Offline convention linter (framework_power).

Validates table definitions *without any network access* so the AI-generated
metadata is constrained before it ever reaches ``plan``/``deploy``. This replaces
the YAML path's JSON-Schema + naming_rules auto-conversion with an explicit,
author-responsible contract: names are validated (not silently rewritten).

Severity model:
- ``error``   blocks deploy (structural problems).
- ``warning`` non-blocking convention drift (e.g. naming style, label coverage).
- ``info``    advisory notes (e.g. auto-picked primary name).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import AttributeType, Relationship, Table
from .registry import Definition

# A minimal set of protected standard entity logical names (no publisher prefix).
STANDARD_ENTITIES = {
    "account", "contact", "systemuser", "team", "businessunit", "transactioncurrency",
    "lead", "opportunity", "systemuser", "queue", "post", "annotation",
}

ERROR = "error"
WARNING = "warning"
INFO = "info"


@dataclass(frozen=True)
class Issue:
    severity: str
    message: str

    @property
    def is_error(self) -> bool:
        return self.severity == ERROR


def _is_custom(name: str, prefix: str) -> bool:
    return name.lower().startswith(f"{prefix}_")


def _after_prefix(name: str, prefix: str) -> str:
    return name[len(prefix) + 1:] if _is_custom(name, prefix) else name


def _is_lowercase_style(name: str, prefix: str) -> bool:
    """True if a custom name uses legacy lowercase_with_underscore style."""
    remainder = _after_prefix(name, prefix)
    return bool(remainder) and remainder == remainder.lower() and "_" in remainder


def lint_table(table: Table, prefix: str = "new") -> list[Issue]:
    """Run offline convention checks on a single table definition."""
    issues: list[Issue] = []
    logical = table.logical_name

    # --- entity naming ---
    if not _is_custom(table.schema_name, prefix) and logical not in STANDARD_ENTITIES:
        issues.append(Issue(WARNING, f"Entity '{table.schema_name}' does not start with prefix '{prefix}_'."))
    if _is_custom(table.schema_name, prefix) and _is_lowercase_style(table.schema_name, prefix):
        issues.append(
            Issue(WARNING, f"Entity '{table.schema_name}' is lowercase; new tables should be PascalCase.")
        )

    # --- columns ---
    seen_columns: set[str] = set()
    primary_flagged = 0
    string_columns = 0
    for col in table.columns:
        key = col.schema_name.lower()
        if key in seen_columns:
            issues.append(Issue(ERROR, f"Duplicate column schema name '{col.schema_name}'."))
        seen_columns.add(key)

        if not _is_custom(col.schema_name, prefix):
            issues.append(Issue(WARNING, f"Column '{col.schema_name}' does not start with prefix '{prefix}_'."))
        if _is_lowercase_style(col.schema_name, prefix):
            issues.append(Issue(WARNING, f"Column '{col.schema_name}' is lowercase; use PascalCase."))

        if col.type == AttributeType.String:
            string_columns += 1
            if col.is_primary_name:
                primary_flagged += 1

        # picklist option uniqueness
        if col.type == AttributeType.Picklist and col.options:
            values = [o.value for o in col.options]
            dupes = {v for v in values if values.count(v) > 1}
            if dupes:
                issues.append(Issue(
                    ERROR,
                    f"Picklist '{col.schema_name}' has duplicate option values: {sorted(dupes)}.",
                ))

    # --- alternate keys ---
    seen_keys: set[str] = set()
    for alternate_key in table.alternate_keys:
        key_name = alternate_key.schema_name.lower()
        if key_name in seen_keys:
            issues.append(Issue(ERROR, f"Duplicate alternate key schema name '{alternate_key.schema_name}'."))
        seen_keys.add(key_name)
        if not alternate_key.columns:
            issues.append(Issue(ERROR, f"Alternate key '{alternate_key.schema_name}' has no columns."))
        for column in alternate_key.columns:
            if column.lower() not in seen_columns:
                issues.append(Issue(
                    ERROR,
                    f"Alternate key '{alternate_key.schema_name}' references unknown column '{column}'.",
                ))

    # --- primary name ---
    if table.primary_name_column:
        if primary_flagged > 1:
            issues.append(Issue(ERROR, "Multiple columns flagged is_primary_name; only one is allowed."))
    elif primary_flagged > 1:
        issues.append(Issue(ERROR, "Multiple columns flagged is_primary_name; only one is allowed."))
    elif primary_flagged == 0:
        if string_columns == 0:
            issues.append(Issue(ERROR, "Table has no String column; Dataverse requires a primary name attribute."))
        else:
            issues.append(
                Issue(INFO, "No column flagged is_primary_name; the first String column will be auto-picked.")
            )

    # --- relationships ---
    seen_rels: set[str] = set()
    for rel in table.relationships:
        issues.extend(_lint_relationship(rel, logical, prefix, seen_rels))

    return issues


def _lint_relationship(rel: Relationship, owner_logical: str, prefix: str, seen: set[str]) -> list[Issue]:
    issues: list[Issue] = []
    key = rel.schema_name.lower()
    if key in seen:
        issues.append(Issue(ERROR, f"Duplicate relationship schema name '{rel.schema_name}'."))
    seen.add(key)

    if not _is_custom(rel.schema_name, prefix):
        issues.append(Issue(
            WARNING,
            f"Relationship '{rel.schema_name}' must start with publisher prefix '{prefix}_' (Dataverse requires this).",
        ))

    if rel.type == "ManyToMany":
        if not rel.referencing_entity or not rel.referenced_entity:
            issues.append(Issue(
                ERROR,
                f"Relationship '{rel.schema_name}' (N:N) needs referencing_entity and referenced_entity.",
            ))
        return issues

    # OneToMany
    if not rel.lookup:
        issues.append(Issue(ERROR, f"1:N relationship '{rel.schema_name}' requires a lookup column."))
    if not rel.referenced_entity or not rel.referencing_entity:
        issues.append(Issue(
            ERROR,
            f"1:N relationship '{rel.schema_name}' needs referenced_entity and referencing_entity.",
        ))
        return issues

    if rel.referencing_entity.lower() != owner_logical:
        issues.append(Issue(
            WARNING,
            f"Relationship '{rel.schema_name}' referencing_entity '{rel.referencing_entity}' "
            f"!= owning table '{owner_logical}'.",
        ))
    if rel.lookup and rel.lookup.target_entity.lower() != rel.referenced_entity.lower():
        issues.append(Issue(
            WARNING,
            f"Relationship '{rel.schema_name}' lookup target '{rel.lookup.target_entity}' "
            f"!= referenced_entity '{rel.referenced_entity}'.",
        ))
    return issues


def lint_definitions(definitions: Iterable[Definition], prefix: str = "new") -> dict[str, list[Issue]]:
    """Lint many definitions, keyed by definition name."""
    return {d.name: lint_table(d.table, prefix=prefix) for d in definitions}


def has_errors(issues: Iterable[Issue]) -> bool:
    return any(i.is_error for i in issues)
