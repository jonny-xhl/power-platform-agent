# Power Platform Agent

> 基于 MCP (Model Context Protocol) 的 Microsoft Power Platform / Dataverse 开发工具链——用代码定义元数据，一行命令同步到云端。

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 简介

Power Platform Agent 提供**两条互补路径**来管理 Dataverse 元数据：

| 路径 | 入口 | 适合场景 |
|------|------|----------|
| **`framework_power` CLI**（推荐） | `python -m framework_power` | 新项目、CI/CD 流水线、类型安全要求 |
| **MCP Server**（Legacy） | `python -m framework.mcp_serve` | AI 辅助开发（Claude Code / Cursor）、已有 YAML 资产 |

两者完全隔离，可独立使用。

---

## 快速开始

### 前置要求

- Python 3.9+
- Dataverse 环境（需 App Registration 的 `client_id` + `client_secret`）
- .NET 8.0+ SDK（仅插件开发需要）

### 安装

```bash
git clone <repo-url>
cd power-platform-agent

# 安装核心依赖
pip install -r requirements.txt

# 安装为可编辑包（提供 pp-mcp 入口命令）
pip install -e .

# 可选：安装 CLI 增强
pip install -e ".[cli]"
```

### 配置

1. 编辑 `config/environments.yaml`，填入 Dataverse 环境 URL：
   ```yaml
   environments:
     dev:
       url: "https://your-org.crm.dynamics.com"
   ```

2. 设置环境变量：
   ```bash
   export DEV_TENANT_ID="your-tenant-id"
   export DEV_CLIENT_ID="your-client-id"
   export DEV_CLIENT_SECRET="your-client-secret"
   ```

### 验证安装

```bash
# 列出已注册的 Python 表定义
python -m framework_power list

# 启动 MCP 服务器
python -m framework.mcp_serve
```

---

## framework_power CLI（Python 优先路径）

`framework_power` 是一套类型化的 Python 库，用 Python 代码替代 YAML 作为元数据的单一事实来源，覆盖完整的 Dataverse 开发链。

### 9 大阶段

| # | 阶段 | 功能 | CLI 示例 |
|---|------|------|----------|
| 1 | **表管理** | 类型化 `Table`/`Column`/`Relationship`，幂等 deploy/plan/reverse | `framework_power deploy new_projectbudget` |
| 2 | **解决方案** | `Solution` 容器 + 6 种组件类型统一分发 | `framework_power solution deploy --env dev` |
| 3 | **安全角色** | 为已存在角色 upsert 表级权限，按表逆向 | `framework_power role deploy --env dev` |
| 4 | **Web 资源** | 本地目录批量同步 + 精准 `PublishXml` | `framework_power webresource sync --env dev` |
| 5 | **窗体** | 结构化 Form 模型，逆向→改布局→正向无损往返 | `framework_power form deploy <entity>` |
| 6 | **视图** | 结构化 View 模型，FetchXml+LayoutXml 配对 | `framework_power view deploy <entity>` |
| 7 | **Ribbon** | 自定义按钮、JS command、显隐规则、隐藏 OOB | `framework_power ribbon deploy --env dev` |
| 8 | **插件** | NuGet PluginPackage 优先，net462/net471 | `framework_power plugin build` |
| 9 | **工作流编排** | `project.py` 清单驱动整条开发链 | `framework_power workflow deploy` |

### 常用命令

```bash
# 代码检查
python -m framework_power lint new_projectbudget

# 只读预演（不写入 Dataverse）
python -m framework_power plan new_projectbudget --env dev

# 同步到 Dataverse
python -m framework_power deploy new_projectbudget --env dev

# 逆向导出（环境 → 本地 Python 文件）
python -m framework_power reverse new_projectbudget --env dev

# 全表部署
python -m framework_power deploy-all --env dev
```

> **设计原则**：非破坏性部署（只 create/update，不 delete）、幂等双向同步、标准组件自动跳过。

---

## MCP Server（AI 交互路径）

MCP Server 将 Dataverse 操作暴露为 Claude Code 可调用的工具，支持通过自然语言管理元数据。

### 在 Claude Code 中配置

在 `.mcp.json` 中添加：

```json
{
  "mcpServers": {
    "power-platform": {
      "command": "python",
      "args": ["{repo_path}/framework/mcp_serve.py"],
      "env": {
        "TENANT_ID": "${TENANT_ID}",
        "CLIENT_ID": "${CLIENT_ID}",
        "CLIENT_SECRET": "${CLIENT_SECRET}"
      }
    }
  }
}
```

或者安装为包后：

```json
{
  "mcpServers": {
    "power-platform": {
      "command": "pp-mcp"
    }
  }
}
```

### 可用工具

| 前缀 | 功能 | 说明 |
|------|------|------|
| `auth_*` | 认证管理 | 登录、状态、环境切换 |
| `metadata_*` | 元数据 CRUD | YAML ↔ Dataverse 的表/字段/关系/表单/视图管理 |
| `naming_*` | 命名转换 | Schema Name 规范化、批量转换、合规校验 |
| `plugin_*` | 插件管理 | .NET 插件构建、部署、Step 注册 |
| `solution_*` | 解决方案 | 导入/导出/差异对比/双向同步 |
| `doc_*` | 文档自律 | 变更检测、影响分析、文档自动更新 |

---

## 项目结构

```
power-platform-agent/
├── sources/                     # 【需求汇总与入口】所有功能的需求、设计、输出
│   ├── features/                # 按功能模块组织
│   │   ├── cpq/                 # CPQ 售前模块（询价→报价→转单）
│   │   ├── so-model/            # 备件销售订单（最完整案例：97字段 Excel→对比→63新增字段 YAML）
│   │   ├── po-model/            # 采购订单模型
│   │   └── feature-payment-management/
│   ├── library/templates/       # 标准化模板（FEATURE_STRUCTURE/PRD_TEMPLATE/ENTITY_DESIGN）
│   └── templates/               # 源文件模板（Excel/Word/PPT 设计模板）
├── framework_power/             # Python 优先部署库（推荐）
│   ├── models.py                # Table/Column/Relationship/Label 类型化模型
│   ├── deployer.py              # 幂等部署引擎
│   ├── reverse.py               # 环境 → Python 逆向
│   ├── codegen.py               # Table → Python 源码生成
│   ├── lint.py                  # 离线约定校验
│   ├── cli.py                   # CLI 入口
│   └── components/              # 解决方案组件注册表（6 种类型统一接口）
├── metadata_py/                 # Python 元数据定义
│   ├── tables/                  # 每表一个 .py 文件（导出 TABLE）
│   ├── forms/                   # 结构化窗体定义
│   ├── views/                   # 结构化视图定义
│   ├── solutions/               # 解决方案清单
│   ├── roles/                   # 安全角色权限定义
│   └── project.py               # 工作流编排清单
├── framework/                   # MCP Server（Legacy 路径）
│   ├── mcp_serve.py             # MCP 服务器入口
│   ├── agents/                  # Agent 路由（core/metadata/plugin/solution）
│   └── utils/                   # DataverseClient、命名转换、YAML 解析器
├── metadata/                    # YAML 元数据定义（Legacy 路径）
│   ├── tables/                  # 表定义
│   ├── forms/                   # 表单定义
│   ├── views/                   # 视图定义
│   └── optionsets/              # 全局选项集
├── config/                      # 配置文件
│   ├── environments.yaml        # 多环境（dev/test/prod）URL 和凭据
│   ├── naming_rules.yaml        # 命名规则（风格、前缀、标准实体保护列表）
│   ├── publishers.yaml          # 发布商配置
│   └── settings.yaml            # Agent 性能与日志设置
├── plugins/                     # .NET 插件源码
├── webresources/                # Web 资源文件（JS/CSS/HTML）
├── docs/                        # 文档
│   ├── spec/                    # 架构、元数据规范
│   └── guides/                  # 使用指南
├── test/                        # 测试（168+ 单元测试）
├── scripts/                     # 工具脚本（Git hooks、数据字典生成）
├── .claude/skills/              # Claude Code 技能（14 个）
├── setup.py                     # 包安装配置
└── requirements.txt
```

> **需求到代码的完整链路**：`sources/features/<feature>/` → Excel 设计 → `dv-model-to-python`（AI 生成）→ `metadata_py/tables/` → `framework_power lint/plan/deploy` → Dataverse。`so-model` 是这一管线的完整参考案例。

---

## 配置说明

所有配置文件位于 `config/` 目录：

| 文件 | 用途 |
|------|------|
| `environments.yaml` | 多环境 URL 和认证方式，支持 `${ENV_VAR}` 变量展开 |
| `naming_rules.yaml` | Schema Name 风格（lowercase/PascalCase）、前缀、标准实体保护列表 |
| `publishers.yaml` | 发布商名称和前缀（默认 `new`） |
| `settings.yaml` | 请求超时、日志级别、并发控制 |

---

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 代码检查
flake8 framework/ framework_power/ --max-line-length=120
mypy framework_power --ignore-missing-imports --explicit-package-bases

# 运行测试
cd test && pytest unit/ -q

# 带覆盖率
cd test && pytest unit/ --cov=framework_power --cov-report=html

# 安装 Git Hooks（提交时自动更新数据字典）
bash scripts/install_hooks.sh
```

---

## 文档

| 文档 | 说明 |
|------|------|
| [架构文档](docs/spec/architecture.md) | 系统架构、Agent 路由、组件依赖 |
| [元数据规范](docs/spec/metadata-spec.md) | 元数据定义规范（含 Python API 和 YAML 格式） |
| [元数据部署指南](docs/metadata-deploy.md) | 两种部署路径完整对比与操作指南 |
| [快速开始](docs/guides/getting-started.md) | 详细入门教程 |
| [编码规范](docs/guides/coding-standards.md) | 代码风格和约定 |

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 主语言 | Python 3.9+（完整类型注解、mypy 严格模式） |
| MCP 协议 | `mcp>=0.1.0`（stdio 传输） |
| 认证 | MSAL（OAuth 2.0 client-credentials） |
| 配置格式 | YAML + JSON Schema 验证 |
| 插件语言 | C# / .NET（net462/net471） |
| CLI | `click` + `rich` |
| 代码质量 | black、flake8、mypy |
| 测试 | pytest + pytest-asyncio + pytest-cov |

---

## License

MIT License —— 详见 [LICENSE](LICENSE)
