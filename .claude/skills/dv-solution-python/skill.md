---
name: dv-solution-python
description: 用 framework_power（Python 优先）管理 Power Platform 解决方案（Solution）的创建、部署、逆向。当用户需要"创建解决方案"、"把表/选项集/Web 资源/表单/视图/插件打包进解决方案"、"解决方案部署到 Dataverse"、"逆向导出解决方案"、处理发布商（Publisher）时使用此技能。短语如"framework_power solution deploy/reverse"、"ninebot-project/metadata_py/solutions"、"解决方案同步 python"。
---

# Power Platform 解决方案管理（Python 优先 / framework_power）

本技能是 **framework_power**（Python 优先的 Dataverse 部署库）的**解决方案（Solution）**管理
入口，对应 Phase 1 的表管理（`dv-model-to-python` / `dv-reverse-metadata`）。它替代旧的
> legacy YAML/Agent 路径（`dv-solution` skill + `framework/`）已于 2026-08-31 移除；本 skill 是解决方案域唯一路径。

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

- 自包含包；Web API client 在 `framework_power/client/`（本仓库唯一引擎）。
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
| workflow（custom action 定义） | 29 | workflow |
| view | 26 | savedquery |
| form | 60 | systemform |
| webresource | 61 | webresource |
| pluginassembly | 91 | pluginassembly（降级路径） |
| sdkmessageprocessingstep | 92 | sdkmessageprocessingstep（含 image 的宿主） |
| plugintype | 90 | plugintype（一般不单独加） |
| pluginpackage（NuGet） | 10030 | pluginpackage（**包路径的解决方案单元**；加 91 会 405） |

## Dataverse 关键行为（务必遵守）

- **依赖顺序**：发布商 → 解决方案 → 组件 → 加入 → 发布。不发布则运行时不可用。
- **PublishAllXml 是组织级**：发布**所有**未托管自定义项，无法只发布单个解决方案。
- **加入组件前组件必须已存在**：`AddSolutionComponent` 有 `@retry_on_metadata_error`，组件
  创建后有小延迟再加入。
- **全局选项集选项 create-only**：选项变更需 `InsertOptionValue`/`UpdateOptionValue` 或 maker
  portal；deployer 对此报告 `manual_update_required`。
- **错误的类型代码**会导致 "Cannot add ... because it does not exist"。
- **【2026-09-11 重要】判断"组件是否已在方案中"不能只看 `solutioncomponents` 表**：该表只列
  **显式添加**的组件。若实体是以 `rootcomponentbehavior=0`（**包含子组件 / IncludeSubcomponents**）
  加入方案的，其实体的**视图/窗体/属性等子组件不单独建记录**，但仍**随方案导出/导入一起传播**。
  正确判据（两条都看）：
  1. 目标**实体**在该方案中的组件记录及其行为：
     `solutioncomponents(<实体组件id>)?$select=componenttype,rootcomponentbehavior,_solutionid_value`
     → `0=IncludeSubcomponents` / `1=DoNotIncludeSubcomponents` / `2=IncludeAsShellOnly`。
     取实体组件 id 的简便方法：`AddSolutionComponent(SolutionUniqueName, ComponentType=1, ComponentId=<实体 MetadataId>)`
     —— 幂等调用会直接返回该实体在方案中的组件记录 id。
  2. `solutioncomponents?$filter=_solutionid_value eq <sid> and componenttype eq 26` 只用于找**显式**视图组件。
  ⇒ 对**实体的子组件**（视图/窗体/属性…）调 `AddSolutionComponent` 是**幂等**的：Dataverse 返回**根组件
  （实体）的记录 id**，不新建记录。看到"HTTP 200 但表里查不到新记录"**不要误判为失败** —— 组件其实已被
  根组件的 IncludeSubcomponents 覆盖。

## 不要做

- **【ADR-013】不要在未备份的情况下改环境**：写操作前 `pp env-guard backup <解决方案> --env <env> --note "…"`
  （solution ZIP + 插件注册快照 + 台账）。恢复时先读 `docs/env_backup/CHANGELOG.md`。
- 不要逆向覆盖 `ninebot-project/metadata_py/solutions/` 下他人维护的定义前先确认。
- 不要让 `solution deploy` 变成破坏性操作。
- 不要在库内生成/改写 FormXml/FetchXml/LayoutXml（保持不透明字符串）。
- 旧路径 `dv-solution`（YAML/Agent）仍存在，但新工作请用本 Python 优先路径。
