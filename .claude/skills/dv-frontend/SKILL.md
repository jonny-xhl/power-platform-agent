---
name: dv-frontend
description: |
  Power Platform Model-Driven App 前端开发最佳实践与设计指南。

  触发关键词（中文）：表单设计、视图设计、前端开发、Web资源、业务规则、表单脚本、样式设计、界面布局、交互设计、Model-Driven App、MCC表单、Dataverse前端
  Triggers (English): form design, view design, frontend development, web resource, business rule, form script, styling, UI layout, interaction design, Model-Driven App, MCC form, Dataverse frontend

  覆盖范围：Model-Driven App 表单设计、视图设计、Web 资源开发、表单脚本、业务规则最佳实践。
  Scope: Form design, View design, Web Resource development, Form scripting, Business rules best practices for Power Platform Dataverse.
---

# Power Platform 前端开发最佳实践

本文档提供 Power Platform Model-Driven App 前端开发的完整指南，涵盖表单、视图、Web 资源和业务规则的设计与实现。

## 一、前端技术栈概览

### 表单类型（Form Types）

| 类型 | 适用场景 | 特点 |
|------|---------|------|
| **Main** | 主要数据录入界面 | 支持多Tab、多Section、完整业务逻辑、BPF |
| **QuickCreate** | 快速创建表单 | 精简字段、关联创建时弹出、不超过5-10字段 |
| **QuickView** | 快速查看面板 | 在其他表单中显示关联记录摘要 |
| **Card** | 卡片视图 | 仪表板卡片显示、1-3个字段 |
| **MainInteraction** | 交互对话框 | 独立对话框界面、对话式体验 |

### 视图类型（View Types）

| 类型 | 说明 | API 类型值 |
|------|------|-----------|
| **PublicView** | 公共视图，所有用户可见 | 0 |
| **AdvancedFind** | 高级查找视图 | 1 |
| **AssociatedView** | 关联视图，显示相关记录 | 2 |
| **QuickFindView** | 快速查找视图，搜索时使用 | 4 |
| **LookupView** | 查找对话框视图 | 64 |

### Web 资源类型（Web Resource Types）

| 类型 | 扩展名 | 说明 |
|------|--------|------|
| CSS | `.css` | 样式表，用于表单自定义样式 |
| JavaScript | `.js` | 表单脚本，处理业务逻辑 |
| HTML | `.html` | 自定义页面或仪表板组件 |
| PNG | `.png` | 图片资源 |
| SVG | `.svg` | 矢量图标 |
| ICO | `.ico` | 图标文件 |
| RESX | `.resx` | 资源文件（多语言） |

## 二、表单设计最佳实践

### 表单类型选择决策树

```
┌─────────────────────────────────────────────────────────────┐
│                    表单类型选择                              │
└─────────────────────────────────────────────────────────────┘
                              │
              需要完整业务逻辑和多个分组？
                              │
               ┌──────────────┴──────────────┐
               │ 是                          │ 否
               ▼                             ▼
          Main 表单                   需要快速录入少量字段？
                                          │
                           ┌──────────────┴──────────────┐
                           │ 是                          │ 否
                           ▼                             ▼
                    QuickCreate 表单            需要在其他表单显示摘要？
                                                       │
                                            ┌──────────┴──────────┐
                                            │ 是                 │ 否
                                            ▼                    ▼
                                    QuickView 表单      需要在仪表板显示？
                                                              │
                                                   ┌──────────┴──────────┐
                                                   │ 是                 │ 否
                                                   ▼                    ▼
                                              Card 表单            Main 表单
```

### 12列网格布局系统

Model-Driven App 使用 12 列网格系统：

```
┌─────────────────────────────────────────────────────────────────┐
│                        12 列网格                                │
├─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┤
│  1  │  2  │  3  │  4  │  5  │  6  │  7  │  8  │  9  │ 10  │ 11  │ 12  │
│8.3% │16.7%│ 25% │33.3%│41.7%│ 50% │58.3%│66.7%│75% │83.3%│91.7%│100% │
└─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘
```

**宽度推荐**：
- 单字段：`width: "1"` 或 `"2"`（适合标签+输入）
- 双字段行：两个 `width: "1"` 或一个 `width: "2"` + 一个 `width: "1"`
- 半宽：`width: "6"`（50%宽度，适合多行文本或备注）
- 全宽：`width: "12"`（100%宽度）

### Tab 设计规范

| 原则 | 规范 | 说明 |
|------|------|------|
| 数量限制 | 2-4 个建议，不超过 6 个 | 过多 Tab 影响用户体验 |
| 分组逻辑 | 按业务流程或信息类别分组 | 如：常规信息、详细信息、关联信息 |
| 命名规范 | 简洁中文，2-4 字 | 如：常规、详情、关联、审核 |
| 展开策略 | 最重要的 Tab 默认展开 | `expand_by_default: true` |
| 可见性 | 非关键 Tab 可默认隐藏 | `visible: false` |

### Section 设计规范

```
Section 结构建议：
├── 每个 Tab 2-6 个 Section
├── 相关字段放在同一 Section
├── 必填字段优先放在左上角
├── Section 内字段按使用频率排序
└── Section 名称清晰描述内容
```

**Section 布局示例**：

```yaml
tabs:
  - schema_name: "general"
    display_name: "常规信息"
    sections:
      - schema_name: "basic_info"
        display_name: "基本信息"
        rows:
          - cells:
              - attribute: "new_name"
                width: "2"        # 跨2列
          - cells:
              - attribute: "new_code"
                width: "1"
              - attribute: "new_status"
                width: "1"
```

### 字段分组策略

**优先级排序**（从高到低）：

1. **必填字段**（Required）- 优先级最高
2. **关键业务字段**（核心业务数据）
3. **查找字段**（关联数据）
4. **常用选项字段**
5. **系统字段**（创建人、修改时间等）
6. **备注/说明字段**（Memo）

### 响应式设计考虑

| 设备类型 | 屏幕宽度 | 布局调整 |
|---------|---------|---------|
| Desktop | > 1024px | 显示完整布局，支持多列 |
| Tablet | 768px - 1024px | 减少列数，使用 2 列布局 |
| Mobile | < 768px | 单列布局，Tab 折叠为菜单 |

### 性能优化建议

```
优化清单：
├── 控制字段数量：单表单建议 < 100 字段
├── 减少嵌套 Web Resource：避免深度嵌套
├── 按需加载 JavaScript：非关键逻辑延迟加载
├── 避免 onLoad 事件执行复杂查询：异步处理耗时操作
├── 使用业务规则替代简单逻辑：服务器执行更高效
└── 限制 Lookup 字段数量：过多影响加载性能
```

### 表单 YAML 示例

完整示例参考：`metadata/forms/account_main.yaml`

```yaml
$schema: "../_schema/form_schema.yaml"

form:
  schema_name: "account_main_form"
  entity: "account"
  type: "Main"
  display_name: "账户主表单"
  is_default: true

tabs:
  - schema_name: "general"
    display_name: "常规信息"
    expand_by_default: true
    sections:
      - schema_name: "basic_info"
        display_name: "基本信息"
        rows:
          - cells:
              - attribute: "accountNumber"
                width: "1"
              - attribute: "status"
                width: "1"

events:
  - schema_name: "onload"
    handlers:
      - function_name: "handleFormLoad"
        library: "new_js/account_handler.js"
        enabled: true
```

## 三、视图设计最佳实践

### FetchXML 编写规范

**标准结构**：

```xml
<fetch version="1.0" mapping="logical" distinct="false" no-lock="true">
  <entity name="account">
    <!-- 列定义 -->
    <attribute name="accountnumber" />
    <attribute name="name" />
    <attribute name="statecode" />

    <!-- 排序 -->
    <order attribute="accountnumber" descending="false" />

    <!-- 过滤器 -->
    <filter type="and">
      <condition attribute="statecode" operator="eq" value="0" />
    </filter>

    <!-- 关联实体 (Join) -->
    <link-entity name="contact" from="contactid" to="primarycontactid" alias="contact">
      <attribute name="fullname" />
    </link-entity>
  </entity>
</fetch>
```

**常用运算符**：

| 运算符 | 说明 | 示例 |
|-------|------|------|
| `eq` | 等于 | `value="0"` |
| `ne` | 不等于 | `value="1"` |
| `like` | 模糊匹配 | `value="%keyword%"` |
| `in` | 包含于列表 | `value="1,2,3"` |
| `not-in` | 不包含于列表 | `value="1,2,3"` |
| `null` | 为空 | 无 value |
| `not-null` | 不为空 | 无 value |
| `today` | 今天 | 无 value |
| `this-week` | 本周 | 无 value |
| `this-month` | 本月 | 无 value |
| `between` | 区间查询 | 两个 value |
| `last-x-hours` | 最近X小时 | `value="24"` |

### 列配置

| 配置项 | 建议 | 说明 |
|-------|------|------|
| 列数量 | 3-8 列 | 避免横向滚动 |
| 列宽 | 80-200px | 根据内容调整 |
| 总宽度 | 800-1200px | 兼顾信息密度 |
| 排序列 | 第一列或关键字段 | 提升浏览效率 |
| 格式化 | 货币、日期等 | 提升可读性 |

### 性能优化

```
索引优化：
├── 过滤字段添加索引
├── 排序字段添加索引
├── 避免 Select *：只获取需要的列
└── 分页查询：Top 100-250

查询优化：
├── 使用 no-lock="true" 避免锁等待
├── 避免 N+1 查询：使用 link-entity
├── 限制返回行数：使用 top 属性
└── 缓存常用数据：适当使用
```

### 视图 YAML 示例

完整示例参考：`metadata/views/account_active.yaml`

```yaml
$schema: "../_schema/view_schema.yaml"

view:
  schema_name: "account_active_view"
  entity: "account"
  type: "PublicView"
  display_name: "活跃账户"
  is_default: true

  fetch_xml: |
    <fetch version="1.0" mapping="logical">
      <entity name="account">
        <attribute name="accountnumber" />
        <attribute name="name" />
        <filter type="and">
          <condition attribute="statecode" operator="eq" value="0" />
        </filter>
      </entity>
    </fetch>

columns:
  - attribute: "accountNumber"
    width: 150
    sort_order: 1
```

## 四、Web 资源开发

### JavaScript 最佳实践

**IIFE 命名空间模式**（推荐）：

```javascript
(function(window, document, undefined) {
    'use strict';

    // 创建命名空间
    window.MyNamespace = window.MyNamespace || {};

    // 私有变量
    var formContext = null;
    var PRIVATE_CONST = 'value';

    // 私有函数
    function privateHelper() {
        // 内部逻辑
    }

    // 公共 API
    window.MyNamespace = {
        handleFormLoad: handleFormLoad,
        handleFormSave: handleFormSave,
        PUBLIC_CONSTANT: 'value'
    };

    // 事件处理函数
    function handleFormLoad(executionContext) {
        formContext = executionContext.getFormContext();
        // 初始化逻辑
    }

})(window, document);
```

**Xrm API 使用规范**：

```javascript
// 获取表单上下文
var formContext = executionContext.getFormContext();

// 字段操作（Attribute）
var attribute = formContext.getAttribute('new_fieldname');
attribute.getValue();           // 获取值
attribute.setValue(value);      // 设置值
attribute.setRequiredLevel('required');  // 设置必填级别
attribute.fireOnChange();       // 触发 onChange 事件

// 控件操作（Control）
var control = formContext.getControl('new_fieldname');
control.setVisible(false);      // 隐藏
control.setDisabled(true);      // 禁用
control.addOnChange(handler);   // 注册变更事件
control.setLabel('新标签');     // 设置标签
control.addNotification(message, 'ERROR'); // 显示通知

// 表单操作
formContext.ui.formSelector.getCurrentItem(); // 当前表单
formContext.data.entity.getId();              // 记录 ID
formContext.data.entity.save('saveandclose'); // 保存
```

**错误处理模式**：

```javascript
function handleFormLoad(executionContext) {
    try {
        formContext = executionContext.getFormContext();
        initializeUI();
        registerEventHandlers();
        console.log('Form loaded successfully');
    } catch (error) {
        console.error('Form load error:', error);
        Xrm.Utility.alertDialog('表单加载失败: ' + error.message);
    }
}
```

完整示例参考：`webresources/js/account_handler.js`

### CSS 样式规范

**避免样式冲突**：

```css
/* 推荐：使用命名空间前缀 */
.my-entity-form .field-container { }
.my-entity-form .status-badge { }

/* 避免：通用选择器 */
/* 不推荐 */
div { }
span { }

/* 推荐 */
.my-specific-class { }
```

**响应式设计**：

```css
/* Desktop - 默认 */
.multi-column {
    display: flex;
    gap: 1rem;
}

/* Tablet */
@media (max-width: 1023px) {
    .multi-column {
        flex-direction: column;
    }
}

/* Mobile */
@media (max-width: 768px) {
    .compact-mode {
        font-size: 14px;
        padding: 0.5rem;
    }
}
```

完整示例参考：`webresources/css/account_form.css`

### HTML Web Resource 设计

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>自定义组件</title>
    <link rel="stylesheet" href="new_css/component.css">
</head>
<body>
    <div id="component-container"></div>
    <script src="new_shared/underscore.js"></script>
    <script src="new_js/component.js"></script>
</body>
</html>
```

### 依赖管理

```yaml
# metadata/webresources/my_entity.yaml
resources:
  - schema_name: "entity_handler"
    type: "js"
    dependencies:
      - "new_shared/underscore.js"
      - "new_shared/jquery.min.js"
      - "new_shared/moment.js"
```

**加载顺序**：依赖 → 主脚本

## 五、表单脚本开发

### 事件处理模式

**onLoad 事件**（表单加载时）：

```javascript
function handleFormLoad(executionContext) {
    var formContext = executionContext.getFormContext();

    // 初始化 UI
    initializeUI();

    // 注册事件处理
    registerEventHandlers();

    // 加载数据
    loadData();
}
```

**onSave 事件**（保存前）：

```javascript
function handleFormSave(executionContext) {
    var eventArgs = executionContext.getEventArgs();

    // 验证表单
    if (!validateForm()) {
        eventArgs.preventDefault();  // 阻止保存
        return;
    }

    // 检查业务规则
    if (!checkBusinessRules()) {
        eventArgs.preventDefault();
        return;
    }
}
```

**onChange 事件**（字段变更时）：

```javascript
function onStatusChange(executionContext) {
    var attribute = executionContext.getEventSource();
    var value = attribute.getValue();

    // 响应值变化
    updateUIByStatus(value);
}
```

### 常见业务逻辑实现

**级联更新字段**：

```javascript
function onAccountTypeChange(executionContext) {
    var accountType = executionContext.getEventSource().getValue();
    var regionField = formContext.getAttribute('new_region');

    // 根据账户类型设置默认区域
    if (accountType === 100000001) {  // VIP
        regionField.setValue('NORTH');
    } else {
        regionField.setValue(null);
    }
}
```

**动态设置必填**：

```javascript
function onProductCategoryChange(executionContext) {
    var category = executionContext.getEventSource().getValue();
    var subCategoryField = formContext.getAttribute('new_subcategory');

    // 电子商品需要选择子类别
    subCategoryField.setRequiredLevel(
        category === 'ELECTRONICS' ? 'required' : 'none'
    );
}
```

**显示/隐藏字段**：

```javascript
function toggleFieldsByStatus(status) {
    var approvedDateControl = formContext.getControl('new_approveddate');
    var reasonControl = formContext.getControl('new_reason');

    if (status === STATUS.APPROVED) {
        approvedDateControl.setVisible(true);
        reasonControl.setVisible(false);
    } else {
        approvedDateControl.setVisible(false);
        reasonControl.setVisible(true);
    }
}
```

## 六、业务规则 vs JavaScript

### 对比矩阵

| 特性 | 业务规则 | JavaScript |
|------|---------|-----------|
| 学习曲线 | 低（无代码） | 高（需编程） |
| 执行位置 | 服务器 + 客户端 | 仅客户端 |
| 离线支持 | ✅ 是 | ❌ 否 |
| 复杂逻辑 | ❌ 不支持 | ✅ 完全支持 |
| 性能 | 较好 | 可能较差 |
| 调试 | 困难 | 相对容易 |
| 维护 | 界面配置 | 代码维护 |

### 何时使用业务规则

```
适用场景：
├── 简单的显示/隐藏逻辑
├── 简单的必填规则
├── 字段值之间的简单依赖
├── 需要离线工作
└── 非技术人员维护需求
```

### 何时使用 JavaScript

```
适用场景：
├── 复杂条件判断
├── 调用 Web API
├── 操作外部系统
├── 自定义验证逻辑
├── 动态加载选项
└── 需要精确控制执行顺序
```

## 七、命名与规范

### Schema Name 命名规则

基于 `config/naming_rules.yaml` 的转换规则：

```yaml
naming:
  prefix: "new_"
  style: "lowercase"
  separator: "_"
  auto_prefix: true

# 转换示例
AccountNumber → new_account_number
CustomerEmail → new_customer_email
```

**验证规则**：
- 最大长度：100 字符
- 最小长度：2 字符
- 禁止字符：空格、连字符(-)、点(.)
- 必须以字母开头
- 允许模式：`^[a-zA-Z][a-zA-Z0-9_]*$`

### 显示名称规范

```
原则：
├── 使用简洁的中文
├── 避免技术术语
├── 保持用户视角
└── 与业务术语一致

示例：
├── new_payment_date → 认款日期
├── new_customer_id → 客户编号
└── new_approval_status → 审批状态
```

### 代码组织规范

```
webresources/
├── shared/              # 共享库
│   ├── underscore.js
│   ├── jquery.min.js
│   └── moment.js
├── js/                  # 表单脚本
│   ├── handlers/        # 事件处理器
│   └── utils/           # 工具函数
├── css/                 # 样式文件
│   └── entities/        # 实体特定样式
└── html/                # HTML 组件
    └── dashboards/      # 仪表板组件
```

### 命名工具

```bash
# 命名转换
naming_convert --input "客户编号" --type schema_name
# 输出: new_customer_number

# 命名验证
naming_validate --name "new_customer_number" --type schema_name
# 输出: ✅ Valid
```

## 八、工作流程

### 表单开发流程

```
1. 需求分析
   └── 确定字段、Tab、Section 布局

2. YAML 定义
   └── 创建 metadata/forms/{entity}_main.yaml

3. 本地验证
   └── metadata_validate(form_yaml, schema="form_schema")

4. 预览现有表单
   └── metadata_get_form(entity="{entity}", form_type=2)

5. 应用变更（mode选择）
   └── 首次创建: metadata_create_form(form_yaml, mode="auto")
   └── 更新现有: metadata_create_form(form_yaml, mode="update", target_form_id="...")

6. 测试验证
   └── 在 Dataverse 中测试表单
```

### 视图开发流程

```
1. 定义需求
   └── 确定列、排序、过滤条件

2. YAML 定义
   └── 创建 metadata/views/{entity}_{view}.yaml

3. FetchXML 编写
   └── 定义查询和过滤

4. 列配置
   └── 设置列宽和格式

5. 应用同步
   └── metadata_apply_yaml(metadata_type="view", name="{entity}_{view}")
```

### Web 资源工作流

```
1. 源文件开发
   └── webresources/js/*.js, webresources/css/*.css

2. YAML 配置
   └── metadata/webresources/{entity}.yaml

3. 依赖声明
   └── 指定依赖的 Web Resources

4. 命名验证
   └── naming_validate --name "new_js/script.js" --type webresource

5. 部署
   └── metadata_apply_yaml(metadata_type="webresource", name="{entity}")
```

## 九、常见问题与解决方案

### 表单性能问题

**症状**：
- 表单加载缓慢（> 3秒）
- 字段响应延迟
- 浏览器卡顿

**解决方案**：
```javascript
// 1. 减少 onLoad 事件中的代码
function handleFormLoad(executionContext) {
    // 延迟非关键操作
    setTimeout(function() {
        loadNonCriticalData();
    }, 500);
}

// 2. 按需加载
function loadSectionData(sectionName) {
    // 只有展开时才加载数据
}

// 3. 使用防抖
var debounceTimer;
function onFieldChange(executionContext) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function() {
        processChange();
    }, 300);
}
```

### 视图查询慢

**症状**：
- 视图加载超过 5 秒
- 分页卡顿

**解决方案**：
```xml
<!-- 1. 添加 no-lock 属性 -->
<fetch version="1.0" mapping="logical" no-lock="true">

<!-- 2. 限制返回列数 -->
<fetch version="1.0" mapping="logical" top="100">

<!-- 3. 只获取需要的列 -->
<attribute name="accountnumber" />
<!-- 避免获取所有列 -->
```

### Web 资源加载失败

**症状**：
- JavaScript 报错
- 样式未生效

**解决方案**：
```yaml
# 1. 检查依赖顺序
resources:
  - schema_name: "underscore"    # 依赖在前
    type: "js"
  - schema_name: "main_script"  # 主脚本在后
    type: "js"
    dependencies:
      - "new_shared/underscore.js"

# 2. 验证命名
# 使用 naming_validate 检查 Schema Name

# 3. 检查浏览器控制台
# F12 → Console 查看具体错误
```

### 样式冲突

**症状**：
- 自定义样式被覆盖
- 影响其他表单

**解决方案**：
```css
/* 1. 使用命名空间前缀 */
.my-entity-form .specific-field { }

/* 2. 增加选择器特异性 */
.my-entity-form .section .field { }

/* 3. 避免使用 !important */
/* 不推荐 */
.field { color: red !important; }

/* 推荐 */
.my-entity-form .field { color: red; }
```

## 参考文件

| 类型 | 路径 | 说明 |
|------|------|------|
| 表单 Schema | `metadata/_schema/form_schema.yaml` | 表单元数据验证 |
| 视图 Schema | `metadata/_schema/view_schema.yaml` | 视图元数据验证 |
| WebResource Schema | `metadata/_schema/webresource_schema.yaml` | Web Resource 元数据验证 |
| 表单示例 | `metadata/forms/account_main.yaml` | 表单 YAML 示例 |
| 视图示例 | `metadata/views/account_active.yaml` | 视图 YAML 示例 |
| WebResource 示例 | `metadata/webresources/account_form.yaml` | Web Resource 配置示例 |
| JS 示例 | `webresources/js/account_handler.js` | 表单脚本示例 |
| CSS 示例 | `webresources/css/account_form.css` | 样式文件示例 |
| 命名规则 | `config/naming_rules.yaml` | 命名转换配置 |

## 相关 MCP 工具

| 工具 | 说明 |
|------|------|
| `metadata_create_form` | 创建/更新表单 |
| `metadata_get_form` | 获取表单详情 |
| `metadata_create_view` | 创建/更新视图 |
| `metadata_list_views` | 列出视图 |
| `metadata_apply_yaml` | 应用元数据变更 |
| `metadata_validate` | 验证元数据定义 |
| `naming_convert` | 命名转换 |
| `naming_validate` | 命名验证 |
