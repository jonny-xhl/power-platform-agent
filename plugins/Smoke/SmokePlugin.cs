using System;
using Microsoft.Xrm.Sdk;

namespace PP.Crm.Plugin.Smoke
{
    /// <summary>
    /// Phase 8 plugin-package smoke plugin. Deployed via the NuGet PluginPackage path (net471, no ILMerge/sign).
    /// Registered as a step on new_fpformsmoke Update (PostOperation) — traces the message + record id.
    /// </summary>
    public class SmokePlugin : IPlugin
    {
        public void Execute(IServiceProvider serviceProvider)
        {
            var context = (IPluginExecutionContext)serviceProvider.GetService(typeof(IPluginExecutionContext));
            var tracing = (ITracingService)serviceProvider.GetService(typeof(ITracingService));
            tracing.Trace("Ninebot.Crm.Plugin.Smoke: " + context.MessageName + " on " + context.PrimaryEntityName
                          + " [" + context.PrimaryEntityId + "]");
        }
    }
}
