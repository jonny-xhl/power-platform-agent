# Power Platform Agent 架构文档

## 概述

Power Platform Agent 是一个基于 Hermes Agent 框架构建的 Power Platform 开发辅助工具。它通过 MCP (Model Context Protocol) 服务器为 Claude Code 和 Cursor 提供工具访问，实现 Power Platform 元数据的代码优先开发。

## 设计原则

### 内容驱动，框架服务

- **内容层 (80%)**: 元数据定义、业务逻辑、配置文件
- **框架层 (20%)**: Agent 代码、MCP 服务、工具路由

### 源文件 → 元数据 → 部署 的生命周期

```
源文件层 → 转换层 → 元数据层 → 部署层
    ↓          ↓          ↓          ↓
  sources/  transformers/ metadata/  Dataverse
```

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      Claude Code / Cursor                       │
│                         (MCP Client)                            │
└─────────────────────────────┬───────────────────────────────────┘
                              │ MCP Protocol
┌─────────────────────────────▼───────────────────────────────────┐
│                    MCP Server (mcp_serve.py)                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Tool Router                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐     │
│  │ Core Agent   │  │ Metadata     │  │ Plugin           │     │
│  │              │  │ Agent        │  │ Agent            │     │
│  │ - Auth       │  │              │  │                  │     │
│  │ - Naming     │  │ - Tables     │  │ - Build          │     │
│  │ - Env Mgmt   │  │ - Forms      │  │ - Deploy         │     │
│  └──────────────┘  │ - Views      │  │ - Step Register  │     │
│  ┌──────────────┐  │ - OptionSets │  └──────────────────┘     │
│  │ Solution     │  └──────────────┘  ┌──────────────────┐     │
│  │ Agent        │                      │ State           │     │
│  │              │                      │ Management      │     │
│  │ - Import     │                      │                 │     │
│  │ - Export     │                      │                 │     │
│  │ - Sync       │                      │                 │     │
│  └──────────────┘                      └──────────────────┘     │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                    Data Dictionary Layer                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │         generate_data_dictionary.py                      │   │
│  │  - YAML Parser  - Virtual Field Filter  - MD Generator  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│              Power Platform API Client Layer                    │
│  ┌────────────┐ ┌────────────┐ ┌──────────────────────┐        │
│  │ Web API    │ │ PAC CLI    │ │ Dataverse SDK        │        │
│  │ Wrapper    │ │ Wrapper    │ │ (for .NET plugins)   │        │
│  └────────────┘ └────────────┘ └──────────────────────┘        │
└─────────────────────────────┬───────────────────────────────────┘
                              │ OAuth 2.0
┌─────────────────────────────▼───────────────────────────────────┐
│                    Dataverse Online                             │
└─────────────────────────────────────────────────────────────────┘
```

## 目录架构

```
power-platform-agent/
├── framework/             # 框架层 (可复用核心组件)
│   ├── agents/            # 代理实现
│   │   ├── core_agent.py
│   │   ├── metadata_agent.py
│   │   ├── plugin_agent.py
│   │   └── solution_agent.py
│   ├── utils/             # 工具函数
│   │   ├── dataverse_client.py
│   │   ├── yaml_parser.py
│   │   ├── schema_validator.py
│   │   └── naming_converter.py
│   └── mcp_serve.py       # MCP服务入口
│
├── sources/               # 源文件层
│   ├── templates/         # Excel/Word/PPT模板
│   ├── features/          # 按功能迭代组织
│   │   └── feature-xxx/
│   │       ├── 01-requirements/    # BRD/PRD/流程图
│   │       └── 02-designs/         # Excel + Markdown
│   └── library/           # 可复用YAML片段
│       ├── table_fragments/
│       ├── form_patterns/
│       └── view_patterns/
│
├── transformers/          # 转换器层 (架构保留，暂不实现)
│
├── metadata/              # 元数据层
│   ├── _schema/           # Schema定义
│   ├── tables/            # 表定义YAML
│   ├── forms/             # 表单定义
│   ├── views/             # 视图定义
│   ├── webresources/      # Web Resource配置
│   ├── ribbon/            # 命令栏定义
│   ├── sitemap/           # 应用导航定义
│   └── optionsets/        # 全局选项集
│
├── docs/                  # 文档层
│   ├── spec/              # 规范文档
│   ├── guides/            # 使用指南
│   └── data_dictionary/   # Git hook自动生成
│       ├── index.md
│       ├── all_tables.md
│       ├── all_optionsets.md
│       ├── tables/
│       └── optionsets/
│
├── scripts/               # 脚本层
│   ├── generate_data_dictionary.py
│   ├── hooks/             # Git hooks
│   │   └── pre-commit.sh
│   └── install_hooks.sh
│
├── webresources/          # Web Resource源文件
│   ├── css/
│   ├── js/
│   ├── html/
│   └── img/
│
├── plugins/               # .NET插件源码
│
├── config/                # 配置文件
│
├── .claude/               # Claude Code配置
│   └── context_config.yaml
│
├── build_and_validate.py  # 构建验证脚本
├── setup.py               # 包安装配置
├── test_imports.py        # 导入测试
├── install.sh / install.bat
└── requirements.txt
```

**说明**：
- **framework/** - 框架代码统一管理，便于复用和迁移
- **sources/** - 按内容生命周期分层 (源文件 → 转换 → 元数据 → 文档)
- **metadata/** - YAML元数据定义，按类型组织
- **docs/data_dictionary/** - Git hook自动生成，无需手动维护

## 核心组件

### 1. MCP Server (mcp_serve.py)

MCP 服务器是整个系统的入口点，负责：
- 暴露工具给 Claude Code/Cursor
- 路由工具调用到相应的代理
- 管理代理生命周期
- 提供资源访问

### 2. Core Agent

核心代理处理：
- 用户认证 (OAuth 2.0)
- 环境管理
- 命名规则转换
- 健康检查

### 3. Metadata Agent

元数据代理处理：
- 表(Table) 元数据管理
- 表单(Form) 元数据管理
- 视图(View) 元数据管理
- Web Resource 管理
- 元数据验证

### 4. Plugin Agent

插件代理处理：
- .NET 插件构建
- 程序集部署
- Step 注册和管理
- 监听模式

### 5. Solution Agent

解决方案代理处理：
- 解决方案导入/导出
- 差异对比
- 双向同步
- 组件管理

### 6. Data Dictionary Generator

数据字典生成器处理：
- YAML 元数据解析
- 虚拟字段过滤
- Markdown 文档生成
- 索引自动更新

**虚拟字段检测规则**：
| 类型 | 检测模式 | 示例 |
|------|----------|------|
| Lookup _name 后缀 | `_[a-z]+_name$` | `primarycontactid_name` |
| 计算字段 | `is_calculated: true` | - |
| 汇总字段 | `aggregate_type` 存在 | - |

**Git Hook 集成**：
- 触发时机：Pre-commit
- 处理范围：仅变更的文件
- 自动更新：docs/data_dictionary/

## 数据流

### 元数据创建流程

1. 用户在 Claude Code 中输入需求
2. MCP Server 接收请求
3. Metadata Agent 解析/验证 YAML 元数据
4. Core Agent 应用命名转换
5. Metadata Agent 调用 Dataverse API 创建元数据
6. 返回结果给用户

### 插件部署流程

1. 开发者修改 .NET 插件代码
2. Plugin Agent 监测到变更
3. 调用 dotnet build 构建程序集
4. 读取生成的 DLL 文件
5. 通过 Dataverse API 部署程序集
6. 注册/更新 Plugin Steps

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

### 自定义处理器

在 `config/extensions.yaml` 中注册自定义处理器：

```yaml
custom_handlers:
  - name: "customAttributeValidator"
    type: "attribute"
    module: "extensions.custom_validators"
    class: "CustomAttributeValidator"
    enabled: true
```

### 钩子点

支持的钩子：
- `before_apply` - 应用前执行
- `after_apply` - 应用后执行
- `on_error` - 错误时执行

## 配置文件

- `config/hermes_profile.yaml` - Hermes Agent 配置
- `config/environments.yaml` - 环境配置
- `config/naming_rules.yaml` - 命名规则
- `config/extensions.yaml` - 扩展配置
- `config/settings.yaml` - 工具设置
- `.claude/context_config.yaml` - LLM 上下文配置
- `metadata/optionsets/global_optionsets.yaml` - 全局选项集定义

## 元数据工作流

### 完整开发流程

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
1. 在 global_optionsets.yaml 中定义全局选项集
   ↓
2. 表定义中使用 option_set_ref 引用
   ↓
3. 数据字典自动生成选项集文档
   ↓
4. LLM 读取文档获取正确的选项值
```

### Git Hook 触发流程

```
1. 开发者修改 metadata/tables/*.yaml
   ↓
2. git add 添加文件到暂存区
   ↓
3. git commit 触发 pre-commit hook
   ↓
4. generate_data_dictionary.py 执行
   ↓
5. 更新 docs/data_dictionary/
   ↓
6. 将生成的文档添加到本次提交
   ↓
7. 提交完成
```

- `config/hermes_profile.yaml` - Hermes Agent 配置
- `config/environments.yaml` - 环境配置
- `config/naming_rules.yaml` - 命名规则
- `config/extensions.yaml` - 扩展配置
- `config/settings.yaml` - 工具设置
- `.claude/context_config.yaml` - LLM 上下文配置
- `metadata/optionsets/global_optionsets.yaml` - 全局选项集定义

## 安全考虑

1. **敏感信息存储**: 使用环境变量存储凭据
2. **Token 管理**: MSAL 自动处理 token 刷新
3. **标准表保护**: 禁止修改标准表元数据
4. **操作审计**: 记录所有重要操作

## 性能优化

1. **批处理请求**: 使用 OData 批处理减少网络往返
2. **缓存**: 元数据和 token 缓存
3. **并发控制**: 限制并发请求数避免限流
4. **重试机制**: 指数退避重试策略
