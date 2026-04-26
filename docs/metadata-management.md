# Power Platform Agent - 元数据管理文档

## 概述

Power Platform Agent 提供完整的元数据管理功能，通过 YAML 定义可以创建和修改 Dataverse 实体（表）、字段（属性）、关系等。

## 核心功能

### 1. 创建表 (Create Table)

通过 YAML 定义创建新的自定义表。

**示例 YAML:**
```yaml
$schema: "../_schema/table_schema.yaml"

schema:
  schema_name: "new_payment_recognition"
  display_name: "认款单"
  description: "记录客户认款信息"
  ownership_type: "UserOwned"
  has_activities: true
  has_notes: true

attributes:
  - name: "new_payment_number"
    type: "String"
    display_name: "认款单号"
    max_length: 50
    required: true
    is_primary_name: true
```

### 2. 修改表 (Update Table)

YAML 定义是声明式的 - Agent 会自动计算差异并只应用必要的变更。

**支持的修改:**
- 添加新字段
- 修改字段属性（显示名称、描述、必填状态等）
- 添加新关系
- 修改关系的级联配置

### 3. 创建字段 (Create Attribute)

支持所有标准 Dataverse 字段类型：

| 类型 | YAML Type | 说明 |
|------|-----------|------|
| 文本 | `String` | 单行文本 |
| 多行文本 | `Memo` | 多行文本 |
| 整数 | `Integer` | 整数 |
| 货币 | `Money` | 货币金额 |
| 日期时间 | `DateTime` | 日期或日期时间 |
| 选项集 | `Picklist` | 下拉选择（本地或全局） |
| 多选选项集 | `MultiSelectPicklist` | 多选下拉 |
| 查找 | `Lookup` | 关联其他表 |
| 客户 | `Customer` | 关联客户或联系人 |
| 所有者 | `Owner` | 关联用户或团队 |
| 是/否 | `Boolean` | 布尔值 |

### 4. 修改字段 (Update Attribute)

修改字段不需要特殊操作，只需更新 YAML 定义并应用：

```yaml
attributes:
  - name: "new_payment_amount"
    type: "Money"
    display_name: "认款金额（元）"  # 修改显示名称
    required: true                  # 修改为必填
```

### 5. 创建关系 (Create Relationship)

关系通过 `lookup_attributes` 和 `relationships` 部分定义。

**ManyToOne 关系（最常用）:**
```yaml
lookup_attributes:
  - name: "new_customerid"
    type: "Lookup"
    display_name: "客户"
    target: "account"

relationships:
  - name: "account_new_payment_recognition"
    related_entity: "account"
    relationship_type: "ManyToOne"
    display_name: "客户"
    referencing_attribute: "new_customerid"
    cascade_assign: "Cascade"
    cascade_delete: "RemoveLink"
```

**关系命名约定:**
- 遵循 `ReferencedEntity_ReferencingEntity` 格式
- 例如: `account_new_payment_recognition`

### 6. 删除关系 (Delete Relationship)

使用 MCP 工具删除关系：

```json
{
  "entity": "new_payment_recognition",
  "relationship_name": "old_relationship_name"
}
```

### 7. 字段选项集 (Local Option Set)

为 Picklist 字段定义本地选项：

```yaml
attributes:
  - name: "new_approval_status"
    type: "Picklist"
    display_name: "审批状态"
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
```

### 8. 全局选项集引用 (Global Option Set)

引用已定义的全局选项集：

```yaml
attributes:
  - name: "new_status"
    type: "Picklist"
    display_name: "状态"
    global_option_set: "global_status_codes"  # 引用全局选项集名称
```

## MCP 工具

### metadata_apply_yaml

**核心工具** - 应用 YAML 定义到 Dataverse，自动计算差异并应用变更。

```json
{
  "table_yaml": "metadata/tables/payment_recognition.yaml",
  "options": {
    "dry_run": false,
    "force_update": false
  }
}
```

### metadata_plan

**预览变更** - 显示将要进行的变更但不执行。

```json
{
  "table_yaml": "metadata/tables/payment_recognition.yaml"
}
```

**返回示例:**
```json
{
  "entity": "new_payment_recognition",
  "has_changes": true,
  "summary": {
    "attribute_create": 2,
    "relationship_create": 1
  },
  "changes": [...]
}
```

### metadata_delete_attribute

删除指定字段。

```json
{
  "entity": "new_payment_recognition",
  "attribute_name": "new_old_field"
}
```

### metadata_delete_relationship

删除指定关系。

```json
{
  "entity": "new_payment_recognition",
  "relationship_name": "old_relationship_name"
}
```

## 工作流程

### 开发流程

1. **创建 YAML 定义**
   ```
   metadata/tables/my_entity.yaml
   ```

2. **预览变更** (可选)
   ```
   调用 metadata_plan 工具
   ```

3. **应用变更**
   ```
   调用 metadata_apply_yaml 工具
   ```

### 迭代流程

1. 修改 YAML 文件
2. 调用 `metadata_apply_yaml` - Agent 自动计算差异
3. 只应用变更的部分

## Deep Insert 模式

查找字段（Lookup）和关系使用 Deep Insert 模式创建：

1. Lookup 属性定义在 `lookup_attributes` 中
2. 关系定义在 `relationships` 中
3. 创建关系时，Lookup 属性自动嵌入关系定义中
4. 一次 API 调用同时创建关系和查找字段

## 级联配置

| 值 | 说明 |
|---|---|
| `Cascade` / `Active` | 级联到所有相关记录 |
| `NoCascade` | 不执行任何操作 |
| `RemoveLink` | 移除关联 |
| `Restrict` | 限制操作 |

## 最佳实践

1. **命名约定**
   - 自定义实体: `{prefix}_{name}` (如 `new_payment_recognition`)
   - 自定义字段: `{prefix}_{lowercase_name}` (如 `new_payment_amount`)
   - 关系: `{referenced_entity}_{referencing_entity}` (如 `account_new_payment_recognition`)

2. **版本控制**
   - 将 YAML 文件纳入 Git 版本控制
   - 可以追踪所有元数据变更历史

3. **增量更新**
   - 每次修改后应用 YAML，而非删除重建
   - Agent 自动处理增量变更

4. **先规划后应用**
   - 使用 `metadata_plan` 预览变更
   - 确认无误后再执行 `metadata_apply_yaml`

## 完整示例

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

  # 客户查找 - 通过关系创建
  # (在 lookup_attributes 中定义)

  # 发票日期
  - name: "new_invoice_date"
    type: "DateTime"
    display_name: "发票日期"
    required: true
    date_only: true

  # 金额
  - name: "new_amount"
    type: "Money"
    display_name: "发票金额"
    required: true
    precision: 2
    min_value: 0

  # 状态 - 使用全局选项集
  - name: "new_status"
    type: "Picklist"
    display_name: "发票状态"
    required: true
    global_option_set: "global_invoice_status"

  # 备注
  - name: "new_notes"
    type: "Memo"
    display_name: "备注"
    max_length: 2000

# 查找字段定义
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

## 错误处理

### 常见错误

1. **属性已存在**
   - Agent 会自动检测并跳过已存在的属性

2. **关系创建失败**
   - 确保引用的实体存在
   - 检查关系名称是否正确

3. **全局选项集不存在**
   - 确保全局选项集已在目标环境中创建

### 错误响应示例

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
