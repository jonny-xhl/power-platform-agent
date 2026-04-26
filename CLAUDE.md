# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库中工作时提供指导。

## 项目描述

Power Platform Agent 是一个基于 MCP (Model Context Protocol) 协议的服务器，为 Claude Code / Cursor 提供 Microsoft Power Platform / Dataverse 的操作能力。核心功能包括：

- **元数据管理**：通过 YAML 声明式定义 Dataverse 表、字段、关系、表单、视图，支持与云端 diff/apply 增量同步
- **命名转换**：自动将中文/驼峰命名转换为符合 Dataverse 规范的 Schema Name（规则见 `config/naming_rules.yaml`）
- **插件管理**：构建 .NET 插件并部署到 Dataverse，注册/管理 Plugin Step
- **解决方案管理**：Power Platform 解决方案的导入、导出、双向同步
- **文档自律**：通过 Git hooks 自动检测代码变更并更新相关文档

## 编程语言要求

- **主要语言**：Python 3.9+（MCP 服务器、Agent、工具链）
- **插件语言**：C# / .NET（Dataverse 插件开发，位于 `plugins/` 目录）
- **配置语言**：YAML（元数据定义、环境配置、命名规则）
- **类型注解**：Python 代码必须包含类型注解（`typing`），项目配置了 `mypy` 类型检查

## 规范要求

### Python 代码规范

- 使用 `black` 格式化，`flake8` 检查（最大行宽 120）
- 所有 async 函数使用 `async/await`，不使用 `@asyncio.coroutine`
- Agent 类必须继承或遵循现有 Agent 的 handler 模式（`handle(tool_name, arguments)`）
- 错误处理返回 JSON 格式 `{"error": "..."}`，不抛出未捕获异常
- 布尔值使用 Python 的 `True`/`False`，禁止使用 `true`/`false`（会导致运行时 NameError）

### 元数据 YAML 规范

- 自定义实体 SchemaName 必须以发布商前缀 `new_` 开头
- 自定义关系的 SchemaName 也必须以 `new_` 开头
- Lookup 字段不能通过 Attributes 端点单独创建，必须通过 Deep Insert（`RelationshipDefinitions`）一次性创建关系 + Lookup
- 级联行为：每个实体只允许一个 Parental（`Active`）关系，自定义关系推荐使用 Referential 模式（`NoCascade` + `RemoveLink`）
- YAML 是期望状态的声明，与 Dataverse 对比后执行 create/update/skip，不执行 delete
- 标准实体（account、contact、systemuser 等）受保护，命名转换时不会被修改（列表见 `config/naming_rules.yaml` 的 `standard_entities`）

### MCP 工具开发规范

- 新工具需在 `framework/mcp_serve.py` 的 `list_tools()` 注册 `Tool` 定义
- 工具按名称前缀路由到对应 Agent（`metadata_*` → MetadataAgent，`plugin_*` → PluginAgent 等）
- `inputSchema` 中的 JSON Schema 值必须是 Python 字面量（`True`/`False`/`None`）
- MCP 服务器通过 `mcp.server.stdio.stdio_server()` 启动，不要使用 `transport` 关键字参数

### 插件开发规范

- 插件位于 `plugins/` 目录，使用 .NET SDK（`Microsoft.Xrm.Sdk`）
- 实现标准 `IPlugin` 接口，入口方法 `Execute(IServiceProvider)`
- 通过 `PluginAgent` 调用 `dotnet build` 构建，`DataverseClient` 部署
- Plugin Step 注册需指定：实体名、消息名（Create/Update/Delete）、阶段（pre-validation/pre-operation/post-operation）

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 以可编辑模式安装（提供 pp-mcp 和 power-platform-mcp CLI 命令）
pip install -e .

# 启动 MCP 服务器（stdio 模式，Claude Code 使用）
python -m framework.mcp_serve

# 构建验证
python build_and_validate.py

# 验证所有模块导入
python test_imports.py
```

### 测试

```bash
# 运行全部测试
bash test/scripts/run_all_tests.sh

# 仅运行单元测试
bash test/scripts/run_unit_tests.sh

# 带覆盖率报告（HTML 报告在 test/reports/html/）
bash test/scripts/run_with_coverage.sh

# 运行单个测试文件
cd test && pytest unit/test_agents/test_core_agent.py

# 按标记运行测试
cd test && pytest -m unit
cd test && pytest -m "requires_auth"  # 需要 Dataverse 凭据
```

测试配置在 `test/pytest.ini`。标记：`unit`、`integration`、`slow`、`requires_auth`、`requires_dataverse`。

### 代码检查

```bash
flake8 framework/ --max-line-length=120
mypy framework/ --ignore-missing-imports
```

### Git Hooks

```bash
bash scripts/install_hooks.sh
```

Pre-commit hook 自动执行：`metadata/` 变更时更新数据字典，framework 代码变更时建议文档更新。

### 数据字典生成

```bash
python scripts/generate_data_dictionary.py --all
python scripts/generate_data_dictionary.py --files metadata/tables/account.yaml
```

## 架构

本项目是一个 MCP (Model Context Protocol) 服务器，将 Dataverse/Power Platform 操作暴露为 Claude Code 可调用的工具。

### Agent 路由模式

所有 MCP 工具通过 Agent 类路由。入口 `framework/mcp_serve.py` 通过装饰器（`@app.list_tools()`、`@app.call_tool()`）注册工具，按工具名前缀分发调用：

| 前缀 | Agent | 文件 |
|------|-------|------|
| `auth_*`、`environment_*`、`naming_*`、`extension_*` | CoreAgent → CoreToolHandler | `framework/agents/core_agent.py` |
| `metadata_*` | MetadataAgent | `framework/agents/metadata_agent.py` |
| `plugin_*` | PluginAgent | `framework/agents/plugin_agent.py` |
| `solution_*` | SolutionAgent | `framework/agents/solution_agent.py` |
| `doc_*` | DocumentationAgent | `framework/agents/documentation_agent.py` |
| `health_check` | CoreAgent 直接调用 | `framework/agents/core_agent.py` |

Agent 通过 `get_agents()` 懒加载初始化。所有 Agent 持有 `CoreAgent` 引用，CoreAgent 拥有 `DataverseClient` 和 `NamingConverter`。

### 组件依赖关系

```
CoreAgent
  ├── DataverseClient (framework/utils/dataverse_client.py) — MSAL 认证 + Dataverse REST API
  └── NamingConverter (framework/utils/naming_converter.py) — Schema Name 转换

MetadataAgent(CoreAgent)
  ├── YAMLMetadataParser (framework/utils/yaml_parser.py)
  ├── SchemaValidator (framework/utils/schema_validator.py)
  └── MetadataManager (framework/agents/metadata_manager.py) — diff/apply 逻辑

PluginAgent(CoreAgent) — 通过 subprocess 调用 dotnet CLI
SolutionAgent(CoreAgent) — 解决方案导入导出与同步
DocumentationAgent
  ├── ChangeDetector (framework/utils/change_detector.py) — git diff 分析
  ├── ImpactAnalyzer (framework/utils/impact_analyzer.py)
  └── LangChainLLMClient (framework/llm/langchain_client.py) — 多提供商 LLM
```

### MCP 服务器启动

服务器使用 `mcp 0.9.1` 底层 `Server` API。启动方式（`framework/mcp_serve.py`）：

```python
from mcp.server.stdio import stdio_server
async with stdio_server() as (read_stream, write_stream):
    await app.run(read_stream, write_stream, app.create_initialization_options())
```

**重要**：`Server.run()` 不接受 `transport`/`port` 关键字参数 — 必须显式传入流对象。不要使用 `app.run(transport="stdio")` 或 `app.run(transport="sse")`。

### 添加新 MCP 工具

1. 在对应 Agent 类中添加处理方法
2. 在 `mcp_serve.py` 的 `list_tools()` 中添加 `Tool(name=..., description=..., inputSchema=...)` 定义
3. 如果工具名前缀不匹配现有路由模式，需在 `call_tool()` 中添加路由

定义工具 schema 时，布尔值必须用 Python 的 `True`/`False`，不能用 JavaScript 的 `true`/`false` — 后者会导致运行时 `NameError`，静默破坏整个工具列表。

### 配置文件

所有配置在 `config/` 目录：

| 文件 | 用途 |
|------|------|
| `environments.yaml` | Dataverse 环境 URL 和凭据（支持 `${ENV_VAR}` 变量展开） |
| `naming_rules.yaml` | Schema Name 前缀、风格、分隔符、受保护实体 |
| `documentation_rules.yaml` | 文档自动更新监控目录 |
| `settings.yaml` | Agent 性能与日志设置 |
| `hermes_profile.yaml` | Agent 配置文件和 MCP 工具元数据 |

### Dataverse API 关键模式

- **Lookup 字段**不能通过 `Attributes` 端点单独创建 — 必须通过 `RelationshipDefinitions` 端点使用 Deep Insert
- 自定义关系的 SchemaName 必须以发布商前缀（`new_`）开头
- 级联配置：`Active` = Parental（每个实体只允许一个），自定义关系推荐 `NoCascade`+`RemoveLink`
- 增量更新策略：YAML = 期望状态 → 与 Dataverse 对比 → create/update/skip（不删除）

### 元数据 YAML 结构

YAML 定义存放在 `metadata/`：
- `metadata/tables/*.yaml` — 实体定义，包含属性和关系
- `metadata/optionsets/*.yaml` — 全局选项集
- `metadata/_schema/*.yaml` — JSON Schema 验证定义

### 技能（Skills）

Claude Code 技能位于 `.claude/skills/`：
- `design-dv-model` — 生成 Dataverse 实体设计 Excel 模板
- `dv-model-to-yaml` — 将 Excel 设计转换为 YAML 元数据
- `dv-auth` — Dataverse 认证指南
- `dv-overview` — Dataverse 元数据建模总览

### CI

GitHub Actions 工作流在 `.github/workflows/test.yml`：在 Python 3.10/3.11/3.12 上运行 flake8 + pytest，覆盖率阈值 50%。
