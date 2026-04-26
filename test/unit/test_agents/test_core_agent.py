#!/usr/bin/env python3
"""
Power Platform Agent - CoreAgent Unit Tests
测试 CoreAgent 的配置加载和认证功能
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import os

# 添加项目路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "framework"))


@pytest.mark.unit
class TestCoreAgentConfig:
    """测试 CoreAgent 配置加载功能"""

    @pytest.fixture
    def mock_config_files(self, tmp_path):
        """创建模拟配置文件"""
        import yaml

        # 创建 hermes_profile.yaml
        hermes_config = {
            "hermes": {
                "profile_name": "power-platform-dev",
                "version": "1.0.0",
            },
            "environments": {
                "current": "dev"
            },
            "naming": {
                "publisher_prefix": "new",
                "schema_name": {
                    "style": "lowercase",
                    "separator": "_",
                }
            }
        }

        hermes_file = tmp_path / "hermes_profile.yaml"
        with open(hermes_file, "w", encoding="utf-8") as f:
            yaml.dump(hermes_config, f)

        # 创建 environments.yaml
        env_config = {
            "environments": {
                "dev": {
                    "name": "Development",
                    "url": "https://dev.crm.dynamics.com",
                    "client_id": "${DEV_CLIENT_ID}",
                    "client_secret": "${DEV_CLIENT_SECRET}",
                },
                "test": {
                    "name": "Testing",
                    "url": "https://test.crm.dynamics.com",
                    "client_id": "${TEST_CLIENT_ID}",
                    "client_secret": "${TEST_CLIENT_SECRET}",
                }
            },
            "current": "dev"
        }

        env_file = tmp_path / "environments.yaml"
        with open(env_file, "w", encoding="utf-8") as f:
            yaml.dump(env_config, f)

        return {
            "hermes": str(hermes_file),
            "environments": str(env_file)
        }

    @pytest.fixture
    def core_agent(self, mock_config_files):
        """创建 CoreAgent 实例"""
        # 模拟 config/environments.yaml 路径
        with patch("framework.agents.core_agent.Path") as mock_path:
            mock_path.return_value = Path(mock_config_files["environments"])

            from framework.agents.core_agent import CoreAgent

            # 使用模拟的配置路径
            agent = CoreAgent(config_path=mock_config_files["hermes"])
            return agent

    def test_init_loads_config(self, core_agent):
        """测试初始化时加载配置"""
        assert core_agent._config is not None
        assert core_agent._config["hermes"]["profile_name"] == "power-platform-dev"
        assert core_agent._current_environment == "dev"

    def test_init_creates_naming_converter(self, core_agent):
        """测试初始化时创建命名转换器"""
        assert core_agent.naming_converter is not None
        assert hasattr(core_agent.naming_converter, "prefix")

    def test_get_environment_config_default(self, core_agent):
        """测试获取默认环境配置"""
        env_config = core_agent.get_environment_config()
        assert env_config["name"] == "Development"
        assert env_config["url"] == "https://dev.crm.dynamics.com"

    def test_get_environment_config_named(self, core_agent):
        """测试获取指定环境配置"""
        env_config = core_agent.get_environment_config("test")
        assert env_config["name"] == "Testing"
        assert env_config["url"] == "https://test.crm.dynamics.com"

    def test_get_environment_config_nonexistent(self, core_agent):
        """测试获取不存在的环境配置"""
        env_config = core_agent.get_environment_config("production")
        assert env_config == {}

    def test_naming_config_loaded(self, core_agent):
        """测试命名配置已加载"""
        assert core_agent.naming_converter.prefix == "new"


@pytest.mark.unit
class TestCoreAgentAuthentication:
    """测试 CoreAgent 认证功能"""

    @pytest.fixture
    def mock_config_files(self, tmp_path):
        """创建模拟配置文件"""
        import yaml

        # 创建 environments.yaml
        env_config = {
            "environments": {
                "dev": {
                    "name": "Development",
                    "url": "https://dev.crm.dynamics.com",
                    "client_id": "test-client-id",
                    "client_secret": "test-client-secret",
                    "tenant_id": "test-tenant-id",
                }
            },
            "current": "dev"
        }

        env_file = tmp_path / "environments.yaml"
        with open(env_file, "w", encoding="utf-8") as f:
            yaml.dump(env_config, f)

        hermes_file = tmp_path / "hermes_profile.yaml"
        with open(hermes_file, "w", encoding="utf-8") as f:
            yaml.dump({"environments": {"current": "dev"}}, f)

        return {
            "hermes": str(hermes_file),
            "environments": str(env_file)
        }

    @pytest.fixture
    def core_agent(self, mock_config_files):
        """创建 CoreAgent 实例"""
        with patch("framework.agents.core_agent.Path") as mock_path:
            from framework.agents.core_agent import CoreAgent
            agent = CoreAgent(config_path=mock_config_files["hermes"])
            return agent

    @pytest.mark.asyncio
    async def test_login_with_access_token(self, core_agent):
        """测试使用 access_token 登录 (Client 模式)"""
        mock_token = "mock-access-token-12345"

        result = await core_agent.login(access_token=mock_token)

        assert result["success"] is True
        assert result["environment"] == "dev"
        assert result["auth_mode"] == "client_token"
        assert "dev" in core_agent._tokens
        assert core_agent._tokens["dev"] == mock_token
        assert "dev" in core_agent._clients

    @pytest.mark.asyncio
    async def test_login_with_confidential_client(self, core_agent):
        """测试使用 confidential client 登录"""
        mock_msal_response = {
            "access_token": "mock-token-from-msal",
            "expires_in": 3600,
            "token_type": "Bearer"
        }

        with patch("framework.agents.core_agent.msal") as mock_msal:
            mock_app = MagicMock()
            mock_app.acquire_token_for_client.return_value = mock_msal_response
            mock_msal.ConfidentialClientApplication.return_value = mock_app

            result = await core_agent.login(
                environment="dev",
                client_id="test-client-id",
                client_secret="test-client-secret"
            )

            assert result["success"] is True
            assert result["auth_mode"] == "confidential_client"
            assert "dev" in core_agent._tokens
            assert core_agent._tokens["dev"] == mock_msal_response["access_token"]

    @pytest.mark.asyncio
    async def test_login_missing_credentials(self, core_agent):
        """测试缺少凭据时的登录"""
        # 移除环境配置中的凭据
        core_agent._environments = {"environments": {"dev": {"url": "https://dev.crm.dynamics.com"}}}

        result = await core_agent.login(environment="dev")

        assert result["success"] is False
        assert "error" in result
        assert "Missing credentials" in result["error"]

    @pytest.mark.asyncio
    async def test_login_msal_failure(self, core_agent):
        """测试 MSAL 认证失败"""
        mock_msal_response = {
            "error": "invalid_client",
            "error_description": "Invalid client credentials"
        }

        with patch("framework.agents.core_agent.msal") as mock_msal:
            mock_app = MagicMock()
            mock_app.acquire_token_for_client.return_value = mock_msal_response
            mock_msal.ConfidentialClientApplication.return_value = mock_app

            result = await core_agent.login(
                environment="dev",
                client_id="invalid-id",
                client_secret="invalid-secret"
            )

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_logout(self, core_agent):
        """测试登出"""
        # 先登录
        core_agent._tokens["dev"] = "mock-token"
        core_agent._clients["dev"] = MagicMock()

        result = await core_agent.logout("dev")

        assert result["success"] is True
        assert result["environment"] == "dev"
        assert "dev" not in core_agent._tokens
        assert "dev" not in core_agent._clients

    @pytest.mark.asyncio
    async def test_status(self, core_agent):
        """测试获取状态"""
        core_agent._tokens["dev"] = "mock-token"
        core_agent._current_environment = "dev"

        result = await core_agent.status()

        assert result["current_environment"] == "dev"
        assert "dev" in result["authenticated_environments"]
        assert "config" in result


@pytest.mark.unit
class TestCoreAgentEnvironmentSwitch:
    """测试 CoreAgent 环境切换功能"""

    @pytest.fixture
    def mock_config_files(self, tmp_path):
        """创建模拟配置文件"""
        import yaml

        env_config = {
            "environments": {
                "dev": {
                    "name": "Development",
                    "url": "https://dev.crm.dynamics.com",
                },
                "test": {
                    "name": "Testing",
                    "url": "https://test.crm.dynamics.com",
                }
            },
            "current": "dev"
        }

        env_file = tmp_path / "environments.yaml"
        with open(env_file, "w", encoding="utf-8") as f:
            yaml.dump(env_config, f)

        hermes_file = tmp_path / "hermes_profile.yaml"
        with open(hermes_file, "w", encoding="utf-8") as f:
            yaml.dump({"environments": {"current": "dev"}}, f)

        return {
            "hermes": str(hermes_file),
            "environments": str(env_file)
        }

    @pytest.fixture
    def core_agent(self, mock_config_files):
        """创建 CoreAgent 实例"""
        from framework.agents.core_agent import CoreAgent
        agent = CoreAgent(config_path=mock_config_files["hermes"])
        return agent

    @pytest.mark.asyncio
    async def test_switch_environment_valid(self, core_agent):
        """测试切换到有效环境"""
        result = await core_agent.switch_environment("test")

        assert result["success"] is True
        assert result["current_environment"] == "test"
        assert core_agent._current_environment == "test"

    @pytest.mark.asyncio
    async def test_switch_environment_invalid(self, core_agent):
        """测试切换到无效环境"""
        result = await core_agent.switch_environment("production")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_list_environments(self, core_agent):
        """测试列出所有环境"""
        result = await core_agent.list_environments()

        assert len(result) == 2
        env_names = [env["name"] for env in result]
        assert "dev" in env_names
        assert "test" in env_names


@pytest.mark.unit
class TestCoreAgentGetClient:
    """测试 CoreAgent 客户端获取功能"""

    @pytest.fixture
    def core_agent(self):
        """创建 CoreAgent 实例"""
        from framework.agents.core_agent import CoreAgent

        # 使用模拟配置
        with patch("framework.agents.core_agent.CoreAgent._load_config"):
            agent = CoreAgent()
            agent._environments = {
                "environments": {
                    "dev": {"url": "https://dev.crm.dynamics.com"}
                }
            }
            agent._current_environment = "dev"
            return agent

    def test_get_client_authenticated(self, core_agent):
        """测试获取已认证环境的客户端"""
        from framework.utils.dataverse_client import DataverseClient

        core_agent._tokens["dev"] = "mock-token"
        core_agent._clients["dev"] = DataverseClient("dev", access_token="mock-token")

        client = core_agent.get_client("dev")

        assert client is not None
        assert isinstance(client, DataverseClient)

    def test_get_client_not_authenticated(self, core_agent):
        """测试获取未认证环境的客户端"""
        from framework.utils.dataverse_client import AuthenticationError

        with pytest.raises(AuthenticationError):
            core_agent.get_client("dev")

    def test_get_client_creates_from_token(self, core_agent):
        """测试从 token 创建客户端"""
        from framework.utils.dataverse_client import DataverseClient

        core_agent._tokens["dev"] = "mock-token"

        client = core_agent.get_client("dev")

        assert client is not None
        assert isinstance(client, DataverseClient)
        assert "dev" in core_agent._clients


@pytest.mark.unit
class TestCoreAgentNaming:
    """测试 CoreAgent 命名转换功能"""

    @pytest.fixture
    def core_agent(self):
        """创建 CoreAgent 实例"""
        from framework.agents.core_agent import CoreAgent

        agent = CoreAgent()
        return agent

    @pytest.mark.asyncio
    async def test_convert_name_schema_name(self, core_agent):
        """测试转换 schema_name"""
        result = await core_agent.convert_name("MyTestEntity", type="schema_name")

        assert result is not None
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_convert_name_webresource(self, core_agent):
        """测试转换 webresource 名称"""
        result = await core_agent.convert_name("account", type="webresource")

        assert result is not None
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_validate_name_valid(self, core_agent):
        """测试验证有效名称"""
        is_valid, error = await core_agent.validate_name("new_my_entity", type="schema_name")

        assert is_valid is True
        assert error is None

    @pytest.mark.asyncio
    async def test_bulk_convert_names(self, core_agent):
        """测试批量转换名称"""
        items = [
            {"name": "MyEntity", "is_standard": False},
            {"name": "AnotherEntity", "is_standard": False},
        ]

        result = await core_agent.bulk_convert_names(items, type="schema_name")

        assert len(result) == 2
        assert all("name" in item for item in result)

    @pytest.mark.asyncio
    async def test_list_naming_rules(self, core_agent):
        """测试列出命名规则"""
        result = await core_agent.list_naming_rules()

        assert "prefix" in result
        assert "schema_name" in result
        assert "webresource" in result


@pytest.mark.unit
class TestCoreAgentHealthCheck:
    """测试 CoreAgent 健康检查功能"""

    @pytest.fixture
    def core_agent(self):
        """创建 CoreAgent 实例"""
        from framework.agents.core_agent import CoreAgent

        agent = CoreAgent()
        agent._current_environment = "dev"
        return agent

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, core_agent):
        """测试健康检查 - 健康"""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        core_agent._clients["dev"] = mock_client
        core_agent._tokens["dev"] = "mock-token"

        result = await core_agent.health_check()

        assert result["status"] == "healthy"
        assert result["authenticated"] is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, core_agent):
        """测试健康检查 - 不健康"""
        mock_client = MagicMock()
        mock_client.ping.return_value = False
        core_agent._clients["dev"] = mock_client
        core_agent._tokens["dev"] = "mock-token"

        result = await core_agent.health_check()

        assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_check_unauthenticated(self, core_agent):
        """测试健康检查 - 未认证"""
        result = await core_agent.health_check()

        assert result["status"] == "unauthenticated"
        assert result["authenticated"] is False


@pytest.mark.unit
class TestToolHandler:
    """测试 ToolHandler 工具处理功能"""

    @pytest.fixture
    def core_agent(self):
        """创建 CoreAgent 实例"""
        from framework.agents.core_agent import CoreAgent
        agent = CoreAgent()
        return agent

    @pytest.fixture
    def tool_handler(self, core_agent):
        """创建 ToolHandler 实例"""
        from framework.agents.core_agent import ToolHandler
        return ToolHandler(core_agent)

    @pytest.mark.asyncio
    async def test_handle_auth_status(self, tool_handler, core_agent):
        """测试 auth_status 工具"""
        core_agent._current_environment = "dev"
        core_agent._tokens = {"dev": "mock-token"}

        result = await tool_handler.handle_tool("auth_status", {})

        assert "success" in result or "current_environment" in result

    @pytest.mark.asyncio
    async def test_handle_environment_list(self, tool_handler, core_agent):
        """测试 environment_list 工具"""
        core_agent._environments = {
            "environments": {
                "dev": {"name": "Development", "url": "https://dev.crm.dynamics.com"}
            }
        }
        core_agent._current_environment = "dev"

        result = await tool_handler.handle_tool("environment_list", {})

        assert result is not None

    @pytest.mark.asyncio
    async def test_handle_naming_convert(self, tool_handler):
        """测试 naming_convert 工具"""
        result = await tool_handler.handle_tool("naming_convert", {
            "input": "MyEntity",
            "type": "schema_name",
            "is_standard": False
        })

        assert result is not None
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_handle_unknown_tool(self, tool_handler):
        """测试未知工具"""
        result = await tool_handler.handle_tool("unknown_tool", {})

        assert "Unknown tool" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
