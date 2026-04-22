#!/bin/bash
# Git pre-commit hook for Power Platform Agent
# 自动更新数据字典
#
# 功能：当检测到 metadata/tables/ 或 metadata/optionsets/ 中的 YAML 文件变更时，
# 自动调用 generate_data_dictionary.py 生成对应的数据字典文档

set -e

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# 获取本次提交涉及的元数据文件
# 只关注 .yaml 文件，排除 .git 目录和子模块
CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACMR | grep -E 'metadata/(tables|optionsets)/.*\.yaml$' || true)

if [ -z "$CHANGED_FILES" ]; then
    # 没有元数据变更，直接退出
    exit 0
fi

echo "🔄 检测到元数据变更，正在更新数据字典..."
echo "变更的文件:"
echo "$CHANGED_FILES" | sed 's/^/  - /'

# 检查 Python 是否可用
if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo "⚠️  警告: 未找到 Python，无法自动生成数据字典"
    echo "   请手动运行: python scripts/generate_data_dictionary.py --all"
    exit 0
fi

# 确定使用 python 还是 python3
PYTHON_CMD="python3"
if command -v python &> /dev/null; then
    PYTHON_CMD="python"
fi

# 调用生成脚本
# 将文件列表作为参数传递
FILE_ARGS=$(echo "$CHANGED_FILES" | tr '\n' ' ' | sed 's/ $//')

$PYTHON_CMD scripts/generate_data_dictionary.py --files $FILE_ARGS

if [ $? -eq 0 ]; then
    echo "✅ 数据字典已更新"

    # 将生成的文档添加到本次提交
    git add docs/data_dictionary/

    echo "📝 生成的文档已添加到本次提交"
else
    echo "❌ 数据字典生成失败"
    echo "   请检查错误信息或手动运行: python scripts/generate_data_dictionary.py --all"
    exit 1
fi

exit 0
