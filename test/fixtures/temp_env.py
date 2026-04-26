"""
Power Platform Agent - Temporary Environment Manager
临时环境管理器，提供临时文件创建和清理的统一接口
"""

import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Union, List
import hashlib
import json


class TempEnvManager:
    """
    临时环境管理器

    提供临时文件和目录的创建、跟踪和自动清理功能。
    支持上下文管理器和显式清理两种使用方式。
    """

    def __init__(self, base_dir: Optional[Union[Path, str]] = None):
        """
        初始化临时环境管理器

        Args:
            base_dir: 临时文件基础目录，默认使用系统temp目录
        """
        self.base_dir = Path(base_dir) if base_dir else Path(tempfile.gettempdir())
        self._tracked_paths: List[Path] = []
        self._context_dirs: List[Path] = []

    @property
    def tracked_paths(self) -> List[Path]:
        """获取所有已跟踪的临时路径"""
        return self._tracked_paths.copy()

    def create_temp_dir(
        self,
        prefix: str = "temp_",
        suffix: str = "",
        track: bool = True,
        cleanup_on_exit: bool = False,
    ) -> Path:
        """
        创建临时目录

        Args:
            prefix: 目录名前缀
            suffix: 目录名后缀
            track: 是否跟踪此目录以便后续清理
            cleanup_on_exit: 是否在进程退出时自动清理

        Returns:
            临时目录路径
        """
        temp_dir = Path(tempfile.mkdtemp(prefix=prefix, suffix=suffix, dir=self.base_dir))

        if track:
            self._tracked_paths.append(temp_dir)
        if cleanup_on_exit:
            self._context_dirs.append(temp_dir)

        return temp_dir

    def create_temp_file(
        self,
        content: Optional[Union[str, bytes]] = None,
        prefix: str = "tmp_",
        suffix: str = ".tmp",
        mode: str = "w",
        encoding: str = "utf-8",
        track: bool = True,
        cleanup_on_exit: bool = False,
    ) -> Path:
        """
        创建临时文件

        Args:
            content: 文件内容
            prefix: 文件名前缀
            suffix: 文件名后缀
            mode: 文件打开模式
            encoding: 文件编码
            track: 是否跟踪此文件以便后续清理
            cleanup_on_exit: 是否在进程退出时自动清理

        Returns:
            临时文件路径
        """
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=self.base_dir)
        os.close(fd)

        temp_file = Path(path)

        if content is not None:
            if "b" in mode:
                temp_file.write_bytes(content)  # type: ignore
            else:
                temp_file.write_text(content, encoding=encoding)  # type: ignore

        if track:
            self._tracked_paths.append(temp_file)
        if cleanup_on_exit:
            self._context_dirs.append(temp_file)

        return temp_file

    def create_temp_json(
        self,
        data: dict,
        prefix: str = "json_",
        suffix: str = ".json",
        track: bool = True,
        cleanup_on_exit: bool = False,
    ) -> Path:
        """
        创建临时JSON文件

        Args:
            data: JSON数据
            prefix: 文件名前缀
            suffix: 文件名后缀
            track: 是否跟踪此文件以便后续清理
            cleanup_on_exit: 是否在进程退出时自动清理

        Returns:
            临时JSON文件路径
        """
        json_content = json.dumps(data, ensure_ascii=False, indent=2)
        return self.create_temp_file(
            content=json_content,
            prefix=prefix,
            suffix=suffix,
            track=track,
            cleanup_on_exit=cleanup_on_exit,
        )

    def create_temp_yaml(
        self,
        content: str,
        prefix: str = "yaml_",
        suffix: str = ".yaml",
        track: bool = True,
        cleanup_on_exit: bool = False,
    ) -> Path:
        """
        创建临时YAML文件

        Args:
            content: YAML内容
            prefix: 文件名前缀
            suffix: 文件名后缀
            track: 是否跟踪此文件以便后续清理
            cleanup_on_exit: 是否在进程退出时自动清理

        Returns:
            临时YAML文件路径
        """
        return self.create_temp_file(
            content=content,
            prefix=prefix,
            suffix=suffix,
            track=track,
            cleanup_on_exit=cleanup_on_exit,
        )

    def cleanup(self, path: Optional[Union[Path, str]] = None) -> bool:
        """
        清理指定的临时文件或目录

        Args:
            path: 要清理的路径，如果为None则清理所有跟踪的路径

        Returns:
            是否清理成功
        """
        if path is None:
            # 清理所有跟踪的路径
            success = True
            for temp_path in reversed(self._tracked_paths):
                if not self._cleanup_path(temp_path):
                    success = False
            self._tracked_paths.clear()
            return success

        temp_path = Path(path)
        result = self._cleanup_path(temp_path)

        # 从跟踪列表中移除
        self._tracked_paths = [p for p in self._tracked_paths if p != temp_path]

        return result

    def _cleanup_path(self, path: Path) -> bool:
        """
        清理单个路径

        Args:
            path: 要清理的路径

        Returns:
            是否清理成功
        """
        try:
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            return True
        except (OSError, PermissionError) as e:
            print(f"警告: 无法清理 {path}: {e}")
            return False

    def cleanup_all(self) -> bool:
        """清理所有跟踪的路径和上下文目录"""
        success = self.cleanup()

        # 清理上下文目录
        for temp_dir in reversed(self._context_dirs):
            if not self._cleanup_path(temp_dir):
                success = False
        self._context_dirs.clear()

        return success

    def is_tracked(self, path: Union[Path, str]) -> bool:
        """
        检查路径是否被跟踪

        Args:
            path: 要检查的路径

        Returns:
            是否被跟踪
        """
        return Path(path) in self._tracked_paths

    def get_temp_dir_size(self) -> int:
        """
        获取临时目录总大小（字节）

        Returns:
            临时目录总大小
        """
        total_size = 0
        for temp_path in self._tracked_paths:
            if temp_path.is_file():
                total_size += temp_path.stat().st_size
            elif temp_path.is_dir():
                total_size += sum(
                    f.stat().st_size for f in temp_path.rglob("*") if f.is_file()
                )
        return total_size

    @contextmanager
    def temp_context(
        self, prefix: str = "ctx_", cleanup_on_exception: bool = True
    ) -> Generator[Path, None, None]:
        """
        临时目录上下文管理器

        Args:
            prefix: 目录名前缀
            cleanup_on_exception: 发生异常时是否清理

        Yields:
            临时目录路径
        """
        temp_dir = self.create_temp_dir(prefix=prefix, cleanup_on_exit=True)

        try:
            yield temp_dir
        except Exception:
            if cleanup_on_exception:
                self._cleanup_path(temp_dir)
            raise

    @contextmanager
    def temp_file_context(
        self,
        content: Optional[Union[str, bytes]] = None,
        prefix: str = "tmp_",
        suffix: str = ".tmp",
        cleanup_on_exception: bool = True,
    ) -> Generator[Path, None, None]:
        """
        临时文件上下文管理器

        Args:
            content: 文件内容
            prefix: 文件名前缀
            suffix: 文件名后缀
            cleanup_on_exception: 发生异常时是否清理

        Yields:
            临时文件路径
        """
        temp_file = self.create_temp_file(
            content=content,
            prefix=prefix,
            suffix=suffix,
            cleanup_on_exit=True,
        )

        try:
            yield temp_file
        except Exception:
            if cleanup_on_exception:
                self._cleanup_path(temp_file)
            raise

    def __del__(self):
        """析构函数，自动清理上下文目录"""
        for temp_dir in reversed(self._context_dirs):
            self._cleanup_path(temp_dir)
        self._context_dirs.clear()

    def __enter__(self):
        """进入上下文"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文，自动清理"""
        self.cleanup_all()
        return False


# =============================================================================
# 全局单例实例
# =============================================================================

_global_manager: Optional[TempEnvManager] = None


def get_temp_manager(base_dir: Optional[Union[Path, str]] = None) -> TempEnvManager:
    """
    获取全局临时环境管理器单例

    Args:
        base_dir: 临时文件基础目录，仅在首次调用时生效

    Returns:
        临时环境管理器实例
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = TempEnvManager(base_dir)
    return _global_manager


def reset_temp_manager():
    """重置全局临时环境管理器"""
    global _global_manager
    if _global_manager is not None:
        _global_manager.cleanup_all()
    _global_manager = None


# =============================================================================
# 便捷函数
# =============================================================================

def create_temp_dir(
    prefix: str = "temp_",
    suffix: str = "",
    base_dir: Optional[Union[Path, str]] = None,
) -> Path:
    """创建临时目录的便捷函数"""
    return get_temp_manager(base_dir).create_temp_dir(prefix=prefix, suffix=suffix)


def create_temp_file(
    content: Optional[Union[str, bytes]] = None,
    prefix: str = "tmp_",
    suffix: str = ".tmp",
    base_dir: Optional[Union[Path, str]] = None,
) -> Path:
    """创建临时文件的便捷函数"""
    return get_temp_manager(base_dir).create_temp_file(
        content=content, prefix=prefix, suffix=suffix
    )


def cleanup_temp_files() -> bool:
    """清理所有临时文件的便捷函数"""
    return get_temp_manager().cleanup_all()
