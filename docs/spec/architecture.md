# Power Platform Agent 架构文档

## 概述

Power Platform Agent 是一个基于 Hermes Agent 框架构建的 Power Platform 开发辅助工具。它通过 MCP (Model Context Protocol) 服务器为 Claude Code 和 Cursor 提供工具访问，实现 Power Platform 元数据的代码优先开发。

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
│  ┌──────────────┐  │ - Web Res    │  └──────────────────┘     │
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
