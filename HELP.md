# Power Platform Agent - 工具帮助文档

> 快速查询所有 MCP 工具的调用方式

---

## 目录

- [认证与环境](#认证与环境)
- [命名规则](#命名规则)
- [元数据管理](#元数据管理)
- [Web Resources](#web-resources)
- [插件管理](#插件管理)
- [解决方案管理](#解决方案管理)
- [扩展与系统](#扩展与系统)

---

## 认证与环境

| 工具名 | 功能 | 参数 | 示例 |
|-------|------|-----|------|
| `auth_login` | 连接到Dataverse环境 | `environment` (可选) | `连接到 dev 环境` |
| `auth_status` | 查看连接状态 | - | `查看连接状态` |
| `auth_logout` | 断开连接 | `environment` (可选) | `登出当前环境` |
| `environment_switch` | 切换环境 | `environment` | `切换到 test 环境` |
| `environment_list` | 列出所有环境 | - | `列出所有配置的环境` |

---

## 命名规则

| 工具名 | 功能 | 参数 | 示例 |
|-------|------|-----|------|
| `naming_convert` | 命名转换 | `input`, `type`=`schema_name`, `is_standard`=`false` | `将 "AccountName" 转换为 schema_name` |
| `naming_validate` | 验证命名 | `name`, `type`=`schema_name` | `验证 "new_account" 是否符合规则` |
| `naming_bulk_convert` | 批量转换 | `items`, `type` | `批量转换 [AccountName, CustomerType] 为 schema_name` |
| `naming_rules_list` | 查看命名规则 | - | `显示当前命名规则配置` |

### 命名类型说明

- `schema_name` - 表/字段命名（如 `new_account_name`）
- `webresource` - Web Resource命名（如 `new_css/style.css`）

---

## 元数据管理

| 工具名 | 功能 | 参数 | 示例 |
|-------|------|-----|------|
| `metadata_parse` | 解析YAML文件 | `file_path`, `type` (可选) | `解析 metadata/tables/account.yaml` |
| `metadata_validate` | 验证元数据 | `metadata_yaml`, `schema` | `验证 account.yaml 的 table_schema` |
| `metadata_create_table` | 创建数据表 | `table_yaml`, `options` | `创建一个客户表` |
| `metadata_create_attribute` | 创建字段 | `attribute_yaml`, `entity` | `为 account 表添加余额字段` |
| `metadata_create_form` | 创建表单 | `form_yaml` | `创建账户主表单` |
| `metadata_create_view` | 创建视图 | `view_yaml` | `创建活跃账户视图` |
| `metadata_export` | 导出元数据 | `entity`, `output_dir`, `metadata_type` | `导出 account 表为 YAML` |
| `metadata_diff` | 对比差异 | `local_path`, `entity` | `对比本地与云端 account 表差异` |
| `metadata_apply` | 应用元数据 | `metadata_type`, `name`, `environment` | `将 customer 表应用到 Dataverse` |
| `metadata_list` | 列出元数据 | `type`, `entity` (可选) | `列出所有表 / 列出 account 表的所有字段` |

### 元数据类型

- `table` - 数据表
- `form` - 表单
- `view` - 视图
- `webresource` - Web Resource

---

## Web Resources

| 工具名 | 功能 | 参数 | 示例 |
|-------|------|-----|------|
| `webresource_parse` | 解析WR配置 | `config_path` | `解析 webresources/account_form.yaml` |
| `webresource_deploy` | 部署WR | `source_path`, `resource_type` | `部署 account_form.css` |
| `webresource_batch` | 批量部署 | `config_path`, `filter` | `批量部署所有 CSS 文件` |
| `webresource_list` | 列出WR | `entity` (可选), `type` (可选) | `列出 account 表的所有 Web Resources` |
| `webresource_naming_check` | 检查命名 | `names` | `检查这些命名是否符合规则` |

---

## 插件管理

| 工具名 | 功能 | 参数 | 示例 |
|-------|------|-----|------|
| `plugin_build` | 构建插件 | `project_path`, `configuration`=`Release` | `构建 AccountPlugin.csproj` |
| `plugin_deploy` | 部署插件 | `assembly_path`, `environment` | `部署 AccountPlugin.dll` |
| `plugin_step_register` | 注册Step | `plugin_name`, `entity`, `message`, `stage`, `config` | `为 account/Create 注册插件Step` |
| `plugin_step_update` | 更新Step | `step_id`, `config` | `更新 Step 配置` |
| `plugin_step_list` | 列出Steps | `plugin_name` (可选), `entity` (可选) | `列出 AccountPlugin 的所有 Steps` |
| `plugin_step_delete` | 删除Step | `step_id` | `删除指定 Step` |
| `plugin_assembly_list` | 列出程序集 | - | `列出已部署的插件程序集` |
| `plugin_watch` | 监听模式 | `project_path` | `开启插件监听模式` |
| `plugin_info` | 插件信息 | `project_path` | `查看插件项目信息` |

### Step 阶段说明

- `pre-validation` - 验证前
- `pre-operation` - 操作前
- `post-operation` - 操作后

### 常用消息

- `Create`, `Update`, `Delete`, `Retrieve`, `RetrieveMultiple`

---

## 解决方案管理

| 工具名 | 功能 | 参数 | 示例 |
|-------|------|-----|------|
| `solution_export` | 导出解决方案 | `solution_name`, `managed`=`false`, `output_path` | `导出 MySolution 解决方案` |
| `solution_import` | 导入解决方案 | `solution_path`, `environment`, `publish`=`true` | `导入 MySolution.zip` |
| `solution_diff` | 对比差异 | `local_path`, `solution_name` | `对比本地与解决方案差异` |
| `solution_sync` | 执行同步 | `direction`, `components`, `environment` | `执行本地到云端同步` |
| `solution_pack` | 打包解决方案 | `components`, `output_path` | `打包组件为解决方案` |
| `solution_status` | 同步状态 | - | `查看同步状态` |
| `solution_add_component` | 添加组件 | `component_type`, `component_id`, `solution_name` | `将表添加到解决方案` |
| `solution_list` | 列出解决方案 | - | `列出所有解决方案` |
| `solution_clone` | 克隆解决方案 | `source_solution`, `target_solution` | `克隆解决方案` |
| `solution_upgrade` | 升级解决方案 | `solution_name` | `升级解决方案` |

### 同步方向

- `local_to_remote` - 本地到云端
- `remote_to_local` - 云端到本地
- `bidirectional` - 双向同步

---

## 扩展与系统

| 工具名 | 功能 | 参数 | 示例 |
|-------|------|-----|------|
| `extension_register` | 注册扩展 | `handler_type`, `module`, `class` | `注册自定义验证器` |
| `extension_list` | 列出扩展 | - | `列出已注册的扩展` |
| `extension_hook_register` | 注册钩子 | `hook_point`, `function` | `注册应用前钩子` |
| `health_check` | 健康检查 | `environment` (可选) | `检查环境连接状态` |

---

## 快速命令速查

```bash
# === 认证 ===
连接到 dev 环境
查看连接状态
切换到 test 环境

# === 表操作 ===
创建一个客户表，包含账户编号、余额字段
验证 customer.yaml
将 customer 表应用到 Dataverse
导出 account 表为 YAML

# === 命名 ===
将 "CustomerName" 转换为 schema_name
验证 "new_account" 命名
显示命名规则

# === 插件 ===
构建 AccountPlugin.csproj
部署 AccountPlugin.dll
为 account/Create 注册插件Step
列出所有 Steps

# === 解决方案 ===
导出 MySolution
导入 solutions/MySolution.zip
对比本地与云端差异
查看同步状态
```

---

## 工作流程示例

### 创建新表的完整流程

```
1. 描述需求
   "创建一个产品表，包含产品编号、名称、价格、库存"

2. 验证生成的YAML
   "验证 product.yaml"

3. 检查命名
   "验证 new_product 是否符合规则"

4. 应用到Dataverse
   "将 product 表应用到 Dataverse"
```

### 插件开发流程

```
1. 构建插件
   "构建 plugins/MyPlugin/MyPlugin.csproj"

2. 部署程序集
   "部署 MyPlugin.dll 到 dev 环境"

3. 注册Step
   "为 account/Create 注册插件Step，阶段为 post-operation"

4. 验证
   "列出 MyPlugin 的所有 Steps"
```

---

## 参数格式说明

### JSON 格式输入

对于复杂数据，可以使用 JSON 格式：

```json
{
  "attributes": [
    {"name": "fieldName", "type": "String", "required": true}
  ]
}
```

### 环境参数

所有支持 `environment` 参数的工具都支持：
- `dev` - 开发环境
- `test` - 测试环境
- `production` - 生产环境

---

## 错误处理

常见错误及解决：

| 错误 | 原因 | 解决 |
|-----|------|------|
| `Not authenticated` | 未登录 | 先执行 `连接到环境` |
| `Schema not found` | 文件不存在 | 检查文件路径 |
| `Validation errors` | 格式错误 | 使用 `验证` 工具检查 |
| `Component exists` | 命名冲突 | 使用不同名称或 `命名转换` |

---

## 获取帮助

在 Claude Code 中，你可以：

1. **自然语言描述**：直接说出你想做什么
   ```
   "我需要创建一个订单表"
   ```

2. **查看工具列表**：
   ```
   "列出所有可用的工具"
   ```

3. **获取具体工具帮助**：
   ```
   "如何使用 metadata_create_table 工具？"
   ```
