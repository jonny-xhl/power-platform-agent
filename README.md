# Power Platform Agent

Power Platform 开发辅助工具 - 基于 Hermes Agent 框架构建，通过 MCP 协议为 Claude Code 和 Cursor 提供工具访问。

## 功能特性

- 📋 **代码优先开发**: 使用 YAML 定义 Power Platform 元数据
- 🔧 **插件自动化**: 自动构建、部署 .NET 插件
- 🔄 **双向同步**: 本地与云端元数据对比和同步
- 📝 **命名规范**: 统一的命名转换和验证规则
- 🧩 **多环境支持**: 管理 dev/test/prod 多环境配置

## 快速开始

### 安装依赖

```bash
# Windows
install.bat

# Linux/Mac
chmod +x install.sh
./install.sh
```

或手动安装：

```bash
pip install -r requirements.txt
```

### 运行构建验证

```bash
python build_and_validate.py
```

### 启动MCP服务器

```bash
# Stdio模式（推荐用于IDE集成）
python mcp_serve.py --stdio

# SSE模式（独立运行）
python mcp_serve.py --port 8000
```

### 测试导入

```bash
python test_imports.py
```

## 项目结构

```
power-platform-agent/
├── metadata/              # YAML元数据定义
│   ├── _schema/           # Schema定义
│   ├── tables/            # 表定义
│   ├── forms/             # 表单定义
│   ├── views/             # 视图定义
│   ├── webresources/      # Web Resource配置
│   ├── ribbon/            # 命令栏定义
│   └── sitemap/           # 应用导航定义
├── webresources/          # Web Resource源文件
│   ├── css/
│   ├── js/
│   ├── html/
│   └── img/
├── plugins/               # .NET插件源码
│   └── AccountPlugin/
├── config/                # 配置文件
│   ├── hermes_profile.yaml
│   ├── environments.yaml
│   ├── naming_rules.yaml
│   ├── extensions.yaml
│   └── settings.yaml
├── agents/                # 代理实现
│   ├── core_agent.py
│   ├── metadata_agent.py
│   ├── plugin_agent.py
│   └── solution_agent.py
├── utils/                 # 工具函数
│   ├── dataverse_client.py
│   ├── yaml_parser.py
│   ├── schema_validator.py
│   └── naming_converter.py
├── skills/                # SKILL定义
├── docs/                  # 文档
└── mcp_serve.py           # MCP服务器入口
```

---

## 快速开始

### 安装依赖

```bash
cd power-platform-agent
pip install -r requirements.txt
```

### 配置环境变量

```bash
export TENANT_ID="your-tenant-id"
export CLIENT_ID="your-client-id"
export CLIENT_SECRET="your-client-secret"
```

### 在 Claude Code 中配置 MCP Server

在 `.claude/settings.json` 中添加：

```json
{
  "mcpServers": {
    "power-platform": {
      "command": "python",
      "args": ["{your_path}/power-platform-agent/mcp_serve.py"],
      "env": {
        "TENANT_ID": "${TENANT_ID}",
        "CLIENT_ID": "${CLIENT_ID}",
        "CLIENT_SECRET": "${CLIENT_SECRET}"
      }
    }
  }
}
```

---

## 使用指南

### 🔐 认证与连接

```
# 连接到开发环境
连接到 dev 环境

# 查看连接状态
查看当前连接状态

# 切换环境
切换到 test 环境

# 断开连接
登出当前环境
```

### 📋 元数据管理

```
# 创建表（自然语言描述）
创建一个客户表，包含以下字段：
- 客户编号 (String, 必填, 主名称)
- 联系电话 (String)
- 账户余额 (Money, 精度2位)
- 客户状态 (Picklist: 活跃/冻结/关闭)

# 验证元数据
验证 metadata/tables/customer.yaml 的格式

# 应用到Dataverse
将 customer 表应用到 Dataverse

# 导出元数据
将 account 表导出为 YAML 到 output/ 目录
```

### 🏷️ 命名转换

```
# 转换Schema名称
将 "CustomerAccountNumber" 转换为 lowercase 风格的 schema_name
# 输出: new_customer_account_number

# 批量转换
转换以下字段名为 schema_name:
- AccountBalance
- CustomerType
- IsActive

# 验证命名
验证 "new_customer_account" 是否符合命名规则

# 查看命名规则
显示当前的命名规则配置
```

### 🔌 插件管理

```
# 构建插件
构建 plugins/AccountPlugin/AccountPlugin.csproj

# 部署插件
部署 plugins/AccountPlugin/bin/Release/net8.0/AccountPlugin.dll

# 注册Step
为 AccountPlugin 注册一个 Step：
- 实体: account
- 消息: Create
- 阶段: post-operation

# 列出Steps
列出 AccountPlugin 的所有注册Steps

# 删除Step
删除指定Step
```

### 📦 解决方案管理

```
# 导出解决方案
导出 MySolution_Dev 解决方案

# 导入解决方案
导入 solutions/MySolution.zip 到 test 环境

# 对比差异
对比本地 metadata/ 与云端 MySolution 的差异

# 双向同步
执行本地到云端的双向同步

# 查看同步状态
查看当前同步状态
```

---

## 典型工作流程

### 流程1: 创建新表

```
1. 编辑 metadata/tables/product.yaml
   ↓
2. 验证: 验证 product.yaml
   ↓
3. 检查命名: 检查命名是否符合规则
   ↓
4. 应用: 将 product 表应用到 Dataverse
   ↓
5. 确认: 查看创建结果
```

### 流程2: 开发插件

```
1. 编写 C# 插件代码
   ↓
2. 配置 plugin_config.yaml
   ↓
3. 构建: 构建插件项目
   ↓
4. 部署: 部署程序集
   ↓
5. 注册: 注册 Plugin Step
   ↓
6. 测试: 在 Dataverse 中测试
```

### 流程3: 表单设计

```
1. 创建表单定义 YAML
   ↓
2. 配置选项卡和分区
   ↓
3. 添加字段到单元格
   ↓
4. 关联 Web Resources
   ↓
5. 应用到 Dataverse
```

---

## 对话示例

### 场景：创建账户表

```
你: 我需要创建一个银行账户表

Agent: 好的，我来帮你创建银行账户表。请告诉我需要哪些字段？

你: 需要账户号、账户类型(储蓄/支票)、余额、开户日期

Agent: 明白了。我将为你创建一个账户表，包含以下字段：
- accountNumber (账户号) - String类型
- accountType (账户类型) - Picklist
- balance (余额) - Money类型
- openedDate (开户日期) - DateTime类型

正在生成 YAML 元数据...
正在验证 Schema...
正在应用命名转换 (account → new_account)...
正在应用到 Dataverse...

✓ 表创建成功！schema_name: new_account
```

### 场景：修复命名问题

```
你: 这个字段命名有问题吗: CustomerAccount_123?

Agent: 让我检查一下...

检查结果：
✗ 不符合命名规则
问题:
  - 包含非法字符 "_123"
  - 建议使用: new_customer_account_123 或 new_customer_account123

是否需要我帮你转换？
```

### 场景：插件部署

```
你: 我修改了插件代码，帮我重新部署

Agent: 好的，正在处理：

1. 检测到插件代码变更
2. 正在构建...
   ✓ 构建成功: AccountPlugin.dll v1.0.0.1
3. 正在部署...
   ✓ 部署成功
4. 正在更新Steps...
   ✓ Step 更新成功

插件已重新部署并生效！
```

---

## 高级技巧

### 1. 批量操作

```
批量转换所有属性名为 schema_name
批量验证 metadata/tables/ 下的所有文件
批量部署 Web Resources
```

### 2. 差异同步

```
对比本地与云端差异，告诉我需要同步什么
执行双向同步，保留本地修改
```

### 3. 监听模式

```
开启插件监听模式，自动构建和部署
```

### 4. 命名规则定制

编辑 `config/naming_rules.yaml`：

```yaml
naming:
  prefix: "your_prefix"        # 修改前缀
  schema_name:
    style: "camelCase"          # 改为驼峰风格
```

---

## 故障排查

| 问题 | 解决方案 |
|-----|---------|
| 认证失败 | 检查环境变量配置 |
| 命名冲突 | 使用 `naming_validate` 检查 |
| API限流 | 等待后重试，系统会自动处理 |
| Schema错误 | 使用 `metadata_validate` 验证 |
| 标准表保护 | 确认是否真的需要修改标准表 |

---

## 命令速查

| 功能 | 命令/描述 |
|-----|----------|
| **认证** | |
| 连接环境 | `连接到 dev 环境` |
| 查看状态 | `查看连接状态` |
| 切换环境 | `切换到 test 环境` |
| **元数据** | |
| 创建表 | `创建一个客户表，包含...` |
| 验证元数据 | `验证 customer.yaml` |
| 应用元数据 | `将 customer 表应用到 Dataverse` |
| 导出元数据 | `导出 account 表为 YAML` |
| **命名** | |
| 转换命名 | `将 "AccountName" 转换为 schema_name` |
| 验证命名 | `验证 "new_customer" 是否符合规则` |
| 查看规则 | `显示当前命名规则` |
| **插件** | |
| 构建插件 | `构建 AccountPlugin.csproj` |
| 部署插件 | `部署 AccountPlugin.dll` |
| 注册Step | `注册插件 Step: account/Create/post` |
| **解决方案** | |
| 导出解决方案 | `导出 MySolution` |
| 导入解决方案 | `导入 MySolution.zip` |
| 对比差异 | `对比本地与云端差异` |
| 同步状态 | `查看同步状态` |

---

## 文档

- [架构文档](docs/spec/architecture.md) - 系统架构设计
- [元数据规范](docs/spec/metadata-spec.md) - 元数据定义规范
- [快速开始](docs/guides/getting-started.md) - 详细入门指南

---

## 技术栈

- **Agent框架**: Hermes Agent
- **MCP协议**: Model Context Protocol
- **元数据格式**: YAML + JSON Schema
- **认证**: MSAL (OAuth 2.0)
- **插件开发**: .NET 8.0

---

## License

MIT License
