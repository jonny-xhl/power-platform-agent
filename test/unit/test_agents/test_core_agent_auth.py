#!/usr/bin/env python3
"""
Power Platform Agent - CoreAgent Comprehensive Unit Tests
测试 CoreAgent 的核心功能：认证、环境切换、命名转换

所有测试使用 mock，不连接真实环境，可独立运行。
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import yaml

# 添加项目路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "framework"))


# ==================== Fixtures ====================

@pytest.fixture
def mock_config_files(tmp_path):
    """创建模拟配置文件"""
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
            "prefix": "new",
            "schema_name": {
                "style": "lowercase",
                "separator": "_",
                "auto_prefix": True
            },
            "webresource": {
                "prefix": "new_",
                "naming_pattern": "{prefix}{category}/{name}.{ext}"
            },
            "validation": {
                "schema_name": {
                    "max_length": 100,
                    "min_length": 2,
                    "forbidden_chars": [" ", "-", "."],
                    "must_start_with": "letter",
                    "allowed_pattern": r"^[a-zA-Z][a-zA-Z0-9_]*$"
                },
                "webresource_name": {
                    "max_length": 256,
                    "forbidden_chars": [],
                    "allowed_pattern": r"^[a-zA-Z0-9_./-]+$"
                }
            },
            "standard_entities": [
                "account", "contact", "opportunity", "lead",
                "activitypointer", "systemuser", "team", "businessunit"
            ]
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
                "client_id": "dev-client-id",
                "client_secret": "dev-client-secret",
                "tenant_id": "dev-tenant-id"
            },
            "test": {
                "name": "Testing",
                "url": "https://test.crm.dynamics.com",
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",
                "tenant_id": "test-tenant-id"
            },
            "production": {
                "name": "Production",
                "url": "https://prod.crm.dynamics.com",
                "client_id": "prod-client-id",
                "client_secret": "prod-client-secret"
            }
        }
    }

    env_file = tmp_path / "environments.yaml"
    with open(env_file, "w", encoding="utf-8") as f:
        yaml.dump(env_config, f)

    return {
        "hermes": str(hermes_file),
        "environments": str(env_file)
    }


@pytest.fixture
def core_agent(mock_config_files):
    """创建 CoreAgent 实例，使用模拟配置"""
    with patch("framework.agents.core_agent.Path") as mock_path:
        # 模拟 Path 行为
        original_path = Path

        def path_wrapper(arg):
            if "environments.yaml" in str(arg):
                return original_path(mock_config_files["environments"])
            return original_path(arg)

        mock_path.side_effect = path_wrapper

        from framework.agents.core_agent import CoreAgent
        agent = CoreAgent(config_path=mock_config_files["hermes"])
        return agent


# ==================== 1. 认证测试 ====================

@pytest.mark.unit
class TestCoreAgentAuthentication:
    """测试 CoreAgent 认证功能"""

    @pytest.mark.asyncio
    async def test_login_with_access_token_success(self, core_agent):
        """测试使用 access_token 登录成功"""
        mock_token = "eyJ0eXAiOiJKV1QiLCJhbGcOiJIUzI1NiJ9.test-token"

        result = await core_agent.login(
            environment="dev",
            access_token=mock_token
        )

        assert result["success"] is True
        assert result["environment"] == "dev"
        assert result["auth_mode"] == "client_token"
        assert result["url"] == "https://dev.crm.dynamics.com"
        assert "dev" in core_agent._tokens
        assert core_agent._tokens["dev"] == mock_token
        assert core_agent._current_environment == "dev"

    @pytest.mark.asyncio
    async def test_login_with_access_token_default_environment(self, core_agent):
        """测试使用 access_token 登录默认环境"""
        mock_token = "test-token-123"

        result = await core_agent.login(access_token=mock_token)

        assert result["success"] is True
        assert result["environment"] == "dev"  # 默认环境

    @pytest.mark.asyncio
    async def test_login_with_access_token_creates_client(self, core_agent):
        """测试 access_token 登录会创建 DataverseClient"""
        mock_token = "test-token-client"

        with patch("framework.agents.core_agent.DataverseClient") as mock_client_class:
            mock_instance = MagicMock()
            mock_client_class.return_value = mock_instance

            await core_agent.login(access_token=mock_token)

            # 验证客户端被正确创建
            assert "dev" in core_agent._clients
            mock_client_class.assert_called_once_with("dev", access_token=mock_token)

    @pytest.mark.asyncio
    async def test_login_confidential_client_success(self, core_agent):
        """测试使用 confidential client 认证成功"""
        mock_msal_response = {
            "access_token": "msal-acquired-token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "expires_on": 1234567890
        }

        with patch("framework.agents.core_agent.msal") as mock_msal:
            mock_app = MagicMock()
            mock_app.acquire_token_for_client.return_value = mock_msal_response
            mock_msal.ConfidentialClientApplication.return_value = mock_app

            result = await core_agent.login(
                environment="test",
                client_id="test-client-id",
                client_secret="test-client-secret"
            )

            assert result["success"] is True
            assert result["auth_mode"] == "confidential_client"
            assert result["expires_in"] == 3600
            assert "test" in core_agent._tokens
            assert core_agent._tokens["test"] == mock_msal_response["access_token"]

    @pytest.mark.asyncio
    async def test_login_confidential_client_with_tenant_id(self, core_agent):
        """测试使用指定 tenant_id 的 confidential client 认证"""
        mock_msal_response = {
            "access_token": "token-with-tenant",
            "expires_in": 7200
        }

        with patch("framework.agents.core_agent.msal") as mock_msal:
            mock_app = MagicMock()
            mock_app.acquire_token_for_client.return_value = mock_msal_response
            mock_msal.ConfidentialClientApplication.return_value = mock_app

            result = await core_agent.login(
                environment="dev",
                client_id="custom-client-id",
                client_secret="custom-secret",
                tenant_id="custom-tenant-id"
            )

            assert result["success"] is True
            # 验证使用了正确的 authority
            expected_authority = "https://login.microsoftonline.com/custom-tenant-id"
            mock_msal.ConfidentialClientApplication.assert_called_once()
            call_kwargs = mock_msal.ConfidentialClientApplication.call_args[1]
            assert call_kwargs["authority"] == expected_authority

    @pytest.mark.asyncio
    async def test_login_confidential_client_no_tenant_id(self, core_agent):
        """测试没有 tenant_id 时使用 organizations 端点"""
        mock_msal_response = {
            "access_token": "token-organizations",
            "expires_in": 3600
        }

        with patch("framework.agents.core_agent.msal") as mock_msal:
            mock_app = MagicMock()
            mock_app.acquire_token_for_client.return_value = mock_msal_response
            mock_msal.ConfidentialClientApplication.return_value = mock_app

            # 使用没有 tenant_id 的环境
            core_agent._environments["environments"]["no_tenant"] = {
                "name": "No Tenant",
                "url": "https://notenant.crm.dynamics.com",
                "client_id": "no-tenant-client",
                "client_secret": "no-tenant-secret"
            }

            result = await core_agent.login(
                environment="no_tenant",
                client_id="no-tenant-client",
                client_secret="no-tenant-secret"
            )

            assert result["success"] is True
            # 验证使用 organizations 端点
            call_kwargs = mock_msal.ConfidentialClientApplication.call_args[1]
            assert call_kwargs["authority"] == "https://login.microsoftonline.com/organizations"

    @pytest.mark.asyncio
    async def test_login_missing_credentials(self, core_agent):
        """测试缺少凭据时登录失败"""
        # 清空环境配置中的凭据
        core_agent._environments["environments"]["dev"] = {
            "name": "Dev",
            "url": "https://dev.crm.dynamics.com"
        }

        result = await core_agent.login(environment="dev")

        assert result["success"] is False
        assert "error" in result
        assert "Missing credentials" in result["error"]

    @pytest.mark.asyncio
    async def test_login_msal_authentication_failed(self, core_agent):
        """测试 MSAL 认证失败"""
        mock_msal_response = {
            "error": "invalid_grant",
            "error_description": "AADSTS700016: Application with identifier was not found"
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
            assert "AADSTS700016" in result["error"]

    @pytest.mark.asyncio
    async def test_login_exception_handling(self, core_agent):
        """测试登录过程中的异常处理"""
        with patch("framework.agents.core_agent.msal") as mock_msal:
            mock_msal.ConfidentialClientApplication.side_effect = Exception("Network error")

            result = await core_agent.login(
                environment="dev",
                client_id="test-id",
                client_secret="test-secret"
            )

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_logout_success(self, core_agent):
        """测试登出成功"""
        # 先模拟登录状态
        core_agent._tokens["dev"] = "test-token"
        core_agent._clients["dev"] = MagicMock()

        result = await core_agent.logout(environment="dev")

        assert result["success"] is True
        assert result["environment"] == "dev"
        assert "dev" not in core_agent._tokens
        assert "dev" not in core_agent._clients

    @pytest.mark.asyncio
    async def test_logout_default_environment(self, core_agent):
        """测试登出默认环境"""
        core_agent._current_environment = "test"
        core_agent._tokens["test"] = "test-token"
        core_agent._clients["test"] = MagicMock()

        result = await core_agent.logout()

        assert result["success"] is True
        assert "test" not in core_agent._tokens

    @pytest.mark.asyncio
    async def test_logout_nonexistent_environment(self, core_agent):
        """测试登出不存在的环境（不应该报错）"""
        result = await core_agent.logout(environment="nonexistent")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_status_authenticated(self, core_agent):
        """测试获取认证状态 - 已认证"""
        core_agent._tokens["dev"] = "dev-token"
        core_agent._tokens["test"] = "test-token"
        core_agent._current_environment = "dev"

        result = await core_agent.status()

        assert result["current_environment"] == "dev"
        assert set(result["authenticated_environments"]) == {"dev", "test"}
        assert "config" in result
        assert result["config"]["naming_prefix"] == "new"

    @pytest.mark.asyncio
    async def test_status_not_authenticated(self, core_agent):
        """测试获取认证状态 - 未认证"""
        core_agent._tokens = {}
        core_agent._current_environment = "dev"

        result = await core_agent.status()

        assert result["current_environment"] == "dev"
        assert result["authenticated_environments"] == []

    @pytest.mark.asyncio
    async def test_status_naming_config(self, core_agent):
        """测试状态中的命名配置"""
        result = await core_agent.status()

        assert "config" in result
        assert result["config"]["naming_prefix"] == "new"
        assert result["config"]["schema_name_style"] == "lowercase"

    @pytest.mark.asyncio
    async def test_login_multiple_environments(self, core_agent):
        """测试登录多个环境"""
        with patch("framework.agents.core_agent.DataverseClient"):
            # 登录第一个环境
            result1 = await core_agent.login(
                environment="dev",
                access_token="dev-token"
            )
            assert result1["success"] is True

            # 登录第二个环境
            result2 = await core_agent.login(
                environment="test",
                access_token="test-token"
            )
            assert result2["success"] is True

            # 验证两个环境都已认证
            assert "dev" in core_agent._tokens
            assert "test" in core_agent._tokens
            assert core_agent._tokens["dev"] == "dev-token"
            assert core_agent._tokens["test"] == "test-token"

    @pytest.mark.asyncio
    async def test_login_preserves_existing_tokens(self, core_agent):
        """测试新登录不影响已有环境的 token"""
        with patch("framework.agents.core_agent.DataverseClient"):
            # 先登录 dev
            await core_agent.login(environment="dev", access_token="dev-token")

            # 再登录 test
            await core_agent.login(environment="test", access_token="test-token")

            # dev 的 token 应该还在
            assert core_agent._tokens["dev"] == "dev-token"
            assert core_agent._tokens["test"] == "test-token"


# ==================== 2. 环境测试 ====================

@pytest.mark.unit
class TestCoreAgentEnvironment:
    """测试 CoreAgent 环境功能"""

    @pytest.mark.asyncio
    async def test_get_environment_config_default(self, core_agent):
        """测试获取默认环境配置"""
        config = core_agent.get_environment_config()

        assert config["name"] == "Development"
        assert config["url"] == "https://dev.crm.dynamics.com"
        assert config["client_id"] == "dev-client-id"

    @pytest.mark.asyncio
    async def test_get_environment_config_named(self, core_agent):
        """测试获取指定环境配置"""
        config = core_agent.get_environment_config("test")

        assert config["name"] == "Testing"
        assert config["url"] == "https://test.crm.dynamics.com"
        assert config["client_id"] == "test-client-id"

    @pytest.mark.asyncio
    async def test_get_environment_config_nonexistent(self, core_agent):
        """测试获取不存在的环境配置"""
        config = core_agent.get_environment_config("staging")

        assert config == {}

    @pytest.mark.asyncio
    async def test_get_environment_config_production(self, core_agent):
        """测试获取生产环境配置"""
        config = core_agent.get_environment_config("production")

        assert config["name"] == "Production"
        assert config["url"] == "https://prod.crm.dynamics.com"
        assert config["client_id"] == "prod-client-id"

    @pytest.mark.asyncio
    async def test_switch_environment_success(self, core_agent):
        """测试切换到有效环境"""
        result = await core_agent.switch_environment("test")

        assert result["success"] is True
        assert result["current_environment"] == "test"
        assert result["authenticated"] is False
        assert core_agent._current_environment == "test"

    @pytest.mark.asyncio
    async def test_switch_environment_authenticated(self, core_agent):
        """测试切换到已认证的环境"""
        # 预先设置 token
        core_agent._tokens["test"] = "test-token"

        with patch("framework.agents.core_agent.DataverseClient"):
            result = await core_agent.switch_environment("test")

            assert result["success"] is True
            assert result["authenticated"] is True
            assert "test" in core_agent._clients

    @pytest.mark.asyncio
    async def test_switch_environment_invalid(self, core_agent):
        """测试切换到无效环境"""
        result = await core_agent.switch_environment("invalid-env")

        assert result["success"] is False
        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_switch_environment_creates_client_when_authenticated(self, core_agent):
        """测试切换到已认证环境时创建客户端"""
        core_agent._tokens["test"] = "test-token"

        with patch("framework.agents.core_agent.DataverseClient") as mock_client_class:
            await core_agent.switch_environment("test")

            mock_client_class.assert_called_once_with("test", access_token="test-token")

    @pytest.mark.asyncio
    async def test_list_environments(self, core_agent):
        """测试列出所有环境"""
        result = await core_agent.list_environments()

        assert len(result) == 3
        env_names = [env["name"] for env in result]
        assert "dev" in env_names
        assert "test" in env_names
        assert "production" in env_names

    @pytest.mark.asyncio
    async def test_list_environments_with_current_flag(self, core_agent):
        """测试列出环境时标记当前环境"""
        result = await core_agent.list_environments()

        current_envs = [env for env in result if env["is_current"]]
        assert len(current_envs) == 1
        assert current_envs[0]["name"] == "dev"

    @pytest.mark.asyncio
    async def test_list_environments_with_authenticated_flag(self, core_agent):
        """测试列出环境时标记已认证环境"""
        core_agent._tokens["test"] = "test-token"

        result = await core_agent.list_environments()

        authenticated = [env for env in result if env["is_authenticated"]]
        assert len(authenticated) == 1
        assert authenticated[0]["name"] == "test"

    @pytest.mark.asyncio
    async def test_list_environments_structure(self, core_agent):
        """测试列出环境的返回结构"""
        result = await core_agent.list_environments()

        for env in result:
            assert "name" in env
            assert "display_name" in env
            assert "url" in env
            assert "is_current" in env
            assert "is_authenticated" in env

    @pytest.mark.asyncio
    async def test_switch_then_list_reflects_current(self, core_agent):
        """测试切换环境后列表反映当前环境"""
        # 初始状态
        result1 = await core_agent.list_environments()
        assert [e["name"] for e in result1 if e["is_current"]] == ["dev"]

        # 切换环境
        await core_agent.switch_environment("test")

        # 验证列表已更新
        result2 = await core_agent.list_environments()
        assert [e["name"] for e in result2 if e["is_current"]] == ["test"]


# ==================== 3. 命名转换测试 ====================

@pytest.mark.unit
class TestCoreAgentNamingConversion:
    """测试 CoreAgent 命名转换功能"""

    @pytest.mark.asyncio
    async def test_convert_schema_name_custom_entity(self, core_agent):
        """测试转换自定义实体 schema_name"""
        result = await core_agent.convert_name(
            name="MyTestEntity",
            type="schema_name",
            is_standard=False
        )

        assert "new" in result.lower()  # 应该包含前缀
        assert "mytestentity" in result.lower()

    @pytest.mark.asyncio
    async def test_convert_schema_name_standard_entity(self, core_agent):
        """测试转换标准实体 schema_name"""
        result = await core_agent.convert_name(
            name="Account",
            type="schema_name",
            is_standard=True
        )

        # 标准实体不加前缀
        assert "new_" not in result.lower()

    @pytest.mark.asyncio
    async def test_convert_schema_name_already_prefixed(self, core_agent):
        """测试已有前缀的名称不再重复添加"""
        result = await core_agent.convert_name(
            name="new_MyEntity",
            type="schema_name",
            is_standard=False
        )

        # 不应该重复前缀
        assert result.count("new_") == 1

    @pytest.mark.asyncio
    async def test_convert_schema_name_pascal_case(self, core_agent):
        """测试 PascalCase 转换"""
        result = await core_agent.convert_name(
            name="CustomerOrder",
            type="schema_name",
            is_standard=False
        )

        assert "_" in result or result.islower()

    @pytest.mark.asyncio
    async def test_convert_webresource_name(self, core_agent):
        """测试转换 Web Resource 名称"""
        result = await core_agent.convert_name(
            name="account",
            type="webresource"
        )

        assert "new_" in result
        assert "css" in result or "js" in result  # 默认类型

    @pytest.mark.asyncio
    async def test_convert_unknown_type(self, core_agent):
        """测试转换未知类型返回原名称"""
        result = await core_agent.convert_name(
            name="OriginalName",
            type="unknown"
        )

        assert result == "OriginalName"

    @pytest.mark.asyncio
    async def test_validate_schema_name_valid(self, core_agent):
        """测试验证有效的 schema_name"""
        is_valid, error = await core_agent.validate_name(
            name="new_my_entity",
            type="schema_name"
        )

        assert is_valid is True
        assert error is None

    @pytest.mark.asyncio
    async def test_validate_schema_name_too_short(self, core_agent):
        """测试验证过短的 schema_name"""
        is_valid, error = await core_agent.validate_name(
            name="a",
            type="schema_name"
        )

        assert is_valid is False
        assert error is not None
        assert "minimum length" in error.lower()

    @pytest.mark.asyncio
    async def test_validate_schema_name_too_long(self, core_agent):
        """测试验证过长的 schema_name"""
        long_name = "a" * 101
        is_valid, error = await core_agent.validate_name(
            name=long_name,
            type="schema_name"
        )

        assert is_valid is False
        assert error is not None
        assert "maximum length" in error.lower()

    @pytest.mark.asyncio
    async def test_validate_schema_name_forbidden_chars(self, core_agent):
        """测试验证包含禁止字符的 schema_name"""
        is_valid, error = await core_agent.validate_name(
            name="new my-entity",
            type="schema_name"
        )

        assert is_valid is False
        assert error is not None
        assert "forbidden" in error.lower() or "character" in error.lower()

    @pytest.mark.asyncio
    async def test_validate_schema_name_starts_with_number(self, core_agent):
        """测试验证以数字开头的 schema_name"""
        is_valid, error = await core_agent.validate_name(
            name="1_invalid_name",
            type="schema_name"
        )

        assert is_valid is False
        assert error is not None
        assert "start with a letter" in error.lower()

    @pytest.mark.asyncio
    async def test_validate_webresource_name_valid(self, core_agent):
        """测试验证有效的 webresource_name"""
        is_valid, error = await core_agent.validate_name(
            name="new_css/account.js",
            type="webresource"
        )

        assert is_valid is True
        assert error is None

    @pytest.mark.asyncio
    async def test_validate_webresource_name_too_long(self, core_agent):
        """测试验证过长的 webresource_name"""
        long_name = "a" * 257
        is_valid, error = await core_agent.validate_name(
            name=long_name,
            type="webresource"
        )

        assert is_valid is False
        assert error is not None

    @pytest.mark.asyncio
    async def test_bulk_convert_names_empty_list(self, core_agent):
        """测试批量转换空列表"""
        result = await core_agent.bulk_convert_names(
            items=[],
            type="schema_name"
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_bulk_convert_names_single_item(self, core_agent):
        """测试批量转换单个项"""
        items = [{"name": "MyEntity", "is_standard": False}]

        result = await core_agent.bulk_convert_names(
            items=items,
            type="schema_name"
        )

        assert len(result) == 1
        assert "name" in result[0]
        assert result[0]["name"] != items[0]["name"]  # 应该被转换

    @pytest.mark.asyncio
    async def test_bulk_convert_names_multiple_items(self, core_agent):
        """测试批量转换多个项"""
        items = [
            {"name": "EntityOne", "is_standard": False},
            {"name": "EntityTwo", "is_standard": False},
            {"name": "EntityThree", "is_standard": True}
        ]

        result = await core_agent.bulk_convert_names(
            items=items,
            type="schema_name"
        )

        assert len(result) == 3
        # 前两个应该有前缀
        assert "new" in result[0]["name"].lower()
        assert "new" in result[1]["name"].lower()
        # 第三个是标准实体，不应该有前缀
        assert "entitythree" in result[2]["name"].lower()

    @pytest.mark.asyncio
    async def test_bulk_convert_names_preserves_other_fields(self, core_agent):
        """测试批量转换保留其他字段"""
        items = [
            {"name": "MyEntity", "is_standard": False, "description": "Test", "other": "value"}
        ]

        result = await core_agent.bulk_convert_names(
            items=items,
            type="schema_name"
        )

        assert result[0]["description"] == "Test"
        assert result[0]["other"] == "value"

    @pytest.mark.asyncio
    async def test_bulk_convert_names_attribute_type(self, core_agent):
        """测试批量转换属性名称"""
        items = [
            {"name": "MyField", "entity": "account"}
        ]

        result = await core_agent.bulk_convert_names(
            items=items,
            type="attribute"
        )

        assert len(result) == 1
        # account 是标准实体，属性可能不加前缀

    @pytest.mark.asyncio
    async def test_list_naming_rules(self, core_agent):
        """测试列出命名规则"""
        result = await core_agent.list_naming_rules()

        assert "prefix" in result
        assert "schema_name" in result
        assert "webresource" in result
        assert result["prefix"] == "new"
        assert result["schema_name"]["style"] == "lowercase"
        assert result["schema_name"]["separator"] == "_"

    @pytest.mark.asyncio
    async def test_list_naming_rules_standard_entities(self, core_agent):
        """测试命名规则包含标准实体数量"""
        result = await core_agent.list_naming_rules()

        assert "standard_entities_count" in result
        assert result["standard_entities_count"] > 0


# ==================== 4. 集成测试 ====================

@pytest.mark.unit
class TestCoreAgentIntegration:
    """测试 CoreAgent 集成场景"""

    @pytest.mark.asyncio
    async def test_full_authentication_flow(self, core_agent):
        """测试完整的认证流程"""
        with patch("framework.agents.core_agent.DataverseClient"):
            # 1. 登录
            login_result = await core_agent.login(
                environment="dev",
                access_token="test-token"
            )
            assert login_result["success"] is True

            # 2. 检查状态
            status = await core_agent.status()
            assert "dev" in status["authenticated_environments"]

            # 3. 登出
            logout_result = await core_agent.logout("dev")
            assert logout_result["success"] is True

            # 4. 再次检查状态
            status_after = await core_agent.status()
            assert "dev" not in status_after["authenticated_environments"]

    @pytest.mark.asyncio
    async def test_environment_switch_flow(self, core_agent):
        """测试环境切换流程"""
        with patch("framework.agents.core_agent.DataverseClient"):
            # 1. 认证第一个环境
            await core_agent.login(environment="dev", access_token="dev-token")

            # 2. 列出环境
            env_list = await core_agent.list_environments()
            dev_env = next(e for e in env_list if e["name"] == "dev")
            assert dev_env["is_current"] is True
            assert dev_env["is_authenticated"] is True

            # 3. 切换环境
            switch_result = await core_agent.switch_environment("test")
            assert switch_result["success"] is True

            # 4. 认证新环境
            await core_agent.login(environment="test", access_token="test-token")

            # 5. 再次列出环境
            env_list_after = await core_agent.list_environments()
            test_env = next(e for e in env_list_after if e["name"] == "test")
            assert test_env["is_current"] is True
            assert test_env["is_authenticated"] is True

    @pytest.mark.asyncio
    async def test_naming_conversion_validation_flow(self, core_agent):
        """测试命名转换和验证流程"""
        # 1. 转换名称
        converted = await core_agent.convert_name(
            name="MyCustomEntity",
            type="schema_name",
            is_standard=False
        )

        # 2. 验证转换后的名称
        is_valid, error = await core_agent.validate_name(
            name=converted,
            type="schema_name"
        )

        assert is_valid is True
        assert error is None

    @pytest.mark.asyncio
    async def test_get_client_after_login(self, core_agent):
        """测试登录后获取客户端"""
        with patch("framework.agents.core_agent.DataverseClient") as mock_client_class:
            mock_instance = MagicMock()
            mock_client_class.return_value = mock_instance

            # 登录
            await core_agent.login(environment="dev", access_token="test-token")

            # 获取客户端
            client = core_agent.get_client("dev")

            assert client is not None
            assert client == mock_instance

    @pytest.mark.asyncio
    async def test_get_client_without_login_raises_error(self, core_agent):
        """测试未登录获取客户端抛出异常"""
        from framework.utils.dataverse_client import AuthenticationError

        with pytest.raises(AuthenticationError):
            core_agent.get_client("dev")

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, core_agent):
        """测试健康检查 - 健康"""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        core_agent._clients["dev"] = mock_client
        core_agent._tokens["dev"] = "test-token"

        result = await core_agent.health_check("dev")

        assert result["status"] == "healthy"
        assert result["authenticated"] is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, core_agent):
        """测试健康检查 - 不健康"""
        mock_client = MagicMock()
        mock_client.ping.return_value = False
        core_agent._clients["dev"] = mock_client
        core_agent._tokens["dev"] = "test-token"

        result = await core_agent.health_check("dev")

        assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_check_unauthenticated(self, core_agent):
        """测试健康检查 - 未认证"""
        result = await core_agent.health_check("dev")

        assert result["status"] == "unauthenticated"
        assert result["authenticated"] is False


# ==================== 5. 边界和异常测试 ====================

@pytest.mark.unit
class TestCoreAgentEdgeCases:
    """测试 CoreAgent 边界情况和异常处理"""

    @pytest.mark.asyncio
    async def test_login_empty_access_token(self, core_agent):
        """测试使用空的 access_token"""
        with patch("framework.agents.core_agent.DataverseClient"):
            result = await core_agent.login(access_token="")

            # 空字符串仍然是一个有效的 token（虽然不是真的）
            # 只是测试不会崩溃
            assert "success" in result

    @pytest.mark.asyncio
    async def test_convert_empty_name(self, core_agent):
        """测试转换空名称"""
        result = await core_agent.convert_name(
            name="",
            type="schema_name"
        )

        # 应该返回空或只包含前缀
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_convert_special_characters(self, core_agent):
        """测试转换包含特殊字符的名称"""
        result = await core_agent.convert_name(
            name="Entity@#$",
            type="schema_name"
        )

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_validate_empty_name(self, core_agent):
        """测试验证空名称"""
        is_valid, error = await core_agent.validate_name(
            name="",
            type="schema_name"
        )

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_list_environments_when_empty(self, core_agent):
        """测试环境列表为空时"""
        core_agent._environments = {"environments": {}}

        result = await core_agent.list_environments()

        assert result == []

    @pytest.mark.asyncio
    async def test_switch_to_empty_environment_name(self, core_agent):
        """测试切换到空环境名"""
        result = await core_agent.switch_environment("")

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_multiple_logout_same_environment(self, core_agent):
        """测试多次登出同一环境"""
        core_agent._tokens["dev"] = "token"

        # 第一次登出
        result1 = await core_agent.logout("dev")
        assert result1["success"] is True

        # 第二次登出（不应该报错）
        result2 = await core_agent.logout("dev")
        assert result2["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
