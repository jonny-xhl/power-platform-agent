---
name: dv-form-python
description: 用 framework_power（Python 优先）对 Dataverse 模型驱动窗体做结构化建模——逆向现有窗体、按字段设计改布局、新建窗体、绑定 JS 事件、管理 web 资源依赖，并加入解决方案。当用户需要"改窗体/表单布局"、"窗体绑定事件/onload/onchange"、"逆向窗体到 Python"、"新建窗体"、"formxml"时使用此技能。短语如"framework_power form deploy/reverse"、"给窗体加事件"、"FormXml"。
---

# Dataverse 窗体操作（Python 优先 / framework_power）

本技能是 **framework_power** 的**窗体（SystemForm）操作**入口（Phase 5），与表（Phase 1）、
解决方案（Phase 2）、安全角色权限（Phase 3）、web 资源目录同步（Phase 4）并列。

## 核心思想：结构化模型，不是不透明字符串

窗体的 `FormXml` 是一段属性极多的 XML。framework_power 把它**解析成类型化 Python
模型**（`Form` → `FormTab`/`FormColumn`/`FormSection`/`FormRow`/`FormCell`/`FormControl`
+ `FormLibrary` + `FormEvent`/`FormEventHandler`），再用 `form_xml.py` 序列化回去。
**每个布局节点都保留完整 `attrs` 字典**，所以逆向→正向**无损往返**（已在真实 account 主窗体
上 live 验证：4 个主窗体、含 7-tab 的复杂窗体全部字节级稳定）。

这意味着：AI 直接用类型化 Python（builder 函数）改窗体——加字段、绑事件、加依赖——
而**不需要手写 XML**。

## 两种实际场景

1. **基于现有窗体改布局/绑事件**：先 `form reverse <entity>` 拉成 Python 模型 → 用 builder
   编辑（`add_field`/`add_event_handler`/...）→ `form deploy`。
2. **纯新建窗体**：`new_form(...)` 脚手架 → builder 填充 → `form deploy`。

## 可编辑窗体类型（已 live 钉死）

`FormType`（环境 authoritative，**不要凭记忆**）：**Main=2、QuickView=6、QuickCreate=7、
Card=11**。（注：早期枚举把 QuickCreate/QuickView 写反过，已按环境实测纠正。）
本工具只**创作/编辑 Main / QuickCreate / QuickView**；Dashboard/Mobile/Card 可逆向、可入快
照，但 lint 会告警"不在可编辑集合"。

## 修改"创建表后自动创建的窗体"（最常见场景）

建表时 Dataverse **自动创建**一组都叫 **"Information"** 的窗体（Main type=2、QuickView type=6、
Card type=11）。你要定制的通常是那个 **type=2 的 Main "Information"**（初始几乎空白：只有表头 +
`new_name`/`ownerid`）。流程：

```bash
python -m framework_power form list new_fpformsmoke --env dev   # 发现：看到 3 个 "Information"
# 选 type=2 的那个 id，reverse → builder 编辑 → deploy（in-place 修改，不改名）
```

两个**已 live 钉死**的关键点（不遵守会踩坑）：
1. **customness 按实体、不按 form 名**：自动创建窗体叫 "Information"（无 `new_` 前缀），但属于自定义表 →
   可编辑。工具按 `is_custom(form.entity)` 判断（自定义表的窗体都算 ours；account 等标准实体的窗体跳过）。
2. **同名窗体必须按 `type` 消歧**：3 个 "Information" 同名，`get_form_by_name` 带 `form_type` 过滤
   （`and type eq 2`）才能命中 Main；否则会命中 QuickView/Card，而它们**不能含 `<events>`** → PATCH 报
   400 `0x8004e300 "...cannot contain element: events"`。工具的 deploy/plan/reverse 都自动传 `form_type`。

所以修改自动创建窗体：**reverse 那个 type=2 的 → 用 builder 加字段/绑事件 → deploy**（按 type 命中 Main，
in-place PATCH，保留其 formid/身份）。

## 事件绑定（最重要的部分，已 live 验证）

FormXml 里事件有两类 handler 容器：
- `<InternalHandlers>` —— **系统** handler，**只读**，逆向保留、**绝不**在此添加。
- `<Handlers>` —— **自定义** handler，**绑事件写这里**。

`add_event_handler` 自动写进 `<Handlers>`：
```python
form = fx.add_library(form, "new_/js/order/order.js")           # web 资源依赖
form = fx.add_event_handler(                                     # 绑 onload
    form, "onload", "Onload", "new_/js/order/order.js",
    pass_execution_context=True,
)
form = fx.add_event_handler(                                     # 控件级 onchange
    form, "onchange", "onCodeChange", "new_/js/order/order.js", control_id="new_code",
)
```
- `library_name` / `<Library name>` / `<Handler libraryName>` **三者都是 web 资源名**
  （Phase 4 命名 `new_/js/...`）。**绑事件前，对应 JS web 资源必须已存在于环境**——先
  `framework_power webresource sync` 同步它。
- `libraryUniqueId` / `handlerUniqueId` 是**必填**的带括号 GUID；序列化时空值会自动生成。
  本环境**不用** `libraryUniqueIdRaw`。
- `add_event_handler` 默认会顺带把 library 加入 `formLibraries`（`add_library_if_missing=True`）。

## 布局：字段摆放（`add_field`）

`add_field` 把一个 P1 `Column`/`LookupColumn` 放到指定 tab/section：
```python
form = fx.add_field(form, col, tab_name="GENERAL_TAB", section_name="General_Section")
```
- **★ 控件 `id` / `datafieldname` 必须全小写**（默认取 `schema_name.lower()`）。属性 `LogicalName`
  在 Dataverse 中**恒为 lowercase**（`new_name`）；写成 PascalCase（`new_Name`）→ 渲染引擎
  **大小写敏感**匹配失败、控件被**静默丢弃** → 用户看到「**section 都在、字段全空**」
  （2026-09-09 live 修复）。**不要沿用 Python 表定义里的 PascalCase 字段名。**
- `classid` 由字段类型推导（已 live 钉死，**2026-09-09 修正**）：text `{4273EDBD-...}`、
  optionset/Picklist `{3EF39988-...}`、lookup `{270BD3DB-...}`、datetime `{5B773807-...}`、
  integer `{C6D124CA-...}`、url `{71716B6C-...}`、boolean `{B737D7BB-...}`、
  **Decimal/Money `{B0C872A3-3FA8-4D39-87D3-B3DCDA23B145}`**、**memo `{E0DECE4B-6FC8-4A8F-A065-082708572369}`**、
  **statuscode `{5D68B988-0661-4db2-BC3E-17598AD3BE6C}`**。⚠️ 旧版把 `{B0C872A3-...}` 误标为 memo，
  实际是 Decimal/Money。Double/File 等未覆盖类型回退 text，可显式传 `classid=` 覆盖。
  ⚠️ **classid 是租户相关 GUID**——优先从同环境一个已正常渲染的窗体 reverse 提取，别硬背。
- section 满列（`cells >= columns`）时自动换行。

## Web 资源依赖

窗体的 JS 依赖 = `formLibraries` 里的 `Library`。用 `add_library` / `remove_library` 管理。
**依赖的资源必须先存在**（Phase 4 `webresource sync`）。

## 发布语义（关键，已 live 验证）

- 窗体 formxml 改动**不会立即生效**，必须 `PublishXml`。
- 窗体发布是**按实体（entity）范围**，**不是**按 form id，也**不是** web 资源那种按 id：
  `PublishXml` body `<importexportxml><entities><entity>{logicalname}</entity></entities>
  </importexportxml>`。`form deploy` 默认在 deploy 后对变更实体做精准按实体发布；
  `--no-publish` 可关。
- ⚠️ 按实体发布会发布**该实体全部未托管自定义项**（窗体/视图/ribbon）——这是 Dataverse 的
  固有粒度，无法只发单个窗体。

## 手写 / 全量替换 formxml 的坑（不走 builder 时，已 live 踩坑 2026-09-09）

需要直接拼 formxml 再 PATCH（而不是用 `add_field` 等 builder）时，以下每条都会让你白忙一场：

- **★ `datafieldname` / `<control id>` 一律小写**。改完**必做回读校验**：正则抽出全部
  `datafieldname`，逐个确认命中实体属性列表（`client.get_attributes(entity)`）——这是唯一能
  提前发现"字段被静默丢弃"的手段。
- **`&` 必须转义成 `&amp;`**：标签文本裸写 `&`（如 "Customer & Product"）→ 解析 400 `0x80048426`。
- **全量 PATCH 要复用原 tab id**：用全新 tab id / 控件 id 会让 Dataverse 重新 INSERT 组件，
  与旧窗体残留组件撞键 → SQL 唯一约束 `0x80073002`。修复三件套：①复用原 tab id ②与旧窗体
  重名的控件 id 改名（如 `new_remark` → `new_remark_ctrl`）③去掉 `DisplayConditions`。
- **主窗体不能删除重建**：`DELETE systemforms` 被拒（"至少保留一个主窗体"）。改布局只能
  **in-place PATCH**。
- **SystemForm 用 PATCH 不用 PUT**：`PUT` 返回 **405**（"Operation not supported on systemform"），
  走 `client.update_form(form_id, {"formxml": ...})`。
- **删字段前先清窗体/视图依赖**：`RetrieveDependenciesForDelete(ComponentType=2, ObjectId=<attr_id>)`，
  `dependentcomponenttype` **26=SavedQuery（视图）、60=SystemForm（窗体）**；顺序：**清引用 →
  `PublishXml` → DELETE 属性**，否则报 `0x8004f01f`。
- **验证前 Ctrl+F5 强刷**：发布后浏览器可能仍渲染旧版缓存，先强刷再下"改了没生效"的结论。

## CLI

```bash
python -m framework_power form list <entity> --env dev                 # 列出实体的窗体（live）
python -m framework_power form show <file>                             # 离线：打印模型摘要
python -m framework_power form lint <file>                             # 离线：约定检查
python -m framework_power form plan <file> --env dev                   # 只读预演
python -m framework_power form deploy <file> --env dev [--solution NAME] [--no-publish]
python -m framework_power form reverse <entity> --env dev [--forms-dir DIR]
# 默认 --forms-dir metadata_py/forms/；逆向每窗体一个文件，导出 FORM
```

## 工作流

```
逆向参考：framework_power form reverse new_order --env dev
  → ninebot-project/metadata_py/forms/new_order__*.py（每窗体一个，结构化模型 + 完整 attrs，无损）
新建/编辑：
  from framework_power import form_xml as fx
  from framework_power.models import Column, AttributeType, Label
  form = fx.new_form("new_Order Main", "new_order")
  form = fx.add_field(form, Column("new_Code", AttributeType.String, Label.zh("单号")), ...)
  form = fx.add_library(form, "new_/js/order/order.js")
  form = fx.add_event_handler(form, "onload", "Onload", "new_/js/order/order.js", pass_execution_context=True)
  → framework_power form plan <file>   （只读预演）
  → framework_power form deploy <file> --solution new_Core   （create/update + 按实体发布 + 入解决方案 code 60）
```

## 保真 / 非破坏约束

- **无损往返**：布局节点保留完整 `attrs`；未建模的 `<form>` 子元素（ancestor/hiddencontrols/
  formParameters/DisplayConditions…）按 `<tabs>` 前后位置分两段原样保留（`extras_pre_xml` /
  `extras_post_xml`）。
- **非破坏**：`deploy` 只 create/update（不删）。`plan`/`deploy` 在**结构化模型**上 diff：
  把 live 窗体逆向成模型再与你的模型比较——**逆向回来未改动的窗体重新 deploy = 跳过
  （would_skip / skipped_unchanged）**，绝不会用重新生成的 formxml 覆盖真实窗体。
- ⚠️ **一个细微差别**：从 builder（`new_form`/`add_field`…）**全新创作**的窗体，其节点
  `attrs` 为空；而逆向得到的节点 `attrs` 已填充。两者语义相同但模型不等，所以**重新 deploy
  一个全新创作的窗体会是 `would_update`**（幂等 re-PATCH，cell/section 的 GUID 会重新生成——
  不影响语义）。关键的非破坏保证（**逆向后未改 → no-op**）不受影响。

## 不要做

- 不要往 `<InternalHandlers>` 写 handler——那是系统的；只写 `<Handlers>`（`add_event_handler`
  已自动处理）。
- 不要凭记忆写 `FormType` 数值——以环境为准（Main=2/QuickView=6/QuickCreate=7/Card=11）。
- 不要假设改了 formxml 立刻生效——必须按实体 `PublishXml`（`form deploy` 默认已做）。
- **不要把 PascalCase 字段名写进 `datafieldname` / `<control id>`**——必须全小写，否则控件被
  静默丢弃，页面只剩空 section（2026-09-09 live 踩坑）。
- 不要给 Double/File 等未覆盖类型盲用 text classid——传显式 `classid=` 或接受回退并验证
  （Decimal/Money 现已覆盖：`{B0C872A3-3FA8-4D39-87D3-B3DCDA23B145}`）。
- `True`/`False`（Python），不要 `true`/`false`。
