# 客户账户 (`account`)

**说明**: 存储客户账户信息，包括账户编号、余额和状态

**所有权类型**: `UserOwned`

---

## 字段列表

| Schema Name | 显示名称 | 类型 | 必填 | 说明 | 选项集引用 |
|-------------|----------|------|------|------|------------|
| `accountNumber` | 账户编号 | `String` | 是 | 唯一账户编号 |  |
| `accountName` | 账户名称 | `String` | 是 | 账户名称 |  |
| `balance` | 账户余额 | `Money` | 否 | 当前账户余额 |  |
| `status` | 状态 | `Picklist` | 是 | 账户状态\n选项: 活跃(100000000), 冻结(100000001), 关闭(100000002) | 本地选项集 |
| `accountType` | 账户类型 | `Picklist` | 否 | 客户账户类型\n选项: 个人(100000000), 企业(100000001), 政府(100000002) | 本地选项集 |
| `creditLimit` | 信用额度 | `Money` | 否 | 客户信用额度 |  |
| `openedDate` | 开户日期 | `DateTime` | 否 | 账户开立日期 |  |
| `notes` | 备注 | `Memo` | 否 | 账户备注信息 |  |

## 关系

| 关系名称 | 关联实体 | 关系类型 | 级联删除 |
|----------|----------|----------|----------|
| `account_contact` | `contact` | OneToMany | RemoveLink |
| `primary_contact` | `contact` | ManyToOne | NoCascade |
| `account_product` | `product` | ManyToMany | NoCascade |

---

## 元数据

- **Schema Name**: `account`
- **源文件**: [`account.yaml`](../../metadata/tables/account.yaml)
- **最后更新**: `2026-04-23 01:25:40`