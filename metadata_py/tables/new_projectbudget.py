"""
Table definition: new_ProjectBudget (canonical framework_power definition).

This file is the single source of truth for the Project Budget table. It is discovered
by the registry (``framework_power list``) because it lives under ``metadata_py/tables/``
and exposes ``TABLE``. Deploy with:

    python -m framework_power lint new_projectbudget
    python -m framework_power plan new_projectbudget --env dev
    python -m framework_power deploy new_projectbudget --env dev

Authoring conventions (see docs/metadata-py-conventions.md):
- PascalCase SchemaName with the publisher prefix (new_).
- Exactly one String column flagged is_primary_name.
- Multi-language labels via Label.bilingual(zh, en).
- Referential cascade (RemoveLink / NoCascade) for custom lookups.
"""

from framework_power import Column, LookupColumn, Relationship, Table
from framework_power.models import (
    AttributeType,
    BooleanLabels,
    Cascade,
    CascadeConfig,
    Label,
    Option,
    RequiredLevel,
)

TABLE: Table = Table(
    schema_name="new_ProjectBudget",
    display_name=Label.bilingual("项目预算", "Project Budget"),
    display_collection_name=Label.bilingual("项目预算", "Project Budgets"),
    description=Label.bilingual("项目预算主表", "Project budget header"),
    has_notes=True,
    columns=[
        Column(
            "new_Name", AttributeType.String,
            display_name=Label.bilingual("预算名称", "Budget Name"),
            is_primary_name=True,
            required=RequiredLevel.ApplicationRequired,
            max_length=200,
        ),
        Column(
            "new_Amount", AttributeType.Money,
            display_name=Label.bilingual("预算金额", "Amount"),
            precision=2, precision_source=2, min_value=0, max_value=1e12,
            required=RequiredLevel.ApplicationRequired,
        ),
        Column(
            "new_Status", AttributeType.Picklist,
            display_name=Label.bilingual("状态", "Status"),
            default_value=1,
            options=[
                Option(1, Label.bilingual("草稿", "Draft")),
                Option(2, Label.bilingual("已批准", "Approved")),
                Option(3, Label.bilingual("已关闭", "Closed")),
            ],
        ),
        Column(
            "new_IsActive", AttributeType.Boolean,
            display_name=Label.bilingual("是否有效", "Is Active"),
            default_value=True,
            boolean_labels=BooleanLabels(
                true_label=Label.bilingual("是", "Yes"),
                false_label=Label.bilingual("否", "No"),
            ),
        ),
        Column(
            "new_StartDate", AttributeType.DateTime,
            display_name=Label.bilingual("开始日期", "Start Date"),
            date_time_behavior="DateOnly", format="DateOnly",
        ),
        Column(
            "new_Notes", AttributeType.Memo,
            display_name=Label.bilingual("备注", "Notes"),
            max_length=2000,
        ),
    ],
    relationships=[
        Relationship(
            schema_name="new_ProjectBudget_Account",
            referenced_entity="account",
            referencing_entity="new_projectbudget",
            lookup=LookupColumn(
                "new_AccountId",
                display_name=Label.bilingual("客户", "Account"),
                target_entity="account",
                required=RequiredLevel.ApplicationRequired,
            ),
            cascade=CascadeConfig(delete=Cascade.RemoveLink, assign=Cascade.NoCascade),
        ),
    ],
)
