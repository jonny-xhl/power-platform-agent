# Figma 设计系统集成规则（Design System Rules for Figma MCP）

> 本文档供 Claude（通过 Figma MCP）在本仓库中工作使用。它不是一份通用前端规范，而是
> **针对本仓库实际结构**的 Figma→代码翻译规则。先读 §0（代码库现实），否则会按通用前端
> 假设走错方向。

---

## 0. 代码库现实（先读这一节）

本仓库 **不是** 典型 Web 前端。它是 **Power Platform / Dataverse 工具链**：一个 Python MCP
服务器 + Python 优先的 Dataverse 部署库（`framework_power/`）+ C# 插件。"前端"不是 React/Vue SPA，
而是 **Microsoft Dataverse Model-Driven App UI**，由本仓库管理的三类具体产物构成：

1. **Web 资源** — 原生 JS / CSS / HTML / SVG，同步到 Dataverse（`webresources/`，Phase 4）
2. **窗体布局** — FormXml，建模为结构化 Python dataclass（Phase 5）
3. **视图布局** — FetchXml + LayoutXml，结构化 Python（Phase 6）
4. **Ribbon 定制** — RibbonDiffXml，结构化 Python（Phase 7）

**本仓库不存在的东西（不要假设存在）：**
- ❌ `package.json`、Node.js、bundler（webpack/vite/rollup）、transpiler（babel/tsc 构建步）
- ❌ React / Vue / Svelte / Angular / Web Components
- ❌ CSS Modules / Styled Components / Emotion / Tailwind / Sass
- ❌ 设计令牌流水线（无 Style Dictionary、无 `design-tokens.json`、无 CSS 变量系统）
- ❌ 组件 Storybook（Storybook / Ladle / Cosmos）
- ❌ 图标库 / sprite 系统（仅有一个临时 SVG）
- ❌ CDN —— 资源由 Dataverse 作为 web 资源下发

因此，本仓库的 Figma→代码集成 **不是**「把 Figma 令牌导入令牌流水线再渲染 React 组件」，而是：
**把 Figma 设计翻译为 (a) 经 Python `Form` builder 生成的 FormXml 布局、(b) 原生 CSS/JS web 资源、
或 (c) 自定义页面的 HTML web 资源。** 下文逐项映射。

---

## 1. 令牌定义（Token Definitions）

**没有正式令牌系统。** 令牌是隐式、分散的硬编码值。

### 颜色
两个 CSS 文件用**不同**的调色板，互相不一致：

- **`webresources/shared/css/XRM.Common.css`**（共享库，**Fluent 风格，新工作以此为准**）：
  - 主色 `#0078d4`（Fluent 主蓝），hover `#106ebe`
  - 文本 `#323130`（主）/ `#605e5c`（次）/ `#495057`
  - 语义：info `#e3f2fd`+`#2196f3`、warning `#fff3e0`+`#ff9800`、error `#ffebee`+`#f44336`、success `#d4edda`+`#155724`
  - 中性/边框 `#e1dfdd` / `#f3f2f1` / `#edebe9`
  - 深色模式覆盖在 `@media (prefers-color-scheme: dark)`

- **`webresources/css/account_form.css`**（实体级，**Bootstrap 风格，视为遗留**）：
  - `#007bff` / `#28a745` / `#dc3545` / `#ffc107` / `#6c757d` / `#17a2b8` / `#6f42c1`

### 字体
`'Segoe UI', Tahoma, Geneva, Verdana, sans-serif`（`account_form.css`）。共享库不设 font-family
（继承 Dataverse shell）。字号是临时 px（12/14/16/18/24/32）。

### 间距
共享库有**唯一真正的令牌式系统** —— 4px 基准刻度的工具类：
```css
.xrm-common-mt-0..4 { margin-top: 0/4/8/12/16px; }   /* 同 mb / p */
```

### Figma 集成指引
- **没有自动令牌同步**。若 Figma 文件发布变量（颜色/间距），必须**手工**映射进 `XRM.Common.css`
  （或新建 tokens CSS）。
- Figma 颜色样式 → `XRM.Common.css` 语义类（`.xrm-common-badge.success` 等）的 hex 值。
- Figma 间距 → 既有 4px 刻度（`mt-1`..`mt-4`），不要引入并行刻度。
- **除非用户明确要求**，不要新建 `design-tokens.json` + Style Dictionary 流水线 —— 对当前架构是 greenfield，
  超出范围。

---

## 2. 组件库（Component Library）

**没有 React/Vue 组件库。** "组件"有两个含义：

### (a) CSS 组件类（`XRM.Common.css`，前缀 `xrm-common-`）—— 可复用视觉组件
- 通知 `.xrm-common-notification`（+ `.info`/`.warning`/`.error`）
- 进度 `.xrm-common-progress-overlay` / `.xrm-common-spinner`
- 对话框 `.xrm-common-dialog-overlay` / `.xrm-common-dialog`（+ header/body/footer）/ `.xrm-common-dialog-button.primary`/`.secondary`
- 徽标 `.xrm-common-badge`（+ `.success`/`.info`/`.warning`/`.error`）
- 字段状态 `.xrm-common-field-error`/`-warning`/`-success`/`-readonly`
- 工具类 `.xrm-common-hidden`/`-invisible`/`-text-center`… + 间距工具类

### (b) 结构化布局原语（`framework_power/components/models.py`，Python dataclass）—— 窗体/视图/ribbon 的"组件"
- **窗体**：`Form` / `FormTab` / `FormColumn` / `FormSection` / `FormRow` / `FormCell` / `FormControl` /
  `FormLabel` / `FormLibrary` / `FormEvent` / `FormEventHandler`
- **视图**：`View` / `ViewColumn` / `ViewOrder` / `ViewCondition` / `ViewFilter` / `ViewLinkEntity`
- **Ribbon**：`RibbonDefinition` / `RibbonButton` / `RibbonCommand` / `RibbonCustomRule` /
  `RibbonLocLabel` / `RibbonScope`

窗体 builder（`framework_power/form_xml.py`：`new_form`/`add_tab`/`add_section`/`add_field`/
`add_library`/`add_event_handler`）等价于「从结构化 props 渲染窗体布局」。`add_field` 按 `Column.type`
选 `classid`（控件类型）：text/optionset/lookup/datetime/integer/url/boolean/memo。

### (c) JS 行为库（`XRM.Common.js`）
暴露 `Form`/`Data`/`Nav`/`UI`/`Ctx`/`Util` 模块 + 链式 `$()`。是行为封装，不是视觉组件。

### 无 Storybook
示例散落：`webresources/js/account_handler.js`（窗体脚本范式）、`webresources/html/account_dashboard.html`（HTML 页范式）。

### Figma 集成指引
- **窗体布局**：Figma 窗体屏 → 把 tab/section/字段排列翻译成 `Form`/`FormTab`/`FormSection`/`FormRow`/`FormCell`
  （用 builder），再 `form deploy`。字段控件类型经 `add_field` classid 映射。
- **独立 UI（对话框/徽标/通知）**：复用既有 `.xrm-common-*` 类，**不要**从 Figma 重新生成。
- 用 **Figma Code Connect** 把 Figma 组件绑到 (a) CSS 类名字符串，或 (b) Python 模型构造调用（若要设计→FormXml 自动化）。

---

## 3. 框架与库（Frameworks & Libraries）

- **主语言**：Python 3.9+（MCP 服务器、`framework_power`、agents）。类型注解必填，`mypy` 严格，
  `black` + `flake8 --max-line-length=120`。
- **插件语言**：C# / .NET（`plugins/`，net462 标准）。
- **前端框架**：**无**。原生 JS 用 IIFE 命名空间；唯一"框架"是 Dataverse Xrm 客户端 API
  （`formContext`、`Xrm.WebApi`、`Xrm.Navigation`、`Xrm.Utility`）。
- **样式**：原生 CSS（无预处理器、无 CSS-in-JS）。
- **构建系统**：
  - Python：`pip install -e .`（setup.py），无 bundler。
  - 前端：**无**。JS 原样下发（`XRM.Common.js` 压缩版与 `XRM.Common.debug.js` 注释版手工维护）。
  - 插件：`dotnet build` + `dotnet pack`（由 `framework_power/client/plugin_build.py` 驱动）。

### Figma 集成指引
- 不要为"对齐 Figma"而引入 JS 框架或 bundler —— 设计必须能用原生 JS/CSS 或 FormXml 表达。
- 生成的代码须过 `flake8 --max-line-length=120`（Python）并遵循 IIFE 命名空间范式（JS）。

---

## 4. 资源管理（Asset Management）

- 资源是 **Dataverse web 资源**，不是文件系统/CDN。`framework_power` Phase 4 把本地 `webresources/`
  目录以 base64 `content` 同步到 Dataverse。
- **命名**：`{publisher}_/{relpath}` → 如 `webresources/js/order/test.js` 成为 Dataverse 资源
  `new_/js/order/test.js`（发布商前缀 `new` 取自 `config/publishers.yaml`）。relpath 用正斜杠。
- **扩展名→类型**：`.js`→3、`.css`→2、`.html`→1、`.png`→5、`.jpg`→6、`.gif`→7、`.svg`→11、
  `.ico`→10、`.xml`→4、`.xsl`/`.xslt`→9。
- **引用**：HTML 内 `<link rel="stylesheet" href="../css/account_form.css">`（相对）或
  `../ClientGlobalContext.js.aspx`（Dataverse 提供）；FormXml/ribbon 内 `$webresource:new_/js/...` 或裸 `new_/js/...`。
- **发布**：同步后 `PublishXml` 只发布本次资源（精准、秒级），区别于组织级 `PublishAllXml`。
- **无 CDN、无优化步**。图片由 Dataverse 原样下发。

### Figma 集成指引
- 从 Figma 导出图片/图标 → 存到 `webresources/img/<feature>/` → `framework_power webresource sync` 部署为 `new_/img/<feature>/...`。
- 在 HTML/JS 中用相对路径或 `new_/img/...` 名引用。
- Figma 的 SVG 放进 `webresources/img/`（类型 11），不要内联为 data URI（除非极小）。

---

## 5. 图标系统（Icon System）

**没有图标系统。** 仅一个 SVG：`webresources/img/fpsmoke/icon.svg`。无 sprite、无图标字体、
无 `@svg-icons` 导入，除 `{prefix}_/{relpath}` web 资源命名外无图标命名约定。

现有 CSS 里的状态/类型"图标"是 **CSS 形状**（如 `.account-type-icon` 是 `background-color` 圆形），
不是图标资产。

### Figma 集成指引
- Figma 图标导出为单独 SVG → `webresources/img/<feature>/`。
- 命名遵循 web 资源约定：文件 `webresources/img/<feature>/<name>.svg` → Dataverse `new_/img/<feature>/<name>.svg`。
- HTML 引用：`<img src="../img/<feature>/<name>.svg">` 或内联 `<svg>`。
- ribbon 引用：按名引用 image webresource。
- 若需要成套图标，建议建立 `webresources/img/icons/` + 命名约定（`<set>-<name>.svg`，如
  `fluent-account.svg`）—— 但这是 greenfield，**建库前先问用户**。

---

## 6. 样式方法（Styling Approach）

- **方法**：原生 CSS + **命名空间前缀 BEM-ish** 类名。共享库用 `xrm-common-` 前缀；实体 CSS 用 `account-` 前缀。
  规避与 Dataverse shell 的样式冲突。
- **无全局 reset** —— 样式作用域在组件类上。Dataverse shell 提供自己的全局样式（Fluent）。
- **特异性**：避免 `!important`，除字段状态覆盖（`.xrm-common-field-error` 用 `!important` 压过
  Dataverse 字段样式）。优先用父命名空间提特异性。
- **响应式**：`@media (max-width: 768px)`（移动端）、`@media print`（打印）、`@media (prefers-color-scheme: dark)`（深色，仅共享库）。
- **动画**：`@keyframes` `slideIn`/`slideUp`/`fadeIn`/`spin`/`pulse`。
- **窗体网格**：Model-Driven App 窗体用 **12 列网格**；cell `width` 是字符串 `"1"`–`"12"`
  （`"2"` = 2/12 宽）。详见 `dv-frontend` SKILL §二。
- **窗体样式约束**：窗体大部分 chrome（tab/section/字段）由 Dataverse 渲染，**不能完全重设样式** ——
  自定义 CSS 主要影响内嵌 web 资源和注入元素。**不要试图按 Figma 整体换肤窗体。**

### Figma 集成指引
- Figma 组件翻译为 `.xrm-common-*` 类（需要新变体时扩展共享 CSS）。
- 自定义 HTML 页（仪表板）遵循 `account_dashboard.html` 范式：`<link>` 共享 CSS + 实体 CSS + 页面级内联 `<style>`。
- 窗体字段放置用 12 列网格（`FormCell` width）。
- 新工作用 Fluent 调色板（`#0078d4` 主色），不用 `account_form.css` 的 Bootstrap 调色板。

---

## 7. 项目结构（Project Structure）

```
power-platform-agent/
├── framework_power/        # Python 优先 Dataverse 部署库（P1–P9）
│   ├── models.py           # Table/Column/Relationship 类型化模型
│   ├── components/         # 解决方案组件类型（注册表）
│   │   ├── models.py       # Form/View/Ribbon/Plugin 结构化模型 ← "组件库"
│   │   ├── form.py view.py ribbon.py plugin.py optionset.py webresource.py
│   │   └── _common.py
│   ├── form_xml.py view_xml.py ribbon_xml.py   # XML 解析/序列化（无损往返）
│   ├── form_sync.py view_sync.py ribbon_sync.py webresource_sync.py optionset_sync.py
│   ├── client/             # 隔离的传输/认证拷贝（plugin_build.py 在此）
│   └── cli.py              # pp ...
├── metadata_py/            # Python 元数据定义（单一事实来源）
│   ├── tables/ solutions/ forms/ views/ roles/ optionsets/
│   └── project.py          # Phase 9 工作流清单
├── webresources/           # ← "前端"（原生 JS/CSS/HTML/SVG）
│   ├── shared/js/XRM.Common.js + .debug.js + .d.ts
│   ├── shared/css/XRM.Common.css
│   ├── shared/js/XRM.Options*.js   # OptionSet 语义化常量
│   ├── js/<entity>/*.js            # 窗体/事件处理器（IIFE 命名空间）
│   ├── css/*.css                   # 实体级样式
│   ├── html/*.html                 # 自定义页面/仪表板
│   └── img/<feature>/*.svg
├── plugins/                # C# .NET 插件工程（net462）
├── metadata/               # （遗留）YAML 元数据
├── config/                 # environments.yaml / publishers.yaml / pipeline.yaml ...
├── .claude/skills/         # dv-* 技能（dv-form-python / dv-frontend ...）
├── test/                   # pytest（test/unit/test_framework_power/）
└── docs/                   # 指南 + 规范
```

### 按功能组织
一个 feature 跨多个目录：
- `metadata_py/tables/<entity>.py`（表定义）
- `metadata_py/forms/<entity>__<form>.py`（窗体布局）
- `metadata_py/views/<entity>__<view>.py`（视图）
- `webresources/js/<entity>/<entity>.form.js` + `<entity>.optionset.js`（行为）
- `webresources/css/<entity>_form.css`（样式，按需）
- `plugins/<PluginProject>/`（服务端逻辑）

部署链（Phase 9）：`optionsets → tables → webresources → plugins → forms → views → roles → ribbon`，
由 `metadata_py/project.py` 驱动，跨两个解决方案（主 + ribbon）。

---

## Figma → 代码翻译手册（具体）

| Figma 产物 | 本仓库目标 | 工具/技能 |
|---|---|---|
| 窗体/屏幕稿 | `Form` 模型（builder）→ `form deploy` | `dv-form-python` |
| 视图/列表稿 | `View` 模型（builder）→ `view deploy` | `dv-view-python` |
| Ribbon 按钮稿 | `RibbonDefinition` → `ribbon deploy` | `dv-ribbon-python` |
| 颜色/间距令牌 | 手工编辑 `XRM.Common.css`（Fluent 调色板） | — |
| 通知/对话框/徽标组件 | 复用 `.xrm-common-*` 类（Code Connect） | `figma-code-connect` |
| 图标资产 | SVG → `webresources/img/<feature>/` → `webresource sync` | `dv-webresource-sync` |
| 自定义 HTML 页（仪表板） | `webresources/html/*.html` + 实体 CSS | `dv-frontend` |
| 窗体事件/交互 | `webresources/js/<entity>/<entity>.form.js`（IIFE + XRM.Common） | `dv-frontend` |

### 拿到 Figma URL 的工作流
1. `get_design_context` / `get_screenshot` 读设计。
2. **分类**：是**窗体布局**、**视图**、**ribbon**，还是**自定义 HTML 页**？（Dataverse UI 多为窗体/视图/ribbon，不是自由 HTML。）
3. 窗体/视图/ribbon：用对应 `framework_power` builder 把设计表达成 Python 模型，再 `lint` → `plan` → `deploy`。
   **不要手写 FormXml/FetchXml。**
4. 自定义 HTML：按 `account_dashboard.html` 范式写 `webresources/html/*.html`，复用 `XRM.Common.css`，加实体 CSS。
5. 图标/图片：导出到 `webresources/img/`，`webresource sync`。
6. 发布：窗体/视图改 → `publish_entity`；web 资源 → 精准 `PublishXml`；ribbon → 经解决方案导入（Phase 7）。

---

## 必须遵守的硬约束（来自 CLAUDE.md）

- `deploy` **非破坏**（只 create/update，从不 delete）。
- 标准实体（account/contact/…）受保护 —— 跳过，不重设样式。
- 命名：自定义组件 `lowercase` + `_` 分隔符 + `new_` 前缀；web 资源 `{prefix}_/{relpath}`。
- JS：IIFE 命名空间、`'use strict'`，经 `XRM.Common` 而非裸 `Xrm`。
- CSS：命名空间前缀类名，避免 `!important` 和全局选择器。
- Python：`True`/`False`、类型注解、`flake8 --max-line-length=120`、`mypy --explicit-package-bases`。
- **未经用户明确要求，不要引入** React/Vue、bundler、令牌流水线。

---

## 关键文件速查

| 用途 | 路径 |
|---|---|
| 共享 CSS 组件库 | `webresources/shared/css/XRM.Common.css` |
| 共享 JS 行为库（压缩） | `webresources/shared/js/XRM.Common.js` |
| 共享 JS 行为库（注释） | `webresources/shared/js/XRM.Common.debug.js` |
| TS 类型定义 | `webresources/shared/js/XRM.Common.d.ts` |
| OptionSet 语义常量 | `webresources/shared/js/XRM.Options*.js` |
| 实体窗体脚本范式 | `webresources/js/account_handler.js` |
| 实体 CSS 范式（遗留调色板） | `webresources/css/account_form.css` |
| HTML 仪表板范式 | `webresources/html/account_dashboard.html` |
| 结构化窗体模型 | `framework_power/components/models.py`（`Form*`） |
| 窗体 XML 解析/序列化 | `framework_power/form_xml.py` |
| 视图 XML 解析/序列化 | `framework_power/view_xml.py` |
| Ribbon XML 解析/序列化 | `framework_power/ribbon_xml.py` |
| 前端开发技能 | `.claude/skills/dv-frontend/SKILL.md` |
| 发布商 + 命名规则 | `config/publishers.yaml` |
