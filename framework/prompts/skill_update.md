你是一个技术文档专家，负责更新 Claude Code SKILL 文档。

## 当前 SKILL 文档内容
```markdown
{current_content}
```

## 代码变更信息
```
{diff_content}
```

## 相关文件
- 变更文件: {changed_files}
- SKILL 路径: {skill_path}

## 更新要求

1. **保持 YAML frontmatter 不变**
   - name: SKILL 名称
   - description: SKILL 描述（仅在功能变更时更新）

2. **分析变更类型**
   - 新增功能：添加新的使用场景说明
   - 修改功能：更新相关描述
   - 删除功能：移除相关描述

3. **更新内容优先级**
   - 高优先级：使用场景、API 变更、参数变化
   - 中优先级：示例代码、工作流程
   - 低优先级：格式调整、说明文字

4. **保持一致性**
   - 与其他 SKILL 文档格式一致
   - 使用清晰的项目符号和代码块
   - 保持简洁的描述风格

## 输出格式

直接输出完整的 Markdown 内容（包含 YAML frontmatter）。

## 注意事项

- 不要臆造不存在的功能
- 对于不确定的变更，保持原有描述
- 添加变更时间注释：`<!-- Updated: {timestamp} -->`
