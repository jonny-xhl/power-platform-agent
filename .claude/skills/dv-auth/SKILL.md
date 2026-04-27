---
name: dv-auth
description: Dataverse 认证指南 - 指导 Agent 如何正确使用已认证的 Dataverse 连接。**重要**：当需要与 Dataverse 交互（创建表、查询记录、修改元数据等）时，必须先阅读此 skill。所有 Dataverse 相关操作都应通过已认证的 core_agent 或 metadata_agent 或 plugin_agent 或 solution_agent进行，不要直接创建新的 DataverseClient 实例。请务必使用此 skill，特别是当你看到 "auth failed"、"access token"、"authentication" 等关键词，或需要执行任何 Dataverse API 调用（metadata_apply_yaml、metadata_create_table、query_records 等）时。
---

# Dataverse 认证指南

## 核心原则

**所有 Dataverse 交互都必须使用已认证的 client，而不是创建新的连接。**

用户已经通过 `auth_login` MCP 工具完成了认证。所有后续的 Dataverse 操作都应该使用这个已建立的认证会话。

## 正确的使用方式

### 方式 1：通过 MCP 工具（推荐）

大多数操作都已经有对应的 MCP 工具，直接调用即可：

```json
// 创建或更新表
{"tool": "metadata_apply_yaml", "arguments": {"table_yaml": "metadata/tables/entity.yaml"}}

// 预览变更
{"tool": "metadata_plan", "arguments": {"table_yaml": "metadata/tables/entity.yaml"}}

// 查询元数据
{"tool": "metadata_list", "arguments": {"type": "table"}}
```

### 方式 2：通过 Python 代码（在项目中）

如果需要在 Python 代码中与 Dataverse 交互，使用已认证的 core_agent：

```python
# 获取已认证的 client
from framework.agents.core_agent import CoreAgent

core_agent = CoreAgent()
# 用户已通过 auth_login 认证，直接获取 client
client = core_agent.get_client()

# 使用 client 进行操作
entity_metadata = client.get_entity_metadata("account")
attributes = client.get_attributes("account")
```

### 方式 3：在 MetadataAgent 中使用

```python
# MetadataAgent 内部会使用已认证的 client
from framework.agents.metadata_agent import MetadataAgent
from framework.agents.core_agent import CoreAgent

core_agent = CoreAgent()
metadata_agent = MetadataAgent(core_agent=core_agent)

# 所有操作都使用已认证的连接
result = await metadata_agent.apply_yaml("metadata/tables/entity.yaml", {})
```

## 错误的使用方式（不要这样做）

### ❌ 直接创建 DataverseClient

```python
# 错误：这样会丢失认证信息
from framework.utils.dataverse_client import DataverseClient
client = DataverseClient()  # 没有认证信息！
client.get_entity_metadata("account")  # 会失败
```

### ❌ 尝试手动设置 access_token

```python
# 错误：不要这样做
import os
token = os.environ.get("DATAVERSE_ACCESS_TOKEN")  # 环境变量通常未设置
client = DataverseClient(access_token=token)  # 会失败
```

### ❌ 运行独立的 Python 脚本

```python
# 错误：独立脚本无法访问已认证的会话
# python test/sync_relationships.py  # 会提示缺少 access_token
```

## 认证流程（用户已完成）

用户可以通过以下方式之一完成认证（只需一次）：

### 方式 1：通过 MCP 工具登录（推荐）

1. 调用 MCP 工具 `auth_login`
2. 提供认证信息（access_token 或 client_id + client_secret）
3. CoreAgent 保存认证状态
4. 后续所有操作自动使用已认证的会话

### 方式 2：通过 .env 文件（本地开发）

在项目根目录创建 `.env` 文件：

```bash
# 复制示例文件
cp .env.example .env
```

然后编辑 `.env` 文件，添加 Dataverse 凭证：

```bash
# 开发环境凭证
DEV_CLIENT_ID=your-client-id-here
DEV_CLIENT_SECRET=your-client-secret-here
DEV_TENANT_ID=your-tenant-id-here  # 可选
```

**重要**：`config/environments.yaml` 中的占位符（如 `${DEV_CLIENT_ID}`）会自动从环境变量或 .env 文件中读取值。

### 方式 3：通过系统环境变量

在系统环境变量中设置（适用于 CI/CD 或团队协作）：

```bash
export DEV_CLIENT_ID="your-client-id"
export DEV_CLIENT_SECRET="your-client-secret"
```

### 自动认证行为

CoreAgent 现在支持自动认证：
- 如果用户已通过 `auth_login` 登录，使用缓存的 token
- 如果没有 token 但 `.env` 文件或环境变量中有凭证，自动获取 token
- 如果都没有，提示用户进行认证

## 常见错误与解决

### 错误：`DATAVERSE_ACCESS_TOKEN environment variable not set`

**原因**：尝试直接运行脚本或创建新的 DataverseClient

**解决**：使用 MCP 工具或通过 core_agent 获取 client

### 错误：`No core agent available`

**原因**：MetadataAgent 或其他 Agent 没有被正确初始化

**解决**：确保在初始化时传入 core_agent
```python
metadata_agent = MetadataAgent(core_agent=core_agent)
```

### 错误：`401 Unauthorized` 或 `403 Forbidden`

**原因**：Token 过期或权限不足

**解决**：提示用户重新调用 `auth_login` 工具

### 错误：`Not authenticated to environment: dev`

**原因**：没有可用的认证凭据

**解决方案**（按推荐顺序）：

1. **创建 .env 文件**（本地开发最简单）：
   ```bash
   # 在项目根目录创建 .env 文件
   DEV_CLIENT_ID=your-actual-client-id
   DEV_CLIENT_SECRET=your-actual-client-secret
   DEV_TENANT_ID=your-tenant-id  # 可选
   ```

2. **调用 MCP 工具 `auth_login`**：
   ```json
   {
     "tool": "auth_login",
     "arguments": {
       "client_id": "your-client-id",
       "client_secret": "your-client-secret"
     }
   }
   ```

3. **设置系统环境变量**：
   ```bash
   export DEV_CLIENT_ID="your-client-id"
   export DEV_CLIENT_SECRET="your-client-secret"
   ```

**注意**：`config/environments.yaml` 中的占位符（如 `${DEV_CLIENT_ID}`）需要从 .env 文件或系统环境变量中读取实际值。

## 操作检查清单

在执行任何 Dataverse 操作前，确认：

- [ ] 是否已通过 MCP 工具调用？
  - 是 → 直接执行，工具已处理认证
  - 否 → 进入下一步检查

- [ ] 是否在 Python 代码中？
  - 是 → 确认使用了 `core_agent.get_client()` 获取 client
  - 否 → 需要先获取认证的 client

- [ ] 是否尝试直接创建 DataverseClient？
  - 是 → 改为使用 core_agent.get_client()
  - 否 → 继续

- [ ] 认证是否有效？
  - 不确定 → 调用 `auth_status` 工具检查
  - 有效 → 继续操作

## MCP 工具参考

### 认证相关

| 工具 | 用途 |
|------|------|
| `auth_login` | 登录/认证（用户已完成） |
| `auth_status` | 检查认证状态 |
| `auth_logout` | 登出 |

### 元数据操作

| 工具 | 用途 |
|------|------|
| `metadata_apply_yaml` | 应用 YAML 定义（核心） |
| `metadata_plan` | 预览变更 |
| `metadata_create_table` | 创建表 |
| `metadata_list` | 列出元数据 |
| `metadata_delete_attribute` | 删除字段 |
| `metadata_delete_relationship` | 删除关系 |

## 快速参考

### 获取认证的 client

```python
# 在代码中获取已认证的 client
from framework.agents.core_agent import CoreAgent

core_agent = CoreAgent()
client = core_agent.get_client()  # 已认证！

# 或通过 MetadataAgent
metadata_agent = MetadataAgent(core_agent=core_agent)
manager = metadata_agent.get_metadata_manager()  # 使用已认证的 client
```

### 调用 Dataverse API

#### 基础查询操作

```python
# 查询实体元数据
entity = client.get_entity_metadata("account")
print(f"Entity: {entity['SchemaName']}")

# 查询实体所有属性
attrs = client.get_attributes("account")
for attr in attrs:
    print(f"  - {attr['SchemaName']}: {attr.get('@odata.type', '')}")

# 查询实体所有关系
relationships = client.get_relationships("account")
```

#### 同步 Metadata YAML

**场景 1: 应用 YAML 创建或更新表**

```python
from framework.agents.metadata_agent import MetadataAgent
from framework.agents.core_agent import CoreAgent
import asyncio

async def sync_table():
    core_agent = CoreAgent()
    metadata_agent = MetadataAgent(core_agent=core_agent)

    # 应用 YAML 定义 - 自动检测差异并应用变更
    result = await metadata_agent.apply_yaml(
        "metadata/tables/payment_recognition.yaml",
        {}
    )

    import json
    result_data = json.loads(result)

    if result_data.get("success"):
        print(f"✓ 同步成功!")
        print(f"  创建/更新的字段: {result_data.get('changes_summary', {})}")
        print(f"  创建/更新的关系: {result_data.get('summary', {})}")
    else:
        print(f"✗ 同步失败: {result_data.get('error')}")

# 运行
asyncio.run(sync_table())
```

**场景 2: 预览 YAML 变更（不执行）**

```python
async def plan_changes():
    core_agent = CoreAgent()
    metadata_agent = MetadataAgent(core_agent=core_agent)

    # 预览将要应用的变更
    result = await metadata_agent.plan_changes(
        "metadata/tables/payment_recognition.yaml"
    )

    import json
    plan = json.loads(result)

    print(f"实体: {plan['entity']}")
    print(f"有变更: {plan['has_changes']}")
    print(f"变更摘要: {plan['summary']}")

    for change in plan.get('changes', []):
        print(f"  - {change['change_type']}: {change['target_type']} - {change['target_name']}")

asyncio.run(plan_changes())
```

**场景 3: 批量同步多个 YAML 文件**

```python
async def sync_multiple_tables():
    core_agent = CoreAgent()
    metadata_agent = MetadataAgent(core_agent=core_agent)

    yaml_files = [
        "metadata/tables/account.yaml",
        "metadata/tables/contact.yaml",
        "metadata/tables/payment_recognition.yaml"
    ]

    results = {}
    for yaml_file in yaml_files:
        print(f"正在同步: {yaml_file}")
        result = await metadata_agent.apply_yaml(yaml_file)
        results[yaml_file] = json.loads(result)

    # 输出汇总
    for yaml_file, result in results.items():
        status = "✓" if result.get("success") else "✗"
        print(f"{status} {yaml_file}")
        if not result.get("success"):
            print(f"    错误: {result.get('error', 'Unknown error')[:100]}")

asyncio.run(sync_multiple_tables())
```

**场景 4: 检查实体当前状态**

```python
def check_entity_status():
    core_agent = CoreAgent()
    client = core_agent.get_client()

    entity_name = "new_payment_recognition"

    # 获取实体元数据
    entity = client.get_entity_metadata(entity_name)
    print(f"实体名称: {entity['DisplayName']['UserLocalizedLabel']['Label']}")
    print(f"Schema Name: {entity['SchemaName']}")

    # 获取所有属性
    attrs = client.get_attributes(entity_name)
    print(f"\n字段数量: {len(attrs)}")

    lookup_attrs = [a for a in attrs if 'Lookup' in a.get('@odata.type', '')]
    print(f"查找字段: {len(lookup_attrs)}")
    for attr in lookup_attrs:
        print(f"  - {attr['SchemaName']} -> {attr.get('Targets', [])}")

    # 获取所有关系
    relationships = client.get_relationships(entity_name)
    print(f"\n关系数量: {len(relationships)}")

    for rel in relationships:
        rel_type = rel.get('@odata.type', '')
        if 'OneToMany' in rel_type:
            print(f"  - {rel['SchemaName']}: {rel['ReferencingEntity']} -> {rel['ReferencedEntity']}")

check_entity_status()
```

**场景 5: 删除字段或关系**

```python
async def delete_metadata():
    core_agent = CoreAgent()
    metadata_agent = MetadataAgent(core_agent=core_agent)

    # 删除字段
    result = await metadata_agent.delete_attribute(
        entity="new_payment_recognition",
        attribute_name="new_old_field"
    )
    print(json.loads(result))

    # 删除关系
    result = await metadata_agent.delete_relationship(
        entity="new_payment_recognition",
        relationship_name="old_relationship_name"
    )
    print(json.loads(result))

asyncio.run(delete_metadata())
```

#### 数据记录操作

```python
# 创建记录
result = client.create_record("account", {
    "name": "Test Account",
    "new_custom_field": "Custom Value"
})
print(f"创建的记录ID: {result['id']}")

# 查询记录
records = client.query_records(
    "account",
    select=["name", "accountid", "createdon"],
    filter="statecode eq 0",  # 只查活跃记录
    order_by="createdon desc",
    top=10
)

for record in records:
    print(f"  - {record['name']} ({record['accountid']})")

# 更新记录
client.update_record("account", record_id, {
    "name": "Updated Account Name"
})
```

#### 使用 MetadataManager 进行高级操作

```python
from framework.agents.metadata_manager import MetadataManager

def advanced_metadata_ops():
    core_agent = CoreAgent()
    manager = MetadataManager(core_agent.get_client())

    entity_name = "new_payment_recognition"

    # 获取当前完整状态
    current_state = manager.get_current_state(entity_name)
    print(f"当前字段数: {len(current_state['attributes'])}")
    print(f"当前关系数: {len(current_state['relationships'])}")

    # 加载期望的 YAML 定义
    import yaml
    with open("metadata/tables/payment_recognition.yaml") as f:
        desired_metadata = yaml.safe_load(f)

    # 计算差异
    diff = manager.compute_diff(entity_name, desired_metadata)

    print(f"\n需要应用的变更:")
    print(f"  摘要: {diff.summary()}")

    for change in diff.changes:
        print(f"  - {change.change_type}: {change.target_type} - {change.target_name}")

    # 应用变更
    if diff.has_changes():
        result = manager.apply_diff(diff, desired_metadata)
        print(f"\n应用结果:")
        print(f"  成功: {len(result['applied'])}")
        print(f"  失败: {len(result['failed'])}")

advanced_metadata_ops()
```

#### 导出实体元数据到 YAML

```python
async def export_entity_to_yaml():
    core_agent = CoreAgent()
    metadata_agent = MetadataAgent(core_agent=core_agent)

    # 导出实体元数据为 YAML
    result = await metadata_agent.export(
        entity="new_payment_recognition",
        output_dir="metadata/exported",
        metadata_type="table"
    )

    print(json.loads(result))

asyncio.run(export_entity_to_yaml())
```

## 需要用户重新认证的情况

如果出现以下情况，提示用户调用 `auth_login`：

1. 所有操作都返回 401/403 错误
2. `auth_status` 显示未认证
3. Token 已过期（通常1小时后）

## 示例：正确的完整流程

```python
# 1. 用户先调用 auth_login（用户在 Claude Code 界面完成）
# {"tool": "auth_login", "arguments": {"client_id": "...", "client_secret": "..."}}

# 2. Agent 执行操作（使用已认证的会话）
from framework.agents.metadata_agent import MetadataAgent
from framework.agents.core_agent import CoreAgent

core_agent = CoreAgent()
metadata_agent = MetadataAgent(core_agent=core_agent)

# 3. 应用 YAML 定义
result = await metadata_agent.apply_yaml(
    "metadata/tables/payment_recognition.yaml",
    {}
)

# 4. 解析结果
import json
result_data = json.loads(result)
print(result_data)
```

## 记住

**不要绕过 core_agent 直接创建 DataverseClient！**

所有 Dataverse 操作都应通过：
1. MCP 工具（推荐）
2. core_agent.get_client() 获取已认证的 client
3. MetadataAgent 或其他已初始化的 Agent
