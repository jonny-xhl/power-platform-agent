"""
framework_power - self-contained, Python-first Dataverse table deploy library.

AI-authored scripts build a :class:`Table` from the typed models below and call
:func:`deploy_table` to reconcile it against a Dataverse environment. This package is
self-contained (the legacy ``framework/`` YAML toolchain was removed 2026-08-31).

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
    AlternateKey,
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
    ContentKind,
    DeployMode,
    Form,
    FormCell,
    FormControl,
    FormColumn,
    FormEvent,
    FormEventHandler,
    FormLabel,
    FormLibrary,
    FormRow,
    FormSection,
    FormTab,
    FormType,
    GlobalOptionSet,
    IsolationMode,
    Plugin,
    PluginProject,
    PluginStep,
    StepImage,
    Publisher,
    QueryType,
    RibbonButton,
    RibbonCommand,
    RibbonCommandOverride,
    RibbonCustomRule,
    RibbonDefinition,
    RibbonDisplayRule,
    RibbonEnableRule,
    RibbonHideOob,
    RibbonLocLabel,
    RibbonScope,
    Solution,
    SourceType,
    View,
    ViewColumn,
    ViewCondition,
    ViewFilter,
    ViewLinkEntity,
    ViewOrder,
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
from .webresource_sync import (
    EXT_TO_TYPE,
    WebResourceSyncConfig,
    plan_webresources,
    reverse_webresources,
    scan_webresources,
    sync_webresources,
)
from .form_sync import (
    FormSyncConfig,
    load_form,
    plan_forms,
    reverse_forms,
    sync_forms,
)
from .view_sync import (
    ViewSyncConfig,
    load_view,
    plan_views,
    reverse_views,
    sync_views,
)
from .label_sync import (
    plan_auto_component_labels,
    sync_auto_component_labels,
)
from .ribbon_sync import (
    codegen_ribbon,
    lint_ribbon,
    load_ribbon,
    plan_ribbons,
    reverse_ribbons,
    sync_ribbons,
)
from .optionset_sync import (
    OptionSetSyncConfig,
    load_optionset,
    plan_optionsets,
    sync_optionsets,
)
from .workflow import (
    DEFAULT_PROJECT_PATH,
    WORKFLOW_STAGE_ORDER,
    Project,
    deploy_workflow,
    lint_workflow,
    load_project,
    plan_workflow,
)
from .data_dictionary import (
    DEFAULT_DICTIONARY_DIR,
    generate_all_tables_summary,
    generate_index,
    generate_table_docs,
    table_to_markdown,
)

__all__ = [
    # models
    "AlternateKey",
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
    "FormCell",
    "FormControl",
    "FormColumn",
    "FormEvent",
    "FormEventHandler",
    "FormLabel",
    "FormLibrary",
    "FormRow",
    "FormSection",
    "FormTab",
    "FormType",
    "GlobalOptionSet",
    "IsolationMode",
    "Plugin",
    "PluginProject",
    "PluginStep",
    "StepImage",
    "CustomAction",
    "ContentKind",
    "DeployMode",
    "Publisher",
    "QueryType",
    "Solution",
    "SourceType",
    "View",
    "ViewColumn",
    "ViewCondition",
    "ViewFilter",
    "ViewLinkEntity",
    "ViewOrder",
    "RibbonButton",
    "RibbonCommand",
    "RibbonCommandOverride",
    "RibbonCustomRule",
    "RibbonDefinition",
    "RibbonDisplayRule",
    "RibbonEnableRule",
    "RibbonHideOob",
    "RibbonLocLabel",
    "RibbonScope",
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
    # web resource directory sync (Phase 4)
    "EXT_TO_TYPE",
    "WebResourceSyncConfig",
    "plan_webresources",
    "reverse_webresources",
    "scan_webresources",
    "sync_webresources",
    # form operations (Phase 5)
    "FormSyncConfig",
    "load_form",
    "plan_forms",
    "reverse_forms",
    "sync_forms",
    # view operations (Phase 6)
    "ViewSyncConfig",
    "load_view",
    "plan_views",
    "reverse_views",
    "sync_views",
    # auto-created view/form name localization (ADR-016)
    "plan_auto_component_labels",
    "sync_auto_component_labels",
    # ribbon operations (Phase 7)
    "codegen_ribbon",
    "lint_ribbon",
    "load_ribbon",
    "plan_ribbons",
    "reverse_ribbons",
    "sync_ribbons",
    # global optionset sync wrapper (Phase 9)
    "OptionSetSyncConfig",
    "load_optionset",
    "plan_optionsets",
    "sync_optionsets",
    # cross-phase development workflow (Phase 9)
    "DEFAULT_PROJECT_PATH",
    "WORKFLOW_STAGE_ORDER",
    "Project",
    "deploy_workflow",
    "lint_workflow",
    "load_project",
    "plan_workflow",
    # data dictionary (Gen 2 Python-first)
    "DEFAULT_DICTIONARY_DIR",
    "generate_all_tables_summary",
    "generate_index",
    "generate_table_docs",
    "table_to_markdown",
]
