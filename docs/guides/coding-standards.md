# Power Platform 开发规范

本文档是开发规范的索引，定义了项目中各类代码的开发标准。详细规范请参考各专项文档。

---

## 规范文档索引

### 前端资源

| 文档 | 适用范围 |
|------|---------|
| [webresource-development.md](./webresource-development.md) | JavaScript / CSS / HTML WebResource 开发规范 |
| [backend-development.md](./backend-development.md) | Dataverse 后端开发规范 |
| [metadata-spec.md](../spec/metadata-spec.md) | 元数据定义规范（含 Python API 编写约定） |

---

## 快速参考

### WebResource 关键规范

- 使用 IIFE 封装 + `'use strict'`
- 优先使用 `XRM.Common` 封装
- Ribbon 函数注意参数顺序
- OnSave 使用异步确认模式

### C# 插件关键规范

- 目标框架 `net462` 或 `net471`
- 使用 NuGet 包引用
- 始终记录 ITracingService
- 安全访问参数（先检查 Contains）

---

## 相关文档

- [webresource-development.md](./webresource-development.md) - WebResource 详细规范
- [backend-development.md](./backend-development.md) - Dataverse 后端详细规范
- [metadata-spec.md](../spec/metadata-spec.md) - 元数据定义规范（含 Python API 编写约定）
- [CLAUDE.md](../../CLAUDE.md) - 项目整体说明
