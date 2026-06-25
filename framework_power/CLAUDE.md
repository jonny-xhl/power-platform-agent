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
                       Form/View/Plugin + 枚举）；XML/base64 为不透明字符串
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

## 10. 如何扩展

- **新增属性类型**：`models.AttributeType` + `serializer._ODATA_TYPE`/`_UPDATABLE_BY_TYPE`/per-type 分支
  + `reverse.TYPE_TO_ENUM`（注意 Virtual 类型走 `@odata.type`）+ `codegen.emit_column` 字段。
- **新增 CLI 子命令**：`cli.py` 加 `cmd_xxx` + `build_parser` 注册。
- **新增模型字段**：`models.py` dataclass + `serializer` 输出 + `reverse` 读取 + `codegen` 回写 +
  `serializer._UPDATABLE_BY_TYPE` 白名单 + 往返测试。
- 改动尽量保持 `Table → table_to_python_source → import → Table` **往返保真**（见
  `test_codegen.py`）。

## 11. 测试与质量

- 测试：`test/unit/test_framework_power/`（`@pytest.mark.unit`，无网络）。
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
