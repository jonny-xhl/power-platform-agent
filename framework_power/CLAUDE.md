# framework_power — 开发指南 (CLAUDE.md)

本文件为 Claude Code 在 `framework_power/` 包内工作时提供指导。它是该项目"Python 优先的 Dataverse
表元数据部署库"，替代旧 `framework/` 的 YAML→转换→Web API 链路（仅限**表**域：表 + 字段 + 关系）。

> 入口文档：根目录 `CLAUDE.md`；部署说明 `docs/metadata-deploy.md`；作者契约
> `docs/metadata-py-conventions.md`；相关 skill：`dv-model-to-python`、`dv-reverse-metadata`、
> `dataverse:dv-metadata`。

---

## 1. 是什么

`framework_power` 把一张表定义为一个**类型化的 Python 模型**（`Table`），模型即"单一事实来源"。
- **正向 `deploy`**：把 `Table` 同步到 Dataverse（create / PATCH-sync 字段 / create-only 关系）。
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

## 2. 硬性约束（必须遵守）

- **与 `framework/` 完全隔离**：本包**不得 import** `framework.*`，也**不得修改** `framework/` 或
  `metadata/`。复用的传输/认证/配置/重试代码已**拷贝**到 `framework_power/client/`，在本包内维护。
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
  client/            拷贝自 framework/utils 并精简（与 framework/ 隔离）
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

## 6. CLI

```bash
python -m framework_power list                                   # 发现 metadata_py/tables/*.py
python -m framework_power show <name>                            # 打印序列化 payload（离线）
python -m framework_power lint [<name>]                          # 离线约定门（0 errors 必须）
python -m framework_power plan <name> --env dev                  # 只读预演
python -m framework_power deploy <name> --env dev                # 正向同步
python -m framework_power deploy-all --env dev                   # 按依赖顺序部署全部
python -m framework_power reverse <name> --env dev               # 逆向导出（全量快照）
python -m framework_power delete <name> --env dev                # 删除表（破坏性；级联字段+关系）
# 全局参数：--definitions-dir <dir>（默认 metadata_py/tables）
```

认证：`get_client(env)` 复用 `config/environments.yaml` + `.env`（client-secret），MSAL
client-credentials，token 缓存于 `.pp-local/state/tokens.json`。

## 7. 工作流（需求 → 定义 → 同步）

```
需求 (sources/features/<feature>/01-prd)
  → design-dv-model → Excel 设计
  → dv-model-to-python → metadata_py/tables/<schema>.py     （AI 按契约生成）
  → framework_power lint          （离线门，0 errors）
  → framework_power plan          （只读预演）
  → framework_power deploy        （同步到环境）
逆向参考：framework_power reverse <name>   （环境 → 本地，供 AI/对比/约束）
```

## 8. 元数据作者约定（摘要，详见 docs/metadata-py-conventions.md）

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
- **`solution deploy/plan` 必须透传 `--definitions-dir`**：表名引用从该目录解析，否则回退到
  默认 `metadata_py/tables`。
- **`PublishAllXml` 组织级**：发布**所有**未托管自定义项，无法只发布单个解决方案。
- **插件自定义 Action create-only**：新建 SDK-message 自定义 Action 需 Workflow，Web API
  单独建不了 → `manual_update_required`；只能加入已存在的。

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
- **classid 映射（已 live 钉死）**：text `{4273EDBD-...}`、optionset `{3EF39988-...}`、lookup
  `{270BD3DB-...}`、datetime `{5B773807-...}`、integer `{C6D124CA-...}`、url `{71716B6C-...}`、
  boolean `{B737D7BB-...}`、memo `{B0C872A3-...}`。`add_field` 按 P1 `Column.type` 选；String
  `format_name=Url` → url classid；`LookupColumn` → lookup。**Money/Decimal/Double/File 未覆盖 →
  回退 text，需显式传 `classid=`**。控件 `id`/`datafieldname` 默认取字段逻辑名（`schema_name.lower()`）。
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
- **自动创建窗体的定制 = 实体级 customness（已 live 钉死）**：建表后 Dataverse 自动创建的窗体都叫
  **"Information"**（无 `new_` 前缀）。所以窗体的 `is_custom` 检查基于**实体**而非 form 名——
  `components/form.deploy/plan/lint` 与 `form_sync.plan_forms/sync_forms` 都用 `is_custom(form.entity, prefix)`。
  自定义表（`new_xxx`）的 "Information" 可编辑；标准实体（account）的窗体仍跳过。（早期按 form 名判断会把
  自动创建窗体误判为 standard 而跳过——已纠正。）
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

## 10. 如何扩展

- **新增属性类型**：`models.AttributeType` + `serializer._ODATA_TYPE`/`_UPDATABLE_BY_TYPE`/per-type 分支
  + `reverse.TYPE_TO_ENUM`（注意 Virtual 类型走 `@odata.type`）+ `codegen.emit_column` 字段。
- **新增 CLI 子命令**：`cli.py` 加 `cmd_xxx` + `build_parser` 注册。
- **新增模型字段**：`models.py` dataclass + `serializer` 输出 + `reverse` 读取 + `codegen` 回写 +
  `serializer._UPDATABLE_BY_TYPE` 白名单 + 往返测试。
- 改动尽量保持 `Table → table_to_python_source → import → Table` **往返保真**（见
  `test_codegen.py`）。

## 11. 测试与质量

- 测试：`test/unit/test_framework_power/`（`@pytest.mark.unit`，无网络，270 用例）。
  运行：`cd test && python -m pytest unit/test_framework_power -o addopts="" -q`。
- Lint：`python -m flake8 framework_power/ --max-line-length=120`。
- 类型：`python -m mypy framework_power --ignore-missing-imports --explicit-package-bases`。
  > **注意**：仓库根目录有个遗留 `__init__.py`，会导致 `mypy <pkg>` 报 "not a valid Python package
  > name" 而中止；**必须加 `--explicit-package-bases`**（这也影响 `mypy framework/`）。
- 覆盖率/HTML 报告等由根 `test/pytest.ini` 控制（默认 `--cov=framework`，对本包测试可用 `-o addopts=""`
  临时关闭以避免 `--cov-fail-under`）。

## 12. 不要做

- 不要 import 或修改 `framework/`、`metadata/`。
- 不要在本包硬编码 token / 环境 URL / 凭据（一律走 `get_client` → `config/` + `.env`）。
- 不要让 `deploy` 变成破坏性操作（delete 是独立显式命令）。
- 不要自动改写用户写的 `schema_name`（命名由作者负责，lint 只校验）。
