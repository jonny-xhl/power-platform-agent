将 YAML 元数据同步到 Dataverse（完整流程：验证 → 计划 → 确认 → 应用 → 验证）。

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

如果认证失败，**停止执行**并提示用户：
1. 检查 `.env` 文件是否配置了 `DEV_CLIENT_ID` 和 `DEV_CLIENT_SECRET`
2. 或调用 MCP 工具 `auth_login` 完成认证
3. 然后重新执行 `/dv-sync`

### Step 2: 发现并验证 YAML

1. 解析 `$ARGUMENTS` 获取目标 YAML 文件路径。如果 `$ARGUMENTS` 为空，列出 `metadata/tables/` 下所有可用的 YAML 文件让用户选择。
2. 确认文件存在。如果文件不存在，**停止执行**。
3. 验证 YAML 格式（同 `/dv-plan` Step 2）：

```python
python -c "
import yaml, json

yaml_path = '$ARGUMENTS'.strip()

try:
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
except Exception as e:
    print(json.dumps({'error': f'Failed to read YAML: {e}'}, ensure_ascii=False))
    exit()

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
    print(json.dumps({
        'valid': True,
        'entity': entity_name,
        'attribute_count': len(attrs),
        'relationship_count': len(rels)
    }, ensure_ascii=False, indent=2))
"
```

4. **额外验证（仅 dv-sync）**：检查关系命名和级联配置

```python
python -c "
import yaml, json

yaml_path = '$ARGUMENTS'.strip()
with open(yaml_path, 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

warnings = []
rels = data.get('relationships', [])

# 检查关系 SchemaName 命名规则（必须以 new_ 开头）
for rel in rels:
    name = rel.get('name', '')
    if not name.startswith('new_'):
        warnings.append(f'Relationship \"{name}\": SchemaName should start with publisher prefix \"new_\" (will cause API error)')

    # 检查级联配置（不能用 Active/parental）
    cascade_fields = ['cascade_assign', 'cascade_delete', 'cascade_reparent', 'cascade_share', 'cascade_unshare']
    for field in cascade_fields:
        if rel.get(field) == 'Active':
            warnings.append(f'Relationship \"{name}\": {field} = Active establishes parental cascade. An entity can only have ONE parental relationship. Recommend using Referential mode instead.')

print(json.dumps({'warnings': warnings}, ensure_ascii=False, indent=2))
"
```

如果有验证错误，列出所有错误并**停止执行**。
如果有 warnings，展示 warnings 但继续执行（提醒用户注意）。

### Step 3: Dry-Run 计划

生成变更计划（不执行任何变更）：

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

收集并解析所有变更项。

### Step 4: 展示计划并等待用户确认 ⚠️

将变更计划格式化展示给用户：

**变更摘要**：
| 类型 | 数量 |
|------|------|
| 实体创建/更新 | N |
| 字段创建 | N |
| 字段更新 | N |
| 关系创建（含 Lookup） | N |
| 关系更新 | N |

**详细变更列表**：
| 操作 | 目标类型 | 目标名称 | 说明 |
|------|---------|---------|------|

**执行顺序**（严格按依赖排序）：
1. 实体（如果需要创建）
2. 非 Lookup 字段
3. 关系 + Lookup 字段（Deep Insert）

如果没有变更，显示 "No changes detected - YAML is already in sync with Dataverse" 并**停止执行**。

**必须等待用户明确确认后才继续。使用 AskUserQuestion 工具询问用户：**
- "以上变更将被应用到 Dataverse。是否确认执行？"
- 提供选项：确认执行 / 取消

如果用户拒绝或选择取消，**停止执行**并显示 "Sync cancelled by user"。

### Step 5: 按依赖顺序应用变更

用户确认后，执行实际同步。

优先使用 MCP 工具 `metadata_apply_yaml`：
```
调用 MCP metadata_apply_yaml，参数: {"table_yaml": "<yaml_path>"}
```

如果 MCP 不可用，使用 Python fallback：

```python
python -c "
import asyncio, json
from framework.agents.core_agent import CoreAgent
from framework.agents.metadata_agent import MetadataAgent

async def apply():
    core = CoreAgent()
    agent = MetadataAgent(core_agent=core)
    result = await agent.apply_yaml('$ARGUMENTS'.strip(), {})
    print(result)

asyncio.run(apply())
"
```

解析结果，报告每个实体的同步进度：
- 实体创建/更新：报告成功或失败
- 字段创建/更新：逐个报告或按批汇总
- 关系创建（Deep Insert）：逐个报告成功或失败

### Step 5.5: 同步窗体

实体同步完成后，自动发现并同步关联的窗体 YAML。

#### 5.5.1 发现窗体 YAML

从实体名推导窗体 YAML 路径：`metadata/forms/{entity_name}_main.yaml`

```python
python -c "
import os, json
from pathlib import Path

forms_dir = Path('metadata/forms')
entity_name = 'new_payment_recognition'  # 从 Step 5 的实体名推导

candidates = [
    forms_dir / f'{entity_name}_main.yaml',
    forms_dir / f'{entity_name.replace(\"new_\", \"\")}_main.yaml',
]
found = [str(c) for c in candidates if c.exists()]

print(json.dumps({'found': found}, ensure_ascii=False))
"
```

如果没有发现窗体 YAML，跳过此步骤，直接进入 Step 6。

#### 5.5.2 窗体同步预览

读取窗体 YAML，展示布局摘要：

```python
python -c "
import yaml, json

yaml_path = 'metadata/forms/payment_recognition_main.yaml'
with open(yaml_path, 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

form = data.get('form', {})
tabs = data.get('tabs', [])

print(f'Form: {form.get(\"display_name\")} ({form.get(\"entity\")})')
print(f'Type: {form.get(\"type\")}')
print(f'Tabs: {len(tabs)}')
for tab in tabs:
    fields = []
    for sec in tab.get('sections', []):
        for row in sec.get('rows', []):
            for cell in row.get('cells', []):
                fields.append(cell.get('attribute'))
    print(f'  {tab.get(\"display_name\")}: {len(fields)} fields')
"
```

#### 5.5.3 执行窗体同步

调用 `metadata_agent.update_form()`，自动处理创建或更新：

```python
python -c "
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path('framework').absolute()))

async def sync_form():
    from agents.core_agent import CoreAgent
    from agents.metadata_agent import MetadataAgent

    core = CoreAgent()
    meta = MetadataAgent(core_agent=core)
    result = await meta.update_form('metadata/forms/payment_recognition_main.yaml')
    print(result)

asyncio.run(sync_form())
"
```

**窗体同步策略**（`update_form` 自动处理）：
- 实体下无任何 Main 窗体 → POST 创建新窗体
- 仅有 Dataverse 自动生成的默认窗体（name="Information"）→ POST 新窗体替代
- 已有定制过的窗体 → PATCH 更新

解析结果，报告：
- 操作类型：create（新建）或 update（更新）
- 如果是 create 替代 auto-generated，显示原 form_id 和新 form_id
- FormXml 长度和 Tab 数量

#### 5.5.4 窗体验证

同步完成后验证窗体状态：

```python
python -c "
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path('framework').absolute()))

from agents.core_agent import CoreAgent
from agents.metadata_agent import MetadataAgent
import asyncio

async def verify():
    core = CoreAgent()
    meta = MetadataAgent(core_agent=core)
    result = await meta.get_form('new_payment_recognition', form_type=2)
    data = json.loads(result)
    forms = data.get('forms', [])
    print(f'Main forms: {len(forms)}')
    for f in forms:
        print(f'  {f.get(\"name\")} | default={f.get(\"isdefault\")} | xml={f.get(\"formxml_length\")}B')

asyncio.run(verify())
"
```

验证检查项：
- 至少存在一个 Main 窗体
- 窗体 formxml > 2000 chars（非自动生成的空壳）
- 窗体 name 不是 "Information"（已被业务名称替代）

### Step 5.6: 同步视图

实体和窗体同步完成后，自动发现并同步关联的视图 YAML。

#### 5.6.1 发现视图 YAML

从实体名推导视图 YAML 路径：`metadata/views/{entity_name}_active.yaml`

```python
python -c "
import os, json
from pathlib import Path

views_dir = Path('metadata/views')
entity_name = 'new_payment_recognition'  # 从 Step 5 的实体名推导

# 移除 new_ 前缀进行匹配
base_name = entity_name.replace('new_', '') if entity_name.startswith('new_') else entity_name

candidates = [
    views_dir / f'{entity_name}_active.yaml',
    views_dir / f'{base_name}_active.yaml',
]
found = [str(c) for c in candidates if c.exists()]

print(json.dumps({'found': found}, ensure_ascii=False))
"
```

如果没有发现视图 YAML，跳过此步骤，直接进入 Step 6。

#### 5.6.2 视图同步预览

读取视图 YAML，展示视图摘要：

```python
python -c "
import yaml, json
import xml.etree.ElementTree as ET

yaml_path = 'metadata/views/payment_recognition_active.yaml'
with open(yaml_path, 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

view = data.get('view', {})
display_name = view.get('display_name', view.get('schema_name', ''))
entity = view.get('entity', '')

# 解析列数
fetchxml = view.get('fetch_xml', '')
layoutxml = view.get('layout_xml', '')

fetch_cols = []
if fetchxml:
    root = ET.fromstring(fetchxml)
    fetch_cols = [attr.get('name') for attr in root.findall('.//entity/attribute')]

layout_cols = []
if layoutxml:
    root = ET.fromstring(layoutxml)
    layout_cols = [cell.get('name') for cell in root.findall('.//row/cell')]

print(f'View: {display_name} ({entity})')
print(f'Type: {view.get(\"type\", \"PublicView\")}')
print(f'FetchXML columns: {len(fetch_cols)}')
print(f'LayoutXML columns: {len(layout_cols)}')
"
```

#### 5.6.3 执行视图同步

调用 `metadata_agent.create_view()`，自动处理创建或更新：

```python
python -c "
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path('framework').absolute()))

async def sync_view():
    from agents.core_agent import CoreAgent
    from agents.metadata_agent import MetadataAgent

    core = CoreAgent()
    meta = MetadataAgent(core_agent=core)
    result = await meta.create_view('metadata/views/payment_recognition_active.yaml', mode='auto')
    print(result)

asyncio.run(sync_view())
"
```

**视图同步策略**（`create_view` 的 mode='auto' 自动处理）：
- 视图不存在 → 创建新视图
- 视图已存在 → 更新现有视图（fetchxml 和 layoutxml）
- **重要**：系统生成的视图（如 "Active 实体名"）无法通过 API 修改，会创建新的自定义视图

解析结果，报告：
- 操作类型：create（新建）或 update（更新）
- 视图名称和 ID
- 列数量

#### 5.6.4 视图验证

同步完成后验证视图状态：

```python
python -c "
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path('framework').absolute()))

from agents.core_agent import CoreAgent
import asyncio

async def verify():
    core = CoreAgent()
    await core.login()
    client = core.get_client()
    
    # 获取实体所有视图
    views = client.get_views('new_payment_recognition')
    
    # 过滤出我们同步的视图
    view_name = '认款单列表（自定义）'  # 或 YAML 中的 display_name
    matched = [v for v in views if view_name in v.get('name', '')]
    
    print(f'Found views: {len(matched)}')
    for v in matched:
        print(f'  {v.get(\"name\")} | id={v.get(\"savedqueryid\")} | default={v.get(\"isdefault\")}')

asyncio.run(verify())
"
```

### Step 6: 应用后验证

同步完成后，查询 Dataverse 当前状态并与 YAML 定义对比：

```python
python -c "
import json, yaml
from framework.agents.core_agent import CoreAgent

core = CoreAgent()
client = core.get_client()
yaml_path = '$ARGUMENTS'.strip()

with open(yaml_path, 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

entity_name = data['schema']['schema_name']

# 查询实体是否存在
try:
    entity = client.get_entity_metadata(entity_name)
    entity_exists = True
except:
    entity_exists = False

# 查询所有自定义属性
attrs = client.get_attributes(entity_name)
attr_map = {a['SchemaName']: a for a in attrs}

# 检查 YAML 中定义的字段是否都已创建
missing_attrs = []
for attr_def in data.get('attributes', []):
    attr_name = attr_def['name']
    if attr_def.get('type') != 'Lookup' and attr_name not in attr_map:
        missing_attrs.append(attr_name)

# 查询关系
try:
    relationships = client.get_relationships(entity_name)
    rel_map = {r['SchemaName']: r for r in relationships}
except:
    rel_map = {}

missing_rels = []
for rel_def in data.get('relationships', []):
    rel_name = rel_def['name']
    if rel_name not in rel_map:
        missing_rels.append(rel_name)

result = {
    'entity_exists': entity_exists,
    'missing_attributes': missing_attrs,
    'missing_relationships': missing_rels,
    'total_attributes_in_dataverse': len([a for a in attrs if a.get('IsCustomAttribute', False)]),
    'total_relationships_in_dataverse': len([r for r in relationships if r.get('IsCustomRelationship', False)]) if entity_exists else 0,
}
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

报告验证结果：
- 所有字段和关系都已创建 → 显示 "Post-sync verification passed"
- 如果执行了窗体同步，报告窗体验证结果（见 5.5.4）
- 如果执行了视图同步，报告视图验证结果（见 5.6.4）
- 有缺失项 → 列出缺失的字段和关系，建议检查错误日志或手动创建

### Step 7: 总结报告

汇总整个同步过程：

**同步结果**：
| 指标 | 值 |
|------|------|
| 实体 | 成功/失败 |
| 字段创建 | N |
| 字段更新 | N |
| 关系创建 | N |
| 关系更新 | N |
| 跳过（无变更） | N |
| 窗体同步 | 创建/更新/跳过 |
| 视图同步 | 创建/更新/跳过 |
| 验证结果 | 通过/有差异 |

**失败项**（如果有的话）：
| 类型 | 名称 | 错误信息 |
|------|------|---------|

**建议后续步骤**（根据结果）：
- 全部成功：可以考虑使用 `/dv-status <entity_name>` 查看最终状态
- 有失败项：检查错误信息，修复 YAML 或环境配置后重新执行 `/dv-sync`
- 有验证差异：检查 Dataverse 中缺失的字段/关系，可能需要手动补充
- 窗体同步后：在 Power Apps Maker 中打开实体验证窗体布局
- 视图同步后：在 Power Apps Maker 中打开视图验证列显示和排序
