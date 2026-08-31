# Power Platform 元数据规范

## 概述

本规范涵盖两套元数据定义方式：

- **YAML 元数据** (`metadata/`) - legacy framework 的声明式 YAML 定义
- **Python API** (`metadata_py/` + `framework_power/`) - 现代化的类型化 Python API

推荐新项目使用 **Python API**，它提供更好的类型安全、IDE 支持和代码补全。

> 本规范只覆盖 **Python API（framework_power）** 作者契约；legacy YAML 规范随 `framework/`
> 于 2026-08-31 一并移除（历史版本见 git）。选项集（全局/本地）的建模方式见下方各字段类型节。

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
AttributeType.Integer      # 整数
AttributeType.BigInt       # 大整数
AttributeType.Money        # 货币
AttributeType.Decimal      # 小数
AttributeType.Double       # 双精度浮点
AttributeType.Picklist     # 选项集
AttributeType.Boolean      # 是/否
AttributeType.Memo         # 多行文本
AttributeType.DateTime     # 日期时间
AttributeType.File         # 文件
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

#### 全局选项集引用（Python 路径）

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
    referenced_entity="contact",          # 父表
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
- 文件名 stem = CLI 定义键（如 `new_projectbudget`）
- 全局选项集：`metadata_py/optionsets/<name>.py`，暴露模块级
  `OPTIONSET: GlobalOptionSet`（被表引用时由 deploy 自动加载，ADR-011）

### 开发流水线

```
需求 (docs/features/<feature>/01-prd)
  → design-dv-model → Excel 设计 (docs/features/<feature>/02-designs)
  → dv-model-to-python  → metadata_py/tables/<schema>.py   （AI 生成步骤）
  → (引用全局选项集时) metadata_py/optionsets/<name>.py
  → framework_power lint          （离线入口校验）
  → framework_power plan --env    （只读预演，含引用选项集 would_* 计划）
  → framework_power deploy --env  （依赖优先同步选项集 → 表同步到 Dataverse）
```

### Python 命名规则

> **与 YAML 路径不同！** YAML 路径使用小写命名（`new_payment_number`）。
> Python 路径使用 Dataverse 标准的 **PascalCase**，命名由作者自行负责 —
> CLI **不会**静默改写名称，`lint` 负责校验，`deploy` 原样部署。

| 元素 | 规则 | 示例 |
|---|---|---|
| 自定义表 `schema_name` | `{prefix_}{PascalCase}` | `new_ProjectBudget` |
| 自定义列 `schema_name` | `{prefix_}{PascalCase}` | `new_PaymentNumber` |
| 关系 `schema_name` | `{prefix_}_{Referenced}{Referencing}` | `new_ProjectBudget_Account` |
| Lookup 列 `schema_name` | `{prefix_}{PascalCase}` 以 `Id` 结尾 | `new_AccountId` |
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
| 日期和时间 | `DateTime` | 设置 `date_time_behavior`、`format` |
| Lookup | 通过 `Relationship` | 不是 `Column` |

### Required 级别

`RequiredLevel.ApplicationRequired` / `Recommended` / `None_`。
主名称列通常为 `ApplicationRequired`。

### 关系约束

- **仅限 Referential 级联**：Dataverse 每个实体只允许一个 Parental 级联，
  而 `UserOwned` 实体已通过 Owner 占用一个。切勿使用 `Cascade.Active`。
- 1:N 关系通过 Deep Insert 创建其 Lookup — **切勿将 Lookup 定义为独立的 `Column`**。
- `lookup.target_entity` 必须等于 `referenced_entity`。
- 被引用的实体必须在目标环境中已存在（deploy 会检查此条件）。

### 结构规则（lint 强制执行）

- **有且仅有一个主名称**：一个 `String` 列设置 `is_primary_name=True`
  （或设置 `Table.primary_name_column`）。零个 String 列为错误。
- 列 `schema_name` 不重复（大小写不敏感）
- Picklist 选项值不重复（同一列内）
- 关系 `schema_name` 不重复
- 每个自定义 `schema_name` 以发布商前缀开头

### 编写后校验

```bash
pp lint new_projectbudget          # 离线；必须 0 错误
pp plan new_projectbudget --env dev    # 只读差异预览
pp deploy new_projectbudget --env dev  # 实际同步
```

`lint` 是约束入口：在 `plan`/`deploy` 之前必须报告 **0 错误**。
警告（如命名风格）属于建议性质，但仍应修复。

### 定义位置与注册表

- 每表一个文件：`metadata_py/tables/<schema_lowercase>.py`
- 每个文件暴露一个模块级变量 `TABLE: Table`（注册表通过此变量自动发现定义）
- 文件名 stem = CLI 使用的定义键（如文件名 `new_projectbudget.py` → CLI 中使用 `new_projectbudget`）

### 开发流水线

```
需求 (docs/features/<feature>/01-prd)
  → design-dv-model → Excel 设计 (docs/features/<feature>/02-designs)
  → dv-model-to-python  → metadata_py/tables/<schema>.py   （AI 生成步骤）
  → framework_power lint          （离线入口校验）
  → framework_power plan --env    （只读预演）
  → framework_power deploy --env  （同步到 Dataverse）
```

### 命名规则 — Python 路径

> **关键差异**：YAML 路径使用小写命名（`new_payment_number`），Python 路径使用 Dataverse 标准的
> **PascalCase**。命名由作者自行负责 — CLI **不会**静默改写名称，`lint` 负责校验，
> `deploy` 原样部署。

| 元素 | 规则 | 示例 |
|---|---|---|
| 自定义表 `schema_name` | `{prefix_}{PascalCase}` | `new_ProjectBudget` |
| 自定义列 `schema_name` | `{prefix_}{PascalCase}` | `new_PaymentNumber` |
| 关系 `schema_name` | `{prefix_}_{Referenced}{Referencing}` | `new_ProjectBudget_Account` |
| Lookup 列 `schema_name` | `{prefix_}{PascalCase}` 以 `Id` 结尾 | `new_AccountId` |
| 标准实体（扩展） | 保持逻辑名称 | `account` |

发布商前缀来自 `config/publishers.yaml`，默认为 `new`。

> **`*Id` 冲突陷阱**：普通列名为 `new_FooId` 会与后续添加的 Lookup 列 `new_FooId`
> 冲突。源系统 ID 请使用 `new_SrcFooId`。

### 类型映射（Excel → `AttributeType`）

| Excel 类型 | `AttributeType` | 说明 |
|---|---|---|
| 文本 / 电子邮件 / 电话 / URL | `String` | 通过 `format_name` 设置 Email/Phone/Url |
| 多行文本 | `Memo` | `max_length` |
| 整数 | `Integer` | `min_value`/`max_value` |
| 小数 | `Decimal` | `precision` |
| 货币 | `Money` | `precision`、`precision_source=2` |
| 浮点数 | `Double` | `precision` |
| 是/否 | `Boolean` | `boolean_labels`、`default_value` |
| 选项集（本地） | `Picklist` | `options=[Option(value, Label...)]` |
| 日期和时间 | `DateTime` | `date_time_behavior`、`format` |
| Lookup | （通过 `Relationship`） | 不是 `Column` |

### Required 级别

`RequiredLevel.ApplicationRequired` / `Recommended` / `None_`。
主名称列通常为 `ApplicationRequired`。所有 `Column` 定义中通过 `required=` 参数设置。

### 结构规则（lint 强制执行）

`pp lint` 在部署前进行离线校验，以下规则零容忍：

- **有且仅有一个主名称**：一个 `String` 列设置 `is_primary_name=True`（或设置
  `Table.primary_name_column`）。若未指定，自动选取第一个 String 列。零个 String 列为错误。
- **列 schema_name 不重复**（大小写不敏感）。
- **Picklist 选项值不重复**（同一列内）。
- **关系 schema_name 不重复**。
- 每个自定义 `schema_name` 以发布商前缀开头。

### 关系级联约束

自定义 Lookup 必须使用 **Referential** 级联（Dataverse 每个实体只允许一个 Parental 级联，
而 `UserOwned` 实体已通过 Owner 占用一个）。切勿使用 `Cascade.Active`。

```python
Relationship(
    schema_name="new_ProjectBudget_Account",
    referenced_entity="account",              # 父表（1 端），逻辑名称
    referencing_entity="new_projectbudget",   # 本表，逻辑名称
    lookup=LookupColumn("new_AccountId",
        Label.bilingual("客户","Account"),
        target_entity="account"),
    cascade=CascadeConfig(delete=Cascade.RemoveLink, assign=Cascade.NoCascade),
)
```

- 1:N 关系通过 Deep Insert 创建其 Lookup — 切勿将 Lookup 定义为独立的 `Column`。
- `lookup.target_entity` 必须等于 `referenced_entity`。
- 被引用的实体必须在目标环境中已存在（deploy 会检查）。

### 编写后校验

```bash
pp lint new_projectbudget         # 离线；必须 0 错误
pp plan new_projectbudget --env dev    # 只读差异预览
pp deploy new_projectbudget --env dev  # 实际同步
```

`lint` 是部署入口：必须报告 **0 错误** 才能执行 `plan`/`deploy`。
警告（如命名风格）属于建议性质，但仍应修复。

---

## 表 (Table) 元数据 (YAML)

### 必需字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema.schema_name` | string | 表的Schema名称（自动加前缀） |
| `schema.display_name` | string | 显示名称 |
| `schema.ownership_type` | string | 所有者类型 |

### 可选字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `schema.description` | string | - | 表描述 |
| `schema.has_activities` | boolean | false | 是否启用活动 |
| `schema.has_notes` | boolean | false | 是否启用注释 |

### 字段类型

支持的字段类型：

| 类型 | 说明 | 特殊属性 |
|------|------|----------|
| `String` | 字符串 | `max_length` |
| `Integer` | 整数 | `min_value`, `max_value` |
| `Money` | 货币 | `precision`, `min_value` |
| `Picklist` | 选项集 | `option_set_ref` 或 `local_options` |
| `MultiSelectPicklist` | 多选选项集 | `options` |
| `Lookup` | 查找 | `entity`, `relationship_name` |
| `Customer` | 客户查找 | - |
| `Owner` | 所有者查找 | - |
| `DateTime` | 日期时间 | - |
| `Boolean` | 是/否 | - |
| `Memo` | 多行文本 | `max_length` |
| `Decimal` | 小数 | `precision`, `min_value`, `max_value` |
| `Double` | 双精度浮点 | `min_value`, `max_value` |
| `BigInt` | 大整数 | `min_value`, `max_value` |

### Picklist 字段详细规范

Picklist 类型字段必须使用以下两种方式之一定义选项：

**方式一：引用全局选项集 (推荐)**

```yaml
- name: customer_status
  type: Picklist
  display_name: 客户状态
  required: true
  option_set_ref: new_customer_status
```

**方式二：本地选项集**

```yaml
- name: region
  type: Picklist
  display_name: 地区
  required: false
  local_options:
    - value: 1
      label: 华东
      color: 008000
    - value: 2
      label: 华南
```

### 字段虚拟属性

用于标识特殊字段的属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `is_calculated` | boolean | 标识为计算字段 |
| `aggregate_type` | string | 汇总字段类型 (如: sum, count) |
| `is_primary_name` | boolean | 是否为主名称字段 |

**注意**：包含以上属性的虚拟字段在生成数据字典时会被自动过滤。

## 表单 (Form) 元数据

### 表单类型

- `Main` - 主表单
- `QuickCreate` - 快速创建表单
- `QuickView` - 快速视图表单
- `Card` - 卡片表单
- `MainInteraction` - 交互对话框

### 结构定义

```yaml
form:
  schema_name: "account_main_form"
  entity: "account"
  type: "Main"
  display_name: "账户主表单"

  tabs:
    - name: "general"
      display_name: "常规"
      sections:
        - name: "basicInfo"
          display_name: "基本信息"
          rows:
            - cells:
                - attribute: "name"
                  width: "1"
```

## 视图 (View) 元数据

### 视图类型

- `PublicView` - 公共视图
- `PrivateView` - 私有视图
- `AdvancedFind` - 高级查找视图
- `AssociatedView` - 关联视图
- `QuickFindView` - 快速查找视图
- `LookupView` - 查找视图

### Fetch XML 操作符

支持的操作符：

- `eq` - 等于
- `ne` - 不等于
- `gt` - 大于
- `ge` - 大于等于
- `lt` - 小于
- `le` - 小于等于
- `like` - 相似
- `in` - 包含于
- `between` - 介于
- `null` - 为空
- `today` - 今天
- `this-week` - 本周
- `this-month` - 本月
- `this-year` - 今年

## Web Resource 元数据

### 资源类型

| 类型 | 扩展名 | MIME类型 |
|-----|--------|---------|
| CSS | .css | text/css |
| JavaScript | .js | text/javascript |
| HTML | .html | text/html |
| PNG | .png | image/png |
| JPEG | .jpg | image/jpeg |
| GIF | .gif | image/gif |
| SVG | .svg | image/svg+xml |
| ICO | .ico | image/x-icon |
| XAP | .xap | application/x-silverlight-app |
| XML | .xml | text/xml |
| XSLT | .xslt | text/xslt |

### 命名模式

```
{prefix}{category}/{name}.{ext}
```

示例：
- `new_css/account_form.css`
- `new_js/account_handler.js`
- `new_html/dashboard.html`

## Ribbon (命令栏) 元数据

### 按钮位置

位置格式：`Mscrm.{Location}.{Entity}.{Tab}.{Group}`

常用位置：
- `Mscrm.HomepageGrid.{entity}.MainTab.Actions` - 主页网格操作
- `Mscrm.Form.{entity}.MainTab.Actions` - 表单操作
- `Mscrm.HomepageGrid.{entity}.ContextMenu` - 右键菜单

### 命令类型

- `javascript` - JavaScript 函数
- `popup` - 弹出窗口
- `navigation` - 导航到 URL
- `event` - 触发事件

### 规则类型

显示规则：
- `selectioncount` - 选择计数
- `customrule` - 自定义规则
- `entityrule` - 实体规则
- `formrule` - 表单规则

启用规则：
- `customrule` - 自定义规则
- `formrule` - 表单规则
- `ocrulerule` - OCR 规则

## Sitemap (应用导航) 元数据

### 子区域类型

- `entity` - 实体列表
- `dashboard` - 仪表板
- `webresource` - Web Resource 页面
- `url` - 外部 URL

### 结构定义

```yaml
sitemap:
  schema_name: "customer_app_sitemap"
  display_name: "客户管理应用"

  areas:
    - name: "customerArea"
      display_name: "客户区域"
      groups:
        - name: "customerGroup"
          display_name: "客户管理"
          subareas:
            - name: "account"
              type: "entity"
              entity: "account"
              default_view: "account_active_view"
```

## 插件元数据

### 消息阶段

- `pre-validation` - 验证前 (Stage 10)
- `pre-operation` - 操作前 (Stage 20)
- `post-operation` - 操作后 (Stage 40)

### 执行模式

- `0` - 同步
- `1` - 异步

### 部署类型

- `0` - 仅服务器端
- `1` - 仅 Microsoft Dynamics 365 for Outlook
- `2` - 两者

## 关系类型

### OneToMany 属性

- `cascade_assign` - 级联分配
- `cascade_delete` - 级联删除
- `cascade_reparent` - 级联重新分配父级
- `cascade_share` - 级联共享
- `cascade_unshare` - 级联取消共享

### 级联类型

- `NoCascade` - 无操作
- `Cascade` - 级联
- `Active` - 激活级联
- `RemoveLink` - 移除链接
- `Restrict` - 限制

### Deep Insert 模式

Lookup 字段和关系通过 Deep Insert 一次性创建：

1. Lookup 属性定义在 `lookup_attributes` 中
2. 关系定义在 `relationships` 中
3. 创建关系时，Lookup 属性自动嵌入关系定义
4. 一次 API 调用同时创建关系和查找字段

## 标准实体保护

以下标准实体不会被命名转换影响：

系统核心：`account`, `contact`, `systemuser`, `team`, `businessunit`, `role`

活动相关：`activitypointer`, `email`, `appointment`, `task`, `phonecall`, `letter`, `fax`

销售相关：`lead`, `opportunity`, `competitor`, `quote`, `salesorder`, `invoice`

完整列表请参考 `config/publishers.yaml` 中的 `naming.standard_entities`。

---

## 元数据文件组织

### 项目目录结构

```
power-platform-agent/
├── framework_power/       # 引擎层 - Python-first 部署库（唯一引擎）
│   ├── __init__.py        # Public API 导出
│   ├── models.py          # 类型化数据模型 (Label, Table, Column...)
│   ├── serializer.py      # 模型序列化器
│   ├── deployer.py        # 表部署逻辑
│   ├── solution_deployer.py # 解决方案管理
│   ├── workflow.py        # 跨阶段工作流编排
│   ├── client/            # API 客户端
│   │   ├── dataverse_client.py
│   │   ├── auth.py
│   │   └── env_config.py
│   ├── components/        # 组件模型注册表
│   │   ├── models.py      # Form, View, Ribbon, Plugin, WebResource...
│   │   ├── optionset_sync.py
│   │   ├── webresource_sync.py
│   │   ├── form_sync.py
│   │   ├── view_sync.py
│   │   └── ribbon_sync.py
│   └── plugins/           # .NET 插件相关
│       └── plugin_build.py
│
├── metadata_py/           # Python 元数据定义 - 类型安全定义
│   ├── tables/           # 表定义 (*.py)
│   ├── optionsets/       # 全局选项集定义 (*.py)
│   ├── forms/            # 表单定义 (*.py)
│   ├── views/            # 视图定义 (*.py)
│   ├── ribbons/          # 命令栏定义 (*.py)
│   └── roles/            # 安全角色定义 (*.py)
│
├── metadata/              # 元数据层 - YAML 定义 (legacy)
│   ├── _schema/           # Schema 定义文件
│   ├── tables/            # 表定义 (*.yaml)
│   ├── forms/             # 表单定义 (*.yaml)
│   ├── views/             # 视图定义 (*.yaml)
│   ├── optionsets/        # 选项集定义
│   ├── webresources/      # Web Resource 配置
│   ├── ribbon/            # 命令栏定义
│   └── sitemap/           # 应用导航定义
│
├── docs/                  # 文档层
│   ├── features/          # 按功能迭代组织（PRD/设计/输出）
│   ├── templates/         # 需求文档模板库 (PRD/实体设计/Excel)
│   ├── data_dictionary/   # Workspace 产物，从云端同步或脚本生成
│   ├── spec/              # 规范文档
│   └── guides/            # 使用指南
│
├── scripts/               # 脚本层
│   ├── generate_data_dictionary.py
│   └── hooks/             # Git hooks
│
├── config/                # 配置文件
├── plugins/               # .NET插件
├── webresources/          # Web资源源文件
└── .claude/               # Claude Code配置
```

### 命名规范

**文件命名**：
- 使用小写字母和下划线
- 表定义文件: `{schema_name}.yaml`
- 例如: `account.yaml`, `contact.yaml`

**Schema 引用**：
```yaml
# 表定义文件顶部引用 Schema
$schema: "../_schema/table_schema.yaml"
```

---

## 数据字典生成

### 自动生成

项目配置了 Git pre-commit hook，在提交 Gen 1 YAML 元数据（`metadata/`）变更时自动生成数据字典。`metadata_py/`（Gen 2 Python 定义）的变更不触发此 hook。

### 手动生成

**路径 1：MCP 工具（推荐，从 Dataverse 云端导出）**

```
调用工具: metadata_export_dictionary
参数: output_dir="docs/data_dictionary", environment="dev"
```

**路径 2：本地脚本（Legacy，从 Gen 1 YAML 生成）**

```bash
# 生成所有文档
python scripts/generate_data_dictionary.py --all

# 生成指定文件
python scripts/generate_data_dictionary.py --files metadata/tables/account.yaml
```

> 注意：此脚本读取 `metadata/*.yaml`（Gen 1 YAML），不适用于 `metadata_py/` Python 定义。

### 生成内容

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

项目提供多种复用机制，减少重复定义：

### 需求文档模板 (docs/templates)

位于 `docs/templates/`，为 Feature 需求编写提供标准化模板：

| 模板文件 | 用途 |
|---------|------|
| `FEATURE_STRUCTURE.md` | Feature 目录结构约定（01-prd → 02-design → 03-implementation → 04-output） |
| `PRD_TEMPLATE.md` | PRD 主模板（背景、流程、实体设计、业务规则、实现计划等 9 个章节） |
| `ENTITY_DESIGN.md` | Dataverse 实体设计模板（字段、Picklist、Lookup、Python 实现参考） |

创建新 Feature 时，复制对应模板到 `docs/features/{feature-name}/` 后填写即可。

### Python 组合复用 (framework_power)

Python 原生支持 import，复用自然且类型安全：

```python
# metadata_py/shared/audit_fields.py
from framework_power import Column, Label, AttributeType, RequiredLevel

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

---

## 开发工作流

### 初始化流程

1. 在 `metadata/tables/` 下创建 YAML 定义文件
2. （可选）使用 `metadata_plan` 预览变更
3. 使用 `metadata_apply_yaml` 应用到 Dataverse

### 迭代流程

1. 修改 YAML 文件
2. 调用 `metadata_apply_yaml` — Agent 自动计算差异
3. 仅应用变更的部分，无需删除重建

> 完整的 MCP 工具清单和部署工作流详见 [元数据部署文档](../metadata-deploy.md)。

---

## 完整 YAML 示例

以下是一个完整的发票表定义，涵盖常用字段类型和关系：

```yaml
$schema: "../_schema/table_schema.yaml"

schema:
  schema_name: "new_invoice"
  display_name: "发票"
  description: "销售发票信息"
  ownership_type: "UserOwned"
  has_activities: true
  has_notes: true

attributes:
  # 主名称字段
  - name: "new_invoice_number"
    type: "String"
    display_name: "发票号"
    max_length: 50
    required: true
    is_primary_name: true

  # 日期字段
  - name: "new_invoice_date"
    type: "DateTime"
    display_name: "发票日期"
    required: true
    date_only: true

  # 货币字段
  - name: "new_amount"
    type: "Money"
    display_name: "发票金额"
    required: true
    precision: 2
    min_value: 0

  # 本地选项集
  - name: "new_status"
    type: "Picklist"
    display_name: "发票状态"
    required: true
    options:
      - value: 100000000
        label: "草稿"
        color: "#808080"
      - value: 100000001
        label: "待审核"
        color: "#FFFF00"
      - value: 100000002
        label: "已审核"
        color: "#008000"

  # 多行文本
  - name: "new_notes"
    type: "Memo"
    display_name: "备注"
    max_length: 2000

# 查找字段
lookup_attributes:
  - name: "new_customerid"
    type: "Lookup"
    display_name: "客户"
    description: "关联客户"
    required: true
    target: "account"

# 关系定义
relationships:
  - name: "account_new_invoice"
    related_entity: "account"
    relationship_type: "ManyToOne"
    display_name: "客户发票"
    referencing_attribute: "new_customerid"
    cascade_assign: "Cascade"
    cascade_delete: "RemoveLink"
    cascade_reparent: "Cascade"
    cascade_share: "Cascade"
    cascade_unshare: "Cascade"
```

---

## 差异检测与变更应用

### 差异检测算法

当调用 `metadata_apply_yaml` 时，Agent 执行以下步骤：

1. 获取当前状态 — 通过 Dataverse API 查询目标环境中的现有元数据
2. 解析期望状态 — 从 YAML 文件中解析目标定义
3. 逐项比较：
   - 实体级别：检查表是否已存在
   - 属性级别：检查每个字段的显示名、描述、必填状态等
   - 关系级别：检查关系和级联配置
4. 生成变更列表 — 明确哪些需要创建、哪些需要更新

### 变更应用顺序

为确保依赖关系正确，变更按以下顺序执行：

1. 创建实体（如不存在）
2. 创建普通属性（非 Lookup）
3. 创建关系（通过 Deep Insert，同时创建 Lookup）

### 自动检测的变更类型

| 差异场景 | Agent 行为 |
|----------|-----------|
| 实体不存在 | 创建实体 |
| 属性不存在 | 创建属性 |
| 属性显示名/描述/必填状态变更 | 更新属性 |
| 关系不存在 | 创建关系（Deep Insert） |
| 关系级联配置变更 | 更新关系 |
| 选项集选项变更 | 更新选项集 |

---

## 错误处理

### 常见错误及处理

| 错误场景 | Agent 行为 |
|----------|-----------|
| 属性已存在 | 自动检测并跳过 |
| 关系创建失败 | 检查引用的实体是否存在、关系名称是否正确 |
| 全局选项集不存在 | 确保目标环境中已创建对应的全局选项集 |

### 错误处理策略

- **部分失败继续执行**：单个字段或关系失败不会中断整个部署
- **详细成功/失败列表**：返回每个操作的执行结果，方便定位问题
- **错误追踪信息**：提供完整的错误消息供调试

### 错误响应格式

```json
{
  "success": false,
  "entity": "new_payment_recognition",
  "failed": [
    {
      "type": "relationship",
      "action": "create",
      "name": "invalid_relationship",
      "error": "Referenced entity not found"
    }
  ]
}
```

---

## 相关文档

- [架构文档](architecture.md) - 系统架构设计
- [元数据部署](../metadata-deploy.md) - 完整部署工作流和 MCP 工具参考
- [快速开始](../guides/getting-started.md) - 详细入门指南
- [数据字典](../data_dictionary/index.md) - Workspace 产物，从 Dataverse 云端同步的数据字典索引

## framework_power API 参考

### 核心部署 API

| 函数 | 说明 |
|------|------|
| `deploy_table(client, table, config?)` | 部署表到 Dataverse |
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
| `sync_webresources(client, config?)` | 同步 Web Resources |
| `sync_forms(client, config?)` | 同步表单 |
| `sync_views(client, config?)` | 同步视图 |
| `sync_ribbons(client, config?)` | 同步 Ribbon 定义 |
| `sync_optionsets(client, config?)` | 同步全局选项集 |

### 工作流编排

| 函数 | 说明 |
|------|------|
| `deploy_workflow(client, project, stages?)` | 按顺序部署各阶段组件 |
| `plan_workflow(client, project)` | 生成完整工作流计划 |
| `lint_workflow(project)` | 检查工作流定义的正确性 |

### 完整 API 列表

参见 `framework_power/__init__.py` 的 `__all__` 导出列表。
