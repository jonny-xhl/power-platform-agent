"""
Power Platform Agent - Integration Tests Configuration
集成测试专用配置
"""

import os
import pytest
from pathlib import Path
from typing import Generator, Optional
import time


# =============================================================================
# 集成测试标记
# =============================================================================

def pytest_configure(config):
    """配置集成测试标记"""
    config.addinivalue_line("markers", "integration: 集成测试（需要外部服务）")
    config.addinivalue_line("markers", "slow: 慢速测试")
    config.addinivalue_line("markers", "requires_auth: 需要认证的测试")
    config.addinivalue_line("markers", "requires_dataverse: 需要真实Dataverse实例的测试")
    config.addinivalue_line("markers", "requires_powerapps: 需要Power Apps环境的测试")
    config.addinivalue_line("markers", "e2e: 端到端测试")


# =============================================================================
# 集成测试环境配置
# =============================================================================

@pytest.fixture(scope="session")
def integration_config():
    """
    集成测试配置

    从环境变量或配置文件读取集成测试所需的配置
    """
    return {
        "dataverse": {
            "url": os.environ.get("PP_DATAVERSE_URL"),
            "tenant_id": os.environ.get("PP_DATAVERSE_TENANT_ID"),
            "client_id": os.environ.get("PP_DATAVERSE_CLIENT_ID"),
            "client_secret": os.environ.get("PP_DATAVERSE_CLIENT_SECRET"),
            "api_version": os.environ.get("PP_DATAVERSE_API_VERSION", "9.2"),
        },
        "powerapps": {
            "url": os.environ.get("PP_POWERAPPS_URL"),
            "environment_id": os.environ.get("PP_POWERAPPS_ENVIRONMENT_ID"),
        },
        "test": {
            "timeout": int(os.environ.get("PP_TEST_TIMEOUT", "120")),
            "retry_attempts": int(os.environ.get("PP_TEST_RETRY_ATTEMPTS", "3")),
            "cleanup_after_test": os.environ.get("PP_TEST_CLEANUP", "true").lower() == "true",
        },
    }


# =============================================================================
# 认证管理
# =============================================================================

@pytest.fixture(scope="session")
def auth_token(integration_config):
    """
    获取认证令牌

    此fixture仅在设置了认证环境变量时返回有效令牌
    """
    dataverse_config = integration_config["dataverse"]

    # 检查是否配置了认证信息
    if not all([
        dataverse_config["url"],
        dataverse_config["tenant_id"],
        dataverse_config["client_id"],
        dataverse_config["client_secret"],
    ]):
        pytest.skip("未配置Dataverse认证信息，设置环境变量以运行此测试")

    # 实际集成测试中，这里会通过OAuth流程获取令牌
    # 测试环境中返回模拟令牌
    return "mock-auth-token"


# =============================================================================
# 测试环境准备
# =============================================================================

@pytest.fixture(scope="function")
def test_environment(integration_config):
    """
    准备测试环境

    创建测试所需的实体、数据等
    """
    config = integration_config

    # 在实际集成测试中，这里会:
    # 1. 连接到Dataverse
    # 2. 创建测试实体
    # 3. 准备测试数据

    created_entities = []

    yield {
        "entities": created_entities,
        "config": config,
    }

    # 清理测试环境
    if config["test"]["cleanup_after_test"]:
        # 删除创建的测试实体
        pass


# =============================================================================
# 重试机制
# =============================================================================

@pytest.fixture(scope="function")
def retry_until_success(integration_config):
    """
    重试直到成功或达到最大尝试次数

    用于处理网络波动等临时性故障
    """
    max_attempts = integration_config["test"]["retry_attempts"]

    def _retry(func, *args, **kwargs):
        last_exception = None
        for attempt in range(max_attempts):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_attempts - 1:
                    time.sleep(2 ** attempt)  # 指数退避
        raise last_exception

    return _retry


# =============================================================================
# 测试数据生成器
# =============================================================================

@pytest.fixture(scope="function")
def test_entity_name():
    """生成唯一的测试实体名称"""
    import uuid
    return f"test_entity_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="function")
def test_account_data():
    """生成测试账户数据"""
    import uuid

    return {
        "name": f"Test Account {uuid.uuid4().hex[:8]}",
        "accountnumber": f"TEST-{uuid.uuid4().hex[:8].upper()}",
        "statecode": 0,
        "statuscode": 1,
    }


@pytest.fixture(scope="function")
def test_contact_data():
    """生成测试联系人数据"""
    import uuid

    return {
        "firstname": f"Test{uuid.uuid4().hex[:4]}",
        "lastname": f"Contact{uuid.uuid4().hex[:4]}",
        "emailaddress1": f"test.{uuid.uuid4().hex[:8]}@example.com",
        "statecode": 0,
        "statuscode": 1,
    }


# =============================================================================
# 跳过条件
# =============================================================================

def skip_if_no_auth():
    """如果没有认证信息则跳过"""
    if not os.environ.get("PP_RUN_AUTH_TESTS"):
        pytest.skip("设置 PP_RUN_AUTH_TESTS=1 来运行需要认证的测试")


def skip_if_no_dataverse():
    """如果没有Dataverse配置则跳过"""
    if not os.environ.get("PP_RUN_DATAVERSE_TESTS"):
        pytest.skip("设置 PP_RUN_DATAVERSE_TESTS=1 来运行需要Dataverse的测试")


def skip_if_slow():
    """如果跳过慢速测试则跳过"""
    if os.environ.get("PP_SKIP_SLOW_TESTS", "true").lower() == "true":
        pytest.skip("慢速测试已跳过（设置 PP_SKIP_SLOW_TESTS=false 来运行）")


# =============================================================================
# 集成测试钩子
# =============================================================================

def pytest_collection_modifyitems(config, items):
    """
    修改集成测试的收集行为

    自动为集成测试添加适当的标记和跳过逻辑
    """
    for item in items:
        # 确保所有集成测试都有integration标记
        if any(item.iter_markers(name=lambda x: x in ["requires_auth", "requires_dataverse", "e2e"])):
            item.add_marker(pytest.mark.integration)

        # 为慢速测试添加slow标记
        if item.nodeid.startswith("test/integration/"):
            # 集成测试通常较慢
            if not item.get_closest_marker("slow"):
                item.add_marker(pytest.mark.slow)


def pytest_report_header(config):
    """添加集成测试信息到报告头"""
    info = []

    if os.environ.get("PP_DATAVERSE_URL"):
        info.append(f"Dataverse URL: {os.environ.get('PP_DATAVERSE_URL')}")

    if os.environ.get("PP_RUN_AUTH_TESTS"):
        info.append("Auth tests: ENABLED")
    else:
        info.append("Auth tests: DISABLED (set PP_RUN_AUTH_TESTS=1)")

    if os.environ.get("PP_RUN_DATAVERSE_TESTS"):
        info.append("Dataverse tests: ENABLED")
    else:
        info.append("Dataverse tests: DISABLED (set PP_RUN_DATAVERSE_TESTS=1)")

    if os.environ.get("PP_SKIP_SLOW_TESTS", "true") == "true":
        info.append("Slow tests: DISABLED (set PP_SKIP_SLOW_TESTS=false)")
    else:
        info.append("Slow tests: ENABLED")

    if info:
        return "\n".join(["", "=" * 70, "Integration Test Configuration", "=" * 70] + info)

    return ""
