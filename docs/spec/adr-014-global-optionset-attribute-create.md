# ADR-014: Global-OptionSet Field Create Must Use `GlobalOptionSet@odata.bind`

## Status
Accepted (pinned live 2026-08-19, dev)

## Context

滚动预测（`new_rollingforecast`）需要新增"商务组"字段：Choice 类型、绑定既有全局选项集
`new_salesgroup`（6 项，100000001-100000006）。环境侧用裸 `create_attribute`（不走
`serialize_column` 声明式路径）直接 POST 属性定义时，先按 ADR-011 的序列化约定发送：

```json
{
  "@odata.type": "Microsoft.Dynamics.CRM.PicklistAttributeMetadata",
  "OptionSet": {"@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata",
                 "IsGlobal": true, "Name": "new_salesgroup"},
  "SchemaName": "new_BusinessGroupId", ...
}
```

被 Dataverse 拒绝：**`0x80048403`**（"Cannot insert duplicate key / 不允许的内联全局选项集"类
校验错误）——属性创建端点的内联 `OptionSet` 只接受 **Local**（`IsGlobal=false` + `Options`），
不接受用内联块"按名引用"一个已存在的全局选项集。

微软文档的标准做法是 OData 绑定导航属性：先按名取全局选项集的 `MetadataId`
（`GlobalOptionSetDefinitions(Name='<lowercase>')`，见 §9.1 的 405/小写坑），再在创建
payload 里用 `GlobalOptionSet@odata.bind` 指向它。

## Decision

**任何"字段绑定既有全局选项集"的属性创建，payload 必须用 bind 语法**：

```python
gos_id = client.get_global_optionset_by_name("new_salesgroup")["MetadataId"]
payload = {
    "@odata.type": "Microsoft.Dynamics.CRM.PicklistAttributeMetadata",
    "GlobalOptionSet@odata.bind": f"/GlobalOptionSetDefinitions({gos_id})",
    "SchemaName": "new_BusinessGroupId",
    "DisplayName": {"LocalizedLabels": [{"Label": "商务组", "LanguageCode": 2052}]},
    "RequiredLevel": {"Value": "None"},   # 必须是 {"Value": ...}，裸字符串会被拒
}
client.create_attribute("new_rollingforecast", payload)
```

三条路径的现状：

| 路径 | 现状 |
| --- | --- |
| 裸 `create_attribute`（临时脚本/skill 直调） | **必须用 bind 语法**（本 ADR，live 验证） |
| `serialize_column` 声明式（`optionset_name`，ADR-011） | **已于 2026-08-21 迁移为 bind 语法并 live 验证**（见下）：`deployer` 在 create 前经 `_resolve_global_optionset_ids` 收集 `{name: MetadataId}` 传入 `serialize_column(global_optionset_ids=...)` / `serialize_table_for_create(...)`；Picklist 引用分支优先发 `GlobalOptionSet@odata.bind`，**无法解析时回退旧内联块**（minimal fakes 兼容，失败面同迁移前）。live 验证：`new_rollingforecast.new_IsSplitRecord` → `new_isornotselect`，204 created，读回 `OptionSet.Name`/`IsGlobal` 正确 |
| maker portal 手工 | 平台自动处理 |

**迁移落地（2026-08-21 增补）**：改动集中在 `serializer.serialize_column` /
`serialize_table_for_create`（新增 `global_optionset_ids` 形参）与 `deployer`
（`_resolve_global_optionset_ids` + `deploy_table` 接线至 `_deploy_entity` /
`_deploy_attributes` 两个 create 调用点）；单元测试
`test_serializer.py::test_serialize_picklist_global_optionset_bind`、
`test_serialize_table_for_create_binds_global_optionsets`、
`test_deployer.py::test_deploy_table_creates_global_picklist_column_with_bind`、
`test_deploy_table_fresh_entity_attributes_use_bind`。

同批引擎配套修复（本 ADR 范畴）：

1. `_ATTRIBUTE_ODATA_TYPES` 补齐 Lookup 家族与常用类型（Lookup/Owner/Customer/PartyList →
   `LookupAttributeMetadata`，State/Status/EntityName/Uniqueidentifier/Image）——此前
   `update_attribute_by_logical_name` 对 Lookup 字段直接 `ValueError: unsupported`，
   必填级调整（如 `new_arownerid`）被阻断。
2. `create_attribute` 对 204 无 body 响应误报 `already_exists` → 改为 `created`
   （Dataverse 属性创建成功常返回空 204，不是冲突）。

## Consequences

- 临时建字段脚本/skill 有了唯一正确的 payload 模板，不再重复踩 `0x80048403`。
- ~~serializer 的 ADR-011 路径携带一个**已知未验证风险**~~ → **已于 2026-08-21 迁移到
  bind 语法并 live 验证**（见上表增补），声明式 create 路径与裸脚本路径行为一致。
- `RequiredLevel` 的 `{"Value": ...}` 对象形式与 bind 语法一起沉淀在模板中，避免裸字符串
  被拒的二次踩坑。

## Verification (2026-08-19, dev)

- 旧内联 payload → `0x80048403` 失败；bind payload → 204 成功。
- 读回验证：`new_BusinessGroupId` 的 `OptionSet.Name == "new_salesgroup"`，6 项选项完整。
- Lookup RequiredLevel PUT（`new_arownerid`/`new_customershortname` → None）在映射补齐后成功。

## Verification (2026-08-21, dev) — serializer 迁移

- `pp deploy new_rollingforecast --solution new_entity930`：`new_IsSplitRecord`
  （Picklist → `new_isornotselect`）声明式 create **204 created**，bind 语法 live 走通。
- 读回验证：`OptionSet.Name == "new_isornotselect"`、`IsGlobal == true`、选项 1=是/0=否。
- 部署后 `plan` 幂等：两新字段 `would_skip`。
