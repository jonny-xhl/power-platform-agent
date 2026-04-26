#!/bin/bash
# Power Platform Agent - Run All Tests
# 运行所有测试的脚本

set -e  # 遇到错误立即退出

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_ROOT="$PROJECT_ROOT/test"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Power Platform Agent - 运行所有测试"
echo "=========================================="
echo "项目根目录: $PROJECT_ROOT"
echo "测试目录: $TEST_ROOT"
echo ""

# 检查pytest是否安装
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}错误: pytest 未安装${NC}"
    echo "请运行: pip install pytest"
    exit 1
fi

# 切换到项目根目录
cd "$PROJECT_ROOT"

# 运行测试前的验证
echo "1. 验证测试隔离性..."
if python "$TEST_ROOT/scripts/verify_test_isolation.py"; then
    echo -e "${GREEN}✓ 测试隔离验证通过${NC}"
else
    echo -e "${YELLOW}⚠ 测试隔离验证发现问题，但继续运行测试${NC}"
fi

echo ""
echo "2. 运行测试套件..."

# 构建pytest命令
PYTEST_CMD="pytest"

# 添加命令行参数
PYTEST_CMD="$PYTEST_CMD -v"
PYTEST_CMD="$PYTEST_CMD --tb=short"
PYTEST_CMD="$PYTEST_CMD --strict-markers"
PYTEST_CMD="$PYTEST_CMD -m 'not slow'"  # 默认跳过慢速测试

# 如果传入了参数，使用它们
if [ $# -gt 0 ]; then
    echo "使用自定义参数: $@"
    pytest "$TEST_ROOT" "$@"
else
    echo "运行命令: $PYTEST_CMD $TEST_ROOT"
    $PYTEST_CMD "$TEST_ROOT"
fi

# 检查测试结果
TEST_RESULT=$?

echo ""
if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}=========================================="
    echo "所有测试通过！"
    echo "==========================================${NC}"
else
    echo -e "${RED}=========================================="
    echo "测试失败，退出码: $TEST_RESULT"
    echo "==========================================${NC}"
fi

exit $TEST_RESULT
