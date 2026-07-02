/**
 * 询价单选项集常量 (new_inquiry)
 * Power Platform - CPQ 询价单字段选项集
 *
 * 类型：字段级选项集（local picklist）
 * 来源：环境实际值（与 metadata_py/tables/new_inquiry.py 一致）
 *
 * 依赖：无（仅定义常量）
 */
(function (window, undefined) {
    'use strict';

    /** 询价单状态（new_status 字段） */
    var INQUIRY_STATUS = {
        DRAFT: 1,        // 草稿
        SUBMITTED: 2,    // 已提交
        QUOTED: 3,       // 已报价
        CLOSED: 4,       // 已关闭
        VOID: 5          // 已作废
    };

    window.InquiryOptionset = {
        STATUS: INQUIRY_STATUS
    };

})(window);
