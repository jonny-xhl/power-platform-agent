查看 Dataverse 实体当前状态（只读查询，零风险）。

参数: `$ARGUMENTS`（实体逻辑名，如 `new_payment_recognition`）

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
3. 然后重新执行 `/dv-status`

### Step 2: 查询实体状态

使用 Python 查询实体完整元数据：

```python
python -c "
import json
from framework.agents.core_agent import CoreAgent

def get_label(obj, default=''):
    \"\"\"安全获取 DisplayName 中的 UserLocalizedLabel.Label\"\"\"
    if obj is None: return default
    ulbl = (obj.get('UserLocalizedLabel') or {}) if isinstance(obj, dict) else {}
    return ulbl.get('Label', default)

core = CoreAgent()
client = core.get_client()
entity_name = '$ARGUMENTS'.strip()

# 获取实体元数据
try:
    entity = client.get_entity_metadata(entity_name)
    entity_info = {
        'schema_name': entity.get('SchemaName'),
        'display_name': get_label(entity.get('DisplayName'), 'N/A'),
        'ownership_type': entity.get('OwnershipType'),
        'is_audit_enabled': (entity.get('IsAuditEnabled') or {}).get('Value', False),
        'has_activities': entity.get('HasActivities', False),
        'has_notes': entity.get('HasNotes', False),
        'primary_id_attribute': entity.get('PrimaryIdAttribute'),
        'primary_name_attribute': entity.get('PrimaryNameAttribute'),
    }
except Exception as e:
    print(json.dumps({'error': f'Entity not found: {e}'}, ensure_ascii=False))
    exit()

# 获取所有属性
attrs = client.get_attributes(entity_name)
custom_attrs = [a for a in attrs if a.get('IsCustomAttribute', False)]
lookup_attrs = [a for a in attrs if 'Lookup' in a.get('@odata.type', '') or a.get('AttributeType') == 'Lookup']

attr_list = []
for a in custom_attrs:
    attr_list.append({
        'schema_name': a.get('SchemaName'),
        'type': a.get('AttributeType'),
        'display_name': get_label(a.get('DisplayName')),
        'required': (a.get('RequiredLevel') or {}).get('Value', 'None'),
    })

lookup_list = []
for a in lookup_attrs:
    lookup_list.append({
        'schema_name': a.get('SchemaName'),
        'targets': a.get('Targets', []),
        'display_name': get_label(a.get('DisplayName')),
    })

# 获取关系
try:
    relationships = client.get_relationships(entity_name)
    custom_rels = [r for r in relationships if r.get('IsCustomRelationship', False)]
    rel_list = []
    for r in custom_rels:
        otype = r.get('@odata.type', '')
        rel_type = 'OneToMany' if 'OneToMany' in otype else 'ManyToMany' if 'ManyToMany' in otype else 'Unknown'
        rel_list.append({
            'schema_name': r.get('SchemaName'),
            'type': rel_type,
            'referencing_entity': r.get('ReferencingEntity', ''),
            'referenced_entity': r.get('ReferencedEntity', ''),
        })
except Exception:
    rel_list = []

result = {
    'entity': entity_info,
    'total_attributes': len(attrs),
    'custom_attributes': len(custom_attrs),
    'lookup_attributes': len(lookup_attrs),
    'custom_relationships': len(rel_list),
    'attributes': attr_list,
    'lookups': lookup_list,
    'relationships': rel_list,
}
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

### Step 3: 格式化输出

将查询结果格式化为清晰的表格展示：

**实体概览**：
| 属性 | 值 |
|------|------|
| Schema Name | entity.schema_name |
| Display Name | entity.display_name |
| Ownership Type | entity.ownership_type |
| 总字段数 | total_attributes |
| 自定义字段 | custom_attributes |
| Lookup 字段 | lookup_attributes |
| 自定义关系 | custom_relationships |

**Lookup 字段列表**（如果有的话）：
| Schema Name | Target Entity | Display Name |
|-------------|---------------|--------------|

**自定义关系列表**（如果有的话）：
| Schema Name | Type | Referencing | Referenced |
|-------------|------|-------------|------------|

如果实体不存在，明确告知用户并建议检查实体名称是否正确。
