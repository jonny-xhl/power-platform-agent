# framework_power — 开发指南 (CLAUDE.md)

本文件为 Claude Code 在 `framework_power/` 包内工作时提供指导。它是该项目"Python 优先的 Dataverse
表元数据部署库"（取代已移除的 legacy `framework/` YAML 链路；2026-08-31 起本仓库唯一引擎，仅限**表**域：表 + 字段 + 关系）。

> 入口文档：根目录 `CLAUDE.md`；部署说明 `docs/metadata-deploy.md`；作者契约
> `docs/spec/metadata-spec.md`；相关 skill：`dv-model-to-python`、`dv-reverse-metadata`、
> `dataverse:dv-metadata`。

---

## 1. 是什么

`framework_power` 把一张表定义为一个**类型化的 Python 模型**（`Table`），模型即"单一事实来源"。
- **正向 `deploy`**：把 `Table` 同步到 Dataverse（create / PATCH-sync 字段 / create-only 关系；
  末尾自动补齐自动创建视图/窗体名的双语标签，ADR-016——平台建表会把 base 语言英文
  复制进 2052 标签位，中文用户看到英文名）。
- **逆向 `reverse`**：把环境中已存在的表导出为本地 Python 定义（全量快照），用于参考、对比、约束 AI。
- **单文件双向**：同一份 `metadata_py/tables/<schema>.py` 既可被逆向覆盖，也可被正向同步。

不使用 YAML，不使用官方 `PowerPlatform-DataverseClient-Python` SDK（无法更新元数据、类型覆盖不全）。
**无新依赖**（仅复用项目已有的 `requests` + `msal`）。

**Phase 2（解决方案）** 把同一思路扩展到 Solution 容器及其组件：`Solution` 模型 + 5 步
`deploy_solution`（发布商→解决方案→部署组件→加入解决方案→发布）+ `reverse_solution`（全量快照）+
单文件 `metadata_py/solutions/<name>.py`。组件类型经 `components/` 注册表统一分发：
`table`（复用 Phase 1）/ `optionset` / `webresource` / `form` / `view` / `plugin`，各自有
model + serializer + deployer + reverse + codegen + lint。`FormXml`/`FetchXml`/`LayoutXml` 与 DLL、
Web 资源内容均为**不透明字符串**（库不生成也不解析）。CLI 入口：`python -m framework_power solution ...`，
详见 `dv-solution-python` skill。

**Phase 4（web 资源目录同步）** 把**本地 web 资源目录**（尤其 JS）作为事实来源：`webresource_sync.py`
扫描目录 → create/update base64 `content`（复用 Phase 2 `components/webresource`）→ 默认**精准
`PublishXml`** 发布（频繁改 JS 秒级生效）→ 可 `--solution` 加入解决方案（code 61）→ 可按前缀 `reverse`
（env→本地解码写字节）。命名 `{prefix}_/{relpath}`，类型由扩展名推导。CLI：`python -m framework_power
webresource scan|plan|sync|reverse|publish`，详见 `dv-webresource-sync` skill 与 §9.3。

**Phase 5（窗体操作）** 把窗体（SystemForm）从 Phase 2 的**不透明 `form_xml` 字符串**升级为
**结构化类型化模型**：`form_xml.py`（stdlib `ElementTree`）做 `parse_formxml`(逆向)/`to_formxml`(正向)，
布局节点保留完整 `attrs` 字典 → 无损往返（真实 account 主窗体 live 验证）。builder 编辑器
（`new_form`/`add_field`/`add_library`/`add_event_handler`/...）让 AI 用类型化 Python 改布局/绑事件，
不用手写 XML。可编辑 Main/QuickCreate/QuickView（环境 authoritative：Main=2/QuickView=6/QuickCreate=7/
Card=11）。事件分 `<InternalHandlers>`(系统只读) / `<Handlers>`(自定义)，`libraryName`/`<Library name>`
= web 资源名（Phase 4 命名）→ 绑事件前资源须先存在。发布**按实体范围**（`publish_entity`）。非破坏：
diff 在结构化模型上做，逆向未改 → `would_skip`。CLI：`python -m framework_power form
list|show|lint|plan|deploy|reverse`，详见 `dv-form-python` skill 与 §9.4。

**Phase 6（视图操作）** 把视图（SavedQuery）从 Phase 2 的**不透明 fetchxml/layoutxml 字符串**升级为
**结构化类型化模型**：`view_xml.py`（stdlib `ElementTree`）做 `parse_view`(逆向)/`to_fetchxml`+`to_layoutxml`
(正向)。视图有**两段配对 XML**（FetchXml 查询 + LayoutXml 网格），**1:1 配对**（列同时驱动 fetch `<attribute>`
+ layout `<cell>`）；每个节点保留完整 `attrs` → 无损往返（真实 new_fpformsmoke 视图 live 验证：含 QuickFind
双过滤、`in` 多值、`eq-userid`）。builder（`new_view`/`add_column`/`add_order`/`add_condition`/`add_link_entity`/
...）。可创建 Public(0)；AdvancedFind(1)/Associated(2)/QuickFind(4)/Lookup(64) 仅更新。`querytype` 是同名视图
消歧键。layout `<grid object=>` 需要**整数 ObjectTypeCode**（`get_object_type_code` 查）。发布**按实体范围**。
非破坏：diff 在结构化模型上做，逆向未改 → `would_skip`。CLI：`python -m framework_power view
list|show|lint|plan|deploy|reverse`，详见 `dv-view-python` skill 与 §9.5。

**Phase 7（Ribbon 定制）**——ribbon **没有 Web API 直写**（只能读 `RetrieveEntityRibbon`/
`RetrieveApplicationRibbon`），必须 `ExportSolution → 改 customizations.xml 的 <RibbonDiffXml> → ImportSolution`
（同 Ribbon Workbench 的传输，但用**专用小型解决方案 + 定向 PublishXml** → 秒级、免备份提示，避开整包
重导入）。**解除 Phase 2 的 ZIP 导入导出暂缓**。`RibbonDefinition`(entity 或 Application) →
`RibbonButton`/`RibbonCommand`/`RibbonDisplayRule`/`RibbonEnableRule`/`RibbonCustomRule`/`RibbonHideOob`/
`RibbonLocLabel`/`RibbonScope`(Form/HomepageGrid/SubGrid/Application)；`ribbon_xml.py` 做 `to_ribbondiff`/
`parse_ribbondiff`；`solution_zip.py` 做 customizations.xml 的 RibbonDiffXml 注入/提取。显隐**统一用
`<CustomRule>`**（JS 返回 bool，fail-closed）；多语言 `<LocLabels>`；隐藏 OOB 默认 `command_override`
（可逆）。CLI：`python -m framework_power ribbon build|show|lint|plan|deploy|reverse`（全局
`--ribbon-solution new_RibbonSoln`），详见 `dv-ribbon-python` skill 与 §9.6。

**Phase 10（App SiteMap 实体菜单）**——把新表加进模型驱动 App 的菜单（区域 → 组 →
SubArea）。**live 钉死：app-aware sitemap 模型**（`appmodule` 无 `sitemapxml` 列；导航 XML
在独立 `sitemap` 实体，键 `sitemapnameunique == appmodule.uniquename`）。结构化模型
`AppSitemap → SiteArea → SiteGroup → SubArea`（attrs/extras 全保留，无损往返）+ 幂等
add/remove（样式克隆既有 SubArea）+ 写前自动备份 + 发布（定向 PublishXml 400 → 回退
PublishAllXml）。CLI：`python -m framework_power sitemap apps|show|plan|add-entity|
remove-entity`，详见 `dv-sitemap-python` skill 与 §9.11 / ADR-015。

## 2. 硬性约束（必须遵守）

- **【ADR-013 强制守则】任何环境写操作前先备份 + 留台账**：`pp env-guard backup <解决方案> --env <env>
  --note "意图"`（solution ZIP + 插件注册快照 + 台账一条龙）。恢复时先读 `docs/env_backup/CHANGELOG.md`。
- **【文档同步守则】引擎代码的行为性变更（新能力/API/CLI、payload 语法、错误码语义、踩坑结论）
  当次任务内必须同步文档**：新决策 → ADR；架构 → `docs/spec/architecture.md`；契约 →
  `metadata-spec.md`；部署语义 → `docs/guides/metadata-deploy.md`；技能 → `.claude/skills/*/skill.md`；
  踩坑 → 本文件 §9 + 根 `CLAUDE.md`。pre-commit hook（`scripts/hooks/pre-commit.sh`）只是建议级
  提醒，不豁免；漏更文档 = 任务未完成。
  详见 §9.10 与 `docs/spec/adr-013-env-backup-and-change-journal.md`。
- **自包含**：legacy `framework/` 已于 2026-08-31 移除，本包是唯一引擎；
  复用的传输/认证/配置/重试代码已**拷贝**到 `framework_power/client/`，在本包内维护。
- **发布商前缀**取自 `config/publishers.yaml`（默认 `new`）。自定义组件 = 带 `new_` 前缀；标准/系统
  组件（无前缀）在正向同步时**自动跳过**。
- **`deploy` 默认非破坏**：只 create/update，从不 delete（delete 需显式 `delete` 命令）。
- **布尔值用 Python `True`/`False`**，不要用 `true`/`false`。

## 3. 包结构

```
framework_power/
  __init__.py        公共 API 再导出（表 + 解决方案 + 组件枚举）
  __main__.py        支持 python -m framework_power ...
  models.py          类型化 dataclass：Table/Column/LookupColumn/Relationship/Label/Option/...
  serializer.py      模型 -> Dataverse Web API JSON（多语言、全类型）
  deployer.py        幂等 deploy_table / 只读 plan_table（前缀跳过、传播等待/重试）
  codegen.py         Table 对象 -> Python 定义源码（逆向输出/往返保真）；emit_label 供复用
  reverse.py         环境元数据 -> Table（全量快照）
  registry.py        发现 metadata_py/tables/*.py（每文件导出 TABLE）；deploy_order 拓扑排序
  lint.py            离线约定校验门（无网络，0 errors 才允许 plan/deploy）
  runtime.py         get_client(env) + argparse_env（复用 client-secret 认证）
  cli.py             表命令 + `solution` 子命令组 + --solutions-dir
  solution_deployer.py  幂等 deploy_solution（5 步：发布商→解决方案→部署组件→加入→发布）+ plan_solution
  solution_reverse.py   reverse_solution（环境 → Solution 全量快照，registry 驱动分发）
  solution_codegen.py   Solution → metadata_py/solutions/<name>.py（registry 驱动、往返保真）
  components/        解决方案组件类型（Phase 2）
    __init__.py        ComponentType + COMPONENT_TYPES 注册表 + table 适配器 + _register_module
    models.py          Solution/Publisher/ComponentRef + 全组件模型（GlobalOptionSet/WebResource/
                       Form/View/Plugin + 枚举）。Form 为结构化模型（Phase 5，见 §9.4）；
                       View 为结构化模型（Phase 6，见 §9.5）；base64 仍为不透明字符串
    serializer.py      serialize_publisher / serialize_solution（含 publisherid@odata.bind）
    _common.py         extract_label / is_custom 共享工具
    optionset.py / webresource.py / form.py / view.py / plugin.py
                       各类型统一接口（serialize/deploy/plan/reverse/codegen/exists/resolve_id/
                       lint + KEY/SOLUTION_CODE/MODEL_CLS/CODEGEN_IMPORTS），自动注册
    env_guard.py       环境变更守卫（ADR-013）：backup_solution（ZIP 轮转）+
                       snapshot_plugin_registrations（org 级插件注册 JSON 快照）+
                       append_change/read_journal（append-only 台账），见 §9.10
  client/            自包含 Web API client（原拷贝自 legacy framework/utils，已精简）
    dataverse_client.py  精简 DataverseClient（表元数据 + 各组件端点 + 解决方案/发布商/发布端点）
    plugin_build.py      dotnet build → base64（插件作者期工具，需 .NET SDK）
    auth.py              AutoAuthenticator（MSAL client-credentials + 缓存）
    env_config.py        load_env_file / expand_env_vars / load_yaml_with_env
    retry_helper.py      @retry_on_metadata_error（默认错误模式已扩展 dv-metadata 信号）
```

## 4. 数据模型（models.py，速查）

- `AttributeType` 枚举：`String / Integer / BigInt / Money / Decimal / Double / Picklist / Boolean /
  Memo / DateTime / File`。**Lookup 不在其中**——查找字段经 `Relationship`（Deep Insert）创建。
- `Label`：多语言，`Label.zh(text)` / `.en(text)` / `.bilingual(zh,en)` / `.parse(...)`；
  `2052`=zh-CN，`1033`=en-US。
- `Column`：非查找字段；`LookupColumn`：查找字段（随 Relationship 创建）。
- `Relationship`：1:N（带 `LookupColumn`）或 N:N；`CascadeConfig` 默认 Referential（`delete=RemoveLink`，
  其余 `NoCascade`，**禁止 `Cascade.Active`**——会触发 Parental 限制）。
- `Table`：`schema_name`（新表用 PascalCase + `new_` 前缀，原样透传不改写）。

## 5. 双向单文件契约（核心）

定义文件：`metadata_py/tables/<schema>.py`，每文件导出 `TABLE: Table`。
- **逆向 `reverse <name>`**：导出**全量快照**（自定义 + 标准字段/关系，过滤虚拟/主键/`*_base`/系统查找
  类型），覆盖写入该文件。
- **正向 `deploy <name>`**：读同一文件同步；**自动跳过标准（无 `new_` 前缀）项**，只创建/同步自定义项
  → 全量快照正向同步是**幂等且安全**的。

**紧凑 codegen（form/view 逆向文件，2026-08-31）**：`components/compact.py` 让逆向生成的
窗体/视图文件省略与模型字段完全重复的 `attrs` 键（仅当 attrs 键集**精确等于**序列化器回退
分支会重建的集合——control 回退无条件发 `datafieldname`，宽松规则会引入 `datafieldname=""`
这类字节差异）；体积约 -25%。**语义无损**：`form_sync`/`view_sync` 的 skip-if-unchanged diff
改用 `normalize()` 两边归一化后比较 → 紧凑文件 vs live 全量 attrs 仍 `would_skip`（幂等保持）。

## 6. CLI

```bash
python -m framework_power list                                   # 发现 metadata_py/tables/*.py
python -m framework_power show <name>                            # 打印序列化 payload（离线）
python -m framework_power lint [<name>]                          # 离线约定门（0 errors 必须）
python -m framework_power plan <name> --env dev                  # 只读预演（默认紧凑摘要）
python -m framework_power deploy <name> --env dev                # 正向同步（默认紧凑摘要）
python -m framework_power deploy-all --env dev                   # 按依赖顺序部署全部（紧凑摘要）
python -m framework_power reverse <name> --env dev               # 逆向导出（全量快照）
python -m framework_power delete <name> --env dev                # 删除表（破坏性；级联字段+关系）
python -m framework_power sitemap apps|show|plan|add-entity|remove-entity --env dev
                                                                  # App 菜单管理（Phase 10/ADR-015）
# 全局参数：--definitions-dir <dir>（默认 metadata_py/tables）
# plan/deploy/deploy-all：--json 打全量结果 JSON（默认紧凑摘要——action 计数 + changed 明细，
#   一眼可审计、token 友好；AI/脚本消费全量时用 --json）
```

认证：`get_client(env)` 复用 `config/environments.yaml` + `.env`（client-secret），MSAL
client-credentials，token 缓存于 `.pp-local/state/tokens.json`。

> **.env scope** (ADR-003): Dataverse 凭证放 `<workspace>/.env`（per-project），
> LLM API 密钥放 `~/.power-platform-agent/.env`（cross-project）。
> `load_env_file()` 自动按 workspace → user-level → CWD 回退链加载。

## 7. 工作流（需求 → 定义 → 同步）

```
需求 (docs/features/<feature>/01-prd)
  → design-dv-model → Excel 设计
  → dv-model-to-python → metadata_py/tables/<schema>.py     （AI 按契约生成）
  → framework_power lint          （离线门，0 errors）
  → framework_power plan          （只读预演）
  → framework_power deploy        （同步到环境）
逆向参考：framework_power reverse <name>   （环境 → 本地，供 AI/对比/约束）
```

## 8. 元数据作者约定（摘要，详见 docs/spec/metadata-spec.md）

- 新表 **PascalCase + `new_` 前缀**（`new_ProjectBudget`）；命名**作者负责、lint 校验、不改写**
  （与旧 YAML 路径的自动转换不同）。
- 每表有且仅有一个 `String` 主名称字段（`is_primary_name=True`）。
- 显示名/选项标签用 `Label.bilingual(zh, en)`。
- 自定义关系以 `new_` 开头、用 **Referential** 级联。
- 避免普通字段以 `Id` 结尾（与查找字段导航属性冲突）。
- `lint` 必须报 **0 errors** 才能 `plan`/`deploy`。

## 9. Dataverse 关键行为（已踩坑，务必遵守）

- **实体属性 PATCH 在部分租户被拒**：`PATCH EntityDefinitions(...)` 返回 `405 / 0x80060888
  "Operation not supported on EntityMetadata"`。`deployer` 把它当作**良性跳过**（实体已存在；
  逆向快照本就匹配）。字段级 PATCH 用 `EntityDefinitions(LogicalName=..)/Attributes(LogicalName=..)`。
- **File 字段在环境中 `AttributeType="Virtual"`**：`reverse` 通过 `@odata.type`
  （`FileAttributeMetadata`）识别为 File，并读取 `MaxSizeInKB`。Image 暂不支持。
- **元数据传播延迟/锁竞争**：每次 create 后等待；`create_attribute`/`update_attribute_by_logical_name`
  /`create_relationship_from_json` 已包 `@retry_on_metadata_error`，识别 `0x80040216`、`0x80060891`、
  "another customization operation is running"、"MetadataCache" 等。
- **关系 create-only**：Dataverse 不支持 PATCH `RelationshipDefinitions`；已存在则跳过。
- **Lookup 经 Deep Insert**：随 1:N 关系一次性创建，不能单独 POST。
- **Picklist/Boolean 的 OptionSet 经属性端点为 create-only**：选项变更需 `InsertOptionValue`/
  `UpdateOptionValue` 或 maker portal；`deployer` 对此报告 `manual_update_required`。
- **【ADR-014】绑定既有全局选项集的字段创建必须用 bind 语法**：属性创建 payload 内联
  `OptionSet.IsGlobal+Name` 会被 **`0x80048403`** 拒（内联块只接受 Local）；
  正确写法 `"GlobalOptionSet@odata.bind": "/GlobalOptionSetDefinitions(<MetadataId>)"`
  （先 `GlobalOptionSetDefinitions(Name='<lowercase>')` 取 id）。`RequiredLevel` 必须
  `{"Value": "None"}` 对象形式。`serialize_column` 的 `optionset_name` 引用路径（ADR-011）
  **已于 2026-08-21 迁移为 bind 语法**（`deployer` 先行 resolve MetadataId 再传入
  `global_optionset_ids`；无法解析时回退内联块），并 live 验证
  （new_rollingforecast.new_IsSplitRecord → new_isornotselect，204 created）。
- **【2026-09-09 修复】`reverse` → 本地 → `deploy` 全链路曾丢 `optionset_name`**（ADR-010 addendum）：
  - `codegen.emit_column()` 原来**只输出 `options=`、从不输出 `optionset_name=`**，导致每次
    reverse 都把**全局选项集静默降级为本地内联**——拿这份定义去新环境 deploy 会**重复建选项集**。
    已修：`optionset_name` 与 `options` 同时输出（前者决定 bind/内联语义，后者仅供文档生成）。
  - `plan` 路径曾用多态 `/Attributes` 的结果（**无 OptionSet 数据**）去跑 `optionset_changed()`，
    于是"本地 N 个选项 vs 远端 0 个"→ 4/4 全局选项集字段全报 `manual_update_required`（误报）。
    已修：`elif not col.optionset_name and optionset_changed(...)`，与 deploy 路径一致——
    **全局选项集的选项不由本表定义管理，不做 per-table diff**。
  - 判据：`pp plan <table>` 出现 `manual_update_required` 且字段带 `optionset_name` → 属旧版误报，升级引擎。
- **`_ATTRIBUTE_ODATA_TYPES` 已覆盖 Lookup 家族**（Lookup/Owner/Customer/PartyList →
  `LookupAttributeMetadata`，及 State/Status/EntityName/Uniqueidentifier/Image）：
  typed GET / `update_attribute_by_logical_name`（如必填级调整）对这些类型可用；
  新增类型映射时同步更新本表和 ADR。
- **Money `*_base` 字段**由 Dataverse 自动创建，逆向/正向均跳过。
- **delete 级联**：`delete_entity` 删表会级联其字段与所属关系（含查找列）。

### 9.1 解决方案域（Phase 2，已 live 踩坑）

- **全局选项集按 `Name` 键查询，且必须小写**：`GlobalOptionSetDefinitions` 不支持
  `$filter`（返回 **405**）；用 `GlobalOptionSetDefinitions(Name='<lowercase>')` 键查询。
  Dataverse 把选项集名存为**小写** logical name（`new_Priority` → `new_priority`），
  查询时必须 `.lower()`，否则 404 → 误判不存在 → 再建触发 `0x80044363 名称不唯一`。
- **解决方案组件走 `solutioncomponents` 实体集，不是导航属性**：`solutions(<id>)/
  solution_solutioncomponents` 与 `.../SolutionComponents` 在部分租户 **404/400**。正确做法：
  先 `get_solution_by_name` 拿 `solutionid`（`unique_name` 不是合法备用键），再
  `solutioncomponents?$filter=_solutionid_value eq <solutionid>`。
- **加入组件用部署返回的 id，不要建后立即按名再查**：元数据传播有延迟，建后立即按名
  `resolve_id` 可能返回 None → 组件漏加（孤立）。各类型 `deploy` 返回 `{"action","id"}`
  或 `{"add_targets":[...]}`（插件），`deploy_solution` 优先用它，避免 create→resolve 竞争。
- **AddSolutionComponent 幂等**：重复加入已存在组件不报错（返回成功），故二次部署的"加入"
  是良性 no-op。
- **解决方案成员原则（可移植/可回归）+ clean 模式（2026-07）**：解决方案原则上**只含自建组件 +
  必要依赖**，不得拖入其它内容（否则污染、不可移植）。痛点是**加实体（code 1）默认含全部子组件**
  （拖入该实体所有 OOB 窗体/视图）。两套可控机制：
  - `deploy_table(..., solution=, solution_clean=True)`（CLI `deploy <t> --solution <s> --solution-clean`）：
    加实体 **SHELL**（`do_not_include_subcomponents=True`）+ 逐个加**自定义字段**（含 relationship lookup
    字段，code 2）→ 解决方案只留自建内容。`solution_clean=False`（默认，向后兼容）仍是「含子组件」。
    **按场景选**：feature/可移植方案用 `--solution-clean`；一次性/调试可用默认。
  - `client.remove_solution_component(name, component_type, object_id)`：**非破坏性**从解决方案移除组件
    （组件本身留在环境的默认未托管层，只是退出解决方案容器）——清理成员的正确姿势。**不要**
    `DELETE solutioncomponents(...)`（400）。走 `RemoveSolutionComponent` action：参数 `SolutionUniqueName`/
    `ComponentType`/`SolutionComponent`（嵌套 `mscrm.solutioncomponent` 对象，action payload 拒绝
    `@odata.bind` 且要求 entity key → `{@odata.type, solutioncomponentid: <组件 objectid>}`，注意传的是
    **组件 objectid** 不是成员记录 id，**已 live 验证**）。
- **`solution deploy/plan` 必须透传 `--definitions-dir`**：表名引用从该目录解析，否则回退到
  默认 `metadata_py/tables`。
- **`PublishAllXml` 组织级**：发布**所有**未托管自定义项，无法只发布单个解决方案。
- ~~插件自定义 Action create-only~~ **已升级（ADR-012，2026-08）**：`components/plugin._deploy_custom_action`
  支持全链路自动建（workflow create + XAML + **激活** + SDK message 解析 + Invoke step 注册 + code 29 入方案），
  失败才回退 `manual_update_required`；详见 §9.7。

### 9.2 安全角色权限域（Phase 3，已 live 验证）

- **角色不在本工具创建**：角色在环境中手动建好；本工具只为**已存在的角色**同步表权限。
  `deploy_role` 遇到缺失角色会报错（不创建）。
- **深度字段是 `privilegedepthmask`（位掩码），不是 `depth`**：`roleprivilegescollection`
  上 `select depth` 会 404（无此属性）。位掩码：USER=1、BUSINESS_UNIT=2、PARENT_CHILD=4、
  GLOBAL=8（"无权限"= 该 roleprivilege 记录不存在）。
- **`roleprivileges` / `roleprivileges` 导航 404**：正确的实体集是
  **`roleprivilegescollection`**；role→privileges 导航属性不可用。
- **privilege 没有 `objecttypecode`、且 `objecttypecode` 不可过滤**：按**表范围**逆向 =
  先解析每张表的 8 个 privilegeid（按名 `prv<Right><EntitySchemaName>`，如
  `prvReadnew_FpSmokeA`，用实体 **SchemaName** 非小写 logical），再用 `privilegeid` 服务端
  过滤 `roleprivilegescollection`。`role reverse --tables` 必填（拒绝拉全环境）。
- **AccessRight**（`privilege.accessright`）：Read=1、Write=2、Append=4、AppendTo=16、
  Create=32、Delete=65536、Share=262144、Assign=524288。
- **`deploy_role` 非破坏 upsert**：只加/改定义中列出的权限；未列出的 right 不动。
- **正向写入只能走 `AddPrivilegesRole` 绑定 Action（关键）**：`roleprivilegescollection`
  实体 **不支持 Create**（`0x80040800 "Create method does not support entities of type
  'roleprivileges'"`）；hand-crafted SOAP 也失败（known-type resolver 不认类型）。正确写法：
  `POST roles(<roleid>)/Microsoft.Dynamics.CRM.AddPrivilegesRole`，body `{"Privileges":[
  {"PrivilegeId":"<guid>","Depth":"<name>"}]}`。
  - **Depth 必须是裸枚举成员名**：`"Basic"`/`"Local"`/`"Deep"`/`"Global"`（PrivilegeDepth 枚举：
    Basic=0/Local=1/Deep=2/Global=3）。整数会 `0x80048d19`；带引号限定名会 500。
  - **位掩码↔枚举映射**：Basic/Local/Deep/Global ↔ 存储的 `privilegedepthmask` 1/2/4/8。
  - **AddPrivilegesRole 是 upsert**：对已存在的 privilege 会更新其 depth（live 验证）。
  - **无单条移除**：`RemoveRolePrivilege` 未作为 Web API action 暴露；故 `deploy_role` 只加/改，
    不回收（要清理某表的权限，删表会级联移除其 roleprivileges）。
- **角色作为解决方案组件**：`ROLE_SOLUTION_CODE=20`（SolutionComponentType，**已 live 验证**：
  `AddSolutionComponent` code=20 成功把角色加入解决方案）；Solution 中 `roles` 为名称引用，
  `solution deploy` 把已存在角色加入解决方案（不在此同步权限，权限走独立 `role deploy`）。

### 9.3 Web 资源目录同步域（Phase 4，已 live 验证）

- **命名 `{prefix}_/{relpath}`**（如 `js/order/test.js` → `new_/js/order/test.js`）：relpath 用正斜杠；
  `webresource_sync.webresource_name` 构造，`relpath_from_name` 反解。环境现有 28 个资源正是此布局。
- **扩展名 → `webresourcetype`**（`EXT_TO_TYPE`）：`.js`→JScript(3)、`.css`→2、`.htm`/`.html`→WebPage(1)、
  `.xml`→4、`.png`→5、`.jpg`/`.jpeg`→6、`.gif`→7、`.xap`→8、`.xsl`/`.xslt`→9、`.ico`→10、`.svg`→11。
  未知扩展名**跳过并告警**（不报错）；dotfile/dot-dir 跳过。
- **content 是 base64**：`scan` 读原始字节 → `base64.b64encode`；`reverse` `base64.b64decode` → 写**字节**
  （保真，不转码）。复用 Phase 2 `components/webresource.deploy`（create 或 PATCH content+displayname）。
- **精准发布走 `PublishXml` action（关键）**：`POST PublishXml` body `{"ParameterXml":
  "<importexportxml><webresources><webresource>{id}</webresource>…</webresources></importexportxml>"}`
  —— 只发布列出的资源 + 刷新引用它们的 form/ribbon 绑定（**已 live 验证**：新建/更新后 `published:true`）。
  与组织级 `PublishAllXml` 不同；频繁改 JS 用精准发布。`client.publish_webresources(ids)`；空 id 列表 no-op。
- **collection 查询不默认返回 `content`**：逆向用 `client.list_webresources_by_prefix(prefix)`，
  显式 `$select=name,webresourceid,webresourcetype,content`（**已 live 验证**：content 返回正常）；
  `$filter=startswith(name,'{prefix}')` 服务端收窄。
- **加入解决方案 code 61**（`components/webresource.SOLUTION_CODE`）：`sync --solution NAME` 调
  `add_solution_component(name,61,id)`，幂等（"already in solution" 良性跳过，复用 `_is_already_exists`）。
- **`sync` 非破坏**：只 create/update；`delete_webresource(id)` 是独立客户端方法（显式清理用，
  **已 live 验证**删除路径），不在 `sync` 内。

### 9.4 窗体域（Phase 5，已 live 验证）

- **窗体 = `systemforms` 实体集**，列：`formid,name,type,objecttypecode,formxml,description,
  iscustomizable,formactivationstate`。**collection 查询不默认返回 `formxml`**（同 web 资源
  `content` 规则）→ 逆向/列表用 `client.list_forms_by_entity(entity)`，显式 `$select` 含 `formxml`。
- **`type` 数值以环境为准（已 live 钉死）**：**Main=2、QuickView=6、QuickCreate=7、Card=11**。
  ⚠️ 早期 `FormType` 枚举把 QuickCreate/QuickView 写反过（误为 6/7），已按环境实测纠正。Dashboard=0、
  Mobile=5 也在枚举中但**不在可编辑集合**（`EDITABLE_FORM_TYPES = {Main, QuickCreate, QuickView}`）。
- **结构化模型 + 无损往返（核心）**：`form_xml.parse_formxml` 把 FormXml 解析成 `Form`(含
  `tabs/columns/sections/rows/cells/controls` + `libraries` + `events`)。**每个布局节点带完整
  `attrs` 字典**（FormXml 属性极多：IsUserDefined/layout/labelwidth/celllabelposition/colspan/
  rowspan/showbar/labelid/locklevel…），序列化时**attrs 优先**（有 attrs 就原样发，无 attrs 发类型化
  默认）→ parse→serialize→parse **幂等**。未建模的 `<form>` 子元素（ancestor/hiddencontrols/
  formParameters/DisplayConditions…）按 `<tabs>` 前后位置分 `extras_pre_xml`/`extras_post_xml`
  原样保留。**已在 4 个真实 account 主窗体（含 7-tab 复杂窗体）live 验证字节级稳定。**
- **sections 嵌套在 columns 里**（`tab/columns/column/sections/section`，真实多列窗体如此）→
  `FormColumn.sections` 保留嵌套；`FormTab.sections` 是跨列扁平视图（只读 helper）。
- **事件绑定**：FormXml 有 `<InternalHandlers>`（系统，只读，逆向保留、**绝不**在此添加）与
  `<Handlers>`（自定义）。`add_event_handler` 只写 `<Handlers>`。`<Handler functionName libraryName
  handlerUniqueId enabled parameters passExecutionContext>`；`<Library name libraryUniqueId>`。
  **`libraryName`/`<Library name>`/`<Handler libraryName>` 三者都是 web 资源名**（`new_/js/...`，
  Phase 4 命名）→ **绑事件前 JS 资源必须先存在**（先 `webresource sync`）。`libraryUniqueId`/
  `handlerUniqueId` 是**必填带括号 GUID**（序列化空值自动 `uuid.uuid4` 生成）；本环境**不用**
  `libraryUniqueIdRaw`（已 live 确认 account 窗体无此属性）。控制级事件（onchange）设 `control_id`，
  窗体级（onload/onsave）不设。
- **classid 映射（已 live 钉死，2026-09-09 修正 memo/Decimal）**：text/String
  `{4273EDBD-AC1D-40D3-9FB2-095C621B552D}`、optionset/Picklist
  `{3EF39988-22BB-4f0b-BBBE-64B5A3748AEE}`、lookup `{270BD3DB-D9AF-4782-9025-509E298DEC0A}`、
  datetime `{5B773807-9FB2-42db-97C3-7A91EFF8ADFF}`、integer `{C6D124CA-...}`、url `{71716B6C-...}`、
  boolean `{B737D7BB-...}`、**Decimal/Money `{B0C872A3-3FA8-4D39-87D3-B3DCDA23B145}`**、
  **memo（多行文本）`{E0DECE4B-6FC8-4A8F-A065-082708572369}`**、
  **statuscode（状态描述）`{5D68B988-0661-4db2-BC3E-17598AD3BE6C}`**。
  ⚠️ **历史错误已修正**：旧版把 `{B0C872A3-...}` 误标为 **memo**，实际它是 **Decimal/Money**；
  memo 真正值是 `{E0DECE4B-...}`。2026-09-09 销售目标主窗体 live 验证：Decimal 字段（单价原币/
  订单数量/金额人民币/签单预算/初始汇率）用 `B0C872A3` 渲染正确，备注 Memo 字段用 `E0DECE4B`
  渲染正确。⚠️ **classid 是租户相关 GUID**——跨环境不要硬背，优先**从同环境一个已渲染正常的
  窗体 reverse 提取**作参考模板。`add_field` 按 P1 `Column.type` 选；String `format_name=Url` →
  url classid；`LookupColumn` → lookup。**Double/File 未覆盖 → 回退 text，需显式传 `classid=`**。
  控件 `id`/`datafieldname` 默认取字段逻辑名（`schema_name.lower()`）——**必须小写**，见 §9.14。
- **非字段（unbound）控件 classid + builder（已 live 钉死）**：subgrid `{E7A81278-8635-4d9e-8D4D-59480B391C5B}`
  + webresource（嵌入 HTML 页）`{6213F1A3-37CE-4A1B-9CCB-CE7B3F1C7AA3}`。两者无 `datafieldname`，配置在
  `<parameters>` 子元素里（`FormControl.parameters` dict 已往返保真）。builder：`add_webresource_cell`
  （参数 `Url/PassParameters/Scrolling/Border`，⚠️ 是 **`PassParameters`** 不是 `PassParams`，值用 `true/false`）
  与 `add_subgrid_cell`（参数 `TargetEntityType/ViewId/RelationshipName/RecordsPerPage/...`）。⚠️ 这两类控件
  的 `<control>` **不要**带 `indicationOfSubgrade` 属性（schema 不允许，报 `0x80048425`）；只放 `id`+`classid`。
- **嵌入 web 资源的 cell 必须有高度 + 合法 id（已 live 钉死）**：webresource 控件所在 `<cell>` **必须带 `rowspan`**
  （`add_webresource_cell` 默认 `rowspan=8`），否则 iframe 渲染成 ~0 高度、**页面不显示**。且 cell 必须有合法 `id`
  (GUID)——曾因给 cell 设 `attrs={"rowspan":"8"}`（旧 serializer 在有 attrs 时只发 attrs、漏了 id）导致 cell `id` 为空 →
  窗体报 `null is not a valid Guid value` + 解决方案查看器无法加载。已修 `_serialize_cell`：authored cell（attrs 无 `id`）
  先发 `id/showlabel/visible` 默认再 overlay attrs；attrs 含 `id`（逆向快照）仍原样发（保往返保真）。
- **标准实体窗体现在可部署（已 live 钉死，2026-07 放开）**：早期 `components/form.deploy/plan` + `form_sync`
  对标准实体（account/contact/...）硬跳过；现按 name+type create-or-PATCH，**允许**在标准实体上新建/更新命名
  窗体（不覆盖 OOB "Information" 除非同名同 type）。安全性靠结构化 diff：逆向未改的窗体重 deploy = `would_skip`/
  `skipped_unchanged`。**视图（view）同样已放开**（2026-07，同 form：`components/view.deploy/plan` + `view_sync` 不再按实体跳过，
  可在标准实体上新建/更新 Public 视图）。optionset/webresource 仍保持标准跳过。
- **发布按实体范围（关键，区别于 web 资源）**：formxml 改动**不会立即生效**，必须 `PublishXml`；
  窗体发布范围是**实体**（不是 form id、也不是 web 资源那种按 id）：`POST PublishXml` body
  `{"ParameterXml":"<importexportxml><entities><entity>{logicalname}</entity></entities>
  </importexportxml>"}`。`client.publish_entity(logical_name)`；`form deploy` 默认对变更实体发布，
  `--no-publish` 关。⚠️ 按实体发布会发布**该实体全部未托管自定义项**（窗体/视图/ribbon）——Dataverse
  固有粒度。
- **非破坏 + 保真 diff**：`plan_forms`/`sync_forms` 把 live 窗体逆向成模型再与 authored 模型比较
  （`==`）；**逆向后未改动的窗体重 deploy = `would_skip`/`skipped_unchanged`**，不 PATCH。
  ⚠️ **细微差别**：全新 builder 创作的窗体节点 `attrs` 为空，逆向的已填充——语义相同但模型不等 →
  重 deploy 是幂等 `would_update`（cell/section GUID 重生成，不影响语义）。关键保证（**逆向未改 →
  no-op**）不受影响。
- **逆向落盘**：`form reverse <entity>` 写 `metadata_py/forms/{entity}__{slug(name)}.py`，每窗体
  一个文件导出 `FORM`（`components.form.codegen` 递归 dataclass→嵌套字面量，含完整 attrs/extras，
  `eval` 可还原）。
- **加入解决方案 code 60**（`components/form.SOLUTION_CODE`）：`form deploy --solution NAME` 调
  `add_solution_component(name,60,id)`，幂等。
- **自动创建窗体的定制 = 实体级 customness（历史背景）**：建表后 Dataverse 自动创建的窗体都叫
  **"Information"**（无 `new_` 前缀）。历史上窗体的 `is_custom` 检查基于**实体**（标准实体窗体跳过）；
  **2026-07 已放开**——`components/form.deploy/plan` 与 `form_sync.plan_forms/sync_forms` 不再按实体跳过，
  标准/自定义实体上的命名窗体均按 name+type create-or-PATCH（见上「标准实体窗体现在可部署」）。
- **同名窗体按 `type` 消歧（已 live 钉死，关键）**：自动创建的 Main/QuickView/Card 窗体**三者都叫
  "Information"**，name-only 查找会命中 QuickView/Card，而它们**不能含 `<events>`** → PATCH 报 400
  `0x8004e300 "Form XML of type quick ... cannot contain element: events"`。故 `get_form_by_name` 带
  `form_type` 过滤（`and type eq N`）；`form_component` 的 deploy/plan/exists/resolve_id 与
  `form_sync._reverse_live/_existing_id` 都传 `form_type=int(form.form_type)`。**修改自动创建的主窗体**
  = reverse 那个 type=2 的 "Information" → builder 编辑 → deploy（按 type 命中 Main，in-place PATCH）。

### 9.5 视图域（Phase 6，已 live 验证）

- **视图 = `savedqueries` 实体集**，列：`savedqueryid,name,querytype,returnedtypecode,fetchxml,layoutxml,
  description,isdefault,iscustomizable,statecode`。**collection 查询不默认返回 `fetchxml`/`layoutxml`**
  （同 form formxml）→ 逆向/列表用 `client.list_views_by_entity(entity)`，显式 `$select` 含两者。
- **`querytype` 以环境为准（已 live 钉死）**：Public=0、AdvancedFind=1、Associated=2、QuickFind=4、Lookup=64
  （还有 8192=OfflineTemplate"My"视图等少用类型）。Public 可创建+更新；其余每实体一个、**仅更新**（`deploy`
  对缺失的非 Public 视图返回 `skipped_standard`，不尝试创建）。`AUTHORABLE_VIEW_TYPES={Public}`、
  `UPDATABLE_VIEW_TYPES` 含上述 5 个。
- **QuickFind 视图不能随意加显示列（已 live 钉死的 Dataverse 约束，非工具 bug）**：给 QuickFind(qt=4)
  视图**加 `<cell>`/fetch `<attribute>`** 会被 Dataverse 拒绝：`400 0x80040216 "An unexpected error occurred"`
  （可复现）。已验证**不是序列化问题**——重新序列化的 fetchxml 与原值**字节级一致**，layout 仅差 XML 属性顺序
  （Dataverse 不关心）；未改动的 QuickFind 往返干净，**只有"加列"这步被拒**。原因是 QuickFind 的布局列与
  `<filter isquickfindfields="1">` 搜索字段强绑定。**要定制 QuickFind，改搜索字段（过滤）而非显示列**：
  用 `set_filter`/`add_condition` 编辑 `isquickfindfields` 过滤里的 condition（工具支持）。其余系统视图
  PATCH 已 live 验证可用：Associated(qt=2) ✓、AdvancedFind(qt=1) ✓、Lookup(qt=64) ✓（`update_view`
  成功；注意同批密集 `PublishXml` 可能撞 429 限流，单独重发发布即可）。
- **结构化模型 + 无损往返（核心）**：`view_xml.parse_view(fetch,layout)` 把两段 XML 解析成 `View`（含
  `columns/filters(递归)/orders/link_entities/primary_id/object_type_code` + `extra_attributes`）。
  **每个节点带完整 `attrs`**，序列化 **attrs 优先**（有 attrs 原样发，无 attrs 发类型化默认）→ 幂等。
  `fetch_attrs`/`grid_attrs`/`row_attrs` 保留其余根属性（version/mapping/savedqueryid；name/jump/select/
  icon/preview；row name）；`extra_attributes` 保留"fetch 有但 layout 无 cell"的隐藏可用列；condition 的
  `<value>` 子元素（`in`/`between`）往返保真。**已在 6 个真实 new_fpformsmoke 视图 live 验证无损。**
- **两段 XML 1:1 配对（关键）**：`columns` **同时**驱动 fetch `<attribute>`（无点的列）+ layout `<cell>`
  （按顺序）；`primary_id` 是 layout `<row id>` 且**始终**也是 fetch `<attribute>`；cell 顺序 = 显示顺序。
  连接列用 `alias.attr`（如 `c.emailaddress1`），其 `<attribute>` 在对应 `link-entity` 上；lint 校验 dotted
  列名引用已知 alias（否则 error）。
- **`object_type_code`（关键，整数）**：layout `<grid object="{int}">` 需要实体的**整数 ObjectTypeCode**
  （不是逻辑名）。逆向从 layout 捕获；新建用 `client.get_object_type_code(entity)`（= `get_entity_metadata`
  `ObjectTypeCode`，已 live 验证 new_fpformsmoke=11076）。`sync_views` 对缺失值的 authored 视图自动填充。
- **过滤树**：`<filter>` 递归 AND/OR（`ViewFilter.filters`）；视图可有**多个并列顶层 `<filter>`**（隐式 AND，
  模型 `View.filters: list`）。`<condition operator>` 任意透传；`in`/`between` 用多个 `<value>` →
  `ViewCondition.values`。部分 operator 无 value（`null`/`eq-userid`/日期相对）。
- **同名视图按 `querytype` 消歧（已 live 钉死）**：自动创建视图名常重复 → `get_view_by_name` 带 `query_type`
  过滤（`and querytype eq N`），`view_component` 的 deploy/plan/exists/resolve_id 与
  `view_sync._reverse_live/_existing_id` 都传 `query_type=int(view.query_type)`（同 form 的 `form_type`）。
- **发布按实体范围**（同 form）：改 fetchxml/layoutxml 需 `PublishXml`，范围实体。复用 `client.publish_entity`。
- **非破坏 + 保真 diff**：`plan_views`/`sync_views` 把 live 视图逆向成模型再比较；**逆向未改 → `would_skip`/
  `skipped_unchanged`**，不重写真实视图。customness 按**实体**（`is_custom(view.entity)`；自定义表的视图可编辑，
  account 等标准实体的视图跳过）。细微差别：全新 builder 创作的视图 attrs 空、逆向的已填充 → 重 deploy 是
  幂等 `would_update`（不影响语义）；关键保证（逆向未改 → no-op）不受影响。
- **逆向落盘**：`view reverse <entity>` 写 `metadata_py/views/{entity}__{slug(name)}.py`，每视图一个文件导出
  `VIEW`（`components.view.codegen` 递归，含完整 attrs，`eval` 可还原）。
- **加入解决方案 code 26**（`components/view.SOLUTION_CODE`）：`view deploy --solution NAME` 调
  `add_solution_component(name,26,id)`，幂等。

### 9.6 Ribbon 域（Phase 7，已 live 验证）

- **Ribbon 没有 Web API 直写（核心）**：只有读函数 `RetrieveEntityRibbon(EntityName=)` /
  `RetrieveApplicationRibbon()`（且本环境 `RetrieveEntityRibbon` 走 `GET …/RetrieveEntityRibbon(EntityName=@p)?@p='x'`
  会 404 "Resource not found for the segment"——故**逆向走 solution 导出**而非该函数）。**写**只能
  `ExportSolution(SolutionName, Managed:false) → ExportSolutionFile(base64 ZIP)` → 改 customizations.xml 的
  `<RibbonDiffXml>` → `ImportSolution(CustomizationFile=base64, OverwriteUnmanagedCustomizations:true)`。
  Ribbon Workbench 慢 + 提示备份是**整包重导入**所致；本工具用**专用小型解决方案**避开。
- **专用 ribbon 解决方案**（默认 `new_RibbonSoln`，`cli._DEFAULT_RIBBON_SOLUTION`）：`ribbon_sync._ensure_solution`
  自动建（用前缀匹配的 publisher）；`_ensure_entity_in_solution` 把目标实体（code 1）加进去（幂等）；
  全局 ribbon 加 Application Ribbons 组件（`_ensure_application_ribbons_in_solution`，组件码待各环境确认）。
- **customizations.xml 结构（已 live 钉死）**：`<ImportExportXml>` 根；每个 `<Entity><Name …>{SCHEMA name}
  </Name><EntityInfo/><FormXml/><SavedQueries/><RibbonDiffXml>…</RibbonDiffXml></Entity>`。⚠️ **实体块
  `<Name>` 是 SchemaName**（如 `new_FpFormSmoke`，且带 `LocalizedName`/`OriginalName` 属性），**不是逻辑名**
  → `solution_zip.inject_entity_ribbondiff` / `extract_ribbondiff` 按 SchemaName 匹配（用
  `client.get_entity_metadata(entity).SchemaName` 查）。注入只替换 `<RibbonDiffXml>` region（regex over
  `<Entity>` 块），**窗体/视图字节级保留** → 导入对它们 no-op。全局 ribbon 是 `</Entities>` 后的**根级**
  `<RibbonDiffXml>`（仅当专用解决方案含 Application Ribbons 组件时存在）。
- **`<RibbonDiffXml>` 默认含 `<Templates><RibbonTemplates Id="Mscrm.Templates"/></Templates>`**（空结构）→
  `ribbon_xml.to_ribbondiff` 必须含它。结构：`<CustomActions>`(CustomAction+Button / HideCustomAction) +
  `<Templates>` + `<CommandDefinitions>`(CommandDefinition) + `<RuleDefinitions>`(DisplayRules/EnableRules) +
  `<LocLabels>`。
- **显隐统一 `<CustomRule>`（项目约定，已按官方文档修正）**：⚠️ **`<CustomRule>` 官方只归
  `<EnableRule>`**——`define-ribbon-display-rules` 列的 21 种 DisplayRule 类型里**没有** CustomRule；RW 严格按
  schema 解析，**DisplayRule 里的 CustomRule 不会显示成 step**（这正是早期"SmokeBtn.DisplayRule 没绑 step"的根因）。
  且 enable-rules 文档明说 **"command bar 里 disabled 即 hidden"** → JS 控制显隐走 `<EnableRule>`+`<CustomRule>`
  才是 docs-canonical 且 RW 可见。故 `add_button(show_fn=, enable_fn=)` 与 `customise_command(show_fn=, enable_fn=)`
  **都生成 EnableRule+CustomRule**（`{button_id}.ShowRule` / `.EnableRule`），接到 command 的 `<EnableRules>`。
  `<CustomRule FunctionName Library="$webresource:…" Default="false|true"><CrmParameter Value="PrimaryControl"/></CustomRule>`，
  JS 返回 bool（true=显示/启用）。**Default 非对称**：自定义按钮 `false`（fail-closed，JS 没加载就藏）；
  OOB customise `true`（fail-OPEN，别因 JS bug 误藏自带按钮）。`<CrmParameter Value>` 顺序=JS 参数顺序（窗体
  `PrimaryControl`=formContext，网格 `SelectedControl`=gridControl）。
- **隐藏/覆盖 OOB**：`hide_oob(oob_command_id, method="command_override")`（默认，可逆，微软推荐）= 覆盖
  `<CommandDefinition Id=<OOB id>>` 的 DisplayRules 为互斥 `Mscrm.HideOnModern` + `Mscrm.ShowOnlyOnModern`
  （永假→**永远隐藏**，丢掉原 command 的规则）。`method="hide_custom_action"` = `<HideCustomAction>`（粘滞难撤销）。
  ⚠️ 这是「**无条件隐藏**」（nuke）语义——只在"彻底移除某 OOB 按钮"时用。
- **「Customise Command」——OOB 按钮条件显隐（保留规则，已 live 验证）**：`ribbon_xml.customise_command(
  ribbon, oob_command_id, library=, show_fn=, enable_fn=, preserve_display_rules=, preserve_enable_rules=,
  actions_xml=)`。对应 Ribbon Workbench 右键 command → "Customise Command"：**保留** OOB 原 Display/Enable
  规则 + **加一个 `<CustomRule>`**（JS 返回 bool）→ 按钮按数据状态**条件**显隐/启禁。与 `hide_oob`（无条件隐藏）
  的区别：本方法不破坏原行为，只在你的 JS 说"隐藏/禁用"时才隐藏/禁用。`show_fn` true=显示/false=隐藏，
  **OOB 用 fail-OPEN（`Default="true"`）**——JS 没加载时保持 OOB 默认（别因 JS bug 误藏一个本来该在的按钮）；
  这与 `add_button` 的 fail-closed（`Default="false"`）刻意不同。`preserve_*` 默认按 command 后缀查
  `ribbon_xml.OOB_COMMAND_RULES`（已 seed `Deactivate` 的 `Mscrm.CanWritePrimary`/`PrimaryIsActive`/
  `PrimaryEntityHasStatecode`）；**未 seed 的 command 必须显式传**。
  ⚠️ **`actions_xml` 坑（关键）**：override 会**整体替换** OOB `<CommandDefinition>`，故要保住点击必须把原
  `<Actions>…</Actions>` 原样塞回（`actions_xml=`）。工具**读不到编译后 ribbon**（`RetrieveEntityRibbon` 仅 SOAP、
  本环境 404/500）→ 拿不到 OOB Actions → **从 Ribbon Workbench 复制该 command 的 `<Actions>` 粘进来**。
  空 `actions_xml` 会生成空 `<Actions/>`，**可能让点击失效**（`lint_ribbon` 会告警）。live smoke：Deactivate
  override 保留 3 条 OOB DisplayRules + 加 EnableRule `new_fpformsmoke.Deactivate.ShowRule`(CustomRule)。
- **CrmParameter → JS 形参（已沉淀，详见 `dv-ribbon-python` skill 表）**：ribbon 把 `<CrmParameter Value=…>`
  **按声明顺序、位置地**传给 JS（无 `Name`；顺序=形参顺序）。`add_button`/`customise_command` 的 JS 参数默认
  **按 scope 选**：窗体 `PrimaryControl`(=formContext)、网格 `SelectedControl`(=gridContext)；用 `params=`(点击)/
  `rule_params=`(规则) 覆盖。CustomRule(显隐/启禁) 返回 bool 或 Promise；点击 `JavaScriptFunction` 无返回。
  常用 Value：`PrimaryControl`/`SelectedControl`/`CommandProperties`/`SelectedControlSelectedItemIds`/
  `SelectedControlSelectedItemCount`/`PrimaryEntityTypeName`/`FirstPrimaryItemId`/`OrgName`/`UserLcid`。
  参考实例：`webresources/js/fpsmoke/ribbon.js`。
- **多语言**：`add_button(label={1033:..,2052:..})` → `<LocLabels><LocLabel Id><Titles><Title languagecode
  description/></Titles></LocLabel>`；按钮 `LabelText="$LocLabels:<id>"` 引用。
- **Location 约定（已 live 钉死，这是按钮"不显示"的头号坑）**：注入位置必须是 **真实存在的 group +
  `.Controls._children` 后缀**：`Mscrm.{Form|HomepageGrid|SubGrid}.{entity}.{area}.Controls._children`；
  Application scope = `Mscrm.{area}.Controls._children`。`add_button(area=None)` 按 scope 选默认 group——
  Form→`MainTab.Save`、HomepageGrid/SubGrid→`MainTab.Management`、Application→`GlobalTab.New`（见
  `ribbon_xml.DEFAULT_AREA_BY_SCOPE`）。**area 必须是真实 group**（form 有 Save/Actions/Collaborate，grid 有
  Management/Actions）；**自造 group（如曾经的 `MainTab.CustomAction`）会让按钮成为孤儿→永不渲染**。
  ⚠️ 这是早期默认 `MainTab.CustomAction._children`（缺 `.Controls`、且 group 不存在）导致"按钮部署成功但
  maker/运行时都看不到"的根因，已修正为 `MainTab.Save.Controls._children`（live 验证：reverse 回显该 Location）。
  想换组就传 `area="MainTab.Actions"`。
- **专用 ribbon 解决方案必须只含实体 SHELL（已 live 钉死）**：`_ensure_entity_in_solution` 调
  `add_solution_component(..., do_not_include_subcomponents=True)`。**不传**会把实体的全部窗体/视图/字段拖进
  解决方案（实体块 ~97KB，含 `<FormXml>`/`<SavedQueries>`），导致 **Ribbon Workbench 拒绝加载**（报"solution
  contains Entities that have all their sub-components included"）且导出/导入变慢。Shell-only 实体块 ~7KB、
  无 FormXml/SavedQueries，但**仍带 `<RibbonDiffXml>`**（本流程唯一编辑的东西）——Workbench 可加载、往返更快。
  ⚠️ 实体若曾被以含子组件方式加过，`add_solution_component` 幂等跳过→必须先 `delete_solution` 再重建（unmanaged
  删除只删容器、不删实体上的 ribbon diff）。
- **经典 RibbonDiffXml 按钮不会出现在 maker 门户的"命令"(Power Fx) 设计器里**——那是另一套（modern commanding）
  系统。**验证按钮要看运行时**：在 model-driven app 里打开该表的一条记录，看命令栏（Save 组附近）。
- **发布**：实体 ribbon 走 `publish_entity`（`<entities><entity>X</entity></entities>`，重发该实体 ribbon+窗体+视图）；
  全局走 `publish_application_ribbon`（`<ribbons><ribbon/></ribbons>`，空 `<ribbon>` 发应用 ribbon）。
- **非破坏**：authored `RibbonDefinition` 是该实体 ribbon diff 的唯一事实来源——重导入只换该 region。
  逆向（`reverse_ribbons`）= 导出专用解决方案 → 提取 `<RibbonDiffXml>` → `parse_ribbondiff`（**作者级 diff**，
  非 RetrieveEntityRibbon 编译结果）。
- **JS 库依赖**：command/rule 的 `Library` 是 webresource 名（`$webresource:new_/js/…`，Phase 4 命名）→
  **ribbon 部署前 JS 必须已同步+发布**，否则显隐/click 回退到 `Default`。

### 9.7 Plugin 域（Phase 8，已 live 验证核心；image/action 全链路见 ADR-012）

Plugin = 程序集 + SDK message step + step image + custom action。Phase 8 把 Phase 2 的「不透明 pluginassembly 上传」升级为
**结构化 + NuGet 包优先**，并修掉 Phase 2 step 注册的多个潜在 bug（Phase 2 从未 live 测过）。**Step Image 与 Custom Action
全链路于 2026-08 RollingForecast 部署中 live 验证并钉死契约（ADR-012）**。

**两条部署路径（已 live 钉死）：**
- **PluginPackage（NuGet，首选，已 live 验证）**：`client.plugin_build.build_plugin_project` → `dotnet pack` 产
  `.nupkg`（base64）→ `POST pluginpackages`。⚠️ **包名必须含发布商前缀**：`pluginpackage.name = {prefix}_{assembly}`
  （如 `new_PP.Crm.Plugin.Smoke`），否则 `0x80040265 "does not contain a solution prefix"`。Dataverse **自动**
  建 `pluginassembly`（用包内 assembly 名，如 `PP.Crm.Plugin.Smoke`），按名 resolve。**无需 ILMerge/签名**。
  ⚠️ **TFM 强制限定（已 live 钉死 + build 时校验）**：本环境 plugin 包运行时**只收 .NET Framework
  `net462`/`net471`**（net462 是**标准/默认**）；assembly 降级路径收 `net462`/`net471`/`net48`。**`net6`/`net8`/
  `netstandard` 一律拒绝**（早 AccountPlugin 是 net8.0 无法部署）。`plugin_build` 在 build 时 `_resolve_deploy_mode`
  + `_validate_tfm_for_mode` **直接抛清晰错误**（`PACKAGE_TFMS=(net462,net471)`、`ASSEMBLY_TFMS=(net462,net471,net48)`），
  避免到 Dataverse 才报晦涩的 "No supported target framework folder"；`PluginProject.target_framework` 默认 `net462`；
  `components/plugin.lint` 也对未支持 TFM 告警。net4xx 工程不能开 `<Nullable>`/`<ImplicitUsings>`（C# 7.3）。build 前要 **清 bin/obj**（TFM
  改动会留 stale 输出让 pack 打错 `lib/<tfm>/`）。
  **命名完全 config 驱动（已 live 验证动态）**：build 传 `-p:AssemblyName={assembly_name}` + `-p:PackageId={prefix}_{assembly_name}`
  覆盖 .csproj 的 `<AssemblyName>`/`<PackageId>` → .csproj 这俩值**被忽略**；不同项目只改 `PluginProject`（company/project/module/kind/prefix），
  DLL/包名/namespace 全跟着 config 走。验证：.csproj 写 `PP.Crm.Plugin.Smoke`、config company=`OtherCorp` → 产出 `OtherCorp.Crm.Plugin.Smoke.dll`。
- **pluginassembly（降级，net48 + 签名 + ILMerge）**：`POST/PATCH pluginassemblies`（content=base64 DLL）。工程
  自己负责 strong-name 签名 + ILRepack 合并分层依赖；工具只 build+上传。fallback 仅当 PluginPackage 不可用时。
  **遗留 .NET 4.6.2 + ILMerge 项目不走 `plugin_build.py`**（dotnet 路径）：部署脚本直接消费 ILMerge 产物 + 注册清单
  （`ninebot-project/plugins/RollingForecast/deploy.py`，幂等可重跑）。

**Step 注册（已 live 钉死，Phase 2 的全是错的）：** step **引用 PluginType 不是 assembly**——
`sdkmessageprocessingstep` 没有 `_pluginassemblyid_value` 字段！正确 payload：
`name` + `sdkmessageid@odata.bind`(/sdkmessages) + **`eventhandler_plugintype@odata.bind`(/plugintypes)** + 实体
限定 `sdkmessagefilterid@odata.bind`(/sdkmessagefilters) + stage/mode/rank/filteringattributes/supporteddeployment。
`eventhandler`/`pluginassemblyid`/`plugintypeid` 作 nav prop 都 **404 undeclared**——只有 `eventhandler_plugintype` 行。
流程：`get_plugintypes_by_assembly` → 选 PluginType（`PluginStep.plugin_type` 匹配 typename/name；空则取唯一）→
`get_sdk_message_id`(message) → `get_sdk_message_filter`(message,entity)（自定义实体通常 OOB 已有；缺则 create）
→ 建 step。
**step 目标实体预检**：注册实体级 step 前 `_register_step` 先 `client.entity_exists(step.entity)`——实体不在环境就**直接 fail**
（清晰报错 "target entity '...' not found; deploy the table first"），否则 Dataverse 在 `sdkmessagefilters` 查询抛晦涩的
`0x80041102 "entity ... not found in MetadataCache"` 400（Phase 9 workflow smoke 踩到——`new_fpformsmoke` 被 env 清掉后）。
故 step 的目标表必须先 deploy。

**Step Image（ADR-012，已 live 钉死）：** `StepImage(alias, image_type: "Pre"|"Post", attributes: str)` 挂
`PluginStep.images`；`sdkmessageprocessingstepimage` create payload = `{entityalias, imagetype(0=Pre/1=Post),
messagepropertyname, sdkmessageprocessingstepid@odata.bind, [attributes]}`。**四个钉住点**：
1. 字段名是 **`attributes`**（不是 SDK 文档常写的 `attributes1`——EntityDefinitions 实测）；
2. **`messagepropertyname` 随消息变化**：**Create → `Id`**（`Target` 在 Create 被拒 `0x8004416b "Message property
   name 'Target' is not valid on message Create"`）；**Update/Delete/其它 → `Target`**。`_image_payload` 按 step.message 自动选；
3. attributes 空/`*` 时**省略字段** = 快照全部属性（空串会被拒）；
4. 幂等按 `entityalias` 查重（`get_step_images` 按 `_sdkmessageprocessingstepid_value` 过滤）；**既有 step 重 deploy
   补挂缺失 image（backfill）**。reverse 回读 images；codegen 往返输出 `StepImage(...)`。

**Custom Action（ADR-012，全链路已 live 验证——不再是 best-effort）：** `CustomAction` 带 `uniquename`/`xaml`/
`plugin_type` 字段。部署链：查 workflow（按 **uniquename**——⚠️ **不带 publisher 前缀**（`new_Interface_X` →
`Interface_X`；SDK message 名才带前缀）；`get_workflow_by_uniquename` type=1 定义优先于 type=2 激活副本）→ 不存在则
`POST workflows`（category=3 Action, type=1 Definition, scope=4 Org；payload 带 `xaml`，**不带** `triggeroncreate`/
`triggeronupdate`——本环境 workflow 实体无这两个属性，带了 400）→ **激活**（`statecode=1, statuscode=2`——激活才生成
SDK message，action 才可调用）→ 解析 SDK message（按带前缀 schema_name）→ 注册 Invoke step（PRT 命名
`{typename}: {message} of any Entity`；幂等按 step 名查重——重复 deploy 不产重复 step）→ workflow 进 `add_targets`
（**code 29**）。XAML：`x:Members` 声明 In/Out 参数（如 `jsondata`(In)/`msg`(Out)），模板源自既有
`Interface_CollectConfirmPaymentAction`（可从在线既有 action 提取）；**XAML 存 `xaml` 字段**（不是 `clientdata`；
collection `$select=xaml` 返回空，须单实体 GET）。激活/创建失败仍回退 `manual_update_required`。

**程序集 content 更新的坑（ADR-012，已 live 钉死）：**
- **content 更换不重枚举 plugintype**：替换 `pluginassembly.content` 后 plugintype 列表**不刷新**，新增 IPlugin 类型
  无法绑 step → `_resolve_plugintype` 解析失败时**自动 `POST plugintypes`** 补建（payload：typename/friendlyname/name +
  `pluginassemblyid@odata.bind`；**不带 `type` 字段**——本环境 plugintype 实体无该属性）。
- **版本号由 DLL AssemblyInfo 决定**：PATCH payload 的 version 不生效。
- **更新 content 前必须清孤儿（部署门禁）**：引用"新 DLL 中已不存在类型"的 step（`0x8004418b` 阻断 assembly 更新）和
  残留 plugintype 记录必须先删。判定孤儿用**元数据分段字符串匹配**（.NET 元数据中 namespace 段与类名分开存储，带点
  全名不连续出现——朴素 `in` 匹配会漏报）。

**解决方案组件码（已 live 钉死）：** `90=PluginType`、`91=PluginAssembly`、`92=SdkMessageProcessingStep`、
**`10030=PluginPackage`**、**`29=Workflow`（custom action 定义）**（Phase 2 的 SOLUTION_CODE=90 是错的——90 是 PluginType）。
**包插件加进命名解决方案：加 `PluginPackage(10030)`，不是 assembly(91)**——assembly 是 package 的一部分，
`AddSolutionComponent(91, asm_id)` 报 **405 `0x8004023b` "Plugin Assembly ... is part of a Plugin Package.
Please export the Package directly."**；加 10030 才行（package 封装 assembly+plugintypes+steps）。故 `add_targets`：
包路径 = `[(10030, package_id), (92, step_id)…]`；assembly 路径 = `[(91, assembly_id), (92, step_id)…]`；
custom action 再加 `[(29, workflow_id), (92, action_step_id)]`。
**step 注册幂等**：deploy 先 `get_steps_by_assembly` 拿已有 step 名，同名 skip（`action:"exists"`）→ 重 deploy 不产重复 step。

**命名（动态 per-project，已 live）：** `{company}.{project}.{Plugin|Action}.{Module}`（`PluginProject.assembly_name`，
`_pascal(module)`）；`company`/`project` 默认 `PP`/`Crm` 但**每项目可覆盖**。assembly/namespace/package-id 用它；
**pluginpackage.name 再加发布商前缀** `{prefix}_{assembly}`。publisher 前缀 `new_` 不变。

**反向：** assembly sourcetype 可能是 4（包派生，不在 `SourceType` 枚举）→ reverse 容错回退 `Database`。step 按
plugintype 反查（`_eventhandler_value`），不是按 assembly。

**CLI：** `python -m framework_power plugin build <dir> <def.py>`（离线打包预览）/ `deploy <dir> <def.py> --env dev
[--plugin-solution NAME]` / `list [--include-system]` / `reverse <name>`。定义文件 `<dir>/plugin_def.py` 导出
`PROJECT = PluginProject(...)`。Skill `dv-plugin-python`。

### 9.8 开发工作流编排域（Phase 9，离线验证 + 待 live）

跨阶段编排层（`workflow.py`）：一个 `metadata_py/project.py` 清单（导出 `PROJECT = Project(...)`）驱动
整条开发链，跨**两个解决方案**：

- **链路**：`optionsets → tables → webresources → plugins → forms → views → roles(opt-in) → ribbon`。
  **ribbon 专用解决方案**（`ribbon_solution`，无 Web API 直写）；**其它进主解决方案**（`main_solution`）。
  两者**必须不同名**（`lint_workflow` 强制）。`WORKFLOW_STAGE_ORDER` 钉死顺序。
- **编排器零手动加组件（核心契约）**：每个 deploy/sync 函数收 `solution=` **自管归属**——编排器**绝不**调用
  `add_solution_component`；只做 ① `_ensure_solutions`（publisher + 两个 solution 外壳，用清单里的 publisher
  而非 phase 的 prefix-lookup hack）② 按链序跑 `_run_stage` ③ 最终 `publish_all_xml`（optionset/table 元数据靠它
  生效；webresource 按 id、form/view 按实体、ribbon 随 import 已各自精准发布）。
  - **三处加法式改动**（默认 None/新增=旧行为不变，168+307 测试不受影响）：`deployer.deploy_table` +
    `solution=None`（自加 code 1）、`role_deployer.deploy_role` + `solution=None`（自加 code 20）、
    新增 `optionset_sync.py`（`sync_optionsets`/`plan_optionsets`/`load_optionset`，镜像 `form_sync`）。
- **清单列表是 stems**（`<dir>/<stem>.py` 解析）；`tables`/`roles` 走各自 registry（`get_definition`/
  `get_role_definition`）；`plugins` 是工程目录（含 `plugin_def.py`，`deploy_plugin` 内 dotnet 构建）；
  `webresources` 是 bool（同步整个 `webresources/`）。某阶段无内容 → `_content_stages` 自动剔除 → 结果里不出现。
- **阶段过滤**：`--only`/`--skip`（取值见 `WORKFLOW_STAGE_ORDER`）；`--include-roles`（roles 默认关，正交的安全
  配置）；`--no-publish`。`plan_workflow` 全 `would_*`、不 ensure solution、不 publish（只读）。
- **optionset 独立文件是新约定**：`metadata_py/optionsets/<stem>.py` 导出 `OPTIONSET`（此前 optionset 只能
  内联进 Solution）。optionset create-only，选项变 → `manual_update_required`。
- **loaders**：`load_project`（importlib + uuid 模块名，镜像 `_load_solution_module`）；其余复用各 phase 的
  `load_form`/`load_view`/`load_ribbon`/`load_optionset`/`get_definition`/`get_role_definition`。
- **CLI：** `python -m framework_power workflow show|lint|plan|deploy`（`--project` 默认
  `metadata_py/project.py`）。Skill `dv-workflow-python`。测试 `test_workflow.py`（13）+ `test_optionset_sync.py`（4）
  + deployer/role_deployer 各 +2（solution 形参），离线全绿。
- **【ADR-018】路径解析修复（2026-09-20 live）**：`Project` 的目录字段是**工作区相对路径**；
  从引擎根带 `--workspace <ws>` 运行时，4 个 workflow 命令加载清单后调
  `resolve_project_dirs(project, ws.root)` 把 7 个目录字段拼成绝对路径——否则 forms/views
  在 `power-platform-agent/metadata_py/...` 下找不到（漏 `ninebot-project/` 前缀）。从工作区
  根运行等价，零行为回退。

### 9.10 环境变更守卫域（ADR-013，已 live 验证）

**改环境前必先备份、全程留台账——引擎级强制守则**（2026-08-19 事故固化：基于未合并分支 DLL 的
"孤儿清理"误删 13 step + 11 plugintype，恢复时无任何可查备份/记录；solution ZIP 覆盖不到
org 级注册）。组件 `components/env_guard.py` + CLI `pp env-guard`：

- **`backup_solution(client, solution, ws)`**：导出 ZIP 到 `workspace/docs/env_backup/{name}.zip`；
  已存在则先**轮转**为 `{name}.{UTC}.zip`（历史永不丢，规范路径永远是最新版）。
- **`snapshot_plugin_registrations(client, ws)`**：org 级插件注册 JSON 快照
  （assemblies→plugintypes→steps 含 stage/mode/filteringattributes→images）——
  **solution ZIP 盲区的补充**（org 级注册的 step/plugintype 不进 solution 导出）。
  live 钉死：**默认跳过 `Microsoft.*`/`System.*` 系统程序集**（全量遍历 + 逐 step 查询
  会超时）；image 用 `get_step_images_bulk` OR-filter 批量（≤15 id/请求，292 step ≈ 20 请求）。
  `assemblies=[...]` 指定范围 / `include_system=True` 显式包含系统程序集。
- **`append_change(ws, env, actor, intent, changes, backups, basis)`**：append-only 台账
  `docs/env_backup/CHANGELOG.md`——时间/环境/操作者/意图/变更明细/备份文件/依据。
  纠错 = 新条目，**绝不改历史**。**恢复时先读台账**（`read_journal` / `pp env-guard log`）。
- **CLI**：`pp env-guard backup <sol>… [--note] [--no-plugin-snapshot]`（备份+台账原子一条）/
  `snapshot [--assemblies]` / `log [--last N] [--json]` / `show`。需 workspace。
- 任何写脚本（deploy/restore/清理）接入模式：写前 `backup_solution` +
  `snapshot_plugin_registrations` + `append_change`；写后 `append_change` 记结果。

### 9.11 App SiteMap 实体菜单域（Phase 10 / ADR-015，已 live 验证）

把新表加进模型驱动 App 菜单（区域 → 组 → SubArea）。`components/sitemap.py`
（`AppSitemap → SiteArea → SiteGroup → SubArea` + `SitemapTitle`，attrs/extras 全保留 →
语义无损往返，同 form/view 契约）+ `sitemap_sync.py`（app 解析/plan/加删实体）+
CLI `pp sitemap apps|show|plan|add-entity|remove-entity`。详见
`ninebot-project/docs/spec/adr-015-app-sitemap-management.md` 与 `dv-sitemap-python` skill。

- **live 钉死：app-aware sitemap 模型**——`appmodule` **没有** `sitemapxml` 列；导航 XML 在
  独立 `sitemap` 实体，键 `sitemap.sitemapnameunique == appmodule.uniquename`
  （app `new_CustomerService` → sitemap 同名）。
- **部署** = `PATCH sitemaps({id}) {sitemapxml}` + 发布；定向
  `PublishXml(<sitemaps><sitemap>{unique}</sitemap></sitemaps>)` 本环境 **400** → 回退
  `PublishAllXml`（组织级）。
- **新增 SubArea 样式克隆**自 sitemap 内既有实体 SubArea（Client/AvailableOffline/
  PassParams/Sku）；标题默认实体显示名（1033+2052）。
- **幂等**：实体已有 SubArea → `skipped_unchanged`；lint 对同实体多处 SubArea 报 error。
- **写前备份**原始 XML 到 `docs/env_backup/sitemap_{unique}.{ts}.bak.xml`（ADR-013 对齐，
  恢复 = PATCH 回去）。
- **【ADR-015 addendum，2026-09-20 live】新增强化**：
  - **`--create-group`**（CLI line 2622 → `add_entity_subarea(create_group_if_missing=…)`）：
    组不存在时自动新建（Id=`group_{uuid4().hex[:8]}`，`attrs={"Id": gid}`，标题取组名 1033+2052）。
    不开则保持 `KeyError("group not found")` 严格语义。
  - **中文菜单标题**：`_entity_display` 优先 `LanguageCode=="2052"`（zh-CN），无中文才回退 1033；
    `add-entity` 不带 `--title` 时菜单直接显示中文（与 ADR-016 视图/窗体名约定一致）。
  - **SiteGroup 必须带 `Id` 属性**（XSD 硬要求，否则 sitemap XML 校验失败）。
- **解决方案**：sitemap = 组件 **code 62**；已在解决方案内（如 `new_entity930` 含
  Customer Service 的 sitemap）则随该解决方案 transport，**不要再 add-component**。
  sitemap 承载**整个 app 导航**（引用解决方案外实体）——transport 时需意识到。
- **live 踩坑（2026-08-27，Workspace.backup_dir）**：`sitemap add-entity/remove-entity`
  曾报 `'Workspace' object has no attribute 'backup_dir'`——`_sitemap_backup_dir` 走
  workspace 解析但 `Workspace` 没有该目录键。已补 `DEFAULT_DIRS["backup"]="docs/env_backup"`
  + `backup_dir` 属性（与 `env_guard.BACKUP_DIRNAME` 对齐），修改需保持二者同步。

### 9.12 实体删除域（已 live 踩坑，2026-08-27 CI 形式发票 2 表移除）

删自定义实体远比"DELETE 实体"复杂，按序排障（工具：`RetrieveDependenciesForDelete`）：

- **依赖查询函数的 Web API 形状**：`GET RetrieveDependenciesForDelete(ObjectId=@i,
  ComponentType=@t)?@i={MetadataId}&@t=1`（参数名是 **ObjectId/ComponentType**，不是
  SDK 消息的 TargetId/TargetComponentType；不带命名空间前缀直接 404）。返回
  `dependentcomponentobjectid/type`（挡删的组件）+ `requiredcomponentobjectid/type`。
- **`0x8004f01f CannotDeleteInUseComponent` 的真实成因优先级**（本次逐一排除）：app
  成员（`appmodulecomponents`，注意 FK 是 `_appmoduleidunique_value` 不是
  `_appmoduleid_value`）、sitemap 引用（`sitemap remove-entity` + PublishAllXml 后即清）、
  解决方案组件行（`RemoveSolutionComponent`）、其它实体的 lookup 关系、workflows/charts/
  其它表单视图 XML 引用——**全查完仍剩 published 层依赖**。
- **published 层依赖环（本次实锤）**：头↔明细互为依赖死锁——头表 Main 窗体的 subgrid
  **依赖明细 Active 视图**（dependencytype=2 已发布），明细的父 **Relationship 依赖头表
  主键 Attribute**；先删谁都被另一个挡。**破环**：不能删最后一个 Main 窗体（`0x8004f661`
  "must have at least one active Main form"）→ 从头表 Main 窗体 formxml **摘掉 subgrid
  cell**（PATCH + `publish_entity` 刷新 published 依赖）→ 删明细 → 删头表。
- **经验顺序**：先 sitemap 摘实体 → RemoveSolutionComponent 摘实体组件 → 用依赖函数看
  剩余依赖 → 破环后再 `pp delete`。0 条记录的表也会被这些元数据依赖挡住。

### 9.13 视图名多语言域（已 live 踩坑，2026-08-28 5 表视图名中文修复）

**API 建表的隐藏副作用**：通过 `POST EntityDefinitions` 建表时，平台自动生成的系统视图
（Active/Inactive/My/QuickFind/Associated/Lookup/AdvancedFind）名称标签会把 **base 语言
（本组织 1033）的英文文本原样复制进所有已启用语言的标签位**（2052 标签存在但文本是英文）
→ 中文个性化用户在视图选择器看到英文名。maker 门户手建的表（如 new_vehiclemodel）则
正确双语。**建表后视图名中文要单独补**（engine 暂未自动化，未来可加）。

修复机制（已 live 验证 35/35）：

- **读**：`GET RetrieveLocLabels(EntityMoniker=@m,AttributeName=@a,IncludeUnpublished=@u)
  ?@m={'@odata.id':'savedqueries(<id>)'}&@a='name'` → 响应在 **`Label.LocalizedLabels`**
  （不是 `value`）。
- **写**：`POST SetLocLabels`，两个坑：① **`EntityMoniker` 用 typed 形态**
  `{"@odata.type":"Microsoft.Dynamics.CRM.savedquery","savedqueryid":"<id>"}`（Action 载荷
  不认 `@odata.id`，报 `0x80048d19`）；② **本组织不接受 `PublishFlag` 参数**（同名 400，
  去掉即 204 成功），发布另走 `publish_entity`。`Labels` 传**完整标签集**（1033 原值 +
  2052 新值）防 replace 语义丢英文。
- **命名按组织健康表惯例**（参照 new_vehiclemodel）：qt=0 → 活动{复数}/停用{复数}（isdefault
  区分）、qt=8192 → 我的{复数}、qt=4 → 快速查找活动{复数}、qt=64/2/1 → {单数}查找视图/
  关联视图/高级查找视图；窗体（type 2/6/11）→ `信息`；{复数}/{单数}取实体 2052
  DisplayCollectionName/DisplayName。
- **引擎已内建自动修复（ADR-016，2026-08-29 live 验证 20/20）**：`deploy_table` 全量
  模式末尾跑 `sync_auto_component_labels`（`label_sync.py`，`DeployConfig.
  localize_auto_components` 可关）——只碰**默认模板命名**的组件（改名过的
  `skipped_custom_name` 不碰），写标签后 **sleep → publish → 回读验证 → 重试**。
  `plan_table` 输出 `auto_component_labels` 预览。新表 deploy 后即双语；存量表重
  deploy 自动治愈（幂等零写入）。
- **窗体标签发布坑（live 钉死）**：`SetLocLabels` 写的是**未发布层**，且不"弄脏"
  窗体记录 → `PublishXml(entity)` 会**跳过**窗体名标签（视图不受影响）；补发
  `PATCH systemforms(name=中文名)`（1033 不动）标脏后再 publish 才生效。引擎已在
  窗体分支自动做这步。

### 9.14 手写 / 全量替换 formxml 域（已 live 踩坑，2026-09-09 销售目标主窗体重建与修复）

脱离 builder 结构化模型、**直接手写 formxml 并 PATCH 全量替换**时的坑（症状往往很隐蔽）：

- **★ `datafieldname` / 控件 `id` 必须全小写（最易踩、最难查）**：属性 `LogicalName` 在
  Dataverse 中**永远存储为小写**（`new_name`）。`<control datafieldname="new_Name">` 写成
  PascalCase 时，渲染引擎**精确匹配（大小写敏感）**失败 → 该控件被**静默丢弃**，用户看到
  **「section 标题全在、里面字段全空」**。修复：正则把 `datafieldname="X"` 与 `<control id="X"`
  全部转小写 → `update_form` PATCH → `publish_entity` → 回读校验（**每个控件的 `datafieldname`
  都必须能命中实体属性列表**）。**教训：生成 formxml 一律小写，不要沿用 Python 定义里的
  PascalCase 字段名。**
- **formxml 内 `&` 必须转义为 `&amp;`**：标签文本（如 "Customer & Product"）裸写 `&` → 解析
  400 `0x80048426`。写文本前做 `xml_escape`。
- **PATCH 全量替换会撞 SQL 唯一约束 `0x80073002`**：新 formxml 用全新 tab id / 控件 id 时，
  Dataverse 会重新 INSERT 组件，与旧窗体残留组件撞键。修复三件套：①**复用原 tab id**；
  ②与旧窗体重名的控件 id 改名（如 `new_remark` → `new_remark_ctrl`）；③去掉 `DisplayConditions`
  元素。
- **★ 改字段显示名后 cell 的 `<label>` 会「自动」跟随 —— 别一上来就 PATCH 窗体**：主窗体 formxml 里
  `<cell>…<label description="旧名" languagecode="2052" />` 看着像硬编码覆盖，但实测（2026-09-16
  滚动预测 3 字段更名：整车物料号→物料号 / 远期汇率→汇率 / 求助→项目最新进展）**只改属性 `DisplayName`
  + `publish_entity`，全程未提交任何 formxml PATCH**，重拉 formxml 后旧名 `count=0`、新名 `count=1`
  —— 平台自动同步了。视图列同理：`<cell name=".." width=".." />` 不带 `labelId` 即跟随属性显示名。
  **正确顺序：先改属性标签 → publish → 回读 formxml / savedquery 确认联动结果 → 再决定是否需要手工补。**
  ⚠️ 边界：仅在 cell label 与属性原显示名**一致**（跟随态）时验证过；若曾被手工改写成别的文字，
  是否仍联动**未验证**，此时才需要手工 `session.patch(.../systemforms(<id>), {'formxml': …})`。
- **主窗体不能删建，只能 in-place PATCH**：`DELETE systemforms` 主窗体被拒（"至少保留一个
  主窗体"）。重建布局的唯一路径是 PATCH formxml。
- **SystemForm 更新用 PATCH，不要 PUT**：直接 `PUT` 返回 **405**（"Operation not supported on
  systemform"）；走引擎 `client.update_form(form_id, {"formxml": ...})`（内部 `session.patch`）
  才成功。
- **删属性前必须先清窗体/视图依赖**：`GET RetrieveDependenciesForDelete(ComponentType=2,
  ObjectId=<attr_metadata_id>)`，`dependentcomponenttype` **26=SavedQuery（视图）、60=SystemForm
  （窗体）**。顺序：**清引用**（视图 PATCH savedquery / 窗体 `update_form`）→ `PublishXml` →
  再 DELETE 属性（204）。跳过清依赖会报 `0x8004f01f`（属性被引用）。
- **发布作用域是实体**：改完 formxml 必须 `client.publish_entity(logical_name)`（等价
  `PublishXml` + `<entities><entity>`）。验证时注意**浏览器缓存**——用 **Ctrl+F5 强刷**再判断。
- **窗体随实体进解决方案**：实体已在解决方案内时，窗体作为子组件随行导出，无需单独
  `AddSolutionComponent`（单独调用可能不生成独立 componenttype=60 行，属正常，不影响 ALM）。

> 交叉引用：视图名多语言见 §9.13（ADR-016 已内建自动修复）。若自行调 `SetLocLabels` 在
> savedquery 上得到 **404**，是调用姿势问题（未用 typed `EntityMoniker`、或 POST 到错误 URL），
> 正确写法见 §9.13。

### 9.15 工作区脚手架模板域（已踩坑，2026-09-10 `.env.example` 从未进版本库）

`pp workspace init` 的脚手架文件全部来自 `framework_power/templates/`（`cli.py` 的
`_TEMPLATES_DIR`）。该目录的 `.gitignore` 有双重身份，两条规则容易打架：

- **★ `.env.*` 规则误伤 `.env.example`（根因）**：`templates/.gitignore` 本意是给**工作区**用的
  （init 时复制到工作区根，防止提交 `.env.local` / `.env.prod` 等真实凭据变体）。但 git 的
  `.gitignore` **分层生效**——它放在 `framework_power/templates/` 下时同样约束该目录自身，于是
  `.env.example` 被一起吞掉，**从未进入版本库**。后果：干净 clone 后 `pp workspace init` 在
  `cli.py` 读它时直接 `FileNotFoundError` 崩溃，新用户连工作区都建不起来，更无从知道要配
  `DEV_CLIENT_ID` / `DEV_CLIENT_SECRET` / `DEV_TENANT_ID`。
- **修复**：保留 `.env` + `.env.*`，追加**白名单** `!.env.example`。`.env.*` 匹配的是文件本身
  而非目录，不存在"父目录被排除则白名单失效"的问题。这样引擎仓库能跟踪模板，工作区也能提交
  自己的副本（模板只含占位符、无密钥，本就该可提交给团队）。
- **模板读取必须容错**：`_read_template()` 在文件缺失时返回 `None` 并打印 `[warn]`，
  `cmd_workspace_init` 逐项判空后跳过——**不要**让一个模板缺失砸掉整个 init。结尾 "Next steps"
  也要按 `env_example.exists()` 分支：有则提示 `cp .env.example .env`，无则退回 `export DEV_*`。
- **自检别被 check-ignore 骗了**：`git check-ignore -v <file>` 命中 `!` 开头的否定规则时**仍会
  输出该行且退出码为 0**。以 `git add --dry-run` 是否被拒、或 `git status --porcelain --ignored`
  是否把文件标成 `!!` 为准。

> 交叉引用：引擎 / 工作区分离（ADR-002）决定 `config/`、`metadata_py/` 不进引擎仓库，新用户
> **只能**靠 `workspace init` 生成配置——所以模板文件必须真的在版本库里，否则 onboarding
> 直接断链。

### 9.16 Picklist 默认值域（已 live 踩坑，2026-09-16 PO 表新增「电摩/非电摩标记」）

**根因：`DefaultValue` 是 Boolean 专用属性，Picklist 用的是 `DefaultFormValue`。** 三处都写错了
名字，导致本地声明的 `default_value` 在**创建 / 补丁 / 反向**三个方向全部静默失效（详见 ADR-017）：

| 层 | 原状 | 后果 |
|---|---|---|
| `serializer.serialize_column` | Picklist 分支**根本不输出**默认值 | 建出来的字段「无默认值」，输出只有 `1 created`，**零报错** |
| `_UPDATABLE_BY_TYPE[Picklist]` | 白名单里没有该键 | 环境默认值漂移时 `plan` 报 `would_skip`，永远修不回来 |
| `reverse.py` Picklist 分支 | 读 `DefaultValue` → 恒为 `None` | 环境里的默认值反向不回来，本地永远缺这一项 |

- **`-1` 是"无默认值"哨兵值**（不是 0，也不是 None）。反向必须归一为 `None`，否则下一轮
  deploy 会把 `-1` 推上去，且**每个无默认值的 Picklist 都会永久 `would_patch`**。
  `new_advance_ratio_met` 就是 `-1`，是验证哨兵处理的现成样本。
- **`bool` 是作者的错**：Picklist 上写 `default_value=True/False` 会被 `False == 0` 悄悄变成
  选项值 0（而 `new_potype` 这类选项是 1/2）。serializer 现在**只告警不推送**——宁可少设一个
  默认值，也不要推一个选项表里不存在的值。
- **补丁路径不需要 typed fetch**（这点和 ADR-010 的 OptionSet 不同）：多态 `/Attributes`
  **确实返回** `DefaultFormValue`（实测 `new_potype` → 1），所以直接拿 `get_attributes()` 的结果
  比对即可，不会误报。
- **一次性副作用**：修好之后，"本地声明了但一直被忽略"的默认值会在该表下次 deploy 时**真正生效**。
  全库审计（21 张本地表）：15 个 Picklist 默认值，**只有 1 个会改变环境**
  —— `new_invoiceappliction.new_taxrate`（本地 2 / 环境 None）。改引擎前后都要跑一遍这个审计。

> 交叉引用：ADR-017（本域决策与验证）；ADR-010（同样是"多态端点缺数据"引发的误报，但那处
> **必须**走 typed fetch，与本条相反）。

## 10. 如何扩展

- **新增属性类型**：`models.AttributeType` + `serializer._ODATA_TYPE`/`_UPDATABLE_BY_TYPE`/per-type 分支
  + `reverse.TYPE_TO_ENUM`（注意 Virtual 类型走 `@odata.type`）+ `codegen.emit_column` 字段。
- **新增 CLI 子命令**：`cli.py` 加 `cmd_xxx` + `build_parser` 注册。
- **新增模型字段**：`models.py` dataclass + `serializer` 输出 + `reverse` 读取 + `codegen` 回写 +
  `serializer._UPDATABLE_BY_TYPE` 白名单 + 往返测试。
- 改动尽量保持 `Table → table_to_python_source → import → Table` **往返保真**（见
  `test_codegen.py`）。

## 11. 测试与质量

- 测试：`test/unit/test_framework_power/`（`@pytest.mark.unit`，无网络，289 用例）。
  运行：`cd test && python -m pytest unit/test_framework_power -o addopts="" -q`。
- Lint：`python -m flake8 framework_power/ --max-line-length=120`。
- 类型：`python -m mypy framework_power --ignore-missing-imports`（根级遗留 `__init__.py` 已移除，不再需要 `--explicit-package-bases`）。
  > **注意**：仓库根目录有个遗留 `__init__.py`，会导致 `mypy <pkg>` 报 "not a valid Python package
  > name" 而中止；**必须加 `--explicit-package-bases`**。
- 覆盖率/HTML 报告等由根 `test/pytest.ini` 控制（默认 `--cov=framework`，对本包测试可用 `-o addopts=""`
  临时关闭以避免 `--cov-fail-under`）。

## 12. 不要做

- 不要把 workspace 数据（ninebot-project/）当引擎代码修改。
- 不要在本包硬编码 token / 环境 URL / 凭据（一律走 `get_client` → `config/` + `.env`）。
- 不要让 `deploy` 变成破坏性操作（delete 是独立显式命令）。
- 不要自动改写用户写的 `schema_name`（命名由作者负责，lint 只校验）。
