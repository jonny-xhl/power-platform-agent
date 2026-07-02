/**
 * 询价单表单处理脚本 (new_inquiry)
 * Power Platform - CPQ 询价单表单业务逻辑
 *
 * 依赖：
 *   - new_/shared/js/XRM.Common.js（公共库）
 *   - new_/js/new_inquiry/new_inquiry.optionset.js（选项集常量）
 *
 * 加载顺序：XRM.Common → new_inquiry.optionset.js → new_inquiry.form.js
 *
 * 功能：
 *   - 表单加载初始化（默认状态、事件注册）
 *   - 状态变更联动（已提交后关键字段只读）
 */
(function (window, document, undefined) {
    'use strict';

    var Common = XRM.Common;
    var Form = Common.Form;
    var Util = Common.Util;
    var Nav = Common.Nav;
    var Optionset = window.InquiryOptionset;

    /** 非草稿状态下只读的字段 */
    var LOCKED_FIELDS = ['new_inquirydate', 'new_targetcountry_id', 'new_channel_id', 'new_salesorg_id'];

    /**
     * 表单 OnLoad
     * @param {object} executionContext - 表单执行上下文
     */
    function handleFormLoad(executionContext) {
        Common.init(executionContext);

        try {
            // 新建时默认状态 = 草稿
            var status = Form.getValue('new_status');
            if (status === null || status === undefined) {
                Form.setValue('new_status', Optionset.STATUS.DRAFT);
            }
            Form.onChange('new_status', onStatusChange);
            applyStatusUi();
            Util.log('Inquiry form loaded');
        } catch (error) {
            Nav.alert('询价单加载失败: ' + (error.message || '未知错误'));
        }
    }

    /** new_status 变更 */
    function onStatusChange() {
        try {
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

    window.InquiryForm = {
        handleFormLoad: handleFormLoad
    };

})(window, document);
