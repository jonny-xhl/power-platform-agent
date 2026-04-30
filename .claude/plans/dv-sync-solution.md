# dv-sync-solution 命令实现计划

## Context

用户需要为 Power Platform 项目添加解决方案级别的批量同步功能。现有的 `dv-sync` 命令专注于单个组件（表/表单/视图）的同步，而解决方案管理需要批量同步多个组件，同时处理发布商、依赖顺序、冲突解决等复杂逻辑。

当前 `solution_agent.py` 已实现核心同步逻辑，MCP 工具也已就绪，但缺少用户可调用的命令接口。

## 目标

创建独立的 `dv-sync-solution` 命令，与 `dv-sync` 保持交互一致性，复用现有实现。

## 设计方案

### 1. 架构概览

```
用户命令层
    ├── dv-sync (组件级同步)
    └── dv-sync-solution (解决方案级同步) ← 新增
            │
            ▼
MCP 工具层 (已实现)
    ├── solution_validate
    ├── solution_plan
    ├── solution_sync_from_yaml
    └── solution_scan
            │
            ▼
Agent 层 (已实现)
    └── SolutionAgent.sync_from_yaml()
            │
            ▼
组件同步 (复用)
    └── MetadataAgent (表/表单/视图)
```

### 2. 同步顺序

正确的依赖顺序：
```
optionset → table → form → view → webresource → plugin
```

### 3. 执行流程

| 步骤 | 操作 |
|------|------|
| 1 | 认证检查 |
| 2 | 发现并验证解决方案 YAML |
| 3 | 发布商检查与创建（自动） |
| 4 | 扫描组件并生成同步计划（Dry-Run） |
| 5 | 展示计划并等待用户确认 ⚠️ |
| 6 | 执行批量同步 |
| 7 | 实时进度报告 |
| 8 | 应用后验证 |
| 9 | 总结报告 |

### 4. 与 dv-sync 的一致性

- 相同的流程结构（9步）
- 相同的输出格式（表格展示）
- 相同的用户确认机制
- 相同的错误处理模式

## 需要创建/修改的文件

### 新建文件

| 文件 | 说明 | 优先级 |
|------|------|--------|
| `.claude/commands/dv-sync-solution.md` | 解决方案同步命令定义 | 必须 |
| `.claude/commands/dv-plan-solution.md` | 解决方案计划预览命令（只读） | 必须 |

### 参考文件（无需修改）

| 文件 | 用途 |
|------|------|
| `framework/agents/solution_agent.py` | 复用现有实现 |
| `framework/mcp_serve.py` | MCP 工具已就绪 |
| `.claude/commands/dv-sync.md` | 交互模式参考 |
| `.claude/skills/dv-solution/SKILL.md` | 解决方案管理文档 |

## dv-sync-solution.md 内容结构

```markdown
将解决方案 YAML 中定义的所有组件同步到 Dataverse。

参数: $ARGUMENTS（解决方案 YAML 文件路径）

## 执行流程

### Step 1: 认证检查
### Step 2: 发现并验证解决方案 YAML
### Step 3: 发布商检查与创建（自动）
### Step 4: 扫描组件并生成同步计划
### Step 5: 展示计划并等待用户确认
### Step 6: 执行批量同步
### Step 7: 实时进度报告
### Step 8: 应用后验证
### Step 9: 总结报告
```

## 验证计划

1. 创建 `dv-sync-solution.md` 文件
2. 创建 `dv-plan-solution.md` 文件
3. 使用 `payment_solution.yaml` 测试命令
4. 验证 MCP 工具调用
5. 验证 Python fallback
6. 确认与 dv-sync 的交互一致性

## 使用示例

```bash
# 基本使用
/dv-sync-solution metadata/solutions/payment_solution.yaml

# 不指定参数时列出可用解决方案
/dv-sync-solution

# 预览计划（不执行）
/dv-plan-solution metadata/solutions/payment_solution.yaml
```
