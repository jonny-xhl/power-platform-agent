# Dataverse App SiteMap 实体菜单管理（Python 优先 / framework_power）

此技能是 **framework_power** 的 **App SiteMap（应用导航菜单）** 操作入口（Phase 10，
ADR-015），把新表加进模型驱动 App 的菜单（区域 → 组 → SubArea），或移除菜单项。
完整决策与 live 踩坑见 `ninebot-project/docs/spec/adr-015-app-sitemap-management.md`。

## 使用场景

- 新表部署后加进某个 App 的菜单（建表 → 视图/窗体 → **app 菜单** 闭环的最后一步）
- 从 App 菜单移除实体
- 查看 App 的区域/组/实体树，或预演（plan）加菜单的结果

## 核心事实（live 钉死，勿凭记忆改）

- **app-aware sitemap 模型**：`appmodule` 没有 `sitemapxml` 列；导航 XML 在独立
  `sitemap` 实体，键为 `sitemap.sitemapnameunique == appmodule.uniquename`
  （例：app `new_CustomerService` → sitemap `new_CustomerService`）。
- **部署** = `PATCH sitemaps({id}) {sitemapxml}` + 发布；发布先试定向
  `PublishXml(<sitemaps>…)`，本环境 400 → **回退 `PublishAllXml`**（组织级）。
- **解决方案**：sitemap 是组件 **code 62**；已在解决方案内（如 `new_entity930` 含
  Customer Service 的 sitemap）则 PATCH 后随该解决方案 transport，不要再 add-component。
  sitemap 承载整个 app 的导航（含解决方案外实体的引用）。
- **幂等**：实体已有 SubArea → `skipped_unchanged`；lint 对同一实体多处 SubArea 报 error。
- **安全**：每次写前自动备份原始 XML 到 `docs/env_backup/sitemap_{unique}.{ts}.bak.xml`
  （ADR-013 对齐；恢复 = 把备份 PATCH 回去）。

## CLI

```bash
# 1. 找 App（--app 接 uniquename 或显示名）
python -m framework_power sitemap apps --env dev

# 2. 看菜单树（区域/组/实体），确认区域和组的准确标题
python -m framework_power sitemap show --app new_CustomerService --env dev

# 3. 只读预演（区域/组可传 Id 或中/英标题）
python -m framework_power sitemap plan new_internal_quotation \
    --app new_CustomerService --area 核价报价管理 --group 报价管理 --env dev

# 4. 加入菜单（幂等；--title 缺省用实体显示名，1033+2052 双语同文）
python -m framework_power sitemap add-entity new_internal_quotation \
    --app new_CustomerService --area 核价报价管理 --group 报价管理 \
    --title 内部报价单 --note "内部报价单上线" --env dev

# 5. 移除（可省略 --area/--group 全局移除）
python -m framework_power sitemap remove-entity new_internal_quotation --app new_CustomerService --env dev
```

从仓库根运行需 `--workspace ninebot-project`。

## 工作流

```
sitemap apps                    # 找到目标 app 的 uniquename
sitemap show --app X            # 找到区域/组的准确标题（或 Id）
sitemap plan <entity> …         # 确认 would_add / would_skip
sitemap add-entity <entity> …   # 备份 → PATCH → 发布 → 回读验证
```

## Python API（需要更细控制时）

```python
from framework_power import sitemap_sync
from framework_power.components import sitemap as sc

model = sc.parse_sitemap(xml, sitemapid="…", sitemapnameunique="new_CustomerService")
model, changed = sc.add_entity_subarea(
    model, "new_x", area_ref="核价报价管理", group_ref="报价管理",
    titles=[sc.SitemapTitle("1033", "内部报价单"), sc.SitemapTitle("2052", "内部报价单")],
)
xml = sc.to_sitemapxml(model)          # 语义无损往返（attrs + extras 保留）
```

模型：`AppSitemap → SiteArea → SiteGroup → SubArea`（+`SitemapTitle`），与 form/view
同契约（attrs 全保留、未建模子元素存 extras）。组件 registry key=`sitemap`（code 62）。

## 不要做

- 不要改自动生成的视图/窗体命名惯例之外的东西——本技能只动菜单；区域/组标题以
  `sitemap show` 的实况为准，不要凭记忆猜。
- 不要给已在解决方案内的 sitemap 再做 add-component（会报错或重复）。
- 不要跳过备份/发布（`--no-publish` 仅在随后统一 PublishAllXml 时使用）。
- `True`/`False`（Python），不要 `true`/`false`。
