/**
 * 报价单选项集常量 (new_quote)
 * Power Platform - CPQ 报价单字段选项集
 *
 * 类型：字段级选项集（local picklist）
 * 来源：环境实际值（与 metadata_py/tables/new_quote.py 一致）
 *
 * 依赖：无（仅定义常量）
 */
(function (window, undefined) {
    'use strict';

    /** 报价单状态（new_status 字段） */
    var QUOTE_STATUS = {
        DRAFT: 1,        // 草稿
        SUBMITTED: 2,    // 已提交
        APPROVED: 3,     // 已批准
        ACCEPTED: 4,     // 已接受
        REJECTED: 5,     // 已拒绝
        EXPIRED: 6,      // 已过期
        CONVERTED: 7     // 已转单
    };

    /** 审批状态（new_approvalstatus 字段） */
    var APPROVAL_STATUS = {
        DRAFT: 1,        // 草稿
        PENDING: 2,      // 待审核
        APPROVED: 3,     // 已审核
        REJECTED: 4      // 已拒绝
    };

    /** 付款条款（new_paymentterms 字段） */
    var PAYMENT_TERMS = {
        ADVANCE_100: 1,  // 预付100%
        COD: 2,          // 货到付款
        NET_30: 3,       // 月结30天
        NET_60: 4,       // 月结60天
        LC: 5            // 信用证
    };

    window.QuoteOptionset = {
        STATUS: QUOTE_STATUS,
        APPROVAL: APPROVAL_STATUS,
        PAYMENT: PAYMENT_TERMS
    };

})(window);
