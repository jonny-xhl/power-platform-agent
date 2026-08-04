---
name: dv-solution-python
description: 用 framework_power（Python 优先）管理 Power Platform 解决方案（Solution）的创建、部署、逆向。当用户需要"创建解决方案"、"把表/选项集/Web 资源/表单/视图/插件打包进解决方案"、"解决方案部署到 Dataverse"、"逆向导出解决方案"、处理发布商（Publisher）时使用此技能。短语如"framework_power solution deploy/reverse"、"ninebot-project/metadata_py/solutions"、"解决方案同步 python"。
---

# Power Platform 解决方案管理（Python 优先 / framework_power）

本技能是 **framework_power**（Python 优先的 Dataverse 部署库）的**解决方案（Solution）**管理
入口，对应 Phase 1 的表管理（`dv-model-to-python` / `dv-reverse-metadata`）。它替代旧的
YAML/Agent 路径（`dv-solution` skill + `framework/agents/solution_agent.py`）用于解决方案域。

## 是什么

把一个解决方案定义为一个**类型化的 Python 模型**（`Solution`），模型即"单一事实来源"：

- **正向 `solution deploy`**：5 步同步到 Dataverse ——
  发布商 → 解决方案对象 → 按依赖顺序部署组件 → 把自定义组件加入解决方案 → 发布。
- **逆向 `solution reverse`**：把环境中已存在的解决方案导出为本地 Python 定义（全量快照）。
- **双向单文件**：同一份 `ninebot-project/metadata_py/solutions/<unique_name>.py` 既可被逆向覆盖，也可被正向同步。

组件类型按 `framework_power/components/` 注册表分发：
`table`（已有，复用 `deploy_table`）/ `optionset` / `webresource` / `form` / `view` / `plugin`。
表单/视图的 `FormXml`/`FetchXml`/`LayoutXml` 与插件 DLL、Web 资源内容都是**不透明字符串**
（base64/原始 XML），库**不生成也不解析**它们；作者提供，逆向原样捕获。

## 硬性约束

- 与 `framework/` 完全隔离（不 import、不改）；复用代码在 `framework_power/client/`。
- **发布商前缀**（默认 `new`）决定"自定义"组件；标准/系统组件（无前缀）在正向同步时**自动跳过**
  → 全量快照正向同步是**幂等且安全**的。
- `solution deploy` **非破坏**：只 create/update/add，从不 delete。
- 每个解决方案必须关联一个发布商（`Publisher` 内联 或 `publisher_key` 引用 `ninebot-project/config/publishers.yaml`）。
- 布尔值用 Python `True`/`False`。

## 定义文件结构

`ninebot-project/metadata_py/solutions/<unique_name>.py`，导出 `SOLUTION: Solution`：

```python
from framework_power import Publisher, Solution, ComponentRef

SOLUTION: Solution = Solution(
    unique_name="new_Core",
    friendly_name="Core",
    version="1.0.0.0",
    publisher_key="default",          # 或内联 publisher=Publisher(name=..., display_name=..., prefix="new")
    tables=["new_projectbudget"],     # NAME REFS -> ninebot-project/metadata_py/tables/<name>.py（由 registry 解析）
    # 选项集/Web 资源/表单/视图/插件随各 wave 作为内联模型加入：
    # optionsets=[...], webresources=[...], forms=[...], views=[...], plugins=[...],
    refs=[ComponentRef(type="webresource", object_id="<guid>")],  # 显式 id 的 add-only 引用
)
```

- `tables` 是**名称引用**（指向 `ninebot-project/metadata_py/tables/<name>.py`），由表 registry 在部署时解析、
  按依赖顺序部署（复用 `deploy_table`）。
- 其它组件类型**内联**在解决方案文件里。

## 5 步部署流程

```
1. 发布商：resolve_publisher -> ensure_publisher_exists（内联 > config key > current）
2. 解决方案对象：不存在则 create，存在且版本变化则 update_version
3. 部署组件：按依赖顺序 optionset -> table -> webresource -> form -> view -> plugin
   （table 经 deploy_table；其它经各自类型 deployer）
4. 加入解决方案：自定义组件 resolve_id -> AddSolutionComponent（"已存在"=良性跳过）
5. 发布：PublishAllXml（发布组织内所有未托管自定义项，非单解决方案）
```

## CLI

```bash
python -m framework_power solution list                          # 发现 ninebot-project/metadata_py/solutions/*.py
python -m framework_power solution show <name>                   # 打印定义摘要（离线）
python -m framework_power solution lint [<name>]                 # 离线约定校验
python -m framework_power solution plan <name> --env dev         # 只读预演
python -m framework_power solution deploy <name> --env dev       # 正向同步（5 步）
python -m framework_power solution reverse <unique_name> --env dev  # 逆向导出（全量快照）
python -m framework_power solution add-component <sol> --type <t> [--name <n> | --id <guid>] --env dev
python -m framework_power solution publish --env dev             # PublishAllXml
# 全局参数：--solutions-dir <dir>（默认 metadata_py/solutions）
```

## 工作流

```
定义：ninebot-project/metadata_py/solutions/<name>.py（AI 按契约生成，或由逆向生成）
  → framework_power solution lint     （离线门）
  → framework_power solution plan     （只读预演）
  → framework_power solution deploy   （同步到环境）
逆向参考：framework_power solution reverse <unique_name>   （环境 → 本地）
```

## 组件类型代码（AddSolutionComponent ComponentType）

| key | 代码 | 实体 |
|-----|------|------|
| table | 1 | EntityMetadata |
| optionset（全局） | 9 | OptionSetMetadata |
| view | 26 | savedquery |
| form | 60 | systemform |
| webresource | 61 | webresource |
| pluginassembly | 90 / step 92 / action 91 | pluginassembly + sdkmessageprocessingstep |

## Dataverse 关键行为（务必遵守）

- **依赖顺序**：发布商 → 解决方案 → 组件 → 加入 → 发布。不发布则运行时不可用。
- **PublishAllXml 是组织级**：发布**所有**未托管自定义项，无法只发布单个解决方案。
- **加入组件前组件必须已存在**：`AddSolutionComponent` 有 `@retry_on_metadata_error`，组件
  创建后有小延迟再加入。
- **全局选项集选项 create-only**：选项变更需 `InsertOptionValue`/`UpdateOptionValue` 或 maker
  portal；deployer 对此报告 `manual_update_required`。
- **错误的类型代码**会导致 "Cannot add ... because it does not exist"。

## 不要做

- 不要 import 或修改 `framework/`、`ninebot-project/metadata/`。
- 不要让 `solution deploy` 变成破坏性操作。
- 不要在库内生成/改写 FormXml/FetchXml/LayoutXml（保持不透明字符串）。
- 旧路径 `dv-solution`（YAML/Agent）仍存在，但新工作请用本 Python 优先路径。
