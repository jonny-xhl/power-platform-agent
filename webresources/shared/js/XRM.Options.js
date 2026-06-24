/**
 * XRM.Options.js — 自动生成的 OptionSet 语义化常量模块
 * ⚠️ 本文件由 metadata_generate_optionset_constants 工具自动生成，请勿手动编辑。
 *
 * 数据源：Dataverse 环境「dev」
 * 生成范围：0 个全局选项集，1 个实体的 29 个字段级 Picklist
 * 生成时间：2026-06-24 20:05:28
 *
 * 用法：
 *   // 字段级：XRM.Options.entities.<entity>.<field>.<Name>
 *   if (XRM.Form.getValue('new_status') ===
 *       XRM.Options.entities.account.new_status.Active) { ... }
 *   // 全局：XRM.Options.global.<optionset>.<Name>
 *   if (val === XRM.Options.global.new_customer_status.Active) { ... }
 *   // 显示标签：XRM.Options.getLabel('account.new_status', value)
 *   // 反查值：  XRM.Options.getValue('account.new_status', '冻结')
 *
 * 说明：
 *   - 常量键优先取英文标签；仅中文标签时回退 Option{value}（行尾注释保留中文）。
 *   - Boolean（Two Options）字段不生成常量（其 getValue() 返回 true/false，请直接判断布尔值）。
 *   - 数据来自环境定义，可能与本地 metadata YAML 不同，以本文件为准。
 */
(function (window, undefined) {
    'use strict';
    window.XRM = window.XRM || {};

    var O = window.XRM.Options = {
        global: {},
        entities: {
            contact: {
                // contact.accountrolecode
                accountrolecode: {
                    Approval: 1,  // 审批
                    Decision: 2,  // 决策
                    DecisionSupport: 3,  // 决策支撑
                    Evaluator: 4,  // 评估人
                    Impact: 5,  // 影响
                },
                // contact.address1_addresstypecode
                address1_addresstypecode: {
                    BillTo: 1,  // 帐单邮寄地址
                    ShipTo: 2,  // 送货地址
                    PrimaryAddress: 3,  // 主要地址
                    Other: 4,  // 其他
                },
                // contact.address1_freighttermscode
                address1_freighttermscode: {
                    FOB: 1,  // FOB
                    NoCharge: 2,  // 免收费用
                },
                // contact.address1_shippingmethodcode
                address1_shippingmethodcode: {
                    Airborne: 1,  // 航空运输
                    DHL: 2,  // DHL
                    FedEx: 3,  // FedEx
                    UPS: 4,  // UPS
                    PostalMail: 5,  // 邮递
                    FullLoad: 6,  // 满载
                    WillCall: 7,  // 自提
                },
                // contact.address2_addresstypecode
                address2_addresstypecode: {
                    DefaultValue: 1,  // 默认值
                },
                // contact.address2_freighttermscode
                address2_freighttermscode: {
                    DefaultValue: 1,  // 默认值
                },
                // contact.address2_shippingmethodcode
                address2_shippingmethodcode: {
                    DefaultValue: 1,  // 默认值
                },
                // contact.address3_addresstypecode
                address3_addresstypecode: {
                    DefaultValue: 1,  // 默认值
                },
                // contact.address3_freighttermscode
                address3_freighttermscode: {
                    DefaultValue: 1,  // 默认值
                },
                // contact.address3_shippingmethodcode
                address3_shippingmethodcode: {
                    DefaultValue: 1,  // 默认值
                },
                // contact.customersizecode
                customersizecode: {
                    DefaultValue: 1,  // 默认值
                },
                // contact.customertypecode
                customertypecode: {
                    DefaultValue: 1,  // 默认值
                },
                // contact.educationcode
                educationcode: {
                    DefaultValue: 1,  // 默认值
                },
                // contact.familystatuscode
                familystatuscode: {
                    Single: 1,  // 单身
                    Married: 2,  // 已婚
                    Divorced: 3,  // 离异
                    Widowed: 4,  // 丧偶
                },
                // contact.gendercode
                gendercode: {
                    Male: 1,  // 男
                    Female: 2,  // 女
                },
                // contact.haschildrencode
                haschildrencode: {
                    DefaultValue: 1,  // 默认值
                },
                // contact.leadsourcecode
                leadsourcecode: {
                    DefaultValue: 1,  // 默认值
                },
                // contact.new_arrelationshiplevel
                new_arrelationshiplevel: {
                    Option1: 1,  // 无话不谈
                    Option2: 2,  // 分享情绪
                    Option3: 3,  // 分享态度
                    Option4: 4,  // 公事公办
                    Option5: 5,  // 抵触沟通
                },
                // contact.new_commstyle
                new_commstyle: {
                    Option1: 1,  // 控制型
                    Option2: 2,  // 倡导型
                    Option3: 3,  // 分析型
                    Option4: 4,  // 亲切型
                },
                // contact.new_contactstatus
                new_contactstatus: {
                    Option1: 1,  // 未接触
                    Option2: 2,  // 初步接触
                    Option3: 3,  // 多次接触
                    Option4: 4,  // 深入接触
                },
                // contact.new_relationship
                new_relationship: {
                    Option5: 5,  // 3-教练
                    Option4: 4,  // 2-排他
                    Option3: 3,  // 1-支持
                    Option2: 2,  // 0-中立
                    Option1: 1,  // 反对
                },
                // contact.paymenttermscode
                paymenttermscode: {
                    Net30: 1,  // N30
                    Option2: 2,  // 2% 10，净30
                    Net45: 3,  // N45
                    Net60: 4,  // N60
                },
                // contact.preferredappointmentdaycode
                preferredappointmentdaycode: {
                    Sunday: 0,  // 星期日
                    Monday: 1,  // 星期一
                    Tuesday: 2,  // 星期二
                    Wednesday: 3,  // 星期三
                    Thursday: 4,  // 星期四
                    Friday: 5,  // 星期五
                    Saturday: 6,  // 星期六
                },
                // contact.preferredappointmenttimecode
                preferredappointmenttimecode: {
                    Morning: 1,  // 上午
                    Afternoon: 2,  // 下午
                    Evening: 3,  // 晚上
                },
                // contact.preferredcontactmethodcode
                preferredcontactmethodcode: {
                    Any: 1,  // 任何方式
                    Email: 2,  // 电子邮件
                    Option3: 3,  // 电话
                    Option4: 4,  // 传真
                },
                // contact.shippingmethodcode
                shippingmethodcode: {
                    DefaultValue: 1,  // 默认值
                },
                // contact.statecode
                statecode: {
                    Active: 0,  // 可用
                    Inactive: 1,  // 停用
                },
                // contact.statuscode
                statuscode: {
                    Active: 1,  // 可用
                    Inactive: 2,  // 停用
                },
                // contact.territorycode
                territorycode: {
                    DefaultValue: 1,  // 默认值
                },
            },
        },
        labels: {
            "contact.accountrolecode": { 1: "审批", 2: "决策", 3: "决策支撑", 4: "评估人", 5: "影响" },
            "contact.address1_addresstypecode": { 1: "帐单邮寄地址", 2: "送货地址", 3: "主要地址", 4: "其他" },
            "contact.address1_freighttermscode": { 1: "FOB", 2: "免收费用" },
            "contact.address1_shippingmethodcode": { 1: "航空运输", 2: "DHL", 3: "FedEx", 4: "UPS", 5: "邮递", 6: "满载", 7: "自提" },
            "contact.address2_addresstypecode": { 1: "默认值" },
            "contact.address2_freighttermscode": { 1: "默认值" },
            "contact.address2_shippingmethodcode": { 1: "默认值" },
            "contact.address3_addresstypecode": { 1: "默认值" },
            "contact.address3_freighttermscode": { 1: "默认值" },
            "contact.address3_shippingmethodcode": { 1: "默认值" },
            "contact.customersizecode": { 1: "默认值" },
            "contact.customertypecode": { 1: "默认值" },
            "contact.educationcode": { 1: "默认值" },
            "contact.familystatuscode": { 1: "单身", 2: "已婚", 3: "离异", 4: "丧偶" },
            "contact.gendercode": { 1: "男", 2: "女" },
            "contact.haschildrencode": { 1: "默认值" },
            "contact.leadsourcecode": { 1: "默认值" },
            "contact.new_arrelationshiplevel": { 1: "无话不谈", 2: "分享情绪", 3: "分享态度", 4: "公事公办", 5: "抵触沟通" },
            "contact.new_commstyle": { 1: "控制型", 2: "倡导型", 3: "分析型", 4: "亲切型" },
            "contact.new_contactstatus": { 1: "未接触", 2: "初步接触", 3: "多次接触", 4: "深入接触" },
            "contact.new_relationship": { 5: "3-教练", 4: "2-排他", 3: "1-支持", 2: "0-中立", 1: "反对" },
            "contact.paymenttermscode": { 1: "N30", 2: "2% 10，净30", 3: "N45", 4: "N60" },
            "contact.preferredappointmentdaycode": { 0: "星期日", 1: "星期一", 2: "星期二", 3: "星期三", 4: "星期四", 5: "星期五", 6: "星期六" },
            "contact.preferredappointmenttimecode": { 1: "上午", 2: "下午", 3: "晚上" },
            "contact.preferredcontactmethodcode": { 1: "任何方式", 2: "电子邮件", 3: "电话", 4: "传真" },
            "contact.shippingmethodcode": { 1: "默认值" },
            "contact.statecode": { 0: "可用", 1: "停用" },
            "contact.statuscode": { 1: "可用", 2: "停用" },
            "contact.territorycode": { 1: "默认值" },
        },
        getLabel: function (path, value) {
            var m = O.labels[path];
            return (m && m[value] !== undefined) ? m[value] : '';
        },
        getValue: function (path, label) {
            var m = O.labels[path];
            if (!m) { return null; }
            for (var v in m) { if (m[v] === label) { return Number(v); } }
            return null;
        }
    };
})(window);
