/**
 * XRM.Options.core.js — 自动生成的 OptionSet 常量（共享 runtime（注册表 + getLabel/getValue））
 * ⚠️ 自动生成，请勿手动编辑。
 * 数据源：Dataverse 环境「dev」
 * 依赖：必须先于本文件加载 XRM.Options.core.js
 */
(function (window, undefined) {
    'use strict';
    window.XRM = window.XRM || {};

    // 防止 core 被重复加载导致覆盖已注册的常量
    if (window.XRM.Options && window.XRM.Options.register) {
        return;
    }

    var _labels = {};  // path -> { value: label }

    var O = window.XRM.Options = {
        global: {},
        entities: {},

        // 注册一个选项集的常量与标签。scope='global' 或实体名；name 为选项集/字段名。
        register: function (scope, name, constants, labels) {
            var store = (scope === 'global')
                ? O.global
                : (O.entities[scope] = O.entities[scope] || {});
            store[name] = constants;
            _labels[(scope === 'global' ? 'global.' : scope + '.') + name] = labels || {};
        },

        getLabel: function (path, value) {
            var m = _labels[path];
            return (m && m[value] !== undefined) ? m[value] : '';
        },
        getValue: function (path, label) {
            var m = _labels[path];
            if (!m) { return null; }
            for (var v in m) { if (m[v] === label) { return Number(v); } }
            return null;
        }
    };
})(window);
