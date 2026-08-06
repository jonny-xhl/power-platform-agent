# SO 实体新增字段执行报告

## 任务
给 SO 实体 (`new_spare_salesorder`) 新增一个 255 长度的字符串字段：打包备注 / Remark / `new_package_remark`，解决方案 `20260806_fix`。

## 执行路径

### Step 1: 查找 SO 实体
- SO 实体不在本地 metadata_py 中，需要从远程 Dataverse 查找
- `pp list --remote` 列出所有自定义表，搜索发现 SO = `new_spare_salesorder`（SO信息），101 列 34 关系

### Step 2: Reverse 实体定义
- `pp reverse new_spare_salesorder` → 生成 `metadata_py/tables/new_spare_salesorder.py`（101 cols, 34 rels）
- `pp reverse new_spare_salesorder --dictionary` → 生成数据字典 Markdown

### Step 3: 添加新字段定义
- 在 `new_spare_salesorder.py` 的 columns 列表中插入一行：
  ```python
  Column('new_package_remark', AttributeType.String,
         display_name=Label.bilingual('打包备注', 'Remark'),
         max_length=255, format_name='Text', format='Text')
  ```
- `pp list` 确认列数从 101 → 102
- `pp show new_spare_salesorder` 验证 JSON payload 中包含新字段，MaxLength=255

### Step 4: 部署到 Dataverse
- `pp deploy new_spare_salesorder --solution 20260806_fix --solution-clean`
- 结果：
  - `new_package_remark`: **action: created** ✅
  - 其余 100 个自定义属性: action: skipped（已存在）
  - 4 个标准属性: action: skipped_standard
  - 34 个关系: action: skipped（已存在）
  - 实体属性更新: skipped（Web API 不支持）
  - 解决方案 `20260806_fix`: 所有自定义字段（含新字段）以 clean 模式添加

### Step 5: 刷新数据字典
- `pp reverse new_spare_salesorder --dictionary` → 更新数据字典，确认 `new_package_remark` 已出现

## CLI 命令序列
```bash
# 1. 查找实体
pp list --remote

# 2. Reverse 实体定义
pp reverse new_spare_salesorder
pp reverse new_spare_salesorder --dictionary

# 3. 编辑定义文件（手动添加字段）
# metadata_py/tables/new_spare_salesorder.py

# 4. 验证
pp list
pp show new_spare_salesorder

# 5. 部署
pp deploy new_spare_salesorder --solution 20260806_fix --solution-clean

# 6. 刷新数据字典
pp reverse new_spare_salesorder --dictionary
```

## 结论
字段 `new_package_remark`（打包备注 / Remark，String 255）已成功创建并加入解决方案 `20260806_fix`。引擎的 reverse → edit → deploy 流程验证通过。
