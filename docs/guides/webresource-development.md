# WebResource 开发规范

本文档定义 Dataverse WebResource（JavaScript/CSS/HTML）的开发标准。

---

## 1. 目录结构

```
webresources/
├── js/               # JavaScript 脚本
│   ├── {entity}/     # 按实体名组织子目录
│   │   ├── {entity}.optionset.js   # 选项集常量（必须独立文件）
│   │   ├── {entity}.service.js     # 数据服务（必须独立文件）
│   │   ├── {entity}.form.js        # 表单处理器
│   │   └── {entity}.ribbon.js      # Ribbon 命令和规则
│   ├── shared/       # 共享工具库（如 XRM.Common）
│   └── fpsmoke/      # 其他功能模块
├── css/              # 样式表
├── html/             # HTML 资源
└── img/              # 图片资源
```

**组织原则**：
- **按实体分目录**：`js/account/`、`js/order/` 等
- **按类型分文件**：每个实体必须包含四类 JS 文件
- **命名前缀**：自定义 WebResource 使用发布商前缀（如 `new_/js/...`）

---

## 2. 命名规范

| 元素 | 规范 | 示例 |
|------|------|------|
| WebResource 名称 | `{prefix}/js/{entity}/{entity}.{type}.js` | `new_/js/account/account.optionset.js` |
| 选项集常量文件 | `{entity}.optionset.js` | `account.optionset.js` |
| 数据服务文件 | `{entity}.service.js` | `account.service.js` |
| 表单处理器文件 | `{entity}.form.js` | `account.form.js` |
| Ribbon 文件 | `{entity}.ribbon.js` | `account.ribbon.js` |
| 命名空间对象 | PascalCase | `AccountHandler`、`AccountService` |
| 常量 | UPPER_SNAKE_CASE | `STATUS.ACTIVE`、`ACCOUNT_TYPE.BUSINESS` |
| 私有变量 | 下划线前缀 `_varName` | `_saveConfirmed`、`accountData` |
| 函数名 | camelCase | `handleFormLoad`、`validateForm` |
| CSS 类名 | kebab-case | `status-badge`、`account-form-field` |

---

## 3. 选项集定义规范（必须）

每个实体的所有选项集（**字段级选项集**和**全局选项集**）必须单独定义在一个 `{entity}.optionset.js` 文件中。

### 3.1 文件结构

```javascript
/**
 * 账户选项集常量定义
 * Power Platform - 账户实体字段选项集
 *
 * 包含：字段级选项集、全局选项集
 */

(function (window, undefined) {
    'use strict';

    // ==================== 字段级选项集 ====================

    /**
     * 账户状态（new_status 字段）
     * 类型：字段级选项集
     */
    var ACCOUNT_STATUS = {
        ACTIVE: 100000000,
        FROZEN: 100000001,
        CLOSED: 100000002
    };

    /**
     * 账户类型（new_accounttype 字段）
     * 类型：字段级选项集
     */
    var ACCOUNT_TYPE = {
        INDIVIDUAL: 100000000,
        BUSINESS: 100000001,
        GOVERNMENT: 100000002
    };

    // ==================== 全局选项集 ====================

    /**
     * 优先级（全局选项集 new_priority）
     * 类型：全局选项集
     */
    var PRIORITY = {
        LOW: 100000000,
        NORMAL: 100000001,
        HIGH: 100000002,
        URGENT: 100000003
    };

    // ==================== 导出 ====================

    window.AccountOptionset = {
        // 字段级选项集
        STATUS: ACCOUNT_STATUS,
        TYPE: ACCOUNT_TYPE,
        // 全局选项集
        PRIORITY: PRIORITY
    };

})(window);
```

### 3.2 选项集分类

| 分类 | 说明 | 示例 |
|------|------|------|
| **字段级选项集** | 绑定到特定实体的字段 | `new_status`、`new_accounttype` |
| **全局选项集** | 独立存在，可被多个字段引用 | `new_priority`、`new_prioritytype` |

### 3.3 命名规范

```javascript
// 选项集变量命名：实体无关的全局选项集使用选项集原名
var PRIORITY = { /* ... */ };

// 字段级选项集：使用字段逻辑名或业务含义
var ACCOUNT_STATUS = { /* ... */ };
var ORDER_STATUS = { /* ... */ };

// 选项值命名：使用业务含义 + 大写下划线
var STATUS = {
    ACTIVE: 100000000,     // 活跃
    INACTIVE: 100000001,    // 未激活
    SUSPENDED: 100000002    // 停用
};
```

### 3.4 使用方式

```javascript
// ✅ 正确：在 Form Handler 中引用选项集常量
(function (window, document, undefined) {
    'use strict';

    var Optionset = window.AccountOptionset;

    function onStatusChange() {
        var status = Form.getValue('new_status');

        // 使用选项集常量进行比较
        if (status === Optionset.STATUS.CLOSED) {
            disableFieldsOnClose();
        }
    }

    function setDefaultStatus() {
        Form.setValue('new_status', Optionset.STATUS.ACTIVE);
    }

})(window, document);
```

```javascript
// ❌ 错误：在代码中硬编码选项值
if (status === 100000002) {  // Magic Number!
    disableFieldsOnClose();
}
```

---

## 4. JavaScript 规范

### 4.1 模块化封装（必须）

```javascript
// ✅ 正确：使用 IIFE 封装，避免全局污染
(function (window, document, undefined) {
    'use strict';

    var MyNamespace = window.MyNamespace || {};

    function privateFunction() { /* ... */ }

    MyNamespace.publicFunction = function () { /* ... */ };

    window.MyNamespace = MyNamespace;

})(window, document);
```

```javascript
// ❌ 错误：污染全局命名空间
function handleFormLoad() { /* ... */ }
var status = 100000000;
```

### 4.2 依赖声明

在文件顶部注释中明确声明依赖：

```javascript
/**
 * 账户表单处理脚本
 * Power Platform - 账户实体表单业务逻辑
 *
 * 依赖：
 *   - new_/js/shared/XRM.Common.js（公共库）
 *   - new_/js/account/account.optionset.js（选项集常量）
 *
 * 本脚本统一通过 XRM.Common 封装调用，避免直接使用原生 Xrm API。
 *
 * 功能:
 * - 表单加载初始化
 * - 账户状态管理
 * - 表单验证
 */
```

### 4.3 使用公共库 XRM.Common

`XRM.Common` 是项目封装的 Dataverse 前端操作库，提供 `Form`、`Data`、`Nav`、`UI`、`Ctx`、`Util` 等模块。

#### 4.3.1 前置条件：窗体库加载顺序

**在 Dataverse 窗体中加载 JS 时，必须按以下顺序排列「窗体库」：**

```
1. new_/js/shared/XRM.Common.debug.js   ← 基础库（最先加载）
2. new_/js/account/account.optionset.js ← 选项集常量
3. new_/js/account/account.form.js     ← 表单处理器
```

#### 4.3.2 Form Handler 中的使用（需要初始化）

Form Handler（如 `account.form.js`）必须先调用 `init()`：

```javascript
// ✅ 正确：Form Handler 中先初始化再使用
(function (window, document, undefined) {
    'use strict';

    // ✅ 引用 XRM.Common 模块
    var Common = XRM.Common;
    var Form = Common.Form;
    var Util = Common.Util;
    var Optionset = window.AccountOptionset;

    /**
     * 表单 OnLoad 事件处理函数
     * @param {object} executionContext - 表单执行上下文
     */
    function handleFormLoad(executionContext) {
        // ✅ 必须先初始化：传入 executionContext
        Common.init(executionContext);

        // 初始化后才能使用 Form/Data/UI 等模块
        Form.onChange('new_status', onStatusChange);
        Form.setRequired('new_email', 'required');
    }

    function onStatusChange() {
        // ✅ 初始化后，可直接使用 Form. 操作
        var status = Form.getValue('new_status');

        if (status === Optionset.STATUS.CLOSED) {
            Form.setDisabled('new_balance', true);
        }
    }

})(window, document);
```

#### 4.3.3 Ribbon JS 中的使用（不需要初始化）

Ribbon 命令函数接收的 `primaryControl` 就是 formContext，**无需调用 init()**，可直接使用全局 API：

**重要原则**：选项集常量**只能在一处定义**（`{entity}.optionset.js`），**多处引用**使用。

```javascript
// ✅ 正确：Ribbon JS 通过 Service 调用数据操作
(function (window, undefined) {
    'use strict';

    // ✅ 引用选项集常量（从 account.optionset.js）
    var Optionset = window.AccountOptionset;
    // ✅ 引用数据服务（从 account.service.js）
    var Service = window.AccountService;
    // ✅ 引用导航模块
    var Nav = XRM.Common.Nav;

    /**
     * 激活账户命令
     * @param {object} primaryControl - 表单上下文
     */
    function cmdActivateAccount(primaryControl) {
        var fc = primaryControl;
        var id = fc.data.entity.getId();

        if (!id) {
            Nav.alert('请先保存记录。');
            return;
        }

        // ✅ 通过 Service 调用，不直接使用 Xrm.WebApi
        Service.activate(id).then(function () {
            fc.data.refresh();
        }).catch(function (error) {
            Nav.alert('激活失败: ' + (error.message || '未知错误'));
        });
    }

    function ruleShowActivateButton(primaryControl) {
        var fc = primaryControl;
        var status = fc.getAttribute('statuscode').getValue();
        // ✅ 使用选项集常量进行比较
        return status !== Optionset.STATUS.ACTIVE;
    }

    function ruleShowCloseButton(primaryControl) {
        var fc = primaryControl;
        var status = fc.getAttribute('statuscode').getValue();
        return status !== Optionset.STATUS.CLOSED;
    }

    // 导出
    window.AccountRibbon = {
        cmdActivate: cmdActivateAccount,
        ruleShowActivate: ruleShowActivateButton,
        ruleShowClose: ruleShowCloseButton
    };

})(window);
```

#### 4.3.4 选项集常量使用原则

**核心规范**：选项集常量**只能在一处定义**，**多处引用使用**。

```
定义处（唯一）                          引用处（多处）
─────────────────────────────────────────────────────────────
{entity}.optionset.js     →            {entity}.form.js
                              →         {entity}.ribbon.js
```

| 文件 | 职责 | 选项集使用方式 |
|------|------|--------------|
| `{entity}.optionset.js` | **定义**所有选项集常量 | ❌ 不引用外部选项集 |
| `{entity}.form.js` | 引用选项集常量 | `var Optionset = window.AccountOptionset` |
| `{entity}.ribbon.js` | 引用选项集常量 | `var Optionset = window.AccountOptionset` |

```javascript
// ❌ 错误：在 Ribbon.js 中重复定义选项集常量
(function (window, undefined) {
    'use strict';

    // ❌ 违反原则：在 ribbon.js 中定义选项集
    var STATUS = {
        ACTIVE: 100000000,
        CLOSED: 100000002
    };

    function cmdActivate(primaryControl) {
        // STATUS.ACTIVE 在此处定义...
    }

})(window);

// ✅ 正确：引用 optionset.js 中定义的常量
(function (window, undefined) {
    'use strict';

    var Optionset = window.AccountOptionset;  // 引用

    function cmdActivate(primaryControl) {
        // Optionset.STATUS.ACTIVE 在 optionset.js 中定义...
    }

})(window);
```

#### 4.3.5 API 使用对比

| 场景 | 使用 XRM.Common | 使用原生 API |
|------|-----------------|--------------|
| Form Handler | `Form.getValue('field')` | `formContext.getAttribute('field').getValue()` |
| Form Handler | `Form.setValue('field', val)` | `formContext.getAttribute('field').setValue(val)` |
| Form Handler | `Common.Data.create(...)` | `Xrm.WebApi.createRecord(...)` |
| Ribbon | `primaryControl.data.entity.getId()` | 同 |
| 导航 | `XRM.Common.Nav.alert(message)` | `Xrm.Navigation.openAlertDialog({ text: message })` |
| 导航 | `XRM.Common.Nav.confirm(msg, title)` | `Xrm.Navigation.openConfirmDialog({ text: msg, title })` |
| 导航 | `XRM.Common.Nav.openDialog(url, options)` | `Xrm.Navigation.openWebResource(url, options)` |

#### 4.3.6 常见错误

```javascript
// ❌ 错误 1：Form Handler 中未初始化就使用 Form. API
function handleFormLoad(executionContext) {
    // ❌ 没有调用 Common.init(executionContext)
    Form.setValue('new_status', 1);  // Form 未定义或功能异常
}

// ❌ 错误 2：Form Handler 中直接使用 formContext
function handleFormLoad(executionContext) {
    var fc = executionContext;  // 未保存，后续无法访问
    Form.setValue('new_status', 1);
}

// ❌ 错误 3：Ribbon JS 中调用 init()
function cmdActivateAccount(primaryControl) {
    XRM.Common.init(primaryControl);  // ❌ Ribbon 不需要 init
    // ...
}
```

#### 4.3.7 XRM.Common 可用模块

```javascript
XRM.Common.init(executionContext);  // 初始化（仅 Form Handler）

XRM.Common.Form     // 表单操作：getValue, setValue, save, onChange...
XRM.Common.Data     // 数据操作：create, update, retrieve, delete...
XRM.Common.Nav      // 导航操作：alert, confirm, openDialog, error...
XRM.Common.UI       // UI 操作：setVisible, setDisabled...
XRM.Common.Ctx      // 上下文：getContext, getUserId, getOrgLcid...
XRM.Common.Util     // 工具函数：formatDate, log, parseXml...
```

#### 4.3.8 XRM.Common.Nav 导航方法

```javascript
var Nav = XRM.Common.Nav;

// 警告对话框
Nav.alert('操作已完成');

// 确认对话框（返回 Promise<boolean>）
Nav.confirm('确定删除吗？', '确认').then(function (ok) {
    if (ok) { /* 执行删除 */ }
});

// 错误对话框
Nav.error('保存失败', { errorCode: '0x80040216' });

// 打开 WebResource 弹窗
Nav.openDialog('new_/html/export.html', {
    width: { value: 600, unit: 'px' },
    height: { value: 400, unit: 'px' },
    title: '导出数据'
});
```

### 4.4 错误处理

```javascript
var Service = window.AccountService;  // 数据服务（Ribbon/Form 中引用）
var Nav = XRM.Common.Nav;  // 导航模块
var Util = XRM.Common.Util;  // 工具函数

// ✅ 正确：使用 try-catch 包裹同步业务逻辑
function handleFormLoad(executionContext) {
    Common.init(executionContext);

    try {
        var accountData = getAccountData();
        initializeUI();
        registerEventHandlers();
        Util.log('Account form loaded successfully');
    } catch (error) {
        Nav.alert('表单加载失败: ' + error.message);
    }
}

// ✅ 正确：异步操作使用 .catch() 处理错误
function onStatusChange() {
    var fc = Form.getContext();
    var id = fc.data.entity.getId();

    // ✅ 通过 Service 调用，不直接使用 Xrm.WebApi
    Service.close(id).then(function () {
        fc.data.refresh();
    }).catch(function (error) {
        Nav.alert('更新状态失败: ' + (error.message || '未知错误'));
    });
}

// ✅ 正确：Ribbon Command 的错误处理
function cmdActivateAccount(primaryControl) {
    var fc = primaryControl || Form.getContext();
    var id = fc.data.entity.getId();

    if (!id) {
        Nav.alert('请先保存记录。');
        return;
    }

    // ✅ 通过 Service 调用，不直接使用 Xrm.WebApi
    Service.activate(id).then(function () {
        fc.data.refresh();
    }).catch(function (error) {
        Nav.alert('激活失败: ' + (error.message || '未知错误'));
    });
}

// ❌ 错误示例
function badExample() {
    accountData = getAccountData();  // 缺少声明，污染全局作用域
    Service.activate(id).then(...);  // ❌ 缺少 .catch() 处理错误
}
```

### 4.5 常量使用规范

**重要**：选项集常量（字段级、全局选项集）**必须定义在 `{entity}.optionset.js` 文件中**，Form Handler **只引用不定义**。

#### 选项集常量定义位置：`{entity}.optionset.js`

```javascript
// account.optionset.js - 选项集常量定义（必须独立文件）
(function (window, undefined) {
    'use strict';

    // 字段级选项集
    var ACCOUNT_STATUS = {
        ACTIVE: 100000000,
        FROZEN: 100000001,
        CLOSED: 100000002
    };

    var ACCOUNT_TYPE = {
        INDIVIDUAL: 100000000,
        BUSINESS: 100000001
    };

    // 全局选项集
    var PRIORITY = {
        LOW: 100000000,
        NORMAL: 100000001,
        HIGH: 100000002
    };

    window.AccountOptionset = {
        STATUS: ACCOUNT_STATUS,
        TYPE: ACCOUNT_TYPE,
        PRIORITY: PRIORITY
    };

})(window);
```

#### Form Handler 中的常量引用：`{entity}.form.js`

```javascript
// account.form.js - 表单处理器（只引用，不定义常量）
(function (window, document, undefined) {
    'use strict';

    // ✅ 正确：从 Optionset 文件引用常量
    var Optionset = window.AccountOptionset;

    function onStatusChange() {
        var status = Form.getValue('new_status');

        // 使用选项集常量进行比较，避免 Magic Number
        if (status === Optionset.STATUS.CLOSED) {
            disableFieldsOnClose();
        }
    }

    function validateAccountType() {
        var type = Form.getValue('new_accounttype');
        return type === Optionset.TYPE.BUSINESS;
    }

})(window, document);
```

#### 错误示例

```javascript
// ❌ 错误：在 Form Handler 中定义选项集常量
(function (window, undefined) {
    'use strict';

    // ❌ 违反规范：不应在 form.js 中定义选项集
    var STATUS = {
        ACTIVE: 100000000,
        CLOSED: 100000002
    };

    function onStatusChange() {
        if (status === STATUS.CLOSED) {  // 应引用 AccountOptionset
            // ...
        }
    }

})(window);
```

#### 常量定义位置总结

| 文件 | 职责 | 常量定义 |
|------|------|---------|
| `{entity}.optionset.js` | **定义**选项集常量 | ✅ 必须定义 |
| `{entity}.form.js` | 引用选项集常量 | ❌ 仅引用 |
| `{entity}.ribbon.js` | 引用选项集常量 | ❌ 仅引用 |

---

## 5. 数据服务层规范（必须）

**前置条件**：Service 层用于前端 JS（Form/Ribbon/HTML）需要与后端 Dataverse 进行数据交互的场景。如果某个 JS 不涉及数据操作，则无需定义 Service。

**职责范围**：Service 层封装所有与后端交互的操作，不仅限于 CRUD，还包括：
- 标准 Web API 操作（create、update、retrieve、delete）
- 自定义 Action（Custom Action）
- 业务流程调用（Workflow Action）
- 特定查询（FetchXML、OData）

禁止在 Form/Ribbon/HTML 中直接调用 `Xrm.WebApi` 或 `Xrm.Navigation.openForm` 等 API。

### 5.1 架构分层

```
┌─────────────────────────────────────────────────────────────┐
│                    数据服务层 (Service)                       │
│                  {entity}.service.js                        │
│  - 定义所有后端交互操作（CRUD/Custom Action/Workflow）       │
│  - 返回 Promise，支持异步操作                                │
└─────────────────────────────────────────────────────────────┘
                              ↑
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  表单处理器   │    │  Ribbon 命令  │    │  HTML 资源    │
│ {entity}.form │    │ {entity}.ribbon│    │ {entity}.html │
│               │    │               │    │               │
│ - 引用 Service│    │ - 引用 Service│    │ - 引用 Service│
│ - 调用服务方法│    │ - 调用服务方法│    │ - 调用服务方法│
└───────────────┘    └───────────────┘    └───────────────┘
```

### 5.2 Service 文件结构

```javascript
/**
 * 账户数据服务
 * Power Platform - 账户实体数据操作接口
 *
 * 依赖：
 *   - new_/js/shared/XRM.Common.js
 *   - new_/js/account/account.optionset.js
 *
 * 职责：
 *   - 定义所有与后端交互的操作（CRUD/Custom Action/Workflow）
 *   - 封装 Xrm.WebApi 调用
 *   - 返回 Promise 统一异步处理
 */

(function (window, undefined) {
    'use strict';

    var Optionset = window.AccountOptionset;

    /**
     * 账户数据服务命名空间
     */
    var AccountService = {

        /**
         * 激活账户
         * @param {string} id - 账户记录 ID
         * @returns {Promise} 更新操作的 Promise
         */
        activate: function (id) {
            return Xrm.WebApi.updateRecord('account', id, {
                statecode: 0,
                statuscode: Optionset.STATUS.ACTIVE
            });
        },

        /**
         * 关闭账户
         * @param {string} id - 账户记录 ID
         * @returns {Promise} 更新操作的 Promise
         */
        close: function (id) {
            return Xrm.WebApi.updateRecord('account', id, {
                statecode: 1,
                statuscode: Optionset.STATUS.CLOSED
            });
        },

        /**
         * 获取账户详情
         * @param {string} id - 账户记录 ID
         * @param {Array<string>} columns - 要查询的列
         * @returns {Promise} 查询结果的 Promise
         */
        getDetails: function (id, columns) {
            columns = columns || ['name', 'statuscode', 'new_accounttype'];
            return Xrm.WebApi.retrieveRecord('account', id, '?$select=' + columns.join(','));
        },

        /**
         * 创建账户
         * @param {object} data - 账户数据
         * @returns {Promise} 创建结果的 Promise
         */
        create: function (data) {
            return Xrm.WebApi.createRecord('account', data);
        },

        /**
         * 删除账户
         * @param {string} id - 账户记录 ID
         * @returns {Promise} 删除操作的 Promise
         */
        remove: function (id) {
            return Xrm.WebApi.deleteRecord('account', id);
        }
    };

    // 导出到全局
    window.AccountService = AccountService;

})(window);
```

### 5.3 引用关系总结

| 文件 | 职责 | 依赖关系 |
|------|------|---------|
| `{entity}.optionset.js` | 定义选项集常量 | 无 |
| `{entity}.service.js` | 定义数据操作 API | optionset.js |
| `{entity}.form.js` | 表单业务逻辑 | optionset.js, service.js |
| `{entity}.ribbon.js` | Ribbon 命令和规则 | optionset.js, service.js |
| `{entity}.html` | 自定义 HTML 页面 | optionset.js, service.js |

### 5.4 WebResource 加载顺序

```
1. new_/js/shared/XRM.Common.debug.js     ← 基础库
2. new_/js/account/account.optionset.js   ← 选项集常量
3. new_/js/account/account.service.js     ← 数据服务（依赖 optionset）
4. new_/js/account/account.form.js        ← 表单处理器（依赖 service）
5. new_/js/account/account.ribbon.js     ← Ribbon（依赖 service）
```

---

## 6. Ribbon JavaScript 特殊规范

### 6.1 架构原则：Command 与 Rule 隔离

Ribbon JS 文件必须将 **命令执行逻辑** 与 **规则判断逻辑** 严格分离，方便独立维护和复用。

```
{entity}.ribbon.js
├── 命令层（Command）     # 调用 Service 执行操作
├── 显示规则（DisplayRule） # 控制按钮/菜单项是否显示
└── 启用规则（EnableRule）  # 控制按钮/菜单项是否可用
```

### 6.2 文件结构规范

```javascript
/**
 * 账户 Ribbon 命令定义
 * Power Platform - 账户实体 Ribbon JS
 *
 * 依赖：
 *   - new_/js/shared/XRM.Common.js
 *   - new_/js/account/account.optionset.js
 *   - new_/js/account/account.service.js     ← 数据服务（必须）
 *
 * 文件结构：
 *   1. Constants（常量定义）      - 定义所有常量，包括 Optionset、业务常量、配置常量
 *   2. Command Functions（命令执行） - 调用 Service，导出给 Ribbon Command
 *   3. Display Rules（显示规则）    - 导出给 Ribbon DisplayRule
 *   4. Enable Rules（启用规则）     - 导出给 Ribbon EnableRule
 *   5. Helper Functions（私有方法）  - 不导出，仅内部使用
 *
 * 常量管理原则：
 *   - 所有常量必须在 IIFE 作用域最顶部集中定义
 *   - 常量必须添加注释说明其含义和用途
 *   - 禁止在函数内部硬编码常量值
 *   - 常用常量组合可定义为新常量，避免重复计算
 *
 * 私有方法管理原则：
 *   - 私有方法使用下划线前缀 _functionName
 *   - 私有方法必须集中在 "Helper Functions" 区块
 *   - 公共方法不导出时也应放在 Helper Functions 区块
 *   - Command/Rule 函数中如需复用逻辑，提取为私有方法
 */

(function (window, undefined) {
    'use strict';

    // ========================================
    // 第1部分：Constants（常量定义）
    // ========================================
    // 说明：在作用域最顶部定义所有常量，每个常量必须添加注释说明其含义

    var Optionset = window.AccountOptionset;
    // Optionset - 账户选项集常量，包含状态码、类型等枚举值
    // 来源：account.optionset.js

    var Service = window.AccountService;
    // Service - 账户数据服务封装，提供激活、关闭等业务操作
    // 来源：account.service.js（数据服务层）

    var Nav = XRM.Common.Nav;
    // Nav - 导航/对话框模块，提供 alert、confirm、openDialog 等方法
    // 来源：XRM.Common.Nav（公共库）

    var Common = XRM.Common;
    // Common - 公共库主模块，提供 Form、Nav、Util 等子模块
    // 来源：XRM.Common

    // 业务常量定义
    var ENTITY_NAME = 'account';
    // ENTITY_NAME - 当前实体的逻辑名称，用于 Web API 调用

    var EXPORT_DIALOG_WIDTH = 800;
    // EXPORT_DIALOG_WIDTH - 导出对话框宽度（像素）

    var EXPORT_DIALOG_HEIGHT = 600;
    // EXPORT_DIALOG_HEIGHT - 导出对话框高度（像素）

    // 常用常量组合（避免重复计算）
    var FORM_STATE_READONLY = 'readonly';
    // FORM_STATE_READONLY - 表单只读状态标识

    var DIALOG_WIDTH_UNIT = 'px';
    // DIALOG_WIDTH_UNIT - 对话框宽度单位

    // ========================================
    // 第2部分：Command Functions（命令执行）
    // ========================================
    // 职责：调用 Service 执行数据操作，不直接使用 Xrm.WebApi
    // 特点：有副作用，会改变数据或触发流程

    /**
     * 激活账户命令
     * @param {object} primaryControl - 表单上下文
     */
    function cmdActivateAccount(primaryControl) {
        var fc = primaryControl;
        var id = fc.data.entity.getId();

        if (!id) {
            Nav.alert('请先保存记录。');
            return;
        }

        // ✅ 通过 Service 调用数据操作，不直接使用 Xrm.WebApi
        Service.activate(id).then(function () {
            Nav.alert('账户已激活。');
            fc.data.refresh();
        }).catch(function (err) {
            Nav.alert('激活失败: ' + (err.message || '未知错误'));
        });
    }

    /**
     * 关闭账户命令
     * @param {object} primaryControl - 表单上下文
     */
    function cmdCloseAccount(primaryControl) {
        var fc = primaryControl;
        var id = fc.data.entity.getId();

        Nav.confirm('确定要关闭此账户吗？', '确认关闭').then(function (ok) {
            if (!ok) return;

            // ✅ 通过 Service 调用数据操作
            return Service.close(id);
        }).then(function () {
            fc.data.refresh();
        }).catch(function (err) {
            Nav.alert('关闭失败: ' + (err.message || '未知错误'));
        });
    }

    /**
     * 导出账户数据命令
     * @param {object} primaryControl - 表单上下文
     */
    function cmdExportAccount(primaryControl) {
        var fc = primaryControl || Form.getContext();
        var id = fc.data.entity.getId();

        // 打开自定义 HTML 资源导出页面
        Nav.openDialog('new_/html/account/export.html', {
            data: { id: id },
            width: { value: EXPORT_DIALOG_WIDTH, unit: DIALOG_WIDTH_UNIT },
            height: { value: EXPORT_DIALOG_HEIGHT, unit: DIALOG_WIDTH_UNIT },
            title: '导出账户数据'
        });
    }

    // ========================================
    // 第3部分：Display Rules（显示规则）
    // ========================================
    // 职责：判断按钮/菜单项是否显示
    // 特点：纯函数，无副作用，返回布尔值

    /**
     * 仅在激活状态显示激活按钮（隐藏已激活的账户的激活按钮）
     */
    function ruleShowActivateButton(primaryControl) {
        var fc = primaryControl || Form.getContext();
        var status = fc.getAttribute('statuscode').getValue();
        return status !== Optionset.STATUS.ACTIVE;
    }

    /**
     * 仅在非关闭状态显示关闭按钮
     */
    function ruleShowCloseButton(primaryControl) {
        var fc = primaryControl || Form.getContext();
        var status = fc.getAttribute('statuscode').getValue();
        return status !== Optionset.STATUS.CLOSED;
    }

    /**
     * 仅对业务账户显示导出按钮
     */
    function ruleShowExportButton(primaryControl) {
        var fc = primaryControl || Form.getContext();
        var type = fc.getAttribute('new_accounttype').getValue();
        return type === Optionset.TYPE.BUSINESS;
    }

    // ========================================
    // 第4部分：Enable Rules（启用规则）
    // ========================================
    // 职责：判断按钮/菜单项是否启用
    // 特点：纯函数，无副作用，返回布尔值

    /**
     * 激活按钮：需要记录已保存
     */
    function ruleEnableActivateButton(primaryControl) {
        var fc = primaryControl || Form.getContext();
        var id = fc.data.entity.getId();
        return !!id;  // 已保存的记录才有 ID
    }

    /**
     * 关闭按钮：需要记录已保存且当前可编辑
     */
    function ruleEnableCloseButton(primaryControl) {
        var fc = primaryControl || Form.getContext();
        var id = fc.data.entity.getId();
        var isEditable = fc.ui.getFormState() !== FORM_STATE_READONLY;
        return !!id && isEditable;
    }

    // ========================================
    // 第5部分：Helper Functions（私有方法）
    // ========================================
    // 内部使用的辅助函数，不导出

    /**
     * 私有方法：验证记录是否可用于操作
     * @param {object} fc - 表单上下文
     * @returns {boolean} 验证是否通过
     */
    function _validateForAction(fc) {
        var id = fc.data.entity.getId();
        if (!id) {
            Nav.alert('请先保存记录。');
            return false;
        }
        return true;
    }

    // ========================================
    // 导出：全局注册
    // ========================================
    // Ribbon Workbench 引用时直接使用函数名

    window.AccountRibbon = {
        // Command
        cmdActivate: cmdActivateAccount,
        cmdClose: cmdCloseAccount,
        cmdExport: cmdExportAccount,

        // DisplayRule
        ruleShowActivate: ruleShowActivateButton,
        ruleShowClose: ruleShowCloseButton,
        ruleShowExport: ruleShowExportButton,

        // EnableRule
        ruleEnableActivate: ruleEnableActivateButton,
        ruleEnableClose: ruleEnableCloseButton
    };

})(window);
```

### 6.3 函数命名规范

| 类型 | 命名模式 | 示例 |
|------|---------|------|
| Command | `cmd{Action}{Entity}` | `cmdActivateAccount`、`cmdCloseOpportunity` |
| DisplayRule | `ruleShow{Feature}{Entity}` | `ruleShowActivateButton`、`ruleShowExportMenu` |
| EnableRule | `ruleEnable{Action}{Target}` | `ruleEnableActivateButton`、`ruleEnableDeleteMenu` |
| 判断型 Rule | `should{Action}{Entity}` | `shouldShowSmoke`、`canEditRecord` |

### 6.4 规则隔离原则

```javascript
var Optionset = window.AccountOptionset;
var Service = window.AccountService;
var Nav = XRM.Common.Nav;

// ❌ 错误：Command 内嵌业务逻辑判断
function cmdActivateAccount(primaryControl) {
    var fc = primaryControl;
    var status = fc.getAttribute('statuscode').getValue();

    // 业务判断混入 Command，违反隔离原则
    if (status === STATUS.ACTIVE) {
        Nav.alert('已是激活状态');
        return;  // 早期返回
    }

    // ❌ 错误：直接使用 Xrm.WebApi，应调用 Service
    Xrm.WebApi.updateRecord('account', id, {
        statecode: 0,
        statuscode: STATUS.ACTIVE
    });
}

// ✅ 正确：Command 只调用 Service，Rule 负责判断
function cmdActivateAccount(primaryControl) {
    var fc = primaryControl;
    var id = fc.data.entity.getId();

    // ✅ 调用 Service 执行数据操作
    Service.activate(id).then(function () {
        fc.data.refresh();
    });
}

function ruleShowActivateButton(primaryControl) {
    var fc = primaryControl;
    var status = fc.getAttribute('statuscode').getValue();
    return status !== Optionset.STATUS.ACTIVE;  // 业务判断在 Rule 中
}
```

### 6.5 Ribbon Workbench 配置

#### 6.5.1 Ribbon JS 依赖关系

Ribbon JS 根据实际使用情况，可能依赖以下文件：

| 依赖类型 | 文件 | 说明 |
|---------|------|------|
| 公共库 | `XRM.Common.js` | 如使用 Nav、Form、Util 等基础模块 |
| 选项集 | `account.optionset.js` | 如使用枚举常量 |
| 数据服务 | `account.service.js` | 如调用后端数据操作 |

**依赖加载顺序**（在 Ribbon JS 之前加载）：

```
加载顺序：
1. new_/js/shared/XRM.Common.js      ← 公共库（基础）
2. new_/js/account/account.optionset.js  ← 选项集常量
3. new_/js/account/account.service.js   ← 数据服务
4. new_/js/account/account.ribbon.js    ← Ribbon 命令（最后加载）
```

#### 6.5.2 Web 资源注册顺序

在 Power Platform 中注册 Web 资源时，**必须按依赖顺序上传**：

1. **公共库优先**：先上传 `XRM.Common.js`，所有 JS 依赖此文件
2. **基础设施次之**：上传 `*.optionset.js`、`*.service.js`
3. **业务逻辑最后**：上传 `*.ribbon.js`、`*.form.js`

> **注意**：Ribbon Workbench 中引用 Ribbon JS 时，平台会自动按依赖顺序加载前置 JS，无需手动配置。但必须在 Ribbon JS 的文件头注释中声明依赖，便于维护。

#### 6.5.3 Ribbon Workbench 函数配置

在 Ribbon Workbench 中配置时，Library 只需填写当前 Ribbon JS 文件路径：

```
Command Properties:
  JavaScript Function: cmdActivateAccount
  Library: new_/js/account/account.ribbon.js

Display Rule:
  JavaScript: ruleShowActivateButton
  Library: new_/js/account/account.ribbon.js

Enable Rule:
  JavaScript: ruleEnableActivateButton
  Library: new_/js/account/account.ribbon.js
```

**注意事项**：
- 每个 Command/Rule 函数只需引用其所在的 Ribbon JS 文件
- 前置依赖（Service、Optionset）在 Ribbon JS 内部通过 `window.*` 引用
- Ribbon Workbench 不需要单独配置前置 JS 的依赖声明

### 6.6 参数传递机制

Ribbon 函数接收参数**按声明顺序传递**（非命名参数）：

```javascript
// ✅ 正确：Form 按钮接收 formContext
function cmdActivateAccount(primaryControl) {
    var fc = primaryControl;
    var id = fc.data.entity.getId();
}

// ✅ 正确：规则函数也接收 primaryControl
function ruleShowActivateButton(primaryControl) {
    var fc = primaryControl;
    return fc.getAttribute("statuscode").getValue() === STATUS.ACTIVE;
}
```

**重要**：
- **自定义按钮的显隐规则默认 fail-closed**：JS 加载失败则按钮隐藏
- **OOB 按钮的显隐规则默认 fail-open**：JS 加载失败则按钮保持原状

---

## 6. 表单事件处理

### 6.1 OnLoad 事件

```javascript
var Common = XRM.Common;
var Util = XRM.Common.Util;

function handleFormLoad(executionContext) {
    Common.init(executionContext);

    try {
        var accountData = getAccountData();
        initializeUI();
        registerEventHandlers();
        Util.log('Account form loaded successfully');
    } catch (error) {
        Common.Nav.alert('表单加载失败: ' + error.message);
    }
}
```

### 6.2 OnSave 事件（异步确认模式）

```javascript
var Common = XRM.Common;
var Form = Common.Form;
var Util = XRM.Common.Util;
var Nav = Common.Nav;

// OnSave 异步确认标记：确认通过后手动触发的保存会被放行，避免循环
var _saveConfirmed = false;

function handleFormSave(executionContext) {
    var eventArgs = executionContext.getEventArgs();

    try {
        // 同步校验失败 -> 阻止保存
        if (!validateForm()) {
            eventArgs.preventDefault();
            return;
        }

        // 已确认的本次手动保存 -> 放行（并复位标记）
        if (_saveConfirmed) {
            _saveConfirmed = false;
            return;
        }

        // 阻断本次保存，转异步确认
        eventArgs.preventDefault();
        var saveMode = eventArgs.getSaveMode ? eventArgs.getSaveMode() : 1;

        checkBusinessRules().then(function (ok) {
            if (ok) {
                _saveConfirmed = true;
                Form.save(saveActionFromMode(saveMode));
            }
        }).catch(function (err) {
            Util.log('保存确认异常: ' + err.message, 'error');
        });
    } catch (error) {
        Nav.alert('保存验证失败: ' + error.message);
        eventArgs.preventDefault();
    }
}

/**
 * 将 OnSave 的 getSaveMode() 数值映射为 Form.save 接受的动作字符串
 */
function saveActionFromMode(mode) {
    if (mode === 2) return 'saveandclose';
    if (mode === 59) return 'saveandnew';
    return 'save';
}
```

### 6.3 OnChange 事件

```javascript
function registerEventHandlers() {
    Form.onChange('new_status', onStatusChange);
    Form.onChange('new_accounttype', onAccountTypeChange);
    Form.onChange('new_balance', onBalanceChange);
}

function onStatusChange() {
    var status = Form.getValue('new_status');
    updateStatusBadge();
    if (status === STATUS.CLOSED) {
        disableFieldsOnClose();
    }
}
```

---

## 7. CSS 规范

### 7.1 命名规范

使用 BEM 命名法或语义化命名：

```css
/* ✅ BEM 命名法 */
.status-badge { /* ... */ }
.status-badge__active { /* ... */ }
.status-badge--large { /* ... */ }

/* ✅ 语义化命名 */
.account-form-container { /* ... */ }
.account-info-section { /* ... */ }

/* ✅ 状态修饰符 */
.balance-display.negative { /* ... */ }
.input-field.error { /* ... */ }
```

### 7.2 代码风格

```css
/**
 * 账户表单样式
 * Power Platform - 账户实体表单自定义样式
 */

/* ==================== 区域分隔 ==================== */

.account-form-container {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    font-size: 14px;
    color: #333;
}

/* ==================== 嵌套层次不要超过3层 ==================== */

.section-title {
    font-weight: 600;
}

.section-title span {
    color: #666;
}

/* ✅ 而非 */
.section .title .text { /* 太深 */ }
```

### 7.3 状态样式

```css
/* 通知状态 */
.account-notification { /* ... */ }
.account-notification.success { background-color: #d4edda; }
.account-notification.error { background-color: #f8d7da; }
.account-notification.warning { background-color: #fff3cd; }
.account-notification.info { background-color: #d1ecf1; }

/* 按钮状态 */
.account-action-button { /* ... */ }
.account-action-button:hover { /* ... */ }
.account-action-button:disabled { /* ... */ }

/* 表单状态 */
.account-form-field { /* ... */ }
.account-form-field.error input { border-color: #dc3545; }
.account-form-field.success input { border-color: #28a745; }
```

---

## 8. HTML 资源

### 8.1 命名规范

```html
<!-- WebResource 命名：{prefix}/html/{module}/{filename}.html -->
<!-- 示例：new_/html/account/dashboard.html -->
```

### 8.2 代码风格

HTML 资源中引用其他 Web 资源时，必须使用**注册到环境中的 Web 资源名称**（以 `$webresource:` 前缀或相对路径格式引用）：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>账户仪表盘</title>
    <!-- 引用 Web 资源：使用 $webresource: 前缀 + 注册的资源名 -->
    <link rel="stylesheet" type="text/css" href="$webresource:new_/css/account_form.css">
</head>
<body>
    <div class="account-dashboard">
        <!-- 内容 -->
    </div>

    <!-- 引用 Web 资源：JS 也必须使用 $webresource: 前缀 -->
    <script src="$webresource:new_/js/account_handler.js"></script>
</body>
</html>
```

**引用规范**：
| 格式 | 示例 | 说明 |
|-----|------|------|
| `$webresource:` 前缀 | `$webresource:new_/js/account_handler.js` | 推荐，显式指定 Web 资源 |
| 相对路径 | `../css/account_form.css` | 可用，相对于 HTML 资源上下文 |
| ❌ 本地绝对路径 | `C:\project\css\account.css` | 禁止，无法在运行时解析 |

---

## 9. WebResource 依赖管理

### 9.1 依赖层级

WebResource 之间存在依赖关系，上传到 Dataverse 时必须正确设置依赖项：

```
共享库层（无依赖）
├── XRM.Common.js              # 基础公共库
└── GlobalOptionset.js         # 全局选项集常量

实体选项集层（依赖共享库）
└── account.optionset.js       # 账户选项集（依赖 XRM.Common）

表单处理层（依赖选项集）
└── account.form.js            # 账户表单处理器（依赖 XRM.Common + account.optionset）

Ribbon 层（依赖表单处理）
└── account.ribbon.js          # 账户 Ribbon（依赖 XRM.Common + account.form）
```

### 9.2 上传规范

上传 WebResource 到 Dataverse 时，必须设置正确的依赖项。依赖取决于代码中实际使用的对象：

| WebResource | 依赖条件 | 可能的依赖项 |
|------------|---------|------------|
| `XRM.Common.js` | 无 | 无 |
| `GlobalOptionset.js` | 仅定义常量，无外部依赖 | 无 |
| `account.optionset.js` | 仅定义常量，无外部依赖 | 无 |
| `account.form.js` | 如使用 Optionset | `account.optionset.js` |
| `account.ribbon.js` | 如使用 Service | `account.service.js` |
| `account.service.js` | 如使用 Optionset | `account.optionset.js` |

**依赖判断原则**：
- 选项集文件（`*.optionset.js`）：仅定义常量，不依赖其他 JS
- Service 文件（`*.service.js`）：如使用 Optionset 常量则依赖选项集
- Form/Ribbon 文件：根据实际使用的全局对象设置依赖

### 9.3 依赖设置检查清单

上传新 WebResource 前，确认以下事项：

1. **分析依赖**：检查代码中引用的全局对象（如 `XRM.Common`、`*Optionset`）
2. **设置依赖**：在 Dataverse WebResource 管理界面设置依赖项
3. **验证加载顺序**：确认发布后脚本按正确顺序加载

### 9.4 常见依赖错误

```javascript
// ❌ 错误：引用未加载的选项集
function onStatusChange() {
    // account.optionset.js 未加载，导致错误
    if (status === AccountOptionset.STATUS.CLOSED) {
        // ...
    }
}

// ✅ 正确：依赖项已正确设置
// account.form.js 依赖 account.optionset.js
```

---

## 10. 最佳实践汇总

1. **始终使用 `'use strict'`** 和 IIFE 封装
2. **优先使用 XRM.Common** 而非原生 Xrm 对象
3. **选项集独立文件** 每个实体创建 `{entity}.optionset.js`，禁止在其他文件中定义
4. **数据服务独立文件** 每个实体创建 `{entity}.service.js`，封装所有 Xrm.WebApi 调用
5. **Command 调用 Service** Ribbon Command 不直接使用 Xrm.WebApi，统一调用 Service
6. **Ribbon 函数** 注意参数顺序和 fail-closed/open 默认行为
7. **异步 OnSave** 使用 preventDefault + 确认 + 手动保存模式
8. **错误处理** 使用 try-catch 并显示友好提示
9. **CSS 命名** 使用语义化/BEM 命名，避免深层嵌套
10. **依赖声明** 在文件顶部注释明确依赖关系
11. **上传时设置依赖项** 确保 WebResource 依赖正确配置

---

## 11. 相关文档

- [plugin-development.md](./plugin-development.md) - C# 插件开发规范
