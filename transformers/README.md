# Transformers 转换器层

本层用于将源文件（Excel/Markdown/Word/PPT）转换为元数据 YAML。

## 当前状态

**保留架构，暂不实现具体转换代码。**

开发人员使用 LLM/SKILL 辅助转换。

## 转换流程

```
源文件 → [LLM/SKILL] → YAML 元数据
```

## 未来扩展方向

当需要自动化转换时，在此目录下实现具体转换脚本：

- `excel_to_yaml.py` - Excel 表定义转 YAML
- `markdown_to_yaml.py` - Markdown 文档转 YAML
- `word_to_yaml.py` - Word BRD/PRD 转 YAML
- `ppt_to_yaml.py` - PPT 流程图转 YAML

## 使用建议

1. 手动将源文件内容复制给 LLM
2. 要求 LLM 按照对应 Schema 生成 YAML
3. 将生成的 YAML 保存到 `metadata/` 目录
4. 运行验证脚本确保格式正确
