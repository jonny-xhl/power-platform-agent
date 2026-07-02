/**
 * 询价明细表单处理脚本 (new_inquirydetail)
 * Power Platform - CPQ 询价明细表单业务逻辑
 *
 * 依赖：
 *   - new_/shared/js/XRM.Common.js（公共库）
 *
 * 加载顺序：XRM.Common → new_inquirydetail.form.js
 * （本实体无选项集字段，故无 optionset.js）
 *
 * 功能：
 *   - 表单加载初始化（数量默认值、标题联动）
 */
(function (window, document, undefined) {
    'use strict';

    var Common = XRM.Common;
    var Form = Common.Form;
    var Util = Common.Util;
    var Nav = Common.Nav;

    /**
     * 表单 OnLoad
     * @param {object} executionContext - 表单执行上下文
     */
    function handleFormLoad(executionContext) {
        Common.init(executionContext);

        try {
            // 新建时数量默认 1
            var qty = Form.getValue('new_qty');
            if (qty === null || qty === undefined) {
                Form.setValue('new_qty', 1);
            }
            Form.onChange('new_qty', onQtyChange);
            Util.log('Inquiry detail form loaded');
        } catch (error) {
            Nav.alert('询价明细加载失败: ' + (error.message || '未知错误'));
        }
    }

    function onQtyChange() {
        try {
            var qty = Form.getValue('new_qty');
            if (qty !== null && qty !== undefined && qty < 0) {
                Form.setValue('new_qty', 0);
            }
        } catch (e) {
            Util.log('onQtyChange error: ' + e.message, 'error');
        }
    }

    window.InquiryDetailForm = {
        handleFormLoad: handleFormLoad
    };

})(window, document);
