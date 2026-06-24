/**
 * 账户表单处理脚本
 * Power Platform - 账户实体表单业务逻辑
 *
 * 依赖：须在「窗体库」中先于本脚本加载 XRM.Common（XRM.Common.debug.js / XRM.Common.js）。
 * 本脚本统一通过 XRM.Common 封装调用，避免直接使用原生 Xrm API。
 *
 * 功能:
 * - 表单加载初始化
 * - 账户状态管理
 * - 余额显示和刷新
 * - 表单验证
 * - 保存处理
 */

(function (window, document, undefined) {
    'use strict';

    // ==================== 命名空间 ====================
    window.AccountHandler = window.AccountHandler || {};

    // 公共库别名（依赖 XRM.Common 先于本脚本加载）
    var Common = XRM.Common;
    var Form = Common.Form;
    var Nav = Common.Nav;
    var Util = Common.Util;

    // ==================== 常量定义 ====================
    // 选项集整数值。后续生成 account 的 OptionSet 常量后，
    // 可替换为 XRM.Options.entities.account.new_status.Active 等语义化引用。
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

    // OnSave 异步确认标记：确认通过后手动触发的保存会被放行，避免循环
    var _saveConfirmed = false;
    var accountData = null;

    // ==================== 表单加载事件 ====================
    /**
     * 表单加载处理函数（绑定到窗体 OnLoad 事件）
     */
    function handleFormLoad(executionContext) {
        // 初始化公共库（内部缓存 formContext / globalContext）
        Common.init(executionContext);

        try {
            accountData = getAccountData();
            initializeUI();
            registerEventHandlers();
            checkAccountStatus();
            Util.log('Account form loaded successfully');
        } catch (error) {
            showError('表单加载失败: ' + error.message);
        }
    }

    // ==================== UI初始化 ====================
    /**
     * 初始化用户界面
     */
    function initializeUI() {
        updateStatusBadge();
        updateAccountTypeIcon();
        formatBalanceDisplay();
        toggleRelatedFields();
    }

    // ==================== 事件注册 ====================
    /**
     * 注册事件处理程序（通过 Common 注册字段 OnChange）
     */
    function registerEventHandlers() {
        Form.onChange('new_status', onStatusChange);
        Form.onChange('new_accounttype', onAccountTypeChange);
        Form.onChange('new_balance', onBalanceChange);
    }

    // ==================== 状态变更处理 ====================
    /**
     * 状态变更处理
     */
    function onStatusChange() {
        var status = Form.getValue('new_status');

        updateStatusBadge();

        if (status === STATUS.CLOSED) {
            disableFieldsOnClose();
        } else if (status === STATUS.FROZEN) {
            showFreezeWarning();
        }
    }

    // ==================== 账户类型变更 ====================
    /**
     * 账户类型变更处理
     */
    function onAccountTypeChange() {
        updateAccountTypeIcon();
        toggleRelatedFields();
    }

    // ==================== 余额变更 ====================
    /**
     * 余额变更处理
     */
    function onBalanceChange() {
        formatBalanceDisplay();
        checkCreditLimit();
    }

    // ==================== 表单保存事件 ====================
    /**
     * 表单保存处理（绑定到窗体 OnSave 事件）
     *
     * 业务规则确认使用 Common.Nav.confirm（异步 Promise）。由于 OnSave 中无法
     * 同步等待异步对话框来决定 preventDefault，采用标准模式：
     *   先 preventDefault 阻断本次自动保存 → 异步确认 → 通过则按原保存模式手动 save。
     * _saveConfirmed 标记用于放行手动触发的二次保存，避免无限循环。
     */
    function handleFormSave(executionContext) {
        var eventArgs = executionContext.getEventArgs();

        try {
            // 同步校验失败 -> 阻止保存
            if (!validateForm()) {
                eventArgs.preventDefault();
                return;
            }

            // 已确认的本次手动保存 -> 放行（并复位标记）
            if (_saveConfirmed) {
                _saveConfirmed = false;
                return;
            }

            // 阻断本次保存，转异步确认
            eventArgs.preventDefault();
            var saveMode = eventArgs.getSaveMode ? eventArgs.getSaveMode() : 1;

            checkBusinessRules().then(function (ok) {
                if (ok) {
                    _saveConfirmed = true;
                    Form.save(saveActionFromMode(saveMode));
                }
            }).catch(function (err) {
                Util.log('保存确认异常: ' + (err && err.message ? err.message : err), 'error');
            });
        } catch (error) {
            showError('保存验证失败: ' + error.message);
            eventArgs.preventDefault();
        }
    }

    /**
     * 将 OnSave 的 getSaveMode() 数值映射为 Common.Form.save 接受的动作字符串
     */
    function saveActionFromMode(mode) {
        // 1=Save, 2=SaveAndClose, 59=SaveAndNew，其余（含 AutoSave=70）按普通保存
        if (mode === 2) return 'saveandclose';
        if (mode === 59) return 'saveandnew';
        return 'save';
    }

    // ==================== 表单验证 ====================
    /**
     * 验证表单数据
     */
    function validateForm() {
        var errors = [];

        if (Util.isEmpty(Form.getValue('new_accountnumber'))) {
            errors.push('账户编号不能为空');
        }

        if (Util.isEmpty(Form.getValue('new_accountname'))) {
            errors.push('账户名称不能为空');
        }

        var balance = Form.getValue('new_balance');
        if (balance !== null && balance < 0) {
            errors.push('余额不能为负数');
        }

        if (errors.length > 0) {
            showValidationErrors(errors);
            return false;
        }
        return true;
    }

    // ==================== 业务规则检查（异步） ====================
    /**
     * 检查业务规则（涉及异步确认对话框）
     * @returns {Promise<boolean>} true 表示通过（含用户确认）
     */
    function checkBusinessRules() {
        var status = Form.getValue('new_status');
        var balance = Form.getValue('new_balance');
        var creditLimit = Form.getValue('new_creditlimit');

        // 余额超过信用额度
        if (balance !== null && creditLimit !== null && balance > creditLimit) {
            return Nav.confirm(
                '账户余额 (' + balance + ') 超过信用额度 (' + creditLimit + ')。\n是否继续保存？',
                '确认'
            );
        }

        // 关闭状态仍有余额
        if (status === STATUS.CLOSED && balance > 0) {
            return Nav.confirm(
                '账户仍有余额 (' + balance + ')。\n确定要关闭账户吗？',
                '确认'
            );
        }

        return Promise.resolve(true);
    }

    // ==================== 辅助函数 ====================

    /**
     * 获取账户数据
     */
    function getAccountData() {
        return {
            accountNumber: Form.getValue('new_accountnumber'),
            accountName: Form.getValue('new_accountname'),
            status: Form.getValue('new_status'),
            balance: Form.getValue('new_balance'),
            accountType: Form.getValue('new_accounttype'),
            creditLimit: Form.getValue('new_creditlimit')
        };
    }

    /**
     * 更新状态标签
     * 注意：CSS 类操作为控件级 API，XRM.Common 未封装，沿用控件原生方法。
     */
    function updateStatusBadge() {
        var status = Form.getValue('new_status');
        var statusControl = Form.getControl('new_status');

        if (statusControl) {
            statusControl.getAttribute().controls.forEach(function (control) {
                control.getClasses().forEach(function (cssClass) {
                    if (cssClass.indexOf('status-badge') === 0) {
                        control.removeCssClass(cssClass);
                    }
                });
            });

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
        var accountType = Form.getValue('new_accounttype');
        var iconClass = '';
        if (accountType === ACCOUNT_TYPE.INDIVIDUAL) {
            iconClass = 'account-type-icon individual';
        } else if (accountType === ACCOUNT_TYPE.BUSINESS) {
            iconClass = 'account-type-icon business';
        } else if (accountType === ACCOUNT_TYPE.GOVERNMENT) {
            iconClass = 'account-type-icon government';
        }
        // 根据 iconClass 更新 UI（占位）
    }

    /**
     * 格式化余额显示
     */
    function formatBalanceDisplay() {
        var balance = Form.getValue('new_balance');
        if (balance !== null && balance !== undefined) {
            Form.setLabel('new_balance', '账户余额 (' + Util.formatCurrency(balance) + ')');
        }
    }

    /**
     * 检查信用额度
     */
    function checkCreditLimit() {
        var balance = Form.getValue('new_balance');
        var creditLimit = Form.getValue('new_creditlimit');

        if (balance !== null && creditLimit !== null && balance > creditLimit) {
            showWarning('账户余额超过信用额度');
        }
    }

    /**
     * 检查账户状态
     */
    function checkAccountStatus() {
        var status = Form.getValue('new_status');

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
        Form.setDisabledLevel(['new_balance', 'new_creditlimit'], true);
    }

    /**
     * 切换相关字段显示
     */
    function toggleRelatedFields() {
        var accountType = Form.getValue('new_accounttype');
        // 根据账户类型显示/隐藏特定字段（占位）
    }

    /**
     * 显示验证错误
     */
    function showValidationErrors(errors) {
        Nav.alert('请修正以下错误:\n' + errors.join('\n'), '验证错误');
    }

    /**
     * 显示通知（统一走 Common 弹窗）
     */
    function showNotification(message, type) {
        // type 在此场景仅作记录，弹窗不区分级别
        Nav.alert(message);
    }

    /**
     * 显示错误
     */
    function showError(message) {
        Nav.alert('错误: ' + message, '错误');
    }

    /**
     * 显示警告
     */
    function showWarning(message) {
        Nav.alert('警告: ' + message, '警告');
    }

    // ==================== 公共API（命令栏/Ribbon） ====================

    /**
     * 确保公共库已用传入的主控件初始化。
     * Ribbon 上下文传入的是 formContext（而非 executionContext），用 shim 适配 Common.init。
     */
    function ensureCommon(primaryControl) {
        if (!Common.isInitialized() && primaryControl) {
            Common.init({ getFormContext: function () { return primaryControl; } });
        }
        return Common;
    }

    /**
     * 批准账户
     */
    function approveAccount(primaryControl) {
        ensureCommon(primaryControl);
        var accountNumber = Form.getValue('new_accountnumber');

        Nav.confirm('确定要批准账户 ' + accountNumber + ' 吗？', '确认').then(function (ok) {
            if (ok) {
                Form.setValue('new_status', STATUS.ACTIVE);
                Form.save('save');
            }
        });
    }

    /**
     * 检查是否可以批准
     */
    function canApproveAccount(primaryControl) {
        ensureCommon(primaryControl);
        return Form.getValue('new_status') !== STATUS.ACTIVE;
    }

    /**
     * 检查账户是否活跃
     */
    function isAccountActive(primaryControl) {
        ensureCommon(primaryControl);
        return Form.getValue('new_status') === STATUS.ACTIVE;
    }

    /**
     * 刷新账户余额
     */
    function refreshAccountBalances() {
        showNotification('正在刷新余额...', 'info');
        // 实现余额刷新逻辑
    }

    /**
     * 设置账户状态
     */
    function setAccountStatus(primaryControl, status) {
        ensureCommon(primaryControl);
        Form.setValue('new_status', status);
        Form.save('save');
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
