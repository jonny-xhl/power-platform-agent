# 联系人 (`contact`)

**说明**: 存储联系人信息

**所有权类型**: `UserOwned`

---

## 字段列表

| Schema Name | 显示名称 | 类型 | 必填 | 说明 | 选项集引用 |
|-------------|----------|------|------|------|------------|
| `firstName` | 名 | `String` | 是 | 联系人的名字 |  |
| `lastName` | 姓 | `String` | 是 | 联系人的姓氏 |  |
| `email` | 电子邮件 | `String` | 是 | 主要电子邮件地址 |  |
| `phone` | 电话 | `String` | 否 | 主要电话号码 |  |
| `mobile` | 手机 | `String` | 否 | 手机号码 |  |

## 关系

| 关系名称 | 关联实体 | 关系类型 | 级联删除 |
|----------|----------|----------|----------|
| `contact_account` | `account` | ManyToOne | NoCascade |

---

## 元数据

- **Schema Name**: `contact`
- **源文件**: [`contact.yaml`](../../metadata/tables/contact.yaml)
- **最后更新**: `2026-04-23 01:25:40`