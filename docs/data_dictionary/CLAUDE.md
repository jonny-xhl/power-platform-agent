# 数据字典文档

本目录包含 Dataverse 环境的数据字典文档，从云端环境同步导出。

## 目录结构

```
docs/data_dictionary/
├── CLAUDE.md           # 本文档
├── index.md            # 总索引：表和全局选项集清单
├── tables/             # 表的数据字典文档
│   ├── account.md
│   ├── contact.md
│   └── new_*.md        # 自定义表
└── optionsets/         # 全局选项集文档
    ├── new_customer_status.md
    ├── new_order_status.md
    └── ...
```

## 文档格式

### 表文档 (tables/*.md)

每个表文档包含：

- **基本信息**：Schema Name、Logical Name、显示名称、说明、所有权类型
- **字段列表**：Schema Name、中文显示名称、类型、必填、说明、Lookup对象、选项集引用
- **关系**：关联实体、关系类型、级联行为
- **元数据**：源文件路径、最后更新时间

示例：
```markdown
# 客户账户 (`account`)

**说明**: 存储客户账户信息，包括账户编号、余额和状态

**所有权类型**: `UserOwned`

---

## 字段列表

| Schema Name | 中文显示名称 | 类型 | 必填 | 说明 | Lookup对象 | 选项集引用 |
|-------------|-------------|------|------|------|-----------|------------|
| `new_account_number` | 账户编号 | `String` | 是 | 唯一账户编号 |  |  |
| `new_balance` | 账户余额 | `Money` | 否 | 当前账户余额 |  |  |
| `new_status` | 状态 | `Picklist` | 是 | 账户状态 |  | 活跃:100000000; 冻结:100000001; 关闭:100000002 |
| `new_customer_id` | 客户 | `Lookup` | 是 | 关联客户 | `account` |  |

## 关系

| 关系名称 | 关联实体 | 关系类型 | 级联删除 |
|----------|----------|----------|----------|
| `new_account_contacts` | `contact` | OneToMany | RemoveLink |

---

## 元数据

- **Schema Name**: `account`
- **最后更新**: `2026-05-28 10:47:57`
```

### 选项集文档 (optionsets/*.md)

每个选项集文档包含：

- **基本信息**：Schema Name、英文名称、说明
- **选项列表**：值、中文标签、英文标签、颜色
- **元数据**：源文件路径、最后更新时间

## 同步方式

数据字典从 Dataverse 云端环境同步，使用 MCP 工具：

### 同步所有表和选项集

```
调用工具: metadata_export_dictionary
参数:
  - output_dir: "docs/data_dictionary" (可选，默认值)
  - custom_only: true (可选，只导出自定义表/字段)
  - environment: "dev" (可选，目标环境)
```

### 同步单个实体

```
调用工具: metadata_export_entity_dictionary
参数:
  - entity_name: "account" (必填)
  - output_dir: "docs/data_dictionary" (可选)
  - environment: "dev" (可选)
```

## 与 metadata/ 的区别

| 目录 | 用途 | 数据来源 |
|------|------|----------|
| `metadata/` | 元数据 YAML 源文件，用于声明式定义 Dataverse 表结构 | 手动编写/设计 |
| `docs/data_dictionary/` | 数据字典文档，用于查阅云端实际结构 | 从 Dataverse 云端同步 |

## 更新策略

- **手动同步**：调用 MCP 工具 `metadata_export_dictionary`
- **查看最新**：数据字典反映云端当前状态，定期同步以保持最新

## 命名规范

- 表文档文件名使用 `logical_name.md` 格式
- 选项集文档文件名使用 `schema_name.md` 格式
- 自定义表和选项集以发布商前缀 `new_` 开头
