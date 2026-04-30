预览解决方案同步计划（只读 Dry-Run，不执行任何变更，零风险）。

参数: `$ARGUMENTS`（解决方案 YAML 文件路径，如 `metadata/solutions/payment_solution.yaml`）

## 执行流程

### Step 1: 认证检查

优先使用 MCP 工具 `auth_status`。如果 MCP 不可用，使用 Python fallback：

```python
python -c "
from framework.agents.core_agent import CoreAgent
import json
core = CoreAgent()
try:
    client = core.get_client()
    status = {'authenticated': True, 'environment': core._current_environment}
    print(json.dumps(status, ensure_ascii=False))
except Exception as e:
    print(json.dumps({'authenticated': False, 'error': str(e)}, ensure_ascii=False))
"
```

如果认证失败，**停止执行**并提示用户：
1. 检查 `.env` 文件是否配置了 `DEV_CLIENT_ID` 和 `DEV_CLIENT_SECRET`
2. 或调用 MCP 工具 `auth_login` 完成认证
3. 然后重新执行 `/dv-plan-solution`

### Step 2: 发现并验证解决方案 YAML

1. 解析 `$ARGUMENTS` 获取解决方案 YAML 文件路径。如果 `$ARGUMENTS` 为空，列出 `metadata/solutions/` 下所有可用的解决方案文件让用户选择：

```python
python -c "
from pathlib import Path
import json

solutions_dir = Path('metadata/solutions')
if solutions_dir.exists():
    files = list(solutions_dir.glob('*.yaml'))
    solutions = [{'name': f.stem, 'path': str(f)} for f in files if f.stem != '_template']
    print(json.dumps({'solutions': solutions}, ensure_ascii=False, indent=2))
else:
    print(json.dumps({'error': 'Solutions directory not found'}, ensure_ascii=False))
"
```

2. 确认文件存在。如果文件不存在，**停止执行**。

3. 验证解决方案 YAML 格式：

优先使用 MCP 工具 `solution_validate`：
```
调用 MCP solution_validate，参数: {"solution_yaml": "<yaml_path>"}
```

如果 MCP 不可用，使用 Python fallback：

```python
python -c "
import asyncio, json
from framework.agents.core_agent import CoreAgent
from framework.agents.solution_agent import SolutionAgent

async def validate():
    core = CoreAgent()
    agent = SolutionAgent(core_agent=core)
    result = await agent.validate_solution_yaml('$ARGUMENTS'.strip())
    print(result)

asyncio.run(validate())
"
```

4. 解析验证结果：
   - 检查 `valid` 字段
   - 如果有 `errors`，列出所有错误并**停止执行**
   - 如果有 `warnings`，展示 warnings 但继续执行

### Step 3: 生成同步计划（Dry-Run）

生成批量同步计划（不执行任何变更）：

优先使用 MCP 工具 `solution_plan`：
```
调用 MCP solution_plan，参数: {"solution_yaml": "<yaml_path>"}
```

如果 MCP 不可用，使用 Python fallback：

```python
python -c "
import asyncio, json
from framework.agents.core_agent import CoreAgent
from framework.agents.solution_agent import SolutionAgent

async def plan():
    core = CoreAgent()
    agent = SolutionAgent(core_agent=core)
    result = await agent.plan('$ARGUMENTS'.strip())
    print(result)

asyncio.run(plan())
"
```

### Step 4: 展示计划（到此结束，不执行）

将同步计划格式化展示给用户：

**解决方案概览**：
| 属性 | 值 |
|------|------|
| 名称 | solution.schema_name |
| 显示名称 | solution.display_name |
| 版本 | solution.version |
| 发布商 | publisher.prefix |

**组件统计**：
| 类型 | 数量 | 待创建 | 待更新 | 跳过 |
|------|------|--------|--------|------|
| 全局选项集 | N | N | N | N |
| 表 | N | N | N | N |
| 表单 | N | N | N | N |
| 视图 | N | N | N | N |
| Web 资源 | N | N | N | N |
| 插件 | N | N | N | N |

**同步顺序**（按依赖关系）：
```
1. optionset（全局选项集）
2. table（表/实体）
3. form（表单）
4. view（视图）
5. webresource（Web 资源）
6. plugin（插件）
```

**详细组件列表**：
| 顺序 | 类型 | 文件路径 | 操作 | 说明 |
|------|------|----------|------|------|
| 1 | table | tables/payment_recognition.yaml | create | 创建新表 |
| 2 | form | forms/payment_recognition_main.yaml | create | 创建主表单 |
| 3 | view | views/payment_recognition_active.yaml | create | 创建活动视图 |

**同步配置**：
| 配置项 | 值 |
|--------|------|
| 方向 | sync.direction (local_to_remote/remote_to_local) |
| 冲突策略 | sync.on_conflict (skip/update/replace/create_only) |

**注意**：到此为止，不执行任何实际变更操作。如需执行，请使用 `/dv-sync-solution` 命令。
