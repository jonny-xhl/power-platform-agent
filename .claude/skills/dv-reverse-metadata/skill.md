---
name: dv-reverse-metadata
description: 将 Dataverse 环境中已有表的结构逆向导出为本地 Python 定义文件（ninebot-project/metadata_py/tables/<schema>.py），用于直观查看表结构、对比差异、约束 AI 生成。当用户需要"导出表结构"、"逆向生成表定义"、"从环境拉取表元数据"、"对比环境与本地差异"、"查看 contact/account 等表的字段"时使用此技能。关键词：逆向、导出、reverse、export、表结构、字段清单、metadata snapshot。
---

# 逆向导出表元数据（Dataverse 环境 → 本地 Python 定义）

将 Dataverse 环境中**已存在**的表逆向导出为 `framework_power` 的 Python 定义文件
`ninebot-project/metadata_py/tables/<schema>.py`，作为本地参考、差异对比与 AI 生成约束。
`pac modelbuilder` 只支持 VB/C#，本流程直接产出可读、可双向使用的 Python 定义。

## 单文件、双向（核心契约）

逆向导出与正向同步共用**同一个** `ninebot-project/metadata_py/tables/<schema>.py` 文件：

- **逆向 `reverse`**：从环境拉取**全量快照**（自定义 + 标准字段/关系，过滤虚拟/主键/`*_base`/
  系统查找类型），覆盖写入该文件 → 真实结构可见、AI 不超出真实字段。
- **正向 `deploy`**：读同一文件同步到环境，但**自动跳过标准（非 `new_` 前缀）字段/关系**
  （它们是系统管理、仅作参考），只创建/同步自定义部分 → 全量快照正向同步是幂等且安全的。

因此一份文件既是参考快照，又能安全正向同步。

## 命令

```bash
# 逆向导出（全量快照，覆盖 ninebot-project/metadata_py/tables/<name>.py）
python -m framework_power reverse contact --env dev

# 指定输出文件
python -m framework_power reverse contact --env dev -o ninebot-project/metadata_py/tables/contact.py

# 导出后：校验（标准字段会有命名 warning，属正常）、只读预览
python -m framework_power lint contact
python -m framework_power plan contact --env dev     # 标准字段显示 would_skip_standard
```

## 使用场景

- 直观查看环境中某表的字段/关系结构（无需连服务器点开 maker portal）
- 正向 `deploy`/`dv-model-to-python` 生成前，先逆向拉取真实结构作为基线对比差异
- 帮助 AI 写代码时不超出环境中真实存在的字段（把逆向文件作为上下文参考）
- 标准实体（contact/account）扩展时，确认已有哪些自定义字段

## 逆向内容

- **保留**：所有非虚拟字段（自定义 + 标准 String/Integer/Money/Picklist/Boolean/Memo/
  DateTime/Decimal/Double/File）+ 本表出站查找关系（1:N、N:N）
- **过滤**：虚拟/计算字段（`IsComputed`/`IsLogical`/`AttributeOf`/`Virtual`）、主键
  （`IsPrimaryId`）、`*_base`、系统查找类型（Owner/Customer/PartyList/State/Status/
  Image/Uniqueidentifier 等）
- **关系**：仅本表作为引用方（`ReferencingEntity == 本表`）的 1:N 与涉及的 N:N；
  本表作为被引用方的关系归属于对方表，不在本文件
- **多语言标签**：按环境实际语言保留（`Label.bilingual` / `Label.en` / `Label.zh`）

## 硬性约束

- **测试仅限 `contact` 表**：开发验证只能对 `contact` 执行逆向，不得导出其他任何表。
- **脱敏**：逆向文件仅含表结构（不含 token/URL/GUID 等机密）。提交前需复查
  `ninebot-project/metadata_py/tables/contact.py`，剥离任何环境特定标识；代码中不得硬编码凭据
  （认证复用 `get_client` → `ninebot-project/config/environments.yaml` + `.env`）。

## 参考文档

- 正向流程与约定：`docs/spec/metadata-spec.md`（§ Python API conventions）、`docs/guides/metadata-deploy.md`
- 类型/模型：`framework_power/models.py`
- 逆向实现：`framework_power/reverse.py`、`framework_power/codegen.py`
- 全局选项集（逆向 Picklist 引用时捕获 `optionset_name`，ADR-009/010/011）：
  `docs/spec/adr-009-optionset-reference-not-inline.md`、`docs/spec/adr-011-self-contained-table-deploy.md`
- Dataverse Web API 细节：`dataverse:dv-metadata` skill
