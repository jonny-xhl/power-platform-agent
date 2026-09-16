# dv-workspace-setup

> 创建和管理 Power Platform workspace —— Engine + Workspace 分离架构的入口技能。

## 何时使用

- 用户要创建一个新的 Power Platform 解决方案项目
- 用户要设置 workspace（`pp workspace init`）
- 用户问"如何开始一个新项目"或"如何在外部仓库使用 power-platform-agent"
- 用户要查看或验证 workspace 状态

## 前置条件

```bash
# 安装 Engine（pip 包，无需 clone 源码）
pip install power-platform-agent

# 验证安装
pp --help
```

## 核心工作流

### 1. 创建新 Workspace

```bash
mkdir my-project && cd my-project
git init

pp workspace init \
  --name my-project \
  --publisher contoso \
  --prefix con \
  --main-solution con_MainSolution
```

`pp workspace init` 在当前目录（上例的 `my-project/`，`--name` 只是清单里的名字，**不会**建同名子目录）
自动创建：
- `pp-workspace.yaml` — workspace 清单（锚文件）
- `config/` — 环境配置、pipeline 映射、命名规则、发布商
- `metadata_py/` — Python 元数据定义目录结构，其中含 `tables/ forms/ views/ ribbons/ roles/ optionsets/ solutions/`
- `webresources/` — Web 资源目录
- `plugins/` — 插件目录
- `webresources/webresources.aliases.json` — **标准文件**，播种为 `{}`（web 资源遗留名覆盖表，
  见 `dv-webresource-sync` 技能；空表 = 全部走 `{prefix}_/{relpath}` 约定，行为中性）
- `requirements.txt`

> **目录与标准文件都是 workspace 契约的一部分**（`workspace.DEFAULT_DIRS` / `STANDARD_FILES`），
> 由 `ensure_files()` 在 init 时播种，且**幂等、绝不覆盖已有文件**。引擎新增任何依赖工作区
> 目录/文件的机制时，都必须同时落进这两个表并补 parity 测试——见根 `CLAUDE.md` 的
> 「新工作区同等支持守则」。只在本机某个工作区里手工补的文件，对新项目等于不存在。

### 2. 配置环境

编辑 `<project>/config/environments.yaml`：

```yaml
environments:
  dev:
    url: "https://your-dev.crm.dynamics.com"
  test:
    url: "https://your-test.crm.dynamics.com"
  production:
    url: "https://your-prod.crm.dynamics.com"
```

设置环境变量：

```bash
export DEV_TENANT_ID="..."
export DEV_CLIENT_ID="..."
export DEV_CLIENT_SECRET="..."
```

### 3. 验证

```bash
# 验证 workspace 结构完整性
pp workspace validate

# 查看 workspace 信息
pp workspace info
```

## Workspace 发现机制

CLI 自动发现 workspace，无需 cd 到根目录：

```
1. --workspace <path>           显式指定
2. PP_WORKSPACE 环境变量          CI/CD 管道
3. CWD/pp-workspace.yaml         当前目录
4. 从 CWD 向上搜索               子目录运行
```

## pp-workspace.yaml 结构

> 这是 workspace 的唯一身份证明。文件放在项目根目录，引擎通过 CWD 向上搜索发现它
> （类似 `.git/` 目录的工作机制）。

```yaml
# pp-workspace.yaml
name: my-project
description: "Project description"

# Publisher identity — 所有自定义组件的前缀来源
publisher: contoso
publisher_prefix: con
publisher_display_name: "Contoso"

# Solution identity — 组件归属的解决方案容器
main_solution: con_MainSolution
ribbon_solution: con_RibbonSoln     # 可选，专用 ribbon 解决方案
version: "1.0.0.0"

# 目录覆盖（可选，省略时使用引擎默认值）
# dirs:
#   tables: metadata_py/tables
#   forms: metadata_py/forms
#   ...
```

### 关键字段说明

| 字段 | 作用 | 被谁读取 |
|------|------|---------|
| `publisher_prefix` | 自定义组件命名前缀（如 `con_`） | 所有 `pp` 命令 |
| `main_solution` | 组件默认归属的解决方案名 | `pp deploy`、`pp solution deploy` |
| `ribbon_solution` | Ribbon 定制的专用解决方案 | `pp ribbon deploy` |
| `dirs` | 自定义目录路径覆盖（可选） | 路径解析器 |

## 下一步

Workspace 创建完成后，使用其他技能开始开发：

| 技能 | 用途 |
|------|------|
| `dv-model-to-python` | 从 Excel 设计生成表定义 |
| `dv-solution-python` | 管理解决方案 |
| `dv-form-python` | 窗体操作 |
| `dv-view-python` | 视图操作 |
| `dv-workflow-python` | 全流程编排 |

## 注意事项

- 本仓库（power-platform-agent）自身也是一个 workspace
- 外部仓库通过 `pip install power-platform-agent` 获取 Engine，无需 clone
- 所有 `pp` 命令都是 workspace-aware，在子目录运行也能正确解析路径
