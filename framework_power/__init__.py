"""
framework_power - self-contained, Python-first Dataverse table deploy library.

AI-authored scripts build a :class:`Table` from the typed models below and call
:func:`deploy_table` to reconcile it against a Dataverse environment. This package is
intentionally isolated from the legacy ``framework/`` YAML toolchain.

Quick start::

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
"""

from .models import (
    AttributeType,
    BooleanLabels,
    Cascade,
    CascadeConfig,
    Column,
    Label,
    LocalizedLabel,
    LookupColumn,
    Option,
    Relationship,
    RequiredLevel,
    Table,
)
from .serializer import (
    build_attribute_patch,
    serialize_column,
    serialize_entity_patch,
    serialize_label,
    serialize_relationship,
    serialize_table_for_create,
)
from .deployer import DeployConfig, deploy_table, plan_table
from .runtime import get_client, argparse_env
from .registry import (
    DEFAULT_DEFINITIONS_DIR,
    Definition,
    deploy_order,
    discover_definitions,
    get_definition,
)
from .lint import Issue, lint_table, lint_definitions, has_errors
from .codegen import table_to_python_source
from .reverse import reverse_table
from .components.models import (
    ComponentRef,
    CustomAction,
    Form,
    FormType,
    GlobalOptionSet,
    IsolationMode,
    Plugin,
    PluginStep,
    Publisher,
    QueryType,
    Solution,
    SourceType,
    View,
    WebResource,
    WebResourceType,
)
from .solution_deployer import (
    SolutionDeployConfig,
    deploy_solution,
    lint_solution,
    plan_solution,
    resolve_publisher,
)
from .solution_reverse import reverse_solution
from .solution_codegen import solution_to_python_source
from .components.models import (
    AccessRight,
    PrivilegeDepth,
    SecurityRole,
    TablePrivilege,
)
from .role_deployer import deploy_role, plan_role
from .role_reverse import reverse_role
from .role_codegen import role_to_python_source
from .role_registry import DEFAULT_ROLES_DIR, RoleDefinition, discover_role_definitions, get_role_definition

__all__ = [
    # models
    "AttributeType",
    "BooleanLabels",
    "Cascade",
    "CascadeConfig",
    "Column",
    "Label",
    "LocalizedLabel",
    "LookupColumn",
    "Option",
    "Relationship",
    "RequiredLevel",
    "Table",
    # serializer
    "build_attribute_patch",
    "serialize_column",
    "serialize_entity_patch",
    "serialize_label",
    "serialize_relationship",
    "serialize_table_for_create",
    # deployer
    "DeployConfig",
    "deploy_table",
    "plan_table",
    # runtime
    "get_client",
    "argparse_env",
    # registry
    "DEFAULT_DEFINITIONS_DIR",
    "Definition",
    "deploy_order",
    "discover_definitions",
    "get_definition",
    # lint
    "Issue",
    "lint_table",
    "lint_definitions",
    "has_errors",
    # codegen + reverse
    "table_to_python_source",
    "reverse_table",
    # solution management (Phase 2)
    "ComponentRef",
    "Form",
    "FormType",
    "GlobalOptionSet",
    "IsolationMode",
    "Plugin",
    "PluginStep",
    "CustomAction",
    "Publisher",
    "QueryType",
    "Solution",
    "SourceType",
    "View",
    "WebResource",
    "WebResourceType",
    "SolutionDeployConfig",
    "deploy_solution",
    "lint_solution",
    "plan_solution",
    "resolve_publisher",
    "reverse_solution",
    "solution_to_python_source",
    # security roles (Phase 3)
    "AccessRight",
    "PrivilegeDepth",
    "SecurityRole",
    "TablePrivilege",
    "deploy_role",
    "plan_role",
    "reverse_role",
    "role_to_python_source",
    "DEFAULT_ROLES_DIR",
    "RoleDefinition",
    "discover_role_definitions",
    "get_role_definition",
]
