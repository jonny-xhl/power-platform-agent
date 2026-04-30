---
name: dv-solution
description: 管理 Power Platform 解决方案（Solution）的创建、同步、导入导出。当用户需要创建解决方案、管理解决方案组件、同步解决方案到 Dataverse、导入导出解决方案文件、处理发布商（Publisher）配置时使用此技能。包括"创建解决方案"、"解决方案同步"、"导入解决方案"、"导出解决方案"、"添加组件到解决方案"、"发布商管理"等短语，或处理 Power Platform Solution/publisher 相关操作时。
---

# Power Platform 解决方案管理

此技能提供 Power Platform 解决方案（Solution）的完整管理功能，包括解决方案的创建、组件管理、同步到 Dataverse、以及发布商（Publisher）配置。

## 解决方案概述

Power Platform 解决方案是**组件的容器**，用于将相关组件（表、表单、视图、Web 资源等）打包在一起进行部署和管理。

### 关键概念

| 概念 | 说明 |
|------|------|
| **解决方案 (Solution)** | 组件的容器，用于打包和部署 |
| **发布商 (Publisher)** | 定义组件的前缀（如 `new_`），一个解决方案必须关联一个发布商 |
| **组件 (Component)** | 表、表单、视图、选项集、Web 资源等 |
| **非托管 (Unmanaged)** | 可修改的解决方案，用于开发环境 |
| **托管 (Managed)** | 不可修改的解决方案，用于生产环境 |

### 依赖顺序

**重要**: 必须按照以下顺序操作：

```
发布商 (Publisher) → 解决方案 (Solution) → 组件 (Components)
```

1. 首先确保发布商存在
2. 然后创建/更新解决方案
3. 最后同步组件到解决方案

## 使用场景

在以下情况使用此技能：
- 创建新的 Power Platform 解决方案
- 将元数据组件添加到解决方案
- 同步解决方案到 Dataverse 环境
- 导出解决方案为 .zip 文件
- 导入解决方案到目标环境
- 配置或切换发布商前缀

## 解决方案 YAML 结构

解决方案定义文件存放在 `metadata/solutions/` 目录：

```yaml
$schema: "../_schema/solution_schema.yaml"

# ================================================================
# 解决方案基本信息
# ================================================================
solution:
  schema_name: "your_solution_name"    # 唯一名称
  display_name: "您的解决方案显示名称"  # 显示名称
  description: "详细描述解决方案的功能和用途"
  version: "1.0.0.0"                   # 版本号：主版本.次版本.内部版本.修订
  publisher: "default"                 # 发布商引用（引用 config/publishers.yaml）
  type: "Unmanaged"                    # 类型：Unmanaged/Managed

# ================================================================
# 解决方案组件（按类型分类）
# ================================================================
components:
  tables:                              # 表定义
    - "tables/your_entity.yaml"
  forms:                               # 表单定义
    - "forms/your_entity_main.yaml"
  views:                               # 视图定义
    - "views/your_entity_active.yaml"
  optionsets:                          # 全局选项集
    - "optionsets/your_global_optionset.yaml"
  webresources:                        # Web 资源
    - "webresources/js/your_script.js"
  plugins:                             # 插件程序集
    - "plugins/YourPlugin/bin/Debug/YourPlugin.dll"
  other:                               # 其他组件
    - component_type: "ribbon"
      id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
      schema_name: "custom_ribbon_command"

# ================================================================
# 同步配置
# ================================================================
sync:
  enabled: true                        # 是否启用同步
  direction: "local_to_remote"         # 同步方向
  on_conflict: "skip"                  # 冲突策略
  order:                               # 同步顺序（遵循依赖关系）
    - "optionset"   # 全局选项集（必须先于表）
    - "table"       # 表（实体）定义
    - "form"        # 表单（依赖表的字段）
    - "view"        # 视图（依赖表的字段）
    - "webresource" # Web 资源
    - "plugin"      # 插件程序集

# ================================================================
# 验证配置
# ================================================================
validation:
  strict_mode: false                   # 严格模式
  check_dependencies: true             # 检查依赖
  check_naming: true                   # 检查命名规范

# ================================================================
# 构建配置
# ================================================================
build:
  auto_increment_version: false        # 自动递增版本号
  export_as_managed: false             # 导出为托管解决方案
  output_path: ""                      # 导出文件输出路径
  include_dependencies: true           # 包含依赖组件
```

## 发布商（Publisher）配置

发布商定义在 `config/publishers.yaml` 中：

```yaml
publishers:
  default:
    schema_name: "DefaultPublishercrmdev"
    display_name: "CrmDev 的默认发布者"
    prefix: "new"

  # 可以定义多个发布商
  contoso:
    schema_name: "ContosoPublisher"
    display_name: "Contoso 发布者"
    prefix: "contoso"

current: "default"  # 当前使用的发布商
```

### 发布商的作用

- **前缀管理**: 自定义组件的 SchemaName 会自动加上发布商前缀
- **标识归属**: 区分不同供应商/开发者创建的组件
- **命名规范**: 确保组件名称在全局范围内唯一

### 前缀命名规则

| 规则 | 说明 |
|------|------|
| 长度 | 3-8 个字符 |
| 字符 | 仅字母和数字，必须以字母开头 |
| 常见示例 | `new`, `contoso`, `adv`, `cust` |

## 组件分类路径

解决方案组件按类型组织，路径相对于 `metadata/` 目录：

| 组件类型 | components 键 | 路径示例 |
|----------|---------------|----------|
| 表 (Table) | `tables` | `tables/payment_recognition.yaml` |
| 表单 (Form) | `forms` | `forms/payment_recognition_main.yaml` |
| 视图 (View) | `views` | `views/payment_recognition_active.yaml` |
| 选项集 (OptionSet) | `optionsets` | `optionsets/global_optionsets.yaml` |
| Web 资源 | `webresources` | `webresources/js/form.js` |
| 插件 | `plugins` | `plugins/Plugin/bin/Debug/Plugin.dll` |

## 解决方案同步工作流

完整的解决方案同步包含以下 5 个步骤：

```
1. 发布商检查与创建
   └── 确保 Publisher 存在，不存在则创建

2. 解决方案对象创建/更新
   └── 在 Dataverse 中创建 Solution 容器

3. 组件同步到 Dataverse
   └── 按依赖顺序创建/更新表、表单、视图等

4. 组件添加到解决方案
   └── 将已同步的组件添加到 Solution 容器中

5. 发布解决方案
   └── 发布自定义项使更改生效
```

### 工作流详细说明

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1 | 检查发布商 | 从 YAML 获取发布商配置，确保在 Dataverse 中存在 |
| 2 | 创建解决方案 | 使用 `create_solution` API 创建 Solution 对象 |
| 3 | 同步组件 | 按依赖顺序同步组件到 Dataverse |
| 4 | 添加组件 | 使用 `add_solution_component` API 将组件加入 Solution |
| 5 | 发布 | 使用 `publish_solution` API 发布自定义项 |

**重要**: 只有完成所有步骤后，解决方案才能在 Dataverse 中正常工作。特别是第 5 步发布操作，不发布则无法在运行时使用新创建的组件。

## 组件类型代码参考

Dataverse SolutionComponentType 选项集定义的组件类型代码（用于调试和问题排查）：

| 类型名称 | 代码 | 说明 | Dataverse 实体 |
|----------|------|------|----------------|
| table/entity | 1 | 实体 | EntityMetadata |
| attribute | 2 | 属性 | AttributeMetadata |
| relationship | 3 | 关系 | RelationshipMetadata |
| optionset | 4/9 | 选项集 | OptionSetMetadata |
| view | 26 | SavedQuery (视图) | savedquery |
| form | 60 | SystemForm (表单) | systemform |
| webresource | 61 | WebResource | webresource |

**注意**: 错误的类型代码会导致添加组件时出现 "Cannot add...because it does not exist" 错误。

## 同步策略

### 同步方向 (direction)

| 方向 | 说明 |
|------|------|
| `local_to_remote` | 本地 YAML → Dataverse（部署） |
| `remote_to_local` | Dataverse → 本地 YAML（导出） |
| `bidirectional` | 双向同步 |

### 冲突解决 (on_conflict)

| 策略 | 说明 |
|------|------|
| `skip` | 跳过已存在的组件（默认，安全） |
| `update` | 更新已存在的组件 |
| `replace` | 替换整个组件 |
| `create_only` | 仅创建新组件 |

### 同步顺序

组件按依赖顺序同步：

```
optionset → table → form → view → webresource → plugin
```

**依赖说明**：
- **全局选项集** - 必须先创建，因为表字段会引用它们
- **表** - 引用全局选项集，字段级选项集在创建表时一起创建
- **表单** - 依赖表的字段定义
- **视图** - 依赖表的字段定义
- **Web 资源** - 独立组件
- **插件** - 可能依赖表

## 创建新解决方案

### 步骤1: 复制模板

```bash
cp .claude/skills/dv-solution/references/solution_template.yaml \
   metadata/solutions/your_solution.yaml
```

### 步骤2: 编辑解决方案文件

填写必要信息：
- 解决方案名称
- 显示名称
- 发布商引用
- 组件列表

### 步骤3: 验证解决方案定义

```bash
python -m framework.utils.schema_validator metadata/solutions/your_solution.yaml
```

### 步骤4: 同步到 Dataverse

```bash
# 通过 MCP 工具
solution_sync_from_yaml --file metadata/solutions/your_solution.yaml

# 或通过 Python
python -m framework.agents.solution_agent sync metadata/solutions/your_solution.yaml
```

## MCP 工具

此技能通过以下 MCP 工具实现功能：

| 工具 | 说明 |
|------|------|
| `solution_sync_from_yaml` | 从 YAML 同步解决方案 |
| `solution_plan` | 预览同步计划（dry-run） |
| `solution_validate` | 验证解决方案定义 |
| `solution_scan` | 扫描解决方案状态 |
| `publisher_create` | 创建发布商 |
| `publisher_list` | 列出所有发布商 |

## 参考文档

详细说明请参阅:
- `.claude/skills/dv-solution/references/solution_template.yaml` - 解决方案模板
- `.claude/skills/dv-solution/references/solution_guide.md` - 完整指南
- `metadata/_schema/solution_schema.yaml` - JSON Schema 定义

## 组件关联解决方案

每个组件 YAML 可以声明所属的解决方案：

```yaml
# 在组件 YAML 文件中
solution:
  schema_name: "payment_solution"  # 所属解决方案名称
  auto_add: true                  # 是否自动添加到解决方案
```

这支持两种同步模式：
1. **组件级同步**: 同步单个组件时自动添加到指定解决方案
2. **解决方案级同步**: 从解决方案 YAML 同步所有组件
