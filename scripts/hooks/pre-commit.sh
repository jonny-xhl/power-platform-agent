#!/bin/bash
# Git pre-commit hook for Power Platform Agent
# 自动更新数据字典 + 文档自律
#
# 功能：
#   1. 检测 metadata/ 变更 → 生成数据字典
#   2. 检测 framework/、config/、.claude/skills/ 变更 → 自动更新文档 (CLAUDE.md, SKILL.md 等)

set -e

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# 确定使用 python 还是 python3
PYTHON_CMD="python3"
if command -v python &> /dev/null; then
    PYTHON_CMD="python"
fi

# 检查 Python 是否可用
if ! command -v "$PYTHON_CMD" &> /dev/null; then
    echo "⚠️  警告: 未找到 Python，跳过所有自动文档更新"
    exit 0
fi

# 获取本次提交涉及的文件
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACMR)

# ==================== 1. 数据字典更新 ====================

META_FILES=$(echo "$STAGED_FILES" | grep -E 'metadata/(tables|optionsets)/.*\.yaml$' || true)

if [ -n "$META_FILES" ]; then
    echo "🔄 检测到元数据变更，正在更新数据字典..."
    echo "$META_FILES" | sed 's/^/  - /'

    FILE_ARGS=$(echo "$META_FILES" | tr '\n' ' ' | sed 's/ $//')

    if $PYTHON_CMD scripts/generate_data_dictionary.py --files $FILE_ARGS; then
        echo "✅ 数据字典已更新"
        git add docs/data_dictionary/
        echo "📝 数据字典已添加到本次提交"
    else
        echo "❌ 数据字典生成失败"
        exit 1
    fi
fi

# ==================== 2. 文档自律更新 ====================

# 检测需要触发文档更新的变更文件
# 匹配规则参考 config/documentation_rules.yaml
DOC_TRIGGER_FILES=$(echo "$STAGED_FILES" | grep -E \
    '^framework/agents/.*\.py$|'\
'^framework/utils/.*\.py$|'\
'^framework/mcp_serve\.py$|'\
'^framework/llm/.*\.py$|'\
'^\.claude/skills/.*\.md$|'\
'^\.claude/skills/.*/scripts/.*\.py$|'\
'^config/.*\.yaml$|'\
'^scripts/.*\.py$' || true)

if [ -z "$DOC_TRIGGER_FILES" ]; then
    exit 0
fi

echo ""
echo "📚 检测到框架/配置/技能变更，正在自动更新文档..."
echo "$DOC_TRIGGER_FILES" | sed 's/^/  - /'

# 调用 update_docs.py 的 suggest 模式
# --mode suggest: 生成 .suggest 建议文件，不直接修改原文档
# --scope staged: 仅分析暂存区变更
# 开发者需要审阅 .suggest 文件后手动应用
if $PYTHON_CMD scripts/update_docs.py --mode suggest --scope staged 2>&1; then
    # 检查是否生成了建议文件
    SUGGEST_FILES=$(find . -name "*.suggest" -maxdepth 4 2>/dev/null || true)
    if [ -n "$SUGGEST_FILES" ]; then
        echo "💡 文档更新建议已生成，请审阅后手动应用："
        echo "$SUGGEST_FILES" | sed 's/^/   /'
        echo ""
        echo "   审阅无误后执行: cp <file>.suggest <file>"
    else
        echo "ℹ️  文档无需更新"
    fi
else
    # 文档更新失败不阻塞提交（可能是 LLM API 未配置）
    echo "⚠️  文档自动更新失败（LLM 可能未配置），请手动运行："
    echo "   python scripts/update_docs.py --mode suggest"
fi

exit 0
