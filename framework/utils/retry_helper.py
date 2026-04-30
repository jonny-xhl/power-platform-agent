"""
Dataverse 元数据传播延时重试辅助工具

Dataverse 创建表/字段/关系后，元数据需要时间传播到所有节点。
本模块提供重试装饰器和等待函数来处理这种延时。
"""

import time
import logging
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class MetadataPropagationError(Exception):
    """元数据传播未在超时时间内完成"""
    pass


def retry_on_metadata_error(
    max_retries: int = 5,
    initial_delay: float = 2.0,
    backoff_factor: float = 1.5,
    jitter: float = 0.5,
    error_patterns: Optional[list[str]] = None
) -> Callable:
    """
    重试装饰器 - 处理元数据传播延时

    Args:
        max_retries: 最大重试次数
        initial_delay: 初始延迟秒数
        backoff_factor: 退避因子（每次重试延迟乘以该因子）
        jitter: 抖动秒数（随机波动，避免同时重试）
        error_patterns: 需要重试的错误模式列表（None 表示默认模式）

    Returns:
        装饰后的函数
    """
    if error_patterns is None:
        error_patterns = [
            "not found",
            "cannot be found",
            "does not exist",
            "entity not found",
            "attribute not found",
            "could not be found",
            "invalid entity",
            "invalid attribute",
            "404",  # HTTP 404
            "metadata id",  # 元数据ID相关错误
            "depends on",  # 依赖关系错误
        ]

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            import random
            delay = initial_delay
            last_error: Optional[Exception] = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    error_msg = str(e).lower()

                    # 检查是否是需要重试的错误
                    should_retry = any(pattern in error_msg for pattern in error_patterns)

                    if should_retry and attempt < max_retries - 1:
                        # 添加随机抖动
                        actual_delay = delay + random.uniform(0, jitter)
                        logger.warning(
                            f"[Retry] {func.__name__} failed (attempt {attempt + 1}/{max_retries}): "
                            f"{e}. Retrying in {actual_delay:.1f}s..."
                        )
                        time.sleep(actual_delay)
                        delay *= backoff_factor
                        continue
                    else:
                        # 不需要重试或已达最大重试次数
                        if not should_retry:
                            logger.debug(f"[Retry] {func.__name__} failed with non-retryable error: {e}")
                        else:
                            logger.error(
                                f"[Retry] {func.__name__} failed after {max_retries} attempts: {e}"
                            )
                        raise

            # 理论上不会到达这里，但为了类型安全
            if last_error:
                raise last_error

        return wrapper
    return decorator


def retry_on_404(max_retries: int = 5, initial_delay: float = 2.0) -> Callable:
    """
    简化版重试装饰器 - 仅针对 404/not found 错误

    Args:
        max_retries: 最大重试次数
        initial_delay: 初始延迟秒数

    Returns:
        装饰后的函数
    """
    return retry_on_metadata_error(
        max_retries=max_retries,
        initial_delay=initial_delay,
        error_patterns=["not found", "cannot be found", "404"]
    )


def wait_for_entity_available(
    check_fn: Callable[[str], Any],
    entity_name: str,
    timeout: float = 30.0,
    check_interval: float = 2.0
) -> dict[str, Any]:
    """
    等待实体元数据可用

    Args:
        check_fn: 检查函数，接收 entity_name，返回元数据或抛出异常
        entity_name: 实体名称
        timeout: 超时时间（秒）
        check_interval: 检查间隔（秒）

    Returns:
        实体元数据

    Raises:
        MetadataPropagationError: 超时后仍不可用
    """
    start = time.time()
    last_error: Optional[Exception] = None

    while time.time() - start < timeout:
        try:
            metadata = check_fn(entity_name)
            logger.info(f"[Wait] Entity '{entity_name}' is now available")
            return metadata
        except Exception as e:
            last_error = e
            logger.debug(f"[Wait] Entity '{entity_name}' not ready: {e}. Retrying...")
            time.sleep(check_interval)

    raise MetadataPropagationError(
        f"Entity '{entity_name}' not available after {timeout}s. Last error: {last_error}"
    )


def wait_for_default_components(
    check_fn: Callable[[str, str], Any],
    entity_name: str,
    component_type: str,
    component_name: str,
    timeout: float = 45.0,
    check_interval: float = 3.0
) -> dict[str, Any]:
    """
    等待 Dataverse 自动创建的默认组件（表单、视图等）

    Dataverse 创建表后会自动创建：
    - 默认表单（Main Form、Quick Create Form）
    - 默认视图（Active View、Quick Find View）

    Args:
        check_fn: 检查函数，接收 entity_name 和 component_name
        entity_name: 实体名称
        component_type: 组件类型（form、view 等）
        component_name: 组件名称
        timeout: 超时时间（秒），默认更长因为默认组件创建需要更多时间
        check_interval: 检查间隔（秒）

    Returns:
        组件元数据

    Raises:
        MetadataPropagationError: 超时后仍不可用
    """
    start = time.time()
    last_error: Optional[Exception] = None

    logger.info(
        f"[Wait] Waiting for default {component_type} '{component_name}' "
        f"for entity '{entity_name}' (timeout: {timeout}s)"
    )

    while time.time() - start < timeout:
        try:
            metadata = check_fn(entity_name, component_name)
            logger.info(
                f"[Wait] Default {component_type} '{component_name}' "
                f"is now available for entity '{entity_name}'"
            )
            return metadata
        except Exception as e:
            last_error = e
            logger.debug(
                f"[Wait] Default {component_type} '{component_name}' "
                f"not ready: {e}. Retrying..."
            )
            time.sleep(check_interval)

    raise MetadataPropagationError(
        f"Default {component_type} '{component_name}' not available after {timeout}s. "
        f"Last error: {last_error}"
    )


def wait_for_attribute_available(
    check_fn: Callable[[str, str], Any],
    entity_name: str,
    attribute_name: str,
    timeout: float = 20.0,
    check_interval: float = 1.5
) -> dict[str, Any]:
    """
    等待属性元数据可用

    Args:
        check_fn: 检查函数，接收 entity_name 和 attribute_name
        entity_name: 实体名称
        attribute_name: 属性名称
        timeout: 超时时间（秒）
        check_interval: 检查间隔（秒）

    Returns:
        属性元数据

    Raises:
        MetadataPropagationError: 超时后仍不可用
    """
    start = time.time()
    last_error: Optional[Exception] = None

    while time.time() - start < timeout:
        try:
            metadata = check_fn(entity_name, attribute_name)
            logger.info(f"[Wait] Attribute '{attribute_name}' is now available for entity '{entity_name}'")
            return metadata
        except Exception as e:
            last_error = e
            logger.debug(f"[Wait] Attribute '{attribute_name}' not ready: {e}. Retrying...")
            time.sleep(check_interval)

    raise MetadataPropagationError(
        f"Attribute '{attribute_name}' not available after {timeout}s. Last error: {last_error}"
    )


class RetryContext:
    """
    重试上下文管理器，用于更细粒度的重试控制

    示例:
        with RetryContext(max_retries=3, delay=2.0) as retry:
            while retry.should_retry():
                try:
                    return some_operation()
                except Exception as e:
                    retry.record_error(e)
    """

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 2.0,
        backoff_factor: float = 1.5,
        error_patterns: Optional[list[str]] = None
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor
        self.error_patterns = error_patterns
        self.attempt = 0
        self.delay = initial_delay
        self.last_error: Optional[Exception] = None
        self._should_continue = True

    def should_retry(self) -> bool:
        """是否应该继续重试"""
        return self.attempt < self.max_retries and self._should_continue

    def record_error(self, error: Exception) -> None:
        """记录错误并决定是否重试"""
        self.last_error = error
        self.attempt += 1

        if self.attempt >= self.max_retries:
            self._should_continue = False
            return

        # 检查是否是可重试的错误
        if self.error_patterns:
            error_msg = str(error).lower()
            should_retry = any(p in error_msg for p in self.error_patterns)
            if not should_retry:
                self._should_continue = False
                return

        # 等待后重试
        logger.warning(f"[RetryContext] Attempt {self.attempt}/{self.max_retries} failed: {error}")
        time.sleep(self.delay)
        self.delay *= self.backoff_factor

    def success(self) -> None:
        """标记成功，停止重试"""
        self._should_continue = False

    def __enter__(self) -> "RetryContext":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.record_error(exc_val)
            # 如果还应该重试，抑制异常
            return self._should_continue
        return False
