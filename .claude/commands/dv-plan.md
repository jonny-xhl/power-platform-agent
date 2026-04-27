预览 YAML 元数据的变更计划（只读 Dry-Run，不执行任何变更，零风险）。

参数: `$ARGUMENTS`（YAML 文件路径，如 `metadata/tables/payment_recognition.yaml`）

## 执行流程

### Step 1: 认证检查

优先使用 MCP 工具 `auth_status`。如果 MCP 不可用（power-platform server 未连接），使用 Python fallback：

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

如果认证失败，提示用户：
1. 检查 `.env` 文件是否配置了 `DEV_CLIENT_ID` 和 `DEV_CLIENT_SECRET`
2. 或调用 MCP 工具 `auth_login` 完成认证
3. 然后重新执行 `/dv-plan`

### Step 2: 发现并验证 YAML

1. 解析 `$ARGUMENTS` 获取目标 YAML 文件路径。如果 `$ARGUMENTS` 为空，列出 `metadata/tables/` 下所有可用的 YAML 文件让用户选择。
2. 确认文件存在。如果文件不存在，提示用户检查路径。
3. 使用 SchemaValidator 验证 YAML 格式：

```python
python -c "
import yaml, json, sys

yaml_path = '$ARGUMENTS'.strip()

# 读取 YAML
try:
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
except Exception as e:
    print(json.dumps({'error': f'Failed to read YAML: {e}'}, ensure_ascii=False))
    exit()

# 基础验证
errors = []
if not data:
    errors.append('YAML file is empty')
else:
    schema = data.get('schema', {})
    if not schema:
        errors.append('Missing required section: schema')
    else:
        if not schema.get('schema_name'):
            errors.append('Missing required field: schema.schema_name')
        if not schema.get('display_name'):
            errors.append('Missing required field: schema.display_name')

    attrs = data.get('attributes', [])
    for i, attr in enumerate(attrs):
        if not attr.get('name'):
            errors.append(f'Attribute [{i}]: missing name')
        if not attr.get('type'):
            errors.append(f'Attribute [{i}]: missing type')
        if not attr.get('display_name'):
            errors.append(f'Attribute [{i}]: missing display_name')

    rels = data.get('relationships', [])
    for i, rel in enumerate(rels):
        if not rel.get('name'):
            errors.append(f'Relationship [{i}]: missing name')
        if not rel.get('related_entity'):
            errors.append(f'Relationship [{i}]: missing related_entity')
        if not rel.get('relationship_type'):
            errors.append(f'Relationship [{i}]: missing relationship_type')

if errors:
    print(json.dumps({'valid': False, 'errors': errors}, ensure_ascii=False, indent=2))
else:
    entity_name = schema.get('schema_name', '')
    attr_count = len(attrs)
    rel_count = len(rels)
    lookup_count = len([a for a in attrs if a.get('type') == 'Lookup'])
    print(json.dumps({
        'valid': True,
        'entity': entity_name,
        'attribute_count': attr_count,
        'lookup_count': lookup_count,
        'relationship_count': rel_count
    }, ensure_ascii=False, indent=2))
"
```

如果有验证错误，列出所有错误并停止。不继续执行后续步骤。

### Step 3: 生成变更计划（Dry-Run）

优先使用 MCP 工具 `metadata_plan`：
```
调用 MCP metadata_plan，参数: {"table_yaml": "<yaml_path>"}
```

如果 MCP 不可用，使用 Python fallback：

```python
python -c "
import asyncio, json
from framework.agents.core_agent import CoreAgent
from framework.agents.metadata_agent import MetadataAgent

async def plan():
    core = CoreAgent()
    agent = MetadataAgent(core_agent=core)
    result = await agent.plan_changes('$ARGUMENTS'.strip())
    print(result)

asyncio.run(plan())
"
```

解析返回的 JSON，收集所有变更项。

### Step 4: 展示计划（到此结束，不执行）

将变更计划格式化展示：

**变更摘要**：
| 类型 | 数量 |
|------|------|
| 实体创建/更新 | N |
| 字段创建 | N |
| 字段更新 | N |
| 关系创建 | N |
| 关系更新 | N |

**详细变更列表**：
| 操作 | 目标类型 | 目标名称 | 说明 |
|------|---------|---------|------|

如果没有变更（YAML 与云端一致），显示 "No changes detected - YAML is already in sync with Dataverse"。

**注意**：到此为止，不执行任何实际变更操作。如需执行，请使用 `/dv-sync` 命令。
