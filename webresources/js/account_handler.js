/**
 * 账户表单处理脚本
 * Power Platform - 账户实体表单业务逻辑
 *
 * 功能:
 * - 表单加载初始化
 * - 账户状态管理
 * - 余额显示和刷新
 * - 表单验证
 * - 保存处理
 */

(function(window, document, undefined) {
    'use strict';

    // ==================== 命名空间 ====================
    window.AccountHandler = window.AccountHandler || {};

    // ==================== 常量定义 ====================
    var STATUS = {
        ACTIVE: 100000000,
        FROZEN: 100000001,
        CLOSED: 100000002
    };

    var ACCOUNT_TYPE = {
        INDIVIDUAL: 100000000,
        BUSINESS: 100000001,
        GOVERNMENT: 100000002
    };

    // ==================== 全局变量 ====================
    var formContext = null;
    var accountData = null;

    // ==================== 表单加载事件 ====================
    /**
     * 表单加载处理函数
     */
    function handleFormLoad(executionContext) {
        formContext = executionContext.getFormContext();

        try {
            // 获取账户数据
            accountData = getAccountData();

            // 初始化UI
            initializeUI();

            // 注册事件处理
            registerEventHandlers();

            // 检查账户状态
            checkAccountStatus();

            console.log('Account form loaded successfully');
        } catch (error) {
            showError('表单加载失败: ' + error.message);
        }
    }

    // ==================== UI初始化 ====================
    /**
     * 初始化用户界面
     */
    function initializeUI() {
        // 设置状态标签样式
        updateStatusBadge();

        // 设置账户类型图标
        updateAccountTypeIcon();

        // 格式化余额显示
        formatBalanceDisplay();

        // 显示/隐藏相关字段
        toggleRelatedFields();
    }

    // ==================== 事件注册 ====================
    /**
     * 注册事件处理程序
     */
    function registerEventHandlers() {
        var statusField = formContext.getAttribute('new_status');
        if (statusField) {
            statusField.addOnChange(onStatusChange);
        }

        var accountTypeField = formContext.getAttribute('new_accounttype');
        if (accountTypeField) {
            accountTypeField.addOnChange(onAccountTypeChange);
        }

        var balanceField = formContext.getAttribute('new_balance');
        if (balanceField) {
            balanceField.addOnChange(onBalanceChange);
        }
    }

    // ==================== 状态变更处理 ====================
    /**
     * 状态变更处理
     */
    function onStatusChange(executionContext) {
        var statusField = executionContext.getEventSource();
        var status = statusField.getValue();

        updateStatusBadge();

        // 根据状态显示/隐藏字段
        if (status === STATUS.CLOSED) {
            // 关闭账户时禁用某些字段
            disableFieldsOnClose();
        } else if (status === STATUS.FROZEN) {
            // 冻结账户时显示警告
            showFreezeWarning();
        }
    }

    // ==================== 账户类型变更 ====================
    /**
     * 账户类型变更处理
     */
    function onAccountTypeChange(executionContext) {
        updateAccountTypeIcon();
        toggleRelatedFields();
    }

    // ==================== 余额变更 ====================
    /**
     * 余额变更处理
     */
    function onBalanceChange(executionContext) {
        formatBalanceDisplay();
        checkCreditLimit();
    }

    // ==================== 表单保存事件 ====================
    /**
     * 表单保存处理
     */
    function handleFormSave(executionContext) {
        var saveEventContext = executionContext.getEventArgs();

        try {
            // 验证表单
            if (!validateForm()) {
                saveEventContext.preventDefault();
                return;
            }

            // 检查业务规则
            if (!checkBusinessRules()) {
                saveEventContext.preventDefault();
                return;
            }

            console.log('Form save validated successfully');
        } catch (error) {
            showError('保存验证失败: ' + error.message);
            saveEventContext.preventDefault();
        }
    }

    // ==================== 表单验证 ====================
    /**
     * 验证表单数据
     */
    function validateForm() {
        var isValid = true;
        var errors = [];

        // 验证账户编号
        var accountNumber = formContext.getAttribute('new_accountnumber').getValue();
        if (!accountNumber || accountNumber.trim() === '') {
            errors.push('账户编号不能为空');
            isValid = false;
        }

        // 验证账户名称
        var accountName = formContext.getAttribute('new_accountname').getValue();
        if (!accountName || accountName.trim() === '') {
            errors.push('账户名称不能为空');
            isValid = false;
        }

        // 验证余额
        var balance = formContext.getAttribute('new_balance').getValue();
        if (balance !== null && balance < 0) {
            errors.push('余额不能为负数');
            isValid = false;
        }

        // 显示验证错误
        if (!isValid) {
            showValidationErrors(errors);
        }

        return isValid;
    }

    // ==================== 业务规则检查 ====================
    /**
     * 检查业务规则
     */
    function checkBusinessRules() {
        var status = formContext.getAttribute('new_status').getValue();
        var balance = formContext.getAttribute('new_balance').getValue();
        var creditLimit = formContext.getAttribute('new_creditlimit').getValue();

        // 检查信用额度
        if (balance !== null && creditLimit !== null && balance > creditLimit) {
            var confirmOverride = confirm(
                '账户余额 (' + balance + ') 超过信用额度 (' + creditLimit + ')。\n' +
                '是否继续保存？'
            );
            if (!confirmOverride) {
                return false;
            }
        }

        // 检查关闭状态
        if (status === STATUS.CLOSED && balance > 0) {
            var confirmClose = confirm(
                '账户仍有余额 (' + balance + ')。\n' +
                '确定要关闭账户吗？'
            );
            if (!confirmClose) {
                return false;
            }
        }

        return true;
    }

    // ==================== 辅助函数 ====================

    /**
     * 获取账户数据
     */
    function getAccountData() {
        return {
            accountNumber: formContext.getAttribute('new_accountnumber').getValue(),
            accountName: formContext.getAttribute('new_accountname').getValue(),
            status: formContext.getAttribute('new_status').getValue(),
            balance: formContext.getAttribute('new_balance').getValue(),
            accountType: formContext.getAttribute('new_accounttype').getValue(),
            creditLimit: formContext.getAttribute('new_creditlimit').getValue()
        };
    }

    /**
     * 更新状态标签
     */
    function updateStatusBadge() {
        var status = formContext.getAttribute('new_status').getValue();
        var statusControl = formContext.getControl('new_status');

        if (statusControl) {
            // 移除所有状态类
            statusControl.getAttribute().controls.forEach(function(control) {
                control.getClasses().forEach(function(cssClass) {
                    if (cssClass.indexOf('status-badge') === 0) {
                        control.removeCssClass(cssClass);
                    }
                });
            });

            // 添加当前状态类
            if (status === STATUS.ACTIVE) {
                statusControl.addCssClass('status-badge active');
            } else if (status === STATUS.FROZEN) {
                statusControl.addCssClass('status-badge frozen');
            } else if (status === STATUS.CLOSED) {
                statusControl.addCssClass('status-badge closed');
            }
        }
    }

    /**
     * 更新账户类型图标
     */
    function updateAccountTypeIcon() {
        var accountType = formContext.getAttribute('new_accounttype').getValue();
        var typeControl = formContext.getControl('new_accounttype');

        if (typeControl) {
            // 根据类型更新图标
            var iconClass = '';
            if (accountType === ACCOUNT_TYPE.INDIVIDUAL) {
                iconClass = 'account-type-icon individual';
            } else if (accountType === ACCOUNT_TYPE.BUSINESS) {
                iconClass = 'account-type-icon business';
            } else if (accountType === ACCOUNT_TYPE.GOVERNMENT) {
                iconClass = 'account-type-icon government';
            }

            // 更新UI
        }
    }

    /**
     * 格式化余额显示
     */
    function formatBalanceDisplay() {
        var balance = formContext.getAttribute('new_balance').getValue();
        var balanceControl = formContext.getControl('new_balance');

        if (balanceControl && balance !== null) {
            var formatted = formatCurrency(balance);
            balanceControl.setLabel('账户余额 (' + formatted + ')');
        }
    }

    /**
     * 格式化货币
     */
    function formatCurrency(amount) {
        return '¥' + amount.toFixed(2).replace(/\d(?=(\d{3})+\.)/g, '$&,');
    }

    /**
     * 检查信用额度
     */
    function checkCreditLimit() {
        var balance = formContext.getAttribute('new_balance').getValue();
        var creditLimit = formContext.getAttribute('new_creditlimit').getValue();

        if (balance !== null && creditLimit !== null && balance > creditLimit) {
            showWarning('账户余额超过信用额度');
        }
    }

    /**
     * 检查账户状态
     */
    function checkAccountStatus() {
        var status = formContext.getAttribute('new_status').getValue();

        if (status === STATUS.FROZEN) {
            showFreezeWarning();
        } else if (status === STATUS.CLOSED) {
            disableFieldsOnClose();
        }
    }

    /**
     * 显示冻结警告
     */
    function showFreezeWarning() {
        showNotification('该账户已被冻结，无法进行交易操作', 'warning');
    }

    /**
     * 关闭时禁用字段
     */
    function disableFieldsOnClose() {
        var fieldsToDisable = ['new_balance', 'new_creditlimit'];
        fieldsToDisable.forEach(function(fieldName) {
            var control = formContext.getControl(fieldName);
            if (control) {
                control.setDisabled(true);
            }
        });
    }

    /**
     * 切换相关字段显示
     */
    function toggleRelatedFields() {
        var accountType = formContext.getAttribute('new_accounttype').getValue();
        // 根据账户类型显示/隐藏特定字段
    }

    /**
     * 显示验证错误
     */
    function showValidationErrors(errors) {
        var message = '请修正以下错误:\n' + errors.join('\n');
        alert(message);
    }

    /**
     * 显示通知
     */
    function showNotification(message, type) {
        type = type || 'info';
        Xrm.Utility.alertDialog(message);
    }

    /**
     * 显示错误
     */
    function showError(message) {
        Xrm.Utility.alertDialog('错误: ' + message);
    }

    /**
     * 显示警告
     */
    function showWarning(message) {
        Xrm.Utility.alertDialog('警告: ' + message);
    }

    // ==================== 公共API ====================

    /**
     * 批准账户
     */
    function approveAccount(selectedControl) {
        var accountNumber = selectedControl.getAttribute('new_accountnumber').getValue();
        var confirmApprove = confirm('确定要批准账户 ' + accountNumber + ' 吗？');

        if (confirmApprove) {
            // 设置状态为活跃
            selectedControl.getAttribute('new_status').setValue(STATUS.ACTIVE);
            selectedControl.data.entity.save();
        }
    }

    /**
     * 检查是否可以批准
     */
    function canApproveAccount(selectedControl) {
        var status = selectedControl.getAttribute('new_status').getValue();
        return status !== STATUS.ACTIVE;
    }

    /**
     * 检查账户是否活跃
     */
    function isAccountActive(selectedControl) {
        var status = selectedControl.getAttribute('new_status').getValue();
        return status === STATUS.ACTIVE;
    }

    /**
     * 刷新账户余额
     */
    function refreshAccountBalances(selectedItems) {
        showNotification('正在刷新余额...', 'info');
        // 实现余额刷新逻辑
    }

    /**
     * 设置账户状态
     */
    function setAccountStatus(selectedControl, status) {
        selectedControl.getAttribute('new_status').setValue(status);
        selectedControl.data.entity.save();
    }

    // ==================== 导出公共API ====================
    window.AccountHandler = {
        handleFormLoad: handleFormLoad,
        handleFormSave: handleFormSave,
        approveAccount: approveAccount,
        canApproveAccount: canApproveAccount,
        isAccountActive: isAccountActive,
        refreshAccountBalances: refreshAccountBalances,
        setAccountStatus: setAccountStatus,
        STATUS: STATUS,
        ACCOUNT_TYPE: ACCOUNT_TYPE
    };

})(window, document);
