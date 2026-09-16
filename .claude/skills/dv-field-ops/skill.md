---
name: dv-field-ops
description: 对 Dataverse 环境中的字段做增删改运维：新增字段（含表尚无本地定义的情况）、删除、改名/改标签、改精度（Money/Decimal）。当用户要求"新增/添加某字段"、"移除/删除某字段"、"改字段标签（中英）"、"货币改两位小数"、"删掉多余字段"时使用。关键词：新增字段、添加字段、删除字段、字段改名、precision、精度、DefaultFormValue、RetrieveDependenciesForDelete、0x8004f01f。
---

# 字段级元数据运维（删 / 改名 / 改精度）

适用前提：字段已在环境中存在，需要改动或移除。新建字段走正常 `pp deploy`。

## 铁律

1. **属性类型（AttributeType）创建后只读** —— 改类型只能删建。
2. **`RetrieveDependenciesForDelete` 会漏报** —— 返回 0 依赖不代表安全，必须再做 XML 字符串兜底扫描。
3. **删除不可逆** —— 先快照 metadata + 数据，再动手。
4. **精度可直改，但降精度不可逆**（已有值被四舍五入）。
5. 本地定义与环境必须同步收尾：环境改完 → `pp plan <table>` 校验 `would_create=0`。
6. **SchemaName 创建后不可改** —— 新增字段前必须先跟用户确认字段名（改名=删建）。
7. **必填级别 `SystemRequired` 不可逆** —— 项目惯例一律用 `ApplicationRequired`。

## 一、裸脚本鉴权模板（必用，否则 401）

```python
import sys; sys.path.insert(0, ROOT)          # ROOT = 仓库根
from dotenv import load_dotenv; load_dotenv(ROOT/'ninebot-project'/'.env')   # 引擎 load_env_file 实测无效
from framework_power.client.env_config import load_yaml_with_env   # 递归展开 ${DEV_TENANT_ID}
from framework_power.client.auth import AutoAuthenticator
from framework_power.client.dataverse_client import DataverseClient

cfg  = load_yaml_with_env(str(CFG))                                # ninebot-project/config/environments.yaml
tok  = AutoAuthenticator(str(CFG)).get_cached_or_refresh_token('dev', cfg['environments']['dev'])
c    = DataverseClient('dev', str(CFG), access_token=tok)
# ⚠️ DataverseClient 没有通用 get()/delete()，用 session：
r = c.session.get(c.get_api_url("EntityDefinitions(LogicalName='<tbl>')/Attributes(LogicalName='<f>')"))
```

Python 解释器用系统 `C:/Users/jonxiang/AppData/Local/Programs/Python/Python313/python.exe`（托管 3.13.12 无 dotenv/msal）。
`pp` CLI 在仓库根执行必须带 `--workspace ninebot-project`，否则 legacy mode 找不到表定义。

## 二、删除字段（五步）

```text
① 快照   metadata: GET EntityDefinitions(LogicalName='<tbl>')/Attributes(LogicalName='<f>')
         数据:     GET <EntitySetName>?$select=<f>     ← 集合名取 EntityDefinitions?$select=EntitySetName，
                                                        直接用逻辑名 → 404
         落盘     ninebot-project/docs/_field_delete_backup/<tbl>__<f>__<ts>.json
② 查依赖 GET RetrieveDependenciesForDelete(ComponentType=2,ObjectId=<MetadataId>)
         dependentcomponenttype: 26=视图 / 60=窗体
③ 兜底扫 GET savedqueries?$filter=returnedtypecode eq '<tbl>'   (fetchxml + layoutxml)
         GET systemforms?$filter=objecttypecode eq '<tbl>'      (formxml)
         对 blob 做 re.search('<字段名>', blob, re.I)  ← API 漏报必须靠这步
④ 清引用 视图: update_view(savedqueryid, patch) 去掉该列
         窗体: 正则删 <cell[^>]*>(?:(?!</cell>).)*?<字段名>.*?</cell> (re.S|re.I)
               再清空 row: <row>\s*</row>；随后 update_form(formid, patch)
         → publish_entity('<tbl>')
⑤ DELETE DELETE EntityDefinitions(LogicalName='<tbl>')/Attributes(LogicalName='<f>')  → 期望 204
         → publish_entity → 读回期望 404
```

- 撞 `0x8004f01f` = 还有依赖没清，回到 ③。
- 主窗体**不能删**，只能 in-place PATCH；SystemForm 用 PATCH（PUT → 405）。

## 三、改标签 / 改名

`update_attribute_by_logical_name(ent, field, {'DisplayName': {...}, ...})` → `publish_entity`。
传 **完整标签集**（1033 + 2052），否则会丢另一语言位。改完同步本地 `metadata_py/tables/<tbl>.py`。

## 四、改精度（Money / Decimal）

```python
c.update_attribute_by_logical_name(ent, f, {'Precision': 6}, attribute_type='Decimal')
c.publish_entity(ent)
```

- **引擎其实也管精度**：`serializer._UPDATABLE_BY_TYPE[Decimal|Money]` 含 `Precision`/`MinValue`/`MaxValue`，
  deploy 的属性补丁路径会走 retrieve-modify-PUT 应用它。所以 `pp deploy <tbl> --fields <cols>` 同样能改精度；
  手写脚本只是更精确可控（一次只动一个属性、逐条回读）。**两条路等价，别以为必须手写。**
- Money 基础货币伴随字段 `<f>_base` **不会自动跟随**，要单独改（Decimal 无此问题）。
- **`MinValue`/`MaxValue` 不会因为改精度而被服务端联动调整**（实测 1e9 保持原样）；本地定义若
  `min_value/max_value` 为 `None`，`serialize_updatable` 会**跳过这两个键**，因此"本地 None vs 环境 0/1e9"
  这种值域漂移 `pp plan` **照不出来**——想对齐就在本地显式写上。
- **改前必须快照**：降精度四舍五入不可逆；升精度虽无损，也要留回滚基线。
  ```python
  # 元数据 + 数据双快照 → ninebot-project/docs/_precision_backup/
  GET EntityDefinitions(LogicalName='<t>')/Attributes(LogicalName='<f>')/Microsoft.Dynamics.CRM.DecimalAttributeMetadata
  GET <t>s?$select=<f1>,<f2>,...&$top=5000        # 全量数据
  ```
  改后重拉数据做字典 diff，**期望 0 差异**（升精度）——这是最有力的无损证明。
- **别用写数据的方式"抽验"精度**：目标表只要有已注册插件（`plugin-registrations*.json` 里能查到），
  PATCH 一条真实记录会触发业务逻辑，可能连锁改动其它字段。只做元数据读回 + 只读数据比对就够。
- 改完同步字段 `description` 文案（常见"6位小数"残留 → `pp plan` 报 would_patch）。
- 别盲改范围：汇率（Decimal 5/12）2 位不够用，且 `exchangerate` 是系统标准字段；百分比/比率不是货币。
- **量化/数量类字段慎用高精度**：precision 决定展示小数位（`1000` → `1000.000000`），数量、信心指数
  这类给 6 位会让列表和窗体很难看。用户要求"全部统一"时照做，但要主动提示这一点。

## 五、收尾校验

```bash
python -m framework_power.cli --workspace ninebot-project plan <tbl>
# 期望：attrs 全 would_skip，would_create=0
```

⚠️ **精度改动的校验不能只看 plan**：

- plan 的 `would_patch` 只告诉你"这个属性有差异"，**差异明细在 `fields` 里**。
  判据是 `fields` 含不含 `Precision`，**不是** `action` 是不是 `would_patch`——
  `DisplayName` 漂移同样会让字段变成 `would_patch`（环境把中文写进了 1033 英文位是常见历史缺陷）。
- 硬判据是 **typed GET 读回**：
  ```python
  GET EntityDefinitions(LogicalName='<t>')/Attributes(LogicalName='<f>')/Microsoft.Dynamics.CRM.DecimalAttributeMetadata?$select=Precision
  ```
- 拿不准差异归属时，**做对照实验**：把本地 `col.precision` 临时改回旧值，重跑
  `build_attribute_patch(col, existing)`，看 `would_patch` 数量是否一致——一致即证明差异与本次改动无关。

## 六、还原被误删的字段（restore）

字段被删除后想找回来：**别靠记忆重建，去备份里挖原始定义**。

1. **定位归属表（必须先做）**：同名 `new_xxx` 可能存在于多张表。用
   `GET EntityDefinitions(LogicalName='<tbl>')/Attributes?$select=LogicalName` 逐表确认，
   或从 `ninebot-project/docs/env_backup/CHANGELOG.md` 搜删除记录（含 intent 与字段清单）。
2. **提取原始定义**：`docs/env_backup/<solution>.zip` → `customizations.xml`（重构前的轮转备份）。
   ```python
   import zipfile, re
   data = zipfile.ZipFile(zip_path).read('customizations.xml').decode('utf-8', 'replace')
   m = re.search(r'<Entity>[\s\S]{0,800}?<Name[^>]*><tbl></Name>', data)
   blk = data[m.start():data.find('</Entity>', m.start())]
   re.search(r'<attribute PhysicalName="new_XXX"[^>]*>[\s\S]*?</attribute>', blk, re.I).group(0)
   ```
   ⚠️ 属性块是 **PascalCase** `PhysicalName`（`new_VersionNo`），正则**必须 `re.I`**，否则会
   "差集里有、块内找不到"自相矛盾。
3. **加回本地定义** `metadata_py/tables/<tbl>.py`（`Column("new_Xxx", AttributeType.String, max_length=N)`），
   然后 `lint`。
4. **增量部署**（别整表跑，避开其它 would_patch 干扰）：
   ```bash
   python -m framework_power.cli --workspace ninebot-project deploy <tbl> --env dev \
          --fields new_Xxx --solution <sol>
   ```
   → 期望 `attrs: 1 created` + `solution: <sol> added`。
5. `publish_entity('<tbl>')` → 读回校验（**`$select` 必须含 `DisplayName`**，否则标签返回空、误判没建上）
   → `pp plan <tbl>` 期望 `would_create=0`。
6. 同步 `docs/data_dictionary/tables/<tbl>.md` + `docs/env_backup/CHANGELOG.md`。

- **字段标签由 create 时写入**；`label_sync.py` 只管视图/窗体名称多语言（ADR-016），
  `deploy --fields` 路径**不走 labels 阶段**（输出只有 attrs 行）——别指望它补标签。

## 七、新增字段

有本地定义时是常规 `pp deploy`，但**没有本地定义**（表从未进过仓库）时多一步 reverse：

1. **先确认现状**：`reverse` 一次看结构，顺便把表纳入源码管理（非破坏性）。
   ```bash
   python -m framework_power.cli --workspace ninebot-project reverse <tbl> --env dev -o .tmp/<tbl>.py
   ```
   ⚠️ reverse 产物的**关系顺序不稳定**（同一张表连续 reverse 两次，关系集合相同但字节不同）
   → 别直接覆盖已有定义，先 diff。
2. **查清 4 件事再动手**（都来自环境，别凭感觉）：
   | 要确认 | 怎么查 | 为什么 |
   |---|---|---|
   | 必填级别惯例 | 列 `Attributes?$select=RequiredLevel` 统计分布 | 项目里通常全用 `ApplicationRequired`；`SystemRequired` **不可逆**且拦截插件/接口写入 |
   | 选项集约定 | 看同类字段 `IsGlobal` | 通用值（是/否）走全局集复用，业务专属值走本地内联（名字自动为 `<entity>_<field>`） |
   | 命名风格 | 看同类字段的 SchemaName | **SchemaName 创建后不可改**，改名只能删建 |
   | 方案归属 | `solutioncomponents?$filter=objectid eq <entity MetadataId>` | `rootcomponentbehavior=0`（含子组件）→ 新字段**自动**随该方案导出，不用显式加组件 |
3. **`--fields` 增量部署 + 立即 `plan` 预演**：`plan` 必须显示 `1 would_create` 且无 `would_patch`。
   ```bash
   python -m framework_power.cli --workspace ninebot-project deploy <tbl> --env dev \
          --fields new_Xxx --solution <sol>
   ```
4. **`publish_entity('<tbl>')` + 读回校验**：类型 / 选项值与标签 / `DefaultFormValue` /
   `RequiredLevel` / `IsAuditEnabled` / `IsValidForAdvancedFind`（引擎把 `is_searchable` 映射到这个键，
   **不是** `IsSearchable`，后者恒 False 属正常）。
5. **字典重生成用 `reverse --dictionary`**（环境基准，保留 Virtual 等本地没有的列）；
   `pp dictionary` 走本地定义，行数会**变少**。
6. 字段**默认值**：Picklist 用 `default_value=<int>` → 落成 Dataverse 的 **`DefaultFormValue`**；
   `bool` 会被引擎告警跳过（ADR-017）。必填 + 有默认值时，新记录自动带值，历史记录仍是空。

## 实测案例

| 日期 | 字段 | 结论 |
|---|---|---|
| 2026-09-10 | `new_rollingforecast.new_forecastamountcny` | API 返回 0 依赖但主窗体 `Information` 实际引用 → 清 cell 后 DELETE 204 |
| 2026-09-11 | `new_rollingforecast.new_actualmaterialnos` | API 0 依赖 + XML 无命中（7 视图/3 窗体）→ 一次 204；27 条记录中 6 条有值已快照 |
| 2026-09-11 | `new_salestarget.new_VersionNo`（**还原**） | 09-09 重构误删的 12 字段之一；从 `new_entity930.20260909T073350Z.zip` 挖出原定义（nvarchar/100）→ 增量 created + publish，`would_create=0` |
| 2026-09-15 | `new_rollingforecast` 13 个 Decimal（**改精度 2→6**） | 逐个 PUT + publish；`MinValue/MaxValue` 未联动（1e9 保持）；41 条 × 13 字段回读零差异；plan 残留 7 个 `would_patch` 经对照实验证明是 **DisplayName 漂移**（环境 1033 位写中文）而非精度 |
| 2026-09-16 | `new_sparepartscustomerpo.new_motorcycle_mark`（**新增**，Picklist） | 表原本无本地定义 → 先 reverse（116 列/47 关系）再插列；`deploy --fields` 1 created；**`DefaultFormValue=2` 直接证明 ADR-017 引擎修复生效**；plan 109 skip / 0 patch；字典用 `reverse --dictionary` 重生成（142→164 行，顺带补上 8 月以来的新字段） |
