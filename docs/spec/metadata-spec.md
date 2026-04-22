# Power Platform 元数据规范

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

- `String` - 字符串
- `Integer` - 整数
- `Money` - 货币
- `Picklist` - 选项集
- `MultiSelectPicklist` - 多选选项集
- `Lookup` - 查找
- `Customer` - 客户查找
- `Owner` - 所有者查找
- `DateTime` - 日期时间
- `Boolean` - 是/否
- `Memo` - 多行文本
- `Decimal` - 小数
- `Double` - 双精度浮点
- `BigInt` - 大整数

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
