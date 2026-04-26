#!/usr/bin/env python3
"""
Power Platform Agent - Cleanup Temporary Files Script
手动清理脚本，可独立运行清除所有临时文件
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timedelta


# =============================================================================
# 配置
# =============================================================================

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 临时目录模式
TEMP_PATTERNS = [
    "temp_*",
    "tmp_*",
    "*.tmp",
    "*.temp",
    "*_temp_",
    "*_tmp_",
]

# 需要清理的目录
TEMP_DIRECTORIES = [
    PROJECT_ROOT / "test" / "temp",
    PROJECT_ROOT / ".pytest_cache",
    PROJECT_ROOT / "test" / "reports",
]

# 老旧文件阈值（天）
OLD_FILE_THRESHOLD_DAYS = 1


# =============================================================================
# 工具函数
# =============================================================================

def find_temp_files(directory: Path, patterns: list[str]) -> list[Path]:
    """
    查找目录下所有临时文件

    Args:
        directory: 要搜索的目录
        patterns: 文件匹配模式列表

    Returns:
        找到的临时文件路径列表
    """
    temp_files = []

    if not directory.exists():
        return temp_files

    for pattern in patterns:
        temp_files.extend(directory.glob(pattern))
        # 递归搜索子目录
        temp_files.extend(directory.rglob(pattern))

    return temp_files


def is_old_file(file_path: Path, threshold_days: int) -> bool:
    """
    判断文件是否超过指定天数未修改

    Args:
        file_path: 文件路径
        threshold_days: 天数阈值

    Returns:
        是否为老旧文件
    """
    if not file_path.exists():
        return False

    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
    age = datetime.now() - mtime
    return age.days >= threshold_days


def cleanup_directory(directory: Path, dry_run: bool = False) -> dict:
    """
    清理目录中的临时文件

    Args:
        directory: 要清理的目录
        dry_run: 是否为演练模式（不实际删除）

    Returns:
        清理统计信息
    """
    stats = {
        "directory": str(directory),
        "files_deleted": 0,
        "dirs_deleted": 0,
        "space_freed": 0,
        "errors": [],
    }

    if not directory.exists():
        return stats

    # 查找临时文件
    temp_files = find_temp_files(directory, TEMP_PATTERNS)

    for file_path in temp_files:
        try:
            size = file_path.stat().st_size if file_path.is_file() else 0

            if dry_run:
                print(f"  [DRY RUN] 将删除: {file_path}")
            else:
                if file_path.is_file():
                    file_path.unlink(missing_ok=True)
                elif file_path.is_dir():
                    shutil.rmtree(file_path, ignore_errors=True)

            stats["files_deleted"] += 1
            stats["space_freed"] += size

        except Exception as e:
            stats["errors"].append(f"{file_path}: {e}")

    # 清理空的临时目录
    for item in directory.iterdir():
        if item.is_dir() and any(p in item.name for p in ["temp", "tmp"]):
            try:
                # 检查目录是否为空
                if not list(item.iterdir()):
                    if dry_run:
                        print(f"  [DRY RUN] 将删除空目录: {item}")
                    else:
                        item.rmdir()
                    stats["dirs_deleted"] += 1
            except Exception as e:
                stats["errors"].append(f"{item}: {e}")

    return stats


def cleanup_all(dry_run: bool = False, include_old: bool = False) -> dict:
    """
    清理所有临时文件和目录

    Args:
        dry_run: 是否为演练模式
        include_old: 是否包含老旧文件

    Returns:
        总体清理统计信息
    """
    total_stats = {
        "directories_cleaned": 0,
        "total_files_deleted": 0,
        "total_dirs_deleted": 0,
        "total_space_freed": 0,
        "all_errors": [],
    }

    for temp_dir in TEMP_DIRECTORIES:
        print(f"\n清理目录: {temp_dir}")
        stats = cleanup_directory(temp_dir, dry_run=dry_run)

        total_stats["directories_cleaned"] += 1
        total_stats["total_files_deleted"] += stats["files_deleted"]
        total_stats["total_dirs_deleted"] += stats["dirs_deleted"]
        total_stats["total_space_freed"] += stats["space_freed"]
        total_stats["all_errors"].extend(stats["errors"])

        print(f"  已删除文件: {stats['files_deleted']}")
        print(f"  已删除目录: {stats['dirs_deleted']}")
        if stats["space_freed"] > 0:
            print(f"  释放空间: {format_size(stats['space_freed'])}")

    # 查找并清理项目根目录下的临时文件
    print(f"\n检查项目根目录: {PROJECT_ROOT}")
    root_temp_files = find_temp_files(PROJECT_ROOT, ["*.tmp", "*.temp", "temp_*", "tmp_*"])

    for file_path in root_temp_files:
        # 跳过test目录内的文件（已处理）
        if "test/temp" in str(file_path) or ".pytest_cache" in str(file_path):
            continue

        # 检查是否为老旧文件
        if include_old or is_old_file(file_path, OLD_FILE_THRESHOLD_DAYS):
            try:
                size = file_path.stat().st_size if file_path.is_file() else 0

                if dry_run:
                    print(f"  [DRY RUN] 将删除: {file_path}")
                else:
                    if file_path.is_file():
                        file_path.unlink(missing_ok=True)
                    elif file_path.is_dir():
                        shutil.rmtree(file_path, ignore_errors=True)

                total_stats["total_files_deleted"] += 1
                total_stats["total_space_freed"] += size

            except Exception as e:
                total_stats["all_errors"].append(f"{file_path}: {e}")

    return total_stats


def format_size(size_bytes: int) -> str:
    """
    格式化字节大小为人类可读格式

    Args:
        size_bytes: 字节数

    Returns:
        格式化后的大小字符串
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def format_errors(errors: list[str]) -> str:
    """
    格式化错误信息

    Args:
        errors: 错误列表

    Returns:
        格式化后的错误字符串
    """
    if not errors:
        return "无错误"

    result = ["\n错误详情:"]
    for error in errors[:10]:  # 最多显示10个错误
        result.append(f"  - {error}")

    if len(errors) > 10:
        result.append(f"  ... 还有 {len(errors) - 10} 个错误")

    return "\n".join(result)


# =============================================================================
# 命令行接口
# =============================================================================

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="清理Power Platform Agent项目的临时文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python cleanup_temp_files.py              # 清理所有临时文件
  python cleanup_temp_files.py --dry-run    # 演练模式，不实际删除
  python cleanup_temp_files.py --include-old # 包含老旧文件
  python cleanup_temp_files.py --dir test/temp  # 清理指定目录
        """,
    )

    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="演练模式，不实际删除文件",
    )

    parser.add_argument(
        "--include-old",
        action="store_true",
        help=f"包含超过{OLD_FILE_THRESHOLD_DAYS}天未修改的老旧文件",
    )

    parser.add_argument(
        "--dir",
        "-d",
        type=str,
        action="append",
        help="指定要清理的目录（可多次使用）",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="静默模式，减少输出",
    )

    args = parser.parse_args()

    # 更新要清理的目录列表
    if args.dir:
        TEMP_DIRECTORIES.clear()
        for dir_path in args.dir:
            TEMP_DIRECTORIES.append(Path(dir_path).resolve())

    # 打印开始信息
    if not args.quiet:
        print("=" * 60)
        print("Power Platform Agent - 临时文件清理工具")
        print("=" * 60)
        print(f"模式: {'演练（不实际删除）' if args.dry_run else '实际删除'}")
        print(f"包含老旧文件: {'是' if args.include_old else '否'}")
        print()

    # 执行清理
    stats = cleanup_all(dry_run=args.dry_run, include_old=args.include_old)

    # 打印摘要
    if not args.quiet:
        print("\n" + "=" * 60)
        print("清理摘要")
        print("=" * 60)
        print(f"已处理目录: {stats['directories_cleaned']}")
        print(f"已删除文件: {stats['total_files_deleted']}")
        print(f"已删除目录: {stats['total_dirs_deleted']}")
        if stats['total_space_freed'] > 0:
            print(f"释放空间: {format_size(stats['total_space_freed'])}")
        print(format_errors(stats['all_errors']))

    # 返回退出码
    if stats['all_errors']:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
