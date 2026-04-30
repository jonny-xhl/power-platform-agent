# Power Platform 元数据规范

## 选项集 (Option Set) 元数据

### 全局选项集

全局选项集定义在 `metadata/optionsets/global_optionsets.yaml` 中，可被多个表引用。

```yaml
global_optionsets:
  - schema_name: new_customer_status
    display_name: 客户状态
    display_name_en: Customer Status
    description: 客户的业务状态
    options:
      - value: 1
        label_zh: 潜在客户
        label_en: Potential
        color: 808080
      - value: 2
        label_zh: 活跃客户
        label_en: Active
        color: 008000
```

### 选项集字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `schema_name` | string | 是 | 选项集 Schema Name |
| `display_name` | string | 是 | 中文显示名称 |
| `display_name_en` | string | 否 | 英文显示名称 |
| `description` | string | 否 | 选项集描述 |
| `options` | array | 是 | 选项列表 |

### 选项字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `value` | integer | 是 | 选项值 |
| `label_zh` | string | 是 | 中文标签 |
| `label_en` | string | 否 | 英文标签 |
| `color` | string | 否 | 颜色代码 (hex) |

### 在表中引用选项集

表定义中可以通过以下两种方式使用选项集：

#### 1. 引用全局选项集

```yaml
attributes:
  - name: status
    type: Picklist
    display_name: 状态
    option_set_ref: new_customer_status  # 引用全局选项集
```

#### 2. 定义本地选项集

```yaml
attributes:
  - name: region
    type: Picklist
    display_name: 地区
    local_options:  # 本地选项集
      - value: 1
        label_zh: 华东
        label_en: East China
      - value: 2
        label_zh: 华南
        label_en: South China
```

### 虚拟字段过滤规则

数据字典生成时会自动过滤以下虚拟字段：

| 类型 | 检测模式 | 示例 |
|------|----------|------|
| Lookup _name 后缀 | `_[a-z]+_name$` | `primarycontactid_name` |
| 计算字段 | `is_calculated: true` | - |
| 汇总字段 | `aggregate_type` 存在 | - |
| Virtual 类型 | `type: "Virtual"` | - |

---

## 表 (Table) 元数据

### 必需字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema.schema_name` | string | 表的Schema名称（自动加前缀） |
| `schema.display_name` | string | 显示名称 |
| `schema.ownership_type` | string | 所有者类型 |

### 可选字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `schema.description` | string | - | 表描述 |
| `schema.has_activities` | boolean | false | 是否启用活动 |
| `schema.has_notes` | boolean | false | 是否启用注释 |

### 字段类型

支持的字段类型：

| 类型 | 说明 | 特殊属性 |
|------|------|----------|
| `String` | 字符串 | `max_length` |
| `Integer` | 整数 | `min_value`, `max_value` |
| `Money` | 货币 | `precision`, `min_value` |
| `Picklist` | 选项集 | `option_set_ref` 或 `local_options` |
| `MultiSelectPicklist` | 多选选项集 | `options` |
| `Lookup` | 查找 | `entity`, `relationship_name` |
| `Customer` | 客户查找 | - |
| `Owner` | 所有者查找 | - |
| `DateTime` | 日期时间 | - |
| `Boolean` | 是/否 | - |
| `Memo` | 多行文本 | `max_length` |
| `Decimal` | 小数 | `precision`, `min_value`, `max_value` |
| `Double` | 双精度浮点 | `min_value`, `max_value` |
| `BigInt` | 大整数 | `min_value`, `max_value` |

### Picklist 字段详细规范

Picklist 类型字段必须使用以下两种方式之一定义选项：

**方式一：引用全局选项集 (推荐)**

```yaml
- name: customer_status
  type: Picklist
  display_name: 客户状态
  required: true
  option_set_ref: new_customer_status
```

**方式二：本地选项集**

```yaml
- name: region
  type: Picklist
  display_name: 地区
  required: false
  local_options:
    - value: 1
      label: 华东
      color: 008000
    - value: 2
      label: 华南
```

### 字段虚拟属性

用于标识特殊字段的属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `is_calculated` | boolean | 标识为计算字段 |
| `aggregate_type` | string | 汇总字段类型 (如: sum, count) |
| `is_primary_name` | boolean | 是否为主名称字段 |

**注意**：包含以上属性的虚拟字段在生成数据字典时会被自动过滤。

## 表单 (Form) 元数据

### 表单类型

- `Main` - 主表单
- `QuickCreate` - 快速创建表单
- `QuickView` - 快速视图表单
- `Card` - 卡片表单
- `MainInteraction` - 交互对话框

### 结构定义

```yaml
form:
  schema_name: "account_main_form"
  entity: "account"
  type: "Main"
  display_name: "账户主表单"

  tabs:
    - name: "general"
      display_name: "常规"
      sections:
        - name: "basicInfo"
          display_name: "基本信息"
          rows:
            - cells:
                - attribute: "name"
                  width: "1"
```

## 视图 (View) 元数据

### 视图类型

- `PublicView` - 公共视图
- `PrivateView` - 私有视图
- `AdvancedFind` - 高级查找视图
- `AssociatedView` - 关联视图
- `QuickFindView` - 快速查找视图
- `LookupView` - 查找视图

### Fetch XML 操作符

支持的操作符：

- `eq` - 等于
- `ne` - 不等于
- `gt` - 大于
- `ge` - 大于等于
- `lt` - 小于
- `le` - 小于等于
- `like` - 相似
- `in` - 包含于
- `between` - 介于
- `null` - 为空
- `today` - 今天
- `this-week` - 本周
- `this-month` - 本月
- `this-year` - 今年

## Web Resource 元数据

### 资源类型

| 类型 | 扩展名 | MIME类型 |
|-----|--------|---------|
| CSS | .css | text/css |
| JavaScript | .js | text/javascript |
| HTML | .html | text/html |
| PNG | .png | image/png |
| JPEG | .jpg | image/jpeg |
| GIF | .gif | image/gif |
| SVG | .svg | image/svg+xml |
| ICO | .ico | image/x-icon |
| XAP | .xap | application/x-silverlight-app |
| XML | .xml | text/xml |
| XSLT | .xslt | text/xslt |

### 命名模式

```
{prefix}{category}/{name}.{ext}
```

示例：
- `new_css/account_form.css`
- `new_js/account_handler.js`
- `new_html/dashboard.html`

## Ribbon (命令栏) 元数据

### 按钮位置

位置格式：`Mscrm.{Location}.{Entity}.{Tab}.{Group}`

常用位置：
- `Mscrm.HomepageGrid.{entity}.MainTab.Actions` - 主页网格操作
- `Mscrm.Form.{entity}.MainTab.Actions` - 表单操作
- `Mscrm.HomepageGrid.{entity}.ContextMenu` - 右键菜单

### 命令类型

- `javascript` - JavaScript 函数
- `popup` - 弹出窗口
- `navigation` - 导航到 URL
- `event` - 触发事件

### 规则类型

显示规则：
- `selectioncount` - 选择计数
- `customrule` - 自定义规则
- `entityrule` - 实体规则
- `formrule` - 表单规则

启用规则：
- `customrule` - 自定义规则
- `formrule` - 表单规则
- `ocrulerule` - OCR 规则

## Sitemap (应用导航) 元数据

### 子区域类型

- `entity` - 实体列表
- `dashboard` - 仪表板
- `webresource` - Web Resource 页面
- `url` - 外部 URL

### 结构定义

```yaml
sitemap:
  schema_name: "customer_app_sitemap"
  display_name: "客户管理应用"

  areas:
    - name: "customerArea"
      display_name: "客户区域"
      groups:
        - name: "customerGroup"
          display_name: "客户管理"
          subareas:
            - name: "account"
              type: "entity"
              entity: "account"
              default_view: "account_active_view"
```

## 插件元数据

### 消息阶段

- `pre-validation` - 验证前 (Stage 10)
- `pre-operation` - 操作前 (Stage 20)
- `post-operation` - 操作后 (Stage 40)

### 执行模式

- `0` - 同步
- `1` - 异步

### 部署类型

- `0` - 仅服务器端
- `1` - 仅 Microsoft Dynamics 365 for Outlook
- `2` - 两者

## 关系类型

### OneToMany 属性

- `cascade_assign` - 级联分配
- `cascade_delete` - 级联删除
- `cascade_reparent` - 级联重新分配父级
- `cascade_share` - 级联共享
- `cascade_unshare` - 级联取消共享

### 级联类型

- `NoCascade` - 无操作
- `Cascade` - 级联
- `Active` - 激活级联
- `RemoveLink` - 移除链接
- `Restrict` - 限制

## 标准实体保护

以下标准实体不会被命名转换影响：

系统核心：`account`, `contact`, `systemuser`, `team`, `businessunit`, `role`

活动相关：`activitypointer`, `email`, `appointment`, `task`, `phonecall`, `letter`, `fax`

销售相关：`lead`, `opportunity`, `competitor`, `quote`, `salesorder`, `invoice`

完整列表请参考 `config/naming_rules.yaml`。

---

## 元数据文件组织

### 项目目录结构

```
power-platform-agent/
├── framework/             # 框架层 (可复用核心组件)
│   ├── agents/            # 代理实现
│   │   ├── core_agent.py
│   │   ├── metadata_agent.py
│   │   ├── plugin_agent.py
│   │   └── solution_agent.py
│   ├── utils/             # 工具函数
│   └── mcp_serve.py       # MCP服务入口
│
├── metadata/              # 元数据层
│   ├── _schema/           # Schema 定义文件
│   ├── tables/            # 表定义 (*.yaml)
│   ├── forms/             # 表单定义 (*.yaml)
│   ├── views/             # 视图定义 (*.yaml)
│   ├── optionsets/        # 选项集定义
│   ├── webresources/      # Web Resource 配置
│   ├── ribbon/            # 命令栏定义
│   └── sitemap/           # 应用导航定义
│
├── sources/               # 源文件层
│   ├── templates/         # Excel/Word/PPT模板
│   ├── features/          # 按功能迭代组织
│   └── library/           # 可复用YAML片段
│
├── docs/                  # 文档层
│   ├── spec/              # 规范文档
│   ├── guides/            # 使用指南
│   └── data_dictionary/   # Git hook自动生成
│
├── scripts/               # 脚本层
│   ├── generate_data_dictionary.py
│   └── hooks/             # Git hooks
│
├── config/                # 配置文件
├── plugins/               # .NET插件
├── webresources/          # Web资源源文件
└── .claude/               # Claude Code配置
```

### 命名规范

**文件命名**：
- 使用小写字母和下划线
- 表定义文件: `{schema_name}.yaml`
- 例如: `account.yaml`, `contact.yaml`

**Schema 引用**：
```yaml
# 表定义文件顶部引用 Schema
$schema: "../_schema/table_schema.yaml"
```

---

## 数据字典生成

### 自动生成

项目配置了 Git pre-commit hook，在提交元数据变更时自动生成数据字典。

### 手动生成

```bash
# 生成所有文档
python scripts/generate_data_dictionary.py --all

# 生成指定文件
python scripts/generate_data_dictionary.py --files metadata/tables/account.yaml
```

### 生成内容

```
docs/data_dictionary/
├── index.md              # 汇总索引
├── all_tables.md         # 所有表结构汇总
├── all_optionsets.md     # 所有选项集汇总
├── tables/               # 单表详细文档
│   ├── account.md
│   └── contact.md
└── optionsets/           # 选项集详细文档
    ├── new_customer_status.md
    └── new_payment_terms.md
```

---

## 组件库复用

### 表片段

位于 `sources/library/table_fragments/`，包含可复用的字段组：

- `standard_audit_fields.yaml` - 标准审计字段
- `address_fields.yaml` - 地址字段
- `contact_info_fields.yaml` - 联系人信息字段

### 表单模式

位于 `sources/library/form_patterns/`，包含常用表单布局：

- `standard_header_form.yaml` - 标准表单头部

### 视图模式

位于 `sources/library/view_patterns/`，包含常用视图定义：

- `active_records_view_template.yaml` - 活跃记录视图模板

---

## 相关文档

- [架构文档](architecture.md) - 系统架构设计
- [快速开始](../guides/getting-started.md) - 详细入门指南
- [数据字典](../data_dictionary/index.md) - 生成的数据字典索引
