/**
 * 报价明细表单处理脚本 (new_quotedetail)
 * Power Platform - CPQ 报价明细表单业务逻辑
 *
 * 依赖：
 *   - new_/shared/js/XRM.Common.js（公共库）
 *
 * 加载顺序：XRM.Common → new_quotedetail.form.js
 * （本实体无选项集字段，故无 optionset.js）
 *
 * 功能：
 *   - 表单加载初始化（数量默认值、事件注册）
 *   - 行小计自动计算：linetotal = qty × unitprice × (1 − discount/100)
 *     触发：new_qty / new_unitprice / new_discount 变更
 */
(function (window, document, undefined) {
    'use strict';

    var Common = XRM.Common;
    var Form = Common.Form;
    var Util = Common.Util;
    var Nav = Common.Nav;

    /** 参与行小计计算的字段 */
    var CALC_FIELDS = ['new_qty', 'new_unitprice', 'new_discount'];

    /**
     * 表单 OnLoad
     * @param {object} executionContext - 表单执行上下文
     */
    function handleFormLoad(executionContext) {
        Common.init(executionContext);

        try {
            var qty = Form.getValue('new_qty');
            if (qty === null || qty === undefined) {
                Form.setValue('new_qty', 1);
            }
            CALC_FIELDS.forEach(function (field) {
                Form.onChange(field, recalcLineTotal);
            });
            recalcLineTotal();
            Util.log('Quote detail form loaded');
        } catch (error) {
            Nav.alert('报价明细加载失败: ' + (error.message || '未知错误'));
        }
    }

    /** 重新计算 new_linetotal = qty × unitprice × (1 − discount/100) */
    function recalcLineTotal() {
        try {
            var qty = num(Form.getValue('new_qty')) || 0;
            var unitprice = num(Form.getValue('new_unitprice')) || 0;
            var discount = num(Form.getValue('new_discount')) || 0;  // 百分比 0-100
            if (discount < 0) { discount = 0; }
            if (discount > 100) { discount = 100; }
            var linetotal = Math.round(qty * unitprice * (1 - discount / 100) * 100) / 100;
            Form.setValue('new_linetotal', linetotal);
        } catch (e) {
            Util.log('recalcLineTotal error: ' + e.message, 'error');
        }
    }

    /** 安全转数字（Money/Decimal getValue 可能返回 number/null） */
    function num(v) {
        if (v === null || v === undefined || v === '') { return 0; }
        var n = Number(v);
        return isNaN(n) ? 0 : n;
    }

    window.QuoteDetailForm = {
        handleFormLoad: handleFormLoad
    };

})(window, document);
