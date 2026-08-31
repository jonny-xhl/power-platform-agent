#!/bin/bash
# Git pre-commit hook for Power Platform Agent (framework_power)
# 文档自律：引擎代码/技能变更时给出建议级提醒（不阻塞提交）
#
# 注：数据字典由 `pp reverse <table> --env <env> --dictionary` 按环境生成
# （workspace 产物，不入本仓库）；本 hook 只做文档同步提醒。

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACMR)

# 需要触发文档更新提醒的变更文件（引擎/技能/配置）
DOC_TRIGGER_FILES=$(echo "$STAGED_FILES" | grep -E \
    '^framework_power/.*\.py$|'\
'^\.claude/skills/.*\.md$|'\
'^\.claude/skills/.*/scripts/.*\.py$|'\
'^scripts/.*\.py$' || true)

if [ -z "$DOC_TRIGGER_FILES" ]; then
    exit 0
fi

echo ""
echo "📚 检测到引擎/技能变更（建议级提醒，不阻塞提交）："
echo "$DOC_TRIGGER_FILES" | sed 's/^/  - /'
echo ""
echo "   按《文档同步守则》(CLAUDE.md) 自查本次变更是否需要同步："
echo "   ① 新决策/行为 → 新 ADR 或增补现有 ADR（docs/spec/adr-*.md）"
echo "   ② 架构 → docs/spec/architecture.md"
echo "   ③ 作者契约 → docs/spec/metadata-spec.md"
echo "   ④ 部署语义 → docs/guides/metadata-deploy.md"
echo "   ⑤ 使用说明 → 对应 .claude/skills/*/skill.md"
echo "   ⑥ 概览/踩坑 → CLAUDE.md / framework_power/CLAUDE.md"
echo ""

exit 0
