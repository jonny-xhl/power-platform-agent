---
name: dv-role-python
description: 用 framework_power（Python 优先）为已存在的 Dataverse 安全角色（Security Role）同步/逆向表级权限（privilege × depth）。当用户需要"给角色分配表权限"、"角色权限同步"、"逆向角色权限"、按表范围导出角色权限时使用此技能。短语如"framework_power role deploy/reverse"、"metadata_py/roles"、"角色权限"。
---

# Dataverse 安全角色权限管理（Python 优先 / framework_power）

本技能是 **framework_power** 的**安全角色表权限**管理入口（Phase 3），与表（Phase 1）、
解决方案（Phase 2）并列。

## 是什么 / 不是什么

- **角色不在本项目创建** —— 角色在环境中手动建好；本技能为**已存在的角色**同步其
  **表级权限**（哪个表的哪种 right、给到什么 depth）。
- **正向 `role deploy`**：把本地定义的权限（right × depth）**upsert** 到环境中的角色
  （非破坏：只加/改定义里列出的权限，未列出的不动）。
- **逆向 `role reverse --tables`**：把环境中角色的权限按**指定的表范围**导出为本地定义。
  `--tables` 必填（拒绝拉取全环境表）。

## 权限模型（已 live 验证）

- 权限（privilege）按名寻址：`prv<Right><EntitySchemaName>`，如 `prvReadnew_FpSmokeA`
  （用实体 **SchemaName**，非小写 logical name）。
- 角色↔权限的关联是 `roleprivilegescollection` 记录，深度存于位掩码字段
  **`privilegedepthmask`**（不是 `depth`）。
- **AccessRight**（`privilege.accessright`）：Read=1、Write=2、Append=4、AppendTo=16、
  Create=32、Delete=65536、Share=262144、Assign=524288。
- **PrivilegeDepth**（`privilegedepthmask` 位掩码）：USER=1、BUSINESS_UNIT=2、
  PARENT_CHILD=4、GLOBAL=8。"无权限"= 该 roleprivilege 记录不存在。
- 关键：`objecttypecode` 在 `privilege`/`roleprivilegescollection` 上**不可过滤**；
  按表范围逆向 = 先解析每张表的 8 个 privilegeid（按名），再用 `privilegeid` 服务端过滤
  `roleprivilegescollection`。

## 定义文件

`metadata_py/roles/<name>.py`，导出 `ROLE: SecurityRole`：

```python
from framework_power import AccessRight, PrivilegeDepth, SecurityRole, TablePrivilege

ROLE: SecurityRole = SecurityRole(
    name="Basic User",  # 必须已存在于环境
    table_privileges=[
        TablePrivilege(
            table="new_fpsmokea",
            rights={
                AccessRight.READ: PrivilegeDepth.USER,
                AccessRight.WRITE: PrivilegeDepth.BUSINESS_UNIT,
                AccessRight.CREATE: PrivilegeDepth.USER,
            },
        ),
    ],
)
```

## CLI

```bash
python -m framework_power role list                          # 发现 metadata_py/roles/*.py
python -m framework_power role show <name>                   # 打印定义（离线）
python -m framework_power role lint [<name>]                 # 离线约定校验
python -m framework_power role plan <name> --env dev         # 只读预演
python -m framework_power role deploy <name> --env dev       # upsert 权限（非破坏）
python -m framework_power role reverse <name> --tables a,b,c --env dev  # 逆向（--tables 必填）
# 全局参数：--roles-dir <dir>（默认 metadata_py/roles）
```

## 工作流

```
角色在环境中手动创建好
  → metadata_py/roles/<name>.py（声明该角色对哪些表、哪些 right、什么 depth）
  → framework_power role lint     （离线门）
  → framework_power role plan     （只读预演）
  → framework_power role deploy   （upsert 到环境）
逆向参考：framework_power role reverse <name> --tables a,b   （环境 → 本地，按表范围）
```

## 硬性约束

- 角色必须已存在；`deploy` 遇到缺失角色会报错（不创建）。
- `deploy` 非破坏：只加/改定义中列出的权限；未列出的 right 不动（要收回需另行显式处理）。
- `reverse --tables` 必填；省略则报错（拒绝拉取全环境）。
- 标准（非 `new_` 前缀）表的权限在 `deploy` 时跳过（参考用）。
- `True`/`False`（Python），不要 `true`/`false`。

## 不要做

- 不要在本工具内创建或删除角色实体（角色手动管理）。
- 不要假设 `roleprivilegescollection` 有 `depth`/`objecttypecode` 字段（实际是
  `privilegedepthmask`；按 `privilegeid` 过滤）。
- 不要在 `reverse` 不给 `--tables` 时拉取全部表。
