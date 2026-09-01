"""Canonical example table definition (``new_ProjectBudget``).

Ships WITH the engine package so unit tests (registry/CLI) and docs share one
stable, tracked definition — independent of any workspace's ``metadata_py/``.

Deploy (workspace copy or direct):::

    python -m framework_power deploy new_projectbudget --env dev \
        --definitions-dir framework_power/examples
"""

from __future__ import annotations

from framework_power import Column, Label, LookupColumn, Relationship, Table
from framework_power.models import (
    AttributeType,
    Cascade,
    CascadeConfig,
    Option,
    RequiredLevel,
)

TABLE: Table = Table(
    schema_name="new_ProjectBudget",
    display_name=Label.bilingual("项目预算", "Project Budget"),
    display_collection_name=Label.bilingual("项目预算", "Project Budgets"),
    description=Label.bilingual(
        "项目预算主表（引擎规范示例）", "Project budget (engine canonical example)"
    ),
    ownership_type="UserOwned",
    has_notes=True,
    is_audit_enabled=True,
    columns=[
        Column(
            "new_Name",
            AttributeType.String,
            display_name=Label.bilingual("名称", "Name"),
            is_primary_name=True,
            required=RequiredLevel.ApplicationRequired,
            max_length=200,
        ),
        Column(
            "new_Amount",
            AttributeType.Money,
            display_name=Label.bilingual("预算金额", "Budget Amount"),
            precision=2,
            precision_source=2,
        ),
        Column(
            "new_Status",
            AttributeType.Picklist,
            display_name=Label.bilingual("状态", "Status"),
            options=[
                Option(1, Label.bilingual("草稿", "Draft")),
                Option(2, Label.bilingual("已批准", "Approved")),
            ],
        ),
    ],
    relationships=[
        Relationship(
            schema_name="new_ProjectBudget_Account",
            referenced_entity="account",
            referencing_entity="new_projectbudget",
            lookup=LookupColumn(
                "new_AccountId",
                Label.bilingual("客户", "Account"),
                target_entity="account",
            ),
            cascade=CascadeConfig(delete=Cascade.RemoveLink, assign=Cascade.NoCascade),
        ),
    ],
)
