# Power Platform Agent 架构文档

## 概述

Power Platform Agent 是一个 **Python-first 的 Dataverse 元数据部署库**（`framework_power`，CLI `pp`），实现 Power Platform 元数据的代码优先开发（类型化 Python 模型 → 同步 Dataverse）。

> 2026-08-31：legacy `framework/`（YAML 链路 + MCP Server/Agent 路由）已整体移除，本仓库为**单引擎架构**。

## 设计原则

### 内容驱动，框架服务

- **内容层 (80%)**: 元数据定义、业务逻辑、配置文件
- **引擎层 (20%)**: framework_power 库与 CLI

### 源文件 → 元数据 → 部署 的生命周期

```
源文件层 → 定义层 → 部署层
    ↓          ↓          ↓
  docs/    metadata_py/   Dataverse
```

### framework_power 设计原则

1. **Python-First**: 使用类型化 Python 数据模型替代 YAML，提升类型安全和 IDE 支持
2. **幂等性**: 所有操作支持 create-or-update，不会产生破坏性变更
3. **自包含**: 单包可导入，无外部引擎依赖
4. **组件化**: 通过 ComponentType 注册表支持可扩展的组件类型

## 引擎架构图（单引擎：framework_power）

```
┌──────────────────────────────────────────────────────────────┐
│                      Claude Code / CI / 终端                  │
│              (pp CLI · skills · project.py 工作流)           │
└─────────────────────────────┬────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│                 framework_power (Python 包)                   │
│  models/serializer → deployer (plan/deploy, 非破坏幂等)       │
│  components/ 注册表: table/optionset/webresource/form/view/   │
│                   sitemap/plugin/ribbon + compact codegen     │
│  *_sync.py 各域: solution/webresource/form/view/ribbon/       │
│                 plugin/role/sitemap/optionset/label           │
│  client/dataverse_client.py — MSAL + Dataverse Web API       │
│  workspace.py (pp-workspace.yaml) + label_sync (ADR-016)     │
└─────────────────────────────┬────────────────────────────────┘
                              │ Web API (OAuth2 client-secret)
                ┌─────────────▼─────────────┐
                │   Dataverse 环境 (dev/test/prod)  │
                └───────────────────────────┘
```

> 2026-08-31：legacy `framework/`（YAML→转换→Web API + MCP Server/Agent 路由）
> 已整体移除；上图为此前的"双框架架构图"的替代。历史设计见 git 与 ADR。

## framework_power 模块架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    framework_power (独立库)                      │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Public API (__init__.py)              │  │
│  │  Table, Column, Relationship, Label, AttributeType...  │  │
│  │  deploy_table, plan_table, reverse_table, lint_table... │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                │
│  ┌───────────────┬───────────┴───────────┬────────────────┐   │
│  ▼               ▼                       ▼                ▼    │
│ models.py    serializer.py           deployer.py      runtime.py │
│ 类型模型        模型序列化              部署逻辑          运行时引导 │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                     client/ (API 客户端)                  │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐  │  │
│  │  │ dataverse_  │  │   auth.py   │  │ env_config.py │  │  │
│  │  │ client.py   │  │  (MSAL)     │  │               │  │  │
│  │  └─────────────┘  └─────────────┘  └───────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                │
│  ┌───────────────────────────┴───────────────────────────────┐  │
│  │                    components/ (组件注册表)                │  │
│  │  models.py | optionset | webresource | form | view | plugin  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                │
│  ┌─────────────┬─────────────┬─────────────┬────────────────┐ │
│  ▼             ▼             ▼             ▼                ▼  │
│ optionset_  webresource_  form_       view_           plugin_ │
│ sync.py     sync.py       sync.py     sync.py         sync.py │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              solution_deployer.py / solution_*.py         │  │
│  │              解决方案管理 (Publisher → Solution → Components) │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                      workflow.py                          │  │
│  │              跨阶段开发工作流编排 (Phase 9)                │  │
│  │  Global Optionset → Entity → WebResource → Plugin        │  │
│  │  → Form → View → [Roles] → Ribbon                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 目录架构

```
power-platform-agent/
├── framework_power/       # Python-first 引擎（本仓库唯一引擎）
│   ├── __init__.py       # 公共 API 导出
│   ├── __main__.py       # pp 入口
│   ├── cli.py            # CLI 入口
│   ├── models.py         # 类型化数据模型 (Table, Column, Label...)
│   ├── serializer.py     # 模型序列化器
│   ├── deployer.py       # 表部署器 (幂等 create-or-update)
│   ├── runtime.py         # 运行时引导 (get_client, argparse_env)
│   ├── registry.py        # 表定义注册表
│   ├── lint.py           # 离线验证
│   ├── codegen.py        # Python 源码生成
│   ├── reverse.py        # 反向工程 (环境 → 模型)
│   │
│   ├── client/            # API 客户端
│   │   ├── __init__.py
│   │   ├── dataverse_client.py  # Dataverse Web API 客户端
│   │   ├── auth.py       # MSAL 认证
│   │   ├── env_config.py # 环境配置加载
│   │   ├── plugin_build.py  # .NET 插件构建
│   │   └── retry_helper.py  # 重试帮助器
│   │
│   ├── components/        # 组件类型注册表
│   │   ├── __init__.py   # ComponentType 注册表
│   │   ├── models.py     # 组件模型 (Solution, Publisher, Form, View, Plugin, Ribbon...)
│   │   ├── optionset.py  # 选项集组件处理器
│   │   ├── webresource.py  # Web Resource 组件处理器
│   │   ├── form.py       # 表单组件处理器
│   │   ├── view.py       # 视图组件处理器
│   │   └── plugin.py     # 插件组件处理器
│   │
│   ├── optionset_sync.py # 全局选项集同步 (discover/plan/sync；deploy 依赖优先调用 + pp optionset CLI)
│   ├── webresource_sync.py  # Web Resource 同步
│   ├── form_sync.py     # 表单同步
│   ├── form_xml.py      # 表单 XML 工具
│   ├── view_sync.py     # 视图同步
│   ├── view_xml.py      # 视图 XML 工具
│   ├── ribbon_sync.py   # Ribbon 命令同步
│   ├── ribbon_xml.py    # Ribbon XML 工具
│   ├── plugin_sync.py   # 插件部署
│   │
│   ├── solution_*.py     # 解决方案管理
│   │   ├── solution_deployer.py   # 解决方案部署
│   │   ├── solution_reverse.py    # 解决方案反向
│   │   ├── solution_codegen.py    # 解决方案代码生成
│   │   └── solution_zip.py       # 解决方案 ZIP 导出/导入
│   │
│   ├── role_*.py         # 安全角色管理
│   │   ├── role_deployer.py
│   │   ├── role_reverse.py
│   │   ├── role_codegen.py
│   │   └── role_registry.py
│   │
│   ├── workflow.py       # 跨阶段开发工作流编排
│   └── examples/         # 示例代码
│
├── metadata_py/          # Python 元数据定义 (framework_power)
│   ├── project.py       # 项目清单
│   ├── tables/           # 表定义 Python 文件
│   ├── forms/            # 表单定义
│   ├── views/            # 视图定义
│   ├── ribbons/         # Ribbon 定义
│   └── optionsets/       # 选项集定义
│
├── docs/                 # 文档层
│   ├── features/         # 按功能迭代组织（PRD/设计/输出）
│   ├── templates/        # 需求文档模板库 (PRD/实体设计/Excel)
│   ├── data_dictionary/  # Workspace 产物，从云端同步或脚本生成
│   ├── spec/             # 规范文档
│   └── guides/           # 使用指南


├── metadata/             # 元数据层 (legacy YAML)
│   ├── _schema/          # Schema定义
│   ├── tables/          # 表定义YAML
│   ├── forms/           # 表单定义
│   └── ...
│
├── scripts/              # 脚本层
│   ├── generate_data_dictionary.py
│   └── hooks/           # Git hooks
│
├── webresources/         # Web Resource源文件
│   ├── css/
│   ├── js/
│   ├── html/
│   └── img/
│
├── plugins/              # .NET插件源码
│
├── config/               # 配置文件
│
├── setup.py              # 包安装配置
└── requirements.txt
```

**说明**：
- **framework_power/** - Python-first 引擎（本仓库唯一引擎）
- **metadata_py/** - framework_power 的元数据定义（类型化 Python，而非 YAML）
- **docs/** - 按内容生命周期分层 (PRD/设计 → 模板 → 产物)，所有文档类输入输出统一管理
- **docs/data_dictionary/** - Workspace 产物，由 `pp reverse <table> --dictionary` 从 Dataverse 云端生成

## 核心组件

### 1. pp CLI (cli.py)

统一入口，负责：
- 表/解决方案/各域子命令（lint/plan/deploy/reverse/…）
- workspace 发现与目录解析（pp-workspace.yaml）
- 认证引导（get_client，client-secret + MSAL）

### 2. Deployer (deployer.py)

表部署器：
- 非破坏幂等同步（entity/attributes/relationships/alternate keys）
- ADR-016 自动视图/窗体名双语标签（label_sync）
- 依赖优先的全局选项集先行同步（ADR-011）

### 3. 组件注册表 (components/)

统一分发各组件类型的 serialize/deploy/plan/reverse/codegen/lint：
table / optionset / webresource / form / view / sitemap / plugin / ribbon；
`compact.py` 提供逆向 codegen 的 attrs 去冗余（紧凑表示 + normalize diff）。

### 4. 各域 sync 模块 (*_sync.py)

solution / optionset / webresource / form / view / ribbon / plugin / role /
sitemap / label：每域提供 plan/sync/reverse 与发布语义。

### 5. Dataverse Client (client/dataverse_client.py)

MSAL client-credentials 认证 + Dataverse Web API 全量封装（元数据/数据/操作/
PublishXml/解决方案 ZIP/插件注册/loc labels）。

**虚拟字段检测规则**：
| 类型 | 检测模式 | 示例 |
|------|----------|------|
| Lookup _name 后缀 | `_[a-z]+_name$` | `primarycontactid_name` |
| 计算字段 | `is_calculated: true` | - |
| 汇总字段 | `aggregate_type` 存在 | - |

**Git Hook 集成**：
- 触发时机：Pre-commit
- 处理范围：仅变更的文件（仅 Gen 1 YAML `metadata/` 路径）
- 自动更新：docs/data_dictionary/（Workspace 产物）

## framework_power 核心模块

### 1. 类型化数据模型 (models.py)

```python
from framework_power import Table, Column, Relationship, Label, AttributeType

table = Table(
    schema_name="new_ProjectBudget",
    display_name=Label.bilingual("项目预算", "Project Budget"),
    columns=[
        Column("new_Name", AttributeType.String,
               display_name=Label.bilingual("名称", "Name"),
               is_primary_name=True, required=RequiredLevel.ApplicationRequired, max_length=200),
    ],
)
```

**核心模型**：
- `Label` / `LocalizedLabel` - 多语言标签 (zh-CN 2052, en-US 1033)
- `Table` - 表定义
- `Column` - 非查找属性
- `LookupColumn` - 查找属性
- `Relationship` - 关系 (1:N, N:N)
- `AttributeType` - 属性类型枚举
- `RequiredLevel` - 必填级别枚举

### 2. 部署器 (deployer.py)

幂等表部署器，实现 create-or-update 策略：

```python
from framework_power import deploy_table, plan_table, get_client

client = get_client("dev")
result = deploy_table(client, table, prefix="new", solution="MySolution")
```

**核心函数**：
- `deploy_table()` - 创建或同步表到 Dataverse；`optionsets_dir=` 开启依赖优先
  全局选项集自动同步（ADR-011，CLI 默认从 workspace `metadata_py/optionsets/` 解析）
- `plan_table()` - 只读预演，返回将执行的操作（含引用选项集 would_* 计划）
- `ensure_referenced_optionsets()` - 收集表中 `optionset_name` 引用并先行同步
  （create-only、幂等；缺失本地定义时只读检查 + `optionsets_missing` 告警）

### 3. Dataverse API 客户端 (client/dataverse_client.py)

轻量级 Web API 客户端：
- 请求会话管理（含重试策略）
- OAuth 2.0 Bearer Token 管理
- 元数据操作 (EntityDefinitions, Attributes, Relationships)
- 组件操作 (WebResources, SystemForms, SavedQueries, PluginAssemblies...)
- 解决方案操作 (Publishers, Solutions, AddSolutionComponent)
- 发布操作 (PublishAllXml, PublishXml)

### 4. 组件注册表 (components/)

可扩展的组件类型系统：

```python
COMPONENT_DEPLOY_ORDER = (
    "optionset",    # 依赖顺序
    "table",
    "webresource",
    "form",
    "view",
    "sitemap",      # Phase 10 / ADR-015
    "plugin",
)
```

**支持的组件类型**：
| 类型 | SolutionComponentCode | 说明 |
|------|---------------------|------|
| table | 1 | 表/实体 |
| optionset | 9 | 全局选项集 |
| view | 26 | 保存的查询 |
| workflow | 29 | 工作流/自定义 Action 定义（ADR-012） |
| form | 60 | 系统表单 |
| webresource | 61 | Web 资源 |
| sitemap | 62 | App SiteMap 实体菜单（app-aware，ADR-015/Phase 10） |
| plugin (assembly) | 91 | 插件程序集（降级路径） |
| plugin (step) | 92 | SDK message 处理步骤 |
| plugin (package) | 10030 | NuGet 插件包（包路径的解决方案单元） |

### 5. 解决方案管理 (solution_*.py)

解决方案部署 5 步流程：

```
1. 确保 Publisher 存在
2. 创建/更新 Solution 对象
3. 按依赖顺序部署组件
4. 添加自定义组件到解决方案
5. 发布所有自定义
```

### 6. 工作流编排 (workflow.py)

跨阶段开发工作流，支持两个解决方案：

```
┌────────────────────────────────────────────────────────────────┐
│  Main Solution              │  Ribbon Solution                │
├─────────────────────────────┼─────────────────────────────────┤
│ Global Optionset            │                                  │
│     ↓                       │                                  │
│ Table (+ Relationships)     │                                  │
│     ↓                       │                                  │
│ WebResource                 │                                  │
│     ↓                       │                                  │
│ Plugin                      │                                  │
│     ↓                       │                                  │
│ Form                        │                                  │
│     ↓                       │                                  │
│ View                        │                                  │
│     ↓                       │                                  │
│ [Roles]                     │                                  │
│     ↓                       │                                  │
│ Ribbon                      │ ← Ribbon (专用解决方案)           │
└─────────────────────────────┴─────────────────────────────────┘
                    ↓
              PublishAllXml
```

## 数据流

### framework_power 元数据创建流程

```
1. 开发者编写 Python 定义
   ↓
2. from framework_power import Table, deploy_table
   ↓
3. deploy_table(client, table) 幂等部署
   ↓
4. plan_table(client, table) 预览变更
   ↓
5. 或 deploy_workflow(client, project) 全流程编排
```

### 插件部署流程

```
1. 开发者修改 .NET 插件代码
   ↓
2. plugin_build.py 构建 DLL/.nupkg（NuGet PluginPackage 优先）
   ↓
3. plugin_sync.py 部署程序集/包（content 更新前清孤儿 step/plugintype）
   ↓
4. 注册/更新 Plugin Steps（幂等，按名查重）
   ↓
5. 注册 Pre/Post Step Images（Create→Id，Update/Delete→Target；ADR-012）
   ↓
6. Custom Action 全链路（workflow 创建+XAML → 激活 → SDK message → Invoke step）
   ↓
7. 添加到解决方案（10030 包 / 91 程序集 / 92 step / 29 workflow）
   ↓
8. PublishAllXml
```

### 解决方案部署流程

```
1. resolve_publisher() 确保发布商存在
   ↓
2. create/update Solution 对象
   ↓
3. 按 COMPONENT_DEPLOY_ORDER 部署组件
   ↓
4. add_solution_component() 添加组件到解决方案
   ↓
5. publish_all_xml() 发布所有自定义
```

## 命名规则

### Schema Name 转换

根据 `config/naming_rules.yaml` 配置，命名会自动转换：

| 输入 | lowercase | camelCase | PascalCase |
|-----|-----------|-----------|------------|
| `AccountNumber` | `new_account_number` | `newAccountNumber` | `NewAccountNumber` |
| `CustomerEmail` | `new_customer_email` | `newCustomerEmail` | `NewCustomerEmail` |

### Web Resource 命名

遵循模式：`{prefix}{category}/{name}.{ext}`

| 类型 | 输入 | 输出 |
|-----|------|------|
| CSS | `account_form` | `new_css/account_form.css` |
| JS | `handler` | `new_js/handler.js` |
| HTML | `dashboard` | `new_html/dashboard.html` |

## 扩展性

### framework_power 组件扩展

在 `components/` 目录下注册新组件类型：

```python
# components/my_component.py
from framework_power.components import ComponentType

KEY = "my_component"
SOLUTION_CODE = 9999
MODEL_CLS = MyModel

def serialize(model): ...
def deploy(client, model, *, prefix): ...
def plan(client, model, *, prefix): ...
def reverse(client, ident): ...
def codegen(model): ...
def exists(client, model): ...
def resolve_id(client, model): ...
def lint(model, *, prefix): ...

# 自动注册
```

### 自定义处理器 (legacy framework)

在 `config/publishers.yaml` 的 `naming` 部分配置命名规则和验证器。

## 配置文件

- `config/environments.yaml` - 环境配置 (dev/test/prod)
- `config/publishers.yaml` - 发布商 + 命名规则
- `config/pipeline.yaml` - CI/CD 流水线
- `config/environment_settings.yaml` - 环境变量与连接引用
- `.claude/context_config.yaml` - LLM 上下文配置
- `metadata/optionsets/global_optionsets.yaml` - 全局选项集定义

## 元数据工作流

### framework_power 开发流程

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Python 定义     │ → │  幂等部署        │ → │   Dataverse     │
│  (metadata_py/)  │    │  deploy_table() │    │   (云环境)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                    │
         ▼                    ▼
┌─────────────────┐    ┌─────────────────┐
│  plan_table()   │    │  metadata_py/    │
│  (预演)         │    │  project.py     │
└─────────────────┘    └─────────────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │  deploy_workflow │
                     │  (全流程编排)     │
                     └─────────────────┘
```

### 完整开发流程 (legacy)

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  源文件     │ -> │ YAML元数据  │ -> │  Dataverse  │
│  (Excel)    │    │ (metadata/) │    │  (部署)      │
└─────────────┘    └─────────────┘    └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │ 数据字典    │
                   │ (自动生成)  │
                   └─────────────┘
```

### 选项集复用流程

```
1. 在 metadata_py/optionsets/ 中定义全局选项集 (OPTIONSET: GlobalOptionSet)
   ↓
2. 表定义中使用 OptionSet 引用 (Column(..., optionset_name="<name>"))
   ↓
3. pp deploy <table>：依赖优先自动同步选项集 → 再部署实体/字段
   (ADR-011；带 --solution 时选项集加入同一解决方案 code 9)
4. 数据字典自动生成选项集文档
   ↓
5. LLM 读取文档获取正确的选项值
   (独立管理：pp optionset list | plan | deploy)

注：裸 `create_attribute` 新建绑定既有全局选项集的字段时，payload 必须用
`GlobalOptionSet@odata.bind` 绑定语法（内联 `OptionSet.IsGlobal+Name` 引用被
`0x80048403` 拒），详见 ADR-014。
```

### Git Hook 触发流程

```
1. 开发者修改 metadata/tables/*.yaml（Gen 1 YAML，Legacy）
   ↓
2. git add 添加文件到暂存区
   ↓
3. git commit 触发 pre-commit hook
   ↓
4. generate_data_dictionary.py 执行（读取 Gen 1 YAML）
   ↓
5. 更新 docs/data_dictionary/（Workspace 产物）
   ↓
6. 将生成的文档添加到本次提交
   ↓
7. 提交完成

注意：metadata_py/tables/*.py（Gen 2 Python 定义）的变更不触发此 hook。
从环境同步数据字典：`pp reverse <table> --env <env> --dictionary`（云端为准）。
```

## 安全考虑

1. **敏感信息存储**: 使用环境变量存储凭据
2. **Token 管理**: MSAL 自动处理 token 刷新
3. **标准表保护**: 禁止修改标准表元数据
4. **操作审计**: 记录所有重要操作
5. **幂等性保证**: 所有操作不会产生意外破坏

## 性能优化

1. **批处理请求**: 使用 OData 批处理减少网络往返
2. **缓存**: 元数据和 token 缓存
3. **并发控制**: 限制并发请求数避免限流
4. **重试机制**: 指数退避重试策略
5. **延迟配置**: 可调延迟避免元数据传播锁竞争

## 开发阶段 (Phase)

| Phase | 功能 | 状态 |
|-------|------|------|
| 1 | 表部署 (Table, Column, Relationship) | ✅ |
| 2 | 解决方案管理 (Solution, Publisher, 组件注册表) | ✅ |
| 3 | 表单/视图同步 | ✅ |
| 4 | 插件部署 | ✅ |
| 5 | Web Resource 同步 | ✅ |
| 6 | 安全角色管理 | ✅ |
| 7 | Ribbon 命令同步 | ✅ |
| 8 | 插件包 (NuGet) / 自定义 Action | ✅ |
| 9 | 跨阶段工作流编排 | ✅ |

## 后续扩展方向

| 方向 | 说明 |
|------|------|
| 表单和视图管理 | 创建/修改表单和视图的完整 CRUD 支持 |
| 全局选项集管理 | 创建全局选项集、更新选项集选项 |
| 解决方案管理 | 添加到解决方案、解决方案导入/导出 |
| 批量操作 | 批量应用多个 YAML、增量同步 |
| 回滚功能 | 记录变更历史，支持回滚到之前版本 |
