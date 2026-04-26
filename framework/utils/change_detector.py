"""
Change Detector - 代码变更检测器

通过 Git diff 检测代码变更，判断是否为有意义变更
"""

import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
# from typing import Optional  # Not needed in Python 3.10+


class ChangeType(Enum):
    """变更类型"""
    ADDED = "A"
    MODIFIED = "M"
    DELETED = "D"
    RENAMED = "R"
    COPIED = "C"


class Significance(Enum):
    """变更重要性"""
    HIGH = "high"       # 重要变更 - 影响 API 或核心逻辑
    MEDIUM = "medium"   # 中等变更 - 影响文档或配置
    LOW = "low"         # 低优先级 - 仅注释或格式
    INSIGNIFICANT = "insignificant"  # 无意义变更 - 仅空白字符


@dataclass
class ChangedFile:
    """变更文件"""
    path: str
    change_type: ChangeType
    significance: Significance = Significance.MEDIUM
    diff_content: str = ""
    stats: dict = field(default_factory=dict)

    @property
    def extension(self) -> str:
        """文件扩展名"""
        return Path(self.path).suffix

    @property
    def is_python(self) -> bool:
        """是否为 Python 文件"""
        return self.extension == ".py"

    @property
    def is_yaml(self) -> bool:
        """是否为 YAML 文件"""
        return self.extension in {".yaml", ".yml"}

    @property
    def is_markdown(self) -> bool:
        """是否为 Markdown 文件"""
        return self.extension in {".md", ".markdown"}


@dataclass
class ChangeReport:
    """变更报告"""
    files: list[ChangedFile] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    commit_hash: str | None = None
    commit_message: str | None = None

    @property
    def significant_files(self) -> list[ChangedFile]:
        """有意义变更的文件"""
        return [f for f in self.files if f.significance != Significance.INSIGNIFICANT]

    @property
    def python_files(self) -> list[ChangedFile]:
        """Python 文件变更"""
        return [f for f in self.files if f.is_python]

    @property
    def yaml_files(self) -> list[ChangedFile]:
        """YAML 文件变更"""
        return [f for f in self.files if f.is_yaml]


class ChangeDetector:
    """变更检测器"""

    # 无意义变更模式
    WHITESPACE_PATTERNS = [
        r'^\s*$',                    # 仅空白行
        r'^\s*#.*$',                 # 仅注释
        r'^\s*"""[\s\S]*?"""',       # 文档字符串
        r"^\s*'''[\s\S]*?'''",       # 文档字符串
    ]

    # 排除的目录模式
    EXCLUDED_DIRS = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        ".venv",
        "venv",
        "env",
        ".tox",
        "dist",
        "build",
        "*.egg-info",
    }

    # 排除的文件模式
    EXCLUDED_PATTERNS = [
        "*.log",
        "*.tmp",
        "*.cache",
        "*.pyc",
        "*.pyo",
        ".DS_Store",
        "Thumbs.db",
    ]

    def __init__(
        self,
        repo_root: Path = None,
        excluded_dirs: set[str] = None,
        excluded_patterns: set[str] = None
    ):
        """
        初始化变更检测器

        Args:
            repo_root: 仓库根目录
            excluded_dirs: 排除的目录
            excluded_patterns: 排除的文件模式
        """
        self.repo_root = repo_root or self._find_repo_root()
        self.excluded_dirs = excluded_dirs or self.EXCLUDED_DIRS.copy()
        self.excluded_patterns = excluded_patterns or self.EXCLUDED_PATTERNS.copy()

    def _find_repo_root(self) -> Path:
        """查找 Git 仓库根目录"""
        path = Path.cwd()
        while path != path.parent:
            if (path / ".git").exists():
                return path
            path = path.parent
        return Path.cwd()

    def _is_excluded(self, file_path: str) -> bool:
        """判断文件是否被排除"""
        path = Path(file_path)

        # 检查目录
        for part in path.parts:
            for pattern in self.excluded_dirs:
                if fnmatch(part, pattern):
                    return True

        # 检查文件名模式
        for pattern in self.excluded_patterns:
            if fnmatch(path.name, pattern) or fnmatch(str(path), pattern):
                return True

        return False

    def get_staged_changes(self) -> ChangeReport:
        """
        获取暂存区的变更

        Returns:
            变更报告
        """
        return self._get_changes("--cached")

    def get_unstaged_changes(self) -> ChangeReport:
        """
        获取工作区的变更

        Returns:
            变更报告
        """
        return self._get_changes("--no-diff-index")

    def get_head_changes(self, commit: str = None) -> ChangeReport:
        """
        获取与指定提交的差异

        Args:
            commit: 目标提交，默认为 HEAD

        Returns:
            变更报告
        """
        if commit is None:
            commit = "HEAD"
        return self._get_changes(f"{commit}^..{commit}")

    def _get_changes(self, diff_spec: str) -> ChangeReport:
        """
        获取变更

        Args:
            diff_spec: diff 规范

        Returns:
            变更报告
        """
        report = ChangeReport()

        # 获取变更文件列表
        try:
            result = subprocess.run(
                ["git", "diff", "--name-status", diff_spec],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True
            )
            output = result.stdout
        except subprocess.CalledProcessError:
            return report

        # 获取当前提交信息
        try:
            commit_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True
            )
            report.commit_hash = commit_result.stdout.strip()
        except subprocess.CalledProcessError:
            pass

        try:
            msg_result = subprocess.run(
                ["git", "log", "-1", "--pretty=%B"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True
            )
            report.commit_message = msg_result.stdout.strip()
        except subprocess.CalledProcessError:
            pass

        # 解析变更文件
        for line in output.strip().split("\n"):
            if not line:
                continue

            parts = line.split("\t", 1)
            if len(parts) < 2:
                continue

            status_char, file_path = parts
            change_type = ChangeType(status_char[0])

            # 跳过排除的文件
            if self._is_excluded(file_path):
                continue

            # 获取 diff 内容
            diff_content = self._get_file_diff(file_path, diff_spec)

            # 分析变更重要性
            significance = self._analyze_significance(file_path, diff_content)

            changed_file = ChangedFile(
                path=file_path,
                change_type=change_type,
                significance=significance,
                diff_content=diff_content,
                stats=self._parse_file_stats(diff_content)
            )

            report.files.append(changed_file)

        return report

    def _get_file_diff(self, file_path: str, diff_spec: str) -> str:
        """
        获取文件的 diff 内容

        Args:
            file_path: 文件路径
            diff_spec: diff 规范

        Returns:
            diff 内容
        """
        try:
            result = subprocess.run(
                ["git", "diff", diff_spec, "--", file_path],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError:
            return ""

    def _parse_file_stats(self, diff_content: str) -> dict:
        """
        解析文件变更统计

        Args:
            diff_content: diff 内容

        Returns:
            统计信息
        """
        stats = {
            "additions": 0,
            "deletions": 0,
            "changes": 0
        }

        for line in diff_content.split("\n"):
            if line.startswith("+") and not line.startswith("+++"):
                stats["additions"] += 1
            elif line.startswith("-") and not line.startswith("---"):
                stats["deletions"] += 1

        stats["changes"] = stats["additions"] + stats["deletions"]
        return stats

    def _analyze_significance(self, file_path: str, diff_content: str) -> Significance:
        """
        分析变更重要性

        Args:
            file_path: 文件路径
            diff_content: diff 内容

        Returns:
            重要性级别
        """
        if not diff_content:
            return Significance.INSIGNIFICANT

        # 关键文件路径
        high_importance_paths = [
            "framework/mcp_serve.py",
            "framework/agents/",
            ".claude/skills/",
            "config/",
        ]

        for pattern in high_importance_paths:
            if pattern in file_path:
                return Significance.HIGH

        # 分析 diff 内容
        meaningful_changes = 0
        whitespace_only = True

        for line in diff_content.split("\n"):
            if not line.startswith(("+", "-", "@@")):
                continue

            # 跳过 diff 头部
            if line.startswith(("+++", "---", "@@")):
                continue

            # 检查是否为有意义的变更
            stripped = line[1:].strip()

            # 空行
            if not stripped:
                continue

            # 注释行
            if stripped.startswith("#"):
                continue

            # 文档字符串
            if stripped.startswith(('"""', "'''")):
                # 简单检查，不完全准确但对大多数情况有效
                continue

            # 有代码变更
            whitespace_only = False
            meaningful_changes += 1

        if whitespace_only:
            return Significance.INSIGNIFICANT

        # 根据变更行数判断
        if meaningful_changes > 50:
            return Significance.HIGH
        elif meaningful_changes > 10:
            return Significance.MEDIUM
        elif meaningful_changes > 0:
            return Significance.LOW

        return Significance.INSIGNIFICANT

    def is_significant_change(self, change: ChangedFile) -> bool:
        """
        判断是否为有意义变更

        Args:
            change: 变更文件

        Returns:
            是否有意义
        """
        return change.significance != Significance.INSIGNIFICANT

    def get_related_files(self, file_path: str) -> list[str]:
        """
        获取相关的文件（如测试文件、文档文件等）

        Args:
            file_path: 原始文件路径

        Returns:
            相关文件列表
        """
        path = Path(file_path)
        related = []

        # 同名的测试文件
        if path.suffix == ".py":
            test_paths = [
                path.parent / f"test_{path.stem}.py",
                path.parent / f"{path.stem}_test.py",
                path.parent.parent / "tests" / f"test_{path.stem}.py",
            ]
            for test_path in test_paths:
                if test_path.exists():
                    related.append(str(test_path))

        # 相关的文档文件
        if path.suffix in {".py", ".yaml", ".yml"}:
            doc_paths = [
                path.with_suffix(".md"),
                path.parent / "README.md",
            ]
            for doc_path in doc_paths:
                if doc_path.exists():
                    related.append(str(doc_path))

        return related


def fnmatch(name: str, pattern: str) -> bool:
    """
    简单的文件名匹配

    Args:
        name: 文件名
        pattern: 模式（支持 * 通配符）

    Returns:
        是否匹配
    """
    import re
    regex = pattern.replace(".", r"\.").replace("*", ".*")
    return re.match(f"^{regex}$", name) is not None
