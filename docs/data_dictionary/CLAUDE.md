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

数据字典通过 `pp` CLI 从 Dataverse 云端环境同步：

### 查看环境中所有自定义表

```bash
# 列出 Dataverse 环境中所有自定义表（new_ 前缀）
pp list --remote

# 列出所有表（不含过滤）
pp list --remote --all
```

### 批量导出所有自定义表

```bash
# 导出所有自定义表的数据字典（顺序执行）
pp reverse --all --dictionary

# 并行导出（8 workers，~2x 加速）
pp reverse --all --dictionary --parallel auto

# 自定义并发数
pp reverse --all --dictionary --parallel 4
```

> **批量导出会自动连带生成**：① `index.md`（从已写的 `tables/*.md` 汇总，含标准/自定义分组
> 与统计）② `optionsets/*.md`（从环境拉取 `new_` 前缀全局选项集）。即一条命令产出完整数据
> 字典。选项集生成是 best-effort，失败不会中断表导出。单表 `pp reverse <name> --dictionary`
> 不触发这两步（仅写单表文档）。


### 导出指定表（含标准表）

```bash
# 同时包含 account、contact、systemuser
pp reverse --all --dictionary --include "account,contact,systemuser"

# 仅导出指定前缀
pp reverse --all --dictionary --prefix "new_"
```

### 导出单表

```bash
# 导出数据字典 Markdown
pp reverse account --dictionary

# 导出为 Python 定义文件（存入 metadata_py/）
pp reverse account
```

> **注意**：数据字典输出到 workspace 的 `docs/data_dictionary/`（如 `ninebot-project/docs/data_dictionary/`），引擎根目录 `docs/data_dictionary/` 仅保留本文档。

## 与 ninebot-project/metadata_py/ 的区别

| 目录 | 用途 | 数据来源 |
|------|------|----------|
| `ninebot-project/metadata_py/` | Python 元数据源文件，用于声明式定义 Dataverse 表结构 | 手动编写/设计，或 `pp reverse <name>` 导出 |
| `ninebot-project/docs/data_dictionary/` | 数据字典 Markdown 文档，用于查阅云端实际结构 | 从 Dataverse 云端同步（`pp reverse --all --dictionary`） |

## 更新策略

- **增量更新**：`pp reverse <name> --dictionary` 更新单表
- **全量同步**：`pp reverse --all --dictionary --parallel auto` 重新同步全部
- **数据时效**：数据字典反映执行时刻的云端状态，需定期同步以保持最新

## 命名规范

- 表文档文件名使用 `logical_name.md` 格式
- 选项集文档文件名使用 `schema_name.md` 格式
- 自定义表和选项集以发布商前缀 `new_` 开头

## 导出数据字典要求

- 除了必要的数据字典md文件，最后**不得产生其他不必要的文件**
- 新添加的数据字典表只能添加到`index.md`的**对应标题最后**，并更新**统计**的内容
- 如果是**Picklist**时，**选项集引用**列必须要有值，格式参考表格中的内容，标签必须使用中文
- 如果是**Lookup**时，**Lookup对象**列必须有值
- 最终需要检查**index.md**中的内容是否正确
- **切记不得随意大批量的导出数据字典，如果有，必须停下来询问**