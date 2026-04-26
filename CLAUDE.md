# Power Platform Agent - Claude 项目文档

> 本文档由 Hermes Agent 自动维护，最后更新：2025-04-25

## 项目概述

Power Platform Agent 是一个为 Claude Code/Cursor 提供 Power Platform 访问能力的 MCP (Model Context Protocol) 服务器。

### 核心功能

- **元数据管理**：管理 Dataverse 表、字段、表单、视图等元数据
- **命名转换**：自动将中文命名转换为符合 Power Platform 规范的 Schema Name
- **插件管理**：构建、部署 .NET 插件到 Dataverse
- **解决方案管理**：导出、导入、同步 Power Platform 解决方案
- **文档自律**：自动检测代码变更并更新相关文档

### 技术栈

- **语言**：Python 3.9+
- **MCP 框架**：mcp 0.9.1
- **认证**：MSAL (Microsoft Authentication Library)
- **YAML 处理**：PyYAML
- **LLM 集成**：支持 Anthropic、智谱、通义千问等多种 LLM

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/jonny-xhl/power-platform-agent.git
cd power-platform-agent

# 安装依赖
pip install -r requirements.txt

# 安装 Git hooks（可选）
bash scripts/install_hooks.sh
```

### 配置

1. 复制配置模板：
```bash
cp config/environments.yaml.example config/environments.yaml
```

2. 配置环境信息：
```yaml
environments:
  dev:
    name: "开发环境"
    url: "https://your-org.crm.dynamics.com"
    client_id: "your-client-id"
    client_secret: "your-client-secret"
```

### 运行 MCP 服务器

```bash
# 启动服务器
python -m framework.mcp_serve

# 或使用 stdio 模式
python -m framework.mcp_serve --stdio
```

### 配置 Claude Code

在 Claude Code 的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "power-platform": {
      "command": "python",
      "args": ["-m", "framework.mcp_serve"],
      "cwd": "/path/to/power-platform-agent"
    }
  }
}
```

## MCP 工具列表

### 认证与环境管理

| 工具名称 | 描述 |
|---------|------|
| `auth_login` | 连接到 Dataverse 环境 |
| `auth_status` | 查看当前连接状态 |
| `auth_logout` | 断开环境连接 |
| `environment_switch` | 切换当前环境 |
| `environment_list` | 列出所有配置的环境 |

### 元数据管理

| 工具名称 | 描述 |
|---------|------|
| `metadata_parse` | 解析 YAML 元数据文件 |
| `metadata_validate` | 验证元数据定义 |
| `metadata_create_table` | 创建数据表 |
| `metadata_create_attribute` | 创建字段 |
| `metadata_create_form` | 创建表单 |
| `metadata_create_view` | 创建视图 |
| `metadata_export` | 导出云端元数据为 YAML |
| `metadata_diff` | 对比本地与云端元数据差异 |
| `metadata_apply` | 应用元数据到 Dataverse |
| `metadata_list` | 列出元数据 |

### 命名规则

| 工具名称 | 描述 |
|---------|------|
| `naming_convert` | 命名转换（根据配置规则） |
| `naming_validate` | 验证命名是否符合规则 |
| `naming_bulk_convert` | 批量转换命名 |
| `naming_rules_list` | 列出当前命名规则 |

### 插件管理

| 工具名称 | 描述 |
|---------|------|
| `plugin_build` | 构建插件项目 |
| `plugin_deploy` | 部署插件 |
| `plugin_step_register` | 注册插件 Step |
| `plugin_step_list` | 列出插件 Steps |
| `plugin_step_delete` | 删除插件 Step |
| `plugin_assembly_list` | 列出已部署的程序集 |
| `plugin_info` | 获取插件项目信息 |

### 解决方案管理

| 工具名称 | 描述 |
|---------|------|
| `solution_export` | 导出解决方案 |
| `solution_import` | 导入解决方案 |
| `solution_diff` | 对比本地与解决方案差异 |
| `solution_sync` | 执行同步 |
| `solution_status` | 查看同步状态 |
| `solution_list` | 列出所有解决方案 |
| `solution_add_component` | 添加组件到解决方案 |

### 文档自动更新

| 工具名称 | 描述 |
|---------|------|
| `doc_analyze_changes` | 分析代码变更，判断是否需要更新文档 |
| `doc_update_skill` | 更新 SKILL 文档 |
| `doc_update_claude_md` | 更新 CLAUDE.md 项目文档 |
| `doc_generate_summary` | 生成代码变更总结 |
| `doc_list_skills` | 列出所有可用的 SKILL |
| `doc_get_mcp_tools` | 获取所有 MCP 工具列表 |
| `doc_full_update` | 执行完整的文档更新流程 |

### 其他

| 工具名称 | 描述 |
|---------|------|
| `extension_list` | 列出已注册的扩展 |
| `health_check` | 健康检查 |

## SKILL 列表

### design-dv-model

生成 Microsoft Dataverse 实体模型设计 Excel 模板。用于设计 Dataverse 表/实体、定义列/字段、创建表单布局、指定视图或文档化数据模型需求。

**主要功能**：
- 生成包含 7 个工作表的完整实体设计模板
- 支持多 Tab 表单布局设计
- 包含 Dataverse 数据类型参考
- 自动应用命名规则

**相关文件**：
- 技能文档：`.claude/skills/design-dv-model/SKILL.md`
- 生成脚本：`.claude/skills/design-dv-model/scripts/generate_template.py`
- 标准模板：`sources/templates/excel/ba_system_design_template.xlsx`

### dv-model-to-yaml

将 Excel 实体设计转换为 YAML 元数据文件。用于将设计文档转换为代码，实现从设计到实现的自动化。

**主要功能**：
- 解析 Excel 中的实体定义
- 生成符合 Schema 的 YAML 文件
- 自动转换数据类型和属性
- 生成关系定义

**相关文件**：
- 技能文档：`.claude/skills/dv-model-to-yaml/SKILL.md`
- 转换脚本：`.claude/skills/dv-model-to-yaml/scripts/convert_excel_to_yaml.py`

## 架构说明

### 目录结构

```
power-platform-agent/
├── framework/              # 框架核心
│   ├── agents/            # 代理模块
│   │   ├── core_agent.py
│   │   ├── metadata_agent.py
│   │   ├── plugin_agent.py
│   │   ├── solution_agent.py
│   │   └── documentation_agent.py
│   ├── utils/             # 工具模块
│   │   ├── change_detector.py
│   │   ├── impact_analyzer.py
│   │   ├── dataverse_client.py
│   │   ├── naming_converter.py
│   │   ├── yaml_parser.py
│   │   └── schema_validator.py
│   ├── llm/               # LLM 集成
│   │   └── langchain_client.py
│   ├── prompts/           # 提示词模板
│   └── mcp_serve.py       # MCP 服务器入口
├── config/                # 配置文件
│   ├── environments.yaml
│   ├── hermes_profile.yaml
│   ├── naming_rules.yaml
│   └── documentation_rules.yaml
├── metadata/              # 元数据定义
│   ├── _schema/           # Schema 定义
│   ├── tables/            # 表定义
│   └── optionsets/        # 选项集定义
├── scripts/               # 脚本工具
│   ├── hooks/             # Git hooks
│   ├── generate_data_dictionary.py
│   └── update_docs.py
├── .claude/               # Claude 配置
│   └── skills/            # 技能定义
├── docs/                  # 文档
│   ├── spec/              # 规范文档
│   ├── guides/            # 指南
│   └── data_dictionary/   # 数据字典
└── sources/               # 源文件
    └── features/          # 功能迭代
```

### 核心组件

#### CoreAgent

核心代理，负责：
- 环境管理
- 认证处理（MSAL）
- 命名转换
- 健康检查

#### MetadataAgent

元数据代理，负责：
- YAML 元数据解析和验证
- Dataverse 实体/字段创建
- 元数据导出和对比
- Schema 管理

#### PluginAgent

插件代理，负责：
- .NET 项目构建
- 程序集部署
- 插件 Step 注册

#### SolutionAgent

解决方案代理，负责：
- 解决方案导入导出
- 组件同步
- 解决方案对比

#### DocumentationAgent

文档代理，负责：
- 代码变更检测
- 影响分析
- 文档自动生成
- 变更总结

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|-------|------|-------|
| `LLM_PROVIDER` | LLM 提供商 | `anthropic` |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | - |
| `ZHIPUAI_API_KEY` | 智谱 API 密钥 | - |
| `DASHSCOPE_API_KEY` | 通义千问 API 密钥 | - |

### 配置文件

#### config/environments.yaml

环境配置文件，定义 Dataverse 环境连接信息。

```yaml
environments:
  dev:
    name: "开发环境"
    url: "https://org.crm.dynamics.com"
    client_id: "${DEV_CLIENT_ID}"
    client_secret: "${DEV_CLIENT_SECRET}"
```

#### config/naming_rules.yaml

命名规则配置，定义命名转换规则。

```yaml
naming:
  prefix: "new"
  schema_name_style: "PascalCase"
  separator: "_"
```

#### config/documentation_rules.yaml

文档更新规则，配置文档自动更新行为。

```yaml
monitored_directories:
  framework:
    - path: "agents/"
      doc_targets: ["CLAUDE.md"]
      impact_type: "agent_api"
```

## 开发指南

### 添加新的 MCP 工具

1. 在相应的 Agent 类中添加处理方法：

```python
async def handle(self, tool_name: str, arguments: Dict[str, Any]) -> str:
    if tool_name == "your_new_tool":
        return await self.your_new_tool_handler(arguments)
```

2. 在 `framework/mcp_serve.py` 的 `list_tools()` 中添加工具定义：

```python
Tool(
    name="your_new_tool",
    description="工具描述",
    inputSchema={...}
)
```

3. 在 `call_tool()` 中添加路由（如果需要）。

### 创建新的 SKILL

1. 在 `.claude/skills/` 下创建技能目录：

```bash
mkdir -p .claude/skills/your-skill-name
```

2. 创建 SKILL.md 文件：

```markdown
---
name: your-skill-name
description: 技能描述
---

# 技能标题

技能详细说明...
```

3. （可选）添加脚本文件：

```bash
mkdir .claude/skills/your-skill-name/scripts
```

### 文档自动更新

项目支持文档自动更新功能：

```bash
# 交互模式
python scripts/update_docs.py

# 分析模式
python scripts/update_docs.py --mode analyze

# 自动更新
python scripts/update_docs.py --mode auto

# 更新指定 SKILL
python scripts/update_docs.py --skill design-dv-model
```

## 变更日志

### 2025-04-25

#### 新增
- 文档自律系统
  - 变更检测器 (ChangeDetector)
  - 影响分析器 (ImpactAnalyzer)
  - 文档代理 (DocumentationAgent)
  - LLM 客户端统一接口 (LangChainLLMClient)
- 新增 MCP 工具：`doc_analyze_changes`, `doc_update_skill`, `doc_update_claude_md`, `doc_generate_summary`, `doc_full_update`
- 新增配置文件：`config/documentation_rules.yaml`
- 新增脚本：`scripts/update_docs.py`
- 更新 pre-commit hook 集成文档更新

#### 改进
- 完善项目文档结构
- 添加 SKILL 自动更新能力

#### 技术债务
- 需要添加单元测试覆盖核心功能
- 需要完善错误处理和日志记录

---

*本文档由 Hermes Agent 文档自律系统自动维护*
