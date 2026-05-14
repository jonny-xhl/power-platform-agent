/**
 * XRM.Common.js TypeScript 类型定义
 * 版本: 1.0.0
 * 描述: 为 XRM.Common.js 提供 TypeScript 类型支持
 */

declare namespace XRM {
    /**
     * XRM.Common 命名空间
     */
    namespace Common {
        // ==================== 类型定义 ====================

        /**
         * 保存操作类型
         */
        type SaveAction = 'save' | 'saveandclose' | 'saveandnew';

        /**
         * 必填级别
         */
        type RequiredLevel = 'none' | 'required' | 'recommended';

        /**
         * 通知级别
         */
        type NotificationLevel = 'INFO' | 'WARNING' | 'ERROR';

        /**
         * 表单类型
         */
        type FormType = 0 | 1 | 2 | 3 | 4 | 6;

        /**
         * 客户端类型
         */
        type ClientType = 'Web' | 'Outlook' | 'Mobile' | 'UnifiedInterface';

        /**
         * 客户端状态
         */
        type ClientState = 'Online' | 'Offline';

        /**
         * 设备类型
         */
        type FormFactor = 'Phone' | 'Tablet' | 'Desktop';

        /**
         * 数据操作结果
         */
        interface DataResult {
            success: boolean;
            id?: string;
            data?: any;
            error?: any;
            count?: number;
        }

        /**
         * 查询选项
         */
        interface QueryOptions {
            filter?: string;
            columns?: string[];
            top?: number;
            orderBy?: string;
            orderDescending?: boolean;
        }

        /**
         * FetchXML 查询对象
         */
        interface FetchXmlOptions {
            entity: string;
            columns?: string[];
            order?: Array<{ attribute: string; descending: boolean }>;
            filter?: {
                type?: 'and' | 'or';
                conditions?: Array<{ attribute: string; operator: string; value?: any }>;
            };
        }

        /**
         * Action 参数
         */
        interface ActionParams {
            [key: string]: any;
        }

        /**
         * 导航选项
         */
        interface NavigationOptions {
            entityName?: string;
            entityId?: string;
            width?: number;
            height?: number;
            position?: number;
            title?: string;
            fromEntityName?: string;
            data?: any;
            createFromEntity?: {
                entityType: string;
                id: string;
            };
            useQuickCreateForm?: boolean;
            openInNewWindow?: boolean;
            target?: number;
        }

        /**
         * 查找对话框选项
         */
        interface LookupOptions {
            entityType: string;
            allowMultiSelect?: boolean;
            defaultEntityType?: string;
            defaultViewId?: string;
            disallowPicklist?: boolean;
            filters?: Array<any>;
            viewIds?: string[];
        }

        /**
         * 用户角色
         */
        interface UserRole {
            id: string;
            name: string;
        }

        /**
         * 事务货币
         */
        interface TransactionCurrency {
            id: string;
            name: string;
            entityType: string;
        }

        /**
         * 日期格式信息
         */
        interface DateFormattingInfo {
            FirstDayOfWeek?: string;
            LongDatePattern?: string;
            MonthDayPattern?: string;
            ShortDatePattern?: string;
            TimeSeparator?: string;
        }

        // ==================== Form API ====================

        namespace Form {
            function getAttribute(name: string): Xrm.Attributes.Attribute<any>;
            function getControl(name: string): Xrm.Controls.Control<any>;
            function getValue(name: string): any;
            function setValue(name: string, value: any): Form;
            function setValues(data: { [key: string]: any }): Form;
            function setRequired(name: string, level: RequiredLevel): Form;
            function setRequiredLevel(names: string | string[], level: RequiredLevel): Form;
            function setDisabled(name: string, disabled: boolean): Form;
            function setDisabledLevel(names: string | string[], disabled: boolean): Form;
            function setVisible(name: string, visible: boolean): Form;
            function setVisibleLevel(names: string | string[], visible: boolean): Form;
            function setLabel(name: string, label: string): Form;
            function addNotification(name: string, message: string, level?: NotificationLevel): Form;
            function clearNotification(name: string): Form;
            function setFocus(name: string): Form;
            function save(action?: SaveAction): void;
            function getFormType(): number;
            function getEntityName(): string;
            function getId(): string;
            function getPrimaryAttributeValue(): string;
            function getIsDirty(): boolean;
            function isValid(): boolean;
            function refresh(save?: boolean): void;
            function getAttributes(): Xrm.Collection<Xrm.Attributes.Attribute<any>>;
            function getControls(): Xrm.Collection<Xrm.Controls.Control<any>>;
            function getDataXml(): string;
            function onLoad(handler: () => void): void;
            function onSave(handler: (context?: any) => void): void;
        }

        // ==================== Data API ====================

        namespace Data {
            function create(entity: string, data: any): Promise<DataResult>;
            function retrieve(entity: string, id: string, columns?: string | string[]): Promise<DataResult>;
            function update(entity: string, id: string, data: any): Promise<DataResult>;
            function delete(entity: string, id: string): Promise<DataResult>;
            function retrieveMultipleRecords(entity: string, options?: string): Promise<DataResult>;
            function query(entity: string, filter?: string, columns?: string[], top?: number): Promise<DataResult>;
            function fetchXml(fetchXml: string): Promise<DataResult>;
            function batch(operations: any[]): Promise<DataResult>;
            function action(name: string, params?: ActionParams, entity?: string, id?: string): Promise<DataResult>;
            function function(name: string, params?: ActionParams): Promise<DataResult>;
            function whoAmI(): Promise<DataResult>;
            function associate(entity: string, id: string, relation: string, relatedId: string): Promise<DataResult>;
            function disassociate(entity: string, id: string, relation: string, relatedId: string): Promise<DataResult>;
        }

        // ==================== Nav API ====================

        namespace Nav {
            function openForm(entity: string, id?: string, options?: NavigationOptions): void;
            function createForm(entity: string, data?: any, options?: NavigationOptions): void;
            function quickCreate(entity: string, data?: any): void;
            function openEntityList(entity: string, viewId?: string): void;
            function openUrl(url: string, width?: number, height?: number): void;
            function openWebResource(name: string, data?: any, options?: any): void;
            function alert(message: string, title?: string): Promise<any>;
            function confirm(message: string, title?: string, confirmLabel?: string, cancelLabel?: string): Promise<boolean>;
            function error(message: string, details?: any): void;
            function openDialog(name: string, options?: NavigationOptions): void;
            function navigateTo(pageInput: any, navigationOptions?: any): void;
        }

        // ==================== UI API ====================

        namespace UI {
            function showNotification(message: string, level?: NotificationLevel, id?: string): void;
            function showInfo(message: string, id?: string): void;
            function showWarning(message: string, id?: string): void;
            function showError(message: string, id?: string): void;
            function clearNotification(id?: string): void;
            function showProgress(message?: string): void;
            function closeProgress(): void;
            function lookupObjects(options: LookupOptions): Promise<any>;
            function refreshParentGrid(entityId?: string): void;
        }

        // ==================== Ctx API ====================

        namespace Ctx {
            // 通用
            function getGlobalContext(): Xrm.GlobalContext;

            // 用户信息
            function getUserId(): string;
            function getUserName(): string;
            function getUserLcid(): number;
            function getUserLangCode(): string;
            function getUserRoles(): UserRole[];
            function getUserRoleIds(): string[];
            function hasRole(roleName: string): boolean;
            function getSecurityRolePrivileges(): string[];
            function getDefaultDashboardId(): string;
            function isHighContrastEnabled(): boolean;
            function isRTL(): boolean;
            function getDateFormattingInfo(): DateFormattingInfo;
            function getTransactionCurrency(): TransactionCurrency;

            // 组织信息
            function getOrgUniqueName(): string;
            function getOrgLcid(): number;
            function getOrgLangCode(): string;
            function getServerUrl(): string;
            function getClientUrl(): string;

            // 客户端信息
            function getClient(): ClientType;
            function getClientState(): ClientState;
            function isOffline(): boolean;
            function getFormFactor(): number;
            function isMobile(): boolean;

            // 多语言
            function translate(key: string, lcid?: number): string;
            function getResourceString(webResourceName: string, key: string): string;
            function setResources(resources: { [langCode: string]: { [key: string]: string } }): void;
            function addResource(langCode: string, key: string, value: string): void;
            function langCodeToLcid(langCode: string): number;
            function lcidToLangCode(lcid: number): string;
        }

        // ==================== Util API ====================

        namespace Util {
            // 格式化
            function formatDate(date: Date | string, format?: string): string;
            function formatNumber(num: number, decimals?: number): string;
            function formatCurrency(amount: number, currency?: string): string;
            function format(template: string, data: any): string;

            // 字符串
            function isEmpty(value: any): boolean;
            function generateGuid(): string;
            function isValidGuid(guid: string): boolean;
            function isValidEmail(email: string): boolean;
            function isValidPhone(phone: string): boolean;
            function encodeUri(str: string): string;
            function decodeUri(str: string): string;

            // 对象
            function deepClone(obj: any): any;

            // 异步
            function sleep(ms: number): Promise<void>;
            function retry(fn: () => Promise<any>, times?: number, delay?: number): Promise<any>;
            function debounce(fn: Function, delay: number): Function;
            function throttle(fn: Function, delay: number): Function;

            // FetchXML
            function objectToFetchXml(obj: FetchXmlOptions): string;

            // 日志
            function log(message: string, level?: string): void;
        }

        // ==================== 核心函数 ====================

        function init(executionContext?: any): void;
        function getFormContext(): Xrm.FormContext;
        function getGlobalContext(): Xrm.GlobalContext;
        function isInitialized(): boolean;
        function getVersion(): string;

        // ==================== 链式调用 ====================

        function $(fields: string | string[]): FieldSelector;

        /**
         * 字段选择器类
         */
        class FieldSelector {
            constructor(fields: string[]);
            val(value?: any): any;
            disable(flag?: boolean): FieldSelector;
            enable(): FieldSelector;
            toggle(visible?: boolean): FieldSelector;
            show(): FieldSelector;
            hide(): FieldSelector;
            require(level?: RequiredLevel): FieldSelector;
            optional(): FieldSelector;
            focus(): FieldSelector;
            notify(message: string, level?: NotificationLevel): FieldSelector;
            clearNotify(): FieldSelector;
            attr(): Xrm.Attributes.Attribute<any>;
            ctrl(): Xrm.Controls.Control<any>;
        }

        // ==================== 简写别名 ====================

        var $form: typeof Form;
        var $data: typeof Data;
        var $nav: typeof Nav;
        var $ui: typeof UI;
        var $ctx: typeof Ctx;
        var $util: typeof Util;
    }
}

// ==================== 扩展 Window 接口 ====================

interface Window {
    XRM: {
        Common: typeof XRM.Common;
    };
}
