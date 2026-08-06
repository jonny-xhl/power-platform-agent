# ADR-007: 合并 sources/ 到 docs/

## Status
Accepted

## Context

工作区 (workspace) 最初有两个存储非代码产物的目录：
- `sources/` — 需求文档、设计产物、模板、Feature PRD 等"输入型"文档
- `docs/` — 数据字典等"输出型"文档

这种分离存在以下问题：

1. **概念重叠**：PRD、需求沟通记录、接口文档、原型等本质上都是文档，人为按"输入"/"输出"分类并不能带来实际价值
2. **认知负担**：团队成员需要记住两个目录的职责边界，新成员容易放错位置
3. **架构不统一**：其他 Power Platform 项目通常只有一个 `docs/` 目录管理所有文档
4. **`sources/` 命名模糊**："sources" 在软件工程中通常指源代码，用于存放 PRD 和 Excel 设计文档容易产生歧义

## Decision

将 `sources/` 下的所有内容合并到 `docs/`，统一用 `docs/` 管理所有文档类产物（输入 + 输出）。

### 迁移映射

| 原路径 | 新路径 |
|--------|--------|
| `sources/features/` | `docs/features/` |
| `sources/templates/excel/` | `docs/templates/excel/` |
| `sources/library/templates/` | `docs/templates/` |
| `sources/library/README.md` | `docs/templates/README.md`（合并） |
| `sources/templates/README.md` | `docs/templates/README.md`（合并） |

### 合并后的 `docs/` 结构

```
docs/
├── features/                # Feature 输出（PRD/设计/对比报告）
│   ├── cpq/
│   ├── so-model/
│   ├── po-model/
│   └── ...
├── templates/               # 需求文档模板
│   ├── FEATURE_STRUCTURE.md
│   ├── PRD_TEMPLATE.md
│   ├── ENTITY_DESIGN.md
│   ├── excel/
│   └── README.md
├── data_dictionary/         # 数据字典（自动生成）
└── ...（未来可能有接口文档、架构图等）
```

## Consequences

### 变得容易
- 所有文档入口统一到 `docs/` 一个目录
- 新成员只需了解 `docs/` 的约定，认知负担降低
- Feature 的生命周期更清晰：文档从 `docs/templates/` → `docs/features/<name>/` → `metadata_py/` → Dataverse

### 变得困难
- 无实质性困难。`sources/` 本身没有独立的构建或部署逻辑

### 需要同步更新
- 17个文件中约 42 处 `sources/` 路径引用需更新为 `docs/`
- `.claude/` skills：`design-dv-model`、`dv-model-to-python`、`dv-model-to-yaml`
- 架构文档：`adr-002`、`metadata-spec.md`、`architecture.md`
- 参考文档：`workspace-architecture-plan.md`、`external-repo-integration-guide.md`
- 根级文档：`README.md`、`CLAUDE.md`
- 工作区：`.gitignore`（`sources/` → `docs/` 不需要 gitignore 改变，`docs/` 本身已经在 workspace 内）
