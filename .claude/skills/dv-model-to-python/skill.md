---
name: dv-model-to-python
description: 将Excel实体设计转换为 framework_power 的 Python 表定义文件（metadata_py/tables/<schema>.py）。当用户需要把 Excel 中的 Dataverse 实体设计转换成 Python 元数据定义、Excel转Python、设计文档转可执行元数据、或使用 framework_power 部署表时使用此技能。包括"转换Excel生成Python表定义"、"Excel转framework_power"、"生成表定义脚本"、"用Python定义表"等短语。
---

# Excel 实体设计转 Python 表定义（framework_power）

此技能将 Excel 中的 Dataverse 实体设计（由 `design-dv-model` 产出）转换为
`framework_power` 的**可执行 Python 表定义**，保存到 `metadata_py/tables/<schema>.py`。
生成的定义即"单一事实来源"——随后用 `framework_power lint → plan → deploy` 同步到 Dataverse。

**重要约束（必须先读）**: `docs/metadata-py-conventions.md` 是 AI 生成的硬性契约；
`framework_power/models.py` 是类型契约。生成的定义必须通过 `python -m framework_power lint <name>`（0 errors）才能进入 plan/deploy。

## 与 dv-model-to-yaml 的关键区别

| 维度 | dv-model-to-yaml（旧） | dv-model-to-python（本技能） |
|------|----------------------|-----------------------------|
| 输出 | `metadata/tables/<schema>.yaml` | `metadata_py/tables/<schema>.py`（暴露 `TABLE`） |
| 命名风格 | lowercase (`new_payment_number`) | **PascalCase** (`new_PaymentNumber`) |
| 命名处理 | NamingConverter 自动改写 | 作者负责；lint 校验、deploy 原样发送 |
| 多语言 | 仅中文 (2052) | **双语** `Label.bilingual(zh, en)` |
| 同步触发 | MCP 工具 `metadata_create_table` | CLI `python -m framework_power deploy` |
| 类型覆盖 | YAML + 后端转换 | framework_power 全类型直发 |

## 使用场景

- 把 `design-dv-model` 产出的 Excel 实体设计转为 Python 定义
- 用 framework_power 新建/扩展表（替代 YAML 路径）
- 批量生成多个实体的 Python 定义

## 输入 / 输出

- **输入**: Excel 设计文件，通常位于
  `sources/features/{feature-name}/02-designs/entities/{design}.xlsx`
  关键工作表 `02_实体模型`（实体/字段）、`05_枚举选项集`（选项集）。
- **输出**: `metadata_py/tables/{schema_lowercase}.py`，文件内 `TABLE: Table = Table(...)`。
  文件名 stem 即 CLI 的定义名（如 `new_projectbudget`）。

## Excel 工作表映射

| Excel 工作表 | Python 输出 |
|-------------|------------|
| `02_实体模型` | `metadata_py/tables/{entity}.py` 的 `Table(...)` |
| `05_枚举选项集` | 内联为 `Column(..., options=[Option(...)])`（本地选项集） |

> 全局选项集 / 表单 / 视图仍走 YAML 路径（本技能 Phase 1 只覆盖**表 + 字段 + 关系**）。

## 数据类型映射（Excel → `AttributeType`）

| Excel 类型 | `AttributeType` | 备注 |
|-----------|-----------------|------|
| Text / Email / Phone / URL | `String` | Email/Phone/Url 用 `format_name` |
| Multiline Text | `Memo` | `max_length` |
| Whole Number | `Integer` | `min_value`/`max_value` |
| Decimal Number | `Decimal` | `precision` |
| Currency | `Money` | `precision`, `precision_source=2` |
| Floating Point | `Double` | `precision` |
| Yes/No | `Boolean` | `boolean_labels`, `default_value` |
| Choice（本地） | `Picklist` | `options=[Option(value, Label.bilingual(zh,en))]` |
| Date and Time | `DateTime` | `date_time_behavior`, `format` |
| Lookup | （经 `Relationship`） | 不是 `Column` |

## 命名（PascalCase + 前缀）

发布商前缀取自 `config/publishers.yaml`（默认 `new`）。**作者直接写出合规的 PascalCase
SchemaName**，lint 只校验不改写。

| Excel 原始 | Python schema_name |
|-----------|--------------------|
| PaymentRecognition | `new_PaymentRecognition` |
| PaymentNumber | `new_PaymentNumber` |
| 认款单号 | `new_PaymentNumber`（按英文/拼音转 PascalCase） |
| account（标准实体扩展） | `account`（表名保持，字段仍加前缀） |

## 转换示例

Excel 行 → Python：

```python
from framework_power import Column, LookupColumn, Relationship, Table
from framework_power.models import (AttributeType, BooleanLabels, Cascade, CascadeConfig,
    Label, Option, RequiredLevel)

TABLE: Table = Table(
    schema_name="new_ProjectBudget",                       # PascalCase + 前缀
    display_name=Label.bilingual("项目预算", "Project Budget"),  # 双语
    display_collection_name=Label.bilingual("项目预算", "Project Budgets"),
    description=Label.bilingual("项目预算主表", "Project budget header"),
    columns=[
        Column("new_Name", AttributeType.String,
               display_name=Label.bilingual("预算名称", "Budget Name"),
               is_primary_name=True, required=RequiredLevel.ApplicationRequired, max_length=200),
        Column("new_Status", AttributeType.Picklist,
               display_name=Label.bilingual("状态", "Status"),
               options=[Option(1, Label.bilingual("草稿", "Draft")),
                        Option(2, Label.bilingual("已批准", "Approved"))]),
    ],
    relationships=[
        # 自定义 Lookup 必须用 Referential 级联（禁止 Cascade.Active）
        Relationship(
            schema_name="new_ProjectBudget_Account",
            referenced_entity="account", referencing_entity="new_projectbudget",
            lookup=LookupColumn("new_AccountId", Label.bilingual("客户", "Account"), target_entity="account"),
            cascade=CascadeConfig(delete=Cascade.RemoveLink, assign=Cascade.NoCascade),
        ),
    ],
)
```

## 转换步骤

1. **定位 Excel**：`sources/features/{feature}/02-designs/entities/{design}.xlsx`。
   Windows 终端读中文可能乱码——写入 UTF-8 临时文件后用 Read 查看（见 dv-model-to-yaml 的编码处理）。
2. **读取 `02_实体模型`**：提取实体名、字段（名称/显示名/英文名/类型/长度/必填/主字段/选项）、关系（关联实体/关联类型）。
3. **按契约生成 `Table`**：PascalCase + 前缀；双语 `Label.bilingual`；每个表有且仅有一个 String 主字段；
   选项值唯一；关系用 Referential 级联。
4. **写入 `metadata_py/tables/{schema_lowercase}.py`**，暴露 `TABLE`。
5. **校验门**：`python -m framework_power lint {name}` 必须 0 errors。
6. **预览**：`python -m framework_power plan {name} --env dev`（只读）。
7. **部署**（用户确认环境后）：`python -m framework_power deploy {name} --env dev`。

## 校验清单（生成后自检）

- [ ] 表名 PascalCase 且带发布商前缀（或为标准实体）
- [ ] 每个字段名带前缀；无一字段名以冲突的 `Id` 结尾（参见 dv-metadata）
- [ ] 有且仅有一个 `is_primary_name=True` 的 String 字段
- [ ] `Label.bilingual(zh, en)` 覆盖所有显示名/选项标签
- [ ] Picklist 选项值唯一
- [ ] 每个自定义关系以 `new_` 开头、用 Referential 级联、`lookup.target_entity == referenced_entity`
- [ ] `framework_power lint {name}` 报告 0 errors

## 参考文档

- 作者契约：`docs/metadata-py-conventions.md`
- 类型/模型：`framework_power/models.py`
- 部署说明：`docs/metadata-deploy.md`
- Dataverse Web API 细节：`dataverse:dv-metadata` skill
