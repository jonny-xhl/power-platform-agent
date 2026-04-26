# 元数据管理功能实现总结

## 已实现的功能

### 1. 核心架构

#### MetadataManager (`framework/agents/metadata_manager.py`)
完整的元数据管理器，负责：
- 状态查询 (`get_current_state`)
- 差异计算 (`compute_diff`)
- 变更应用 (`apply_diff`)

#### MetadataAgent 增强 (`framework/agents/metadata_agent.py`)
新增方法：
- `apply_yaml()` - 应用YAML定义（核心方法）
- `plan_changes()` - 预览变更（dry run）
- `delete_attribute()` - 删除字段
- `delete_relationship()` - 删除关系
- `sync_relationships()` - 同步关系

### 2. 支持的操作

| 操作 | 状态 | MCP工具 | 说明 |
|------|------|---------|------|
| 创建表 | ✅ | metadata_apply_yaml | 新建实体 |
| 修改表 | ✅ | metadata_apply_yaml | 自动检测差异并更新 |
| 创建字段 | ✅ | metadata_apply_yaml | 支持所有标准类型 |
| 修改字段 | ✅ | metadata_apply_yaml | 更新显示名、描述、必填状态等 |
| 删除字段 | ✅ | metadata_delete_attribute | 删除指定字段 |
| 创建关系 | ✅ | metadata_apply_yaml | Deep Insert模式 |
| 删除关系 | ✅ | metadata_delete_relationship | 删除指定关系 |
| 本地选项集 | ✅ | metadata_apply_yaml | Picklist字段 |
| 全局选项集 | ✅ | metadata_apply_yaml | 引用全局选项集 |

### 3. 字段类型支持

- String (文本)
- Memo (多行文本)
- Integer (整数)
- Money (货币)
- Decimal (小数)
- Double (双精度)
- BigInt (大整数)
- DateTime (日期时间)
- Boolean (布尔)
- Picklist (选项集)
- MultiSelectPicklist (多选选项集)
- Lookup (查找)
- Customer (客户)
- Owner (所有者)
- Status (状态)
- State (状态原因)

### 4. 关系类型支持

- ManyToOne (多对一) - 通过Deep Insert创建
- OneToMany (一对多)
- ManyToMany (多对多)

### 5. 级联配置

所有级联类型均支持：
- Cascade (Active)
- NoCascade
- RemoveLink
- Restrict
- UserOwned

### 6. 差异计算

自动检测以下变更：
- 实体不存在 → 创建实体
- 属性不存在 → 创建属性
- 属性显示名/描述/必填状态变更 → 更新属性
- 关系不存在 → 创建关系（Deep Insert）
- 关系级联配置变更 → 更新关系
- 选项集选项变更 → 更新选项集

### 7. Deep Insert 模式

Lookup字段和关系通过Deep Insert创建：
- Lookup定义在 `lookup_attributes` 中
- 关系定义在 `relationships` 中
- 创建关系时自动嵌入Lookup属性
- 一次API调用同时创建两者

### 8. 全局选项集支持

Picklist字段可以引用全局选项集：
```yaml
attributes:
  - name: "new_status"
    type: "Picklist"
    global_option_set: "global_status_codes"
```

## MCP 工具

### 新增工具

| 工具名 | 功能 |
|--------|------|
| metadata_apply_yaml | 应用YAML定义（核心） |
| metadata_plan | 预览变更（dry run） |
| metadata_delete_attribute | 删除字段 |
| metadata_delete_relationship | 删除关系 |
| metadata_sync_relationships | 同步关系 |

### 更新的工具

| 工具名 | 更新内容 |
|--------|----------|
| metadata_create_table | 保持向后兼容 |
| metadata_create_attribute | 保持向后兼容 |

## 文件变更

### 新增文件
- `framework/agents/metadata_manager.py` - 元数据管理器
- `docs/metadata-management.md` - 用户文档

### 修改文件
- `framework/agents/metadata_agent.py` - 增加新方法和工具处理
- `framework/utils/dataverse_client.py` - 支持全局选项集、Deep Insert
- `framework/mcp_serve.py` - 新增MCP工具定义
- `metadata/_schema/table_schema.yaml` - Schema增强

## YAML 结构

```yaml
$schema: "../_schema/table_schema.yaml"

schema:
  schema_name: "entity_name"
  display_name: "显示名称"
  # ... 其他实体属性

attributes:
  - name: "field_name"
    type: "String"
    display_name: "字段名"
    # ... 其他字段属性

lookup_attributes:
  - name: "lookup_field_name"
    type: "Lookup"
    target: "related_entity"
    # ... 其他查找属性

relationships:
  - name: "related_entity_current_entity"
    related_entity: "related_entity"
    relationship_type: "ManyToOne"
    referencing_attribute: "lookup_field_name"
    # ... 级联配置
```

## 使用示例

### 1. 创建新表

```json
{
  "tool": "metadata_apply_yaml",
  "arguments": {
    "table_yaml": "metadata/tables/new_entity.yaml"
  }
}
```

### 2. 预览变更

```json
{
  "tool": "metadata_plan",
  "arguments": {
    "table_yaml": "metadata/tables/new_entity.yaml"
  }
}
```

### 3. 删除字段

```json
{
  "tool": "metadata_delete_attribute",
  "arguments": {
    "entity": "new_entity",
    "attribute_name": "new_old_field"
  }
}
```

### 4. 删除关系

```json
{
  "tool": "metadata_delete_relationship",
  "arguments": {
    "entity": "new_entity",
    "relationship_name": "old_relationship"
  }
}
```

## 技术细节

### 差异检测算法

1. 获取当前状态（通过Dataverse API）
2. 解析期望状态（从YAML）
3. 逐项比较：
   - 实体级别
   - 属性级别
   - 关系级别
4. 生成变更列表

### 变更应用顺序

1. 创建实体（如不存在）
2. 创建普通属性（非Lookup）
3. 创建关系（通过Deep Insert，同时创建Lookup）

### 错误处理

- 部分失败继续执行
- 返回详细的成功/失败列表
- 提供错误追踪信息

## 后续扩展方向

1. **表单和视图管理**
   - 创建/修改表单
   - 创建/修改视图

2. **全局选项集管理**
   - 创建全局选项集
   - 更新全局选项集选项

3. **解决方案管理**
   - 添加到解决方案
   - 解决方案导入/导出

4. **批量操作**
   - 批量应用多个YAML
   - 增量同步

5. **回滚功能**
   - 记录变更历史
   - 支持回滚到之前版本
