---
skill:
  id: "power-platform-metadata"
  name: "Power Platform 元数据管理"
  version: "1.0.0"
  author: "Power Platform Team"
  description: "管理Dataverse表、字段、表单、视图等元数据"
  category: "power-platform"

  triggers:
    keywords:
      - "创建表"
      - "新建实体"
      - "添加字段"
      - "设计表单"
      - "创建视图"
      - "metadata"
      - "元数据"
      - "table"
      - "entity"

    contexts:
      - "dataverse"
      - "power platform"
      - "microsoft"
      - "crm"

  requirements:
    tools:
      - "metadata_parse"
      - "metadata_validate"
      - "metadata_apply"
      - "metadata_export"
      - "naming_convert"
      - "naming_validate"

    resources:
      - "metadata_files"
      - "naming_rules"

    dependencies:
      skills:
        - "shared-naming"
        - "shared-validation"

  capabilities:
    - "parse_yaml_metadata"
    - "validate_schema"
    - "apply_to_dataverse"
    - "export_from_dataverse"
    - "diff_metadata"

  metadata:
    created_at: "2025-01-15"
    updated_at: "2025-01-20"
    tokens_estimate: 2500
---

# Power Platform 元数据管理

## 概述

本技能提供Power Platform Dataverse元数据管理的完整流程指导，包括表、字段、表单、视图的创建、更新和同步。

## 标准表保护

**重要**：以下标准表不会被命名转换影响，需要特殊处理：

### 系统核心表
- `account` - 账户/客户表
- `contact` - 联系人表
- `systemuser` - 系统用户表
- `team` - 团队表
- `businessunit` - 业务部门表
- `role` - 角色表
- `privilege` - 权限表

### 活动相关
- `activitypointer` - 活动指针
- `email` - 电子邮件
- `appointment` - 约会
- `task` - 任务
- `phonecall` - 电话呼叫
- `letter` - 信件
- `fax` - 传真

### 销售相关
- `lead` - 线索
- `opportunity` - 商机
- `competitor` - 竞争对手
- `quote` - 报价
- `salesorder` - 销售订单
- `invoice` - 发票

[完整列表见 `config/naming_rules.yaml` 中的 `standard_entities`]

## 工作流程

### 1. 创建新表

**步骤**：
1. 在 `metadata/tables/` 创建 YAML 文件
2. 验证 Schema
3. 应用命名转换
4. 应用到 Dataverse

**示例**：
```yaml
# metadata/tables/customer.yaml
$schema: "../_schema/table_schema.yaml"

schema:
  schema_name: "customer"
  display_name: "客户"
  ownership_type: "UserOwned"

attributes:
  - name: "customerCode"
    type: "String"
    display_name: "客户编号"
    required: true
    is_primary_name: true
```

**执行**：
```
1. metadata_parse --file_path metadata/tables/customer.yaml --type table
2. metadata_validate --metadata_yaml customer --schema table_schema
3. metadata_apply --metadata_type table --name customer
```

### 2. 添加字段

**字段类型**：
- `String` - 字符串 (max_length: 1-4000)
- `Integer` - 整数
- `Money` - 货币 (precision: 0-10)
- `Picklist` - 选项集
- `Lookup` - 查找
- `DateTime` - 日期时间
- `Boolean` - 是/否
- `Memo` - 多行文本

**示例**：
```yaml
attributes:
  - name: "creditLimit"
    type: "Money"
    display_name: "信用额度"
    required: false
    min_value: 0
    precision: 2
```

### 3. 创建表单

**表单类型**：
- `Main` - 主表单
- `QuickCreate` - 快速创建
- `QuickView` - 快速视图
- `Card` - 卡片

**结构**：
```yaml
form:
  schema_name: "customer_main_form"
  entity: "customer"
  type: "Main"
  display_name: "客户主表单"

  tabs:
    - name: "general"
      display_name: "常规"
      sections:
        - name: "basicInfo"
          display_name: "基本信息"
          rows:
            - cells:
                - attribute: "customerCode"
                  width: "1"
```

### 4. 创建视图

**视图类型**：
- `PublicView` - 公共视图
- `PrivateView` - 私有视图
- `AdvancedFind` - 高级查找
- `AssociatedView` - 关联视图

**Fetch XML**：
```xml
<fetch version="1.0" mapping="logical">
  <entity name="customer">
    <attribute name="customercode" />
    <attribute name="name" />
    <order attribute="customercode" descending="false" />
  </entity>
</fetch>
```

## 命名规则

### Schema Name 转换

根据配置，schema_name 会自动转换：

| 输入 | lowercase | camelCase | PascalCase |
|-----|-----------|-----------|------------|
| `AccountNumber` | `new_account_number` | `newAccountNumber` | `NewAccountNumber` |
| `CustomerEmail` | `new_customer_email` | `newCustomerEmail` | `NewCustomerEmail` |

自动添加前缀：`{prefix}` + `{converted_name}`

### Web Resource 命名

遵循模式：`{prefix}{category}/{name}.{ext}`

| 类型 | 输入 | 输出 |
|-----|------|------|
| CSS | `account_form` | `new_css/account_form.css` |
| JS | `handler` | `new_js/handler.js` |
| HTML | `dashboard` | `new_html/dashboard.html` |

## 表创建选项

默认情况下，以下选项均为 `false`（不导入）：

```yaml
options:
  import_dependencies: false    # 依赖项
  import_subcomponents: false   # 子组件
  create_audit_fields: false    # 审计字段
  enable_quick_create: false    # 快速创建
```

## 表单创建选项

```yaml
options:
  use_field_display_label: true  # 使用字段的display label
  enable_security: false
  show_image: false
```

## 关系定义

### 一对多关系

```yaml
relationships:
  - name: "customer_contact"
    related_entity: "contact"
    relationship_type: "OneToMany"
    cascade_assign: "NoCascade"
    cascade_delete: "RemoveLink"
```

### 多对一关系

```yaml
relationships:
  - name: "primary_customer"
    related_entity: "customer"
    relationship_type: "ManyToOne"
    referencing_attribute: "primarycustomerid"
```

## 故障排查

### 常见错误

1. **命名冲突**
   - 错误：`A component with that name already exists`
   - 解决：检查命名规则配置，使用 `naming_validate` 验证

2. **Schema验证失败**
   - 错误：`Validation errors: ...`
   - 解决：检查YAML格式，确保符合Schema定义

3. **标准表保护触发**
   - 错误：`Cannot modify standard entity`
   - 解决：确认是否真的需要修改标准表，考虑创建自定义表

4. **属性类型不支持**
   - 错误：`Invalid attribute type`
   - 解决：使用支持的字段类型

## 最佳实践

1. **使用YAML注释**：为复杂的元数据添加说明
2. **保持命名一致**：遵循项目命名规范
3. **渐进式开发**：先创建表，再添加字段和关系
4. **本地验证**：在应用前先验证元数据
5. **版本控制**：将YAML文件纳入Git管理

## 示例

### 创建客户账户表

```yaml
# metadata/tables/account.yaml
$schema: "../_schema/table_schema.yaml"

schema:
  schema_name: "account"
  display_name: "客户账户"
  description: "存储客户账户信息"
  ownership_type: "UserOwned"

attributes:
  - name: "accountNumber"
    type: "String"
    display_name: "账户编号"
    required: true
    is_primary_name: true

  - name: "balance"
    type: "Money"
    display_name: "账户余额"
    precision: 2
```

### 创建余额字段

```yaml
attributes:
  - name: "balance"
    type: "Money"
    display_name: "余额"
    required: false
    min_value: 0
    precision: 2
```

### 设计主表单

```yaml
form:
  schema_name: "account_main_form"
  entity: "account"
  type: "Main"
  display_name: "账户主表单"

  tabs:
    - name: "general"
      display_name: "常规信息"
      sections:
        - name: "basicInfo"
          display_name: "基本信息"
          rows:
            - cells:
                - attribute: "accountNumber"
                  width: "1"
```

## 相关资源

- [Power Platform Web API 文档](https://learn.microsoft.com/power-apps/developer/data-platform/webapi/overview)
- [Dataverse 元数据 API](https://learn.microsoft.com/power-apps/developer/data-platform/customize-entity-metadata)
- [项目命名规则](../../config/naming_rules.yaml)
- [Schema定义](../../metadata/_schema/)
