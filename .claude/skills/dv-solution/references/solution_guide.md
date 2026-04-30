# 解决方案元数据定义

本目录包含 Power Platform 解决方案的 YAML 元数据定义。

## 目录结构

```
metadata/solutions/
├── _schema/                    # Schema 定义目录（位于上级目录）
│   └── solution_schema.yaml   # 解决方案 JSON Schema
├── _template.yaml             # 解决方案模板文件
├── payment_solution.yaml      # 示例：认款管理解决方案
└── README.md                  # 本文件

config/
└── publishers.yaml            # 发布商配置定义
```

## 解决方案文件结构

解决方案 YAML 文件包含以下主要部分：

### 1. solution（解决方案基本信息）

```yaml
solution:
  name: "solution_name"           # 唯一名称
  display_name: "解决方案显示名称"  # 显示名称
  description: "解决方案描述"      # 描述
  version: "1.0.0.0"              # 版本号
  publisher: "default"            # 发布商引用（引用 config/publishers.yaml）
  type: "Unmanaged"               # 类型：Unmanaged/Managed
```

**关于发布商（Publisher）：**

发布商是 Power Platform 的核心概念：
- **作用**：自定义组件的 SchemaName 和 LogicalName 会自动加上发布商的前缀
- **前缀**：这就是为什么自定义实体通常以 `new_` 开头的原因
- **配置**：发布商定义在 `config/publishers.yaml` 中

默认发布商配置：
```yaml
# config/publishers.yaml
publishers:
  default:
    name: "DefaultPublishercrmdev"
    display_name: "CrmDev 的默认发布者"
    prefix: "new"
```

在解决方案中引用发布商：
```yaml
# 推荐：使用引用
solution:
  publisher: "default"  # 引用 config/publishers.yaml 中的 key

# 或直接指定（不推荐）
solution:
  publisher_info:
    name: "DefaultPublishercrmdev"
    display_name: "CrmDev 的默认发布者"
    prefix: "new"
```

### 2. components（组件列表）

按类型分类组织组件：

```yaml
components:
  tables:          # 表定义
    - "tables/entity.yaml"
  forms:           # 表单定义
    - "forms/entity_main.yaml"
  views:           # 视图定义
    - "views/entity_active.yaml"
  optionsets:      # 全局选项集
    - "optionsets/custom_optionset.yaml"
  webresources:    # Web 资源
    - "webresources/js/script.js"
  plugins:         # 插件程序集
    - "plugins/Plugin/bin/Plugin.dll"
  other:           # 其他组件
    - component_type: "ribbon"
      id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

### 3. sync（同步配置）

```yaml
sync:
  enabled: true                   # 是否启用同步
  direction: "local_to_remote"    # 同步方向
  on_conflict: "skip"             # 冲突策略
  order:                          # 同步顺序
    - "table"
    - "optionset"
    - "form"
    - "view"
```

### 4. validation（验证配置）

```yaml
validation:
  strict_mode: false              # 严格模式
  check_dependencies: true        # 检查依赖
  check_naming: true              # 检查命名
```

### 5. build（构建配置）

```yaml
build:
  auto_increment_version: false   # 自动递增版本
  export_as_managed: false        # 导出为托管
  output_path: ""                 # 输出路径
```

## 创建新解决方案

1. 复制模板文件：
   ```bash
   cp metadata/solutions/_template.yaml metadata/solutions/your_solution.yaml
   ```

2. 编辑解决方案文件，填写必要信息

3. 验证解决方案定义：
   ```bash
   python -m framework.utils.schema_validator metadata/solutions/your_solution.yaml
   ```

## 同步策略

### 冲突处理（on_conflict）

| 策略 | 说明 |
|------|------|
| `skip` | 跳过已存在的组件（默认，安全） |
| `overwrite` | 用本地定义覆盖云端 |
| `merge` | 尝试合并变更 |
| `ask` | 同步前询问用户 |

### 同步方向（direction）

| 方向 | 说明 |
|------|------|
| `local_to_remote` | 本地 YAML → Dataverse（部署） |
| `remote_to_local` | Dataverse → 本地 YAML（导出） |
| `bidirectional` | 双向同步 |

## 示例

参见 `payment_solution.yaml` 了解完整的解决方案定义示例。

## 组件类型代码参考

Dataverse SolutionComponentType 选项集定义的组件类型代码：

| 类型名称 | 代码 | 说明 | Dataverse 实体 |
|----------|------|------|----------------|
| table/entity | 1 | 实体 | EntityMetadata |
| attribute | 2 | 属性 | AttributeMetadata |
| relationship | 3 | 关系 | RelationshipMetadata |
| optionset | 4/9 | 选项集 | OptionSetMetadata |
| view | 26 | SavedQuery (视图) | savedquery |
| form | 60 | SystemForm (表单) | systemform |
| webresource | 61 | WebResource | webresource |

### 常见错误

错误的组件类型代码会导致以下错误：
```
Cannot add EntityRelationshipRole with id... because it does not exist
```

这通常意味着使用了错误的 `componenttype` 值。例如：
- 视图（View）应使用代码 **26**（SavedQuery），而不是 11
- 表单（Form）应使用代码 **60**（SystemForm），而不是 10
- Web 资源应使用代码 **61**（WebResource），而不是 21

### 查询实际类型代码

可以通过 Dataverse Web API 查询实际的组件类型代码：

```
GET /api/data/v9.2/stringmaps?$filter=objecttypecode eq 'solutioncomponent'&$select=attributevalue&displayname
```
