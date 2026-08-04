---
name: dv-ribbon-python
description: 用 framework_power（Python 优先）给 Dataverse 窗体/视图/子网格/全局 ribbon 加自定义按钮、绑定 JS command、用 CustomRule 控制显隐、多语言标签、隐藏/覆盖 OOB 按钮，经专用解决方案（export→改 RibbonDiffXml→import→定向发布）部署。当用户需要"加 ribbon 按钮"、"ribbon 绑事件/JS"、"ribbon 显隐 CustomRule"、"隐藏系统按钮"、"RibbonDiffXml"、"ribbon workbench 替代"时使用。短语如"framework_power ribbon deploy/reverse"、"给窗体加按钮"、"ribbon customrule"。
---

# Dataverse Ribbon 定制（Python 优先 / framework_power）

本技能是 **framework_power** 的 **ribbon（命令栏）定制**入口（Phase 7），与表/解决方案/角色/web 资源/
窗体/视图并列。

## 核心事实：ribbon 没有 Web API 直写，必须走 solution 导入导出

Ribbon 与窗体/视图**本质不同**：它没有 `systemforms`/`savedqueries` 那样的实体集，Web API 只能
**读**（`RetrieveEntityRibbon`/`RetrieveApplicationRibbon`）。**写只能**：`ExportSolution → 改
customizations.xml 的 <RibbonDiffXml> → ImportSolution`（Ribbon Workbench 也是这么做的）。

**为什么我们更快、免备份提示**：Ribbon Workbench 慢 + 提示备份，是因为它**整包重导入你指向的解决方案**。
本工具用**专用小型 ribbon 解决方案**（默认 `new_RibbonSoln`，只含目标实体 + JS 资源）→ 注入 RibbonDiffXml
→ 导入 → **定向 `PublishXml`**。秒级、不碰你的 `new_Core` 等真实解决方案、专用解决方案本身就是 git 回滚点。

## 工作流（两步）

```bash
# 1. 先同步 ribbon 引用的 JS 库（Phase 4），否则按钮的显隐/click 会回退到 Default
python -m framework_power webresource sync webresources --env dev

# 2. 编写 ribbon 定义（Python），再部署
python -m framework_power ribbon deploy ninebot-project/metadata_py/ribbons/new_order.py --env dev
```

ribbon 定义示例：
```python
from framework_power import RibbonScope
from framework_power.ribbon_xml import new_ribbon, add_button, hide_oob

RIBBON = add_button(
    new_ribbon("new_order"),
    "new_order.Approve",
    scope=RibbonScope.Form,                       # Form / HomepageGrid / SubGrid / Application
    label={"1033": "Approve", "2052": "审批"},     # 多语言 LocLabel
    tooltip={"1033": "Approve this order", "2052": "审批此订单"},
    library="new_/js/order/ribbon.js",            # Phase 4 命名，必须已存在
    on_click_fn="onApproveClick",                 # command 的 <Actions> JS
    show_fn="shouldShowApprove",                  # <DisplayRule><CustomRule> 显隐 JS（返回 bool）
    enable_fn="shouldEnableApprove",              # <EnableRule><CustomRule> 启用/禁用 JS
)
RIBBON = hide_oob(RIBBON, "Mscrm.Form.new_order.Deactivate")  # 默认 command_override（可逆）
```

## 显隐统一用 CustomRule（项目约定，按官方文档）

⚠️ **`<CustomRule>` 官方只归 `<EnableRule>`**：MS Learn `define-ribbon-display-rules` 列的 21 种 DisplayRule
类型里**没有** CustomRule；`define-ribbon-enable-rules` 才列了它，并明说 **"command bar 里 disabled 即 hidden"**。
Ribbon Workbench 严格按 schema 解析 → **放在 `<DisplayRule>` 里的 CustomRule 不会显示成 step**（这是
"SmokeBtn.DisplayRule 没绑 step"的根因）。

所以 `add_button(show_fn=, enable_fn=)` 和 `customise_command(show_fn=, enable_fn=)` **都生成 `<EnableRule>`+
`<CustomRule>`**（`show_fn` → `{id}.ShowRule`，`enable_fn` → `{id}.EnableRule`），接到 command 的 `<EnableRules>`。
JS 返回 bool（true=显示/启用，false=隐藏/禁用）。

**Default 非对称**：自定义按钮 `Default="false"`（fail-closed：JS 没加载就藏）；OOB customise `Default="true"`
（fail-OPEN：别因 JS bug 误藏自带按钮）。一个 JS 函数可驱动多个规则。

## ribbon JS 参数接收（`<CrmParameter>` → JS 形参，必读）

ribbon 把 `<CrmParameter Value="...">` **按声明顺序、位置地**传给 JS 函数（**无 `Name`**；顺序 = JS 形参顺序，
类型要匹配）。工具默认按 scope 选：**窗体按钮 `PrimaryControl`、网格按钮 `SelectedControl`**；用 `add_button` 的
`params=`（点击）/ `rule_params=`（显隐·启禁规则）覆盖。JS 这样接：

| `<CrmParameter Value>` | JS 形参 | 是什么 | 窗体 | 网格 |
|---|---|---|:-:|:-:|
| `PrimaryControl` | 第 1 个 | **formContext**（窗体上下文） | ✓ | — |
| `SelectedControl` | 第 1 个 | **gridContext**（网格上下文） | — | ✓ |
| `CommandProperties` | 下一个 | 事件信息（`SourceControlId` 等） | ✓ | ✓ |
| `SelectedControlSelectedItemIds` | 下一个 | 选中记录 id 数组 | — | ✓ |
| `SelectedControlSelectedItemCount` | 下一个 | 选中条数（int） | — | ✓ |
| `PrimaryEntityTypeName` | 下一个 | 实体逻辑名（string） | ✓ | ✓ |
| `FirstPrimaryItemId` | 下一个 | 当前记录 id（窗体） | ✓ | — |
| `OrgName` / `OrgLcid` / `UserLcid` | 下一个 | 组织名 / 语言代码 | ✓ | ✓ |

**窗体按钮**（`PrimaryControl` = formContext）：
```js
// 点击（command <Actions><JavaScriptFunction>）—— 不需要返回值
function onApprove(primaryControl) {
  var fc = primaryControl;                       // = formContext
  var status = fc.getAttribute("statuscode").getValue();
  if (status !== 1) return;
  fc.data.refresh();                             // 刷新
}
// 显隐（EnableRule <CustomRule>）—— 返回 bool（也支持 Promise，10s 超时按 false）
function shouldShowApprove(primaryControl) {
  return primaryControl.getAttribute("statuscode").getValue() === 1;
}
```

**网格按钮**（`SelectedControl` = gridContext；再声明 `SelectedControlSelectedItemIds` 拿选中 id）：
```js
function onBulkApprove(selectedControl, selectedIds) {  // SelectedControl + SelectedControlSelectedItemIds
  selectedIds.forEach(function (id) { /* ... */ });
  selectedControl.refresh();                    // gridContext.refresh()
}
function shouldShowBulk(selectedControl, selectedCount) {  // + SelectedControlSelectedItemCount
  return selectedCount > 0;                     // 选中了才启用
}
```

要点：
- **形参顺序 = `<CrmParameter Value=...>` 声明顺序**，无 `Name`（只有 `<Url>` 参数才要 `Name`）。
- **CustomRule（显隐/启禁）必须返回 `true`/`false`**（或 `Promise`）；`Default` 是 JS 没加载/超时的回退值
  （自定义按钮 `false`=藏，OOB customise `true`=保留默认）。
- **点击 `JavaScriptFunction` 不需要返回值**。
- **绑 JS 前 webresource 必须 sync+publish**（Phase 4），否则 CustomRule 回退 `Default`（藏/失效）。
- 参考实例：`ninebot-project/webresources/js/fpsmoke/ribbon.js`（formContext 用法注释）。

## 隐藏/覆盖 OOB 按钮（"自定义 D365 自带 ribbon"）—— 两种语义，别用错

**(A) 无条件隐藏（彻底移除）** —— `hide_oob(ribbon, oob_command_id)`：默认 `command_override`（可逆）覆盖该 OOB
按钮的 `<CommandDefinition>`，DisplayRules 设为互斥 `Mscrm.HideOnModern` + `Mscrm.ShowOnlyOnModern`（永假→
**永远隐藏**，丢掉原 command 规则）。另支持 `method="hide_custom_action"`（`<HideCustomAction>`，粘滞难撤销）。
`oob_command_id` 形如 `Mscrm.Form.account.Deactivate`。只在"这个 OOB 按钮我永远不想要"时用。

**(B) Customise Command —— 条件显隐（保留原行为，按数据状态）** —— `customise_command(...)`，对应 Ribbon
Workbench 右键 command → "Customise Command"：**保留** OOB 原 Display/Enable 规则 + **加一个 `<CustomRule>`**
（JS 返回 bool）→ 按钮按数据状态**条件**显隐/启禁。业务里最常见的需求（"某状态下藏掉 Deactivate/Delete"）用这个，
不要用 (A)。

```python
from framework_power.ribbon_xml import customise_command
RIBBON = customise_command(
    RIBBON, "Mscrm.Form.new_order.Deactivate",
    library="new_/js/order/ribbon.js",
    show_fn="shouldShowDeactivate",     # JS: true=显示 / false=隐藏（fail-OPEN：Default="true"）
    # enable_fn="shouldEnableDeactivate",  # 可选：true=启用 / false=禁用
    # preserve_display_rules=[...],         # 未 seed 的 command 必须显式传（见下）
    # actions_xml="<Actions>…</Actions>",   # 见下「点击保命」
)
```

- `preserve_display_rules` / `preserve_enable_rules`：要保留的 OOB 规则 id。默认按 command 后缀查
  `ribbon_xml.OOB_COMMAND_RULES`（已 seed `Deactivate`：`Mscrm.CanWritePrimary`/`PrimaryIsActive`/
  `PrimaryEntityHasStatecode`）。**未 seed 的 command 必须显式传**——工具读不到编译后 ribbon，规则得你在 RW 看一眼抄来。
- ⚠️ **点击保命（`actions_xml`）**：override **整体替换** OOB `<CommandDefinition>`，要保住点击就得把原
  `<Actions>…</Actions>` 原样塞回（`actions_xml=`）。从 Ribbon Workbench 复制该 command 的 `<Actions>` 粘进来。
  空 `actions_xml` 生成空 `<Actions/>`，**可能让点击失效**（`lint` 会告警）。

## 部署机制（关键，已 live 验证）

`ribbon deploy` 对每个 ribbon：
1. 确保**专用解决方案**存在（默认 `new_RibbonSoln`）+ 含目标实体（**shell-only**：`DoNotIncludeSubcomponents=true`，
   只含实体壳 + 其 `<RibbonDiffXml>`，不含窗体/视图）或全局 ribbon 的 Application Ribbons 组件。
2. `ExportSolution` → 解包 `customizations.xml` → **只替换该实体（或全局）的 `<RibbonDiffXml>`**（窗体/视图原样保留 → 导入对它们 no-op）。
3. `ImportSolution`（`OverwriteUnmanagedCustomizations=true`）。
4. 定向 `PublishXml`：实体 ribbon 走 `<entities><entity>X</entity></entities>`；全局走 `<ribbons><ribbon/></ribbons>`。

⚠️ **实体块的 `<Name>` 是 SchemaName（如 `new_FpFormSmoke`），不是逻辑名**——注入按 SchemaName 匹配
（工具自动用 `get_entity_metadata` 查）。这是已踩坑点。

## Location 约定（按钮"不显示"的头号坑，已 live 钉死）

注入位置**必须是真实存在的 group + `.Controls._children`**：
`Mscrm.{Form|HomepageGrid|SubGrid}.{entity}.{group}.Controls._children`（Application = `Mscrm.{group}.Controls._children`）。
`add_button(area=None)` 按 scope 选默认 group：**Form→`MainTab.Save`、HomepageGrid/SubGrid→`MainTab.Management`、
Application→`GlobalTab.New`**。**area 必须是真实 group**（form: Save/Actions/Collaborate；grid: Management/Actions）；
**自造 group（如 `MainTab.CustomAction`）会让按钮成为孤儿→永不渲染**（部署成功但运行时/maker 都看不到）。
想换组：`add_button(..., area="MainTab.Actions")`。

## 验证按钮要看"运行时"，不是 maker 设计器

经典 `RibbonDiffXml` 按钮**不会**出现在 maker 门户的"命令"(Power Fx) 设计器里——那是另一套 modern commanding
系统。**看按钮**：在 model-driven app 里打开该表的一条记录，看命令栏（默认 Save 组附近）。能用 Ribbon Workbench
加载专用解决方案（shell-only 才行）查看/微调。

## 两个"专用解决方案"硬约束（已 live 钉死）

1. **只含实体 shell**（`DoNotIncludeSubcomponents=true`）：否则实体拖入全部窗体/视图 → Ribbon Workbench 报
   "solution contains Entities that have all their sub-components included" 拒绝加载，且导出/导入变慢。
2. **实体若曾以含子组件方式加过**，重加会被幂等跳过 → 需先 `delete_solution`（unmanaged 删除只删容器、不删
   实体上的 ribbon diff）再重建。

## 多语言

`add_button(label={1033: "Approve", 2052: "审批"})` → `<LocLabels>` 里每个 `<Title languagecode description>`，
按钮 `LabelText="$LocLabels:<id>"` 引用。默认语言 zh-CN(2052)，可传 str（单语言）或 dict。

## 逆向

`ribbon reverse <entity>`（或 `--application`）= 导出专用解决方案 → 提取该实体的 `<RibbonDiffXml>` → 解析成
模型（**作者级 diff**，不是 RetrieveEntityRibbon 的编译后 ribbon——后者 404 且巨大）。

## CLI

```bash
python -m framework_power ribbon build <file>                          # 打印 RibbonDiffXml 片段（离线）
python -m framework_power ribbon show <file>                           # 模型摘要（离线）
python -m framework_power ribbon lint <file>                           # 约定检查（离线）
python -m framework_power ribbon plan <file> --env dev                 # 只读预演
python -m framework_power ribbon deploy <file> --env dev [--no-publish]
python -m framework_power ribbon reverse <entity|--application> --env dev
# 全局 --ribbon-solution new_RibbonSoln（专用解决方案）、--ribbons-dir metadata_py/ribbons/
```

## 不要做

- **不要**把 ribbon deploy 指向你的真实解决方案（如 `new_Core`）——会整包重导入，慢、≈Ribbon Workbench。
  用专用 `new_RibbonSoln`。
- **不要**在 JS 库同步前部署 ribbon——按钮显隐/click 会因库缺失回退到 `Default`（隐藏/无效）。
- **不要**凭空写 OOB command id——用 `Mscrm.{Form|HomepageGrid|SubGrid}.{entity}.<Button>` 形式。
- **不要**自造 group 名当 `area`（如 `MainTab.CustomAction`）——按钮成孤儿、永不渲染；用真实 group
  （`add_button` 默认 `MainTab.Save` 即可，见「Location 约定」）。
- **不要**靠 maker 门户"命令"(Power Fx) 设计器确认经典 ribbon 按钮——它不在那；**看运行时**（打开记录看命令栏）。
- 显隐**统一用 CustomRule**（项目约定）；不要手写其它 DisplayRule/EnableRule 类型。
- `True`/`False`（Python），不要 `true`/`false`。
