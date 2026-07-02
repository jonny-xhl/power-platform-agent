/**
 * 报价单表单处理脚本 (new_quote)
 * Power Platform - CPQ 报价单表单业务逻辑
 *
 * 依赖：
 *   - new_/shared/js/XRM.Common.js（公共库）
 *   - new_/js/new_quote/new_quote.optionset.js（选项集常量）
 *
 * 加载顺序：XRM.Common → new_quote.optionset.js → new_quote.form.js
 *
 * 功能：
 *   - 表单加载初始化（默认状态/审批/事件注册）
 *   - 状态变更联动：提交后自动置审批=待审核；非草稿锁定关键字段
 */
(function (window, document, undefined) {
    'use strict';

    var Common = XRM.Common;
    var Form = Common.Form;
    var Util = Common.Util;
    var Nav = Common.Nav;
    var Optionset = window.QuoteOptionset;

    /** 非草稿状态下只读的字段 */
    var LOCKED_FIELDS = ['new_pricelist_id', 'new_shippingterm_id', 'new_targetcountry_id', 'new_paymentterms'];

    /**
     * 表单 OnLoad
     * @param {object} executionContext - 表单执行上下文
     */
    function handleFormLoad(executionContext) {
        Common.init(executionContext);

        try {
            var status = Form.getValue('new_status');
            if (status === null || status === undefined) {
                Form.setValue('new_status', Optionset.STATUS.DRAFT);
            }
            var approval = Form.getValue('new_approvalstatus');
            if (approval === null || approval === undefined) {
                Form.setValue('new_approvalstatus', Optionset.APPROVAL.DRAFT);
            }
            Form.onChange('new_status', onStatusChange);
            applyStatusUi();
            Util.log('Quote form loaded');
        } catch (error) {
            Nav.alert('报价单加载失败: ' + (error.message || '未知错误'));
        }
    }

    /** new_status 变更 */
    function onStatusChange() {
        try {
            var status = Form.getValue('new_status');
            // 提交后自动进入待审核
            if (status === Optionset.STATUS.SUBMITTED) {
                var approval = Form.getValue('new_approvalstatus');
                if (approval === null || approval === undefined || approval === Optionset.APPROVAL.DRAFT) {
                    Form.setValue('new_approvalstatus', Optionset.APPROVAL.PENDING);
                }
            }
            applyStatusUi();
        } catch (error) {
            Util.log('onStatusChange error: ' + error.message, 'error');
        }
    }

    /** 根据状态切换关键字段只读 */
    function applyStatusUi() {
        var status = Form.getValue('new_status');
        var readonly = status !== null && status !== undefined && status !== Optionset.STATUS.DRAFT;
        LOCKED_FIELDS.forEach(function (field) {
            try { Form.setDisabled(field, readonly); } catch (e) { /* field may be absent */ }
        });
    }

    window.QuoteForm = {
        handleFormLoad: handleFormLoad
    };

})(window, document);
