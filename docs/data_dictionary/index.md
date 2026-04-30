# 数据字典索引

*自动生成于: 2026-04-30 10:38:35*

---

## 表 (Tables)

| 表名 | Schema Name | 字段数 | 最后更新 | 说明 |
|------|-------------|--------|----------|------|
| [客户账户](tables/account.md) | `account` | 7 | 2026-04-30 | 存储客户账户信息，包括账户编号、余额和状态 |
| [联系人](tables/contact.md) | `contact` | 3 | 2026-04-30 | 存储联系人信息 |
| [客户地址](tables/new_customer_address.md) | `new_customer_address` | 12 | 2026-04-30 | 记录客户的地址信息，支持审批流程和多级区域管理 |
| [认款单](tables/new_payment_recognition.md) | `new_payment_recognition` | 16 | 2026-04-30 | 记录客户认款信息，关联订单、发票和客户，支持审批流程 |

## 选项集 (Option Sets)

| 选项集 | Schema Name | 类型 | 选项数量 |
|--------|-------------|------|----------|
| [客户状态](optionsets/new_customer_status.md) | `new_customer_status` | 全局 | 4 |
| [付款条件](optionsets/new_payment_terms.md) | `new_payment_terms` | 全局 | 4 |
| [订单状态](optionsets/new_order_status.md) | `new_order_status` | 全局 | 5 |
| [优先级](optionsets/new_priority.md) | `new_priority` | 全局 | 4 |
| [是否](optionsets/new_yes_no.md) | `new_yes_no` | 全局 | 2 |

---

## 快速导航

- [所有表结构](all_tables.md) - 完整的表结构列表
- [所有选项集](all_optionsets.md) - 完整的选项集定义
