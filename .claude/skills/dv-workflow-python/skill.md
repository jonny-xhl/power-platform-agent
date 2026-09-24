---
name: dv-workflow-python
description: 用 framework_power（Python 优先）跨阶段编排开发工作流——一个 project.py 清单驱动整条开发链（Global Optionset → Entity → Relationship → webresource → plugin → form → view → [roles] → ribbon），跨两个解决方案（主解决方案 + 专用 ribbon 解决方案），每个阶段自管 solution 归属。当用户需要"开发流程/workflow"、"一条命令部署全部"、"整合各阶段"、"framework_power workflow deploy/plan/lint"、"project.py 清单"时使用。
---

# Dataverse 开发工作流编排（Python 优先 / framework_power）

本技能是 **framework_power** 的 **跨阶段编排入口（Phase 9）**。把 Phase 1–8 的孤立 deploy 命令
串成一条按依赖顺序的开发链，由**一个显式清单** `ninebot-project/metadata_py/project.py` 驱动，跨**两个解决方案**。

## 核心事实

- **整条链（用户确认的最长链路）**：

  ```
  Global Optionset → Entity(+Relationship) → webresource → plugin → form → view → [roles] → ribbon
  |<----------------------- 主解决方案 ----------------------->|            |<-- 专用 ribbon 解决方案 -->|
  ```

- **两个解决方案（硬约束）**：主解决方案（`main_solution`）装**除 ribbon 外的一切**；
  **ribbon 单独一个专用解决方案**（`ribbon_solution`，Phase 7 默认 `new_RibbonSoln`），因为 ribbon
  没有 Web API 直写路径，只能 `ExportSolution→改 customizations.xml→ImportSolution`，无法走主解决方案的
  `AddSolutionComponent` 流程。**两者必须不同名**（lint 强制）。

- **每个阶段自管 solution 归属（统一契约）**：所有 deploy/sync 函数都收 `solution=`，自己把组件加进
  解决方案——**编排器不做任何手动 `add_solution_component`**。编排器只负责：① ensure 两个 solution
  外壳（含 publisher）② 按链序跑各阶段 ③ 最终 `PublishAllXml`（让 optionset/table 元数据生效；其它阶段
  已各自精准发布——webresource 按 id、form/view 按实体、ribbon 随 import）。

  | 阶段 | 调用 | 自加 solution code |
  |------|------|-------------------|
  | optionsets | `sync_optionsets(models, solution=main)` | 9 |
  | tables | `deploy_order` → `deploy_table(t, solution=main)` | 1 |
  | webresources | `sync_webresources(root, solution=main)` | 61（+精准 publish） |
  | plugins | `deploy_plugin(dir, solution=main)` | 10030/+92 |
  | forms | `sync_forms(forms, solution=main)` | 60（+按实体 publish） |
  | views | `sync_views(views, solution=main)` | 26（+按实体 publish） |
  | roles *(opt-in)* | `deploy_role(role, solution=main)` | 20 |
  | ribbon | `sync_ribbons(models, solution=ribbon)` | 专用解决方案 export/import（+精准 publish） |

  ⚠️ `deploy_table`/`deploy_role` 的 `solution=` 是 Phase 9 **加法式新增形参**，默认 `None` = 旧行为不变。
  `sync_optionsets` 是 Phase 9 **新增**的包装（optionset 此前是唯一没有 `*_sync.py` 的组件类型）。

## 清单 `ninebot-project/metadata_py/project.py`

```python
from framework_power import Project, Publisher

PUBLISHER = Publisher(name="new", display_name="PP", prefix="new")

PROJECT = Project(
    main_solution="new_WorkflowSoln",
    ribbon_solution="new_RibbonSoln",
    publisher=PUBLISHER,
    version="1.0.0.0",                       # 必须 X.Y.Z.W
    optionsets=["new_category"],             # stems → ninebot-project/metadata_py/optionsets/<stem>.py（新目录）
    tables=["new_order", "new_customer"],    # 名称引用 → ninebot-project/metadata_py/tables/（按依赖序）
    webresources=True,                       # bool：同步整个 ninebot-project/webresources/ 目录进主解决方案
    plugins=["ninebot-project/plugins/Smoke"],               # 工程目录（含 plugin_def.py；dotnet 构建）
    forms=["new_order__Main"],               # stems → ninebot-project/metadata_py/forms/<stem>.py（{entity}__{Name}）
    views=["new_order__Active"],             # stems → ninebot-project/metadata_py/views/<stem>.py
    ribbons=["new_order"],                   # stems → ninebot-project/metadata_py/ribbons/<stem>.py
    roles=[],                                # 名称引用 → ninebot-project/metadata_py/roles/（opt-in 阶段）
)
```

**列表是 STEMS**，按 `<dir>/<stem>.py` 解析；`tables`/`roles` 是名称引用（走各自 registry）；
`plugins` 是工程目录；`webresources` 是 bool。每个阶段在**没有配置内容时自动跳过**（结果里不出现）。

## CLI

```bash
python -m framework_power workflow show                                   # 看解析后的清单（离线）
python -m framework_power workflow lint                                   # 离线检查（字段/版本/引用文件存在）
python -m framework_power workflow plan  --env dev                        # 只读预演（全部 would_*）
python -m framework_power workflow deploy --env dev                       # 跑整条链（ensure→阶段→publish）

# 常用过滤断言：
python -m framework_power workflow deploy --env dev --skip plugins        # 跳过 .NET 构建
python -m framework_power workflow deploy --env dev --only tables,views   # 只跑指定阶段
python -m framework_power workflow deploy --env dev --include-roles       # 开启 roles 阶段（默认关）
python -m framework_power workflow deploy --env dev --no-publish          # 跳过最终 PublishAllXml
python -m framework_power workflow deploy --env dev --project path/to/project.py   # 指定清单
```

阶段名（`--only`/`--skip` 取值）：`optionsets, tables, webresources, plugins, forms, views, roles, ribbon`。

## 关键约束 / 踩坑

- **全局 optionset 文件是新约定**：`ninebot-project/metadata_py/optionsets/<stem>.py` 导出 `OPTIONSET = GlobalOptionSet(...)`
  （此前 optionset 只能内联进 Solution，没有独立文件）。optionset 是 create-only——选项变了报
  `manual_update_required`（用 maker 门户 / InsertOptionValue）。
- **非破坏 + 幂等**：各阶段只 create/update/add；标准（非 `new_` 前缀）组件跳过；form/view 在结构化模型上
  diff，逆向未改的重 deploy = `skipped_unchanged`，绝不重写真实 form/view。重跑整条链安全。
- **plugin 阶段要 dotnet**：`deploy_plugin` 在工作流内 `dotnet build`+`pack`。本环境 plugin 运行时只收
  **net462/net471**（Phase 8 钉死）。不想构建就 `--skip plugins`。详见 [[dv-plugin-python]]。
- **ribbon 绑 JS 前资源必须先存在**：链序里 webresource 在 form/ribbon 之前，正是为此。
- **roles 默认关**：角色不在开发链路里（安全配置正交），用 `--include-roles` 才同步表权限 + 加进主解决方案；
  角色必须环境里**已存在**（工具不创建角色，只同步权限 + 加入解决方案，code 20）。
- **【ADR-018】`--workspace` 路径解析（2026-09-20 live）**：从**引擎仓库根**带 `--workspace ninebot-project`
  运行时，4 个 workflow 命令（show/lint/plan/deploy）加载清单后会把 7 个目录字段
  （`forms_dir`/`views_dir`/`tables_dir`/`optionsets_dir`/`ribbons_dir`/`roles_dir`/`webresources_root`）
  **拼上工作区根**变绝对路径——否则会到 `power-platform-agent/metadata_py/...` 下找文件（漏
  `ninebot-project/` 前缀）。从工作区根直接运行则无需 `--workspace`，行为等价。
- **True/False（Python）**，不要 `true`/`false`。

## 不要做

- 不要让 `main_solution` 和 `ribbon_solution` 同名（lint 报错；ribbon 必须独立解决方案）。
- 不要指望编排器手动加组件——归属全部由各阶段 `solution=` 自管；若某阶段没加进解决方案，去查该阶段的
  `solution=` 是否传了，而不是在编排器里补 `add_solution_component`。
- 不要用 `workflow deploy` 部署不属于自己的组件（标准实体/account 等会被各阶段自动 skip，但仍应只列自有组件）。
