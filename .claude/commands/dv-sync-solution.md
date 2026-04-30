将解决方案 YAML 中定义的所有组件批量同步到 Dataverse（完整流程：验证 → 计划 → 确认 → 按依赖顺序执行 → 验证）。

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
3. 然后重新执行 `/dv-sync-solution`

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

### Step 3: 发布商检查与创建（自动处理）

解决方案同步的第一步是确保发布商存在。这部分由 `solution_agent.sync_from_yaml` 自动处理，无需用户干预。

### Step 4: 扫描组件并生成同步计划（Dry-Run）

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

解析返回的 JSON，收集以下信息：
- 解决方案基本信息
- 组件总数和分类统计
- 同步顺序（按依赖排序）
- 每个组件的当前状态和预期操作

### Step 5: 展示计划并等待用户确认 ⚠️

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
2. table（表/实体）- 包含所有非 Lookup 字段
3. relationship（关系）- 包含 Lookup 字段 Deep Insert
4. form（表单）
5. view（视图）
6. webresource（Web 资源）
7. plugin（插件）
```

**详细组件列表**：
| 顺序 | 类型 | 文件路径 | 操作 | 说明 |
|------|------|----------|------|------|
| 1 | table | tables/payment_recognition.yaml | create | 一次性创建表 + 所有非 Lookup 字段 |
| 2 | relationship | (在 table YAML 中定义) | create | 创建关系 + 自动创建 Lookup 字段 |
| 3 | form | forms/payment_recognition_main.yaml | create | 创建主表单 |
| 4 | view | views/payment_recognition_active.yaml | create | 创建活动视图 |

**同步配置**：
| 配置项 | 值 |
|--------|------|
| 方向 | sync.direction (local_to_remote/remote_to_local) |
| 冲突策略 | sync.on_conflict (skip/update/replace/create_only) |

如果没有变更（所有组件都已同步），显示 "All components are already in sync with Dataverse" 并**停止执行**。

**必须等待用户明确确认后才继续。使用 AskUserQuestion 工具询问用户：**
- "以上变更将被应用到 Dataverse。是否确认执行？"
- 提供选项：确认执行 / 取消

如果用户拒绝或选择取消，**停止执行**并显示 "Solution sync cancelled by user"。

### Step 6: 执行批量同步

用户确认后，执行实际的解决方案同步。

优先使用 MCP 工具 `solution_sync_from_yaml`：
```
调用 MCP solution_sync_from_yaml，参数: {"solution_yaml": "<yaml_path>", "dry_run": false}
```

如果 MCP 不可用，使用 Python fallback：

```python
python -c "
import asyncio, json
from framework.agents.core_agent import CoreAgent
from framework.agents.solution_agent import SolutionAgent

async def sync():
    core = CoreAgent()
    agent = SolutionAgent(core_agent=core)
    result = await agent.sync_from_yaml('$ARGUMENTS'.strip(), dry_run=False)
    print(result)

asyncio.run(sync())
"
```

### Step 7: 实时进度报告

解析同步结果，按组件类型分组报告进度：

**发布商状态**：
- 发布商名称和前缀
- 状态：已存在 / 新创建

**组件同步进度**（按类型分组）：

| 类型 | 组件 | 状态 | 说明 |
|------|------|------|------|
| table | payment_recognition | 成功 | 实体 + N 个字段一次性创建 |
| relationship | new_payment_account | 成功 | 关系 + Lookup 字段 Deep Insert |
| relationship | new_payment_systemuser | 成功 | 关系 + Lookup 字段 Deep Insert |
| form | payment_recognition_main | 成功 | 表单已更新 |
| view | payment_recognition_active | 成功 | 视图已创建 |

对于每个失败的组件，显示详细错误信息。

**表创建详情**（新增）：
- **实体名称**：new_payment_recognition
- **创建方式**：一次性 POST EntityDefinitions
- **包含字段**：N 个（String, Integer, Money, Picklist, DateTime 等）
- **Lookup 字段**：M 个（通过关系创建）

**关系创建详情**（新增）：
- **关系类型**：OneToMany/ManyToMany
- **Lookup 字段**：随关系自动创建（Deep Insert）
- **级联配置**：Assign/Delete/Reparent/Share/Unshare

### Step 8: 应用后验证

同步完成后，验证解决方案状态：

```python
python -c "
import asyncio, json
from framework.agents.core_agent import CoreAgent
from framework.agents.solution_agent import SolutionAgent

async def scan():
    core = CoreAgent()
    agent = SolutionAgent(core_agent=core)
    result = await agent.scan_components('$ARGUMENTS'.strip())
    print(result)

asyncio.run(scan())
"
```

验证检查项：
- 所有组件是否已在 Dataverse 中创建/更新
- 组件数量是否与解决方案定义一致
- 依赖关系是否正确建立

### Step 9: 总结报告

汇总整个同步过程：

**同步结果摘要**：
| 指标 | 值 |
|------|------|
| 解决方案 | payment_solution |
| 总组件数 | N |
| 成功 | N |
| 失败 | N |
| 跳过 | N |
| 验证结果 | 通过/有差异 |

**按类型统计**：
| 类型 | 成功 | 失败 | 跳过 |
|------|------|------|------|
| optionset | N | N | N |
| table | N | N | N |
| form | N | N | N |
| view | N | N | N |
| webresource | N | N | N |
| plugin | N | N | N |

**失败项**（如果有的话）：
| 类型 | 组件 | 错误信息 |
|------|------|---------|

**建议后续步骤**（根据结果）：
- 全部成功：可以考虑使用 MCP 工具 `solution_export` 导出解决方案文件
- 有失败项：检查错误信息，修复 YAML 或环境配置后重新执行 `/dv-sync-solution`
- 有验证差异：检查 Dataverse 中缺失的组件，可能需要手动补充

## Dataverse 环境规则和限制 ⚠️

### 1. 视图必须包含 LayoutXML

**Dataverse 要求**：新版本 Dataverse 视图必须包含 `LayoutXML`，否则无法在 Maker Power（新界面）中打开，会提示"需要使用经典模式打开"。

**LayoutXML 必需字段**：
- `object`：实体的 ObjectTypeCode
- `jump`：实体的主名称属性（PrimaryNameAttribute）
- `id`：实体的主键属性（PrimaryIdAttribute）

**YAML 定义示例**：
```yaml
view:
  schema_name: "new_entity_active"
  entity: "new_entity"
  type: "PublicView"
  display_name: "Active Records"  # ← 这是实际显示在 UI 中的名称

columns:
  - attribute: "new_name"
    width: 200
  - attribute: "new_status"
    width: 100
```

### 2. 视图的 name 字段是显示名称

**Dataverse API 规则**：
- `name` 字段：视图的显示名称（如 "Active Customer Address"）
- `savedqueryid` 字段：唯一标识符（GUID）
- **不存在单独的 `display_name` 字段**

**YAML 映射**：
- YAML 中的 `display_name` → API 的 `name` 字段
- YAML 中的 `schema_name` → 仅用于内部引用，不发送到 API

### 3. Lookup 字段必须通过关系创建

**Dataverse 限制**：Lookup 类型的字段**不能**通过 `EntityDefinitions/{id}/Attributes` 端点单独创建，会返回错误：

```
Attribute of type LookupAttributeMetadata cannot be created through the SDK
```

**正确方式**：通过 `RelationshipDefinitions` 端点使用 Deep Insert，在创建关系的同时创建 Lookup 字段。

**YAML 定义**：
```yaml
lookup_attributes:
  - schema_name: "new_account_id"
    type: "Lookup"
    display_name: "客户"
    target: "account"  # ← 必需：指定目标实体

relationships:
  - schema_name: "new_account_new_entity"
    related_entity: "account"
    relationship_type: "ManyToOne"
    referencing_attribute: "new_account_id"  # ← 对应 lookup_attributes.schema_name
```

### 4. 自定义关系 SchemaName 必须以发布商前缀开头

**Dataverse 命名规范**：
- 自定义关系的 `SchemaName` 必须以发布商前缀（如 `new_`）开头
- 标准实体的关系可以例外，但自定义实体之间的关系必须遵守

**示例**：
- ✅ `new_account_new_customer_address`
- ✅ `new_businessunit_new_customer_address_approvaldept`
- ❌ `account_new_customer_address`（可能被拒绝）

### 5. 级联配置限制

**Dataverse 限制**：每个实体只允许有一个 Parental 级联关系（`Cascade: "Active"`）。

**推荐配置**（Referential 模式）：
```yaml
cascade_assign: "NoCascade"
cascade_delete: "RemoveLink"
cascade_reparent: "NoCascade"
cascade_share: "NoCascade"
cascade_unshare: "NoCascade"
```

### 6. 关系创建时的 ReferencedEntity 和 ReferencingEntity

**OneToMany 关系（从"一"的一方创建）**：
- `ReferencedEntity`：引用的实体（"一"的一方）
- `ReferencingEntity`：引用对方的实体（"多"的一方）
- `ReferencedAttribute`：被引用实体的主键（如 `accountid`）
- `ReferencingAttribute`：引用实体的外键 Lookup 字段（如 `new_account_id`）

**示例**（new_customer_address → account）：
```yaml
relationships:
  - schema_name: "new_account_new_customer_address"
    related_entity: "account"              # ReferencedEntity（"一"）
    relationship_type: "ManyToOne"
    referencing_attribute: "new_account_id" # ReferencingAttribute（外键）
```
