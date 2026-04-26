---
name: dv-overview
description: Dataverse 元数据建模、表结构搭建、REST API 自动化操作标准总览。包含实体、选项集、字段、Lookup、表关系、视图、表单、Web资源、插件、业务逻辑的创建依赖顺序、API调用规范、命名规范、类型映射、增量更新、报错处理、限流并发与企业级落地最佳实践。只要用户提问、开发、编写代码、梳理流程、制定规范、排查问题、自动化开发涉及 Dataverse 相关操作，包含建模、实体、数据表、字段、查找、关系、选项集、UI配置、插件、Web资源、Power Platform、Dataverse REST/WebAPI 等场景，自动优先加载并启用本Skill。典型关键词：Dataverse、PowerPlatform、元数据、实体、表、字段、Lookup、选项集、关系、建模、REST、WebAPI、自动化、标准化、插件、视图、表单、命名规范、增量同步、错误处理、限流并发。
---

# 一、核心原则

先容器、后元数据：先建发布商 / 解决方案，再建业务组件
先独立、后依赖：无依赖组件优先，依赖型组件后置
先数据结构、后 UI / 逻辑：表 / 字段 / 关系 → 表单 / 视图 → 业务逻辑
必等异步生效：实体创建后必须校验就绪，再执行后续操作

# 二、标准化执行顺序（必按序号）

## 1. 基础容器（最先创建）

发布者 → 非托管解决方案
所有组件必须绑定目标解决方案

## 2. 全局独立元数据

全局选项集（无任何依赖）

## 3. 数据结构核心（强依赖顺序）

实体（主表 → 子表）→ 等待实体生效
实体字段（文本 / 数字 / 日期 / 本地选项集）
绑定全局选项集的字段
Lookup 字段（目标实体必须已存在）

## 4. 表关系

1:N 关系（依赖双实体 + Lookup 字段）
N:N 关系（依赖双实体）

## 5. UI 布局组件

视图（依赖实体 + 字段 + 关系）
表单（依赖实体 + 字段 + 关系 + 视图）
Web 资源（JS/CSS/HTML）
命令栏 / 按钮（依赖实体 + 表单 + Web 资源）

## 6. 业务逻辑组件

插件程序集
插件步骤（依赖实体 + 程序集）
业务规则 / 工作流 / 自定义 API
字段安全配置

## 7. 收尾

组件校验 → 解决方案导出 / 发布

# 三、REST API 关键规则

Lookup / 关系：双实体必须先存在
全局选项集：必须先于引用它的字段
实体创建：必须 GET 查询确认就绪
所有请求：携带 Solution 关联信息
禁止并行创建依赖型组件

# 四、最简校验清单

容器 → 全局选项集 → 实体 → 字段 → Lookup → 关系 → 视图 / 表单 → 按钮 / Web 资源 → 插件 / 逻辑

# 五、Dataverse 操作方式

本项目通过 `DataverseClient`（基于 requests + MSAL）封装所有 Web API 调用。

## 核心操作模式

- **通过 MCP 工具调用（推荐）**：`metadata_apply_yaml`、`metadata_create_table` 等工具
- **通过 Python 代码调用**：`core_agent.get_client()` 获取已认证的 DataverseClient 实例

## 表单操作模式

Dataverse 中一个实体可能有多个 Main 表单（form_type=2），为防止重复创建，`metadata_create_form` 工具支持多种操作模式。

### MCP 工具参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `form_yaml` | string | YAML 文件路径或 JSON 字符串，定义表单结构 |
| `mode` | string | 操作模式，见下方详细说明 |
| `target_form_id` | string | 目标表单 ID（update 模式必需） |

### 操作模式（mode 参数）

| 模式 | 说明 | 使用场景 |
|------|------|---------|
| `auto` | 自动模式（默认） | 没有 Main 表单时创建，有则更新第一个 |
| `list` | 列出所有 Main 表单 | 让用户查看并选择要操作的表单 |
| `create_new` | 强制创建新表单 | 明确需要新建独立的 Main 表单 |
| `update` | 更新指定表单 | 需配合 `target_form_id` 指定要更新的表单 |

### 推荐工作流程

1. **首次创建表单**：使用 `mode="auto"` 或 `mode="create_new"`
2. **查看现有表单**：使用 `mode="list"` 列出所有 Main 表单
3. **更新现有表单**：先 `list` 获取表单 ID，再使用 `mode="update"` + `target_form_id`

### 列出 Main 表单工具

使用 `metadata_get_form` 工具获取实体的所有 Main 表单：

| 参数 | 类型 | 说明 |
|------|------|------|
| `entity` | string | 实体逻辑名称 |
| `form_type` | integer | 表单类型（2=Main，5=Mobile，6=QuickCreate，7=QuickView） |

返回包含表单 ID、名称、描述的列表，用于选择要更新的目标表单。

> 参考实现：`framework/agents/metadata_agent.py` 中的 `list_main_forms()` 和 `create_form()` 方法

## API 基础

- API URL 格式：`{env_url}/api/data/v9.2/{endpoint}`
- 必需请求头：

| 请求头 | 值 |
|-------|------|
| OData-Version | 4.0 |
| OData-MaxVersion | 4.0 |
| Accept | application/json |
| Content-Type | application/json; charset=utf-8 |
| Prefer | odata.include-annotations=* |
| Authorization | Bearer {access_token} |

- HTTP 方法映射：

| 方法 | 用途 |
|------|------|
| POST | 创建记录/元数据 |
| GET | 查询记录/元数据 |
| PUT | 替换元数据定义 |
| PATCH | 更新数据记录 |
| DELETE | 删除记录/元数据 |

- 解决方案关联：创建组件时通过 `MSCRM.SolutionUniqueName` 请求头将组件添加到目标解决方案

> 参考实现：`framework/utils/dataverse_client.py` 中的 `_create_session()` 和 `get_api_url()` 方法

# 六、数据类型映射

YAML 中定义的属性类型与 Dataverse AttributeMetadata 类型的完整映射：

| YAML 类型 | Dataverse OData 类型 | 说明 |
|-----------|---------------------|------|
| String | Microsoft.Dynamics.CRM.StringAttributeMetadata | 文本，需设置 MaxLength（默认 100） |
| Integer | Microsoft.Dynamics.CRM.IntegerAttributeMetadata | 整数，可设置 MinValue/MaxValue |
| Money | Microsoft.Dynamics.CRM.MoneyAttributeMetadata | 货币，需设置 Precision（默认 2）和 PrecisionSource |
| Picklist | Microsoft.Dynamics.CRM.PicklistAttributeMetadata | 选项集，支持全局和本地两种模式 |
| Lookup | Microsoft.Dynamics.CRM.LookupAttributeMetadata | 查找字段，需设置 Targets 数组 |
| Customer | Microsoft.Dynamics.CRM.CustomerAttributeMetadata | 客户查找（多目标） |
| Owner | Microsoft.Dynamics.CRM.OwnerAttributeMetadata | 负责人查找 |
| DateTime | Microsoft.Dynamics.CRM.DateTimeAttributeMetadata | 日期时间，通过 Format 区分 DateOnly/DateAndTime |
| Boolean | Microsoft.Dynamics.CRM.BooleanAttributeMetadata | 布尔，自动生成 TrueOption/FalseOption |
| Memo | Microsoft.Dynamics.CRM.MemoAttributeMetadata | 多行文本，默认 MaxLength=2000 |
| Decimal | Microsoft.Dynamics.CRM.DecimalAttributeMetadata | 十进制数，可设置 Precision/MinValue/MaxValue |
| Double | Microsoft.Dynamics.CRM.DoubleAttributeMetadata | 双精度浮点数 |
| BigInt | Microsoft.Dynamics.CRM.BigIntAttributeMetadata | 大整数 |

## 特殊类型配置

- **DateTime**：设置 `date_only: true` 时使用 `Format: DateOnly`，否则 `DateAndTime`
- **Money**：`Precision` 控制小数位数，`PrecisionSource: 2` 表示使用自定义精度
- **Picklist**：
  - 全局选项集：`OptionSet.IsGlobal: true`，通过 `Name` 引用已定义的全局选项集
  - 本地选项集：`OptionSet.IsGlobal: false`，在 `Options` 数组中内联定义选项值
- **Boolean**：自动生成 `TrueOption`（值=1）和 `FalseOption`（值=0），标签默认为"是"/"否"

> 参考实现：`framework/utils/dataverse_client.py` 中的 `_convert_attribute_metadata()` 方法

# 七、命名规则（基于 naming_rules.yaml）

命名转换由 `NamingConverter` 类自动处理，配置文件为 `config/naming_rules.yaml`。

## 核心规则

| 配置项 | 值 | 说明 |
|-------|------|------|
| prefix | "new" | 发布商前缀 |
| style | "lowercase" | Schema Name 风格 |
| separator | "_" | 分隔符 |
| auto_prefix | true | 自动添加前缀 |

## 标准实体保护

标准实体保护列表中的实体（account、contact、systemuser、team、businessunit、role、privilege、lead、opportunity 等系统核心表）不会被命名转换影响。

## 命名验证

| 规则 | 值 |
|------|------|
| max_length | 100 |
| min_length | 2 |
| forbidden_chars | 空格、连字符(-)、点(.) |
| must_start_with | 字母 |
| allowed_pattern | ^[a-zA-Z][a-zA-Z0-9_]*$ |

## 转换示例

输入 `AccountNumber` → 输出 `new_account_number`（lowercase + separator="_" + auto_prefix）

## Web Resource 命名

模式：`{prefix}{category}/{name}.{ext}`，例如 `new_css/account.css`、`new_js/form.js`

> 参考实现：`framework/utils/naming_converter.py`、`config/naming_rules.yaml`

# 八、Deep Insert 模式

创建 Lookup 字段和关系时，**必须**使用 Deep Insert 模式——在 `RelationshipDefinitions` 端点创建 `OneToManyRelationshipMetadata` 时嵌入 `LookupAttributeMetadata`。

## 关键约束

- **不能**单独创建 Lookup 字段再建关系，必须一体化操作（调用 `EntityDefinitions({id})/Attributes` 创建 Lookup 会返回 "Attribute of type LookupAttributeMetadata cannot be created through the SDK" 错误）
- ManyToOne 关系从 referenced entity（被引用实体）角度创建 OneToMany 关系
- 通过 `POST RelationshipDefinitions` 端点执行

## 正确的请求体结构

```json
POST /api/data/v9.2/RelationshipDefinitions
{
  "@odata.type": "Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata",
  "SchemaName": "new_account_payment_recognition",
  "ReferencedEntity": "account",
  "ReferencingEntity": "new_payment_recognition",
  "ReferencedAttribute": "accountid",
  "CascadeConfiguration": {
    "Assign": "NoCascade",
    "Delete": "RemoveLink",
    "Merge": "NoCascade",
    "Reparent": "NoCascade",
    "Share": "NoCascade",
    "Unshare": "NoCascade"
  },
  "Lookup": {
    "@odata.type": "Microsoft.Dynamics.CRM.LookupAttributeMetadata",
    "SchemaName": "new_customerid",
    "DisplayName": {
      "@odata.type": "Microsoft.Dynamics.CRM.Label",
      "LocalizedLabels": [
        { "@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel", "Label": "客户", "LanguageCode": 1033 },
        { "@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel", "Label": "客户", "LanguageCode": 2052 }
      ]
    },
    "Description": {
      "@odata.type": "Microsoft.Dynamics.CRM.Label",
      "LocalizedLabels": [...]
    },
    "AttributeType": "Lookup",
    "AttributeTypeName": { "Value": "LookupType" },
    "RequiredLevel": { "Value": "None" },
    "IsValidForCreate": true,
    "IsValidForRead": true,
    "IsValidForUpdate": true,
    "Targets": ["account"]
  }
}
```

### Deep Insert 请求体三大关键点

1. **不设顶层 `ReferencingAttribute`**：Deep Insert 时 API 自动从 `Lookup.SchemaName` 推断，设置会导致 404 "Could not find an attribute with specified name"
2. **Lookup 对象必须包含 `AttributeTypeName`**：`{"Value": "LookupType"}`，缺少会导致请求失败
3. **Label 必须带 `@odata.type` 注解**：`Label` 对象需要 `"@odata.type": "Microsoft.Dynamics.CRM.Label"`，`LocalizedLabel` 需要 `"@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel"`

## 关系 SchemaName 命名规则

自定义关系的 SchemaName **必须以发布商前缀开头**（如 `new_`），否则返回 "Custom relationship names must start with a publisher prefix" 错误。

| 被引用实体 | 正确命名 | 错误命名 | 说明 |
|-----------|---------|---------|------|
| account | `account_new_payment_recognition` 或 `new_account_payment_recognition` | - | account 等少数标准实体名可作为前缀 |
| systemuser | `new_systemuser_payment_recognition_handledby` | `systemuser_new_payment_recognition_handledby` | systemuser 关系**必须**以 `new_` 开头 |
| 自定义实体 | `new_entity1_entity2` | `entity1_new_entity2` | 自定义实体关系必须以 `new_` 开头 |

**推荐统一使用 `new_` 前缀**，避免不同被引用实体的命名不一致问题。

## 级联行为类型（CascadeConfiguration）

这是创建关系最容易踩坑的地方。Dataverse 中每种级联值决定了不同的关系行为：

### 级联值含义

| API 值 | 含义 | 父子关系 |
|--------|------|---------|
| `Active` | **Parental 级联**：级联所有操作 | **是**（建立父子关系） |
| `Cascade` | **逻辑级联**：级联操作但不建立父子关系 | 否 |
| `NoCascade` | 不级联 | 否 |
| `RemoveLink` | 清除引用字段的值 | 否 |
| `Restrict` | 阻止操作 | 否 |

### 核心限制：一个实体只能有一个 Parental 关系

- `Active` 级联会建立 **parental（父子）关系**，一个实体**只能有一个** parental 关系
- `UserOwned` 实体已通过 Owner 隐式拥有一个 parental 关系
- 如果创建了 account → entity 的 parental 关系，后续所有实体（systemuser、team 等）的 Lookup 关系都会失败

### 推荐级联配置模式

**Referential 模式（推荐，适用于绝大多数自定义 Lookup）**：

```json
"CascadeConfiguration": {
  "Assign": "NoCascade",
  "Delete": "RemoveLink",
  "Merge": "NoCascade",
  "Reparent": "NoCascade",
  "Share": "NoCascade",
  "Unshare": "NoCascade"
}
```

**Parental 模式（谨慎使用，一个实体只能有一个）**：

```json
"CascadeConfiguration": {
  "Assign": "Active",
  "Delete": "Cascade",
  "Merge": "Cascade",
  "Reparent": "Active",
  "Share": "Active",
  "Unshare": "Active"
}
```

### 常见错误：MultipleParentsNotSupported

```
错误码: 0x80047007
消息: Entity: new_xxx is parented to Entity with name account.
      Cannot create another parental relation with Entity: SystemUser
```

**根因**：实体已存在一个 parental 关系（Assign/Reparent/Share/Unshare 设为 `Active` 或部分设为 `Cascade`），尝试再创建另一个 parental 关系。

**解决方案**：将所有自定义 Lookup 关系使用 Referential 模式（`NoCascade` + `RemoveLink`），只保留一个核心关系为 Parental（如需要）。

> 参考实现：`framework/utils/dataverse_client.py` 中的 `create_relationship()` 和 `_create_many_to_one_as_one_to_many()` 方法

# 九、增量更新策略

项目采用声明式对比模式：YAML 定义期望状态，与 Dataverse 当前状态对比后决定操作。

## 工作流程

1. 解析 YAML 定义获取期望状态
2. 查询 Dataverse 获取当前状态
3. 计算差异（diff）
4. 应用变更（apply）

## 三种操作

| 操作 | 条件 | 说明 |
|------|------|------|
| create | 目标不存在 | 创建新组件 |
| update | 存在但有差异 | 更新可变属性 |
| skip | 完全一致 | 无需操作 |

## 安全保证

- **不删除** YAML 中未定义的已有组件（删除逻辑已被注释掉）
- 只增不减，确保线上数据安全

## 可更新字段

- DisplayName（显示名称）
- Description（描述）
- RequiredLevel（必填级别）
- 级联配置（CascadeConfiguration：Assign/Delete/Merge/Reparent/Share/Unshare）

## 不可变字段

- SchemaName（创建后不可更改）
- AttributeType（数据类型不可更改）
- MaxLength 等结构性属性（String.MaxLength 等不可更改）

> 参考实现：`framework/agents/metadata_manager.py` 中的 `compute_diff()`、`apply_diff()`、`_compare_attribute()` 方法

# 十、错误处理与重试

## 常见 HTTP 错误码

| 状态码 | 含义 | 处理方式 |
|--------|------|---------|
| 400 | 请求格式错误或验证失败 | 检查请求体格式和字段值 |
| 401 | 未认证或 Token 过期 | 重新获取 access_token |
| 403 | 权限不足 | 检查用户/应用角色权限 |
| 404 | 资源不存在 | 确认实体/字段是否已创建 |
| 409 | 冲突（如唯一约束违反） | 检查是否存在同名组件 |
| 412 | 前置条件失败 | 检查 If-Match / If-None-Match 头 |
| 429 | 请求限流 | 等待 Retry-After 头指定的秒数后重试 |

## Dataverse 特定错误码

| 错误码 | 错误名 | 原因 | 解决方案 |
|--------|--------|------|---------|
| `0x80047007` | MultipleParentsNotSupported | 实体已有一个 parental 关系，不能再创建另一个 | 将 CascadeConfiguration 改为 Referential 模式（详见第八节） |
| `0x80060888` | 名称验证失败 | 自定义关系/字段 SchemaName 不以发布商前缀开头 | SchemaName 必须以 `new_` 前缀开头 |
| `0x80040217` | EntityNotFound | 关系或实体未找到 | 确认组件是否已创建，检查 SchemaName 拼写 |
| SDK Lookup 创建 | "Attribute of type LookupAttributeMetadata cannot be created through the SDK" | 尝试通过 Attributes 端点单独创建 Lookup 字段 | 必须使用 Deep Insert 通过 RelationshipDefinitions 端点创建 |

## 自动重试机制

- 重试策略基于 `urllib3.Retry`，指数退避
- 触发重试的状态码：429、500、502、503、504
- 默认重试次数：3 次（可通过 environments.yaml 的 `settings.retry_count` 配置）
- backoff_factor=1（第1次等1秒，第2次等2秒，第3次等4秒）

## 批量操作

- 使用 `Prefer: odata.continue-on-error` 头允许 $batch 中部分失败继续执行

> 参考实现：`framework/utils/dataverse_client.py` 中的 `_create_session()` 方法

# 十一、API 限流与并发

## 服务保护限制（Dataverse 平台级）

| 限制类型 | 值 |
|---------|------|
| 请求速率 | 6000 请求 / 5 分钟 |
| 执行时间 | 20 分钟上限 |
| 并发连接 | 52 个并发请求 |

## 本项目配置（config/environments.yaml）

| 配置项 | 值 | 说明 |
|-------|------|------|
| max_workers | 5 | 并行工作线程数 |
| max_parallel_requests | 10 | 最大并行请求数 |
| requests_per_minute | 300 | 每分钟请求上限 |
| burst_size | 50 | 突发请求上限 |
| batch_size | 100 | 批量操作大小 |
| api.timeout | 120 | 单次请求超时（秒） |

## $batch 批量操作

- 最多 1000 个子请求
- 使用 `Content-ID` 引用前序操作的结果
- 适用于无依赖关系的批量创建/更新

# 十二、本地化标签

DisplayName 和 Description 使用 `LocalizedLabels` 数组格式。

## 推荐做法

同时设置 1033（英语）和 2052（简体中文）两种语言：

```json
{
  "DisplayName": {
    "LocalizedLabels": [
      {
        "Label": "账户名称",
        "LanguageCode": 2052
      },
      {
        "Label": "Account Name",
        "LanguageCode": 1033
      }
    ]
  }
}
```

## 格式说明

- `Label`：显示文本
- `LanguageCode`：语言代码（1033=英语，2052=简体中文）
- 标签为空时返回 `null`，不发送到 API

> 参考实现：`framework/utils/dataverse_client.py` 中各处的 `_create_localized_label()` 函数
