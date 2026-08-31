# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库中工作时提供指导。

## 项目描述

Power Platform Agent 是一个 **Python 优先的 Dataverse 元数据部署库**（`framework_power`，
CLI `pp`），用"类型化 Python 模型"作为元数据的单一事实来源（需求 → Python 定义 → sync
Dataverse）。核心能力：表/字段/关系、全局选项集、解决方案与全组件（webresource/form/view/
sitemap/plugin/ribbon/role）、App 菜单、环境备份守卫、跨阶段工作流编排。

> 2026-08-31：legacy `framework/`（YAML + MCP Server 链路）已整体移除——近期所有实践均走
> `framework_power` CLI，YAML/MCP 路径不再维护。历史决策见 `docs/spec/adr-*.md`。

## framework_power（本仓库唯一引擎）

`framework_power/` 是自包含包：类型化模型 + 序列化器 + Dataverse client（复用代码在
`framework_power/client/`）+ 各域 `*_sync.py` + 组件注册表。
分支：`feat/framework-power-metadata`。**包内开发指南详见 `framework_power/CLAUDE.md`。**

### Phase 1 — 表（已完成，已 live 验证）

- `Table`/`Column`/`Relationship`/`Label` 类型化模型；幂等 `deploy_table`（create + PATCH-sync 字段
  + create-only 关系，**非破坏**）+ 只读 `plan_table` + `reverse_table`（环境→本地全量快照）。
  deploy 末尾自动补齐**自动创建视图/窗体名的双语标签**（ADR-016：平台建表把 base 英文
  复制进 2052 标签位致中文用户看到英文名；按组织模板命名，只碰默认命名组件，幂等）。
- 定义文件 `ninebot-project/metadata_py/tables/<schema>.py`（每文件导出 `TABLE`）；**双向单文件**：逆向覆盖、正向同步，
  标准（无 `new_` 前缀）组件自动跳过 → 全量快照正向同步幂等且安全。
- **全局选项集引用自洽**（ADR-011）：Picklist 列声明 `optionset_name` 引用
  `ninebot-project/metadata_py/optionsets/<name>.py`（导出 `OPTIONSET: GlobalOptionSet`）；
  `pp deploy <table>` 依赖优先**先行同步**被引用选项集（create-only、幂等，带 `--solution`
  时加入同一解决方案 code 9），无本地定义时降级只读检查 + `optionsets_missing` 告警。
  独立管理：`pp optionset list|plan|deploy [--name] [--solution]`。
- CLI：`python -m framework_power list|show|lint|plan|deploy|deploy-all|reverse|delete [name] --env dev`。
- Skill：`dv-model-to-python`（Excel 设计→Python 定义）、`dv-reverse-metadata`（逆向）。

### Phase 2 — 解决方案管理（已完成，已 live 验证）

把同一思路扩展到 **Solution 容器 + 全部组件类型**：

- `Solution`/`Publisher`/`ComponentRef` 模型；`deploy_solution` **5 步流程**
  （发布商 → 解决方案 → 按依赖顺序部署组件 → 加入解决方案 → `PublishAllXml`）+ 只读 `plan_solution`
  + `reverse_solution`（环境→Solution 全量快照）+ `solution_to_python_source`（往返保真）。
- **双向单文件** `ninebot-project/metadata_py/solutions/<name>.py`（导出 `SOLUTION`）；`tables` 为名称引用（指向
  `ninebot-project/metadata_py/tables/`），其它组件内联。
- 组件类型经 `framework_power/components/` 注册表统一分发（`COMPONENT_TYPES`，各类型 serialize/deploy/
  plan/reverse/codegen/lint 统一接口）：

  | 类型 | 代码 | 部署语义 |
  |------|------|----------|
  | `table` | 1 | 复用 Phase 1 `deploy_table`（薄适配器，未重构） |
  | `optionset` | 9 | 全局选项集；选项 create-only，变更报 `manual_update_required` |
  | `webresource` | 61 | create 或 PATCH base64 `content` |
  | `form` | 60 | create 或 PATCH 不透明 `formxml` |
  | `view` | 26 | create 或 PATCH 不透明 `fetchxml`/`layoutxml` |
  | `plugin` | 91+92（包路径 10030） | assembly/package + steps + Pre/Post images；custom action 全链路（+29 workflow） |

  新增类型只需加一个 per-type 模块并注册，`solution_codegen`/`solution_reverse` 自动支持。
- **不透明负载**：FormXml/FetchXml/LayoutXml 与 DLL/WebResource 内容为字符串字段（库不生成/解析）；
  插件 DLL 由 `client/plugin_build.py`（dotnet→base64）生成。
- CLI：`python -m framework_power solution list|show|lint|plan|deploy|reverse|add-component|publish`。
- Skill：`dv-solution-python`。
- ZIP 导入导出（`ExportSolution`/`ImportSolution`）**本期暂缓** — 仅组件级管理。

### Phase 3 — 安全角色权限同步（已完成，已 live 验证）

为**已存在的安全角色**同步表级权限（right × depth），双向、按表范围逆向：

- **角色不在本项目创建**（环境手动建好）；`deploy_role` 给已存在角色 upsert 表权限
  （非破坏：只加/改定义中列出的权限）。缺失角色报错。
- `SecurityRole`/`TablePrivilege`/`AccessRight`/`PrivilegeDepth` 模型；定义文件
  `ninebot-project/metadata_py/roles/<name>.py`（导出 `ROLE`），双向单文件。
- 权限模型（已 live 验证，详见 `framework_power/CLAUDE.md §9.2`）：深度存于
  `roleprivilegescollection.privilegedepthmask` 位掩码（USER=1/BU=2/PARENT_CHILD=4/GLOBAL=8，
  **不是** `depth`）；privilege 按名 `prv<Right><SchemaName>` 寻址（无 `objecttypecode`），
  故**按表范围逆向** = 先解析表的 8 个 privilegeid 再用 `privilegeid` 服务端过滤。
- CLI：`python -m framework_power role list|show|lint|plan|deploy|reverse`（`reverse` 必填
  `--tables`）。Skill：`dv-role-python`。
- 角色也是**解决方案组件**：`Solution.roles` 为名称引用，`solution deploy` 把已存在角色
  加入解决方案（`ROLE_SOLUTION_CODE=20`）；权限同步走独立的 `role deploy`。

### Phase 4 — Web 资源目录同步（已完成，已 live 验证）

把**本地 web 资源目录**（尤其 JS）批量同步到 Dataverse + 精准发布 + 按前缀逆向，专为频繁更新设计：

- 本地目录即事实来源；命名 **`{prefix}_/{relpath}`**（如 `js/order/test.js` → `new_/js/order/test.js`，
  与环境现有资源布局一致）；`webresourcetype`（1-11）由扩展名推导（`.js`→3、`.css`→2、`.svg`→11…）。
- `sync` 非破坏 create/update base64 `content`（复用 Phase 2 `components/webresource`），默认同步后
  **精准 `PublishXml`**（只发布本次资源，秒级生效）—— 频繁改 JS 的关键；`--no-publish` 可关。
- `--solution NAME` 把资源加入解决方案（code 61，幂等）；`publish <name>` 按名解析 id 再精准发布。
- `reverse` env→本地：base64 解码写字节回 `<dir>/{relpath}`，默认只拉本发布商（`new_/`），
  `--name-prefix` 可收窄。collection 查询需显式 `$select` 才返回 `content`。
- CLI：`python -m framework_power webresource scan|plan|sync|reverse|publish`（根目录默认 `ninebot-project/webresources/`）。
- Skill：`dv-webresource-sync`。

### Phase 5 — 窗体操作（已完成，已 live 验证）

把窗体（SystemForm）从 Phase 2 的**不透明 formxml 字符串**升级为**结构化类型化模型**，
覆盖两种实际场景：基于现有窗体改布局/绑事件、纯新建窗体：

- `Form`/`FormTab`/`FormColumn`/`FormSection`/`FormRow`/`FormCell`/`FormControl`/`FormLabel`/
  `FormLibrary`/`FormEvent`/`FormEventHandler` 模型；`form_xml.py` 用 stdlib `ElementTree` 做
  `parse_formxml`(逆向)/`to_formxml`(正向)。**每个布局节点保留完整 `attrs` 字典** + 未建模
  `<form>` 子元素按 `<tabs>` 前后分两段原样保留 → 逆向→正向**无损往返**（已在真实 account
  主窗体 live 验证：含 7-tab 的复杂窗体字节级稳定）。
- **builder 编辑器**（copy-on-write）：`new_form`/`add_tab`/`add_section`/`add_field`(按 P1
  `Column` 类型选 classid)/`add_library`/`remove_library`/`add_event_handler`/`remove_event_handler`。
  AI 直接用类型化 Python 改窗体，无需手写 XML。
- **可编辑窗体类型**（环境 authoritative，已 live 钉死）：**Main=2、QuickView=6、QuickCreate=7、
  Card=11**（早期枚举把 QuickCreate/QuickView 写反过，已纠正）。只创作/编辑 Main/QuickCreate/
  QuickView；Dashboard/Mobile/Card 可逆向但 lint 告警。
- **事件绑定（核心）**：FormXml 有 `<InternalHandlers>`(系统，只读) 与 `<Handlers>`(自定义)；
  `add_event_handler` 只写 `<Handlers>`。`<Library name>`/`<Handler libraryName>` 都是 **web
  资源名**（`new_/js/...`）→ **绑事件前 JS 资源必须先存在**（Phase 4 sync）。`libraryUniqueId`/
  `handlerUniqueId` 是必填带括号 GUID（序列化时空值自动生成）；本环境**不用** `libraryUniqueIdRaw`。
- **发布按实体范围**：formxml 改动需 `PublishXml`，且范围是**实体**（`<entities><entity>{logical}
  </entity></entities>`），不是 form id、也不是 web 资源那种按 id。`form deploy` 默认对变更
  实体精准发布；`--no-publish` 可关。`publish_entity` 客户端方法。
- **非破坏 + 保真**：`plan`/`deploy` 在**结构化模型**上 diff（live 逆向成模型再比较）→ **逆向后
  未改动的窗体重新 deploy = `would_skip`/`skipped_unchanged`**，绝不用重新生成的 formxml 覆盖真实
  窗体。（细微差别：全新 builder 创作的窗体 attrs 为空、逆向的已填充，语义相同但模型不等 →
  重 deploy 是幂等 `would_update`，cell GUID 重生成，不影响语义。）
- CLI：`python -m framework_power form list|show|lint|plan|deploy|reverse`（`reverse <entity>` 写
  `ninebot-project/metadata_py/forms/{entity}__{name}.py`，每窗体一个文件导出 `FORM`）。Skill：`dv-form-python`。

### Phase 6 — 视图操作（已完成，已 live 验证）

把视图（SavedQuery）从 Phase 2 的**不透明 fetchxml/layoutxml 字符串**升级为**结构化类型化模型**，
覆盖：新建 Public 视图、改现有/自动创建视图（加列/排序/过滤）：

- `View`/`ViewColumn`/`ViewOrder`/`ViewCondition`/`ViewFilter`(递归 AND/OR)/`ViewLinkEntity` 模型；
  `view_xml.py` 用 stdlib `ElementTree` 做 `parse_view`(逆向)/`to_fetchxml`+`to_layoutxml`(正向)。
  视图有**两段配对 XML**（FetchXml 查询 + LayoutXml 网格），**1:1 配对**（列同时驱动 fetch `<attribute>`
  + layout `<cell>`）；每个节点保留完整 `attrs` → 逆向→正向**无损往返**（真实 new_fpformsmoke 视图 live
  验证：含 QuickFind 双过滤、`in` 多值 `<value>`、`eq-userid` 无值）。
- **builder 编辑器**（copy-on-write）：`new_view`/`add_column`/`remove_column`/`reorder_columns`/
  `add_order`/`set_filter`/`add_condition`(单值/多值)/`add_link_entity`。AI 用类型化 Python 改视图，不写 XML。
- **关键字段**：`primary_id`（layout `<row id>`，始终也是 fetch `<attribute>`）；`object_type_code`（layout
  `<grid object=>` 需要的**整数 ObjectTypeCode**，逆向捕获、新建用 `client.get_object_type_code` 查）。
- **querytype（环境钉死）**：Public=0(可创建+更新)、AdvancedFind=1/Associated=2/QuickFind=4/Lookup=64
  （每实体一个、仅更新）。`querytype` 是**同名视图消歧键**→查找带 querytype（同 form 的 type）。
- **发布按实体范围**：改 fetchxml/layoutxml 需 `PublishXml`，范围实体（同 form）。`view deploy` 默认对变更
  实体发布；`--no-publish` 关。
- **非破坏 + 保真**：`plan`/`deploy` 在结构化模型上 diff → 逆向未改的视图重 deploy = `would_skip`/
  `skipped_unchanged`，不重写真实视图。customness 按**实体**（自定义表的视图可编辑）。
- CLI：`python -m framework_power view list|show|lint|plan|deploy|reverse`（`reverse <entity>` 写
  `ninebot-project/metadata_py/views/{entity}__{name}.py`，每视图一个文件导出 `VIEW`）。Skill：`dv-view-python`。

### Phase 7 — Ribbon 定制（已完成，已 live 验证）

给窗体/视图/子网格/全局 ribbon 加自定义按钮、绑 JS command、控制显隐、多语言标签、隐藏/覆盖 OOB 按钮。
**Ribbon 与窗体/视图本质不同：没有 Web API 直写**，只能 `ExportSolution → 改 customizations.xml 的
<RibbonDiffXml> → ImportSolution`（Web API 只能读：`RetrieveEntityRibbon`/`RetrieveApplicationRibbon`）。
故 Phase 7 **解除 Phase 2 的 ZIP 导入导出暂缓**作为 ribbon 的部署基础。

- `RibbonDefinition`/`RibbonButton`/`RibbonCommand`/`RibbonCommandOverride`/`RibbonDisplayRule`/`RibbonEnableRule`/
  `RibbonCustomRule`/`RibbonHideOob`/`RibbonLocLabel`/`RibbonScope`(Form/HomepageGrid/SubGrid/Application) 模型；
  `ribbon_xml.py` 做 `to_ribbondiff`(正向)/`parse_ribbondiff`(逆向)。builder `add_button`(自动接 show_fn/enable_fn
  → `<CustomRule>` 显隐)/`hide_oob`(无条件隐藏,默认 command_override 可逆)/`customise_command`(OOB「Customise Command」,
  保留原规则+加 CustomRule 做条件显隐,fail-OPEN)/`add_command`/`add_loclabel`。
- **专用小型 ribbon 解决方案 + 定向发布**（默认 `new_RibbonSoln`）：避开 Ribbon Workbench 的整包重导入
  （慢 + 提示备份）。`solution_zip.py` 做 customizations.xml 的 RibbonDiffXml 注入/提取（只替换该 region，
  窗体/视图字节级保留）；client `export_solution`/`import_solution`/`publish_application_ribbon`。
- **显隐统一用 `<CustomRule>`，且官方只归 `<EnableRule>`**（已按 MS Learn 修正）：`define-ribbon-display-rules`
  列的 21 种 DisplayRule 类型不含 CustomRule，RW 严格按 schema → DisplayRule 里的 CustomRule 不显示成 step；
  enable-rules 文档明说 "command bar 里 disabled 即 hidden" → `add_button`/`customise_command` 的 `show_fn`/`enable_fn`
  **都生成 `<EnableRule>`+`<CustomRule>`**。Default 非对称：自定义按钮 `false`(fail-closed)、OOB customise `true`(fail-OPEN)；
  **多语言** `<LocLabels>` (1033+2052)；**隐藏 OOB** 默认 `command_override`（覆盖 `<CommandDefinition>` + 互斥
  `Mscrm.HideOnModern`/`Mscrm.ShowOnlyOnModern`，可逆）。
- **已 live 踩坑**：customizations.xml 实体块 `<Name>` 是 **SchemaName**（如 `new_FpFormSmoke`）不是逻辑名
  → 注入按 SchemaName 匹配（`get_entity_metadata` 查）；`<RibbonDiffXml>` 默认含
  `<Templates><RibbonTemplates Id="Mscrm.Templates"/></Templates>`；**Location 必须是真实 group +
  `.Controls._children`**（`Mscrm.{scope}.{entity}.{group}.Controls._children`，默认 group Form→`MainTab.Save`/
  grid→`MainTab.Management`/app→`GlobalTab.New`；自造 group 会让按钮成孤儿不渲染——这是"按钮部署成功却看不到"的头号坑）；
  **专用解决方案只含实体 shell**（`DoNotIncludeSubcomponents=true`，否则拖入全部窗体/视图 → Ribbon Workbench
  拒绝加载 + 变慢）；**经典 ribbon 按钮不在 maker 门户"命令"设计器**（看运行时）。详见 `framework_power/CLAUDE.md §9.6`。
- CLI：`python -m framework_power ribbon build|show|lint|plan|deploy|reverse`（全局 `--ribbon-solution
  new_RibbonSoln`、`--ribbons-dir`）。Skill：`dv-ribbon-python`。

### Phase 8 — Plugin 操作（已完成，核心已 live 验证；image/action 全链路 ADR-012 已 live 验证）

构建 .NET plugin（**NuGet `PluginPackage` 优先**，net48+ILMerge+签名降级）+ 自动注册 assembly/step（**含 Pre/Post
Image**）+ **custom action 全链路**（workflow 创建 + XAML + 激活 + Invoke step）+ 加进解决方案。Phase 2 只有
「不透明 pluginassembly 上传」（step 注册从未 live 测，全是错的）。

- `Plugin`/`PluginProject`/`PluginStep`/`StepImage`/`CustomAction`/`DeployMode`/`ContentKind` 模型；
  `client/plugin_build.py` `build_plugin_project`（`dotnet build`+`pack`→base64 .nupkg，按 TFM 选 Package/Assembly，
  build 前清 bin/obj）；`plugin_sync.py`（`deploy_plugin`/`list_plugins`/`reverse_plugin`）。
- **已 live 踩坑**（详见 `framework_power/CLAUDE.md §9.7`）：pluginpackage 包名**必须含发布商前缀** `new_<assembly>`
  （`0x80040265`）；本环境 TFM**强制 net462 标准**（net471 也收；net6/net8/netstandard build 时直接拒），免 ILMerge/签名；step **引用 PluginType 不是
  assembly**——nav prop 只认 `eventhandler_plugintype@odata.bind`（`pluginassemblyid`/`eventhandler`/`plugintypeid` 全 404），
  实体限定走 `sdkmessagefilterid`；组件码 `90=PluginType`/`91=PluginAssembly`/`92=Step`/`10030=PluginPackage`/`29=Workflow`；
  **包插件加进命名解决方案要加 `PluginPackage(10030)`（assembly 91 报 405 "export the Package directly"），不是 assembly**；
  step 注册幂等（按名 skip existing + 既有 step 补挂 image）；命名 `{company}.{project}.{Plugin|Action}.{Module}` 动态 per-project
  （默认 `PP.Crm`）。
- **ADR-012（2026-08 live 钉死，RollingForecast 18 step + 19 image + 4 action 全量验证）**：Step Image 字段名是
  `attributes`（非 `attributes1`）、`messagepropertyname` 随消息（**Create→`Id`**，Update/Delete→`Target`）；custom action
  workflow `uniquename` 不带前缀、XAML 存 `xaml` 字段、**激活才生成 SDK message**、action step 命名 `{typename}: {message}
  of any Entity`；**content 更新不重枚举 plugintype**（解析失败自动补建，不带 `type` 字段）；更新 content 前须清孤儿
  step/plugintype（`0x8004418b`）。详见 `ninebot-project/docs/spec/adr-012-plugin-image-and-custom-action-deploy.md`。
- CLI：`python -m framework_power plugin build|deploy|list|reverse`（`--plugin-solution new_PluginSoln`）。Skill：`dv-plugin-python`。

### Phase 9 — 开发工作流编排（已完成，离线验证 + 待 live）

把 Phase 1–8 的孤立 deploy 命令串成**一条按依赖顺序的开发链**，由**一个显式清单**驱动，跨
**两个解决方案**（一条命令部署全部）：

- **链路（用户确认的最长链路）**：`Global Optionset → Entity(+Relationship) → webresource → plugin →
  form → view → [roles] → ribbon`。**ribbon 单独专用解决方案**（无 Web API 直写，走 export/import）；
  **其它全部装进主解决方案**。两者必须不同名（lint 强制）。
- **编排器零手动加组件**：每个 deploy/sync 函数都收 `solution=` **自管归属**——编排器只负责
  ① ensure 两个 solution 外壳（含 publisher）② 按链序跑各阶段 ③ 最终 `PublishAllXml`（optionset/table
  元数据靠它生效）。为此 Phase 9 做了三处**加法式**改动：`deploy_table`/`deploy_role` 加 `solution=None`
  形参（默认 None=旧行为不变）；新增 `optionset_sync.py`（optionset 此前是唯一没有 `*_sync.py` 的组件类型）。
- **显式清单 `ninebot-project/metadata_py/project.py`**（导出 `PROJECT = Project(...)`）：`main_solution`/`ribbon_solution`/
  `publisher`/`version` + 各阶段组件列表。列表是 **stems**（按 `<dir>/<stem>.py` 解析）；`tables`/`roles`
  是名称引用（走 registry）；`plugins` 是工程目录；`webresources` 是 bool。**某阶段没配内容则自动跳过**。
- **阶段过滤**：`--only a,b` / `--skip a,b`（取值：optionsets/tables/webresources/plugins/forms/views/roles/
  ribbon）；`--include-roles`（角色阶段默认关，opt-in）；`--no-publish`。
- CLI：`python -m framework_power workflow show|lint|plan|deploy`（`--project ninebot-project/metadata_py/project.py`）。
  Skill：`dv-workflow-python`。

### Phase 10 — App SiteMap 实体菜单管理（已完成，已 live 验证）

把新表加进模型驱动 App 的菜单（区域 → 组 → SubArea），新表上线闭环（建表 → 视图/窗体 →
**app 菜单** → 数据字典）的最后一块。**live 钉死：app-aware sitemap 模型**——`appmodule`
无 `sitemapxml` 列，导航 XML 在独立 `sitemap` 实体，键 `sitemapnameunique ==
appmodule.uniquename`（如 app `new_CustomerService`）。详见 ADR-015 与
`framework_power/CLAUDE.md §9.11`。

- 结构化模型 `AppSitemap → SiteArea → SiteGroup → SubArea`（attrs/extras 全保留 → 无损往返，
  同 form/view 契约）；组件 registry key=`sitemap`（**code 62**，部署序 view 后）。
- **部署** = `PATCH sitemaps({id}) {sitemapxml}` + 发布（定向 `PublishXml(<sitemaps>)` 本环境
  400 → 回退 `PublishAllXml`）；新增 SubArea **样式克隆**既有实体条目；幂等（已有 →
  `skipped_unchanged`，lint 对重复实体报 error）；写前自动备份原始 XML 到
  `docs/env_backup/sitemap_{unique}.{ts}.bak.xml`（ADR-013 对齐）。
- **解决方案**：sitemap 已在解决方案内（`new_entity930` 含 Customer Service 的 sitemap）则
  PATCH 后随其 transport，**不要再 add-component**；sitemap 承载整个 app 导航。
- CLI：`python -m framework_power sitemap apps|show|plan|add-entity|remove-entity`
  （`--app` 接 uniquename/显示名，`--area/--group` 接 Id 或中/英标题）。Skill：`dv-sitemap-python`。

### 关键约束

- **【强制守则 ADR-013：改环境前必先备份 + 全程留台账】任何对 Dataverse 环境的写操作
  （deploy/update/delete/清理/注册）之前，必须先执行 `python -m framework_power --workspace
  ninebot-project env-guard backup <解决方案名> --env dev --note "意图"`（备份 ZIP 到
  `workspace/docs/env_backup/{解决方案名}.zip` + org 级插件注册快照 JSON），操作后用
  `env-guard log` 核对台账。恢复时**先读台账** `docs/env_backup/CHANGELOG.md` 再动手。
  动机：2026-08-19 误删 13 step + 11 plugintype 后无任何可查备份/记录。详见
  `docs/spec/adr-013-env-backup-and-change-journal.md`。
- **【文档同步守则：引擎代码变更必须同步文档】任何对引擎代码（`framework_power/**`、
  `.claude/skills/**` 脚本）的行为性变更——新能力、新 API/CLI 命令、
  payload 语法、错误码语义、已踩坑行为——当次任务内必须同步更新对应文档，不等下次：
  ① 新决策/行为 → 新 ADR（`docs/spec/adr-0XX-*.md`）或增补现有 ADR；② 架构 →
  `docs/spec/architecture.md`；③ 作者契约 → `docs/spec/metadata-spec.md`；④ 部署语义 →
  `docs/guides/metadata-deploy.md`；⑤ 使用说明 → 对应 `.claude/skills/*/skill.md`；
  ⑥ 概览 → 根 `CLAUDE.md` / `framework_power/CLAUDE.md`（§9 踩坑清单）；⑦ README。
  Git hook（`scripts/hooks/pre-commit.sh`，`bash scripts/install_hooks.sh` 安装）只做
  **建议**级提醒，不构成豁免；未同步文档的引擎变更视为任务未完成。
- 认证复用 `ninebot-project/config/environments.yaml` + `.env`（`get_client`，client-secret + MSAL）。
- `deploy` **非破坏**（create/update/add）；标准（非 `new_` 前缀）组件正向同步**跳过** → 全量快照安全。
- 布尔用 `True`/`False`；mypy 严格；`flake8 --max-line-length=120`；mypy 需 `--explicit-package-bases`（仓库根有遗留 `__init__.py`）。
- **已 live 踩坑**（详见 `framework_power/CLAUDE.md §9`）：全局选项集按**小写** `Name` 键查询（禁
  `$filter`/405）；解决方案组件走 `solutioncomponents` 实体集（导航属性 404/400）；部署返回 id 避免
  create→resolve 竞争；`PublishAllXml` 组织级（发布全部未托管自定义项）。

## 编程语言要求

- **主要语言**：Python 3.9+（引擎、CLI、工具链）
- **插件语言**：C# / .NET（Dataverse 插件开发，位于 `ninebot-project/plugins/` 目录）
- **配置语言**：YAML（workspace 清单、环境配置、命名规则）
- **类型注解**：Python 代码必须包含类型注解（`typing`），项目配置了 `mypy` 类型检查

## 规范要求

### Python 代码规范

- 使用 `black` 格式化，`flake8` 检查（最大行宽 120）
- 布尔值使用 Python 的 `True`/`False`，禁止使用 `true`/`false`（会导致运行时 NameError）

### 元数据命名与建模规范

- **【硬核要求】schema_name 必须严格遵循 `ninebot-project/config/naming_rules.yaml` 定义的命名规则**：
  - 风格：`lowercase`（小写 + 下划线分隔，本组织既有惯例；新表亦可用 PascalCase——lint 只告警不拦截）
  - 分隔符：`_`
  - 自定义组件自动添加前缀 `{prefix}`
  - 标准实体（account、contact 等）不受前缀规则保护，但组件级 schema_name 仍需遵循 lowercase 风格
  - **禁止使用驼峰命名**（如 `approveAccount`、`customerArea`），必须使用 `approve_account`、`customer_area`
  - 所有元数据定义的 schema_name 值必须符合此规范，包括：tables、forms、views、ribbon、sitemap、webresources 等

- 自定义实体 SchemaName 必须以发布商前缀 `ninebot-project/config/publishers.yaml->{prefix}` 开头
- 自定义关系的 SchemaName 也必须以 `ninebot-project/config/publishers.yaml->{prefix}` 开头
- Lookup 字段不能通过 Attributes 端点单独创建，必须通过 Deep Insert（`RelationshipDefinitions`）一次性创建关系 + Lookup
- 级联行为：每个实体只允许一个 Parental（`Active`）关系，自定义关系推荐使用 Referential 模式（`NoCascade` + `RemoveLink`）
- 定义是期望状态的声明，与 Dataverse 对比后执行 create/update/skip，不执行 delete
- 标准实体（account、contact、systemuser 等）受保护，命名转换时不会被修改（列表见 `ninebot-project/config/naming_rules.yaml` 的 `standard_entities`）

### 插件开发规范

- 插件位于 `ninebot-project/plugins/` 目录，使用 .NET SDK（`Microsoft.Xrm.Sdk`）
- 实现标准 `IPlugin` 接口，入口方法 `Execute(IServiceProvider)`
- 通过 `PluginAgent` 调用 `dotnet build` 构建，`DataverseClient` 部署
- Plugin Step 注册需指定：实体名、消息名（Create/Update/Delete）、阶段（pre-validation/pre-operation/post-operation）

## 常用命令

```bash
# 安装依赖 + 以可编辑模式安装（提供 pp / pp-agent CLI 命令）
pip install -r requirements.txt
pip install -e .
```

### 测试

```bash
# 运行全部测试
bash test/scripts/run_all_tests.sh

# 仅运行单元测试
bash test/scripts/run_unit_tests.sh

# 带覆盖率报告（HTML 报告在 test/reports/html/）
bash test/scripts/run_with_coverage.sh

# 运行单个测试文件
cd test && pytest unit/test_agents/test_core_agent.py

# 按标记运行测试
cd test && pytest -m unit
cd test && pytest -m "requires_auth"  # 需要 Dataverse 凭据
```

测试配置在 `test/pytest.ini`。标记：`unit`、`integration`、`slow`、`requires_auth`、`requires_dataverse`。

### 代码检查

```bash
# framework/（已于 2026-08-31 移除；如历史分支需要可回查 git log）

# framework_power/（Python 优先库；mypy 需 --explicit-package-bases，因仓库根有遗留 __init__.py）
flake8 framework_power/ --max-line-length=120
mypy framework_power --ignore-missing-imports --explicit-package-bases
cd test && python -m pytest unit/test_framework_power -o addopts="" -q   # 168 单元测试，离线、fake client
```

### Git Hooks

```bash
bash scripts/install_hooks.sh
```

Pre-commit hook 对引擎/技能变更给出**建议级**文档同步提醒（ADR/架构/契约/部署语义/skill/概览 六处自查）。

### 数据字典生成

```bash
python -m framework_power --workspace ninebot-project reverse <table> --env dev --dictionary
```

## 架构

本仓库是单引擎架构：`framework_power` Python 包（类型化模型 + 序列化 + Web API client + 各域 sync + 组件注册表）。

```
framework_power/
├── models.py / serializer.py          # P1 类型化模型 + Web API 序列化（表/字段/关系/标签）
├── client/dataverse_client.py         # MSAL 认证 + Dataverse REST/Web API（唯一 client）
├── deployer.py                        # deploy_table / plan_table（非破坏、幂等）
├── registry.py / runtime.py / workspace.py
├── components/                        # 组件注册表：table/optionset/webresource/form/view/
│                                      # sitemap/plugin/ribbon + models + compact(紧凑codegen)
├── *_sync.py                          # solution/optionset/webresource/form/view/ribbon/
│                                      # plugin/role/sitemap/label 各域 sync+plan+reverse
├── label_sync.py                      # ADR-016 自动视图/窗体名双语
├── data_dictionary.py                 # reverse --dictionary 数据字典生成
└── cli.py                             # pp CLI（lint/plan/deploy/reverse/…全子命令）
```

### 配置文件

所有配置在 `ninebot-project/config/` 目录：

| 文件 | 用途 |
|------|------|
| `environments.yaml` | Dataverse 环境 URL 和凭据（支持 `${ENV_VAR}` 变量展开） |
| `publishers.yaml` | 发布商配置 + 命名规则（schema name 风格、受保护实体列表、验证规则） |
| `pipeline.yaml` | CI/CD 流水线（分支→环境→部署策略） |
| `environment_settings.yaml` | 部署后环境变量与连接引用配置 |

### Dataverse API 关键模式

- **Lookup 字段**不能通过 `Attributes` 端点单独创建 — 必须通过 `RelationshipDefinitions` 端点使用 Deep Insert
- 自定义关系的 SchemaName 必须以发布商前缀（`new_`）开头
- 级联配置：`Active` = Parental（每个实体只允许一个），自定义关系推荐 `NoCascade`+`RemoveLink`
- 增量更新策略：Python 定义 = 期望状态 → 与 Dataverse 对比 → create/update/skip（不删除）

### 技能（Skills）

Claude Code 技能位于 `.claude/skills/`：
- `design-dv-model` — 生成 Dataverse 实体设计 Excel 模板
- `dv-overview` — Dataverse 元数据建模总览
- `dv-model-to-python` — Excel 设计 → `framework_power` Python 表定义（Phase 1）
- `dv-reverse-metadata` — 逆向导出表（环境 → Python，Phase 1）
- `dv-solution-python` — `framework_power` 解决方案管理（Phase 2）
- `dv-role-python` — `framework_power` 安全角色权限同步（Phase 3）
- `dv-webresource-sync` — `framework_power` web 资源目录同步/发布/逆向（Phase 4）
- `dv-form-python` — `framework_power` 窗体结构化建模（逆向/改布局/绑事件/新建，Phase 5）
- `dv-view-python` — `framework_power` 视图结构化建模（逆向/加列/排序/过滤/新建，Phase 6）
- `dv-ribbon-python` — `framework_power` ribbon 定制（加按钮/绑 JS/CustomRule 显隐/隐藏 OOB，Phase 7）
- `dv-plugin-python` — `framework_power` plugin 构建/注册（NuGet PluginPackage 优先，net462/net471，Phase 8）
- `dv-workflow-python` — `framework_power` 跨阶段开发工作流编排（project.py 清单驱动整条链，主 + ribbon 两个解决方案，Phase 9）
- `dv-sitemap-python` — `framework_power` App SiteMap 实体菜单管理（加表进 app 区域/组，app-aware sitemap 模型，Phase 10）

### CI

GitHub Actions 工作流在 `.github/workflows/test.yml`：在 Python 3.10/3.11/3.12 上运行 flake8 + pytest，覆盖率阈值 50%。
