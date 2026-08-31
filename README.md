# Power Platform Agent

> **Engine + Workspace 架构**：安装 pip 包，一行命令创建 Workspace，用 Python 代码定义 Dataverse 元数据，一条命令同步到云端。

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 架构概览

Power Platform Agent 采用 **Engine + Workspace 分离架构**：

```
┌─────────────────────────────────────────────────────┐
│  Engine（pip 包：power-platform-agent）              │
│  ├── framework_power/   CLI + 部署引擎               │
│  └── framework_power/templates/  脚手架模板          │
└──────────────────────┬──────────────────────────────┘
                       │ pip install power-platform-agent
                       │ pp workspace init
                       ▼
┌─────────────────────────────────────────────────────┐
│  Workspace（每个项目独立的工作区）                    │
│  ├── pp-workspace.yaml     ← 工作区清单（锚文件）     │
│  ├── metadata_py/tables/   ← Python 表定义           │
│  ├── config/               ← 环境配置                │
│  ├── plugins/              ← .NET 插件               │
│  └── webresources/         ← JS/CSS 资源             │
└─────────────────────────────────────────────────────┘
```

| 组件 | 职责 |
|------|------|
| **Engine** | CLI 工具、部署引擎、模板——作为 pip 包分发 |
| **Workspace** | 项目数据（表定义、配置、插件、资源）——`pp-workspace.yaml` 作为锚文件标识 |

**两条路径**：

| 路径 | 入口 | 适合场景 |
|------|------|----------|
| **`pp` CLI**（推荐） | `pp <command>` | 新项目、CI/CD 流水线、类型安全 |

---

## 快速开始（外部项目）

### 前置要求

- Python 3.9+
- Dataverse 环境（需 App Registration 的 `client_id` + `client_secret`）
- .NET 8.0+ SDK（仅插件开发需要）

### 第一步：安装 Engine

```bash
# 从 PyPI 安装（推荐）
pip install power-platform-agent

# 或从 Git 安装（私有仓库）
pip install git+https://github.com/your-org/power-platform-agent.git@main
```

### 第二步：创建 Workspace

```bash
mkdir my-cpq-solution && cd my-cpq-solution
git init

# 创建工作区结构（自动生成 pp-workspace.yaml + 目录 + 配置模板）
pp workspace init --name my-cpq-solution \
  --publisher contoso \
  --prefix con \
  --main-solution con_CPQ
```

`pp workspace init` 自动创建：

```
my-cpq-solution/
├── pp-workspace.yaml           ← 工作区清单
├── config/
│   ├── environments.yaml       ← Dataverse 环境 URL + 凭据
│   ├── publishers.yaml         ← 发布商 + 命名规则
│   ├── pipeline.yaml           ← CI/CD 分支→环境映射
│   └── environment_settings.yaml
├── metadata_py/
│   ├── tables/                 ← Python 表定义（每文件导出 TABLE）
│   ├── forms/
│   ├── views/
│   ├── roles/
│   └── project.py              ← 工作流编排清单
├── webresources/
├── plugins/
└── requirements.txt
```

### 第三步：配置环境

1. 编辑 `config/environments.yaml`，填入 Dataverse 环境 URL：
   ```yaml
   environments:
     dev:
       url: "https://your-dev.crm.dynamics.com"
     test:
       url: "https://your-test.crm.dynamics.com"
   ```

2. 设置环境变量（或创建 `.env` 文件）：
   ```bash
   export DEV_TENANT_ID="your-tenant-id"
   export DEV_CLIENT_ID="your-client-id"
   export DEV_CLIENT_SECRET="your-client-secret"
   ```

### 第四步：验证

```bash
# 验证工作区结构
pp workspace validate

# 查看工作区信息
pp workspace info

# 列出已注册的表定义（此时应为空）
pp list
```

> **不需要 clone 本仓库**——`pip install power-platform-agent` 即可获得全部 CLI 能力。

---

## 快速开始（本仓库开发）

如果你在**本仓库**（power-platform-agent 本身）中开发：

```bash
git clone <repo-url>
cd power-platform-agent

# 安装核心依赖 + 可编辑包
pip install -r requirements.txt
pip install -e .

# 本仓库自身也是一个 workspace（pp-workspace.yaml 在根目录）
pp workspace info
pp list
```

---

## Workspace 发现机制

CLI 在执行任何命令前，会自动发现当前 workspace：

```
1. --workspace <path>           ← CLI 显式指定（最高优先级）
2. PP_WORKSPACE 环境变量          ← CI/CD 管道
3. CWD/pp-workspace.yaml         ← 当前目录有锚文件
4. 从 CWD 向上搜索               ← 像 git 一样向上查找
5. 报错: "Not in a Power Platform workspace"
```

在 workspace 内的**任何子目录**执行命令都能正确解析路径——无需关心当前所在目录。

---

## `pp` CLI（Python 优先路径）

`pp` 是 workspace-aware 的命令行工具，用 Python 代码替代 YAML 作为元数据的单一事实来源，覆盖完整的 Dataverse 开发链。

> 在本仓库开发时，`pp` 和 `python -m framework_power` 完全等价。

### 9 大阶段

| # | 阶段 | 功能 | CLI 示例 |
|---|------|------|----------|
| 1 | **表管理** | 类型化 `Table`/`Column`/`Relationship`，幂等 deploy/plan/reverse；引用的全局选项集依赖优先自动同步（ADR-011） | `pp deploy new_projectbudget` |
| 1b | **全局选项集** | `GlobalOptionSet` 独立建模，create-only 同步 + 漂移检测 | `pp optionset deploy new_salesgroup` |
| 2 | **解决方案** | `Solution` 容器 + 6 种组件类型统一分发 | `pp solution deploy --env dev` |
| 3 | **安全角色** | 为已存在角色 upsert 表级权限，按表逆向 | `pp role deploy --env dev` |
| 4 | **Web 资源** | 本地目录批量同步 + 精准 `PublishXml` | `pp webresource sync --env dev` |
| 5 | **窗体** | 结构化 Form 模型，逆向→改布局→正向无损往返 | `pp form deploy <entity>` |
| 6 | **视图** | 结构化 View 模型，FetchXml+LayoutXml 配对 | `pp view deploy <entity>` |
| 7 | **Ribbon** | 自定义按钮、JS command、显隐规则、隐藏 OOB | `pp ribbon deploy --env dev` |
| 8 | **插件** | NuGet PluginPackage 优先，net462/net471；Step Pre/Post Image + Custom Action 全链路（ADR-012） | `pp plugin build` |
| 9 | **工作流编排** | `project.py` 清单驱动整条开发链 | `pp workflow deploy` |

### Workspace 管理

```bash
# 创建新工作区
pp workspace init --name <name> --publisher <pub> --prefix <pre> --main-solution <sol>

# 查看工作区信息（路径、目录、发布商等）
pp workspace info

# 验证工作区结构完整性
pp workspace validate
```

### 常用命令

```bash
# 代码检查
pp lint new_projectbudget

# 只读预演（不写入 Dataverse）
pp plan new_projectbudget --env dev

# 同步到 Dataverse（引用的全局选项集会先行自动同步）
pp deploy new_projectbudget --env dev

# 全局选项集独立管理（列表 / 同步）
pp optionset list
pp optionset deploy new_salesgroup --env dev --solution new_entity930

# ���向导出（环境 → 本地 Python 文件）
pp reverse new_projectbudget --env dev

# 全表部署
pp deploy-all --env dev

# 指定工作区（不用 cd 到 workspace 目录）
pp --workspace /path/to/my-project list
```

### CI/CD Pipeline

```bash
# 查看分支→环境映射
pp pipeline map

# 动态组合解决方案组件
pp pipeline compose --branch develop

# Source mode 部署到 DEV
pp pipeline run --branch develop

# Promote mode（DEV→UAT→PROD）
pp pipeline promote --branch release/1.0
```

> **设计原则**：非破坏性部署（只 create/update，不 delete）、幂等双向同步、标准组件自动跳过。

---

## 项目结构

### Engine（本仓库 = pip 包源码）

```
power-platform-agent/
├── framework_power/             # ← Engine 核心代码
│   ├── workspace.py             #   Workspace 发现/创建/验证
│   ├── cli.py                   #   CLI 入口（pp 命令）
│   ├── deployer.py              #   幂等部署引擎
│   ├── pipeline/                #   CI/CD pipeline 模块
│   ├── components/              #   6 种解决方案组件注册表
│   └── templates/               #   脚手架模板（pp workspace init 使用）
├── setup.py                     # pip 包定义（pp / pp-agent 入口点）
└── test/                        # 测试（337+ 单元测试）
```

### Workspace（各项目的标准结构）

每个 Power Platform 解决方案项目都是独立的 workspace：

```
my-cpq-solution/                 # ← Workspace（独立 Git 仓库）
├── pp-workspace.yaml            # 工作区清单（锚文件，类似 package.json）
├── metadata_py/                 # Python 元数据定义
│   ├── tables/                  #   每表一个 .py（导出 TABLE）
│   ├── forms/                   #   结构化窗体定义
│   ├── views/                   #   结构化视图定义
│   ├── solutions/               #   解决方案清单
│   ├── roles/                   #   安全角色权限定义
│   └��─ project.py               #   工作流编排清单
├── config/                      # 配置文件
│   ├── environments.yaml        #   多环境 URL 和凭据
│   ├── pipeline.yaml            #   CI/CD 分支→环境映射
│   ├── naming_rules.yaml        #   命名规则
│   └── publishers.yaml          #   发布商配置
├── plugins/                     # .NET 插件源码
├── webresources/                # Web 资源（JS/CSS/HTML）
├── requirements.txt             # pip install power-platform-agent
└── README.md
```

> **本仓库自身也是一个 workspace**（根目录有 `pp-workspace.yaml`），用于功能测试和参考。

> **需求到代码的完整链路**：`docs/features/<feature>/` → Excel 设计 → `dv-model-to-python`（AI 生成）→ `metadata_py/tables/` → `pp lint/plan/deploy` → Dataverse。`so-model` 是这一管线的完整参考案例。

---

## 配置说明

所有配置文件位于 `config/` 目录：

| 文件 | 用途 |
|------|------|
| `environments.yaml` | 多环境 URL 和认证方式，支持 `${ENV_VAR}` 变量展开 |
| `publishers.yaml` | 发布商名称、前缀 + 命名规则（schema name 风格、标准实体保护列表、验证规则） |
| `pipeline.yaml` | CI/CD 分支→环境映射与部署策略 |
| `environment_settings.yaml` | 部署后环境变量与连接引用 |

---

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 代码检查
flake8 framework_power/ --max-line-length=120
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
| [Workspace 架构规划](docs/references/pac-cli/workspace-architecture-plan.md) | Engine + Workspace 分离架构设计 |
| [Workspace 验证报告](docs/references/pac-cli/workspace-verification-report.md) | 15 维度系统审计结果 |
| [外部仓库集成指南](docs/references/pac-cli/external-repo-integration-guide.md) | 外部项目如何使用 `pp workspace init` |
| [元数据规范](docs/spec/metadata-spec.md) | 元数据定义规范（含 Python API 和 YAML 格式） |
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
