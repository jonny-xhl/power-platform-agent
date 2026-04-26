"""
Power Platform Agent - Custom Test Assertions
自定义测试断言辅助函数
"""

import os
from pathlib import Path
from typing import Any, Optional, Union, List, Dict
import re


def assert_file_exists(
    path: Union[Path, str],
    message: Optional[str] = None,
) -> Path:
    """
    断言文件存在

    Args:
        path: 文件路径
        message: 自定义错误消息

    Returns:
        文件路径对象

    Raises:
        AssertionError: 文件不存在
    """
    path_obj = Path(path)
    if not path_obj.exists():
        msg = message or f"文件不存在: {path_obj}"
        raise AssertionError(msg)
    return path_obj


def assert_file_not_exists(
    path: Union[Path, str],
    message: Optional[str] = None,
) -> None:
    """
    断言文件不存在

    Args:
        path: 文件路径
        message: 自定义错误消息

    Raises:
        AssertionError: 文件存在
    """
    path_obj = Path(path)
    if path_obj.exists():
        msg = message or f"文件不应存在: {path_obj}"
        raise AssertionError(msg)


def assert_dir_exists(
    path: Union[Path, str],
    message: Optional[str] = None,
) -> Path:
    """
    断言目录存在

    Args:
        path: 目录路径
        message: 自定义错误消息

    Returns:
        目录路径对象

    Raises:
        AssertionError: 目录不存在或不是目录
    """
    path_obj = Path(path)
    if not path_obj.is_dir():
        msg = message or f"目录不存在: {path_obj}"
        raise AssertionError(msg)
    return path_obj


def assert_file_contains(
    path: Union[Path, str],
    content: str,
    encoding: str = "utf-8",
    message: Optional[str] = None,
) -> None:
    """
    断言文件包含指定内容

    Args:
        path: 文件路径
        content: 期望包含的内容
        encoding: 文件编码
        message: 自定义错误消息

    Raises:
        AssertionError: 文件不包含指定内容
    """
    path_obj = Path(path)
    if not path_obj.exists():
        raise AssertionError(f"文件不存在: {path_obj}")

    file_content = path_obj.read_text(encoding=encoding)
    if content not in file_content:
        msg = message or f"文件 {path_obj} 不包含内容: {content}"
        raise AssertionError(msg)


def assert_file_matches_pattern(
    path: Union[Path, str],
    pattern: Union[str, re.Pattern],
    encoding: str = "utf-8",
    message: Optional[str] = None,
) -> None:
    """
    断言文件内容匹配正则表达式

    Args:
        path: 文件路径
        pattern: 正则表达式模式
        encoding: 文件编码
        message: 自定义错误消息

    Raises:
        AssertionError: 文件内容不匹配模式
    """
    path_obj = Path(path)
    if not path_obj.exists():
        raise AssertionError(f"文件不存在: {path_obj}")

    file_content = path_obj.read_text(encoding=encoding)

    if isinstance(pattern, str):
        pattern = re.compile(pattern)

    if not pattern.search(file_content):
        msg = message or f"文件 {path_obj} 不匹配模式: {pattern.pattern}"
        raise AssertionError(msg)


def assert_yaml_valid(
    path: Union[Path, str],
    message: Optional[str] = None,
) -> None:
    """
    断言YAML文件有效

    Args:
        path: YAML文件路径
        message: 自定义错误消息

    Raises:
        AssertionError: YAML文件无效
    """
    try:
        import yaml

        path_obj = Path(path)
        with open(path_obj, "r", encoding="utf-8") as f:
            yaml.safe_load(f)
    except ImportError:
        raise AssertionError("需要安装 PyYAML: pip install pyyaml")
    except Exception as e:
        msg = message or f"YAML文件无效: {path_obj}\n错误: {e}"
        raise AssertionError(msg)


def assert_json_valid(
    path: Union[Path, str],
    message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    断言JSON文件有效

    Args:
        path: JSON文件路径
        message: 自定义错误消息

    Returns:
        解析后的JSON数据

    Raises:
        AssertionError: JSON文件无效
    """
    import json

    path_obj = Path(path)
    if not path_obj.exists():
        raise AssertionError(f"文件不存在: {path_obj}")

    try:
        with open(path_obj, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        msg = message or f"JSON文件无效: {path_obj}\n错误: {e}"
        raise AssertionError(msg)
    except Exception as e:
        msg = message or f"读取JSON文件失败: {path_obj}\n错误: {e}"
        raise AssertionError(msg)


def assert_files_equal(
    path1: Union[Path, str],
    path2: Union[Path, str],
    message: Optional[str] = None,
) -> None:
    """
    断言两个文件内容相同

    Args:
        path1: 第一个文件路径
        path2: 第二个文件路径
        message: 自定义错误消息

    Raises:
        AssertionError: 文件内容不同
    """
    path1_obj = Path(path1)
    path2_obj = Path(path2)

    if not path1_obj.exists():
        raise AssertionError(f"文件不存在: {path1_obj}")
    if not path2_obj.exists():
        raise AssertionError(f"文件不存在: {path2_obj}")

    content1 = path1_obj.read_bytes()
    content2 = path2_obj.read_bytes()

    if content1 != content2:
        msg = message or f"文件内容不同: {path1_obj} 和 {path2_obj}"
        raise AssertionError(msg)


def assert_dict_subset(
    subset: Dict[str, Any],
    superset: Dict[str, Any],
    message: Optional[str] = None,
) -> None:
    """
    断言一个字典是另一个字典的子集

    Args:
        subset: 子集字典
        superset: 父集字典
        message: 自定义错误消息

    Raises:
        AssertionError: subset 不是 superset 的子集
    """
    for key, value in subset.items():
        if key not in superset:
            msg = message or f"键 '{key}' 不在父集中"
            raise AssertionError(msg)
        if superset[key] != value:
            msg = message or f"键 '{key}' 的值不匹配: 期望 {value}, 实际 {superset[key]}"
            raise AssertionError(msg)


def assert_list_contains(
    items: List[Any],
    item: Any,
    message: Optional[str] = None,
) -> None:
    """
    断言列表包含指定元素

    Args:
        items: 列表
        item: 要查找的元素
        message: 自定义错误消息

    Raises:
        AssertionError: 列表不包含指定元素
    """
    if item not in items:
        msg = message or f"列表不包含元素: {item}"
        raise AssertionError(msg)


def assert_env_var_set(
    var_name: str,
    message: Optional[str] = None,
) -> str:
    """
    断言环境变量已设置

    Args:
        var_name: 环境变量名
        message: 自定义错误消息

    Returns:
        环境变量值

    Raises:
        AssertionError: 环境变量未设置
    """
    if var_name not in os.environ:
        msg = message or f"环境变量未设置: {var_name}"
        raise AssertionError(msg)
    return os.environ[var_name]


def assert_module_importable(
    module_name: str,
    message: Optional[str] = None,
) -> None:
    """
    断言模块可以导入

    Args:
        module_name: 模块名
        message: 自定义错误消息

    Raises:
        AssertionError: 模块无法导入
    """
    try:
        __import__(module_name)
    except ImportError as e:
        msg = message or f"模块无法导入: {module_name}\n错误: {e}"
        raise AssertionError(msg)


def assert_pascal_case(
    name: str,
    message: Optional[str] = None,
) -> None:
    """
    断言字符串符合PascalCase命名规范

    Args:
        name: 要检查的字符串
        message: 自定义错误消息

    Raises:
        AssertionError: 不符合PascalCase
    """
    if not re.match(r'^[A-Z][a-zA-Z0-9]*$', name):
        msg = message or f"'{name}' 不符合PascalCase命名规范"
        raise AssertionError(msg)


def assert_snake_case(
    name: str,
    message: Optional[str] = None,
) -> None:
    """
    断言字符串符合snake_case命名规范

    Args:
        name: 要检查的字符串
        message: 自定义错误消息

    Raises:
        AssertionError: 不符合snake_case
    """
    if not re.match(r'^[a-z][a-z0-9_]*$', name):
        msg = message or f"'{name}' 不符合snake_case命名规范"
        raise AssertionError(msg)


def assert_kebab_case(
    name: str,
    message: Optional[str] = None,
) -> None:
    """
    断言字符串符合kebab-case命名规范

    Args:
        name: 要检查的字符串
        message: 自定义错误消息

    Raises:
        AssertionError: 不符合kebab-case
    """
    if not re.match(r'^[a-z][a-z0-9-]*$', name):
        msg = message or f"'{name}' 不符合kebab-case命名规范"
        raise AssertionError(msg)
