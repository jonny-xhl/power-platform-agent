"""Phase 8 plugin-package smoke project definition.

Naming follows the project-wide rule ``{company}.{project}.{kind}.{Module}``:
``PP.Crm.Plugin.Smoke`` (dynamic per project — override company/project here for other projects).
Built + deployed via the NuGet PluginPackage path (net471, no ILMerge/sign).
"""
from framework_power.components.models import DeployMode, PluginProject, PluginStep

PROJECT = PluginProject(
    module="Smoke",
    company="PP",
    project="Crm",
    kind="Plugin",
    target_framework="net462",
    deploy_mode=DeployMode.Package,  # NuGet PluginPackage (preferred)
    version="1.0.0.0",
    steps=[
        PluginStep(
            name="new_fpformsmoke.Smoke.Update.PostOp",
            message="Update",
            entity="new_fpformsmoke",
            stage=40,           # PostOperation
            mode=0,             # synchronous
            filtering_attributes="new_category",
        ),
    ],
)
