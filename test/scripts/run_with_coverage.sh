#!/bin/bash
# Power Platform Agent - Run Tests with Coverage
# 运行测试并生成覆盖率报告的脚本

set -e  # 遇到错误立即退出

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_ROOT="$PROJECT_ROOT/test"
COVERAGE_REPORT_DIR="$TEST_ROOT/reports/coverage"
HTML_REPORT_DIR="$TEST_ROOT/reports/html"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Power Platform Agent - 运行测试（含覆盖率）"
echo "=========================================="
echo "项目根目录: $PROJECT_ROOT"
echo "覆盖率报告目录: $COVERAGE_REPORT_DIR"
echo "HTML报告目录: $HTML_REPORT_DIR"
echo ""

# 检查pytest是否安装
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}错误: pytest 未安装${NC}"
    echo "请运行: pip install pytest pytest-cov"
    exit 1
fi

# 检查pytest-cov是否安装
if ! python -c "import pytest_cov" &> /dev/null; then
    echo -e "${YELLOW}警告: pytest-cov 未安装${NC}"
    echo "请运行: pip install pytest-cov"
    echo "尝试继续运行（可能不支持覆盖率报告）..."
fi

# 创建报告目录
mkdir -p "$COVERAGE_REPORT_DIR"
mkdir -p "$HTML_REPORT_DIR"

# 切换到项目根目录
cd "$PROJECT_ROOT"

# 构建pytest命令
PYTEST_CMD="pytest"
PYTEST_CMD="$PYTEST_CMD -v"
PYTEST_CMD="$PYTEST_CMD --tb=short"
PYTEST_CMD="$PYTEST_CMD --strict-markers"
PYTEST_CMD="$PYTEST_CMD -m 'not slow'"

# 添加覆盖率选项
PYTEST_CMD="$PYTEST_CMD --cov=framework"
PYTEST_CMD="$PYTEST_CMD --cov-report=term-missing"
PYTEST_CMD="$PYTEST_CMD --cov-report=html:$COVERAGE_REPORT_DIR"
PYTEST_CMD="$PYTEST_CMD --cov-report=xml:$COVERAGE_REPORT_DIR/coverage.xml"
PYTEST_CMD="$PYTEST_CMD --cov-fail-under=0"  # 不设置最低覆盖率要求

# 添加HTML报告选项
PYTEST_CMD="$PYTEST_CMD --html=$HTML_REPORT_DIR/report.html"
PYTEST_CMD="$PYTEST_CMD --self-contained-html"

echo "运行命令: $PYTEST_CMD $TEST_ROOT"
echo ""

# 运行测试
$PYTEST_CMD "$TEST_ROOT" "$@" || TEST_RESULT=$?

# 检查测试结果
echo ""
if [ ${TEST_RESULT:-0} -eq 0 ]; then
    echo -e "${GREEN}=========================================="
    echo "测试完成！"
    echo "==========================================${NC}"
    echo ""
    echo "报告已生成:"
    echo "  - HTML覆盖率报告: file://$COVERAGE_REPORT_DIR/index.html"
    echo "  - HTML测试报告: file://$HTML_REPORT_DIR/report.html"
    echo ""

    # 尝试自动打开报告（仅在支持的系统上）
    if command -v xdg-open &> /dev/null; then
        echo "尝试打开覆盖率报告..."
        xdg-open "$COVERAGE_REPORT_DIR/index.html" &> /dev/null || true
    elif command -v open &> /dev/null; then
        echo "尝试打开覆盖率报告..."
        open "$COVERAGE_REPORT_DIR/index.html" &> /dev/null || true
    fi
else
    echo -e "${RED}=========================================="
    echo "测试失败，退出码: ${TEST_RESULT:-0}"
    echo "==========================================${NC}"
fi

exit ${TEST_RESULT:-0}
