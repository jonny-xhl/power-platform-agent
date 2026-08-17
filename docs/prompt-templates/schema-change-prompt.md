# Power Platform 表结构变更 — 标准请求 Prompt

> 复制以下模板，填入参数后发送即可。AI 会自动选择正确的部署策略（增量 / 全量）。
>
> **引擎级模板**：适用于任何 workspace。Workspace 专属信息（解决方案名、命名前缀、publisher）
> 请从 `pp-workspace.yaml` 和 `config/` 目录获取。

---

## 模板 A：新增字段（单字段 / 多字段）

```
给 {实体中文名}（{实体英文名}）新增字段：

| 字段中文 | 字段英文 | 字段名 | 类型 | 必填 | 默认值 | 其他约束 |
|----------|----------|--------|------|------|--------|----------|
| {中文名} | {EnglishName} | {prefix}_{field_name} | {类型} | {是/否} | {值} | {精度/最大长度/选项值等} |

解决方案：{solution_name}
```

### 类型说明

| 类型 | 关键字 | 额外约束（选填） | 示例 |
|------|--------|------------------|------|
| 单行文本 | String | max_length, format_name | `max_length=255, format_name=Text` |
| 多行文本 | Memo | max_length | `max_length=2000` |
| 整数 | Integer | min_value, max_value | `min_value=0, max_value=100` |
| 小数 | Decimal | precision, min_value, max_value | `precision=2` |
| 货币 | Money | precision, min_value, max_value | `precision=2` |
| 布尔 | Boolean | default_value, true/false标签 | `default_value=False` |
| 选项集 | Picklist | 选项值列表 或 global optionset名 | `草稿:1; 已批准:2` |
| 日期时间 | DateTime | format, date_time_behavior | `format=DateOnly` |
| 查找 | Lookup | 目标实体 | `目标实体: account` |

### 示例

```
给 备件销售订单（new_spare_salesorder）新增字段：

| 字段中文 | 字段英文 | 字段名 | 类型 | 必填 | 默认值 | 其他约束 |
|----------|----------|--------|------|------|--------|----------|
| 打包备注 | Remark | new_package_remark | String | 否 | | max_length=255 |

解决方案：new_entity_core
```

```
给 回款计划明细（new_collection_plan_detail）新增多个字段：

| 字段中文 | 字段英文 | 字段名 | 类型 | 必填 | 默认值 | 其他约束 |
|----------|----------|--------|------|------|--------|----------|
| 审核状态 | Approval Status | new_approval_status | Picklist | 是 | | 草稿:1; 已审核:2; 已驳回:3 |
| 审核日期 | Approval Date | new_approval_date | DateTime | 否 | | format=DateOnly |
| 审核人 | Approved By | new_approvedby | Lookup | 否 | | 目标实体: systemuser |

解决方案：new_entity_core
```

---

## 模板 B：创建新表

```
创建新表：

表名（中文）：{中文名}
表名（英文）：{EnglishName}
表名（字段名）：{prefix}_{table_name}
所有权类型：{UserOwned/Organization}
启用活动：{是/否}
启用审计：{是/否}

字段列表：
| 字段中文 | 字段英文 | 字段名 | 类型 | 必填 | 主名称字段 | 其他约束 |
|----------|----------|--------|------|------|-----------|----------|
| {中文名} | {EnglishName} | {prefix}_{xxx} | {类型} | {是/否} | {是/否} | {...} |

查找关系（如有）：
| 关系名称 | 目标实体 | 显示名称 | 必填 | 级联 |
|----------|----------|----------|------|------|
| {prefix}_{rel_name} | {target_entity} | {显示名} | {是/否} | merge=NoCascade |

解决方案：{solution_name}
```

### 示例

```
创建新表：

表名（中文）：质保工单
表名（英文）：Warranty Work Order
表名（字段名）：new_warranty_workorder
所有权类型：UserOwned
启用活动：是
启用审计：是

字段列表：
| 字段中文 | 字段英文 | 字段名 | 类型 | 必填 | 主名称字段 | 其他约束 |
|----------|----------|--------|------|------|-----------|----------|
| 工单编号 | Work Order No | new_workorderno | String | 是 | 是 | max_length=100 |
| 工单状态 | Status | new_status | Picklist | 是 | | 待处理:1; 处理中:2; 已完成:3 |
| 报修日期 | Report Date | new_reportdate | DateTime | 是 | | format=DateOnly |
| 预估费用 | Estimated Cost | new_estimatedcost | Money | 否 | | precision=2 |
| 是否加急 | Is Urgent | new_isurgent | Boolean | 否 | False | |

查找关系：
| 关系名称 | 目标实体 | 显示名称 | 必填 | 级联 |
|----------|----------|----------|------|------|
| new_warranty_workorder_customerid_account | account | 客户 | 是 | merge=NoCascade |
| new_warranty_workorder_contactid_contact | contact | 联系人 | 否 | merge=NoCascade |

解决方案：new_entity_core
```

---

## 模板 C：修改已有字段属性

```
修改 {实体中文名}（{实体英文名}）的已有字段：

| 字段名 | 修改项 | 原值 | 新值 |
|--------|--------|------|------|
| {field_name} | {修改项} | {旧值} | {新值} |

解决方案：{solution_name}
```

> ⚠️ 注意：普通可变属性由引擎计算最小差异，再通过 typed GET → retrieve-modify-`PUT` 更新完整字段元数据。已有本地 Picklist 的新增值和声明语言标签变更由引擎自动使用 `InsertOptionValue` / `UpdateOptionValue` 增量同步，远端额外值默认保留；字段类型等不兼容变更仍需备份、删除并重建字段。

### 示例

```
修改 备件销售订单（new_spare_salesorder）的已有字段：

| 字段名 | 修改项 | 原值 | 新值 |
|--------|--------|------|------|
| new_package_remark | MaxLength | 100 | 500 |
| new_order_status | RequiredLevel | none | required |

解决方案：new_entity_core
```

---

## 模板 D：逆向导出 / 数据字典更新

```
逆向导出 {实体中文名}（{实体英文名}）的数据字典

环境：{dev/uat/prod}
```

或批量更新全部数据字典：

```
重新生成所有表的数据字典

环境：{dev/uat/prod}
```

---

## 快速参考

### 部署策略自动判定

| 场景 | 策略 | 命令 |
|------|------|------|
| 新增字段到已有表 | 增量部署 (`--fields`) | `pp deploy {table} --fields {f1,f2} --solution {sol}` |
| 创建新表 | 全量部署 | `pp deploy {table} --solution {sol}` |
| 修改字段属性 | 增量字段同步（typed GET + PUT） | `pp deploy {table} --fields {f1,f2} --solution {sol}` |
| 新增/重命名本地 Choice 选项 | 增量选项同步（Insert/UpdateOptionValue；不隐式删除） | `pp deploy {table} --fields {choice_field} --solution {sol}` |
| 逆向导出 + 数据字典 | reverse | `pp reverse {table} --env {env} --dictionary` |

### 字段命名规范

命名前缀（`{prefix}`）从 workspace 的 `pp-workspace.yaml` → `publisher_prefix` 获取。

- **字段名（LogicalName）**：`{prefix}_` 前缀 + 小写下划线，如 `new_send_email`
- **SchemaName**：`{prefix}_` 前缀 + PascalCase，如 `new_SendEmail`
- **字段英文**：自然英文，如 `Send Email`
- **关系名称**：`{prefix}_{referencing}_{lookup_field}_{referenced}`，如 `new_quote_customerid_account`

### 查找 Workspace 可用解决方案

发送 prompt 前，AI 应自动读取以下文件获取 workspace 专属信息：

| 文件 | 内容 |
|------|------|
| `pp-workspace.yaml` | `main_solution`（主解决方案）、`publisher`、`publisher_prefix` |
| `metadata_py/project.py` | 全部已注册的表和解决方案映射 |
| `config/` | publishers.yaml、pipeline.yaml（环境→解决方案映射） |

---

## 选项集 & 布尔值多语言规范

> **引擎完全支持多语言标签**：`Label` 模型支持 `Label.bilingual(中, en)` 构造器，
> `serialize_label()` 会生成完整的 `LocalizedLabels` 数组（LanguageCode: 2052=zh-CN, 1033=en-US），
> 逆向导出和数据字典也会保留双语言。

### Picklist（选项集）选项值格式

选项值同时支持单语言简写和多语言写法。**建议始终使用多语言写法**。

#### 简写格式（默认中文）

```
草稿:1; 已批准:2; 已驳回:3
```

→ AI 会生成 `Option(1, Label.zh("草稿"))` — 只有中文标签，英文环境会回退显示中文。

#### 多语言格式（推荐）

```
草稿/Draft:1; 已批准/Approved:2; 已驳回/Rejected:3
```

→ AI 会生成 `Option(1, Label.bilingual("草稿", "Draft"))` — 中英文环境各自显示对应标签。

#### 引用全局选项集

如果选项值引用的是已有的全局选项集（Global OptionSet），直接写名称：

```
global: new_order_status
```

→ AI 会生成 `Column(..., optionset_name="new_order_status")`，不内联选项值，
数据字典中以文档链接展示。

### Boolean（布尔值）标签格式

布尔值默认标签是 `True=是, False=否`（引擎自动填充）。如需自定义标签：

#### 简写格式（默认中文）

```
default_value=False, True=启用, False=禁用
```

#### 多语言格式（推荐）

```
default_value=False, True=启用/Enabled, False=禁用/Disabled
```

### 多语言语法解析规则

AI 解析选项值/布尔标签时，按以下规则处理：

| 格式 | 解析结果 | 示例 |
|------|---------|------|
| `标签:值` | 单语言（zh-CN） | `草稿:1` → `Option(1, Label.zh("草稿"))` |
| `中文/英文:值` | 双语言（zh-CN / en-US） | `草稿/Draft:1` → `Option(1, Label.bilingual("草稿", "Draft"))` |
| `global: 名称` | 全局选项集引用 | `global: new_status` → `optionset_name="new_status"` |
| `True=中文/英文` | 布尔值 True 标签 | `True=启用/Enabled` → `Label.bilingual("启用", "Enabled")` |
| 不指定 | 布尔值使用默认 | → `True=是/Yes, False=否/No` |

### 支持的语言代码

| 语言 | LanguageCode | 引擎常量 |
|------|-------------|---------|
| 简体中文 | 2052 | `LANGUAGE_ZH_CN` |
| English (US) | 1033 | `LANGUAGE_EN_US` |

> 目前引擎内置 `Label.zh()` / `Label.en()` / `Label.bilingual()` 三个快捷构造器。
> 如需三语以上（如日文 1041），可扩展 `LocalizedLabel` 列表直接构造。

### 多语言 Picklist 示例

```
给 备件销售订单（new_spare_salesorder）新增字段：

| 字段中文 | 字段英文 | 字段名 | 类型 | 必填 | 默认值 | 其他约束 |
|----------|----------|--------|------|------|--------|----------|
| 审核状态 | Approval Status | new_approval_status | Picklist | 是 | | 草稿/Draft:1; 已审核/Approved:2; 已驳回/Rejected:3 |
| 物流方式 | Shipping Method | new_shipping_method | Picklist | 否 | | global: new_shipping_type |

解决方案：new_entity_core
```

AI 会生成：

```python
Column("new_approval_status", AttributeType.Picklist,
    display_name=Label.bilingual("审核状态", "Approval Status"),
    required=RequiredLevel.ApplicationRequired,
    options=[
        Option(1, Label.bilingual("草稿", "Draft")),
        Option(2, Label.bilingual("已审核", "Approved")),
        Option(3, Label.bilingual("已驳回", "Rejected")),
    ],
),
Column("new_shipping_method", AttributeType.Picklist,
    display_name=Label.bilingual("物流方式", "Shipping Method"),
    optionset_name="new_shipping_type",
),
```
