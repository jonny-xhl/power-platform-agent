---
name: dv-plugin-python
description: 用 framework_power（Python 优先）构建 .NET plugin 程序集（NuGet PluginPackage 优先，net48+ILMerge+签名降级）并注册到 Dataverse（自动建 assembly + step、best-effort custom action、加进解决方案），按 {公司}.{项目}.{Plugin|Action}.{模块} 动态命名。当用户需要"注册 plugin"、"plugin step"、"custom action"、"plugin package/nuget"、"ILMerge 签名"、"framework_power plugin deploy/build/reverse"时使用。
---

# Dataverse Plugin 操作（Python 优先 / framework_power）

本技能是 **framework_power** 的 **plugin** 入口（Phase 8）。Plugin = 程序集 + SDK message step + custom action。

## 核心事实（已 live 钉死）

- **首选 NuGet `PluginPackage`**：`dotnet pack` 出 `.nupkg` → `POST pluginpackages`。**免 ILMerge、免签名**，依赖打进包。
  ⚠️ **包名必须含发布商前缀** `new_<assembly>`（否则 `0x80040265 does not contain a solution prefix`）。
  ⚠️ **TFM 强制限定（build 时校验）**：本环境 plugin 包运行时**只收 .NET Framework `net462`/`net471`**（`net462` 是标准/默认）；
  assembly 降级路径收 `net462`/`net471`/`net48`。**`net6`/`net8`/`netstandard` 一律拒绝**——`build_plugin_project` 在 build 时
  直接抛清晰错误，不到 Dataverse 才失败。
  Dataverse **自动建 pluginassembly**（按包内 assembly 名 resolve）。
- **降级 `pluginassembly`**：net48 + 自己签名 + ILRepack 合并依赖 → `POST pluginassemblies`（base64 DLL）。仅当包路径不可用。

## 命名（动态 per-project）

`{company}.{project}.{Plugin|Action}.{Module}`（`PluginProject.assembly_name`，模块 PascalCase）。
`company`/`project` 默认 `PP`/`Crm`，**每个项目可在 `plugin_def.py` 覆盖**。assembly/namespace/package-id 用它；
**pluginpackage.name 再加前缀** `new_{assembly}`。publisher 前缀 `new_` 不变。

## 工作流

```bash
# 1. 写 .NET 工程（net462, IPlugin）+ plugin_def.py（导出 PROJECT = PluginProject(...)）
# 2. 构建并部署（NuGet 包优先）
python -m framework_power plugin deploy ninebot-project/plugins/<dir> ninebot-project/plugins/<dir>/plugin_def.py --env dev [--plugin-solution new_PluginSoln]
# 只构建预览（离线）
python -m framework_power plugin build  ninebot-project/plugins/<dir> ninebot-project/plugins/<dir>/plugin_def.py
# 列环境里的 plugin / 反向
python -m framework_power plugin list --env dev
python -m framework_power plugin reverse <assembly-name> --env dev
```

`plugin_def.py` 示例：
```python
from framework_power.components.models import DeployMode, PluginProject, PluginStep

PROJECT = PluginProject(
    module="Smoke", company="PP", project="Crm", kind="Plugin",
    target_framework="net462", deploy_mode=DeployMode.Package, version="1.0.0.0",
    steps=[PluginStep(name="new_x.Smoke.Update.PostOp", message="Update",
                      entity="new_x", stage=40, filtering_attributes="new_category")],
)
```

## Step 注册（关键，别踩 Phase 2 的坑）

step **引用 PluginType（`eventhandler_plugintype@odata.bind`），不是 assembly**——`sdkmessageprocessingstep` 没有
`_pluginassemblyid_value`！正确 payload：`name` + `sdkmessageid@odata.bind` + **`eventhandler_plugintype@odata.bind`**
+ 实体限定 `sdkmessagefilterid@odata.bind` + stage/mode/rank/filteringattributes。工具自动：resolve PluginType（按
assembly）→ sdkmessage（按 message 名）→ sdkmessagefilter（按 message+entity，缺则 create）→ 建 step。
`PluginStep.plugin_type` 指定类名（多插件工程必填；单插件留空）。
⚠️ **目标实体必须先存在**：注册实体级 step 前，工具先 `client.entity_exists(step.entity)` 预检——实体不在环境里就
**直接 fail**（清晰报错 "target entity '...' not found; deploy the table first"），而不是让 Dataverse 在
`sdkmessagefilters` 查询里抛晦涩的 `0x80041102 "entity not found in MetadataCache"` 400。故 step 的目标表得先 deploy。

## 解决方案

组件码 `91=PluginAssembly`、`92=Step`（90 是 PluginType）、**`10030=PluginPackage`**。
**包插件加进命名解决方案：加 `PluginPackage(10030)`，不是 assembly(91)**——assembly 是 package 的一部分，
`AddSolutionComponent(91, asm)` 报 **405 "export the Package directly"**；加 10030（封装 assembly+plugintypes+steps）。
故 deploy 对包插件的 `add_targets` = `[(10030, package_id), (92, step_id)…]`；assembly 路径 = `[(91, asm_id), (92, step_id)…]`。
**step 注册幂等**：deploy 先查已有 step 名，同名 skip（`exists`），重 deploy 不产重复。

## Custom Action（best-effort）

`customise` 时工具尝试 `POST workflows`(category=3) 自动建 Action 定义 + 注册引用其 message 的 step；Web API 单独
建可调用 Action 不可靠 → 失败回退 `manual_update_required`（maker 门户建好 Action 再 redeploy 注册 step）。

## .NET 工程注意

- `net462`（标准）或 `net471`：**不要** `<Nullable>enable</Nullable>` / `<ImplicitUsings>enable</ImplicitUsings>`（C# 7.3）。
- **命名完全由 `plugin_def.py` 的 `PluginProject` 驱动**：build 传 `-p:AssemblyName` + `-p:PackageId` 覆盖
  .csproj 里的值 → **.csproj 的 `<AssemblyName>`/`<PackageId>` 会被忽略**（不同项目只改 config，不用动 .csproj）。
  （`<AssemblyName>` 写不写都行；namespace 在 .cs 里随便。）
- `PackageReference Microsoft.CrmSdk.CoreAssemblies`（IPlugin）。
- build 前**清 bin/obj**（工具自动）——TFM 改动留 stale 输出会让 pack 打错 `lib/<tfm>/`。

## 不要做

- **不要**用 net6/net8 目标（本环境包运行时只收 net462/net471）。
- **不要**让包名不含 `new_` 前缀（被拒）。
- **不要**在 step payload 用 `pluginassemblyid`/`eventhandler`/`plugintypeid` 作 nav prop（全 404）；只用 `eventhandler_plugintype@odata.bind`。
- `True`/`False`（Python），不要 `true`/`false`。
