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
         */
        isValidGuid: function (guid) {
            var pattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
            return pattern.test(guid);
        },

        /**
         * 验证邮箱格式
         * @param {string} email - 邮箱地址
         */
        isValidEmail: function (email) {
            var pattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            return pattern.test(email);
        },

        /**
         * 验证电话号码
         * @param {string} phone - 电话号码
         */
        isValidPhone: function (phone) {
            var pattern = /^[\d\s\-\+\(\)]+$/;
            return pattern.test(phone) && phone.replace(/\D/g, '').length >= 7;
        },

        /**
         * URI 编码
         * @param {string} str - 要编码的字符串
         */
        encodeUri: function (str) {
            return encodeURIComponent(str);
        },

        /**
         * URI 解码
         * @param {string} str - 要解码的字符串
         */
        decodeUri: function (str) {
            return decodeURIComponent(str);
        },

        /**
         * 深度克隆对象
         * @param {object} obj - 要克隆的对象
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
         * @param {string} level - 日志级别
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
         */
        getAttribute: function (name) {
            if (!_formContext) return null;
            return _formContext.getAttribute(name);
        },

        /**
         * 获取控件对象
         * @param {string} name - 字段名称
         */
        getControl: function (name) {
            if (!_formContext) return null;
            return _formContext.getControl(name);
        },

        /**
         * 获取字段值
         * @param {string} name - 字段名称
         */
        getValue: function (name) {
            var attr = Form.getAttribute(name);
            return attr ? attr.getValue() : null;
        },

        /**
         * 设置字段值
         * @param {string} name - 字段名称
         * @param {any} value - 字段值
         */
        setValue: function (name, value) {
            var attr = Form.getAttribute(name);
            if (attr) attr.setValue(value);
            return Form; // 支持链式调用
        },

        /**
         * 批量设置字段值
         * @param {object} data - 字段值对象 { field1: value1, field2: value2 }
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
         */
        clearNotification: function (name) {
            var control = Form.getControl(name);
            if (control) control.clearNotification();
            return Form;
        },

        /**
         * 设置焦点到字段
         * @param {string} name - 字段名称
         */
        setFocus: function (name) {
            var control = Form.getControl(name);
            if (control) control.setFocus();
            return Form;
        },

        /**
         * 保存表单
         * @param {string} action - 保存操作: 'save', 'saveandclose', 'saveandnew'
         */
        save: function (action) {
            if (!_formContext || !_formContext.data.entity) return;
            _formContext.data.entity.save(action || 'saveandclose');
        },

        /**
         * 获取表单类型
         * @returns {number} 表单类型: 0=undefined, 1=create, 2=update, 3=readonly, 4=disabled, 6=quickcreate
         */
        getFormType: function () {
            if (!_formContext) return null;
            return _formContext.ui.getFormType();
        },

        /**
         * 获取实体名称
         */
        getEntityName: function () {
            if (!_formContext || !_formContext.data.entity) return null;
            return _formContext.data.entity.getEntityName();
        },

        /**
         * 获取记录 ID
         */
        getId: function () {
            if (!_formContext || !_formContext.data.entity) return null;
            return _formContext.data.entity.getId();
        },

        /**
         * 获取主属性值
         */
        getPrimaryAttributeValue: function () {
            if (!_formContext || !_formContext.data.entity) return null;
            return _formContext.data.entity.getPrimaryAttributeValue();
        },

        /**
         * 检查表单是否有修改
         */
        getIsDirty: function () {
            if (!_formContext || !_formContext.data.entity) return false;
            return _formContext.data.entity.getIsDirty();
        },

        /**
         * 验证表单
         */
        isValid: function () {
            if (!_formContext || !_formContext.data) return true;
            return _formContext.data.isValid();
        },

        /**
         * 刷新表单
         * @param {boolean} save - 是否先保存
         */
        refresh: function (save) {
            if (!_formContext || !_formContext.data) return;
            _formContext.data.refresh(save === true);
        },

        /**
         * 获取所有属性
         */
        getAttributes: function () {
            if (!_formContext || !_formContext.data.entity) return [];
            return _formContext.data.entity.attributes.get();
        },

        /**
         * 获取所有控件
         */
        getControls: function () {
            if (!_formContext || !_formContext.ui) return [];
            return _formContext.ui.controls.get();
        },

        /**
         * 获取数据 XML
         */
        getDataXml: function () {
            if (!_formContext || !_formContext.data.entity) return '';
            return _formContext.data.entity.getDataXml();
        },

        /**
         * 注册 OnLoad 事件
         * @param {function} handler - 事件处理函数
         */
        onLoad: function (handler) {
            if (!_formContext || !_formContext.data) return;
            _formContext.data.addOnLoad(handler);
        },

        /**
         * 注册 OnSave 事件
         * @param {function} handler - 事件处理函数
         */
        onSave: function (handler) {
            if (!_formContext || !_formContext.data.entity) return;
            _formContext.data.entity.addOnSave(handler);
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
         * @returns {Promise}
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
         * @returns {Promise}
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
         * @returns {Promise}
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
         * @returns {Promise}
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
         * @returns {Promise}
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
         * @returns {Promise}
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
         * @returns {Promise}
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
         * @returns {Promise}
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
         * @returns {Promise}
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
         * @returns {Promise}
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
         * @returns {Promise}
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
         * @returns {Promise}
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
         * @returns {Promise}
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
         * @returns {Promise<boolean>}
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
         */
        error: function (message, details) {
            Xrm.Navigation.openErrorDialog({ message: message, details: details });
        },

        /**
         * 打开对话框
         * @param {string} name - 页面名称 (webresource 或 custom)
         * @param {object} options - 对话框选项
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
         */
        showInfo: function (message, id) {
            UI.showNotification(message, 'INFO', id);
        },

        /**
         * 显示警告通知
         * @param {string} message - 消息内容
         * @param {string} id - 唯一 ID (可选)
         */
        showWarning: function (message, id) {
            UI.showNotification(message, 'WARNING', id);
        },

        /**
         * 显示错误通知
         * @param {string} message - 消息内容
         * @param {string} id - 唯一 ID (可选)
         */
        showError: function (message, id) {
            UI.showNotification(message, 'ERROR', id);
        },

        /**
         * 清除表单通知
         * @param {string} id - 通知 ID (不传则清除所有)
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
         */
        showProgress: function (message) {
            Xrm.Utility.showProgressIndicator(message || 'Loading...');
        },

        /**
         * 关闭进度指示器
         */
        closeProgress: function () {
            Xrm.Utility.closeProgressIndicator();
        },

        /**
         * 打开查找对话框
         * @param {object} options - 查找选项
         */
        lookupObjects: function (options) {
            return Xrm.Utility.lookupObjects(options);
        },

        /**
         * 刷新父网格
         * @param {string} entityId - 记录 ID (可选)
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
         */
        getUserId: function () {
            return Ctx.getGlobalContext().userSettings.userId;
        },

        /**
         * 获取用户名
         */
        getUserName: function () {
            return Ctx.getGlobalContext().userSettings.userName;
        },

        /**
         * 获取用户语言代码 (LCID)
         */
        getUserLcid: function () {
            return Ctx.getGlobalContext().userSettings.languageId;
        },

        /**
         * 获取用户语言代码 (如 zh-CN)
         */
        getUserLangCode: function () {
            var lcid = Ctx.getUserLcid();
            return _lcidMap[lcid] || 'en-US';
        },

        /**
         * 获取用户角色
         */
        getUserRoles: function () {
            return Ctx.getGlobalContext().userSettings.roles;
        },

        /**
         * 获取用户角色 GUID 列表
         */
        getUserRoleIds: function () {
            var roles = Ctx.getUserRoles();
            return roles ? roles.map(function (r) { return r.id; }) : [];
        },

        /**
         * 检查用户是否有指定角色
         * @param {string} roleName - 角色名称
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
         */
        getSecurityRolePrivileges: function () {
            return Ctx.getGlobalContext().userSettings.securityRolePrivileges;
        },

        /**
         * 获取用户默认仪表板 ID
         */
        getDefaultDashboardId: function () {
            return Ctx.getGlobalContext().userSettings.defaultDashboardId;
        },

        /**
         * 检查是否启用了高对比度
         */
        isHighContrastEnabled: function () {
            return Ctx.getGlobalContext().userSettings.isHighContrastEnabled;
        },

        /**
         * 检查是否为 RTL 语言
         */
        isRTL: function () {
            return Ctx.getGlobalContext().userSettings.isRTL;
        },

        /**
         * 获取用户日期格式信息
         */
        getDateFormattingInfo: function () {
            return Ctx.getGlobalContext().userSettings.dateFormattingInfo;
        },

        /**
         * 获取用户事务货币
         */
        getTransactionCurrency: function () {
            return Ctx.getGlobalContext().userSettings.transactionCurrency;
        },

        // ==================== 组织信息 ====================

        /**
         * 获取组织唯一名称
         */
        getOrgUniqueName: function () {
            return Ctx.getGlobalContext().organizationSettings.uniqueName;
        },

        /**
         * 获取组织语言代码 (LCID)
         */
        getOrgLcid: function () {
            return Ctx.getGlobalContext().organizationSettings.languageId;
        },

        /**
         * 获取组织语言代码 (如 zh-CN)
         */
        getOrgLangCode: function () {
            var lcid = Ctx.getOrgLcid();
            return _lcidMap[lcid] || 'en-US';
        },

        /**
         * 获取服务器 URL
         */
        getServerUrl: function () {
            return Ctx.getGlobalContext().getClientUrl();
        },

        /**
         * 获取客户端 URL (别名)
         */
        getClientUrl: function () {
            return Ctx.getServerUrl();
        },

        // ==================== 客户端信息 ====================

        /**
         * 获取客户端类型
         * @returns {string} 'Web', 'Outlook', 'Mobile', 'UnifiedInterface'
         */
        getClient: function () {
            return Ctx.getGlobalContext().client.getClient();
        },

        /**
         * 获取客户端状态
         * @returns {string} 'Online', 'Offline'
         */
        getClientState: function () {
            return Ctx.getGlobalContext().client.getClientState();
        },

        /**
         * 检查是否离线
         */
        isOffline: function () {
            return Ctx.getClientState() === 'Offline';
        },

        /**
         * 获取设备形状因子
         * @returns {string} 'Phone', 'Tablet', 'Desktop'
         */
        getFormFactor: function () {
            return Ctx.getGlobalContext().client.getFormFactor();
        },

        /**
         * 是否为移动设备
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
         */
        getResourceString: function (webResourceName, key) {
            return Xrm.Utility.getResourceString(webResourceName, key);
        },

        /**
         * 设置资源字典
         * @param {object} resources - 资源对象
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
         */
        addResource: function (langCode, key, value) {
            _resources[langCode] = _resources[langCode] || {};
            _resources[langCode][key] = value;
        },

        /**
         * 语言代码转 LCID
         * @param {string} langCode - 语言代码 (如 zh-CN)
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
     */
    function getFormContext() {
        return _formContext;
    }

    /**
     * 获取全局上下文
     */
    function getGlobalContext() {
        return _globalContext;
    }

    /**
     * 检查是否已初始化
     */
    function isInitialized() {
        return _isInitialized;
    }

    /**
     * 获取版本号
     */
    function getVersion() {
        return _version;
    }

    // ==================== 链式调用选择器 ====================

    /**
     * 字段选择器 (jQuery 风格)
     * @param {string|array} fields - 字段名或字段名数组
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
         */
        enable: function () {
            return this.disable(false);
        },

        /**
         * 显示/隐藏
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
         */
        show: function () {
            return this.toggle(true);
        },

        /**
         * 隐藏
         */
        hide: function () {
            return this.toggle(false);
        },

        /**
         * 设置必填
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
         */
        optional: function () {
            return this.require('none');
        },

        /**
         * 设置焦点
         */
        focus: function () {
            if (this.fields.length > 0) {
                Form.setFocus(this.fields[0]);
            }
            return this;
        },

        /**
         * 添加通知
         */
        notify: function (message, level) {
            if (this.fields.length > 0) {
                Form.addNotification(this.fields[0], message, level || 'INFO');
            }
            return this;
        },

        /**
         * 清除通知
         */
        clearNotify: function () {
            this.fields.forEach(function (f) {
                Form.clearNotification(f);
            });
            return this;
        },

        /**
         * 获取属性对象
         */
        attr: function () {
            if (this.fields.length > 0) {
                return Form.getAttribute(this.fields[0]);
            }
            return null;
        },

        /**
         * 获取控件对象
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
