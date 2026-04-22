using System;
using Microsoft.Xrm.Sdk;

namespace PowerPlatform.Plugins.Account
{
    /// <summary>
    /// 账户插件 - 处理账户实体的创建和更新操作
    /// </summary>
    public class AccountPlugin : IPlugin
    {
        /// <summary>
        /// 插件执行入口点
        /// </summary>
        /// <param name="serviceProvider">服务提供者</param>
        public void Execute(IServiceProvider serviceProvider)
        {
            // 获取上下文
            var context = (IPluginExecutionContext)serviceProvider.GetService(typeof(IPluginExecutionContext));
            var tracingService = (ITracingService)serviceProvider.GetService(typeof(ITracingService));

            try
            {
                tracingService.Trace($"AccountPlugin started at {DateTime.UtcNow}");
                tracingService.Trace($"Message: {context.MessageName}");
                tracingService.Trace($"Stage: {context.Stage}");

                // 获取目标实体
                if (!context.InputParameters.Contains("Target") || context.InputParameters["Target"] is not Entity)
                {
                    tracingService.Trace("Target entity not found in input parameters.");
                    return;
                }

                var entity = (Entity)context.InputParameters["Target"];

                // 根据消息执行不同操作
                switch (context.MessageName.ToLower())
                {
                    case "create":
                        OnCreate(entity, tracingService, serviceProvider);
                        break;
                    case "update":
                        OnUpdate(entity, tracingService, serviceProvider);
                        break;
                    case "delete":
                        OnDelete(entity, tracingService, serviceProvider);
                        break;
                    default:
                        tracingService.Trace($"Unhandled message: {context.MessageName}");
                        break;
                }

                tracingService.Trace("AccountPlugin completed successfully.");
            }
            catch (Exception ex)
            {
                tracingService.Trace($"Error in AccountPlugin: {ex.ToString()}");
                throw new InvalidPluginExecutionException($"AccountPlugin执行失败: {ex.Message}");
            }
        }

        /// <summary>
        /// 处理账户创建
        /// </summary>
        private void OnCreate(Entity entity, ITracingService tracingService, IServiceProvider serviceProvider)
        {
            tracingService.Trace("Handling Create message for Account entity");

            // 验证必填字段
            if (!entity.Contains("new_accountnumber"))
            {
                entity["new_accountnumber"] = GenerateAccountNumber(tracingService);
                tracingService.Trace($"Generated account number: {entity["new_accountnumber"]}");
            }

            // 设置默认状态
            if (!entity.Contains("new_status"))
            {
                entity["new_status"] = new OptionSetValue(100000000); // 活跃
                tracingService.Trace("Set default status to Active");
            }

            // 设置创建日期
            if (!entity.Contains("new_openeddate"))
            {
                entity["new_openeddate"] = DateTime.UtcNow;
                tracingService.Trace($"Set opened date to {DateTime.UtcNow}");
            }
        }

        /// <summary>
        /// 处理账户更新
        /// </summary>
        private void OnUpdate(Entity entity, ITracingService tracingService, IServiceProvider serviceProvider)
        {
            tracingService.Trace("Handling Update message for Account entity");

            // 检查状态变更
            if (entity.Contains("new_status"))
            {
                var newStatus = entity.GetAttributeValue<OptionSetValue>("new_status")?.Value;
                tracingService.Trace($"Status changed to: {newStatus}");

                // 如果账户被关闭，执行相关业务逻辑
                if (newStatus == 100000002) // 关闭
                {
                    HandleAccountClosure(entity, tracingService, serviceProvider);
                }
            }

            // 检查余额变更
            if (entity.Contains("new_balance"))
            {
                var balance = entity.GetAttributeValue<Money>("new_balance")?.Value ?? 0;
                tracingService.Trace($"Balance updated to: {balance}");

                // 检查信用额度
                CheckCreditLimit(entity, tracingService, serviceProvider);
            }
        }

        /// <summary>
        /// 处理账户删除
        /// </summary>
        private void OnDelete(Entity entity, ITracingService tracingService, IServiceProvider serviceProvider)
        {
            tracingService.Trace("Handling Delete message for Account entity");

            var accountId = entity.Id;
            tracingService.Trace($"Deleting account: {accountId}");

            // 获取插件上下文
            var context = (IPluginExecutionContext)serviceProvider.GetService(typeof(IPluginExecutionContext));

            // 在实际删除前检查关联数据
            var serviceFactory = (IOrganizationServiceFactory)serviceProvider.GetService(typeof(IOrganizationServiceFactory));
            var service = serviceFactory.CreateOrganizationService(context);

            // 检查是否有未结交易
            if (HasPendingTransactions(accountId, service, tracingService))
            {
                throw new InvalidPluginExecutionException("账户有未结交易，无法删除");
            }
        }

        /// <summary>
        /// 生成账户编号
        /// </summary>
        private string GenerateAccountNumber(ITracingService tracingService)
        {
            // 生成格式: ACC + 年月日 + 4位随机数
            var datePart = DateTime.Now.ToString("yyyyMMdd");
            var randomPart = new Random().Next(1000, 9999);
            var accountNumber = $"ACC{datePart}{randomPart}";

            tracingService.Trace($"Generated account number: {accountNumber}");
            return accountNumber;
        }

        /// <summary>
        /// 处理账户关闭
        /// </summary>
        private void HandleAccountClosure(Entity entity, ITracingService tracingService, IServiceProvider serviceProvider)
        {
            tracingService.Trace("Handling account closure");

            // 检查余额是否为零
            var serviceFactory = (IOrganizationServiceFactory)serviceProvider.GetService(typeof(IOrganizationServiceFactory));
            var service = serviceFactory.CreateOrganizationService(null);

            var account = service.Retrieve(
                entity.LogicalName,
                entity.Id,
                new Microsoft.Xrm.Sdk.Query.ColumnSet("new_balance", "new_creditlimit")
            );

            var balance = account.GetAttributeValue<Money>("new_balance")?.Value ?? 0;

            if (balance > 0)
            {
                tracingService.Trace($"Warning: Closing account with balance: {balance}");
                // 在实际应用中，可能需要额外的确认或处理
            }
        }

        /// <summary>
        /// 检查信用额度
        /// </summary>
        private void CheckCreditLimit(Entity entity, ITracingService tracingService, IServiceProvider serviceProvider)
        {
            tracingService.Trace("Checking credit limit");

            var serviceFactory = (IOrganizationServiceFactory)serviceProvider.GetService(typeof(IOrganizationServiceFactory));
            var service = serviceFactory.CreateOrganizationService(null);

            var account = service.Retrieve(
                entity.LogicalName,
                entity.Id,
                new Microsoft.Xrm.Sdk.Query.ColumnSet("new_balance", "new_creditlimit")
            );

            var balance = account.GetAttributeValue<Money>("new_balance")?.Value ?? 0;
            var creditLimit = account.GetAttributeValue<Money>("new_creditlimit")?.Value ?? 0;

            if (balance > creditLimit)
            {
                tracingService.Trace($"Warning: Balance ({balance}) exceeds credit limit ({creditLimit})");
                // 可以设置一个警告字段或发送通知
            }
        }

        /// <summary>
        /// 检查是否有未结交易
        /// </summary>
        private bool HasPendingTransactions(Guid accountId, IOrganizationService service, ITracingService tracingService)
        {
            tracingService.Trace($"Checking pending transactions for account: {accountId}");

            // 实现检查逻辑
            // 这里简化处理，实际应用需要查询交易表

            return false;
        }
    }
}
