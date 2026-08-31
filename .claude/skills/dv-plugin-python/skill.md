---
name: dv-plugin-python
description: 用 framework_power（Python 优先）构建 .NET plugin 程序集（NuGet PluginPackage 优先，net48+ILMerge+签名降级）并注册到 Dataverse（自动建 assembly + step + Pre/Post Image、custom action 全链路（创建+激活+Invoke step）、加进解决方案），按 {公司}.{项目}.{Plugin|Action}.{模块} 动态命名。当用户需要"注册 plugin"、"plugin step"、"step image / PreImage / PostImage"、"custom action"、"plugin package/nuget"、"ILMerge 签名"、"framework_power plugin deploy/build/reverse"时使用。
---

# Dataverse Plugin 操作（Python 优先 / framework_power）

本技能是 **framework_power** 的 **plugin** 入口（Phase 8）。Plugin = 程序集 + SDK message step + step image + custom action。

## 改环境前必先备份（ADR-013 强制）

任何 plugin 写操作（deploy / 更新 content / 删 step / 清孤儿 / 注册 action）**之前**：

```bash
python -m framework_power --workspace ninebot-project env-guard backup <解决方案名> --env dev \
  --note "本次意图（如：RF 插件部署）"
```

一条命令完成：solution ZIP（`workspace/docs/env_backup/{解决方案名}.zip`，历史自动轮转）+ **org 级插件注册
快照 JSON**（org 级注册的 step/plugintype 不进 solution 导出——正是 2026-08-19 误删事故的恢复盲区）+ 台账
一条记录。**恢复时先读台账** `docs/env_backup/CHANGELOG.md`（`pp env-guard log`）。仅快照：
`pp env-guard snapshot [--assemblies a,b]`。详见 `docs/spec/adr-013-env-backup-and-change-journal.md`。

## 核心事实（已 live 钉死）

- **首选 NuGet `PluginPackage`**：`dotnet pack` 出 `.nupkg` → `POST pluginpackages`。**免 ILMerge、免签名**，依赖打进包。
  ⚠️ **包名必须含发布商前缀** `new_<assembly>`（否则 `0x80040265 does not contain a solution prefix`）。
  ⚠️ **TFM 强制限定（build 时校验）**：本环境 plugin 包运行时**只收 .NET Framework `net462`/`net471`**（`net462` 是标准/默认）；
  assembly 降级路径收 `net462`/`net471`/`net48`。**`net6`/`net8`/`netstandard` 一律拒绝**——`build_plugin_project` 在 build 时
  直接抛清晰错误，不到 Dataverse 才失败。
  Dataverse **自动建 pluginassembly**（按包内 assembly 名 resolve）。
- **降级 `pluginassembly`**：net48 + 自己签名 + ILRepack 合并依赖 → `POST pluginassemblies`（base64 DLL）。仅当包路径不可用。
  **遗留 .NET 4.6.2 + ILMerge 产物**（如 RollingForecast）：不走 `plugin_build.py`，直接消费 ILMerge 产物 + 注册清单
  （参考 `ninebot-project/plugins/RollingForecast/deploy.py`）。

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

`plugin_def.py` 示例（含 image + custom action）：
```python
from framework_power.components.models import (CustomAction, DeployMode, Label,
                                               PluginProject, PluginStep, StepImage)

PROJECT = PluginProject(
    module="Smoke", company="PP", project="Crm", kind="Plugin",
    target_framework="net462", deploy_mode=DeployMode.Package, version="1.0.0.0",
    steps=[
        PluginStep(name="PP.Crm.Plugin.Smoke.SmokePlugin: Update of new_x",
                   message="Update", entity="new_x", stage=40, mode=1,
                   filtering_attributes="new_category", plugin_type="PP.Crm.Plugin.Smoke.SmokePlugin",
                   images=(  # Pre/Post Image（插件代码经 context.Pre/PostEntityImages[alias] 读取）
                       StepImage(alias="PreImage", image_type="Pre", attributes="new_name,new_status"),
                       StepImage(alias="PostImage", image_type="Post", attributes=""),
                   )),
    ],
    custom_actions=[
        CustomAction(schema_name="new_Interface_SmokeAction",
                     display_name=Label.bilingual("烟测动作", "Smoke Action"),
                     entity=None,  # None = 全局 action
                     xaml=XAML_TEMPLATE,        # x:Members 声明 jsondata(In)/msg(Out) 参数
                     plugin_type="PP.Crm.Action.Smoke.SmokeActionPlugin"),
    ],
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

### Step Image（Pre/Post Image，ADR-012）

`StepImage(alias, image_type="Pre"|"Post", attributes=...)` 挂在 `PluginStep.images`。契约（已 live 钉死）：

- **字段名是 `attributes`**（不是 SDK 文档常写的 `attributes1`）；空串/`"*"` = 快照全部属性（payload 省略该字段）。
- **`messagepropertyname` 随消息变化（头号坑）**：**`Create` → `Id`**（`Target` 在 Create 消息被 `0x8004416b` 拒绝：
  "Message property name 'Target' is not valid on message Create"）；**`Update`/`Delete`/其它 → `Target`**。工具按
  step.message 自动选。
- `imagetype`：0=Pre、1=Post；payload 绑定 `sdkmessageprocessingstepid@odata.bind`。
- **幂等**：按 `entityalias` 查重；已存在 step 重 deploy 会**补挂缺失的 image（backfill）**。
- reverse 回读 images；codegen 往返输出 `StepImage(...)`。

## Custom Action（全链路，ADR-012，已 live 验证）

`CustomAction(schema_name=, display_name=, entity=None, xaml=, plugin_type=)`，部署链：

1. 按 **workflow `uniquename`** 查定义（⚠️ **uniquename 不带 publisher 前缀**：`new_Interface_X` → `Interface_X`；
   SDK message 名才带前缀；查重 type=1 定义优先于 type=2 激活副本）。
2. 不存在则 `POST workflows`（category=3 Action, type=1 Definition, scope=4 Org）：payload 带 **`xaml`**（`x:Members`
   声明 In/Out 参数，如 `jsondata`(In)/`msg`(Out)；模板可从在线既有 action 提取）；**不带** `triggeroncreate`/
   `triggeronupdate`（本环境 workflow 实体无这两个属性，带了 400）。XAML 存 `xaml` 字段（不是 `clientdata`；
   collection `$select=xaml` 返回空，须单实体 GET）。
3. **激活**（`statecode=1, statuscode=2`）——激活才生成 SDK message，action 才可调用。
4. 解析 SDK message（按带前缀的 schema_name）→ 注册 Invoke step（PRT 命名约定 `{typename}: {message} of any Entity`；
   幂等按 step 名查重——重复 deploy 不产重复 step）。
5. workflow 进解决方案 `add_targets`（**code 29**）。

失败路径仍回退 `manual_update_required`（如激活失败 → maker 门户处理后再 redeploy）。

## 程序集 content 更新的坑（ADR-012）

- **content 更换不重枚举 plugintype**：替换 `pluginassembly.content` 后 plugintype 列表**不刷新**，新增 IPlugin 类型
  无法绑 step → 工具在 `_resolve_plugintype` 解析失败时**自动 `POST plugintypes`** 补建（payload：typename/friendlyname/
  name + `pluginassemblyid@odata.bind`；**不带 `type` 字段**——本环境 plugintype 实体无该属性）。
- **版本号由 DLL AssemblyInfo 决定**：PATCH payload 的 version 不生效。
- **更新 content 前必须清孤儿**（0x8004418b 阻断）：引用"新 DLL 中已不存在类型"的 step 和残留 plugintype 记录会挡住
  assembly 更新——删除后才能替换。判定孤儿用元数据分段字符串匹配（.NET 元数据中 namespace 段与类名分开存储）。

## 解决方案

组件码 `91=PluginAssembly`、`92=Step`、`90=PluginType`、`10030=PluginPackage`、**`29=Workflow（custom action 定义）`**。
**包插件加进命名解决方案：加 `PluginPackage(10030)`，不是 assembly(91)**——assembly 是 package 的一部分，
`AddSolutionComponent(91, asm)` 报 **405 "export the Package directly"**；加 10030（封装 assembly+plugintypes+steps）。
故 deploy 对包插件的 `add_targets` = `[(10030, package_id), (92, step_id)…]`；assembly 路径 = `[(91, asm_id), (92, step_id)…]`；
custom action 再加 `[(29, workflow_id), (92, action_step_id)]`。
**step 注册幂等**：deploy 先查已有 step 名，同名 skip（`exists`），重 deploy 不产重复。

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
- **不要**给 Create 消息的 image 用 `messagepropertyname=Target`（用 `Id`；工具自动处理，手写 payload 时注意）。
- **不要**用 `attributes1` 字段名（live 字段是 `attributes`）。
- **不要**在 workflow create payload 带 `triggeroncreate`/`triggeronupdate`（本环境无此属性）。
- `True`/`False`（Python），不要 `true`/`false`。
