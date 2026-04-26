#!/usr/bin/env python3
"""
Power Platform Agent - Test Isolation Verification Script
围栏验证脚本，确保测试文件都在test目录下

This script verifies that all test-related files are properly contained
within the test/ directory structure, preventing scattered test files.
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple, Set


# =============================================================================
# 配置
# =============================================================================

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 允许的测试文件位置
ALLOWED_TEST_DIRS = {
    PROJECT_ROOT / "test",
}

# 测试文件模式
TEST_FILE_PATTERNS = [
    re.compile(r"^test_.*\.py$"),      # test_*.py
    re.compile(r"^.*_test\.py$"),      # *_test.py
    re.compile(r"^conftest\.py$"),     # conftest.py
]

# 允许在根目录的测试相关文件
ROOT_WHITELIST = [
    "pytest.ini",
    "pyproject.toml",
    "setup.cfg",
    "tox.ini",
    ".coveragerc",
    # 构建和安装脚本
    "setup.py",
    "build_and_validate.py",
]

# 需要检查的测试模式（在代码中）
TEST_IMPORT_PATTERNS = [
    re.compile(r"import\s+pytest"),
    re.compile(r"from\s+pytest\s+import"),
    re.compile(r"import\s+unittest"),
    re.compile(r"from\s+unittest\s+import"),
    re.compile(r"@pytest\."),
    re.compile(r"@patch\("),
    re.compile(r"@mock\("),
]


# =============================================================================
# 工具函数
# =============================================================================

def is_test_file(file_path: Path) -> bool:
    """
    判断文件是否为测试文件

    Args:
        file_path: 文件路径

    Returns:
        是否为测试文件
    """
    if not file_path.is_file() or file_path.suffix != ".py":
        return False

    filename = file_path.name

    # 检查文件名模式
    for pattern in TEST_FILE_PATTERNS:
        if pattern.match(filename):
            return True

    # 检查文件内容
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")

        # 检查是否包含测试相关的导入或装饰器
        for pattern in TEST_IMPORT_PATTERNS:
            if pattern.search(content):
                return True

        # 检查是否继承自测试类
        if "unittest.TestCase" in content or "pytest" in content:
            return True

    except Exception:
        pass

    return False


def is_in_allowed_test_dir(file_path: Path) -> bool:
    """
    判断文件是否在允许的测试目录中

    Args:
        file_path: 文件路径

    Returns:
        是否在允许的测试目录中
    """
    for allowed_dir in ALLOWED_TEST_DIRS:
        try:
            file_path.relative_to(allowed_dir)
            return True
        except ValueError:
            continue
    return False


def is_whitelisted(file_path: Path, project_root: Path) -> bool:
    """
    判断文件是否在白名单中

    Args:
        file_path: 文件路径
        project_root: 项目根目录

    Returns:
        是否在白名单中
    """
    try:
        rel_path = file_path.relative_to(project_root)
        # 检查是否为根目录的白名单文件
        if rel_path.name in ROOT_WHITELIST or str(rel_path) in ROOT_WHITELIST:
            return True
        # 检查是否在.git目录中
        if ".git" in rel_path.parts or ".github" in rel_path.parts:
            return True
    except ValueError:
        pass
    return False


def find_violations(project_root: Path) -> Dict[str, List[Path]]:
    """
    查找违反测试隔离规则的文件

    Args:
        project_root: 项目根目录

    Returns:
        违规文件字典，按类型分组
    """
    violations = {
        "test_files_outside_test_dir": [],
        "test_configs_outside_test_dir": [],
        "potential_test_files": [],
    }

    # 排除的目录
    exclude_dirs = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".tox",
        "dist",
        "build",
        ".eggs",
        "*.egg-info",
        ".pytest_cache",
        ".mypy_cache",
        ".idea",
        ".vscode",
    }

    # 遍历项目目录
    for item in project_root.rglob("*.py"):
        # 跳过测试目录内的文件
        if item.is_relative_to(project_root / "test"):
            continue

        # 跳过排除的目录
        if any(excluded in item.parts for excluded in exclude_dirs):
            continue

        # 跳过白名单文件
        if is_whitelisted(item, project_root):
            continue

        # 检查是否为测试文件
        if is_test_file(item):
            violations["test_files_outside_test_dir"].append(item)

        # 检查是否为测试配置文件
        if item.name in ["conftest.py", "pytest.ini"]:
            violations["test_configs_outside_test_dir"].append(item)

    # 检查根目录的测试配置文件
    for item in project_root.iterdir():
        if item.name in ["pytest.ini", "pyproject.toml", "setup.cfg"]:
            if not item.is_relative_to(project_root / "test"):
                # 这些文件在根目录是允许的，但记录下来
                violations["test_configs_outside_test_dir"].append(item)

    return violations


def check_test_imports_outside_tests(project_root: Path) -> List[Path]:
    """
    检查在非测试文件中导入测试模块的情况

    Args:
        project_root: 项目根目录

    Returns:
        违规文件列表
    """
    violations = []

    # 要检查的源代码目录
    source_dirs = [
        project_root / "framework",
        project_root / "plugins",
        project_root / "extensions",
        project_root / "scripts",
    ]

    test_modules = {"pytest", "unittest", "mock", "fixtures"}

    for source_dir in source_dirs:
        if not source_dir.exists():
            continue

        for item in source_dir.rglob("*.py"):
            try:
                content = item.read_text(encoding="utf-8", errors="ignore")

                # 检查是否导入测试模块
                for module in test_modules:
                    if f"import {module}" in content or f"from {module}" in content:
                        violations.append(item)
                        break

            except Exception:
                pass

    return violations


def check_temp_files_scattered(project_root: Path) -> List[Path]:
    """
    检查散落在各处的临时文件

    Args:
        project_root: 项目根目录

    Returns:
        临时文件列表
    """
    temp_files = []

    # 临时文件模式
    temp_patterns = ["*.tmp", "*.temp", "temp_*", "tmp_*"]

    for pattern in temp_patterns:
        for item in project_root.glob(pattern):
            # 排除test/temp目录
            if not item.is_relative_to(project_root / "test" / "temp"):
                # 排除其他允许的临时目录
                if not any(excluded in str(item) for excluded in [".git", ".pytest_cache", "node_modules"]):
                    temp_files.append(item)

    return temp_files


def format_violations_report(violations: Dict[str, List[Path]], project_root: Path) -> str:
    """
    格式化违规报告

    Args:
        violations: 违规文件字典
        project_root: 项目根目录

    Returns:
        格式化的报告字符串
    """
    lines = []
    lines.append("=" * 70)
    lines.append("测试隔离验证报告")
    lines.append("=" * 70)
    lines.append(f"项目根目录: {project_root}")
    lines.append("")

    total_violations = sum(len(files) for files in violations.values())

    if total_violations == 0:
        lines.append("[OK] 未发现违规项！所有测试文件都正确放置在 test/ 目录下。")
        lines.append("")
        return "\n".join(lines)

    # 报告违规项
    for category, files in violations.items():
        if not files:
            continue

        category_name = {
            "test_files_outside_test_dir": "测试文件在 test/ 目录外",
            "test_configs_outside_test_dir": "测试配置文件在 test/ 目录外",
            "potential_test_files": "疑似测试文件",
        }.get(category, category)

        lines.append(f"[!] {category_name}: {len(files)} 个文件")

        for file_path in files:
            try:
                rel_path = file_path.relative_to(project_root)
            except ValueError:
                rel_path = file_path
            lines.append(f"  - {rel_path}")

        lines.append("")

    return "\n".join(lines)


def main() -> int:
    """主函数"""
    import sys

    # 设置标准输出编码为UTF-8
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    print("=" * 70)
    print("Power Platform Agent - 测试隔离验证")
    print("=" * 70)
    print()

    # 查找违规文件
    violations = find_violations(PROJECT_ROOT)

    # 检查测试导入
    test_import_violations = check_test_imports_outside_tests(PROJECT_ROOT)
    if test_import_violations:
        violations["test_imports_in_source"] = test_import_violations

    # 检查临时文件
    temp_file_violations = check_temp_files_scattered(PROJECT_ROOT)
    if temp_file_violations:
        violations["temp_files_scattered"] = temp_file_violations

    # 生成报告
    report = format_violations_report(violations, PROJECT_ROOT)
    print(report)

    # 检查是否有违规
    total_violations = sum(len(files) for files in violations.values())

    if total_violations == 0:
        print("[OK] 测试隔离验证通过！")
        return 0
    else:
        print(f"[WARNING] 发现 {total_violations} 个违规项，请修复后重试。")
        print()
        print("建议:")
        print("  1. 将测试文件移动到 test/unit/ 或 test/integration/ 目录")
        print("  2. 将 conftest.py 放置在 test/ 目录或其子目录")
        print("  3. 避免在源代码中导入测试模块")
        print("  4. 清理散落的临时文件")
        return 1


if __name__ == "__main__":
    sys.exit(main())
