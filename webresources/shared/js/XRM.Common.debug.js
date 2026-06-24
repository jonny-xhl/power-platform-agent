/**
 * XRM.Common.js - Power Platform Dataverse 前端通用库
 * 版本: 1.0.0
 * 描述: 类似 jQuery 的 Dataverse 前端操作封装库
 * 作者: Power Platform Agent
 * 许可: MIT License
 *
 * 使用方法:
 * 1. 在表单事件中调用 XRM.Common.init(executionContext) 初始化
 * 2. 使用 XRM.Common.Form/Data/Nav/UI/Ctx/Util 模块进行操作
 *
 * 示例:
 * XRM.Common.init(executionContext);
 * XRM.Common.Form.setValue('new_field', 'value');
 * XRM.Common.Data.create('account', { name: 'Test' });
 */

(function (window, Xrm, undefined) {
    'use strict';

    // ============================================================
    // 私有变量和常量
    // ============================================================

    var _version = '1.0.0';
    var _formContext = null;
    var _globalContext = null;
    var _isInitialized = false;

    // 语言代码映射
    var _lcidMap = {
        1025: 'ar-SA',   // 阿拉伯语（沙特阿拉伯）
        1028: 'zh-TW',   // 中文（台湾）
        1031: 'de-DE',   // 德语（德国）
        1033: 'en-US',   // 英语（美国）
        1034: 'es-ES',   // 西班牙语（西班牙）
        1036: 'fr-FR',   // 法语（法国）
        1040: 'it-IT',   // 意大利语（意大利）
        1041: 'ja-JP',   // 日语（日本）
        1042: 'ko-KR',   // 朝鲜语（韩国）
        2052: 'zh-CN',   // 中文（中国）
        2070: 'pt-PT',   // 葡萄牙语（葡萄牙）
        3082: 'es-MX',   // 西班牙语（墨西哥）
        // 更多语言代码...
    };

    // 内置资源字典
    var _resources = {
        'zh-CN': {
            'common.save': '保存',
            'common.cancel': '取消',
            'common.delete': '删除',
            'common.edit': '编辑',
            'common.create': '新建',
            'common.confirm': '确认',
            'common.success': '操作成功',
            'common.error': '操作失败',
            'common.warning': '警告',
            'common.info': '信息',
            'common.loading': '加载中...',
            'common.processing': '处理中...',
            'common.noData': '暂无数据',
            'common.select': '请选择',
            'error.required': '此字段为必填项',
            'error.invalid': '输入值无效',
            'error.network': '网络请求失败',
            'error.unknown': '未知错误'
        },
        'en-US': {
            'common.save': 'Save',
            'common.cancel': 'Cancel',
            'common.delete': 'Delete',
            'common.edit': 'Edit',
            'common.create': 'Create',
            'common.confirm': 'Confirm',
            'common.success': 'Success',
            'common.error': 'Error',
            'common.warning': 'Warning',
            'common.info': 'Information',
            'common.loading': 'Loading...',
            'common.processing': 'Processing...',
            'common.noData': 'No data',
            'common.select': 'Please select',
            'error.required': 'This field is required',
            'error.invalid': 'Invalid input',
            'error.network': 'Network request failed',
            'error.unknown': 'Unknown error'
        }
    };

    // ============================================================
    // 工具函数模块 (Util)
    // ============================================================

    var Util = {
        /**
         * 格式化日期
         * @param {Date} date - 日期对象
         * @param {string} format - 格式字符串 (默认: 'yyyy-MM-dd')
         * @returns {string} 格式化后的日期字符串
         *
         * @example
         * // 返回 '2024-03-15'
         * XRM.Common.Util.formatDate(new Date(2024, 2, 15));
         * // 返回 '2024-03-15 14:30:00'
         * XRM.Common.Util.formatDate(new Date(2024, 2, 15, 14, 30), 'yyyy-MM-dd HH:mm:ss');
         * // 返回 '14:30'
         * XRM.Common.Util.formatDate(new Date(), 'HH:mm');
         */
        formatDate: function (date, format) {
            if (!date) return '';
            if (typeof date === 'string') date = new Date(date);

            format = format || 'yyyy-MM-dd';
            var year = date.getFullYear();
            var month = String(date.getMonth() + 1).padStart(2, '0');
            var day = String(date.getDate()).padStart(2, '0');
            var hours = String(date.getHours()).padStart(2, '0');
            var minutes = String(date.getMinutes()).padStart(2, '0');
            var seconds = String(date.getSeconds()).padStart(2, '0');

            return format
                .replace('yyyy', year)
                .replace('MM', month)
                .replace('dd', day)
                .replace('HH', hours)
                .replace('mm', minutes)
                .replace('ss', seconds);
        },

        /**
         * 格式化数字
         * @param {number} num - 数字
         * @param {number} decimals - 小数位数
         * @returns {string} 格式化后的数字字符串
         *
         * @example
         * // 返回 '3.14'
         * XRM.Common.Util.formatNumber(3.14159, 2);
         * // 返回 '100.00'
         * XRM.Common.Util.formatNumber(100);
         */
        formatNumber: function (num, decimals) {
            if (num === null || num === undefined || isNaN(num)) return '';
            decimals = decimals || 2;
            return Number(num).toFixed(decimals);
        },

        /**
         * 格式化货币
         * @param {number} amount - 金额
         * @param {string} currency - 货币符号 (默认: '¥')
         * @returns {string} 格式化后的货币字符串
         *
         * @example
         * // 返回 '¥1,234.56'
         * XRM.Common.Util.formatCurrency(1234.56);
         * // 返回 '$9,999.00'
         * XRM.Common.Util.formatCurrency(9999, '$');
         */
        formatCurrency: function (amount, currency) {
            if (amount === null || amount === undefined || isNaN(amount)) return '';
            currency = currency || '¥';
            var parts = Number(amount).toFixed(2).split('.');
            parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
            return currency + parts.join('.');
        },

        /**
         * 模板格式化
         * @param {string} template - 模板字符串，使用 {key} 占位符
         * @param {object} data - 数据对象
         * @returns {string} 替换后的字符串
         *
         * @example
         * // 返回 'Hello, Alice! You are 30 years old.'
         * XRM.Common.Util.format('Hello, {name}! You are {age} years old.', { name: 'Alice', age: 30 });
         */
        format: function (template, data) {
            if (!template) return '';
            if (!data) return template;
            return template.replace(/\{(\w+)\}/g, function (match, key) {
                return data[key] !== undefined ? data[key] : match;
            });
        },

        /**
         * 检查值是否为空
         * @param {any} value - 要检查的值
         * @returns {boolean} 为空返回 true
         *
         * @example
         * XRM.Common.Util.isEmpty('');        // true
         * XRM.Common.Util.isEmpty(null);      // true
         * XRM.Common.Util.isEmpty([]);        // true
         * XRM.Common.Util.isEmpty('text');    // false
         */
        isEmpty: function (value) {
            if (value === null || value === undefined) return true;
            if (typeof value === 'string') return value.trim() === '';
            if (Array.isArray(value)) return value.length === 0;
            if (typeof value === 'object') return Object.keys(value).length === 0;
            return false;
        },

        /**
         * 生成 GUID
         * @returns {string} 新的 GUID 字符串
         *
         * @example
         * // 返回类似 '5f8b3c2e-1a4d-4e2b-9c3f-7a8d2e1b0c4a'
         * var id = XRM.Common.Util.generateGuid();
         */
        generateGuid: function () {
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
                var r = Math.random() * 16 | 0;
                var v = c === 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
        },

        /**
         * 验证 GUID 格式
         * @param {string} guid - GUID 字符串
         * @returns {boolean} 格式正确返回 true
         *
         * @example
         * XRM.Common.Util.isValidGuid('5f8b3c2e-1a4d-4e2b-9c3f-7a8d2e1b0c4a'); // true
         * XRM.Common.Util.isValidGuid('abc');                                   // false
         */
        isValidGuid: function (guid) {
            var pattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
            return pattern.test(guid);
        },

        /**
         * 验证邮箱格式
         * @param {string} email - 邮箱地址
         * @returns {boolean} 格式正确返回 true
         *
         * @example
         * XRM.Common.Util.isValidEmail('user@example.com'); // true
         * XRM.Common.Util.isValidEmail('invalid-email');    // false
         */
        isValidEmail: function (email) {
            var pattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            return pattern.test(email);
        },

        /**
         * 验证电话号码
         * @param {string} phone - 电话号码
         * @returns {boolean} 格式正确返回 true
         *
         * @example
         * XRM.Common.Util.isValidPhone('+86 138-0013-8000'); // true
         * XRM.Common.Util.isValidPhone('123');               // false
         */
        isValidPhone: function (phone) {
            var pattern = /^[\d\s\-\+\(\)]+$/;
            return pattern.test(phone) && phone.replace(/\D/g, '').length >= 7;
        },

        /**
         * URI 编码
         * @param {string} str - 要编码的字符串
         * @returns {string} 编码后的字符串
         *
         * @example
         * // 返回 'a%20b%26c'
         * XRM.Common.Util.encodeUri('a b&c');
         */
        encodeUri: function (str) {
            return encodeURIComponent(str);
        },

        /**
         * URI 解码
         * @param {string} str - 要解码的字符串
         * @returns {string} 解码后的字符串
         *
         * @example
         * // 返回 'a b&c'
         * XRM.Common.Util.decodeUri('a%20b%26c');
         */
        decodeUri: function (str) {
            return decodeURIComponent(str);
        },

        /**
         * 深度克隆对象
         * @param {object} obj - 要克隆的对象
         * @returns {object} 克隆后的新对象（与原对象无引用关系）
         *
         * @example
         * var original = { name: 'A', nested: { value: 1 } };
         * var copy = XRM.Common.Util.deepClone(original);
         * copy.nested.value = 2;  // 不影响 original.nested.value
         */
        deepClone: function (obj) {
            if (obj === null || typeof obj !== 'object') return obj;
            if (obj instanceof Date) return new Date(obj.getTime());
            if (obj instanceof Array) return obj.map(function (item) { return Util.deepClone(item); });
            var cloned = {};
            for (var key in obj) {
                if (obj.hasOwnProperty(key)) {
                    cloned[key] = Util.deepClone(obj[key]);
                }
            }
            return cloned;
        },

        /**
         * 延迟执行
         * @param {number} ms - 延迟毫秒数
         * @returns {Promise} 在指定毫秒后 resolve 的 Promise
         *
         * @example
         * // 等待 500ms 后继续执行
         * XRM.Common.Util.sleep(500).then(function () {
         *     console.log('done');
         * });
         */
        sleep: function (ms) {
            return new Promise(function (resolve) {
                setTimeout(resolve, ms);
            });
        },

        /**
         * 防抖函数
         * @param {function} fn - 要防抖的函数
         * @param {number} delay - 延迟毫秒数
         * @returns {function} 防抖后的函数（连续调用只执行最后一次）
         *
         * @example
         * // 字段 onChange 频繁触发时，停止输入 300ms 后才执行
         * var debouncedSave = XRM.Common.Util.debounce(saveRecord, 300);
         * formContext.getAttribute('name').addOnChange(debouncedSave);
         */
        debounce: function (fn, delay) {
            var timer = null;
            return function () {
                var args = arguments;
                var context = this;
                clearTimeout(timer);
                timer = setTimeout(function () {
                    fn.apply(context, args);
                }, delay);
            };
        },

        /**
         * 节流函数
         * @param {function} fn - 要节流的函数
         * @param {number} delay - 延迟毫秒数
         * @returns {function} 节流后的函数（指定时间窗口内最多执行一次）
         *
         * @example
         * // 滚动事件每 200ms 最多触发一次
         * var throttledHandler = XRM.Common.Util.throttle(onScroll, 200);
         */
        throttle: function (fn, delay) {
            var lastCall = 0;
            return function () {
                var now = Date.now();
                var args = arguments;
                var context = this;
                if (now - lastCall >= delay) {
                    lastCall = now;
                    fn.apply(context, args);
                }
            };
        },

        /**
         * 重试函数
         * @param {function} fn - 要重试的函数（返回 Promise）
         * @param {number} times - 重试次数
         * @param {number} delay - 重试延迟
         * @returns {Promise} 最终的 Promise 结果
         *
         * @example
         * // 失败时最多重试 3 次，每次间隔 1000ms
         * XRM.Common.Util.retry(function () {
         *     return XRM.Common.Data.retrieve('account', id);
         * }, 3, 1000).then(function (res) { /* ... *\/ });
         */
        retry: function (fn, times, delay) {
            times = times || 3;
            delay = delay || 1000;

            function attempt(remaining) {
                return fn().catch(function (error) {
                    if (remaining <= 1) throw error;
                    return Util.sleep(delay).then(function () {
                        return attempt(remaining - 1);
                    });
                });
            }

            return attempt(times);
        },

        /**
         * 对象转 FetchXML
         * @param {object} obj - 查询对象
         * @returns {string} FetchXML 字符串
         *
         * @example
         * var xml = XRM.Common.Util.objectToFetchXml({
         *     entity: 'account',
         *     columns: ['name', 'emailaddress1'],
         *     filter: {
         *         type: 'and',
         *         conditions: [{ attribute: 'statecode', operator: 'eq', value: '0' }]
         *     }
         * });
         * XRM.Common.Data.fetchXml(xml).then(function (res) { /* ... *\/ });
         */
        objectToFetchXml: function (obj) {
            if (!obj || !obj.entity) return '';

            var xml = '<fetch version="1.0" mapping="logical" output-format="xml-platform">';
            xml += '<entity name="' + obj.entity + '">';

            // 添加列
            if (obj.columns) {
                obj.columns.forEach(function (col) {
                    xml += '<attribute name="' + col + '" />';
                });
            }

            // 添加排序
            if (obj.order) {
                obj.order.forEach(function (o) {
                    xml += '<order attribute="' + o.attribute + '" ';
                    xml += 'descending="' + (o.descending ? 'true' : 'false') + '" />';
                });
            }

            // 添加过滤
            if (obj.filter) {
                xml += '<filter type="' + (obj.filter.type || 'and') + '">';
                if (obj.filter.conditions) {
                    obj.filter.conditions.forEach(function (c) {
                        xml += '<condition attribute="' + c.attribute + '" ';
                        xml += 'operator="' + c.operator + '" ';
                        if (c.value !== undefined) xml += 'value="' + c.value + '" ';
                        xml += '/>';
                    });
                }
                xml += '</filter>';
            }

            xml += '</entity></fetch>';
            return xml;
        },

        /**
         * 记录日志
         * @param {string} message - 日志消息
         * @param {string} level - 日志级别 ('info' | 'warn' | 'error')，默认 'info'
         *
         * @example
         * XRM.Common.Util.log('保存成功');              // [INFO]
         * XRM.Common.Util.log('字段缺失', 'warn');      // [WARN]
         * XRM.Common.Util.log('请求失败', 'error');     // [ERROR]
         */
        log: function (message, level) {
            level = level || 'info';
            var timestamp = Util.formatDate(new Date(), 'yyyy-MM-dd HH:mm:ss');
            var logMessage = '[' + timestamp + '] [' + level.toUpperCase() + '] ' + message;

            switch (level) {
                case 'error':
                    console.error(logMessage);
                    break;
                case 'warn':
                    console.warn(logMessage);
                    break;
                case 'info':
                default:
                    console.log(logMessage);
                    break;
            }
        }
    };

    // ============================================================
    // Form 模块 - 表单操作
    // ============================================================

    var Form = {
        /**
         * 获取属性对象
         * @param {string} name - 字段名称
         * @returns {object|null} Xrm 属性对象
         *
         * @example
         * var attr = XRM.Common.Form.getAttribute('new_amount');
         * if (attr) { var val = attr.getValue(); }
         */
        getAttribute: function (name) {
            if (!_formContext) return null;
            return _formContext.getAttribute(name);
        },

        /**
         * 获取控件对象
         * @param {string} name - 字段名称
         * @returns {object|null} Xrm 控件对象
         *
         * @example
         * var ctrl = XRM.Common.Form.getControl('new_amount');
         * if (ctrl) { ctrl.setDisabled(true); }
         */
        getControl: function (name) {
            if (!_formContext) return null;
            return _formContext.getControl(name);
        },

        /**
         * 获取字段值
         * @param {string} name - 字段名称
         * @returns {any} 字段值，字段不存在返回 null
         *
         * @example
         * var name = XRM.Common.Form.getValue('name');          // 文本
         * var isActive = XRM.Common.Form.getValue('statecode'); // 选项集
         */
        getValue: function (name) {
            var attr = Form.getAttribute(name);
            return attr ? attr.getValue() : null;
        },

        /**
         * 设置字段值
         * @param {string} name - 字段名称
         * @param {any} value - 字段值
         * @returns {Form} Form 对象，支持链式调用
         *
         * @example
         * // 普通调用
         * XRM.Common.Form.setValue('new_amount', 100);
         * // 链式调用
         * XRM.Common.Form.setValue('new_amount', 100).setValue('new_status', 1);
         */
        setValue: function (name, value) {
            var attr = Form.getAttribute(name);
            if (attr) attr.setValue(value);
            return Form; // 支持链式调用
        },

        /**
         * 批量设置字段值
         * @param {object} data - 字段值对象 { field1: value1, field2: value2 }
         * @returns {Form} Form 对象，支持链式调用
         *
         * @example
         * XRM.Common.Form.setValues({
         *     new_amount: 100,
         *     new_status: 1,
         *     description: '批量更新'
         * });
         */
        setValues: function (data) {
            if (!data || typeof data !== 'object') return Form;
            for (var name in data) {
                if (data.hasOwnProperty(name)) {
                    Form.setValue(name, data[name]);
                }
            }
            return Form;
        },

        /**
         * 设置必填级别
         * @param {string} name - 字段名称
         * @param {string} level - 必填级别: 'none', 'required', 'recommended'
         * @returns {Form} Form 对象，支持链式调用
         *
         * @example
         * XRM.Common.Form.setRequired('new_email', 'required');    // 必填
         * XRM.Common.Form.setRequired('new_email', 'recommended'); // 推荐
         * XRM.Common.Form.setRequired('new_email', 'none');        // 清除
         */
        setRequired: function (name, level) {
            var attr = Form.getAttribute(name);
            if (attr) attr.setRequiredLevel(level || 'none');
            return Form;
        },

        /**
         * 批量设置必填级别
         * @param {array|string} names - 字段名称数组
         * @param {string} level - 必填级别
         * @returns {Form} Form 对象，支持链式调用
         *
         * @example
         * XRM.Common.Form.setRequiredLevel(['new_name', 'new_email'], 'required');
         */
        setRequiredLevel: function (names, level) {
            if (typeof names === 'string') names = [names];
            names.forEach(function (name) {
                Form.setRequired(name, level);
            });
            return Form;
        },

        /**
         * 启用/禁用字段
         * @param {string} name - 字段名称
         * @param {boolean} disabled - 是否禁用
         * @returns {Form} Form 对象，支持链式调用
         *
         * @example
         * XRM.Common.Form.setDisabled('new_amount', true);   // 禁用
         * XRM.Common.Form.setDisabled('new_amount', false);  // 启用
         */
        setDisabled: function (name, disabled) {
            var control = Form.getControl(name);
            if (control) control.setDisabled(disabled);
            return Form;
        },

        /**
         * 批量启用/禁用字段
         * @param {array|string} names - 字段名称数组
         * @param {boolean} disabled - 是否禁用
         * @returns {Form} Form 对象，支持链式调用
         *
         * @example
         * XRM.Common.Form.setDisabledLevel(['new_name', 'new_amount'], true);
         */
        setDisabledLevel: function (names, disabled) {
            if (typeof names === 'string') names = [names];
            names.forEach(function (name) {
                Form.setDisabled(name, disabled);
            });
            return Form;
        },

        /**
         * 显示/隐藏字段
         * @param {string} name - 字段名称
         * @param {boolean} visible - 是否可见
         * @returns {Form} Form 对象，支持链式调用
         *
         * @example
         * XRM.Common.Form.setVisible('new_secret', false); // 隐藏
         * XRM.Common.Form.setVisible('new_secret', true);  // 显示
         */
        setVisible: function (name, visible) {
            var control = Form.getControl(name);
            if (control) control.setVisible(visible);
            return Form;
        },

        /**
         * 批量显示/隐藏字段
         * @param {array|string} names - 字段名称数组
         * @param {boolean} visible - 是否可见
         * @returns {Form} Form 对象，支持链式调用
         *
         * @example
         * XRM.Common.Form.setVisibleLevel(['new_a', 'new_b'], false);
         */
        setVisibleLevel: function (names, visible) {
            if (typeof names === 'string') names = [names];
            names.forEach(function (name) {
                Form.setVisible(name, visible);
            });
            return Form;
        },

        /**
         * 设置字段标签
         * @param {string} name - 字段名称
         * @param {string} label - 标签文本
         * @returns {Form} Form 对象，支持链式调用
         *
         * @example
         * XRM.Common.Form.setLabel('new_amount', '总金额');
         */
        setLabel: function (name, label) {
            var control = Form.getControl(name);
            if (control) control.setLabel(label);
            return Form;
        },

        /**
         * 添加字段通知
         * @param {string} name - 字段名称
         * @param {string} message - 通知消息
         * @param {string} level - 通知级别: 'INFO', 'WARNING', 'ERROR'
         * @returns {Form} Form 对象，支持链式调用
         *
         * @example
         * XRM.Common.Form.addNotification('new_email', '邮箱格式不正确', 'ERROR');
         */
        addNotification: function (name, message, level) {
            var control = Form.getControl(name);
            if (control) {
                control.addNotification({
                    message: message,
                    level: level || 'INFO',
                    uniqueId: name + '_notification'
                });
            }
            return Form;
        },

        /**
         * 清除字段通知
         * @param {string} name - 字段名称
         * @returns {Form} Form 对象，支持链式调用
         *
         * @example
         * XRM.Common.Form.clearNotification('new_email');
         */
        clearNotification: function (name) {
            var control = Form.getControl(name);
            if (control) control.clearNotification();
            return Form;
        },

        /**
         * 设置焦点到字段
         * @param {string} name - 字段名称
         * @returns {Form} Form 对象，支持链式调用
         *
         * @example
         * XRM.Common.Form.setFocus('new_name');
         */
        setFocus: function (name) {
            var control = Form.getControl(name);
            if (control) control.setFocus();
            return Form;
        },

        /**
         * 保存表单
         * @param {string} action - 保存操作: 'save', 'saveandclose', 'saveandnew'
         *
         * @example
         * XRM.Common.Form.save('saveandclose'); // 保存并关闭
         * XRM.Common.Form.save('saveandnew');   // 保存并新建
         */
        save: function (action) {
            if (!_formContext || !_formContext.data.entity) return;
            _formContext.data.entity.save(action || 'saveandclose');
        },

        /**
         * 获取表单类型
         * @returns {number} 表单类型: 0=undefined, 1=create, 2=update, 3=readonly, 4=disabled, 6=quickcreate
         *
         * @example
         * if (XRM.Common.Form.getFormType() === 1) {
         *     // 新建记录时的逻辑
         * }
         */
        getFormType: function () {
            if (!_formContext) return null;
            return _formContext.ui.getFormType();
        },

        /**
         * 获取实体名称
         * @returns {string|null} 实体逻辑名称（如 'account'）
         *
         * @example
         * var entity = XRM.Common.Form.getEntityName(); // 'account'
         */
        getEntityName: function () {
            if (!_formContext || !_formContext.data.entity) return null;
            return _formContext.data.entity.getEntityName();
        },

        /**
         * 获取记录 ID
         * @returns {string|null} 当前记录 GUID（带花括号）
         *
         * @example
         * var id = XRM.Common.Form.getId(); // '{xxxxxxxx-xxxx-...}'
         */
        getId: function () {
            if (!_formContext || !_formContext.data.entity) return null;
            return _formContext.data.entity.getId();
        },

        /**
         * 获取主属性值
         * @returns {string|null} 主属性（通常为名称）值
         *
         * @example
         * var primary = XRM.Common.Form.getPrimaryAttributeValue(); // 'Contoso Ltd.'
         */
        getPrimaryAttributeValue: function () {
            if (!_formContext || !_formContext.data.entity) return null;
            return _formContext.data.entity.getPrimaryAttributeValue();
        },

        /**
         * 检查表单是否有修改
         * @returns {boolean} 有未保存修改返回 true
         *
         * @example
         * if (XRM.Common.Form.getIsDirty()) {
         *     XRM.Common.Form.save();
         * }
         */
        getIsDirty: function () {
            if (!_formContext || !_formContext.data.entity) return false;
            return _formContext.data.entity.getIsDirty();
        },

        /**
         * 验证表单
         * @returns {boolean} 表单数据全部有效返回 true
         *
         * @example
         * if (XRM.Common.Form.isValid()) {
         *     XRM.Common.Form.save('saveandclose');
         * }
         */
        isValid: function () {
            if (!_formContext || !_formContext.data) return true;
            return _formContext.data.isValid();
        },

        /**
         * 刷新表单
         * @param {boolean} save - 是否先保存
         *
         * @example
         * XRM.Common.Form.refresh(false); // 不保存直接刷新
         * XRM.Common.Form.refresh(true);  // 先保存再刷新
         */
        refresh: function (save) {
            if (!_formContext || !_formContext.data) return;
            _formContext.data.refresh(save === true);
        },

        /**
         * 获取所有属性
         * @returns {array} 属性对象数组
         *
         * @example
         * var attrs = XRM.Common.Form.getAttributes();
         * attrs.forEach(function (attr) { /* ... *\/ });
         */
        getAttributes: function () {
            if (!_formContext || !_formContext.data.entity) return [];
            return _formContext.data.entity.attributes.get();
        },

        /**
         * 获取所有控件
         * @returns {array} 控件对象数组
         *
         * @example
         * var ctrls = XRM.Common.Form.getControls();
         */
        getControls: function () {
            if (!_formContext || !_formContext.ui) return [];
            return _formContext.ui.controls.get();
        },

        /**
         * 获取数据 XML
         * @returns {string} 当前记录的 XML 字符串
         *
         * @example
         * var xml = XRM.Common.Form.getDataXml();
         */
        getDataXml: function () {
            if (!_formContext || !_formContext.data.entity) return '';
            return _formContext.data.entity.getDataXml();
        },

        /**
         * 注册 OnLoad 事件
         * @param {function} handler - 事件处理函数
         *
         * @example
         * XRM.Common.Form.onLoad(function (executionContext) {
         *     // 表单数据加载后执行
         * });
         */
        onLoad: function (handler) {
            if (!_formContext || !_formContext.data) return;
            _formContext.data.addOnLoad(handler);
        },

        /**
         * 注册 OnSave 事件
         * @param {function} handler - 事件处理函数
         *
         * @example
         * XRM.Common.Form.onSave(function (executionContext) {
         *     // 保存前校验
         *     var eventArgs = executionContext.getEventArgs();
         * });
         */
        onSave: function (handler) {
            if (!_formContext || !_formContext.data.entity) return;
            _formContext.data.entity.addOnSave(handler);
        },

        /**
         * 注册字段 OnChange 事件
         * @param {string} name - 字段名称
         * @param {function} handler - 事件处理函数（可接收 executionContext）
         * @returns {Form} Form 对象，支持链式调用
         *
         * @example
         * XRM.Common.Form.onChange('new_status', function () {
         *     if (XRM.Common.Form.getValue('new_status') === 1) { /* ... *\/ }
         * });
         */
        onChange: function (name, handler) {
            var attr = Form.getAttribute(name);
            if (attr) attr.addOnChange(handler);
            return Form;
        }
    };

    // ============================================================
    // Data 模块 - 数据操作 (Web API)
    // ============================================================

    var Data = {
        /**
         * 创建记录
         * @param {string} entity - 实体逻辑名称
         * @param {object} data - 记录数据
         * @returns {Promise} resolve({ success, id, data }) / reject({ success, error })
         *
         * @example
         * XRM.Common.Data.create('account', { name: 'Contoso', emailaddress1: 'a@b.com' })
         *     .then(function (res) {
         *         console.log('新建 ID:', res.id);
         *     })
         *     .catch(function (err) { console.error(err.error); });
         */
        create: function (entity, data) {
            return new Promise(function (resolve, reject) {
                Xrm.WebApi.createRecord(entity, data).then(
                    function (result) {
                        resolve({ success: true, id: result.id, data: result });
                    },
                    function (error) {
                        reject({ success: false, error: error });
                    }
                );
            });
        },

        /**
         * 检索记录
         * @param {string} entity - 实体逻辑名称
         * @param {string} id - 记录 ID
         * @param {array|string} columns - 要检索的列
         * @returns {Promise} resolve({ success, data }) / reject({ success, error })
         *
         * @example
         * XRM.Common.Data.retrieve('account', '{guid}', ['name', 'emailaddress1'])
         *     .then(function (res) { console.log(res.data.name); });
         */
        retrieve: function (entity, id, columns) {
            return new Promise(function (resolve, reject) {
                var options = columns ? '$select=' + (Array.isArray(columns) ? columns.join(',') : columns) : '';
                Xrm.WebApi.retrieveRecord(entity, id, options).then(
                    function (result) {
                        resolve({ success: true, data: result });
                    },
                    function (error) {
                        reject({ success: false, error: error });
                    }
                );
            });
        },

        /**
         * 更新记录
         * @param {string} entity - 实体逻辑名称
         * @param {string} id - 记录 ID
         * @param {object} data - 更新数据
         * @returns {Promise} resolve({ success, data }) / reject({ success, error })
         *
         * @example
         * XRM.Common.Data.update('account', '{guid}', { name: 'New Name' })
         *     .then(function (res) { console.log('已更新'); });
         */
        update: function (entity, id, data) {
            return new Promise(function (resolve, reject) {
                Xrm.WebApi.updateRecord(entity, id, data).then(
                    function (result) {
                        resolve({ success: true, data: result });
                    },
                    function (error) {
                        reject({ success: false, error: error });
                    }
                );
            });
        },

        /**
         * 删除记录
         * @param {string} entity - 实体逻辑名称
         * @param {string} id - 记录 ID
         * @returns {Promise} resolve({ success, data }) / reject({ success, error })
         *
         * @example
         * XRM.Common.Data.delete('account', '{guid}')
         *     .then(function () { console.log('已删除'); });
         */
        delete: function (entity, id) {
            return new Promise(function (resolve, reject) {
                Xrm.WebApi.deleteRecord(entity, id).then(
                    function (result) {
                        resolve({ success: true, data: result });
                    },
                    function (error) {
                        reject({ success: false, error: error });
                    }
                );
            });
        },

        /**
         * 查询多条记录
         * @param {string} entity - 实体逻辑名称
         * @param {string|array} options - OData 查询选项或 FetchXML
         * @returns {Promise} resolve({ success, data, count }) / reject({ success, error })
         *
         * @example
         * XRM.Common.Data.retrieveMultipleRecords('account', '$select=name&$top=10')
         *     .then(function (res) {
         *         console.log('记录数:', res.count, res.data);
         *     });
         */
        retrieveMultipleRecords: function (entity, options) {
            return new Promise(function (resolve, reject) {
                Xrm.WebApi.retrieveMultipleRecords(entity, options).then(
                    function (result) {
                        resolve({ success: true, data: result.entities, count: result.entities.length });
                    },
                    function (error) {
                        reject({ success: false, error: error });
                    }
                );
            });
        },

        /**
         * 简化查询
         * @param {string} entity - 实体逻辑名称
         * @param {string} filter - 过滤条件 (可选)
         * @param {array} columns - 要检索的列 (可选)
         * @param {number} top - 返回记录数 (可选)
         * @returns {Promise} resolve({ success, data, count }) / reject({ success, error })
         *
         * @example
         * XRM.Common.Data.query(
         *     'account',
         *     "statecode eq 0 and revenue gt 1000",
         *     ['name', 'revenue'],
         *     5
         * ).then(function (res) { console.log(res.data); });
         */
        query: function (entity, filter, columns, top) {
            var options = [];
            if (columns) {
                options.push('$select=' + (Array.isArray(columns) ? columns.join(',') : columns));
            }
            if (filter) {
                options.push('$filter=' + filter);
            }
            if (top) {
                options.push('$top=' + top);
            }
            return Data.retrieveMultipleRecords(entity, options.join('&'));
        },

        /**
         * FetchXML 查询
         * @param {string} fetchXml - FetchXML 字符串
         * @returns {Promise} resolve({ success, data, count }) / reject({ success, error })
         *
         * @example
         * var xml = '<fetch><entity name="account"><attribute name="name"/><filter><condition attribute="statecode" operator="eq" value="0"/></filter></entity></fetch>';
         * XRM.Common.Data.fetchXml(xml)
         *     .then(function (res) { console.log(res.data); });
         */
        fetchXml: function (fetchXml) {
            return new Promise(function (resolve, reject) {
                // 需要解析 fetchXml 获取实体名称
                var entityMatch = fetchXml.match(/entity\s+name="([^"]+)"/);
                if (!entityMatch) {
                    reject({ success: false, error: 'Invalid FetchXML' });
                    return;
                }
                var entity = entityMatch[1];
                var options = '?fetchXml=' + encodeURIComponent(fetchXml);
                Xrm.WebApi.retrieveMultipleRecords(entity, options).then(
                    function (result) {
                        resolve({ success: true, data: result.entities, count: result.entities.length });
                    },
                    function (error) {
                        reject({ success: false, error: error });
                    }
                );
            });
        },

        /**
         * 批量执行操作
         * @param {array} operations - 操作数组
         * @returns {Promise} resolve({ success, data }) / reject({ success, error })
         *
         * @example
         * var requests = [ /* Xrm.WebApi.online.execute 请求对象数组 *\/ ];
         * XRM.Common.Data.batch(requests)
         *     .then(function (res) { console.log('批量完成'); });
         */
        batch: function (operations) {
            if (!Xrm.WebApi.online.executeMultiple) {
                return Promise.reject({ success: false, error: 'executeMultiple not supported' });
            }
            return new Promise(function (resolve, reject) {
                Xrm.WebApi.online.executeMultiple(operations).then(
                    function (result) {
                        resolve({ success: true, data: result });
                    },
                    function (error) {
                        reject({ success: false, error: error });
                    }
                );
            });
        },

        /**
         * 执行 Action
         * @param {string} name - Action 名称
         * @param {object} params - Action 参数
         * @param {string} entity - 绑定实体名称 (可选，用于绑定 Action)
         * @param {string} id - 记录 ID (可选，用于绑定 Action)
         * @returns {Promise} resolve({ success, data }) / reject({ success, error })
         *
         * @example
         * // 全局 Action
         * XRM.Common.Data.action('new_calculate_score', { amount: 100 })
         *     .then(function (res) { console.log(res.data); });
         * // 绑定到记录的 Action
         * XRM.Common.Data.action('new_approve', { comment: '通过' }, 'account', '{guid}')
         *     .then(function (res) { console.log(res.data); });
         */
        action: function (name, params, entity, id) {
            return new Promise(function (resolve, reject) {
                var request = {
                    actionName: name,
                    parameters: params || {}
                };

                if (entity && id) {
                    request.entity = { id: id, entityType: entity };
                    request.getMetadata = function () {
                        return {
                            boundParameter: {
                                propertyName: 'entity',
                                parameterType: 'binding'
                            }
                        };
                    };
                }

                Xrm.WebApi.online.execute(request).then(
                    function (result) {
                        resolve({ success: true, data: result });
                    },
                    function (error) {
                        reject({ success: false, error: error });
                    }
                );
            });
        },

        /**
         * 执行 Function
         * @param {string} name - Function 名称
         * @param {object} params - Function 参数
         * @returns {Promise} resolve({ success, data }) / reject({ success, error })
         *
         * @example
         * XRM.Common.Data.function('GetCurrentUserRoles', {})
         *     .then(function (res) { console.log(res.data); });
         */
        function: function (name, params) {
            return new Promise(function (resolve, reject) {
                var request = {
                    functionName: name,
                    parameters: params || {}
                };

                Xrm.WebApi.online.execute(request).then(
                    function (result) {
                        resolve({ success: true, data: result });
                    },
                    function (error) {
                        reject({ success: false, error: error });
                    }
                );
            });
        },

        /**
         * 获取当前用户信息 (WhoAmI)
         * @returns {Promise} resolve({ success, data }) / reject({ success, error })
         *
         * @example
         * XRM.Common.Data.whoAmI()
         *     .then(function (res) { console.log(res.data.UserId); });
         */
        whoAmI: function () {
            return Data.function('WhoAmI');
        },

        /**
         * 建立关联
         * @param {string} entity - 实体名称
         * @param {string} id - 记录 ID
         * @param {string} relation - 关系名称
         * @param {string} relatedId - 关联记录 ID
         * @returns {Promise} resolve({ success, data }) / reject({ success, error })
         *
         * @example
         * XRM.Common.Data.associate('account', '{accId}', 'contact_customer_accounts', '{contactId}')
         *     .then(function () { console.log('已关联'); });
         */
        associate: function (entity, id, relation, relatedId) {
            return new Promise(function (resolve, reject) {
                var relationship = {
                    schemaName: relation,
                    relatedEntityId: relatedId
                };
                Xrm.WebApi.associateRecord(entity, id, relation, relationship).then(
                    function (result) {
                        resolve({ success: true, data: result });
                    },
                    function (error) {
                        reject({ success: false, error: error });
                    }
                );
            });
        },

        /**
         * 解除关联
         * @param {string} entity - 实体名称
         * @param {string} id - 记录 ID
         * @param {string} relation - 关系名称
         * @param {string} relatedId - 关联记录 ID
         * @returns {Promise} resolve({ success, data }) / reject({ success, error })
         *
         * @example
         * XRM.Common.Data.disassociate('account', '{accId}', 'contact_customer_accounts', '{contactId}')
         *     .then(function () { console.log('已解除关联'); });
         */
        disassociate: function (entity, id, relation, relatedId) {
            return new Promise(function (resolve, reject) {
                Xrm.WebApi.disassociateRecord(entity, id, relation, relatedId).then(
                    function (result) {
                        resolve({ success: true, data: result });
                    },
                    function (error) {
                        reject({ success: false, error: error });
                    }
                );
            });
        }
    };

    // ============================================================
    // Nav 模块 - 导航操作
    // ============================================================

    var Nav = {
        /**
         * 打开表单
         * @param {string} entity - 实体逻辑名称
         * @param {string} id - 记录 ID (可选)
         * @param {object} options - 选项 (可选)
         *
         * @example
         * // 打开现有记录
         * XRM.Common.Nav.openForm('account', '{guid}');
         * // 打开指定窗体
         * XRM.Common.Nav.openForm('account', '{guid}', { formId: '{formGuid}' });
         */
        openForm: function (entity, id, options) {
            options = options || {};
            options.entityName = entity;
            if (id) options.entityId = id;
            Xrm.Navigation.openForm(options);
        },

        /**
         * 创建新记录
         * @param {string} entity - 实体逻辑名称
         * @param {object} data - 默认值 (可选)
         * @param {object} options - 选项 (可选)
         *
         * @example
         * XRM.Common.Nav.createForm('account', { name: '默认名称' });
         */
        createForm: function (entity, data, options) {
            options = options || {};
            options.entityName = entity;
            if (data) options.createFromEntity = data;
            Xrm.Navigation.openForm(options);
        },

        /**
         * 快速创建表单
         * @param {string} entity - 实体逻辑名称
         * @param {object} data - 默认值 (可选)
         *
         * @example
         * XRM.Common.Nav.quickCreate('contact', { firstname: '张' });
         */
        quickCreate: function (entity, data) {
            var options = {
                entityName: entity,
                useQuickCreateForm: true
            };
            if (data) options.createFromEntity = data;
            Xrm.Navigation.openForm(options);
        },

        /**
         * 打开实体列表
         * @param {string} entity - 实体逻辑名称
         * @param {string} viewId - 视图 ID (可选)
         *
         * @example
         * XRM.Common.Nav.openEntityList('account');
         * // 打开指定视图
         * XRM.Common.Nav.openEntityList('account', '{viewGuid}');
         */
        openEntityList: function (entity, viewId) {
            var pageInput = {
                pageType: 'entitylist',
                entityName: entity
            };
            if (viewId) pageInput.viewId = viewId;
            Xrm.Navigation.navigateTo(pageInput);
        },

        /**
         * 打开 URL
         * @param {string} url - URL 地址
         * @param {number} width - 窗口宽度 (可选)
         * @param {number} height - 窗口高度 (可选)
         *
         * @example
         * XRM.Common.Nav.openUrl('https://example.com', 800, 600);
         */
        openUrl: function (url, width, height) {
            var options = { url: url };
            if (width) options.width = width;
            if (height) options.height = height;
            Xrm.Navigation.openUrl(options);
        },

        /**
         * 打开 Web 资源
         * @param {string} name - Web 资源名称
         * @param {object} data - 传递的数据 (可选)
         * @param {object} options - 选项 (可选)
         *
         * @example
         * XRM.Common.Nav.openWebResource('new_/html/page.html', { id: 123 });
         */
        openWebResource: function (name, data, options) {
            options = options || {};
            options.webResourceName = name;
            if (data) options.data = data;
            Xrm.Navigation.openWebResource(options);
        },

        /**
         * 警告对话框
         * @param {string} message - 消息内容
         * @param {string} title - 标题 (可选)
         * @returns {Promise}
         *
         * @example
         * XRM.Common.Nav.alert('操作已完成', '提示');
         */
        alert: function (message, title) {
            return Xrm.Navigation.openAlertDialog({
                text: message,
                title: title || ''
            });
        },

        /**
         * 确认对话框
         * @param {string} message - 消息内容
         * @param {string} title - 标题 (可选)
         * @param {string} confirmButtonLabel - 确认按钮文本 (可选)
         * @param {string} cancelButtonLabel - 取消按钮文本 (可选)
         * @returns {Promise<boolean>} 用户点击确认返回 true
         *
         * @example
         * XRM.Common.Nav.confirm('确定删除该记录吗？', '确认', '删除', '取消')
         *     .then(function (ok) {
         *         if (ok) { XRM.Common.Data.delete('account', id); }
         *     });
         */
        confirm: function (message, title, confirmButtonLabel, cancelButtonLabel) {
            var config = {
                text: message,
                title: title || '',
                confirmButtonLabel: confirmButtonLabel || 'OK',
                cancelButtonLabel: cancelButtonLabel || 'Cancel'
            };
            return Xrm.Navigation.openConfirmDialog(config).then(
                function (result) { return result.confirmed; },
                function () { return false; }
            );
        },

        /**
         * 错误对话框
         * @param {string} message - 错误消息
         * @param {object} details - 错误详情 (可选)
         *
         * @example
         * XRM.Common.Nav.error('保存失败', { errorCode: '0x80040216' });
         */
        error: function (message, details) {
            Xrm.Navigation.openErrorDialog({ message: message, details: details });
        },

        /**
         * 打开对话框
         * @param {string} name - 页面名称 (webresource 或 custom)
         * @param {object} options - 对话框选项
         *
         * @example
         * // 打开自定义页面（居中弹窗）
         * XRM.Common.Nav.openDialog('myCustomPage', {
         *     width: { value: 600, unit: 'px' },
         *     height: { value: 400, unit: 'px' },
         *     title: '弹窗标题',
         *     position: 1
         * });
         */
        openDialog: function (name, options) {
            options = options || {};
            if (name.endsWith('.html') || name.includes('/')) {
                // Web 资源
                Xrm.Navigation.openWebResource(name, options);
            } else {
                // 自定义页面
                var pageInput = { pageType: 'custom', name: name };
                if (options.entityType) pageInput.entityName = options.entityType;
                if (options.data) pageInput.data = options.data;

                var navigationOptions = {};
                if (options.width) navigationOptions.width = options.width;
                if (options.height) navigationOptions.height = options.height;
                if (options.position) navigationOptions.position = options.position;
                if (options.title) navigationOptions.title = options.title;

                Xrm.Navigation.navigateTo(pageInput, navigationOptions);
            }
        },

        /**
         * 通用导航
         * @param {object} pageInput - 页面输入参数
         * @param {object} navigationOptions - 导航选项 (可选)
         *
         * @example
         * XRM.Common.Nav.navigateTo(
         *     { pageType: 'webresource', webresourceName: 'new_/page.html' },
         *     { target: 2 }
         * );
         */
        navigateTo: function (pageInput, navigationOptions) {
            Xrm.Navigation.navigateTo(pageInput, navigationOptions || {});
        }
    };

    // ============================================================
    // UI 模块 - UI 操作
    // ============================================================

    var UI = {
        /**
         * 显示表单级通知
         * @param {string} message - 消息内容
         * @param {string} level - 通知级别: 'INFO', 'WARNING', 'ERROR'
         * @param {string} id - 唯一 ID (用于清除)
         *
         * @example
         * XRM.Common.UI.showNotification('数据加载完成', 'INFO', 'load_done');
         */
        showNotification: function (message, level, id) {
            if (!_formContext || !_formContext.ui) return;
            level = level || 'INFO';
            id = id || 'notification_' + Date.now();
            _formContext.ui.setFormNotification(message, level, id);
        },

        /**
         * 显示信息通知
         * @param {string} message - 消息内容
         * @param {string} id - 唯一 ID (可选)
         *
         * @example
         * XRM.Common.UI.showInfo('保存成功');
         */
        showInfo: function (message, id) {
            UI.showNotification(message, 'INFO', id);
        },

        /**
         * 显示警告通知
         * @param {string} message - 消息内容
         * @param {string} id - 唯一 ID (可选)
         *
         * @example
         * XRM.Common.UI.showWarning('库存不足');
         */
        showWarning: function (message, id) {
            UI.showNotification(message, 'WARNING', id);
        },

        /**
         * 显示错误通知
         * @param {string} message - 消息内容
         * @param {string} id - 唯一 ID (可选)
         *
         * @example
         * XRM.Common.UI.showError('提交失败，请重试');
         */
        showError: function (message, id) {
            UI.showNotification(message, 'ERROR', id);
        },

        /**
         * 清除表单通知
         * @param {string} id - 通知 ID (不传则清除所有)
         *
         * @example
         * XRM.Common.UI.clearNotification('load_done'); // 清除指定
         * XRM.Common.UI.clearNotification();            // 清除全部
         */
        clearNotification: function (id) {
            if (!_formContext || !_formContext.ui) return;
            if (id) {
                _formContext.ui.clearFormNotification(id);
            } else {
                // 清除所有通知需要逐个清除，这里简化处理
                var notifications = _formContext.ui.formSelector.getCurrentItem().getNotifications();
                if (notifications) {
                    notifications.forEach(function (notification) {
                        _formContext.ui.clearFormNotification(notification.id);
                    });
                }
            }
        },

        /**
         * 显示进度指示器
         * @param {string} message - 进度消息
         *
         * @example
         * XRM.Common.UI.showProgress('正在保存...');
         */
        showProgress: function (message) {
            Xrm.Utility.showProgressIndicator(message || 'Loading...');
        },

        /**
         * 关闭进度指示器
         *
         * @example
         * XRM.Common.UI.closeProgress();
         */
        closeProgress: function () {
            Xrm.Utility.closeProgressIndicator();
        },

        /**
         * 打开查找对话框
         * @param {object} options - 查找选项
         * @returns {Promise} 用户选择的记录
         *
         * @example
         * XRM.Common.UI.lookupObjects({
         *     entityTypes: ['account'],
         *     allowMultiSelect: false,
         *     defaultViewId: '{viewGuid}'
         * }).then(function (result) {
         *     if (result && result.length > 0) {
         *         console.log(result[0].name, result[0].id);
         *     }
         * });
         */
        lookupObjects: function (options) {
            return Xrm.Utility.lookupObjects(options);
        },

        /**
         * 刷新父网格
         * @param {string} entityId - 记录 ID (可选)
         *
         * @example
         * XRM.Common.UI.refreshParentGrid('{guid}');
         */
        refreshParentGrid: function (entityId) {
            Xrm.Utility.refreshParentGrid(entityId);
        }
    };

    // ============================================================
    // Ctx 模块 - 上下文信息
    // ============================================================

    var Ctx = {
        /**
         * 获取全局上下文对象
         * @returns {object} Xrm 全局上下文
         *
         * @example
         * var ctx = XRM.Common.Ctx.getGlobalContext();
         */
        getGlobalContext: function () {
            if (!_globalContext) {
                _globalContext = Xrm.Utility.getGlobalContext();
            }
            return _globalContext;
        },

        // ==================== 用户信息 ====================

        /**
         * 获取用户 ID
         * @returns {string} 当前用户 GUID
         *
         * @example
         * var userId = XRM.Common.Ctx.getUserId();
         */
        getUserId: function () {
            return Ctx.getGlobalContext().userSettings.userId;
        },

        /**
         * 获取用户名
         * @returns {string} 当前用户登录名
         *
         * @example
         * var userName = XRM.Common.Ctx.getUserName();
         */
        getUserName: function () {
            return Ctx.getGlobalContext().userSettings.userName;
        },

        /**
         * 获取用户语言代码 (LCID)
         * @returns {number} 语言 LCID（如 2052）
         *
         * @example
         * var lcid = XRM.Common.Ctx.getUserLcid(); // 2052
         */
        getUserLcid: function () {
            return Ctx.getGlobalContext().userSettings.languageId;
        },

        /**
         * 获取用户语言代码 (如 zh-CN)
         * @returns {string} 语言代码（如 'zh-CN'）
         *
         * @example
         * var lang = XRM.Common.Ctx.getUserLangCode(); // 'zh-CN'
         */
        getUserLangCode: function () {
            var lcid = Ctx.getUserLcid();
            return _lcidMap[lcid] || 'en-US';
        },

        /**
         * 获取用户角色
         * @returns {object} 角色集合
         *
         * @example
         * var roles = XRM.Common.Ctx.getUserRoles();
         * roles.forEach(function (r) { console.log(r.name, r.id); });
         */
        getUserRoles: function () {
            return Ctx.getGlobalContext().userSettings.roles;
        },

        /**
         * 获取用户角色 GUID 列表
         * @returns {array} 角色 ID 数组
         *
         * @example
         * var roleIds = XRM.Common.Ctx.getUserRoleIds();
         */
        getUserRoleIds: function () {
            var roles = Ctx.getUserRoles();
            return roles ? roles.map(function (r) { return r.id; }) : [];
        },

        /**
         * 检查用户是否有指定角色
         * @param {string} roleName - 角色名称
         * @returns {boolean} 拥有该角色返回 true
         *
         * @example
         * if (XRM.Common.Ctx.hasRole('系统管理员')) {
         *     // 管理员专属逻辑
         * }
         */
        hasRole: function (roleName) {
            var roles = Ctx.getUserRoles();
            if (!roles) return false;
            return roles.some(function (r) {
                return r.name === roleName;
            });
        },

        /**
         * 获取用户安全角色权限
         * @returns {object} 权限集合
         *
         * @example
         * var privileges = XRM.Common.Ctx.getSecurityRolePrivileges();
         */
        getSecurityRolePrivileges: function () {
            return Ctx.getGlobalContext().userSettings.securityRolePrivileges;
        },

        /**
         * 获取用户默认仪表板 ID
         * @returns {string} 默认仪表板 GUID
         *
         * @example
         * var dashboardId = XRM.Common.Ctx.getDefaultDashboardId();
         */
        getDefaultDashboardId: function () {
            return Ctx.getGlobalContext().userSettings.defaultDashboardId;
        },

        /**
         * 检查是否启用了高对比度
         * @returns {boolean}
         *
         * @example
         * if (XRM.Common.Ctx.isHighContrastEnabled()) { /* 高对比度适配 *\/ }
         */
        isHighContrastEnabled: function () {
            return Ctx.getGlobalContext().userSettings.isHighContrastEnabled;
        },

        /**
         * 检查是否为 RTL 语言
         * @returns {boolean}
         *
         * @example
         * if (XRM.Common.Ctx.isRTL()) { /* 从右到左布局适配 *\/ }
         */
        isRTL: function () {
            return Ctx.getGlobalContext().userSettings.isRTL;
        },

        /**
         * 获取用户日期格式信息
         * @returns {object} 日期格式对象
         *
         * @example
         * var fmt = XRM.Common.Ctx.getDateFormattingInfo();
         */
        getDateFormattingInfo: function () {
            return Ctx.getGlobalContext().userSettings.dateFormattingInfo;
        },

        /**
         * 获取用户事务货币
         * @returns {object} 事务货币对象
         *
         * @example
         * var currency = XRM.Common.Ctx.getTransactionCurrency();
         */
        getTransactionCurrency: function () {
            return Ctx.getGlobalContext().userSettings.transactionCurrency;
        },

        // ==================== 组织信息 ====================

        /**
         * 获取组织唯一名称
         * @returns {string} 组织唯一名称
         *
         * @example
         * var org = XRM.Common.Ctx.getOrgUniqueName(); // 'contoso'
         */
        getOrgUniqueName: function () {
            return Ctx.getGlobalContext().organizationSettings.uniqueName;
        },

        /**
         * 获取组织语言代码 (LCID)
         * @returns {number} 组织基础语言 LCID
         *
         * @example
         * var lcid = XRM.Common.Ctx.getOrgLcid(); // 2052
         */
        getOrgLcid: function () {
            return Ctx.getGlobalContext().organizationSettings.languageId;
        },

        /**
         * 获取组织语言代码 (如 zh-CN)
         * @returns {string} 语言代码（如 'zh-CN'）
         *
         * @example
         * var lang = XRM.Common.Ctx.getOrgLangCode(); // 'zh-CN'
         */
        getOrgLangCode: function () {
            var lcid = Ctx.getOrgLcid();
            return _lcidMap[lcid] || 'en-US';
        },

        /**
         * 获取服务器 URL
         * @returns {string} Dataverse 客户端 URL
         *
         * @example
         * var url = XRM.Common.Ctx.getServerUrl(); // 'https://org.crm.dynamics.com'
         */
        getServerUrl: function () {
            return Ctx.getGlobalContext().getClientUrl();
        },

        /**
         * 获取客户端 URL (别名)
         * @returns {string} Dataverse 客户端 URL
         *
         * @example
         * var url = XRM.Common.Ctx.getClientUrl();
         */
        getClientUrl: function () {
            return Ctx.getServerUrl();
        },

        // ==================== 客户端信息 ====================

        /**
         * 获取客户端类型
         * @returns {string} 'Web', 'Outlook', 'Mobile', 'UnifiedInterface'
         *
         * @example
         * var client = XRM.Common.Ctx.getClient();
         */
        getClient: function () {
            return Ctx.getGlobalContext().client.getClient();
        },

        /**
         * 获取客户端状态
         * @returns {string} 'Online', 'Offline'
         *
         * @example
         * var state = XRM.Common.Ctx.getClientState();
         */
        getClientState: function () {
            return Ctx.getGlobalContext().client.getClientState();
        },

        /**
         * 检查是否离线
         * @returns {boolean} 离线返回 true
         *
         * @example
         * if (XRM.Common.Ctx.isOffline()) { /* 离线处理 *\/ }
         */
        isOffline: function () {
            return Ctx.getClientState() === 'Offline';
        },

        /**
         * 获取设备形状因子
         * @returns {string} 'Phone', 'Tablet', 'Desktop'
         *
         * @example
         * var factor = XRM.Common.Ctx.getFormFactor();
         */
        getFormFactor: function () {
            return Ctx.getGlobalContext().client.getFormFactor();
        },

        /**
         * 是否为移动设备
         * @returns {boolean} 手机或平板返回 true
         *
         * @example
         * if (XRM.Common.Ctx.isMobile()) { /* 移动端布局 *\/ }
         */
        isMobile: function () {
            var factor = Ctx.getFormFactor();
            return factor === 1 || factor === 2; // Phone or Tablet
        },

        // ==================== 多语言支持 ====================

        /**
         * 翻译资源键
         * @param {string} key - 资源键
         * @param {number} lcid - 语言代码 (可选，默认使用用户语言)
         * @returns {string} 当前语言下的文案
         *
         * @example
         * // 返回 '保存' (zh-CN) 或 'Save' (en-US)
         * var text = XRM.Common.Ctx.translate('common.save');
         * // 指定英文
         * var text = XRM.Common.Ctx.translate('common.save', 1033); // 'Save'
         */
        translate: function (key, lcid) {
            var langCode;
            if (lcid) {
                langCode = _lcidMap[lcid] || 'en-US';
            } else {
                langCode = Ctx.getUserLangCode();
            }

            var resources = _resources[langCode] || _resources['en-US'];
            return resources[key] || key;
        },

        /**
         * 获取 Web 资源字符串
         * @param {string} webResourceName - Web 资源名称
         * @param {string} key - 资源键
         * @returns {string} 本地化字符串
         *
         * @example
         * var text = XRM.Common.Ctx.getResourceString('new_/resx/strings', 'btn_save');
         */
        getResourceString: function (webResourceName, key) {
            return Xrm.Utility.getResourceString(webResourceName, key);
        },

        /**
         * 设置资源字典
         * @param {object} resources - 资源对象
         *
         * @example
         * XRM.Common.Ctx.setResources({
         *     'zh-CN': { 'custom.hello': '你好' },
         *     'en-US': { 'custom.hello': 'Hello' }
         * });
         */
        setResources: function (resources) {
            for (var langCode in resources) {
                if (resources.hasOwnProperty(langCode)) {
                    _resources[langCode] = _resources[langCode] || {};
                    for (var key in resources[langCode]) {
                        if (resources[langCode].hasOwnProperty(key)) {
                            _resources[langCode][key] = resources[langCode][key];
                        }
                    }
                }
            }
        },

        /**
         * 添加资源
         * @param {string} langCode - 语言代码
         * @param {string} key - 资源键
         * @param {string} value - 资源值
         *
         * @example
         * XRM.Common.Ctx.addResource('zh-CN', 'custom.bye', '再见');
         */
        addResource: function (langCode, key, value) {
            _resources[langCode] = _resources[langCode] || {};
            _resources[langCode][key] = value;
        },

        /**
         * 语言代码转 LCID
         * @param {string} langCode - 语言代码 (如 zh-CN)
         * @returns {number} 对应的 LCID
         *
         * @example
         * XRM.Common.Ctx.langCodeToLcid('zh-CN'); // 2052
         */
        langCodeToLcid: function (langCode) {
            for (var lcid in _lcidMap) {
                if (_lcidMap[lcid] === langCode) {
                    return parseInt(lcid);
                }
            }
            return 1033; // 默认英语
        },

        /**
         * LCID 转语言代码
         * @param {number} lcid - LCID
         * @returns {string} 语言代码
         *
         * @example
         * XRM.Common.Ctx.lcidToLangCode(2052); // 'zh-CN'
         */
        lcidToLangCode: function (lcid) {
            return _lcidMap[lcid] || 'en-US';
        }
    };

    // ============================================================
    // 核心初始化和导出
    // ============================================================

    /**
     * 初始化库
     * @param {object} executionContext - 执行上下文对象
     *
     * @example
     * // 必须在表单 OnLoad 事件中调用一次，传入执行上下文
     * function onLoad(executionContext) {
     *     XRM.Common.init(executionContext);
     *     // 之后即可使用 Form/UI 等模块
     * }
     */
    function init(executionContext) {
        if (executionContext) {
            _formContext = executionContext.getFormContext();
        }
        _globalContext = Xrm.Utility.getGlobalContext();
        _isInitialized = true;
        Util.log('XRM.Common.js v' + _version + ' initialized', 'info');
    }

    /**
     * 获取表单上下文
     * @returns {object|null} 当前表单上下文
     *
     * @example
     * var formCtx = XRM.Common.getFormContext();
     */
    function getFormContext() {
        return _formContext;
    }

    /**
     * 获取全局上下文
     * @returns {object|null} 全局上下文
     *
     * @example
     * var globalCtx = XRM.Common.getGlobalContext();
     */
    function getGlobalContext() {
        return _globalContext;
    }

    /**
     * 检查是否已初始化
     * @returns {boolean} 已初始化返回 true
     *
     * @example
     * if (!XRM.Common.isInitialized()) { XRM.Common.init(executionContext); }
     */
    function isInitialized() {
        return _isInitialized;
    }

    /**
     * 获取版本号
     * @returns {string} 库版本号
     *
     * @example
     * var ver = XRM.Common.getVersion(); // '1.0.0'
     */
    function getVersion() {
        return _version;
    }

    // ==================== 链式调用选择器 ====================

    /**
     * 字段选择器 (jQuery 风格)
     * @param {string|array} fields - 字段名或字段名数组
     * @returns {FieldSelector} 字段选择器对象，支持链式调用
     *
     * @example
     * // 单字段
     * XRM.Common.$('new_name').val('张三').require().show();
     * // 多字段
     * XRM.Common.$(['new_a', 'new_b']).disable().hide();
     */
    function $(fields) {
        return new FieldSelector(Array.isArray(fields) ? fields : [fields]);
    }

    /**
     * 字段选择器类
     */
    function FieldSelector(fields) {
        this.fields = fields;
    }

    FieldSelector.prototype = {
        /**
         * 获取/设置值
         * @param {any} [value] - 不传为获取，传入为设置
         * @returns {any|FieldSelector} 获取时返回值，设置时返回 this
         *
         * @example
         * var v = XRM.Common.$('new_amount').val();   // 获取
         * XRM.Common.$('new_amount').val(100);         // 设置
         */
        val: function (value) {
            if (value === undefined) {
                return Form.getValue(this.fields[0]);
            }
            this.fields.forEach(function (f) {
                Form.setValue(f, value);
            });
            return this;
        },

        /**
         * 启用/禁用
         * @param {boolean} [flag=true] - 是否禁用，默认 true
         * @returns {FieldSelector} this
         *
         * @example
         * XRM.Common.$('new_amount').disable(true);  // 禁用
         * XRM.Common.$('new_amount').disable(false); // 启用
         */
        disable: function (flag) {
            if (flag === undefined) flag = true;
            this.fields.forEach(function (f) {
                Form.setDisabled(f, flag);
            });
            return this;
        },

        /**
         * 启用
         * @returns {FieldSelector} this
         *
         * @example
         * XRM.Common.$('new_amount').enable();
         */
        enable: function () {
            return this.disable(false);
        },

        /**
         * 显示/隐藏
         * @param {boolean} [visible=true] - 是否可见，默认 true
         * @returns {FieldSelector} this
         *
         * @example
         * XRM.Common.$('new_secret').toggle(false); // 隐藏
         */
        toggle: function (visible) {
            if (visible === undefined) visible = true;
            this.fields.forEach(function (f) {
                Form.setVisible(f, visible);
            });
            return this;
        },

        /**
         * 显示
         * @returns {FieldSelector} this
         *
         * @example
         * XRM.Common.$('new_secret').show();
         */
        show: function () {
            return this.toggle(true);
        },

        /**
         * 隐藏
         * @returns {FieldSelector} this
         *
         * @example
         * XRM.Common.$('new_secret').hide();
         */
        hide: function () {
            return this.toggle(false);
        },

        /**
         * 设置必填
         * @param {string} [level='required'] - 必填级别
         * @returns {FieldSelector} this
         *
         * @example
         * XRM.Common.$('new_email').require();              // 必填
         * XRM.Common.$('new_email').require('recommended'); // 推荐
         */
        require: function (level) {
            if (level === undefined) level = 'required';
            this.fields.forEach(function (f) {
                Form.setRequired(f, level);
            });
            return this;
        },

        /**
         * 设置为非必填
         * @returns {FieldSelector} this
         *
         * @example
         * XRM.Common.$('new_email').optional();
         */
        optional: function () {
            return this.require('none');
        },

        /**
         * 设置焦点
         * @returns {FieldSelector} this
         *
         * @example
         * XRM.Common.$('new_name').focus();
         */
        focus: function () {
            if (this.fields.length > 0) {
                Form.setFocus(this.fields[0]);
            }
            return this;
        },

        /**
         * 添加通知
         * @param {string} message - 通知消息
         * @param {string} [level='INFO'] - 通知级别
         * @returns {FieldSelector} this
         *
         * @example
         * XRM.Common.$('new_email').notify('邮箱格式不正确', 'ERROR');
         */
        notify: function (message, level) {
            if (this.fields.length > 0) {
                Form.addNotification(this.fields[0], message, level || 'INFO');
            }
            return this;
        },

        /**
         * 清除通知
         * @returns {FieldSelector} this
         *
         * @example
         * XRM.Common.$('new_email').clearNotify();
         */
        clearNotify: function () {
            this.fields.forEach(function (f) {
                Form.clearNotification(f);
            });
            return this;
        },

        /**
         * 获取属性对象
         * @returns {object|null} 第一个字段的属性对象
         *
         * @example
         * var attr = XRM.Common.$('new_amount').attr();
         */
        attr: function () {
            if (this.fields.length > 0) {
                return Form.getAttribute(this.fields[0]);
            }
            return null;
        },

        /**
         * 获取控件对象
         * @returns {object|null} 第一个字段的控件对象
         *
         * @example
         * var ctrl = XRM.Common.$('new_amount').ctrl();
         */
        ctrl: function () {
            if (this.fields.length > 0) {
                return Form.getControl(this.fields[0]);
            }
            return null;
        }
    };

    // ==================== 导出 ====================

    window.XRM = window.XRM || {};
    window.XRM.Common = {
        // 版本信息
        version: _version,

        // 初始化
        init: init,
        getFormContext: getFormContext,
        getGlobalContext: getGlobalContext,
        isInitialized: isInitialized,
        getVersion: getVersion,

        // 模块
        Form: Form,
        Data: Data,
        Nav: Nav,
        UI: UI,
        Ctx: Ctx,
        Util: Util,

        // 链式调用
        $: $,

        // 简写别名
        $form: Form,
        $data: Data,
        $nav: Nav,
        $ui: UI,
        $ctx: Ctx,
        $util: Util
    };

    // 兼容性：如果没有 Xrm 对象（在 HTML Web Resource 中），使用 window.top.Xrm
    if (!window.Xrm && window.top && window.top.Xrm) {
        window.Xrm = window.top.Xrm;
    }

    Util.log('XRM.Common.js v' + _version + ' loaded', 'info');

})(window, window.Xrm);
