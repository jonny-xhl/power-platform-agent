#!/bin/bash
# Power Platform Agent - Run Integration Tests
# 运行集成测试的脚本

set -e  # 遇到错误立即退出

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_ROOT="$PROJECT_ROOT/test"
INTEGRATION_TEST_DIR="$TEST_ROOT/integration"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Power Platform Agent - 运行集成测试"
echo "=========================================="
echo "项目根目录: $PROJECT_ROOT"
echo "集成测试目录: $INTEGRATION_TEST_DIR"
echo ""

# 检查pytest是否安装
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}错误: pytest 未安装${NC}"
    echo "请运行: pip install pytest"
    exit 1
fi

# 检查集成测试目录是否存在
if [ ! -d "$INTEGRATION_TEST_DIR" ]; then
    echo -e "${RED}错误: 集成测试目录不存在: $INTEGRATION_TEST_DIR${NC}"
    exit 1
fi

# 检查环境变量
echo "检查集成测试环境变量..."
if [ -z "$PP_DATAVERSE_URL" ]; then
    echo -e "${YELLOW}⚠ 警告: PP_DATAVERSE_URL 未设置${NC}"
fi
if [ -z "$PP_RUN_AUTH_TESTS" ]; then
    echo -e "${BLUE}ℹ 提示: 设置 PP_RUN_AUTH_TESTS=1 来运行需要认证的测试${NC}"
fi
if [ -z "$PP_RUN_DATAVERSE_TESTS" ]; then
    echo -e "${BLUE}ℹ 提示: 设置 PP_RUN_DATAVERSE_TESTS=1 来运行需要Dataverse的测试${NC}"
fi
echo ""

# 切换到项目根目录
cd "$PROJECT_ROOT"

# 构建pytest命令
PYTEST_CMD="pytest"
PYTEST_CMD="$PYTEST_CMD -v"
PYTEST_CMD="$PYTEST_CMD --tb=short"
PYTEST_CMD="$PYTEST_CMD --strict-markers"
PYTEST_CMD="$PYTEST_CMD -m integration"  # 只运行标记为integration的测试

# 如果传入了参数，使用它们
if [ $# -gt 0 ]; then
    echo "使用自定义参数: $@"
    pytest "$INTEGRATION_TEST_DIR" "$@"
else
    echo "运行命令: $PYTEST_CMD $INTEGRATION_TEST_DIR"
    $PYTEST_CMD "$INTEGRATION_TEST_DIR"
fi

# 检查测试结果
TEST_RESULT=$?

echo ""
if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}=========================================="
    echo "集成测试通过！"
    echo "==========================================${NC}"
else
    echo -e "${RED}=========================================="
    echo "集成测试失败，退出码: $TEST_RESULT"
    echo "==========================================${NC}"
fi

exit $TEST_RESULT
