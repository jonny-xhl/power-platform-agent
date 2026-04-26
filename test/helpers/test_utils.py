"""
Power Platform Agent - Test Utility Functions
测试辅助工具函数
"""

import asyncio
import functools
import inspect
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, TypeVar, ParamSpec, Optional
from unittest.mock import MagicMock, patch

P = ParamSpec("P")
T = TypeVar("T")


# =============================================================================
# 装饰器
# =============================================================================

def skip_if(condition: bool, reason: str = ""):
    """
    条件跳过测试装饰器

    Args:
        condition: 跳过条件
        reason: 跳过原因

    Returns:
        装饰器函数
    """
    import pytest

    return pytest.mark.skipif(condition, reason=reason)


def skip_if_not(module_name: str, reason: Optional[str] = None):
    """
    模块不存在时跳过测试

    Args:
        module_name: 模块名
        reason: 跳过原因

    Returns:
        装饰器函数
    """
    import pytest

    try:
        __import__(module_name)
        return pytest.mark.skipif(False, reason="")
    except ImportError:
        return pytest.mark.skipif(
            True,
            reason=reason or f"需要安装 {module_name} 模块"
        )


def repeat(times: int):
    """
    重复运行测试装饰器

    Args:
        times: 重复次数

    Returns:
        装饰器函数
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            for _ in range(times):
                result = func(*args, **kwargs)
            return result

        return wrapper

    return decorator


def timeout(seconds: float):
    """
    测试超时装饰器

    Args:
        seconds: 超时秒数

    Returns:
        装饰器函数
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError(f"测试超时: {func.__name__} 超过 {seconds} 秒")

            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(seconds))
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wrapper

    return decorator


def with_mock_env(**env_vars: str):
    """
    临时设置环境变量装饰器

    Args:
        **env_vars: 环境变量键值对

    Returns:
        装饰器函数
    """
    import os

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            original_values = {}
            for key, value in env_vars.items():
                original_values[key] = os.environ.get(key)
                os.environ[key] = value

            try:
                return func(*args, **kwargs)
            finally:
                for key, original_value in original_values.items():
                    if original_value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = original_value

        return wrapper

    return decorator


# =============================================================================
# 异步测试辅助
# =============================================================================

def run_async(coro):
    """
    运行异步函数的辅助函数

    Args:
        coro: 协程对象

    Returns:
        协程的返回值
    """
    return asyncio.run(coro)


def async_test(func: Callable[P, T]) -> Callable[P, T]:
    """
    异步测试装饰器

    Args:
        func: 异步测试函数

    Returns:
        包装后的同步函数
    """
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return asyncio.run(func(*args, **kwargs))

    return wrapper


# =============================================================================
# 上下文管理器
# =============================================================================

@contextmanager
def assert_raises(exception_type: type, message: Optional[str] = None):
    """
    断言抛出异常的上下文管理器

    Args:
        exception_type: 期望的异常类型
        message: 期望的异常消息（可选）

    Yields:
        None

    Raises:
        AssertionError: 未抛出异常或异常消息不匹配
    """
    try:
        yield
        raise AssertionError(f"期望抛出 {exception_type.__name__}，但未抛出异常")
    except exception_type as e:
        if message is not None and message not in str(e):
            raise AssertionError(
                f"异常消息不匹配\n期望包含: {message}\n实际: {str(e)}"
            )


@contextmanager
def assert_no_exception():
    """
    断言不抛出异常的上下文管理器

    Yields:
        None

    Raises:
        AssertionError: 抛出了异常
    """
    try:
        yield
    except Exception as e:
        raise AssertionError(f"期望不抛出异常，但抛出了: {type(e).__name__}: {e}")


@contextmanager
def mock_time():
    """
    模拟时间的上下文管理器

    Yields:
        mock_time对象
    """
    import unittest.mock as mock

    with mock.patch("time.time") as mock_time:
        mock_time.return_value = 0
        yield mock_time


@contextmanager
def temporary_cwd(path: Path):
    """
    临时更改工作目录

    Args:
        path: 临时工作目录

    Yields:
        None
    """
    import os

    original_cwd = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original_cwd)


@contextmanager
def capture_output():
    """
    捕获标准输出的上下文管理器

    Yields:
        (stdout_string, stderr_string)
    """
    from io import StringIO
    import sys

    old_stdout = sys.stdout
    old_stderr = sys.stderr

    try:
        out = StringIO()
        err = StringIO()
        sys.stdout = out
        sys.stderr = err
        yield out, err
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


# =============================================================================
# 性能测试辅助
# =============================================================================

def measure_time(func: Callable[P, T]) -> tuple[T, float]:
    """
    测量函数执行时间

    Args:
        func: 要测量的函数

    Returns:
        (函数返回值, 执行时间秒数)
    """
    start_time = time.perf_counter()
    result = func()
    end_time = time.perf_counter()
    return result, end_time - start_time


def time_it(func: Callable[P, T]) -> Callable[P, T]:
    """
    测量并打印函数执行时间的装饰器

    Args:
        func: 要测量的函数

    Returns:
        包装后的函数
    """
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        result, elapsed = measure_time(lambda: func(*args, **kwargs))
        print(f"{func.__name__} 执行时间: {elapsed:.4f} 秒")
        return result

    return wrapper


# =============================================================================
# 模拟辅助
# =============================================================================

def create_mock_response(
    status_code: int = 200,
    json_data: Optional[dict] = None,
    text: str = "",
    headers: Optional[dict] = None,
) -> MagicMock:
    """
    创建模拟HTTP响应

    Args:
        status_code: HTTP状态码
        json_data: JSON响应数据
        text: 文本响应内容
        headers: 响应头

    Returns:
        模拟响应对象
    """
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.ok = status_code < 400
    mock_resp.text = text

    if json_data:
        mock_resp.json.return_value = json_data

    if headers:
        mock_resp.headers = headers

    return mock_resp


def patch_with_mock(
    target: str,
    return_value: Any = None,
    side_effect: Optional[Callable] = None,
) -> MagicMock:
    """
    创建并应用模拟补丁

    Args:
        target: 要模拟的目标（格式: "module.path.to.function"）
        return_value: 返回值
        side_effect: 副作用函数

    Returns:
        模拟对象
    """
    patcher = patch(target, return_value=return_value, side_effect=side_effect)
    mock_obj = patcher.start()
    return mock_obj


# =============================================================================
# 生成测试数据
# =============================================================================

def generate_test_email(domain: str = "example.com") -> str:
    """生成测试邮箱地址"""
    import uuid
    return f"test-{uuid.uuid4()}@{domain}"


def generate_test_name(prefix: str = "test") -> str:
    """生成测试名称"""
    import uuid
    return f"{prefix}-{uuid.uuid4()}"


def generate_test_url(path: str = "/") -> str:
    """生成测试URL"""
    return f"https://test.example.com{path}"


# =============================================================================
# 路径辅助
# =============================================================================

def get_test_data_path(*parts: str) -> Path:
    """
    获取测试数据文件路径

    Args:
        *parts: 路径部分

    Returns:
        测试数据文件完整路径
    """
    test_root = Path(__file__).parent.parent
    return test_root / "data" / Path(*parts)


def get_test_fixture_path(*parts: str) -> Path:
    """
    �试测试夹具文件路径

    Args:
        *parts: 路径部分

    Returns:
        测试夹具文件完整路径
    """
    test_root = Path(__file__).parent.parent
    return test_root / "fixtures" / Path(*parts)
