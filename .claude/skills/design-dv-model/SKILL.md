---
name: design-dv-model
description: 生成Microsoft Dataverse实体模型设计Excel模板。当用户需要设计Dataverse表/实体、定义列/字段、创建表单布局、指定视图或文档化数据模型需求时使用此技能。包括"设计表"、"创建实体模型"、"定义字段"、"表单设计"、"视图定义"、"数据模型文档"等短语，或处理Power Platform/Dataverse数据建模时。
---

# Dataverse实体模型设计

此技能用于生成Microsoft Dataverse实体模型的综合Excel模板，包括实体定义、视图配置、表单布局、选项集和业务规则。

**重要提示**:
1. 始终参考标准模板 `sources/templates/excel/ba_system_design_template.xlsx` 以保持结构、格式和命名约定的一致性
2. **生成的文件必须放在 `sources/features/` 下的功能迭代目录中**
3. **命名规则遵循 `config/naming_rules.yaml` 配置**：
   - 自定义实体 Schema Name: `{prefix}_{name}` (如 `new_payment_recognition`)
   - 自定义字段 Schema Name: `{prefix}_{lowercase_name}` (如 `new_payment_amount`)
   - 关系名称 Schema Name: `{prefix}_{relationship_name}` (如 `new_payment_customer`)
   - 标准实体(如account)的自定义字段也需遵循相同规则

## 使用场景

在以下情况使用此技能：
- 设计新的Dataverse表/实体
- 文档化现有Dataverse架构
- 规划多Tab表单布局
- 定义视图列和配置
- 创建选项集/选择列
- 指定业务规则和验证

## 参考模板

**标准模板位置**: `sources/templates/excel/ba_system_design_template.xlsx`

这是包含标准结构、格式和示例数据的参考模板。生成新模板时，请先读取此文件以确保一致性。

## 输出文件位置约束

**重要**: 生成的Excel文件必须放置在功能迭代目录结构中：

```
sources/features/
└── feature-xxx/              # 功能迭代目录 (如: feature-customer-management)
    ├── 01-requirements/      # 需求文档 (BRD/PRD/流程图)
    └── 02-designs/           # 设计文档
        ├── entities/         # ← 实体设计Excel放这里
        ├── forms/           # 表单设计
        └── views/           # 视图设计
```

**文件命名规范**: `{feature_name}_entity_design.xlsx`

示例：
- `customer_management_entity_design.xlsx`
- `order_processing_entity_design.xlsx`

**目录创建流程**:
1. 确认功能迭代名称 (feature-xxx)
2. 检查/创建 `sources/features/feature-xxx/02-designs/entities/` 目录
3. 在该目录下生成设计文件

## 模板结构

Excel模板包含7个工作表：

1. **01_使用说明** - 使用指南和重要说明
2. **02_实体模型** - 实体/字段定义（Dataverse数据类型）
3. **03_视图定义** - 视图列配置
4. **04_表单设计** - 多Tab表单布局画布
5. **05_枚举选项集** - 选项集/选择定义
6. **06_业务规则** - 业务规则定义
7. **07_Dataverse类型** - Dataverse数据类型参考

## Dataverse核心概念

### 主字段 (Primary Field)
- **每个表必须有且仅有一个主字段**
- 必须是Text类型
- 用作查找字段和相关记录列表中的记录标题
- 示例：account表的account_name，contact表的fullname

### 支持的数据类型

| 类型 | API类型 | 可作主字段 | 说明 |
|------|---------|-----------|------|
| Text | StringType | 是 | 单行文本（最大4000） |
| Multiline Text | MemoType | 否 | 多行文本（最大1048576） |
| Email | StringType(Email) | 否 | 电子邮件地址 |
| Phone | StringType(Phone) | 否 | 电话号码 |
| URL | StringType(URL) | 否 | 网站链接 |
| Date and Time | DateTimeType | 否 | 日期时间值 |
| Whole Number | IntegerType | 否 | 整数 |
| Decimal Number | DecimalType | 否 | 十进制数（精度10） |
| Currency | MoneyType | 否 | 货币值 |
| Yes/No | BooleanType | 否 | 布尔值（两个选项） |
| Choice | PicklistType | 否 | 选项集（单选） |
| MultiSelect Choice | MultiSelectPicklistType | 否 | 选项集（多选） |
| Lookup | LookupType | 否 | 多对一关系 |
| Customer | LookupType(Customer) | 否 | 客户查找（Account或Contact） |
| Owner | LookupType(Owner) | 否 | 所有者（User或Team） |
| Autonumber | StringType(Autonumber) | 否 | 自动编号 |

## 使用方法

### 步骤1：确认功能迭代名称

询问用户当前设计属于哪个功能迭代：
- 如果是新功能，创建新的feature-xxx目录
- 如果是已有功能，使用现有目录

### 步骤2：读取参考模板

读取标准模板以了解结构：
```
读取 sources/templates/excel/ba_system_design_template.xlsx
```

### 步骤3：创建目标目录

确认/创建目标目录：
```
sources/features/{feature_name}/02-designs/entities/
```

### 步骤4：生成实体设计文件

在目标目录下生成实体设计Excel文件，文件名格式：
```
{feature_name}_entity_design.xlsx
```

### 步骤5：填充实体数据

根据用户需求：
1. 解析实体名称和字段定义
2. 填充"02_实体模型"工作表
3. 确保主字段设置正确
4. 包含所有7个工作表的正确结构

### 多Tab表单设计

表单设计工作表（04_表单设计）用于规划窗体的 Tab/Section/字段布局。

#### Excel 布局规则

左侧列 A-G 为可视化布局区域，右侧 L-Q 为字段属性配置：

| 区域 | 说明 |
|------|------|
| A 列 | Tab 标记（`<Tab N: 名称>`） |
| B-E 列 | 字段放置（可视化网格，每行最多 2 个字段） |
| L 列 | 字段 schema name |
| M 列 | 是否只读 |
| N 列 | 是否必填 |
| Q 列 | Tab 归属标记 |

#### 设计约束

| 约束 | 说明 |
|------|------|
| Tab 数量 | 通常 2-4 个，按业务逻辑分组 |
| Section 分组 | 每个 Tab 内按语义分区 |
| 字段布局 | 每行 1-2 个字段，宽度和 ≤ 2 |
| 必填字段 | 放在 Tab 顶部、靠左位置 |
| Lookup 字段 | 与普通字段放在同一 Section |

设计完成后，通过 `dv-model-to-yaml` 将 Excel 表单设计转换为 `metadata/forms/{entity}_main.yaml`，再通过 `/dv-sync` 同步到 Dataverse。窗体 YAML 格式和同步策略详见 `dv-model-to-yaml` skill。

## 视图设计

视图设计工作表（03_视图定义）用于配置实体列表视图的显示列和排序。

### Excel 列结构

| 列 | 说明 | 取值 |
|----|------|------|
| 视图名称 | 视图唯一标识 | 如 "Active Accounts" |
| 实体名称 | 所属实体逻辑名 | 如 "account" |
| 序号 | 列显示顺序 | 1, 2, 3... |
| 字段名称 | 字段 schema name | 如 "accountnumber" |
| 显示名称 | 列标题 | 中文显示名 |
| 列宽 | 列宽度（像素） | 50-500 |
| 对齐方式 | left/center/right | 默认 left |
| 是否可排序 | 是/否 | 默认是 |
| 是否可筛选 | 是/否 | 默认是 |
| 排序方式 | asc/desc | 排序方向 |
| 格式 | text/number/date | 数据格式 |
| 综合方式 | 汇总类型 | sum/avg/count |

### 视图设计约束

| 约束 | 说明 |
|------|------|
| 列数量 | 建议 3-8 列，避免过宽 |
| 列宽 | 总宽度建议 800-1200 像素 |
| 排序 | 通常按第一列或关键字段排序 |
| 必含列 | 建议包含主字段和状态字段 |

设计完成后，通过 `dv-model-to-yaml` 将 Excel 视图设计转换为 `metadata/views/{entity}_{view}.yaml`，再通过 `/dv-sync` 同步到 Dataverse。视图 YAML 格式详见 `dv-model-to-yaml` skill。

## 工作流程示例

```
用户: 设计客户管理模块的实体
      ↓
LLM: 确认功能迭代名称为 feature-customer-management
      ↓
LLM: 创建目录 sources/features/feature-customer-management/02-designs/entities/
      ↓
LLM: 读取标准模板 sources/templates/excel/ba_system_design_template.xlsx
      ↓
LLM: 生成文件 sources/features/feature-customer-management/02-designs/entities/customer_management_entity_design.xlsx
      ↓
LLM: 填充客户实体数据到02_实体模型工作表
```

## 脚本位置

`scripts/generate_template.py` - 执行此脚本可创建新模板

## 项目架构参考

详细架构说明请参考：`docs/spec/architecture.md`
