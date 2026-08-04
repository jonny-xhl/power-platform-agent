---
name: dv-view-python
description: 用 framework_power（Python 优先）对 Dataverse 视图（SavedQuery）做结构化建模——逆向现有视图、加列/减列/排序、设过滤条件（AND/OR 树 + 多值）、连接 link-entity，并加入解决方案。当用户需要"改视图/列"、"视图过滤条件"、"逆向视图到 Python"、"新建视图"、"FetchXml/LayoutXml"时使用此技能。短语如"framework_power view deploy/reverse"、"给视图加列"、"视图筛选"。
---

# Dataverse 视图操作（Python 优先 / framework_power）

本技能是 **framework_power** 的**视图（SavedQuery）操作**入口（Phase 6），与表（P1）、解决方案（P2）、
安全角色权限（P3）、web 资源目录同步（P4）、窗体（P5）并列。

## 核心思想：结构化模型，不是不透明 XML

视图有**两段配对 XML**：**FetchXml**（查询：列 + 过滤 + 排序 + 连接）和 **LayoutXml**（网格：显示的列 +
顺序 + 宽度），二者 **1:1 配对**（每个 `<cell>` 对应一个 fetch `<attribute>`；cell 顺序 = 显示顺序）。
framework_power 把它们**解析成一个类型化 `View`**，再用 `view_xml.py` 序列化回去。**每个节点保留完整
`attrs` 字典** → 逆向→正向**无损往返**（已在真实 new_fpformsmoke 视图上 live 验证：含 QuickFind 双过滤、
`in` 多值、`eq-userid` 无值）。

AI 直接用类型化 Python（builder 函数）改视图——加列、设过滤、排序——**不需要手写 XML**。

## 两种实际场景

1. **新建 Public 视图**：`new_view` 脚手架 → builder 填充 → `view deploy`。
2. **改现有/自动创建视图**：`view reverse <entity>` 拉成 Python 模型 → builder 编辑 → `view deploy`
   （in-place 修改，按 `querytype` 命中）。

## 视图类型（querytype，已 live 钉死）

| querytype | 名称 | 操作 |
|-----------|------|------|
| 0 | Public（公共列表视图） | **创建 + 更新**（唯一可创建的） |
| 1 | Advanced Find | 仅更新（每实体一个） |
| 2 | Associated | 仅更新 |
| 4 | Quick Find | 仅更新 |
| 64 | Lookup | 仅更新 |

`querytype` 是**同名视图的消歧键**（建表自动创建的视图名常重复）→ 查找必须带 `querytype`（工具自动传）。

### ⚠️ QuickFind 视图不能随意加显示列（Dataverse 约束，已 live 验证）

给 QuickFind(qt=4) 视图**加 `<cell>` / fetch `<attribute>`** 会被 Dataverse 拒绝：`400 0x80040216`
"An unexpected error occurred"（可复现）。已证明**不是工具问题**——重新序列化的 fetchxml 与原值字节级一致，
未改动的 QuickFind 往返干净，**只有"加列"这步被拒**。原因：QuickFind 布局列与 `<filter isquickfindfields="1">`
搜索字段强绑定。

**要定制 QuickFind，改搜索字段（过滤）而非显示列**：用 `set_filter` / `add_condition` 编辑
`isquickfindfields` 过滤里的 condition（决定搜索框搜哪些字段）。其余系统视图 PATCH 已验证可用：
Associated ✓、AdvancedFind ✓、Lookup ✓（`update_view` 成功；密集 `PublishXml` 可能撞 429 限流，单独重发即可）。

## 关键字段（必须懂）

- **`primary_id`**：layout `<row id>` 指向的主键字段（如 `new_xxxid`），**始终**也在 fetch `<attribute>` 里。
- **`object_type_code`**：layout `<grid object="...">` 需要的**整数 ObjectTypeCode**（不是逻辑名！）。逆向自动捕获；
  新建时用 `client.get_object_type_code(entity)` 查（已 live 验证：`get_entity_metadata.ObjectTypeCode`）。
  `new_view` 必填此参数。
- **`columns`**：显示列，**同时**驱动 fetch `<attribute>`（无点的列）+ layout `<cell>`（按顺序）。
  连接列用 `alias.attr` 形式（如 `c.emailaddress1`），其 `<attribute>` 在对应 link-entity 上。

## 过滤条件（FetchXml 过滤树）

`<filter>` 可嵌套（AND/OR 任意树）；`<condition>` 的 `operator` 任意透传（eq/ne/gt/like/in/null/
eq-userid/last-x-days/…）。`in`/`between` 用多个 `<value>` 子元素：

```python
from framework_power import view_xml as vx
v = vx.new_view("new_Order Active", "new_order", primary_id="new_orderid",
                object_type_code=client.get_object_type_code("new_order"))
v = vx.add_column(v, "new_name")
v = vx.add_order(v, "new_name")
v = vx.add_condition(v, "statecode", "eq", value="0")          # 单值
v = vx.add_condition(v, "new_status", "in", values=["1", "2"])  # 多值 <value>
```

- 视图可有**多个并列顶层 `<filter>`**（隐式 AND）——模型里是 `View.filters: list`。
- `set_filter(view, ViewFilter(...))` 替换；`add_link_entity(...)` 加连接（其列用 `alias.attr` 引用）。

## 发布语义（关键，已 live 验证）

- 改了 fetchxml/layoutxml **需 `PublishXml` 才生效**，范围是**实体**（不是单个视图）：
  `<importexportxml><entities><entity>{logical}</entity></entities></importexportxml>`。
- `view deploy` 默认 deploy 后对变更实体做**按实体发布**（同 form）；`--no-publish` 可关。
- ⚠️ 按实体发布会发布**该实体全部未托管自定义项**（视图/窗体/ribbon）——Dataverse 固有粒度。

## CLI

```bash
python -m framework_power view list <entity> --env dev                 # 列出实体的视图（live）
python -m framework_power view show <file>                             # 离线：打印模型摘要
python -m framework_power view lint <file>                             # 离线：约定检查
python -m framework_power view plan <file> --env dev                   # 只读预演
python -m framework_power view deploy <file> --env dev [--solution NAME] [--no-publish]
python -m framework_power view reverse <entity> --env dev [--views-dir DIR]
# 默认 --views-dir metadata_py/views/；逆向每视图一个文件，导出 VIEW
```

## 工作流

```
逆向参考：framework_power view reverse new_order --env dev
  → ninebot-project/metadata_py/views/new_order__*.py（每视图一个，结构化模型 + 完整 attrs，无损）
新建/编辑：
  from framework_power import view_xml as vx
  v = vx.new_view("new_Order Active", "new_order",
                  primary_id="new_orderid", object_type_code=client.get_object_type_code("new_order"))
  v = vx.add_column(v, "new_name", width=200)
  v = vx.add_order(v, "new_name")
  v = vx.add_condition(v, "statecode", "eq", value="0")
  → framework_power view plan <file>    （只读预演）
  → framework_power view deploy <file> --solution new_Core   （create/update + 按实体发布 + 入解决方案 code 26）
改自动创建视图：reverse 那个 querytype=0 的 → add_column → deploy（按 querytype 命中，in-place）
```

## 保真 / 非破坏约束

- **无损往返**：每个节点带完整 `attrs`；fetch/grid/row 的其余根属性（version/mapping/savedqueryid；
  name/jump/select/icon/preview；row name）按 `fetch_attrs`/`grid_attrs`/`row_attrs` 原样保留；
  `extra_attributes` 保留"fetch 有但 layout 无 cell"的隐藏可用列；condition 的 `<value>` 子元素往返保真。
- **非破坏**：`deploy` 只 create/update（不删）。`plan`/`deploy` 在**结构化模型**上 diff：把 live 视图逆向成
  模型再与你的模型比较——**逆向回来未改动的视图重新 deploy = 跳过（would_skip / skipped_unchanged）**，
  绝不用重新生成的 XML 覆盖真实视图。
- ⚠️ **细微差别**：全新 builder 创作的视图节点 `attrs` 为空，逆向的已填充——语义相同但模型不等 → 重 deploy
  是幂等 `would_update`。关键保证（**逆向未改 → no-op**）不受影响。
- customness 按**实体**：自定义表（`new_xxx`）的视图可编辑；标准实体（account）的视图跳过。

## 不要做

- 不要凭记忆写 querytype 数值——以环境为准（Public=0/AdvancedFind=1/Associated=2/QuickFind=4/Lookup=64）。
- 不要给 `new_view` 传 `object_type_code=0` 或不传——layoutxml `<grid object>` 需要正确整数；
  用 `client.get_object_type_code(entity)` 查。
- 不要假设改了 fetchxml 立刻生效——必须按实体 `PublishXml`（`view deploy` 默认已做）。
- 不要把 `alias.attr` 列加进去却没声明对应 `link-entity`（lint 会报"unknown link-entity alias"）。
- 不要给 QuickFind(qt=4) 视图加显示列——Dataverse 拒绝（`400 0x80040216`，见上）。改搜索字段用过滤编辑。
- `True`/`False`（Python），不要 `true`/`false`。
