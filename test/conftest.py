"""
Power Platform Agent - Pytest Global Configuration
全局pytest配置文件，定义共享fixtures和测试环境设置
"""

import os
import sys
import shutil
import tempfile
from pathlib import Path
from typing import Generator, Optional
import pytest


# =============================================================================
# 项目路径设置
# =============================================================================

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
FRAMEWORK_ROOT = PROJECT_ROOT / "framework"
TEST_ROOT = PROJECT_ROOT / "test"
TEST_DATA_ROOT = TEST_ROOT / "data"
TEST_TEMP_ROOT = TEST_ROOT / "temp"
TEST_FIXTURES_ROOT = TEST_ROOT / "fixtures"

# 将项目路径添加到 sys.path
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(FRAMEWORK_ROOT))


# =============================================================================
# 测试标记定义
# =============================================================================
def pytest_configure(config):
    """注册pytest标记"""
    config.addinivalue_line("markers", "unit: 单元测试（快速，无外部依赖）")
    config.addinivalue_line("markers", "integration: 集成测试（需要外部服务）")
    config.addinivalue_line("markers", "slow: 慢速测试")
    config.addinivalue_line("markers", "requires_auth: 需要认证的测试")
    config.addinivalue_line("markers", "requires_dataverse: 需要真实Dataverse实例的测试")


# =============================================================================
# 共享 Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def project_root() -> Path:
    """项目根目录路径"""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def framework_root() -> Path:
    """框架目录路径"""
    return FRAMEWORK_ROOT


@pytest.fixture(scope="session")
def test_data_root() -> Path:
    """测试数据目录路径"""
    return TEST_DATA_ROOT


@pytest.fixture(scope="session")
def test_temp_root() -> Path:
    """测试临时目录路径"""
    return TEST_TEMP_ROOT


@pytest.fixture(scope="function")
def temp_dir(test_temp_root) -> Generator[Path, None, None]:
    """
    创建临时测试目录（每个测试函数独立）
    测试完成后自动清理
    """
    temp_path = test_temp_root / f"temp_{tempfile.gettempprefix()}{os.getpid()}"
    temp_path.mkdir(parents=True, exist_ok=True)

    yield temp_path

    # 清理临时目录
    if temp_path.exists():
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture(scope="function")
def temp_file(temp_dir) -> Generator[Path, None, None]:
    """
    创建临时测试文件（每个测试函数独立）
    返回临时文件路径，测试完成后自动清理
    """
    fd, path = tempfile.mkstemp(dir=temp_dir, suffix=".tmp")
    os.close(fd)

    yield Path(path)

    # 清理临时文件
    if Path(path).exists():
        Path(path).unlink(missing_ok=True)


@pytest.fixture(scope="session")
def valid_yaml_samples(test_data_root) -> Path:
    """有效YAML测试数据目录"""
    return test_data_root / "yaml" / "valid"


@pytest.fixture(scope="session")
def invalid_yaml_samples(test_data_root) -> Path:
    """无效YAML测试数据目录（用于验证）"""
    return test_data_root / "yaml" / "invalid"


@pytest.fixture(scope="session")
def mock_response_data(test_data_root) -> Path:
    """API响应测试数据目录"""
    return test_data_root / "responses"


@pytest.fixture(scope="session")
def test_config_dir(test_data_root) -> Path:
    """测试配置目录"""
    return test_data_root / "config"


# =============================================================================
# 自动清理机制
# =============================================================================

@pytest.fixture(scope="session", autouse=True)
def cleanup_temp_files_on_start(test_temp_root):
    """
    测试会话开始时清理旧的临时文件
    autouse=True 表示自动运行，无需显式调用
    """
    if test_temp_root.exists():
        for item in test_temp_root.iterdir():
            if item.is_file() and item.name != "README.md":
                item.unlink(missing_ok=True)
            elif item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
    yield
    # 测试会话结束后再次清理
    if test_temp_root.exists():
        for item in test_temp_root.iterdir():
            if item.is_file() and item.name != "README.md":
                item.unlink(missing_ok=True)
            elif item.is_dir():
                shutil.rmtree(item, ignore_errors=True)


@pytest.fixture(scope="function", autouse=True)
def cleanup_temp_files_after_test(test_temp_root):
    """
    每个测试函数结束后清理该测试创建的临时文件
    autouse=True 表示自动运行，无需显式调用
    """
    yield
    # 检查是否有当前测试遗留的临时文件
    if test_temp_root.exists():
        temp_pattern = f"temp_{os.getpid()}"
        for item in test_temp_root.iterdir():
            if temp_pattern in item.name or (item.is_dir() and item.name.startswith("temp_")):
                if item.is_file():
                    item.unlink(missing_ok=True)
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)


# =============================================================================
# 环境变量管理
# =============================================================================

@pytest.fixture(scope="function")
def mock_env(monkeypatch):
    """
    提供临时环境变量的fixture
    用法:
        def test_something(mock_env):
            mock_env.set("MY_VAR", "value")
    """
    class MockEnv:
        def __init__(self, monkeypatch):
            self._monkeypatch = monkeypatch
            self._original = {}

        def set(self, key: str, value: str):
            """设置环境变量"""
            if key in os.environ:
                self._original[key] = os.environ[key]
            self._monkeypatch.setenv(key, value)

        def unset(self, key: str):
            """取消环境变量"""
            self._monkeypatch.delenv(key, raising=False)

        def restore(self):
            """恢复所有原始环境变量"""
            for key, value in self._original.items():
                self._monkeypatch.setenv(key, value)

    return MockEnv(monkeypatch)


# =============================================================================
# 模拟服务器配置
# =============================================================================

@pytest.fixture(scope="session")
def mock_dataverse_server():
    """
    模拟Dataverse服务器配置
    返回服务器URL和认证信息
    """
    return {
        "url": "https://mock.dataverse.server",
        "tenant_id": "mock-tenant-id",
        "client_id": "mock-client-id",
        "client_secret": "mock-secret",
        "api_version": "9.2",
    }


# =============================================================================
# 跳过条件配置
# =============================================================================

def pytest_collection_modifyitems(config, items):
    """
    根据标记和条件自动跳过测试
    """
    # 跳过需要认证的测试（除非设置了环境变量）
    if not os.environ.get("PP_RUN_AUTH_TESTS"):
        skip_auth = pytest.mark.skip(reason="需要设置 PP_RUN_AUTH_TESTS=1 来运行认证测试")
        for item in items:
            if "requires_auth" in item.keywords:
                item.add_marker(skip_auth)

    # 跳过需要真实Dataverse的测试
    if not os.environ.get("PP_RUN_DATAVERSE_TESTS"):
        skip_dataverse = pytest.mark.skip(reason="需要设置 PP_RUN_DATAVERSE_TESTS=1 来运行Dataverse测试")
        for item in items:
            if "requires_dataverse" in item.keywords:
                item.add_marker(skip_dataverse)


# =============================================================================
# 测试报告钩子
# =============================================================================

# def pytest_html_report_title(report):
#     """自定义HTML报告标题"""
#     # Skip if pytest-html is not installed
#     if hasattr(report, 'title'):
#         report.title = "Power Platform Agent - 测试报告"


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """在测试摘要后显示额外信息"""
    terminalreporter.write_sep("=", "测试目录结构验证")
    terminalreporter.write_line("确保所有测试文件都在 test/ 目录下", yellow=True)
    terminalreporter.write_line("运行验证脚本: python test/scripts/verify_test_isolation.py")
