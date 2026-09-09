# 元数据部署

部署方式：**Python API（`framework_power`）**，定义格式 `metadata_py/*.py`，
入口 CLI（`pp`）或代码调用。（legacy YAML + MCP 链路已于 2026-08-31 随 `framework/` 移除，
历史见 git。）

---


## Python API (`framework_power`)

自包含的 **Python-first** 库（本仓库唯一引擎，legacy YAML/MCP 链路已于 2026-08-31 移除）。
直接用**类型化 Python 模型**定义表 —— 模型定义本身*就是*唯一真实来源 —— 然后通过
`deploy_table()` 同步到目标环境。

### 优势

- 每张表一个可执行的真实来源（无需单独的 YAML + 转换器）。
- 完整覆盖字段类型（String、Integer、BigInt、Money、Decimal、Double、
  Picklist、Boolean、Memo、DateTime、File），支持 MaxLength / Precision / 范围约束。
- 多语言标签（zh-CN + en-US，或任意语言）。
- 支持**创建**与**更新**：字段先计算最小属性差异，再按 Dataverse 的 typed GET → retrieve-modify-`PUT` 合约更新完整具体类型元数据；同时支持关系创建。
- 命名采用**校验而非自动改写**（与 YAML 路径不同），保证定义的可预期性。
- 无需额外依赖（项目已使用 `requests` + `msal`）。

### 快速开始

```python
from framework_power import Table, Column, deploy_table, get_client
from framework_power.models import AttributeType, Label, RequiredLevel

table = Table(
    schema_name="new_ProjectBudget",
    display_name=Label.bilingual("项目预算", "Project Budget"),
    columns=[
        Column("new_Name", AttributeType.String,
               display_name=Label.bilingual("名称", "Name"),
               is_primary_name=True, required=RequiredLevel.ApplicationRequired, max_length=200),
    ],
)
print(deploy_table(get_client("dev"), table))
```

完整参考脚本（覆盖所有字段类型 + 1:N 关系）位于 `framework_power/examples/setup_projectbudget.py`：

```bash
pp.examples.setup_projectbudget --env dev
```

### CLI 工作流

推荐流水线为 **需求 → 定义 → 同步**，定义文件存放在 `metadata_py/tables/` 下
（每表一个 `<schema>.py`，各暴露 `TABLE`）。通过统一的 CLI 驱动：

```bash
pp list                           # 发现 metadata_py/tables/*.py
pp show new_projectbudget         # 打印序列化后的请求体（离线模式）
pp lint new_projectbudget         # 离线约定检查（要求 0 错误）
pp lint                           # 检查所有定义
pp plan new_projectbudget --env dev   # 只读干运行
pp deploy new_projectbudget --env dev # 同步到 Dataverse
pp deploy-all --env dev           # 全量部署，按引用顺序处理
```

- **需求 → 定义**：`dv-model-to-python` skill 将 Excel 设计（来自 `design-dv-model`）
  转换为 `metadata_py/tables/<schema>.py`。
- **触发方式**：`framework_power` 是普通库（非 MCP 工具），AI 通过终端执行上述 CLI
  —— 无需 MCP 来回。
- **`lint` 为约束门禁**：离线强制编写合约（前缀、PascalCase、单主名称、重复检查），
  确保在访问环境前生成结果已被约束。

### 部署语义

`deploy_table(client, table)` **幂等且无破坏性**：

| 对象 | 行为 |
| --- | --- |
| 实体 | 缺失则创建（创建 payload 即携带 `IsAuditEnabled` 等属性）；否则 PATCH 可更新属性（DisplayName、Description、HasNotes、IsAuditEnabled、IsQuickCreateEnabled）；若环境拒绝 EntityDefinitions PATCH（405 / 0x80060888），自动降级为「强一致 GET 完整定义 → 叠加差异 → 清理响应字段 → PUT」，结果标注 `method: put`。 |
| 字段 | 实体首次创建时内联携带。实体已存在时：缺失则 POST；否则计算可变属性差异，通过具体类型强一致 GET 获取完整定义，清理只读属性、叠加差异后 PUT。无差异时不发 PUT。 |
| 本地 Picklist 选项 | 对已有字段执行 typed GET + `$expand=OptionSet`；缺少值调用 `InsertOptionValue`，已存在值的本地声明语言标签发生变化时调用 `UpdateOptionValue(MergeLabels=true)`；远端额外值保留；有修改才定向发布实体。 |
| 全局选项集引用 | 字段声明 `optionset_name="<global>"` 时，创建 payload **先 resolve MetadataId 再用 `GlobalOptionSet@odata.bind` 绑定**已有全局选项集（ADR-014，不内联选项；MetadataId 无法解析时回退内联 `OptionSet.IsGlobal+Name` 引用块）；已有字段的选项同步自动跳过（选项归全局选项集所有，由其独立流程维护）。 |
| 引用的全局选项集本体 | **依赖优先自动同步**（ADR-011）：部署表前先收集 `optionset_name` 引用，从 `metadata_py/optionsets/<name>.py` 加载本地定义并先行同步（create-only、幂等、漂移报 `manual_update_required`）；带 `--solution` 时同步加入同一解决方案（code 9）。无本地定义时降级为只读在线检查并在 `optionsets_missing` 记录告警，**不阻断部署**。 |
| 绑定既有全局选项集的**新建**字段（裸 `create_attribute`） | 内联 `OptionSet.IsGlobal+Name` 引用会被 `0x80048403` 拒绝；必须用 **`GlobalOptionSet@odata.bind": "/GlobalOptionSetDefinitions(<MetadataId>)"`** 绑定语法（先按小写名取 MetadataId），详见 ADR-014。声明式 `optionset_name` 路径已于 2026-08-21 迁移为同一 bind 语法（`deployer` 先行 resolve）并 live 验证。 |
| 删除字段（手工运维，引擎不自动删） | **属性类型创建后只读**——改类型（如 Boolean→Picklist）只能**删建**，不能 PATCH `AttributeType`。删除前必须清依赖，否则报 `0x8004f01f`：①`RetrieveDependenciesForDelete(ComponentType=2,ObjectId=<attr_metadata_id>)` 查依赖；②`dependentcomponenttype` **26=SavedQuery（视图）/ 60=SystemForm（窗体）**；③清引用（视图 PATCH `savedquery`、窗体 `client.update_form` PATCH 掉该字段的 `<cell>`）；④`PublishXml`；⑤DELETE 属性（204）。 |
| 关系 | 仅创建（Dataverse 不支持 PATCH 关系定义）。已存在则跳过。 |
| 自动创建视图/窗体名称（ADR-016） | 全量 `pp deploy <table>` 末尾自动**补齐双语名称标签**：平台建表把 base 语言（英文）文本复制进所有语言标签位 → 中文个性化用户看到英文名。引擎按组织模板（活动/停用/我的/快速查找活动{复数}、{单数}查找/关联/高级查找视图、窗体"信息"）写 2052 标签（1033 不动），只碰**默认命名**组件（改名过的跳过），写后 sleep→publish→验证→重试（窗体额外 PATCH name 标脏才可发布）。幂等：已本地化零写入；`plan` 出 `auto_component_labels` 预览。`DeployConfig(localize_auto_components=False)` 可关。 |
| App SiteMap 实体菜单（Phase 10/ADR-015） | `pp sitemap add-entity <entity> --app <app> --area <A> --group <G>`：定位 app-aware sitemap（`sitemap.sitemapnameunique == appmodule.uniquename`，appmodule 本身无 `sitemapxml` 列）→ 实体已有 SubArea 则 `skipped_unchanged`（幂等，lint 对重复报 error）→ 否则**写前备份**原始 XML 到 `docs/env_backup/sitemap_{unique}.{ts}.bak.xml` → `PATCH sitemaps({id}) {sitemapxml}`（新 SubArea 样式克隆自既有实体条目）→ 发布（定向 `PublishXml(<sitemaps>)` 400 → 回退 `PublishAllXml`）→ 回读验证。sitemap 是解决方案组件 **code 62**：已在解决方案内（如 `new_entity930`）则随其 transport，勿再 add-component。`remove-entity` 同语义（全局或按 area/group 范围）。 |

本地 Picklist 的值和多语言标签已经支持由 `pp deploy <table> --fields <field>`
增量同步，并可传递 `--solution`。该流程默认**不删除**远端额外值，因为删除可能导致
现有业务数据失效。Boolean 标签和全局 OptionSet 的已有选项更新仍使用各自独立流程，
不会由本地 Picklist 同步逻辑隐式处理。引用全局选项集的字段（`optionset_name`）在
部署时只建立字段→选项集的链接，选项的增删改始终在全局选项集侧完成（可用
`pp optionset deploy --name <os> [--solution <sol>]` 独立管理，或
`pp optionset list / plan` 查看）。

### 元数据传播与重试

Dataverse 每次创建后需要 3–30 秒完成索引构建 / 缓存传播。部署器会在各阶段之间等待，
并对瞬时信号（`0x80040216`、`0x80060891`、
"another customization operation is running"、MetadataCache 未命中）进行退避重试。
可通过 `DeployConfig` 调整等待时间：

```python
from framework_power import deploy_table, DeployConfig
deploy_table(client, table, config=DeployConfig(after_entity_create_delay=8.0))
```

### 标签

`Label` 承载一个或多个 `(text, language_code)` 对。便捷方法：

```python
Label.zh("名称")                 # 仅 zh-CN
Label.en("Name")                 # 仅 en-US
Label.bilingual("名称", "Name")   # zh-CN + en-US
Label.parse("名称")               # str -> 仅中文；接受 Label/LocalizedLabel/(zh, en)
```

### 认证

`get_client(environment)` 读取 `config/environments.yaml`（展开 `.env` 中的 `${DEV_*}`
变量），通过客户端凭据流获取令牌（缓存优先，过期则刷新）。令牌持久化存储在
`.pp-local/state/tokens.json`。

### 类型参考

完整数据类定义参见 `framework_power/models.py`（`Table`、`Column`、
`LookupColumn`、`Relationship`、`CascadeConfig`、`Option`、`BooleanLabels`、`Label`
及枚举）。Dataverse Web API 类型/格式详情请参考 `dataverse:dv-metadata` skill。

---

## 相关文档

- [元数据规范](spec/metadata-spec.md) - 元数据定义规范（Python API 作者契约）
- [架构文档](spec/architecture.md) - 系统架构设计
- [快速开始](guides/getting-started.md) - 详细入门指南
