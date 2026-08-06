# Power Platform 快速开始指南

## 架构概览

Power Platform Agent 采用 **Engine + Workspace 分离架构**：

- **Engine**（pip 包 `power-platform-agent`）：提供 CLI 工具 `pp`、部署引擎、MCP Server
- **Workspace**（每个项目独立）：包含表定义、配置、插件、Web 资源

外部项目只需 `pip install power-platform-agent` + `pp workspace init`，无需 clone 任何仓库。

---

## 安装

### 前置要求

- Python 3.9+
- .NET SDK 8.0+（仅插件开发需要）
- Dataverse 环境（需 App Registration 的 `client_id` + `client_secret`）

### 方式一：外部项目安装（推荐）

```bash
# 从 PyPI 安装 Engine
pip install power-platform-agent

# 验证安装
pp --help
```

### 方式二：本仓库开发安装

```bash
git clone <repo-url>
cd power-platform-agent
pip install -r requirements.txt
pip install -e .
```

---

## 创建 Workspace

### 第一步：初始化项目

```bash
mkdir my-cpq-solution && cd my-cpq-solution
git init

# 创建 workspace（自动生成目录结构 + 配置模板）
pp workspace init \
  --name my-cpq-solution \
  --publisher contoso \
  --prefix con \
  --main-solution con_CPQ
```

### 第二步：配置环境

编辑 `config/environments.yaml`：

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
export DEV_TENANT_ID="your-tenant-id"
export DEV_CLIENT_ID="your-client-id"
export DEV_CLIENT_SECRET="your-client-secret"
```

### 第三步：验证

```bash
# 验证 workspace 结构
pp workspace validate

# 查看工作区信息
pp workspace info
```

---

## 基本使用

### 表管理（Phase 1）

```bash
# 创建表定义文件
# metadata_py/tables/new_customer.py -> 导出 TABLE

# 代码检查
pp lint new_customer

# 只读预演
pp plan new_customer --env dev

# 部署到 Dataverse
pp deploy new_customer --env dev

# 逆向导出（环境 → 本地）
pp reverse new_customer --env dev
```

### 解决方案管理（Phase 2）

```bash
# 列出解决方案
pp solution list

# 部署解决方案
pp solution deploy --env dev
```

### Web 资源（Phase 4）

```bash
# 扫描 webresources/ 目录
pp webresource scan

# 同步到 Dataverse
pp webresource sync --env dev
```

### 工作流编排（Phase 9）

```bash
# 检查 project.py 清单
pp workflow lint

# 部署全部组件（按依赖顺序）
pp workflow deploy --env dev
```

### CI/CD Pipeline

```bash
# 查看分支→环境映射
pp pipeline map

# 部署到 DEV（source mode）
pp pipeline run --branch develop

# 升级到 UAT/PROD（promote mode）
pp pipeline promote --branch release/1.0
```

---

## Workspace 发现

CLI 自动发现 workspace，在**任何子目录**执行命令都能正确解析：

```
优先级：
1. --workspace <path>           显式指定
2. PP_WORKSPACE 环境变量          CI/CD
3. CWD/pp-workspace.yaml         当前目录
4. 从 CWD 向上搜索               像 git 一样
```

---

## MCP Server（AI 交互路径）

MCP Server 将 Dataverse 操作暴露为 Claude Code 可调用的工具。

### 在 Claude Code 中配置

安装后直接使用：

```json
{
  "mcpServers": {
    "power-platform": {
      "command": "pp-mcp"
    }
  }
}
```

### Claude Code 中使用

```plaintext
# 通过自然语言操作
请创建一个客户表，包含账户编号、余额和状态字段
```

---

## 插件开发

### 创建插件项目

```bash
dotnet new classlib -n MyPlugin -f net462
cd MyPlugin
dotnet add package Microsoft.CrmSdk.CoreAssemblies
```

### 构建和部署

```bash
# 构建 .NET 插件
pp plugin build --project-dir plugins/MyPlugin

# 部署到 Dataverse
pp plugin deploy --project-dir plugins/MyPlugin --env dev
```

---

## 典型开发流程

1. **初始化**：`pp workspace init` 创建项目结构
2. **设计**：在 `metadata_py/tables/` 创建 Python 表定义
3. **检查**：`pp lint` 离线验证
4. **预演**：`pp plan --env dev` 只读预览变更
5. **部署**：`pp deploy --env dev` 同步到 DEV
6. **编排**：`pp workflow deploy` 一条命令部署全部
7. **CI/CD**：`pp pipeline run/promote` 自动化环境切换

---

## 故障排查

### 认证失败

```
错误: Authentication failed
解决: 检查 config/environments.yaml 和环境变量（TENANT_ID, CLIENT_ID, CLIENT_SECRET）
```

### Workspace 未找到

```
错误: Not in a Power Platform workspace
解决: 确保当前目录或上级目录有 pp-workspace.yaml，或使用 --workspace <path> 指定
```

### 命名冲突

```
错误: A component with that name already exists
解决: 使用 pp lint 检查命名，确保遵循 config/publishers.yaml 中的 naming 规则
```

---

## 下一步

- [Workspace 架构规划](../references/pac-cli/workspace-architecture-plan.md)
- [外部仓库集成指南](../references/pac-cli/external-repo-integration-guide.md)
- [编码规范](coding-standards.md)
- [配置指南](configuration.md)
