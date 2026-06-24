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
from .deployer import DeployConfig, deploy_table
from .runtime import get_client, argparse_env

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
    # runtime
    "get_client",
    "argparse_env",
]
