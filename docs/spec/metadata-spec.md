# Power Platform 元数据规范

## 概述

本规范是 **Python API（`framework_power`）** 的作者契约：元数据以类型化 Python 模型定义
（`metadata_py/*.py`），经 `pp` CLI 同步到 Dataverse。

> legacy YAML 规范随 `framework/` 于 2026-08-31 一并移除（历史版本见 git）。
> 选项集（全局/本地）的建模方式见下方各字段类型节。

---

## Python API (framework_power)

### 快速开始

```python
from framework_power import (
    Table, Column, Label, AttributeType, RequiredLevel,
    deploy_table, get_client
)

# 定义多语言标签
title = Label.bilingual("项目预算", "Project Budget")

# 定义字段
columns = [
    Column(
        schema_name="new_Name",
        type=AttributeType.String,
        display_name=Label.bilingual("名称", "Name"),
        is_primary_name=True,
        required=RequiredLevel.ApplicationRequired,
        max_length=200
    ),
]

# 定义表
table = Table(
    schema_name="new_ProjectBudget",
    display_name=title,
    columns=columns,
)

# 部署到环境
result = deploy_table(get_client("dev"), table)
```

### 标签 API

```python
from framework_power.models import Label, LocalizedLabel, LANGUAGE_ZH_CN, LANGUAGE_EN_US

# 多种创建方式
label_zh = Label.zh("中文标签")
label_en = Label.en("English Label")
label_bilingual = Label.bilingual("中文", "English")

# 手动构建多语言标签
label = Label([
    LocalizedLabel("中文文本", LANGUAGE_ZH_CN),
    LocalizedLabel("English Text", LANGUAGE_EN_US),
])

# 类型兼容
label = Label.parse("纯中文")           # 中文
label = Label.parse(("中", "En"))        # 双语
label = Label.parse(Label.zh("已有"))    # 直接传递
```

### 字段类型

```python
from framework_power.models import AttributeType

# 支持的字段类型
AttributeType.String      # 字符串
AttributeType.Integer     # 整数
AttributeType.BigInt      # 大整数
AttributeType.Money       # 货币
AttributeType.Decimal     # 小数
AttributeType.Double      # 双精度浮点
AttributeType.Picklist    # 选项集
AttributeType.Boolean     # 是/否
AttributeType.Memo        # 多行文本
AttributeType.DateTime    # 日期时间
AttributeType.File        # 文件
```

### Column 定义

```python
from framework_power.models import Column, AttributeType, RequiredLevel, Label

# 字符串字段
Column(
    schema_name="new_name",
    type=AttributeType.String,
    display_name=Label.zh("名称"),
    max_length=100,
    format_name="Text",  # Text/Email/Url/Phone/TextArea
    required=RequiredLevel.ApplicationRequired,
)

# 整数字段
Column(
    schema_name="new_quantity",
    type=AttributeType.Integer,
    display_name=Label.zh("数量"),
    min_value=0,
    max_value=10000,
)

# 货币字段
Column(
    schema_name="new_amount",
    type=AttributeType.Money,
    display_name=Label.zh("金额"),
    precision=2,
    precision_source=2,  # 0=组织, 1=货币, 2=字段
)

# 日期字段
Column(
    schema_name="new_start_date",
    type=AttributeType.DateTime,
    display_name=Label.zh("开始日期"),
    format="DateOnly",  # DateOnly/DateAndTime
    date_time_behavior="UserLocal",  # UserLocal/DateOnly/TimeZoneIndependent
)

# 布尔字段
from framework_power.models import BooleanLabels
Column(
    schema_name="new_is_active",
    type=AttributeType.Boolean,
    display_name=Label.zh("是否启用"),
    boolean_labels=BooleanLabels(
        true_label=Label.zh("是"),
        false_label=Label.zh("否"),
    ),
)

# Picklist 字段 (本地选项集)
from framework_power.models import Option
Column(
    schema_name="new_priority",
    type=AttributeType.Picklist,
    display_name=Label.zh("优先级"),
    options=[
        Option(value=1, label=Label.zh("低")),
        Option(value=2, label=Label.zh("中")),
        Option(value=3, label=Label.zh("高")),
    ],
)

# Picklist 字段 (引用全局选项集 — ADR-009/ADR-011)
Column(
    schema_name="new_businessgroup_id",
    type=AttributeType.Picklist,
    display_name=Label.bilingual("商务组", "Business Group"),
    optionset_name="new_salesgroup",  # 引用 metadata_py/optionsets/new_salesgroup.py
    required=RequiredLevel.ApplicationRequired,
)
```

#### 全局选项集引用

`optionset_name` 指向 `metadata_py/optionsets/<name>.py` 中独立建模的
`GlobalOptionSet`（模块级 `OPTIONSET` 变量，导出 `name` / `display_name` /
`options` / 可选 `description`）。语义契约：

- 序列化为 `OptionSet.IsGlobal=true + Name` 引用，**不内联选项**（选项归全局
  选项集所有，选项增删改在选项集侧完成）。
- **依赖优先自动同步**（ADR-011）：`pp deploy <table>` 会先收集表中所有
  `optionset_name` 引用，加载对应本地定义并**先行同步**（create-only、幂等、
  漂移报 `manual_update_required`），再部署实体/字段；带 `--solution` 时选项集
  自动加入同一解决方案（code 9）。无本地定义时降级为只读在线检查并在结果
  `optionsets_missing` 记录告警（不阻断部署，但新环境会失败——务必建模）。
- 也可独立管理：`pp optionset list | plan | deploy [--name] [--solution]`。

### LookupColumn 和 Relationship

```python
from framework_power.models import (
    LookupColumn, Relationship, CascadeConfig, Cascade, Label
)

# 定义查找字段 (通过 Relationship 部署)
Relationship(
    schema_name="new_ProjectBudget_Contact",
    referenced_entity="contact",            # 父表
    referencing_entity="new_projectbudget", # 子表
    lookup=LookupColumn(
        schema_name="new_ContactId",
        display_name=Label.zh("联系人"),
        target_entity="contact",
        required=RequiredLevel.None_,
    ),
    cascade=CascadeConfig(
        assign=Cascade.NoCascade,
        delete=Cascade.RemoveLink,
    ),
)

# N:N 关系
Relationship(
    schema_name="new_Course_Trainer",
    type="ManyToMany",
    intersect_entity_name="new_course_trainer",
    display_name=Label.bilingual("课程-讲师", "Course-Trainer"),
)
```

### Table 定义

```python
from framework_power import Table, Column, Label

table = Table(
    schema_name="new_ProjectBudget",
    display_name=Label.bilingual("项目预算", "Project Budget"),
    display_collection_name=Label.bilingual("项目预算", "Project Budgets"),
    description=Label.bilingual("项目预算信息", "Project Budget Information"),
    ownership_type="UserOwned",  # UserOwned/OrganizationOwned
    has_activities=False,
    has_notes=True,
    is_audit_enabled=True,
    primary_name_column="new_name",
    columns=[
        # ... Column 定义
    ],
    relationships=[
        # ... Relationship 定义
    ],
)
```

### 定义位置与注册表

- 每表一个文件：`metadata_py/tables/<schema_lowercase>.py`
- 每个文件暴露模块级 `TABLE: Table`（注册表通过此变量发现定义）
- 文件名 stem = CLI 定义键（如 `new_projectbudget.py` → CLI `new_projectbudget`）
- 全局选项集：`metadata_py/optionsets/<name>.py`，暴露模块级
  `OPTIONSET: GlobalOptionSet`（被表引用时由 deploy 自动加载，ADR-011）
- 双向单文件：同一文件可被 `pp reverse` 覆盖（全量快照）、也可正向 `pp deploy`；
  标准（无 `new_` 前缀）项自动跳过 → 全量快照正向同步幂等且安全

### 开发流水线

```
需求 (docs/features/<feature>/01-prd)
  → design-dv-model → Excel 设计 (docs/features/<feature>/02-designs)
  → dv-model-to-python  → metadata_py/tables/<schema>.py   （AI 生成步骤）
  → (引用全局选项集时) metadata_py/optionsets/<name>.py
  → pp lint <name>                 （离线入口校验，0 errors）
  → pp plan <name> --env dev       （只读预演，含引用选项集 would_* 计划）
  → pp deploy <name> --env dev     （依赖优先同步选项集 → 表同步到 Dataverse）
```

### 命名规则

引擎**不自动改写名称**：作者负责命名，`lint` 校验、`deploy` 原样发送。

- Dataverse 标准 **PascalCase**（`new_PaymentNumber`）是引擎文档的默认约定；
  **本组织既有表多用 snake_case**（`new_payment_number`，与 Excel 数据字典的
  API 名对齐）——`lint` 对小写风格仅告警不拦截，**与既有表保持一致即可**。

| 元素 | 规则 | 示例 |
|---|---|---|
| 自定义表 `schema_name` | `{prefix_}{Name}` | `new_ProjectBudget` |
| 自定义列 `schema_name` | `{prefix_}{Name}` | `new_PaymentNumber` |
| 关系 `schema_name` | `{prefix_}_{Referenced}{Referencing}` | `new_ProjectBudget_Account` |
| Lookup 列 `schema_name` | `{prefix_}{Name}` 以 `Id` 结尾 | `new_AccountId` |
| 标准实体（扩展） | 保持逻辑名称 | `account` |

发布商前缀来自 `config/publishers.yaml`，默认 `new`。

> **避免 `*Id` 冲突陷阱**：普通列名为 `new_FooId` 会与后续添加的
> Lookup 列 `new_FooId` 冲突。源系统 ID 请使用 `new_SrcFooId`。

### 标签约定

对 `display_name`、`display_collection_name`、`description`、选项标签和布尔值
是/否标签，使用 `Label.bilingual(zh, en)`（中文 2052，英文 1033）。
如果只有一种语言，`Label.zh(text)` 也可以，但**双语是项目标准**。

### 类型映射（Excel → AttributeType）

| Excel 类型 | `AttributeType` | 说明 |
|---|---|---|
| 文本 / 电子邮件 / 电话 / URL | `String` | 通过 `format_name` 设置 Email/Phone/Url |
| 多行文本 | `Memo` | 设置 `max_length` |
| 整数 | `Integer` | 设置 `min_value`/`max_value` |
| 小数 | `Decimal` | 设置 `precision` |
| 货币 | `Money` | 设置 `precision`、`precision_source=2` |
| 浮点数 | `Double` | 设置 `precision` |
| 是/否 | `Boolean` | 设置 `boolean_labels`、`default_value` |
| 选项集（本地） | `Picklist` | `options=[Option(value, Label...)]` |
| 选项集（跨表复用/既有全局） | `Picklist` | `optionset_name="<name>"` 引用（ADR-011） |
| 日期和时间 | `DateTime` | 设置 `date_time_behavior`、`format` |
| Lookup | 通过 `Relationship` | 不是 `Column` |

### Required 级别

`RequiredLevel.ApplicationRequired` / `Recommended` / `None_`。
主名称列通常为 `ApplicationRequired`。所有 `Column` 定义中通过 `required=` 参数设置。

### 关系约束

- **仅限 Referential 级联**：Dataverse 每个实体只允许一个 Parental 级联，
  而 `UserOwned` 实体已通过 Owner 占用一个。切勿使用 `Cascade.Active`。
- 1:N 关系通过 Deep Insert 创建其 Lookup — **切勿将 Lookup 定义为独立的 `Column`**。
- `lookup.target_entity` 必须等于 `referenced_entity`。
- 被引用的实体必须在目标环境中已存在（deploy 会检查此条件）。
- 关系仅支持创建（Dataverse 不支持 PATCH 关系定义）；已存在则跳过。

```python
Relationship(
    schema_name="new_ProjectBudget_Account",
    referenced_entity="account",              # 父表（1 端），逻辑名称
    referencing_entity="new_projectbudget",   # 本表，逻辑名称
    lookup=LookupColumn("new_AccountId",
        Label.bilingual("客户", "Account"),
        target_entity="account"),
    cascade=CascadeConfig(delete=Cascade.RemoveLink, assign=Cascade.NoCascade),
)
```

### 结构规则（lint 强制执行）

`pp lint` 在部署前进行离线校验，以下规则零容忍（0 errors 才能 plan/deploy）：

- **有且仅有一个主名称**：一个 `String` 列设置 `is_primary_name=True`（或设置
  `Table.primary_name_column`）。零个 String 列为错误。
- 列 `schema_name` 不重复（大小写不敏感）
- Picklist 选项值不重复（同一列内）
- 关系 `schema_name` 不重复
- 每个自定义 `schema_name` 以发布商前缀开头

警告（如命名风格）属于建议性质，但仍应修复。

### 编写后校验

```bash
pp lint new_projectbudget              # 离线；必须 0 错误
pp plan new_projectbudget --env dev    # 只读差异预览（默认紧凑摘要，--json 全量）
pp deploy new_projectbudget --env dev  # 实际同步
```

---

## Dataverse 关键行为（引擎契约相关）

### 级联类型

- `NoCascade` - 无操作
- `Cascade` - 级联
- `Active` - 激活级联（Parental；每实体仅一个，UserOwned 已被 Owner 占用）
- `RemoveLink` - 移除链接
- `Restrict` - 限制

### Deep Insert 模式

Lookup 字段和关系通过 `RelationshipDefinitions` Deep Insert 一次性创建：

1. Lookup 属性定义在 `Relationship.lookup`（`LookupColumn`）
2. 创建关系时，Lookup 属性自动嵌入关系定义
3. 一次 API 调用同时创建关系和查找字段

### FetchXml 操作符（视图过滤条件可用）

`eq` / `ne` / `gt` / `ge` / `lt` / `le` / `like` / `in` / `between` / `null` /
`not-null` / `today` / `this-week` / `this-month` / `this-year` /
`last-x-months`（如明细视图"最近6个月"）/ `eq-userid` 等用户相关操作符。
多值用 `values=[...]`（生成多个 `<value>` 子元素）。

### Web Resource 类型（Phase 4 目录同步）

| 类型 | 扩展名 | webresourcetype |
|-----|--------|---------|
| CSS | .css | 2 |
| JavaScript | .js | 3 |
| HTML | .html | 1 |
| PNG | .png | 5 |
| JPEG | .jpg | 6 |
| GIF | .gif | 7 |
| SVG | .svg | 11 |
| ICO | .ico | 8 |
| XML | .xml | 4 |
| XSLT | .xslt | 9 |

命名模式：`{prefix}_/{relpath}`（如 `js/order/test.js` → `new_/js/order/test.js`），
类型由扩展名推导；未知扩展名跳过并告警。

### 标准实体保护

以下标准实体不会被前缀规则影响（正向同步自动跳过标准组件）：

系统核心：`account`, `contact`, `systemuser`, `team`, `businessunit`, `role`

活动相关：`activitypointer`, `email`, `appointment`, `task`, `phonecall`, `letter`, `fax`

销售相关：`lead`, `opportunity`, `competitor`, `quote`, `salesorder`, `invoice`

完整列表请参考 `config/publishers.yaml` 中的 `naming.standard_entities`。

---

## 元数据文件组织

### 项目目录结构

```
power-platform-agent/            # 引擎仓库
├── framework_power/             # 引擎层 - Python-first 部署库（唯一引擎）
│   ├── models.py / serializer.py / deployer.py / cli.py
│   ├── client/                  # 自包含 Dataverse Web API client
│   ├── components/              # 组件注册表（table/optionset/webresource/form/
│   │                            #   view/sitemap/plugin/ribbon + compact codegen）
│   └── *_sync.py                # 各域 plan/sync/reverse（solution/optionset/
│                                #   webresource/form/view/ribbon/plugin/role/
│                                #   sitemap/label）
│
├── <workspace>/                 # 工作区（如 ninebot-project/，不入引擎仓库）
│   ├── metadata_py/
│   │   ├── tables/              # 表定义 (*.py)
│   │   ├── optionsets/          # 全局选项集定义 (*.py)
│   │   ├── forms/               # 窗体定义 (*.py，逆向生成)
│   │   ├── views/               # 视图定义 (*.py，逆向生成)
│   │   ├── ribbons/             # 命令栏定义 (*.py)
│   │   ├── roles/               # 安全角色定义 (*.py)
│   │   └── project.py           # 跨阶段工作流清单 (Phase 9)
│   ├── webresources/            # Web 资源源文件（Phase 4 目录同步）
│   ├── plugins/                 # .NET 插件工程 (Phase 8)
│   ├── config/                  # environments.yaml / publishers.yaml / .env
│   └── docs/                    # features/ 数据字典/ env_backup/ 台账
│
├── docs/                        # 引擎文档层
│   ├── spec/                    # 规范文档（本文件、architecture.md、ADR）
│   └── guides/                  # 使用指南
└── .claude/skills/              # Claude Code 技能
```

### 文件命名

- 使用小写字母和下划线：`new_projectbudget.py`
- 表定义文件 stem = CLI 定义键

---

## 数据字典生成

```bash
# 按环境逆向生成（云端为准，写入 <workspace>/docs/data_dictionary/）
pp reverse <table> --env dev --dictionary
```

生成内容：

```
docs/data_dictionary/
├── index.md              # 汇总索引
├── CLAUDE.md             # Agent 使用说明
├── tables/               # 单表详细文档
│   ├── {schema_name}.md
│   └── ...
└── optionsets/           # 选项集详细文档
    ├── {schema_name}.md
    └── ...
```

---

## 复用模式

### 需求文档模板 (docs/templates)

| 模板文件 | 用途 |
|---------|------|
| `FEATURE_STRUCTURE.md` | Feature 目录结构约定（01-prd → 02-design → 03-implementation → 04-output） |
| `PRD_TEMPLATE.md` | PRD 主模板（背景、流程、实体设计、业务规则、实现计划等 9 个章节） |
| `ENTITY_DESIGN.md` | Dataverse 实体设计模板（字段、Picklist、Lookup、Python 实现参考） |

创建新 Feature 时，复制对应模板到 `docs/features/{feature-name}/` 后填写即可。

### Python 组合复用

Python 原生支持 import，复用自然且类型安全：

```python
# metadata_py/shared/audit_fields.py
from framework_power import Column, Label, AttributeType

AUDIT_COLUMNS = [
    Column("new_CreatedBy", AttributeType.String,
           display_name=Label.zh("创建人"), is_primary_name=False),
    Column("new_CreatedOn", AttributeType.DateTime,
           display_name=Label.zh("创建时间"), format="DateAndTime"),
]

# metadata_py/tables/my_table.py - 引用共享字段
from framework_power import Table, Label
from metadata_py.shared.audit_fields import AUDIT_COLUMNS

table = Table(
    schema_name="new_MyTable",
    display_name=Label.zh("我的表"),
    columns=AUDIT_COLUMNS + [
        Column("new_Name", AttributeType.String, ...),
    ],
)
```

### 内置默认配置

`framework_power` 为关系级联等场景提供了合理的默认值，无需重复声明：

```python
from framework_power.models import CascadeConfig, Cascade

# 使用默认值（多为保守策略）
CascadeConfig()

# 显式覆盖
CascadeConfig(delete=Cascade.Cascade_, assign=Cascade.Cascade_)
```

---

## 开发工作流

### 初始化流程

1. 在 `metadata_py/tables/` 下创建表定义文件（或 `pp reverse <table>` 逆向既有表）
2. `pp lint <name>` 校验（0 errors）
3. `pp plan <name> --env dev` 预览 → `pp deploy <name> --env dev` 应用

### 迭代流程

1. 修改 Python 定义
2. `pp plan` → `pp deploy` — 引擎在结构化模型上 diff，仅应用变更部分
3. 重部署幂等：无差异 = `would_skip` / `skipped`，从不删除

> 完整部署语义（含 ADR-016 自动名本地化、ADR-011 选项集先行同步）详见
> [元数据部署文档](../guides/metadata-deploy.md)。

---

## 错误处理

| 错误场景 | 引擎行为 |
|----------|-----------|
| 属性/关系已存在 | 自动检测并跳过（幂等） |
| 关系创建失败 | 检查引用实体是否存在、关系名是否正确 |
| 全局选项集本地未建模 | `optionsets_missing` 告警，不阻断（新环境会失败） |
| 全局选项集选项漂移 | `manual_update_required`（选项归选项集侧管理） |
| 环境写操作前 | ADR-013：先 `pp env-guard backup` + 台账 |

- **部分失败继续执行**：单个字段或关系失败不会中断整个部署
- **详细结果列表**：deploy/plan 返回每个操作的动作与错误，方便定位
- 元数据传播等待与瞬时错误（`0x80040216` 等）自动退避重试

---

## 相关文档

- [架构文档](architecture.md) - 系统架构设计
- [元数据部署](../guides/metadata-deploy.md) - 完整部署工作流与部署语义
- [快速开始](../guides/getting-started.md) - 详细入门指南

## framework_power API 参考

### 核心部署 API

| 函数 | 说明 |
|------|------|
| `deploy_table(client, table, config?)` | 部署表到 Dataverse（幂等非破坏） |
| `plan_table(client, table)` | 生成部署计划（预览变更） |
| `reverse_table(client, logical_name)` | 从现有表反向生成 Python 定义 |
| `lint_table(table)` | 检查表定义的正确性 |

### 解决方案管理

| 函数 | 说明 |
|------|------|
| `deploy_solution(client, solution, config?)` | 部署解决方案 |
| `plan_solution(client, solution)` | 生成解决方案部署计划 |
| `reverse_solution(client, solution_name)` | 从现有解决方案反向生成 |
| `resolve_publisher(client, publisher_name)` | 解析发布者信息 |

### 组件同步

| 函数 | 说明 |
|------|------|
| `sync_webresources(client, config?)` | 同步 Web Resources 目录 |
| `sync_forms(client, forms)` | 同步窗体（结构化模型 diff） |
| `sync_views(client, views)` | 同步视图（结构化模型 diff） |
| `sync_ribbons(client, ribbons)` | 同步 Ribbon（专用解决方案 export→import） |
| `sync_optionsets(client, optionsets)` | 同步全局选项集 |

### 工作流编排

| 函数 | 说明 |
|------|------|
| `deploy_workflow(client, project, stages?)` | 按顺序部署各阶段组件 |
| `plan_workflow(client, project)` | 生成完整工作流计划 |
| `lint_workflow(project)` | 检查工作流定义的正确性 |

### 完整 API 列表

参见 `framework_power/__init__.py` 的 `__all__` 导出列表。
