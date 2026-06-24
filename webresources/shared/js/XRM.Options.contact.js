/**
 * XRM.Options.contact.js — 自动生成的 OptionSet 常量（实体 contact 的字段级 Picklist）
 * ⚠️ 自动生成，请勿手动编辑。
 * 数据源：Dataverse 环境「dev」
 * 依赖：必须先于本文件加载 XRM.Options.core.js
 */

(function (window, undefined) {
    'use strict';
    if (!window.XRM || !window.XRM.Options || !window.XRM.Options.register) {
        throw new Error('XRM.Options.core.js 必须先于 XRM.Options.contact.js 加载（请检查窗体库加载顺序）');
    }
    var R = window.XRM.Options.register;
    R("contact", "accountrolecode", {
        Approval: 1,  // 审批
        Decision: 2,  // 决策
        DecisionSupport: 3,  // 决策支撑
        Evaluator: 4,  // 评估人
        Impact: 5,  // 影响
    }, { 1: "审批", 2: "决策", 3: "决策支撑", 4: "评估人", 5: "影响" });
    R("contact", "address1_addresstypecode", {
        BillTo: 1,  // 帐单邮寄地址
        ShipTo: 2,  // 送货地址
        PrimaryAddress: 3,  // 主要地址
        Other: 4,  // 其他
    }, { 1: "帐单邮寄地址", 2: "送货地址", 3: "主要地址", 4: "其他" });
    R("contact", "address1_freighttermscode", {
        FOB: 1,  // FOB
        NoCharge: 2,  // 免收费用
    }, { 1: "FOB", 2: "免收费用" });
    R("contact", "address1_shippingmethodcode", {
        Airborne: 1,  // 航空运输
        DHL: 2,  // DHL
        FedEx: 3,  // FedEx
        UPS: 4,  // UPS
        PostalMail: 5,  // 邮递
        FullLoad: 6,  // Full Load
        WillCall: 7,  // Will Call
    }, { 1: "航空运输", 2: "DHL", 3: "FedEx", 4: "UPS", 5: "邮递", 6: "Full Load", 7: "Will Call" });
    R("contact", "address2_addresstypecode", {
        DefaultValue: 1,  // 默认值
    }, { 1: "默认值" });
    R("contact", "address2_freighttermscode", {
        DefaultValue: 1,  // 默认值
    }, { 1: "默认值" });
    R("contact", "address2_shippingmethodcode", {
        DefaultValue: 1,  // 默认值
    }, { 1: "默认值" });
    R("contact", "address3_addresstypecode", {
        DefaultValue: 1,  // 默认值
    }, { 1: "默认值" });
    R("contact", "address3_freighttermscode", {
        DefaultValue: 1,  // 默认值
    }, { 1: "默认值" });
    R("contact", "address3_shippingmethodcode", {
        DefaultValue: 1,  // 默认值
    }, { 1: "默认值" });
    R("contact", "customersizecode", {
        DefaultValue: 1,  // 默认值
    }, { 1: "默认值" });
    R("contact", "customertypecode", {
        DefaultValue: 1,  // 默认值
    }, { 1: "默认值" });
    R("contact", "educationcode", {
        DefaultValue: 1,  // 默认值
    }, { 1: "默认值" });
    R("contact", "familystatuscode", {
        Single: 1,  // 单身
        Married: 2,  // 已婚
        Divorced: 3,  // 离异
        Widowed: 4,  // 丧偶
    }, { 1: "单身", 2: "已婚", 3: "离异", 4: "丧偶" });
    R("contact", "gendercode", {
        Male: 1,  // 男
        Female: 2,  // 女
    }, { 1: "男", 2: "女" });
    R("contact", "haschildrencode", {
        DefaultValue: 1,  // 默认值
    }, { 1: "默认值" });
    R("contact", "leadsourcecode", {
        DefaultValue: 1,  // 默认值
    }, { 1: "默认值" });
    R("contact", "new_arrelationshiplevel", {
        Option1: 1,  // 无话不谈
        Option2: 2,  // 分享情绪
        Option3: 3,  // 分享态度
        Option4: 4,  // 公事公办
        Option5: 5,  // 抵触沟通
    }, { 1: "无话不谈", 2: "分享情绪", 3: "分享态度", 4: "公事公办", 5: "抵触沟通" });
    R("contact", "new_commstyle", {
        Option1: 1,  // 控制型
        Option2: 2,  // 倡导型
        Option3: 3,  // 分析型
        Option4: 4,  // 亲切型
    }, { 1: "控制型", 2: "倡导型", 3: "分析型", 4: "亲切型" });
    R("contact", "new_contactstatus", {
        Option1: 1,  // 未接触
        Option2: 2,  // 初步接触
        Option3: 3,  // 多次接触
        Option4: 4,  // 深入接触
    }, { 1: "未接触", 2: "初步接触", 3: "多次接触", 4: "深入接触" });
    R("contact", "new_relationship", {
        Option5: 5,  // 3-教练
        Option4: 4,  // 2-排他
        Option3: 3,  // 1-支持
        Option2: 2,  // 0-中立
        Option1: 1,  // 反对
    }, { 5: "3-教练", 4: "2-排他", 3: "1-支持", 2: "0-中立", 1: "反对" });
    R("contact", "paymenttermscode", {
        Net30: 1,  // N30
        Option2: 2,  // 2% 10，净30
        Net45: 3,  // N45
        Net60: 4,  // N60
    }, { 1: "N30", 2: "2% 10，净30", 3: "N45", 4: "N60" });
    R("contact", "preferredappointmentdaycode", {
        Sunday: 0,  // 星期日
        Monday: 1,  // 星期一
        Tuesday: 2,  // 星期二
        Wednesday: 3,  // 星期三
        Thursday: 4,  // 星期四
        Friday: 5,  // 星期五
        Saturday: 6,  // 星期六
    }, { 0: "星期日", 1: "星期一", 2: "星期二", 3: "星期三", 4: "星期四", 5: "星期五", 6: "星期六" });
    R("contact", "preferredappointmenttimecode", {
        Morning: 1,  // 上午
        Afternoon: 2,  // 下午
        Evening: 3,  // 晚上
    }, { 1: "上午", 2: "下午", 3: "晚上" });
    R("contact", "preferredcontactmethodcode", {
        Any: 1,  // 任何方式
        Email: 2,  // 电子邮件
        Option3: 3,  // 电话
        Option4: 4,  // 传真
    }, { 1: "任何方式", 2: "电子邮件", 3: "电话", 4: "传真" });
    R("contact", "shippingmethodcode", {
        DefaultValue: 1,  // 默认值
    }, { 1: "默认值" });
    R("contact", "statecode", {
        Active: 0,  // 可用
        Inactive: 1,  // 停用
    }, { 0: "可用", 1: "停用" });
    R("contact", "statuscode", {
        Active: 1,  // 可用
        Inactive: 2,  // 停用
    }, { 1: "可用", 2: "停用" });
    R("contact", "territorycode", {
        DefaultValue: 1,  // 默认值
    }, { 1: "默认值" });
})(window);
