# 源文件模板目录

本目录存放各种格式的元数据定义模板，用于业务分析师编写需求文档。

## 目录结构

```
templates/
├── excel/           # Excel 模板
│   ├── table_definition_template.xlsx
│   ├── form_design_template.xlsx
│   └── view_design_template.xlsx
├── markdown/        # Markdown 模板
├── word/            # Word 模板
│   ├── brd_template.docx
│   └── prd_template.docx
└── ppt/             # PowerPoint 模板
    └── business_flow_template.pptx
```

## 使用说明

1. **Excel 模板**: 用于定义表结构、表单设计、视图设计
2. **Word 模板**: 用于编写业务需求文档(BRD)和产品需求文档(PRD)
3. **PPT 模板**: 用于绘制业务流程图
4. **Markdown 模板**: 用于轻量级文档编写

## 模板命名规范

- 使用 `template` 后缀标识模板文件
- 使用下划线分隔多个单词
- 使用英文命名，便于版本控制

## 贡献模板

新增模板时，请在此 README 中更新目录结构说明。
