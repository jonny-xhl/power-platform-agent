---
skill:
  id: "shared-naming"
  name: "命名规则"
  version: "1.0.0"
  author: "Power Platform Team"
  description: "Power Platform命名转换和验证规则"
  category: "shared"

  triggers:
    keywords:
      - "命名"
      - "naming"
      - "schema name"
      - "转换"
      - "验证"
      - "prefix"
      - "命名规则"

  requirements:
    tools:
      - "naming_convert"
      - "naming_validate"
      - "naming_bulk_convert"
      - "naming_rules_list"

    resources:
      - "naming_rules"

  capabilities:
    - "convert_schema_name"
    - "convert_webresource_name"
    - "validate_naming"
    - "apply_prefix"

  metadata:
    created_at: "2025-01-15"
    updated_at: "2025-01-20"
    tokens_estimate: 1500
---

# Power Platform 命名规则

## 概述

本技能定义了Power Platform开发中的命名转换和验证规则，确保所有元数据对象符合命名规范。

## 发布商前缀

所有自定义对象都需要添加发布商前缀以避免冲突：

- **默认前缀**: `new`
- **配置位置**: `config/naming_rules.yaml`
- **自动添加**: 默认启用

## Schema Name 命名

### 命名风格

支持三种命名风格：

| 风格 | 格式 | 示例 |
|-----|------|------|
| `lowercase` | `prefix_name_with_underscores` | `new_customer_account` |
| `camelCase` | `prefixNameWithCamelCase` | `newCustomerAccount` |
| `PascalCase` | `PrefixNameWithPascalCase` | `NewCustomerAccount` |

### 转换规则

1. **Pascal/Camel → lowercase**
   - `AccountNumber` → `account_number`
   - `CustomerName` → `customer_name`
   - 在大写字母前插入下划线，然后全部小写

2. **自动添加前缀**
   - `account_number` → `new_account_number`
   - `customer_name` → `new_customer_name`

3. **分隔符**
   - `lowercase` 风格使用 `_` 作为分隔符
   - 其他风格不使用分隔符

## Web Resource 命名

### 命名模式

```
{prefix}{category}/{name}.{ext}
```

### 类型到分类的映射

| 类型 | 分类 | 示例 |
|-----|------|------|
| CSS | `css` | `new_css/account_form.css` |
| JavaScript | `js` | `new_js/account_handler.js` |
| HTML | `html` | `new_html/dashboard.html` |
| PNG | `png` | `new_png/icon.png` |
| SVG | `svg` | `new_svg/logo.svg` |

### 自动转换

```yaml
resources:
  - name: "account_form"
    type: "css"
    # 自动转换为: new_css/account_form.css

  - name: "account_handler"
    type: "js"
    # 自动转换为: new_js/account_handler.js
```

## 标准实体保护

以下标准实体**不会**被添加前缀：

### 系统核心
- account, contact, systemuser, team, businessunit

### 活动相关
- activitypointer, email, appointment, task, phonecall

### 销售相关
- lead, opportunity, competitor, quote, salesorder, invoice

[完整列表见配置文件]

## 验证规则

### Schema Name 验证

- **最大长度**: 100 字符
- **最小长度**: 2 字符
- **禁止字符**: 空格、`-`、`.`
- **必须以**: 字母开头
- **允许模式**: `^[a-zA-Z][a-zA-Z0-9_]*$`

### Web Resource 名称验证

- **最大长度**: 256 字符
- **禁止字符**: 空格
- **允许模式**: `^[a-zA-Z0-9_./-]+$`

## 转换示例

### 输入 → lowercase

| 输入 | 输出 |
|-----|------|
| `AccountNumber` | `new_account_number` |
| `CustomerEmailAddress` | `new_customer_email_address` |
| `Balance` | `new_balance` |
| `IsActive` | `new_is_active` |

### 输入 → camelCase

| 输入 | 输出 |
|-----|------|
| `AccountNumber` | `newAccountNumber` |
| `CustomerName` | `newCustomerName` |
| `balance` | `newBalance` |

### 输入 → PascalCase

| 输入 | 输出 |
|-----|------|
| `AccountNumber` | `NewAccountNumber` |
| `CustomerName` | `NewCustomerName` |
| `balance` | `NewBalance` |

## 批量转换

```json
{
  "items": [
    {"name": "AccountNumber", "is_standard": false},
    {"name": "CustomerName", "is_standard": false},
    {"name": "contact", "is_standard": true}
  ],
  "type": "schema_name"
}

// 结果:
// new_account_number
// new_customer_name
// contact (保持不变)
```

## 保留字

以下保留字不会进行命名转换：

- `account`
- `contact`
- `systemuser`
- `businessunit`
- [更多见配置文件]

## 配置文件

命名规则配置位于 `config/naming_rules.yaml`：

```yaml
naming:
  prefix: "new"

  schema_name:
    style: "lowercase"
    separator: "_"
    auto_prefix: true

  webresource:
    category_style: "lowercase"
    naming_pattern: "{prefix}{category}/{name}.{ext}"
```

## API 使用

### 转换命名

```python
result = await naming_convert(
    input="AccountNumber",
    type="schema_name",
    is_standard=false
)
# 返回: "new_account_number"
```

### 验证命名

```python
is_valid, error = await naming_validate(
    name="new_account_number",
    type="schema_name"
)
# 返回: (True, None) 或 (False, "错误信息")
```

### 批量转换

```python
results = await naming_bulk_convert(
    items=[{"name": "AccountNumber"}, {"name": "CustomerName"}],
    type="schema_name"
)
```

## 最佳实践

1. **保持一致性**: 在整个项目中使用相同的命名风格
2. **使用有意义的名称**: 名称应反映对象的用途
3. **遵循约定**: 遵循Power Platform的命名约定
4. **验证命名**: 在应用前验证命名是否正确
5. **保护标准实体**: 不要尝试修改标准实体的命名

## 故障排查

### 问题: 名称冲突

**错误**: 组件已存在

**解决方案**:
- 使用不同的名称
- 检查是否使用了正确的前缀
- 使用 `naming_validate` 验证

### 问题: 验证失败

**错误**: 包含非法字符

**解决方案**:
- 移除空格、连字符、点号
- 确保以字母开头
- 使用下划线分隔单词

### 问题: 标准实体被转换

**错误**: 标准实体名称被修改

**解决方案**:
- 在标准实体列表中添加该实体
- 使用 `is_standard: true` 标记
