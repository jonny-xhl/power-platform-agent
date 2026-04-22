#!/bin/bash
# Git hooks 安装脚本
#
# 功能：将 scripts/hooks/ 中的 hook 文件安装到 .git/hooks/

set -e

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_SOURCE="$PROJECT_ROOT/scripts/hooks"
HOOKS_TARGET="$PROJECT_ROOT/.git/hooks"

echo "🔧 正在安装 Git hooks..."

# 检查 .git 目录是否存在
if [ ! -d "$PROJECT_ROOT/.git" ]; then
    echo "❌ 错误: 未找到 .git 目录"
    echo "   请确保在 Git 仓库根目录运行此脚本"
    exit 1
fi

# 确保 hooks 目录存在
mkdir -p "$HOOKS_TARGET"

# 安装 pre-commit hook
if [ -f "$HOOKS_SOURCE/pre-commit.sh" ]; then
    cp "$HOOKS_SOURCE/pre-commit.sh" "$HOOKS_TARGET/pre-commit"
    chmod +x "$HOOKS_TARGET/pre-commit"
    echo "  ✓ pre-commit hook 已安装"
else
    echo "  ⚠️  警告: 未找到 pre-commit.sh"
fi

# 安装其他 hooks (可根据需要扩展)
# if [ -f "$HOOKS_SOURCE/pre-push.sh" ]; then
#     cp "$HOOKS_SOURCE/pre-push.sh" "$HOOKS_TARGET/pre-push"
#     chmod +x "$HOOKS_TARGET/pre-push"
#     echo "  ✓ pre-push hook 已安装"
# fi

echo ""
echo "✅ Git hooks 安装完成!"
echo ""
echo "已安装的 hooks:"
ls -1 "$HOOKS_TARGET" | grep -v '\.sample$' | sed 's/^/  - /'
echo ""
echo "提示: 如需禁用 hook，可删除 .git/hooks/ 中的对应文件"
