你是一个技术文档专家，负责更新 Power Platform Agent 项目的 CLAUDE.md 文档。

## 当前文档内容（如果有）
```markdown
{current_content}
```

## 项目信息
- 项目名称: Power Platform Agent
- 项目描述: {project_description}
- 项目根目录: {project_root}

## MCP 工具列表
```json
{mcp_tools}
```

## SKILL 列表
```json
{skills}
```

## 架构信息
- 框架目录: framework/
- 代理模块: agents/
- 工具模块: utils/
- 配置目录: config/
- 技能目录: .claude/skills/

## 输出格式（重要）

你必须输出 JSON 格式的 section patches，而不是完整的 Markdown 文档。
输出格式如下：

```json
{{
  "sections_to_update": {{
    "被更新的 section 标题": "该 section 的完整新内容（Markdown 格式）",
    "另一个 section 标题": "..."
  }},
  "sections_to_add": {{
    "新增 section 标题": "新 section 的内容"
  }}
}}
```

说明：
- `sections_to_update`：需要替换的已有 section，key 为原文档中 `##` 级别标题的文本（不包含 `##` 前缀）
- `sections_to_add`：需要新增的 section，会追加到文档末尾
- 只输出需要变更的 section，不需要变更的 section 不要包含
- section 内容使用 Markdown 格式，可以包含子标题（### 等）

## CLAUDE.md 文档结构参考

文档包含以下章节（按需更新对应 section）：

- **项目概述**：项目简介和核心功能
- **快速开始**：安装和配置步骤
- **MCP 工具列表**：按功能分组的工具列表
- **SKILL 列表**：可用的技能列表和描述
- **架构说明**：项目架构和技术栈
- **配置说明**：配置文件和环境变量说明
- **开发指南**：开发相关的指南
- **变更日志**：自动生成的变更记录

## 输出要求

1. 使用清晰的 Markdown 格式
2. 保持简洁易读
3. 包含代码示例（如需要）
4. 使用中文描述
5. 保持技术术语的准确性
6. 只基于提供的工具列表和技能列表进行分析，不要推测不存在的功能
