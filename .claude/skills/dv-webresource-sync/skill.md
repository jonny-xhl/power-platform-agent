---
name: dv-webresource-sync
description: 用 framework_power（Python 优先）把本地 web 资源目录（尤其 JS）批量同步/发布到 Dataverse，支持加入解决方案、按前缀逆向。当用户需要"同步 web 资源/js/css"、"频繁更新 JS 并发布"、"webresource 目录同步"、"逆向 web 资源到本地"时使用此技能。短语如"framework_power webresource sync/reverse/publish"、"ninebot-project/webresources/"、"new_/js/..."。
---

# Dataverse Web 资源目录同步（Python 优先 / framework_power）

本技能是 **framework_power** 的 **web 资源目录同步**入口（Phase 4），与表（Phase 1）、
解决方案（Phase 2）、安全角色权限（Phase 3）并列。专为**频繁更新**的 JS/CSS 等 web 资源设计。

## 是什么 / 不是什么

- **本地目录即事实来源**：把一个本地根目录下的 web 文件（js/css/html/svg/png...）批量同步到
  Dataverse（create/update base64 `content`），**非破坏**（只 create/update，不 delete）。
- **同步后精准发布**：默认调用**精准 `PublishXml`**（只发布本次同步的资源），让新内容立即生效 ——
  这是频繁改 JS 的关键。`--no-publish` 可跳过；另有独立 `publish <name>` 命令按名发布。
- **解决方案管理**：`--solution NAME` 把同步的资源加入解决方案（code 61，幂等）。
- **按前缀逆向**：`reverse` 把环境中的资源 base64 解码写回本地目录，默认只拉本发布商
  （`new_/`），可 `--name-prefix` 进一步收窄。

## 命名约定（已 live 验证，与现有资源一致）

web 资源名 = **`{prefix}_/{relpath}`**，relpath = 文件相对根目录的路径（正斜杠）。例如本地
`js/order/test.js` → `new_/js/order/test.js`；`js/common/XRM.com.js` → `new_/js/common/XRM.com.js`。
（环境里现有 28 个资源正是这个布局。）`webresourcetype`（1-11）独立由**文件扩展名**推导。

### 遗留名：`webresources.aliases.json`（默认不存在，由 `init` 播种为 `{}`）

约定**推不出**的既有资源名（历史上没按 `{prefix}_/{relpath}` 建的，例如环境里叫
`new_Orders.html` 而本地文件在 `html/orders.html`）必须在 sync 根的这个表里**显式声明**：

```json
{ "html/orders.html": "new_Orders.html" }
```

键 = relpath（正斜杠，同 `--include` 的写法）；值 = 环境中**真实**的名字。命中的文件按表里的名
同步 → `deploy` 按名查得到既有记录 → **更新它，而不是新建一个重复资源**。未列出的文件（含所有
新增文件）继续走约定，**不需要任何登记**。`reverse` 也认这张表，往返落在同一个本地路径。

不这么做会怎样：约定名 `new_/html/orders.html` 在环境里查不到 → `sync` **新建**一个重复资源，
而你所有既有调用方（ribbon/form）仍然加载旧的 `new_Orders.html` —— 改了等于没改。
**改完先 `plan`，确认是 `would_update` 而不是 `would_create`。**

## 类型映射（扩展名 → webresourcetype）

`.js`→JScript(3)、`.css`→Css(2)、`.htm`/`.html`→WebPage(1)、`.xml`→Xml(4)、`.png`→Png(5)、
`.jpg`/`.jpeg`→Jpg(6)、`.gif`→Gif(7)、`.xap`→Silverlight(8)、`.xsl`/`.xslt`→Xsl(9)、
`.ico`→Ico(10)、`.svg`→Svg(11)。**未知扩展名跳过并告警**；dotfile/dot-dir 跳过。

## 发布语义（关键，已 live 验证）

- **`PublishXml`（精准）**：`POST PublishXml`，body `{"ParameterXml":
  "<importexportxml><webresources><webresource>{id}</webresource>...</webresources>
  </importexportxml>"}`。只发布列出的资源 + 刷新引用它的 form/ribbon 绑定 → 新 JS 立即生效。
- 与 `PublishAllXml`（组织级，发布全部未托管自定义项）不同；频繁改 JS 用精准发布。
- 新建资源也需发布才生效；`sync` 默认在 create/update 后自动精准发布。

## CLI

```bash
python -m framework_power webresource scan [<dir>]                          # 离线：列出文件→名字/类型
python -m framework_power webresource plan   [<dir>] --env dev              # 只读预演
python -m framework_power webresource sync   [<dir>] --env dev [--solution NAME] [--no-publish]
python -m framework_power webresource reverse [<dir>] --env dev [--name-prefix PREFIX]
python -m framework_power webresource publish <name> [<name>...] --env dev  # 按名解析 id → 精准发布
# <dir> 默认 ninebot-project/webresources/；全局可改根目录
```

## 工作流

```
本地 ninebot-project/webresources/（按 type/module 组织，如 js/order/test.js）
  → framework_power webresource scan           （离线：核对将生成的名字）
  → framework_power webresource plan           （只读预演）
  → framework_power webresource sync           （create/update + 自动精准发布）
  → （可选）sync --solution new_Core           （加入解决方案，code 61）
频繁改 JS：改文件 → 再 sync（update + 精准发布），秒级生效
逆向参考：framework_power webresource reverse --name-prefix new_/js/   （环境 → 本地，按前缀）
```

## 硬性约束

- `sync` 非破坏：只 create/update；未列出的 right/资源不动；delete 是独立的 `delete_webresource`
  客户端方法（用于显式清理），不在 `sync` 内。
- `reverse` 默认按 `{prefix}_/` 收窄（只拉本发布商），避免拉全环境；可 `--name-prefix` 再收窄。
- 名字必须以 `{prefix}_` 开头（`new_/...`）；否则视为标准组件跳过。**别名表的值也受此约束**
  （缺前缀会在 `scan` 阶段 warning，否则 `deploy` 会把它当标准资源静默跳过）。
- 别名表内容非法（不是 JSON 对象 / 值空 / 值非字符串）→ **`ValueError` 直接失败**，不回落成约定名
  ——静默回落正是制造重复资源的那条路径。键拼错（没有对应文件）会 warning（`--include` 过滤时不报）。
- content 是 base64 字符串；本地文件按**原始字节**读/写（逆向写字节保真，不转码）。
- `True`/`False`（Python），不要 `true`/`false`。

## 不要做

- 不要用 `PublishAllXml` 做频繁 JS 发布 —— 用 `sync`（精准 `PublishXml`）或 `publish <name>`。
- 不要假设 collection 查询默认返回 `content` —— 逆向查询走 `list_webresources_by_prefix`，
  显式 `$select=...content`。
- 不要把未知扩展名当 web 资源同步（会报错或类型错）；只处理映射表内的扩展名。
- 不要同步 dotfile / `.git` 等（scan 已自动跳过）。
