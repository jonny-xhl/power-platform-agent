"""
Solution-component type registry (framework_power Phase 2).

A :class:`ComponentType` bundles the model + the functions that deploy, plan,
reverse, serialize, codegen, lint, existence-check, and resolve the ObjectId for
one component type (table, optionset, webresource, form, view, plugin).
``deploy_solution`` / ``reverse_solution`` dispatch through ``COMPONENT_TYPES``
instead of hard-coding each type, so new types register without touching the
solution layer.

Wave 1 registers only ``table`` as a thin adapter over the existing Phase-1
``deploy_table`` / ``plan_table`` / ``reverse_table`` / ``table_to_python_source``
+ ``lint_table`` — Phase-1 table code paths are NOT refactored. Later waves add
``optionset`` / ``webresource`` / ``form`` / ``view`` / ``plugin``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..codegen import table_to_python_source
from ..deployer import deploy_table, plan_table
from ..lint import Issue, lint_table
from ..models import Table
from ..reverse import reverse_table
from ..serializer import serialize_table_for_create

# Dependency order: optionset before table (picklist columns may reference a global
# optionset), then the types that depend on a table existing, then plugins.
COMPONENT_DEPLOY_ORDER: tuple[str, ...] = (
    "optionset",
    "table",
    "webresource",
    "form",
    "view",
    "plugin",
)


@dataclass(frozen=True)
class ComponentType:
    """A registered component type and the functions that handle it."""

    key: str  # "table" | "optionset" | "webresource" | "form" | "view" | "plugin"
    solution_component_type: int  # AddSolutionComponent ComponentType code
    model_cls: type  # the typed dataclass (Table | GlobalOptionSet | ...)
    serialize: Callable[..., Any]  # model -> Web API create payload (dict)
    deploy: Callable[..., Any]  # (client, model, *, prefix, config) -> dict
    plan: Callable[..., Any]  # (client, model, *, prefix) -> dict  (read-only)
    reverse: Callable[..., Any]  # (client, ident) -> model  (full snapshot)
    codegen: Callable[..., Any]  # model -> python source str
    exists: Callable[..., Any]  # (client, model) -> bool
    resolve_id: Callable[..., Any]  # (client, model) -> str | None
    lint: Callable[..., Any]  # (model, *, prefix) -> list[Issue]
    deploy_depends_on: tuple[str, ...] = ()
    codegen_imports: tuple[str, ...] = ()  # names codegen references (for import line)


# ----------------------------------------------------------------- table adapter


def _table_serialize(table: Table) -> dict[str, Any]:
    return serialize_table_for_create(table)


def _table_deploy(
    client: Any, table: Table, *, prefix: str = "new", config: Any = None
) -> dict[str, Any]:
    return deploy_table(client, table, config=config, prefix=prefix)


def _table_plan(client: Any, table: Table, *, prefix: str = "new") -> dict[str, Any]:
    return plan_table(client, table, prefix=prefix)


def _table_reverse(client: Any, ident: str) -> Table:
    return reverse_table(client, ident)


def _table_codegen(table: Table) -> str:
    return table_to_python_source(table)


def _table_exists(client: Any, table: Table) -> bool:
    return bool(client.entity_exists(table.logical_name))


def _table_resolve_id(client: Any, table: Table) -> Optional[str]:
    return client.get_entity_metadata(table.logical_name).get("MetadataId")


def _table_lint(table: Table, *, prefix: str = "new") -> list[Issue]:
    return lint_table(table, prefix=prefix)


_TABLE_TYPE = ComponentType(
    key="table",
    solution_component_type=1,
    model_cls=Table,
    serialize=_table_serialize,
    deploy=_table_deploy,
    plan=_table_plan,
    reverse=_table_reverse,
    codegen=_table_codegen,
    exists=_table_exists,
    resolve_id=_table_resolve_id,
    lint=_table_lint,
    deploy_depends_on=("optionset",),
)


# ----------------------------------------------------------------- registry

# Tables are registered in Wave 1; optionset/webresource/form/view/plugin are added
# by their respective waves (each appends to this dict). deploy_solution iterates
# COMPONENT_DEPLOY_ORDER and skips types not yet present here.
COMPONENT_TYPES: dict[str, ComponentType] = {
    "table": _TABLE_TYPE,
}


def component_type_for_code(code: int) -> Optional[str]:
    """Return the registry key whose ``solution_component_type == code``, or None."""
    for key, ctype in COMPONENT_TYPES.items():
        if ctype.solution_component_type == code:
            return key
    return None


def _register_module(mod: Any) -> None:
    """Register a per-type module (uniform serialize/deploy/.../lint interface)."""
    COMPONENT_TYPES[mod.KEY] = ComponentType(
        key=mod.KEY,
        solution_component_type=mod.SOLUTION_CODE,
        model_cls=mod.MODEL_CLS,
        serialize=mod.serialize,
        deploy=mod.deploy,
        plan=mod.plan,
        reverse=mod.reverse,
        codegen=mod.codegen,
        exists=mod.exists,
        resolve_id=mod.resolve_id,
        lint=mod.lint,
        deploy_depends_on=getattr(mod, "DEPENDS_ON", ()),
        codegen_imports=getattr(mod, "CODEGEN_IMPORTS", ()),
    )


# Per-type handlers (imported AFTER COMPONENT_TYPES is defined). Each module is
# pure (no import from this package __init__), so there is no import cycle.
from . import optionset as _optionset  # noqa: E402
from . import webresource as _webresource  # noqa: E402
from . import form as _form  # noqa: E402
from . import view as _view  # noqa: E402
from . import plugin as _plugin  # noqa: E402

for _mod in (_optionset, _webresource, _form, _view, _plugin):  # noqa: E402
    _register_module(_mod)
