# Power Platform 快速开始指南

## 安装

### 前置要求

- Python 3.8+
- .NET SDK 8.0+ (用于插件开发)
- PAC CLI (可选，用于解决方案管理)

### 安装步骤

1. 克隆或下载项目
```bash
git clone https://github.com/your-org/power-platform-agent.git
cd power-platform-agent
```

2. 安装 Python 依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量
```bash
export TENANT_ID="your-tenant-id"
export CLIENT_ID="your-client-id"
export CLIENT_SECRET="your-client-secret"
```

## 配置

### 环境配置

编辑 `config/environments.yaml`，添加你的环境信息：

```yaml
environments:
  dev:
    url: "https://your-org-dev.crm.dynamics.com"
    tenant_id: "${TENANT_ID}"
    client_id: "${CLIENT_ID}"
    client_secret: "${CLIENT_SECRET}"
```

### 命名规则配置

编辑 `config/naming_rules.yaml`，设置你的命名偏好：

```yaml
naming:
  prefix: "new"  # 发布商前缀
  schema_name:
    style: "lowercase"  # lowercase | camelCase | PascalCase
    auto_prefix: true
```

## 使用

### 启动 MCP 服务器

```bash
python mcp_serve.py
```

或使用 stdio 模式：

```bash
python mcp_serve.py --stdio
```

### 在 Claude Code 中使用

1. 连接到环境
```plaintext
/auth login --env dev
```

2. 创建表
```plaintext
请创建一个客户表，包含账户编号、余额和状态字段
```

3. 添加字段
```plaintext
为账户表添加一个信用额度字段，类型为货币
```

4. 创建表单
```plaintext
创建一个账户主表单，包含基本信息和财务信息两个选项卡
```

### 命名转换

```plaintext
将 "CustomerAccountNumber" 转换为 schema_name
# 结果: new_customer_account_number
```

### 验证元数据

```yaml
# metadata/tables/customer.yaml
$schema: "../_schema/table_schema.yaml"

schema:
  schema_name: "customer"
  display_name: "客户"
  ownership_type: "UserOwned"
```

```plaintext
验证 metadata/tables/customer.yaml
```

## 插件开发

### 创建插件项目

```bash
dotnet new classlib -n MyPlugin -f net8.0
cd MyPlugin
dotnet add package Microsoft.CrmSdk.CoreAssemblies
```

### 编写插件

```csharp
using Microsoft.Xrm.Sdk;

public class MyPlugin : IPlugin
{
    public void Execute(IServiceProvider serviceProvider)
    {
        var context = (IPluginExecutionContext)serviceProvider.GetService(typeof(IPluginExecutionContext));
        var tracingService = (ITracingService)serviceProvider.GetService(typeof(ITracingService));

        tracingService.Trace("Plugin executed!");
    }
}
```

### 构建和部署

```plaintext
/plugin_build --project_path plugins/MyPlugin/MyPlugin.csproj
/plugin_deploy --assembly_path plugins/MyPlugin/bin/Release/net8.0/MyPlugin.dll
/plugin_step_register --plugin_name MyPlugin --entity account --message Create --stage post-operation
```

## 解决方案管理

### 导出解决方案

```plaintext
/solution_export --solution_name MySolution --managed false
```

### 导入解决方案

```plaintext
/solution_import --solution_path solutions/MySolution.zip
```

### 对比差异

```plaintext
/solution_diff --local_path metadata/tables --solution_name MySolution
```

## 工作流程

### 典型开发流程

1. **设计阶段**
   - 在 `metadata/` 目录创建 YAML 定义文件
   - 使用 Schema 验证确保格式正确

2. **开发阶段**
   - 使用 `metadata_apply` 应用元数据到开发环境
   - 在 Dataverse 中测试

3. **插件开发**
   - 编写 .NET 插件代码
   - 使用监听模式自动构建和部署

4. **测试阶段**
   - 在测试环境中验证
   - 使用 `solution_diff` 检查差异

5. **部署阶段**
   - 使用解决方案导出/导入
   - 或使用元数据同步

### 命名规范

建议遵循以下命名规范：

1. **Schema Name**: 使用 `lowercase` 风格
   - `customer_account` (而非 `CustomerAccount`)

2. **Display Name**: 使用中文
   - `display_name: "客户账户"`

3. **Web Resource**: 按类型组织
   - `new_css/account_form.css`
   - `new_js/account_handler.js`

## 故障排查

### 认证失败

```
错误: Authentication failed
解决: 检查环境变量配置，确认 CLIENT_ID 和 CLIENT_SECRET 正确
```

### 命名冲突

```
错误: A component with that name already exists
解决: 使用 naming_validate 检查命名，或使用不同的名称
```

### 限流错误

```
错误: 429 Too Many Requests
解决: 等待片刻后重试，或减少并发请求数
```

## 最佳实践

1. **使用版本控制**
   - 将 `metadata/` 目录纳入 Git 管理
   - 为每个功能创建分支

2. **测试环境优先**
   - 始终在测试环境验证后再部署到生产环境

3. **命名一致性**
   - 保持命名风格一致
   - 使用前缀避免冲突

4. **文档化**
   - 为自定义元数据添加描述
   - 记录重要的业务规则

5. **备份**
   - 定期导出解决方案作为备份
   - 保留重要的配置文件

## 下一步

- 阅读 [架构文档](architecture.md)
- 参考 [命名规范](naming-spec.md)
- 查看 [元数据规范](metadata-spec.md)
- 了解 [API 参考](api-spec.md)
