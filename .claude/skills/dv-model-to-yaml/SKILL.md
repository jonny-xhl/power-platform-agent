---
name: dv-model-to-yaml
description: 将Excel实体设计转换为YAML元数据文件。当用户需要将Excel中的Dataverse实体定义转换成YAML格式、将设计文档转换为代码、Excel转YAML、实体设计转元数据时使用此技能。包括"转换Excel"、"生成YAML"、"Excel转元数据"、"设计文档转YAML"等短语，或处理Power Platform/Dataverse元数据转换时。
---

# Excel实体设计转YAML元数据

此技能将Excel中的Dataverse实体设计转换为符合Schema规范的YAML元数据文件，并保存到正确的metadata目录。

**重要提示**:
1. 始终参考 `metadata/_schema/table_schema.yaml` 确保生成的YAML符合规范
2. 生成的YAML文件必须放在 `metadata/tables/` 目录下
3. 选项集需要独立管理，放在 `metadata/optionsets/` 目录
4. 复杂转换逻辑可以借助 `transformers/` 层的能力

## 使用场景

在以下情况使用此技能：
- 将Excel实体设计转换为YAML元数据
- 从设计文档生成Dataverse表定义
- 批量转换多个实体设计
- 将Excel中的选项集转换为独立的YAML文件
- 验证Excel设计是否符合YAML Schema规范

## 命名规则处理

根据 `config/naming_rules.yaml` 配置，YAML中的name字段应直接使用符合规则的Schema Name：

### 命名规则配置

| 配置项 | 当前值 | 说明 |
|--------|--------|------|
| prefix | "new" | 发布商前缀 |
| style | "lowercase" | 命名风格 (lowercase/camelCase/PascalCase) |
| separator | "_" | 分隔符 |
| auto_prefix | true | 自动添加前缀 |

### YAML中的name格式要求

**重要**: 生成的YAML中，name字段应直接使用符合命名规则的Schema Name，而非原始名称。

| 类型 | name格式示例 | 说明 |
|------|-------------|------|
| 自定义实体 | `new_payment_recognition` | {prefix}_{lowercase_name} |
| 标准实体 | `account` | 保持原名 |
| 自定义字段 | `new_payment_amount` | {prefix}_{lowercase_name} |
| 标准实体自定义字段 | `new_account_number` | 即使是标准实体的自定义字段也需加前缀 |
| 关系名称 | `new_payment_customer` | {prefix}_{relationship_name} |

### 转换示例

Excel中的原始名称 → YAML中的name字段：

| Excel原始名称 | YAML name (lowercase风格) |
|--------------|--------------------------|
| PaymentRecognition | new_payment_recognition |
| Order Detail | new_order_detail |
| accountType | new_account_type |
| customer (标准) | customer |
| account (标准) | account |

### 字段名转换规则

Excel中的字段名 → YAML中的name字段：

| Excel字段名 | YAML name |
|-----------|-----------|
| PaymentNumber | new_payment_number |
| Customer Type | new_customer_type |
| FirstName | new_first_name |
| Balance | new_balance |
**Form Schema**: `metadata/_schema/form_schema.yaml`
**View Schema**: `metadata/_schema/view_schema.yaml`

### 表Schema结构

```yaml
$schema: "../../_schema/table_schema.yaml"

schema:
  schema_name: "new_payment_recognition"  # 表名: {prefix}_{lowercase_name}
  display_name: "认款单"                   # 中文显示名
  description: "表描述"
  ownership_type: "UserOwned"

  options:
    import_dependencies: false
    create_audit_fields: true

attributes:
  - schema_name: "new_payment_number"    # 字段名: {prefix}_{lowercase_name}
    type: "String"
    display_name: "认款单号"
    required: true
    max_length: 100
    is_primary_name: true

  - schema_name: "new_payment_amount"
    type: "Money"
    display_name: "认款金额"
    required: true

relationships:
  - schema_name: "new_payment_customer"  # 关系名: {prefix}_{relationship_name}
    related_entity: "account"
    relationship_type: "ManyToOne"
    referencing_attribute: "new_customerid"
```

## 输出文件位置

### 表定义
```
metadata/tables/
└── {table_name}.yaml          # 表YAML文件
```

### 选项集
```
metadata/optionsets/
├── global_optionsets.yaml     # 全局选项集
└── {table_name}_{field_name}_options.yaml  # 本地选项集
```

## Excel工作表映射

| Excel工作表 | YAML输出 | 说明 |
|-------------|----------|------|
| 02_实体模型 | metadata/tables/{entity}.yaml | 表定义 |
| 05_枚举选项集 | metadata/optionsets/*.yaml | 选项集定义 |
| 03_视图定义 | metadata/views/{entity}_{view}.yaml | 视图定义 |
| 04_表单设计 | metadata/forms/{entity}_main.yaml | 窗体 YAML |

## 数据类型映射

Excel数据类型 → YAML类型映射：

| Excel类型 | YAML Type | 说明 |
|-----------|-----------|------|
| Text | String | 单行文本 |
| Multiline Text | Memo | 多行文本 |
| Email | String | 电子邮件(特殊格式) |
| Phone | String | 电话号码(特殊格式) |
| URL | String | 网址(特殊格式) |
| Date and Time | DateTime | 日期时间 |
| Whole Number | Integer | 整数 |
| Decimal Number | Decimal | 十进制数 |
| Currency | Money | 货币 |
| Floating Point Number | Double | 浮点数 |
| Yes/No | Boolean | 布尔值 |
| Choice | Picklist | 选项集(单选) |
| MultiSelect Choice | MultiSelectPicklist | 选项集(多选) |
| Lookup | Lookup | 查找字段 |
| Customer | Customer | 客户查找 |
| Owner | Owner | 所有者 |
| Autonumber | String | 自动编号(特殊格式) |
| Unique Identifier | Uniqueidentifier | GUID |

## 字段属性映射

| Excel列 | YAML属性 | 转换规则 |
|---------|----------|----------|
| 字段名称 | name | **按命名规则转换**: {prefix}_{lowercase_name} |
| 显示名称 | display_name | 直接使用 |
| 英文显示名称 | - | 可记录在description中 |
| 数据类型 | type | 按类型映射表转换 |
| 长度 | max_length | 数值直接映射 |
| 默认值 | default_value | 直接映射 |
| 是否必填 | required | "是"→true, "否"→false |
| 是否唯一 | - | 记录在description |
| 是否主字段 | is_primary_name | "是"→true, 仅一个为true |
| 可搜索 | searchable | "是"→true, "否"→false |
| 关联实体 | entity (Lookup类型) | 直接映射 |
| 关联类型 | relationship_type | Many-to-One→ManyToOne |
| **选项集引用** | **option_set_ref** | **Choice类型专用**：引用全局选项集名称（在05工作表中定义） |
| **选项定义** | **options** | **Choice类型专用**：本地选项集内联定义，格式 `标签=值,标签=值` |

**name字段转换示例**:
- Excel: "PaymentNumber" → YAML: "new_payment_number"
- Excel: "Customer Type" → YAML: "new_customer_type"
- Excel: "备注" → YAML: "new_remarks"

## 选项集处理

### Excel 中的选项集定义方式

Dataverse 支持两种选项集类型，在"02_实体模型"工作表中通过不同列指定：

| 类型 | 使用方式 | Excel填写 |
|-----|---------|-----------|
| **全局选项集** | 多个实体/字段共用，在"05_枚举选项集"中定义 | 在"选项集引用"列填写选项集名称 |
| **本地选项集** | 仅当前字段使用，内联定义 | 在"选项定义"列填写 `标签=值,标签=值` |

### 选项集定义规则

- **只能二选一**：不能同时填写"选项集引用"和"选项定义"
- **全局选项集**：引用的选项集必须在"05_枚举选项集"工作表中已定义
- **本地选项集**：选项值必须为整数，格式如 `激活=1,禁用=2,待审核=3`

### Excel 填写示例

**示例 1：引用全局选项集**

| 字段名称 | 数据类型 | 选项集引用 | 选项定义 |
|---------|---------|-----------|---------|
| account_type | Choice | account_type | （留空） |

**示例 2：使用本地选项集**

| 字段名称 | 数据类型 | 选项集引用 | 选项定义 |
|---------|---------|-----------|---------|
| priority | Choice | （留空） | 高=3,中=2,低=1 |

### 选项集YAML结构

```yaml
# 全局选项集
$schema: "../../_schema/optionset_schema.yaml"
name: "global_optionsets"
display_name: "全局选项集"
options:
  - value: 100000000
    label: "选项1"
    color: "#FF0000"
```

## 窗体 YAML 转换

从 Excel "04_表单设计" 工作表提取 Tab/Section/字段布局，生成 `metadata/forms/{entity}_main.yaml`。

### Excel → 窗体 YAML 映射

Excel 的 A 列标记 Tab（`<Tab N: 名称>`），布局区域展示字段排列，右侧 L-Q 列提供字段属性：

| Excel 列/区域 | YAML 路径 | 说明 |
|---------------|-----------|------|
| A 列 Tab 标记 | `tabs[].display_name` | Tab 显示名称 |
| 布局区的行 | `tabs[].sections[].rows[]` | 每行 1-2 个字段 |
| L 列（字段名） | `cells[].attribute` | 字段 schema name |
| Q 列（Tab 归属） | 确定字段属于哪个 Tab | 分组依据 |

### 窗体 YAML 完整结构

```yaml
$schema: "../_schema/form_schema.yaml"

form:
  schema_name: "{entity}_main_form"
  entity: "{entity_logical_name}"
  type: "Main"
  display_name: "显示名称"
  is_default: true
  # form_id 无需手动指定，update_form 自动查找

  options:
    use_field_display_label: true
    enable_navigation: true

tabs:
  - name: "tab_basic"          # 逻辑名：英文、无空格、无中文，同表单内唯一
    display_name: "基本信息"
    expand_by_default: true
    sections:
      - name: "sec_core"       # Section 逻辑名：英文、无空格
        display_name: "核心信息"
        rows:
          - cells:             # 单字段占满行
              - attribute: "new_field1"
                width: "2"
          - cells:             # 双字段并排
              - attribute: "new_field2"
                width: "1"
              - attribute: "new_field3"
                width: "1"
```

### 转换规则

| 规则 | 说明 |
|------|------|
| Tab name | 从 Excel Tab 标题生成（英文、无空格，如 `tab_basic`） |
| Section name | 从 Excel 分组区域提取（如 `sec_core`） |
| Cell attribute | 直接使用 Excel L 列的 schema name |
| Cell width | `"1"` = 半行, `"2"` = 整行，每行宽度和 ≤ 2 |
| Cell label | 不设置，Dataverse 自动使用字段 DisplayName |
| 字段来源 | 必须在实体 YAML 的 attributes 或 lookup_attributes 中已定义 |
| Lookup 字段 | 与普通字段放在同一 Section |

### 同步到 Dataverse

生成的窗体 YAML 通过 `/dv-sync` 或 `metadata_agent.update_form()` 同步：

| 场景 | 操作 |
|------|------|
| 实体无任何 Main 窗体 | POST 创建 |
| 仅有自动生成的默认窗体（name="Information"） | POST 新窗体替代 |
| 已有定制过的窗体 | PATCH 更新 |

**关键约束**：
- 自动生成的默认窗体受平台保护，无法 PATCH，必须 POST 新窗体替代
- 窗体始终通过 formxml 操作，formjson 由 Dataverse 自动转换，不可通过 API 直接修改
- Tab/Section 的 `<label>` 使用 `languagecode` 属性：`1033`=英文，`2052`=中文
- `objecttypecode` 在查询和创建时均为实体逻辑名称字符串（Edm.String），不是 ObjectTypeCode 数值

## 视图 YAML 转换

从 Excel "03_视图定义" 工作表提取视图配置，生成 `metadata/views/{entity}_{view}.yaml`。

### Dataverse 视图类型

Dataverse 实体创建后自动生成 6 类视图，可通过 API 修改：

| 视图类型 | QueryType | 可创建 | 可更新 | 可删除 | 说明 |
|----------|-----------|--------|--------|--------|------|
| PublicView | 0 | ✓ | ✓ | ✓ | 公共视图，可设为默认视图 |
| AdvancedFind | 1 | ✗ | ✓ | ✗ | 高级查找视图 |
| AssociatedView | 2 | ✗ | ✓ | ✗ | 关联视图（导航面板） |
| QuickFindView | 4 | ✗ | ✓ | ✗ | 快速查找视图（搜索） |
| LookupView | 64 | ✗ | ✓ | ✗ | 查找视图（默认查找） |

**注意**：只有 PublicView (QueryType=0) 可以创建和删除，其他类型只能更新。

### Excel → 视图 YAML 映射

| Excel 列 | YAML 路径 | 说明 |
|----------|-----------|------|
| 视图名称 | `view.schema_name` | 视图唯一标识 |
| 实体名称 | `view.entity` | 所属实体 |
| 序号 | `columns[].sort_order` | 列排序顺序 |
| 字段名称 | `columns[].attribute` | 字段 schema name |
| 显示名称 | - | 用于文档，不直接写入 YAML |
| 列宽 | `columns[].width` | 列宽度（像素） |
| 对齐方式 | `columns[].align` | left/center/right |
| 是否可排序 | `columns[].sortable` | 布尔值 |
| 是否可筛选 | `columns[].filterable` | 布尔值 |
| 排序方式 | 用于 `fetchxml` 的 order | asc/desc |
| 格式 | `columns[].format` | text/number/money/date 等 |
| 综合方式 | - | 暂不转换 |

### 视图 YAML 完整结构

```yaml
$schema: "../../_schema/view_schema.yaml"

view:
  schema_name: "account_active_accounts"    # 视图唯一标识
  entity: "account"                          # 所属实体
  type: "PublicView"                         # 视图类型
  display_name: "活跃账户"                    # 显示名称
  is_default: true                           # 是否为默认视图

  # Fetch XML 查询定义（自动从 columns 构建）
  fetch_xml: |
    <fetch version="1.0" mapping="logical">
      <entity name="account">
        <attribute name="accountnumber" />
        <attribute name="name" />
        <attribute name="telephone1" />
        <attribute name="emailaddress1" />
        <attribute name="statuscode" />
        <attribute name="createdon" />
        <order attribute="accountnumber" descending="false" />
      </entity>
    </fetch>

columns:
  - attribute: "accountnumber"
    width: 200
    sort_order: 1
    align: "left"
    sortable: true
    filterable: true
    format: "text"

  - attribute: "name"
    width: 200
    sort_order: 2
    align: "left"
    sortable: true
    filterable: true
    format: "text"
```

### 同步到 Dataverse

生成的视图 YAML 通过 `/dv-sync` 或 `metadata_agent.create_view()` 同步：

| 场景 | 操作 |
|------|------|
| 视图不存在 | POST 创建新视图 |
| 视图已存在 | PATCH 更新 FetchXml/LayoutXml |

**关键约束**：
- 只能创建 PublicView (QueryType=0)，其他类型通过更新现有视图实现
- 公共视图可以删除，但系统内置视图建议只更新不删除
- 视图通过 `fetchxml` 和 `layoutxml` 操作，不是 layoutjson
- `returnedtypecode` 是实体逻辑名称字符串

### 转换脚本

使用统一的 `convert_excel_to_yaml.py` 脚本转换视图定义（视图转换已整合到主脚本）：

```bash
# 转换所有内容（实体 + 选项集 + 视图）
python .claude/skills/dv-model-to-yaml/scripts/convert_excel_to_yaml.py \
  sources/features/xxx/02-designs/design.xlsx --include-views

# 指定输出目录
python .claude/skills/dv-model-to-yaml/scripts/convert_excel_to_yaml.py \
  sources/features/xxx/02-designs/design.xlsx -o metadata/ --include-views

# 仅转换视图
python .claude/skills/dv-model-to-yaml/scripts/convert_excel_to_yaml.py \
  sources/features/xxx/02-designs/design.xlsx --views-only
```

### 关系类型转换

| Excel关联类型 | YAML Relationship Type |
|---------------|----------------------|
| Many-to-One | ManyToOne |
| One-to-Many | OneToMany |
| Many-to-Many | ManyToMany |

### 级联规则

默认级联规则：
- ManyToOne: NoCascade
- OneToMany: RemoveLink (删除时)
- ManyToMany: NoCascade

### 关系命名规则（重要）

自定义关系的 `schema_name` 字段**必须以发布商前缀 `new_` 开头**，否则 Dataverse 会返回 "Custom relationship names must start with a publisher prefix" 错误。

```yaml
# ✓ 正确：以 new_ 开头
relationships:
  - schema_name: "new_account_payment_recognition"
    related_entity: "account"
    relationship_type: "ManyToOne"
    referencing_attribute: "new_customerid"

  - schema_name: "new_systemuser_payment_recognition_handledby"
    related_entity: "systemuser"
    relationship_type: "ManyToOne"
    referencing_attribute: "new_handledby"

# ✗ 错误：不以 new_ 开头（部分标准实体如 account 可能侥幸通过，但 systemuser 必定失败）
relationships:
  - schema_name: "systemuser_new_payment_recognition_handledby"  # 会报错！
```

### 级联配置规则（重要）

一个 Dataverse 实体**只能有一个 parental 关系**。`UserOwned` 实体已通过 Owner 拥有隐式 parental 关系，因此自定义 Lookup 关系应使用 **Referential 级联模式**：

```yaml
relationships:
  - name: "new_account_payment_recognition"
    related_entity: "account"
    relationship_type: "ManyToOne"
    referencing_attribute: "new_customerid"
    # Referential 级联模式（推荐）
    cascade_assign: "NoCascade"
    cascade_delete: "RemoveLink"
    cascade_reparent: "NoCascade"
    cascade_share: "NoCascade"
    cascade_unshare: "NoCascade"
```

**禁止使用 `Active` 级联值**：`Active` 会建立 parental 关系，多个 parental 关系会导致 `MultipleParentsNotSupported (0x80047007)` 错误。

## 使用方法

### 步骤1：定位Excel文件

确认Excel文件位置，通常在：
```
sources/features/{feature-name}/02-designs/entities/{design_file}.xlsx
```

### 步骤2：读取Excel工作表

读取 "02_实体模型" 工作表，提取实体定义

### 步骤3：解析并验证

1. 检查主字段：每个表必须有且仅有一个主字段
2. 验证数据类型：确保类型映射正确
3. 检查必填字段：主字段通常为必填
4. 识别选项集：区分全局和本地选项集

### 步骤4：生成YAML文件

生成符合Schema规范的YAML文件，保存到：
```
metadata/tables/{table_schema_name}.yaml
```

### 步骤5：处理选项集

如包含选项集，生成独立的选项集YAML文件：
```
metadata/optionsets/{table_name}_{field_name}_options.yaml
```

### 步骤6：处理表单（可选）

使用 `--include-forms` 参数转换窗体设计：
```bash
python .claude/skills/dv-model-to-yaml/scripts/convert_excel_to_yaml.py \
  design.xlsx --include-forms
```

生成的窗体YAML保存到：
```
metadata/forms/{entity}_main.yaml
```

## CLI 命令用法

```bash
# 基本用法：转换实体和选项集
python scripts/convert_excel_to_yaml.py design.xlsx

# 包含窗体转换
python scripts/convert_excel_to_yaml.py design.xlsx --include-forms

# 包含视图转换
python scripts/convert_excel_to_yaml.py design.xlsx --include-views

# 包含窗体和视图转换
python scripts/convert_excel_to_yaml.py design.xlsx --include-forms --include-views

# 指定输出目录
python scripts/convert_excel_to_yaml.py design.xlsx -o metadata/

# 仅转换窗体
python scripts/convert_excel_to_yaml.py design.xlsx --forms-only

# 仅转换视图
python scripts/convert_excel_to_yaml.py design.xlsx --views-only

# 查看帮助
python scripts/convert_excel_to_yaml.py --help
```

## 复杂转换场景

对于以下复杂场景，建议使用 `transformers/` 层：

1. **多表关联处理** - 需要分析多个表之间的关系
2. **继承结构** - 基于现有表创建新表
3. **批量转换** - 一次转换多个Excel文件
4. **自定义字段类型** - 非标准Dataverse类型
5. **复杂验证规则** - 需要跨表验证

调用方式：
```
使用 transformers/excel_to_yaml.py 处理复杂转换
```

## 脚本位置

`scripts/convert_excel_to_yaml.py` - 执行Excel到YAML的转换

## 参考文档

- 架构文档: `docs/spec/architecture.md`
- Table Schema: `metadata/_schema/table_schema.yaml`
- 示例YAML: `docs/data_dictionary/tables/*.md`
