#!/usr/bin/env python3
"""
Canonical AI-authored deploy example for framework_power.

Defines the ``new_ProjectBudget`` table as typed Python models (the single source of
truth) and reconciles it against a Dataverse environment via :func:`deploy_table`.

Covers every common column type, multi-language (zh + en) labels, and a 1:N
relationship that creates a lookup column (Deep Insert). Re-running is idempotent.

Usage:
    python -m framework_power.examples.setup_projectbudget --env dev
    python framework_power/examples/setup_projectbudget.py --env dev
"""

from __future__ import annotations

import json

from framework_power import Column, LookupColumn, Relationship, Table, deploy_table, get_client
from framework_power.models import (
    AttributeType,
    BooleanLabels,
    Cascade,
    CascadeConfig,
    Label,
    Option,
    RequiredLevel,
)
from framework_power.runtime import argparse_env


def build_table() -> Table:
    return Table(
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


def main() -> int:
    env = argparse_env(description="Deploy the new_ProjectBudget table")
    client = get_client(env)
    result = deploy_table(client, build_table())
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
