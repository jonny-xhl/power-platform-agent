# Dataverse 后端开发规范

本文档定义 Dataverse C# 插件（.NET）的开发标准。

---

## 1. 代码生成

从 `plugin_def.py` 配置生成 C# 插件文件：

```python
from framework_power.client.plugin_build import load_plugin_project, generate_plugin_cs

# 加载配置
config = load_plugin_project("plugins/Smoke/plugin_def.py")

# 生成 C# 文件
generated = generate_plugin_cs(config, "plugins/Smoke")
# 输出: ['plugins/Smoke/SmokePlugin.cs', 'plugins/Smoke/PP.Crm.Plugin.Smoke.csproj']
```

**生成的文件**：
- `{Module}Plugin.cs` - 插件类模板
- `{AssemblyName}.csproj` - 项目文件

**生成后需完成的工作**：
1. 在插件类中实现具体业务逻辑
2. 如需多个插件类，手动创建并注册到 Step

---

## 2. 目录结构

```
plugins/
└── {Company}.{Project}.{Plugins | Actions}.{Module}/
    ├── {Company}.{Project}.{Plugins | Actions}.{Module}.csproj
    └── *.cs
```

**示例**：
```
plugins/
└── PP.Crm.Plugin.Smoke/
    ├── PP.Crm.Plugin.Smoke.csproj
    └── SmokePlugin.cs
```

---

## 3. 项目文件规范

### 3.1 csproj 配置

```xml
<!-- ✅ 正确：使用 Microsoft.NET.Sdk（SDK-style 项目，dotnet CLI 完全支持） -->
<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <!-- 必须：net462（net6/net8/netstandard 运行时直接拒绝） -->
    <TargetFramework>net462</TargetFramework>
    <Version>1.0.0.0</Version>
    <AssemblyName>PP.Crm.Plugin.{Name}</AssemblyName>
    <PackageId>PP.Crm.Plugin.{Name}</PackageId>
    <Description>插件功能描述</Description>
  </PropertyGroup>

  <ItemGroup>
    <!-- 使用 Microsoft.CrmSdk.CoreAssemblies NuGet 包 -->
    <PackageReference Include="Microsoft.CrmSdk.CoreAssemblies" Version="9.0.2.42" />
  </ItemGroup>

</Project>
```

### 2.2 重要约束

| 项目 | 说明 |
|------|------|
| 目标框架 | 必须 `net462`（`net6`/`net8`/`netstandard` 会触发运行时错误） |
| 项目格式 | SDK-style 项目（`Microsoft.NET.Sdk`），由 `dotnet build` 构建 |
| 部署模式 | PluginPackage（NuGet 包，推荐）或 PluginAssembly（DLL + ILMerge） |

### 2.3 TFM 与部署模式对应

| 部署模式 | 支持的 TFM | 说明 |
|---------|-----------|------|
| **PluginPackage**（推荐） | `net462` | NuGet 包格式，无需 ILMerge/签名 |
| **PluginAssembly**（回退） | `net462` | 需 ILMerge + 强签名 |

---

## 4. 命名规范

| 元素 | 规范 | 示例 |
|------|------|------|
| 项目命名空间 | `{Company}.{Project}.{Module}` | `PP.Crm.Application` |
| 程序集名称 | `{Company}.{Project}.{Module}` | `PP.Crm.Application` |
| 插件类名 | `{Entity}{Action}{Type}Plugin` | `AccountCreatePostPlugin`、`OrderUpdatePrePlugin` |

### 4.1 C# 编码规范

#### 4.1.1 命名规范

```csharp
// ✅ 类名、方法名、属性名：PascalCase
public class AccountService
{
    public string AccountName { get; set; }

    public void CreateAccount() { }
}

// ✅ 私有字段：_camelCase（带下划线前缀）
private readonly IOrganizationService _service;
private readonly ITracingService _tracing;

// ✅ 接口名：I + PascalCase
public interface IAccountAppService { }
public class AccountAppService : IAccountAppService { }

// ✅ 常量：PascalCase
public const string DefaultConnectionString = "...";

// ✅ 枚举值：PascalCase
public enum OrderStatus
{
    Pending,
    Confirmed,
    Shipped
}

// ❌ 避免：匈牙利命名法、缩写（非通用情况下）
// private string m_strName;        // 避免
// private string sName;            // 避免
```

#### 4.1.2 代码格式化

```csharp
// ✅ 使用 C# 12 空引用类型（项目需启用 Nullable）
public class AccountService
{
    // ✅ 非空引用类型参数
    public void CreateAccount(string accountName)
    {
        ArgumentException.ThrowIfNullOrEmpty(accountName);
    }

    // ✅ 可空引用类型用 ? 标记
    public string? GetAccountName(Guid? id)
    {
        if (id == null) return null;
        // ...
    }
}

// ✅ 使用文件级 namespace（C# 10+）
namespace PP.Crm.Application.Account;

// ✅ 简化的类型声明（C# 12+）
public record AccountDto(string Name, string Email);

// ✅ 简洁的属性初始化
public class Config
{
    public string Name { get; set; } = string.Empty;
    public int Timeout { get; set; } = 30;
}
```

#### 4.1.3 最佳实践

```csharp
// ✅ 使用 Primary Constructor（C# 12）
public class AccountAppService(IOrganizationService service, ITracingService tracing)
{
    public void Create(AccountDto dto)
    {
        tracing.Trace("Creating account: {0}", dto.Name);
        var entity = new Account { Name = dto.Name };
        service.Create(entity);
    }
}

// ✅ 使用 pattern matching（C# 8+）
public string GetStatusDescription(OrderStatus status) => status switch
{
    OrderStatus.Pending => "待处理",
    OrderStatus.Confirmed => "已确认",
    OrderStatus.Shipped => "已发货",
    _ => "未知状态"
};

// ✅ 使用 null 条件运算符
var name = entity?.GetAttributeValue<string>("name") ?? "Unknown";

// ✅ 使用 ?.?. 链式调用
var value = targetEntity?.GetAttributeValue<OptionSetValue>("status")?.Value;

// ✅ 使用内插字符串（优于 string.Format）
tracing.Trace("Account {0} created by {1}", id, userId);
```

#### 4.1.4 注释规范

```csharp
/// <summary>
/// 账户应用服务
/// </summary>
/// <remarks>
/// 提供账户的创建、更新、删除等业务操作
/// </remarks>
public interface IAccountAppService
{
    /// <summary>
    /// 创建账户
    /// </summary>
    /// <param name="dto">账户创建请求</param>
    /// <returns>新创建的账户ID</returns>
    /// <exception cref="InvalidPluginExecutionException">当账户名已存在时抛出</exception>
    Guid Create(AccountCreateDto dto);
}

// TODO: 稍后实现此方法（仅用于临时标记）
// FIXME: 修复此处的逻辑问题
// HACK: 临时解决方案
```

#### 4.1.5 LINQ 最佳实践

```csharp
// ✅ 使用 LINQ 方法语法（链式调用）
var activeAccounts = accounts
    .Where(a => a.Status == AccountStatus.Active)
    .OrderBy(a => a.Name)
    .Select(a => new { a.Id, a.Name })
    .ToList();

// ✅ 使用 Sum/Count 聚合
var total = orders.Sum(o => o.Amount);

// ❌ 避免在 LINQ 中执行副作用
// orders.ForEach(o => { o.Process(); service.Update(o); });  // 避免

// ✅ 正确：分离查询和更新
var ordersToProcess = orders.Where(o => !o.Processed).ToList();
foreach (var order in ordersToProcess)
{
    order.Processed = true;
    service.Update(order);
}
```

#### 4.1.6 异步编程规范

```csharp
// ✅ 异步方法命名：Async 后缀
public async Task<Account> GetAccountAsync(Guid id)
{
    return await Task.FromResult(service.Retrieve("account", id, new ColumnSet(true)));
}

// ✅ 使用 ValueTask 避免不必要的分配（高性能场景）
public ValueTask<Account> GetAccountValueTaskAsync(Guid id)
{
    return new ValueTask<Account>(service.Retrieve("account", id, new ColumnSet(true)));
}

// ✅ 异步空操作
await Task.CompletedTask;

// ✅ 异步集合操作
var tasks = entities.Select(e => ProcessEntityAsync(e));
await Task.WhenAll(tasks);
```

---

## 5. 插件代码风格

### 5.1 基础插件模板

```csharp
using System;
using Microsoft.Xrm.Sdk;

namespace PP.Crm.Plugin.Smoke
{
    /// <summary>
    /// 插件功能描述。
    /// 注册信息：实体 new_fpformsmoke，消息 Update，阶段 PostOperation。
    /// </summary>
    public class SmokePlugin : IPlugin
    {
        public void Execute(IServiceProvider serviceProvider)
        {
            // 1. 获取执行上下文
            var context = (IPluginExecutionContext)serviceProvider.GetService(typeof(IPluginExecutionContext));

            // 2. 获取跟踪服务（用于调试）
            var tracing = (ITracingService)serviceProvider.GetService(typeof(ITracingService));

            // 3. 记录跟踪信息
            tracing.Trace("Plugin started: " + context.MessageName);

            try
            {
                // 4. 获取目标实体（如果是 Create/Update）
                if (context.InputParameters.Contains("Target"))
                {
                    var target = (Entity)context.InputParameters["Target"];

                    // 业务逻辑...

                    tracing.Trace("Plugin completed successfully");
                }
            }
            catch (Exception ex)
            {
                tracing.Trace("Plugin error: " + ex.Message);
                throw new InvalidPluginExecutionException("操作失败，请联系管理员。", ex);
            }
        }
    }
}
```

### 5.2 服务获取模式

```csharp
// 标准服务获取（按此顺序）
var context = (IPluginExecutionContext)serviceProvider.GetService(typeof(IPluginExecutionContext));
var tracing = (ITracingService)serviceProvider.GetService(typeof(ITracingService));
var serviceFactory = (IOrganizationServiceFactory)serviceProvider.GetService(typeof(IOrganizationServiceFactory));
var service = serviceFactory.CreateOrganizationService(context.UserId);

// 跟踪日志
tracing.Trace("Debug message: {0}", someValue);
```

### 5.3 输入参数安全访问

```csharp
// ✅ 正确：检查参数是否存在
if (context.InputParameters.Contains("Target") && context.InputParameters["Target"] is Entity target)
{
    var name = target.GetAttributeValue<string>("new_name");
}

// ✅ 正确：获取图像
if (context.PostEntityImages.Contains("PostImage"))
{
    var postImage = context.PostEntityImages["PostImage"];
    var status = postImage.GetAttributeValue<OptionSetValue>("statuscode")?.Value;
}

// ❌ 错误：直接访问可能不存在的参数
var target = (Entity)context.InputParameters["Target"]; // 可能抛出 InvalidCastException
```

### 5.4 异常处理

```csharp
// ✅ 正确：抛出 InvalidPluginExecutionException
throw new InvalidPluginExecutionException("业务错误描述", ex);

// ✅ 正确：记录后重新抛出
catch (FaultException<OrganizationServiceFault> ex)
{
    tracing.Trace("Dataverse error: " + ex.Message);
    throw;
}
```

**Organization Service 异常处理规范**：

在使用 `IOrganizationService` 进行数据操作时，异常处理必须遵循以下规范，避免事务问题：

```csharp
// ✅ 正确：仅记录日志，不要吞掉异常
try
{
    _service.Update(entity);
}
catch (FaultException<OrganizationServiceFault> ex)
{
    _tracing.Trace("Update failed: {0}", ex.Message);
    throw;  // 必须抛出，让事务回滚
}

// ❌ 错误：捕获并吞掉异常，导致事务无法回滚
try
{
    _service.Update(entity);
}
catch (Exception ex)
{
    // 错误：不抛出异常，事务会提交但数据可能不一致
    _tracing.Trace("Update failed: {0}", ex.Message);
}
```

| 操作 | 异常处理 | 原因 |
|------|---------|------|
| `Create/Update/Delete` | 记录日志后抛出 | 确保事务回滚 |
| `Retrieve/RetrieveMultiple` | 记录日志后抛出 | 保持数据一致性 |
| 业务校验失败 | 抛出 `InvalidPluginExecutionException` | 终止当前操作 |

> **重要**：Plugin 中的异常会触发事务回滚，这是预期行为。不要在 `catch` 块中仅记录日志而不抛出异常，除非明确知道业务上需要这样做。

### 5.5 基类封装设计

为避免重复代码，建议封装基类来处理通用逻辑：

#### 4.5.1 插件基类设计

```csharp
namespace PP.Crm.Plugin.Core
{
    /// <summary>
    /// 插件基类，封装通用服务获取和日志记录逻辑
    /// </summary>
    public abstract class PluginBase : IPlugin
    {
        protected IPluginExecutionContext Context { get; private set; }
        protected ITracingService Tracing { get; private set; }
        protected IOrganizationService Service { get; private set; }
        protected Entity Target => Context.InputParameters.Contains("Target")
            ? Context.InputParameters["Target"] as Entity : null;

        public void Execute(IServiceProvider serviceProvider)
        {
            // 1. 获取执行上下文
            Context = (IPluginExecutionContext)serviceProvider.GetService(typeof(IPluginExecutionContext));

            // 2. 获取跟踪服务
            Tracing = (ITracingService)serviceProvider.GetService(typeof(ITracingService));

            // 3. 获取组织服务
            var factory = (IOrganizationServiceFactory)serviceProvider.GetService(typeof(IOrganizationServiceFactory));
            Service = factory.CreateOrganizationService(Context.UserId);

            try
            {
                ExecutePlugin();
            }
            catch (Exception ex)
            {
                Tracing.Trace("Error in {0}: {1}", GetType().Name, ex.Message);
                throw new InvalidPluginExecutionException("操作失败，请联系管理员。", ex);
            }
        }

        /// <summary>
        /// 子类实现具体业务逻辑
        /// </summary>
        protected abstract void ExecutePlugin();
    }
}
```

**使用示例**：

```csharp
public class AccountCreatePostPlugin : PluginBase
{
    protected override void ExecutePlugin()
    {
        if (Target == null) return;

        Tracing.Trace("Creating account: {0}", Target.LogicalName);
        var name = Target.GetAttributeValue<string>("name");

        // 业务逻辑...
    }
}
```

#### 4.5.2 服务层封装

```csharp
namespace PP.Crm.Plugin.Core
{
    /// <summary>
    /// 数据服务基类，封装常用 CRUD 操作
    /// </summary>
    public class ServiceContext
    {
        protected readonly IOrganizationService _service;
        protected readonly ITracingService _tracing;

        public ServiceContext(IOrganizationService service, ITracingService tracing)
        {
            _service = service;
            _tracing = tracing;
        }

        /// <summary>
        /// 安全获取实体
        /// </summary>
        public Entity Retrieve(string entityName, Guid id, ColumnSet columns)
        {
            try
            {
                return _service.Retrieve(entityName, id, columns);
            }
            catch (Exception ex)
            {
                _tracing.Trace("Retrieve error: {0}", ex.Message);
                throw;
            }
        }

        /// <summary>
        /// 安全更新实体
        /// </summary>
        public void Update(Entity entity)
        {
            _service.Update(entity);
            _tracing.Trace("Updated {0}: {1}", entity.LogicalName, entity.Id);
        }

        /// <summary>
        /// 执行 FetchXML 查询
        /// </summary>
        public EntityCollection RetrieveMultiple(string fetchXml)
        {
            var query = new FetchExpression(fetchXml);
            return _service.RetrieveMultiple(query);
        }
    }
}
```

#### 4.5.3 验证辅助类

```csharp
namespace PP.Crm.Plugin.Core
{
    /// <summary>
    /// 插件验证辅助类
    /// </summary>
    public static class PluginValidator
    {
        /// <summary>
        /// 验证目标实体是否存在
        /// </summary>
        public static bool HasTarget(IPluginExecutionContext context)
        {
            return context.InputParameters.Contains("Target")
                && context.InputParameters["Target"] is Entity;
        }

        /// <summary>
        /// 安全获取属性值
        /// </summary>
        public static T GetValue<T>(Entity entity, string attributeName)
        {
            return entity?.GetAttributeValue<T>(attributeName);
        }

        /// <summary>
        /// 安全获取选项集值
        /// </summary>
        public static int? GetOptionSetValue(Entity entity, string attributeName)
        {
            return entity?.GetAttributeValue<OptionSetValue>(attributeName)?.Value;
        }
    }
}
```

#### 4.5.4 基类使用原则

| 原则 | 说明 |
|-----|------|
| 抽象通用逻辑 | 服务获取、异常处理、日志记录等重复逻辑放入基类 |
| 单一职责 | 基类仅处理基础设施，具体业务逻辑由子类实现 |
| 依赖注入 | 通过构造函数注入必要的服务（如 ServiceContext） |
| 不可见域 | 不在基类中硬编码实体名称、属性名称等业务相关常量 |

#### 4.5.5 项目结构建议

完整的后端项目架构：

```
src/
├── PP.Crm.Common/                        # 通用工具层（无业务依赖，所有层可用）
│   ├── PP.Crm.Common.csproj
│   ├── DateTimeHelper.cs                 # 日期时间处理
│   ├── JsonHelper.cs                     # JSON 序列化/反序列化
│   ├── StringHelper.cs                   # 字符串处理
│   ├── ValidationHelper.cs               # 通用验证
│   ├── EncryptionHelper.cs               # 加密/解密工具
│   ├── ConfigHelper.cs                   # 配置文件读取
│   ├── LogHelper.cs                      # 日志辅助（通用版）
│   ├── HttpClientHelper.cs               # HTTP 请求封装
│   ├── Guard.cs                          # 参数校验（Guard Clauses）
│   └── Extensions/
│       ├── StringExtensions.cs           # 字符串扩展方法
│       ├── DateTimeExtensions.cs         # 日期扩展方法
│       └── EnumerableExtensions.cs       # 集合扩展方法
│
├── PP.Crm.Core/                         # 领域基础设施（Plugin 相关基类）
│   ├── PP.Crm.Core.csproj               # 依赖 Common
│   ├── PluginBase.cs                     # 插件基类
│   ├── ServiceContext.cs                 # 数据服务基类
│   ├── PluginValidator.cs                # 验证辅助类
│   ├── TracingHelper.cs                  # 跟踪日志辅助（Dataverse）
│   ├── ExceptionHelper.cs                # 异常处理辅助
│   └── Constants/
│       └── ErrorMessages.cs             # 错误消息常量
│
├── PP.Crm.Shared/                        # 共享层（实体模型、DTO、枚举）
│   ├── PP.Crm.Shared.csproj             # 依赖 Common
│   ├── Entities/
│   │   ├── Account.cs                   # Early-bound 实体类
│   │   ├── Contact.cs
│   │   └── Order.cs
│   ├── OptionSets/
│   │   ├── AccountStatus.cs             # 选项集常量
│   │   └── OrderPriority.cs
│   ├── DTOs/
│   │   ├── AccountCreateRequest.cs      # 请求 DTO
│   │   └── AccountCreateResponse.cs     # 响应 DTO
│   └── Enums/
│       └── PluginStage.cs               # 阶段枚举
│
├── PP.Crm.Application/                  # 应用服务层（DDD Application，封装业务用例）
│   ├── PP.Crm.Application.csproj        # 依赖 Common + Core + Shared
│   ├── Account/                         # 可被 Plugin/Workflow/Api/Console 复用
│   │   ├── IAccountAppService.cs         # 应用服务接口
│   │   └── AccountAppService.cs          # 服务实现（用例编排）
│   ├── Order/
│   │   ├── IOrderAppService.cs
│   │   └── OrderAppService.cs
│   ├── Contact/
│   │   ├── IContactAppService.cs
│   │   └── ContactAppService.cs
│   └── Helpers/
│       └── AppServiceFactory.cs           # 服务工厂
│
├── PP.Crm.Plugins/                       # 插件基础设施（仅负责消息处理，调用 Application）
│   ├── PP.Crm.Plugins.csproj            # 依赖 Common + Core + Shared + Application
│   ├── Account/
│   │   ├── AccountCreatePostPlugin.cs
│   │   └── AccountUpdatePrePlugin.cs
│   └── Order/
│       └── OrderCreatePrePlugin.cs
│
└── PP.Crm.Workflow/                      # 自定义 Workflow Activity
    ├── PP.Crm.Workflow.csproj            # 依赖 Common + Core + Shared + Application
    └── Activities/
        ├── CalculateDiscount.cs
        └── SendNotification.cs

tests/
├── PP.Crm.Common.Tests/                  # 通用工具测试
├── PP.Crm.Core.Tests/                    # 基础设施测试
├── PP.Crm.Shared.Tests/                   # 共享层测试
├── PP.Crm.Application.Tests/             # 应用服务测试
└── PP.Crm.Plugins.Tests/                  # 插件测试
```

**项目引用关系**：

```
                         ┌─────────────────────┐
                         │     PP.Crm.Common    │
                         │  （无依赖，通用工具层）  │
                         └──────────┬──────────┘
                                    ↑
              ┌──────────────────────┴──────────────────────┐
              │                         │                   │
┌─────────────┴─────────────┐  ┌────────┴────────┐  ┌─────┴─────┐
│        Core              │  │     Shared      │  │ Application│
│ - Plugin基类            │  │ - 实体模型       │  │ - 业务用例 │
│ - 数据访问基类          │  │ - DTO/枚举      │  │ - 依赖     │
│ - 依赖 Common           │  │ - 依赖 Common   │  │   Common+  │
└─────────────────────────┘  └─────────────────┘  │   Core+    │
                                                  │   Shared   │
                                                  └─────┬─────┘
                                                        ↑
                              ┌──────────────────────────┴──────────────────────┐
                              ↓                                                       ↓
                      ┌───────────────┐                                   ┌───────────────┐
                      │   Plugins    │                                   │   Workflow    │
                      │ - 消息处理   │                                   │ - 自定义活动  │
                      │ - 依赖全链路 │                                   │ - 依赖全链路  │
                      └───────────────┘                                   └───────────────┘
```

**各项目职责**：

| 项目 | 职责 | 依赖 |
|------|------|------|
| `Common` | 通用工具（字符串、日期、JSON、加密、验证等） | 无 |
| `Core` | Plugin 基类、数据访问基类、日志辅助 | Common |
| `Shared` | 实体模型、选项集、DTO、枚举 | Common |
| `Application` | 业务用例封装（DDD Application层） | Common + Core + Shared |
| `Plugins` | 消息处理（调用 Application，不含业务逻辑） | Common + Core + Shared + Application |
| `Workflow` | 自定义 Workflow Activity（调用 Application） | Common + Core + Shared + Application |
| `*.Tests` | 单元测试 | 对应业务项目 |

**JSON 序列化选择**：

> **优先使用 Json.NET (Newtonsoft.Json)**，避免使用 System.Text.Json。

| 库 | 推荐程度 | 原因 |
|---|:---:|---|
| **Json.NET** (Newtonsoft.Json) | ✅ 首选 | 完全可控的序列化行为，无版本限制 |
| System.Text.Json | ⚠️ 慎用 | Dataverse 环境存在版本约束问题 |

**为什么慎用 System.Text.Json**：
- Dataverse 服务端使用的 `Microsoft.CrmSdk.CoreAssemblies` 包内部已依赖特定版本的 System.Text.Json
- 如果插件程序集也引用 System.Text.Json，可能产生版本冲突
- 如果必须使用，需通过 **Dependent Assemblies** 功能将特定版本打包上传（仅支持 Online，不支持 On-premises）
- 新项目建议直接使用 Json.NET，完全避免此问题

**为什么 Application 单独成层**：

```
Plugin A (账户创建后)                    Plugin B (订单创建时)
      │                                        │
      ↓                                        ↓
AccountAppService.UpdateBalance()    OrderAppService.CreateWithValidation()
      │                                        │
      └────────────────┬───────────────────────┘
                       ↓
              ┌────────────────┐
              │   共享的业务逻辑  │
              └────────────────┘
```

| 分层 | 说明 |
|------|------|
| Plugins | 入口点，接收消息，调用 Application，不含业务逻辑 |
| Application | 业务用例封装（DDD Application层），可被 Plugin/Workflow/Api 复用 |
| Core | 基础设施（数据访问基类、工具类） |
| Shared | 数据模型（实体、DTO、枚举） |

**NuGet 包引用**：

```xml
<!-- 所有项目 -->
<PackageReference Include="Microsoft.CrmSdk.CoreAssemblies" Version="9.0.2.42" />

<!-- Shared 项目（Early-bound 工具） -->
<PackageReference Include="Microsoft.CrmSdk.XrmTooling.CoreAssembly" Version="9.1.0.7" />
```

---

## 6. Plugin Step 注册规范

### 6.1 Step 配置要素

Step 注册必须指定：
- **实体名**（LogicalName）
- **消息名**：Create / Update / Delete / Retrieve / RetrieveMultiple / 自定义 Action
- **阶段**：PreValidation (10) / PreOperation (20) / PostOperation (40)
- **执行模式**：Synchronous (0) / Asynchronous (1)

### 6.2 Step 配置示例

```csharp
// Step 配置（通过 framework_power 部署）
var step = new PluginStep
{
    PluginType = "PP.Crm.Plugins.Account.Create",
    MessageName = "Create",
    EntityName = "new_account",
    Stage = Stage.PostOperation,
    Mode = ExecutionMode.Synchronous,
    Rank = 1
};
```

### 6.3 阶段选择指南

| 阶段 | 值 | 适用场景 |
|------|-----|---------|
| PreValidation | 10 | 数据验证（早于事务） |
| PreOperation | 20 | 数据修改（事务内） |
| PostOperation | 40 | 后置处理（事务后） |

---

## 7. 常用插件模式

### 7.1 Create 插件

```csharp
public class AccountCreatePlugin : IPlugin
{
    public void Execute(IServiceProvider serviceProvider)
    {
        var context = (IPluginExecutionContext)serviceProvider.GetService(typeof(IPluginExecutionContext));
        var tracing = (ITracingService)serviceProvider.GetService(typeof(ITracingService));

        if (context.InputParameters.Contains("Target") && context.InputParameters["Target"] is Entity entity)
        {
            // 设置默认值
            if (!entity.Contains("new_status"))
            {
                entity["new_status"] = new OptionSetValue(100000000); // Active
            }

            tracing.Trace("Account created: " + entity.Id);
        }
    }
}
```

### 7.2 Update 插件

```csharp
public class AccountUpdatePlugin : IPlugin
{
    public void Execute(IServiceProvider serviceProvider)
    {
        var context = (IPluginExecutionContext)serviceProvider.GetService(typeof(IPluginExecutionContext));
        var tracing = (ITracingService)serviceProvider.GetService(typeof(ITracingService));

        if (context.InputParameters.Contains("Target") && context.InputParameters["Target"] is Entity entity)
        {
            // 获取更新前的值（需要注册 PreEntityImage）
            if (context.PreEntityImages.Contains("PreImage"))
            {
                var preImage = context.PreEntityImages["PreImage"];
                var oldStatus = preImage.GetAttributeValue<OptionSetValue>("statuscode")?.Value;
            }

            // 检查特定字段变更
            if (entity.Contains("new_status"))
            {
                var newStatus = entity.GetAttributeValue<OptionSetValue>("new_status")?.Value;
                tracing.Trace("Status changed to: " + newStatus);
            }
        }
    }
}
```

### 7.3 异步插件

```csharp
public class AccountAsyncPlugin : IPlugin
{
    public void Execute(IServiceProvider serviceProvider)
    {
        var context = (IPluginExecutionContext)serviceProvider.GetService(typeof(IPluginExecutionContext));
        var tracing = (ITracingService)serviceProvider.GetService(typeof(ITracingService));

        try
        {
            // 执行业务逻辑
            var target = (Entity)context.InputParameters["Target"];

            // 异步操作示例：发送通知
            SendNotificationAsync(target);

            tracing.Trace("Async plugin queued successfully");
        }
        catch (Exception ex)
        {
            tracing.Trace("Async plugin error: " + ex.Message);
            throw new InvalidPluginExecutionException("异步处理失败", ex);
        }
    }

    private void SendNotificationAsync(Entity account)
    {
        // 实现通知逻辑
    }
}
```

---

## 8. 调试与日志

### 8.1 跟踪日志

```csharp
// 基本日志
tracing.Trace("Plugin started");
tracing.Trace("EntityId: " + context.PrimaryEntityId);

// 带参数的日志
tracing.Trace("Processing record: {0}, Message: {1}",
    context.PrimaryEntityId,
    context.MessageName);

// 条件日志
if (tracing.IsTracingEnabled)
{
    tracing.Trace("Detailed debug info...");
}
```

### 8.2 PluginProfile 调试

在开发环境启用 PluginProfile 进行性能分析：

```csharp
// 监控慢查询
tracing.Trace("Query execution time: " + stopwatch.ElapsedMilliseconds + "ms");
```

---

## 9. 代码检查与构建

### 9.1 项目结构

```
src/
├── PP.Crm.Common/           # 通用工具层（无外部依赖）
├── PP.Crm.Core/             # 插件基础设施（依赖 Common）
├── PP.Crm.Shared/           # 共享层（依赖 Common）
├── PP.Crm.Application/      # 应用服务层（依赖 Common + Core + Shared）
├── PP.Crm.Plugins/          # 插件层（依赖 Common + Core + Shared + Application）
└── PP.Crm.Workflow/         # 工作流层（依赖 Common + Core + Shared + Application）
```

### 9.2 构建命令

```bash
# 进入 src 目录
cd src

# 还原依赖
dotnet restore

# 构建所有项目
dotnet build

# 构建 Release 版本
dotnet build -c Release

# 构建特定项目
dotnet build PP.Crm.Plugins/PP.Crm.Plugins.csproj

# 运行测试
dotnet test
```

### 9.3 NuGet 包引用

```xml
<!-- 所有项目 -->
<PackageReference Include="Microsoft.CrmSdk.CoreAssemblies" Version="9.0.2.42" />

<!-- Application 层（使用 Json.NET） -->
<PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
```

### 9.4 常见构建错误

| 错误 | 解决方案 |
|------|---------|
| `<TargetFramework>net6.0</TargetFramework>` 不支持 | 改为 `<TargetFramework>net462</TargetFramework>` |
| 找不到 Microsoft.Xrm.Sdk | 添加 `Microsoft.CrmSdk.CoreAssemblies` NuGet 包 |
| System.Text.Json 版本冲突 | 使用 Json.NET 替代，参考 4.5.5 JSON 序列化选择 |
| 项目循环依赖 | 检查依赖关系：Common → Core/Shared → Application → Plugins/Workflow |
| 强签名错误 | 确保所有项目签名配置一致 |

---

## 10. 最佳实践汇总

### 10.1 架构原则

1. **分层依赖**：只允许上层依赖下层，禁止反向依赖
   - `Common` → `Core` / `Shared` → `Application` → `Plugins` / `Workflow`
2. **单一职责**：每个项目专注一个职责
3. **接口分离**：Application 层使用接口，便于测试和替换

### 10.2 开发规范

1. **目标框架** 必须是 net462
2. **JSON 序列化** 优先使用 Json.NET（Newtonsoft.Json）
3. **使用 NuGet Package** 而非直接引用 DLL
4. **始终获取和记录** ITracingService
5. **安全访问参数** 先检查 Contains 再访问
6. **异常处理** 使用 InvalidPluginExecutionException，参考 5.4 节
7. **事务一致性** 异常必须抛出，确保事务回滚
8. **保持插件轻量** 避免长时间运行的操作
9. **注册 PreEntityImage** 用于比较更新前后的值
10. **业务逻辑上移** Plugin 仅处理消息，调用 Application 层

---

## 11. 相关文档

- [webresource-development.md](./webresource-development.md) - WebResource 开发规范
- [coding-standards.md](./coding-standards.md) - 开发规范索引
- [framework_power/CLAUDE.md](../../framework_power/CLAUDE.md) - Python 部署库详细说明
