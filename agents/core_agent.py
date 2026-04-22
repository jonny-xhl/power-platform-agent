"""
Power Platform Agent - 核心代理
处理认证、环境切换和核心功能
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import msal
from utils.dataverse_client import DataverseClient, AuthenticationError
from utils.naming_converter import NamingConverter

# 设置日志
logger = logging.getLogger(__name__)


class CoreAgent:
    """核心代理 - 处理认证、环境和命名"""

    def __init__(self, config_path: str = "config/hermes_profile.yaml"):
        """
        初始化核心代理

        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self._config = None
        self._environments = None
        self._current_environment = None
        self._tokens = {}
        self._clients = {}

        # 初始化命名转换器
        self.naming_converter = NamingConverter()

        self._load_config()

    # ==================== 配置管理 ====================

    def _load_config(self) -> None:
        """加载配置"""
        import yaml
        config_file = Path(self.config_path)
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)

            # 加载环境配置
            env_config = self._config.get("environments", {})
            self._current_environment = env_config.get("current", "dev")

            # 加载环境配置详情
            env_file = Path("config/environments.yaml")
            if env_file.exists():
                with open(env_file, "r", encoding="utf-8") as f:
                    self._environments = yaml.safe_load(f)
        else:
            self._config = {"environments": {}}
            self._environments = {"environments": {}}

    def get_environment_config(self, environment: Optional[str] = None) -> Dict[str, Any]:
        """
        获取环境配置

        Args:
            environment: 环境名称，默认使用当前环境

        Returns:
            环境配置字典
        """
        env = environment or self._current_environment
        return self._environments.get("environments", {}).get(env, {})

    # ==================== 认证 ====================

    async def login(
        self,
        environment: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        登录到Dataverse环境

        Args:
            environment: 环境名称
            client_id: 客户端ID（覆盖配置）
            client_secret: 客户端密钥（覆盖配置）
            tenant_id: 租户ID（覆盖配置）

        Returns:
            登录结果
        """
        env = environment or self._current_environment
        env_config = self.get_environment_config(env)

        # 使用提供的凭据或从配置获取
        tenant_id = tenant_id or env_config.get("tenant_id")
        client_id = client_id or env_config.get("client_id")
        client_secret = client_secret or env_config.get("client_secret")

        if not all([tenant_id, client_id, client_secret]):
            return {
                "success": False,
                "error": "Missing credentials. Provide tenant_id, client_id, and client_secret."
            }

        try:
            # 创建MSAL应用
            authority = f"https://login.microsoftonline.com/{tenant_id}"
            app = msal.ConfidentialClientApplication(
                client_id=client_id,
                authority=authority,
                client_credential=client_secret
            )

            # 获取token
            scope = [f"{env_config.get('url', '')}/.default"]
            result = app.acquire_token_for_client(scopes=scope)

            if "access_token" in result:
                # 保存token
                self._tokens[env] = result["access_token"]
                self._current_environment = env

                # 创建并保存客户端
                client = DataverseClient(env, access_token=result["access_token"])
                self._clients[env] = client

                return {
                    "success": True,
                    "environment": env,
                    "url": env_config.get("url"),
                    "expires_in": result.get("expires_in", 3600)
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error_description", "Authentication failed")
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def logout(self, environment: Optional[str] = None) -> Dict[str, Any]:
        """
        登出

        Args:
            environment: 环境名称

        Returns:
            登出结果
        """
        env = environment or self._current_environment

        if env in self._tokens:
            del self._tokens[env]

        if env in self._clients:
            del self._clients[env]

        return {"success": True, "environment": env}

    async def status(self) -> Dict[str, Any]:
        """
        获取当前状态

        Returns:
            状态信息
        """
        return {
            "current_environment": self._current_environment,
            "authenticated_environments": list(self._tokens.keys()),
            "config": {
                "naming_prefix": self.naming_converter.prefix,
                "schema_name_style": self.naming_converter.schema_name_style
            }
        }

    # ==================== 环境切换 ====================

    async def switch_environment(self, environment: str) -> Dict[str, Any]:
        """
        切换环境

        Args:
            environment: 目标环境名称

        Returns:
            切换结果
        """
        if environment not in self._environments.get("environments", {}):
            return {
                "success": False,
                "error": f"Environment not found: {environment}"
            }

        self._current_environment = environment

        # 如果有该环境的token，创建客户端
        if environment in self._tokens:
            client = DataverseClient(environment, access_token=self._tokens[environment])
            self._clients[environment] = client

        return {
            "success": True,
            "current_environment": environment,
            "authenticated": environment in self._tokens
        }

    async def list_environments(self) -> List[Dict[str, Any]]:
        """
        列出所有环境

        Returns:
            环境列表
        """
        environments = []
        for name, config in self._environments.get("environments", {}).items():
            environments.append({
                "name": name,
                "display_name": config.get("name", name),
                "url": config.get("url", ""),
                "is_current": name == self._current_environment,
                "is_authenticated": name in self._tokens
            })
        return environments

    # ==================== 客户端获取 ====================

    def get_client(self, environment: Optional[str] = None) -> DataverseClient:
        """
        获取Dataverse客户端

        Args:
            environment: 环境名称

        Returns:
            Dataverse客户端实例

        Raises:
            AuthenticationError: 未认证
        """
        env = environment or self._current_environment

        if env not in self._clients:
            if env in self._tokens:
                self._clients[env] = DataverseClient(env, access_token=self._tokens[env])
            else:
                raise AuthenticationError(f"Not authenticated to environment: {env}")

        return self._clients[env]

    # ==================== 命名转换 ====================

    async def convert_name(
        self,
        name: str,
        type: str = "schema_name",
        is_standard: bool = False
    ) -> str:
        """
        转换名称

        Args:
            name: 原始名称
            type: 类型 (schema_name, webresource)
            is_standard: 是否为标准实体

        Returns:
            转换后的名称
        """
        if type == "schema_name":
            return self.naming_converter.convert_schema_name(name, is_standard)
        elif type == "webresource":
            resource_type = "css"  # 默认，应该从参数获取
            return self.naming_converter.convert_webresource_name(name, resource_type)
        else:
            return name

    async def validate_name(
        self,
        name: str,
        type: str = "schema_name"
    ) -> Tuple[bool, Optional[str]]:
        """
        验证名称

        Args:
            name: 要验证的名称
            type: 类型

        Returns:
            (是否有效, 错误信息)
        """
        if type == "schema_name":
            return self.naming_converter.validate_schema_name(name)
        elif type == "webresource":
            return self.naming_converter.validate_webresource_name(name)
        else:
            return True, None

    async def bulk_convert_names(
        self,
        items: List[Dict[str, Any]],
        type: str = "schema_name"
    ) -> List[Dict[str, Any]]:
        """
        批量转换名称

        Args:
            items: 项目列表
            type: 类型

        Returns:
            转换后的列表
        """
        result = []

        for item in items:
            converted = item.copy()
            name = item.get("name", "")

            if type == "schema_name":
                is_standard = item.get("is_standard", False)
                converted["name"] = await self.convert_name(name, type, is_standard)
            elif type == "attribute":
                entity_name = item.get("entity", "")
                is_standard = self.naming_converter.is_standard_entity(entity_name)
                converted["name"] = await self.convert_name(name, type, is_standard)

            result.append(converted)

        return result

    # ==================== 命名规则 ====================

    async def list_naming_rules(self) -> Dict[str, Any]:
        """
        列出当前命名规则

        Returns:
            命名规则配置
        """
        return {
            "prefix": self.naming_converter.prefix,
            "schema_name": {
                "style": self.naming_converter.schema_name_style,
                "separator": self.naming_converter.separator,
                "auto_prefix": self.naming_converter.auto_prefix
            },
            "webresource": {
                "prefix": self.config.get("naming", {}).get("webresource", {}).get("prefix", f"{self.naming_converter.prefix}_"),
                "naming_pattern": self.config.get("naming", {}).get("webresource", {}).get("naming_pattern", "{prefix}{category}/{name}.{ext}")
            },
            "standard_entities_count": len(self.naming_converter._standard_entities)
        }

    # ==================== 扩展和钩子 ====================

    async def register_extension(
        self,
        handler_type: str,
        module: str,
        class_name: str,
        enabled: bool = True
    ) -> Dict[str, Any]:
        """
        注册自定义扩展

        Args:
            handler_type: 处理器类型
            module: 模块路径
            class_name: 类名
            enabled: 是否启用

        Returns:
            注册结果
        """
        # 这里实现扩展注册逻辑
        return {
            "success": True,
            "handler": {
                "type": handler_type,
                "module": module,
                "class": class_name,
                "enabled": enabled
            }
        }

    async def list_extensions(self) -> List[Dict[str, Any]]:
        """
        列出已注册的扩展

        Returns:
            扩展列表
        """
        # 这里返回已注册的扩展
        extensions = self._config.get("extensions", {}).get("custom_handlers", [])
        return [
            {
                "name": ext.get("name"),
                "type": ext.get("type"),
                "module": ext.get("module"),
                "class": ext.get("class"),
                "enabled": ext.get("enabled", True)
            }
            for ext in extensions
        ]

    # ==================== 健康检查 ====================

    async def health_check(self, environment: Optional[str] = None) -> Dict[str, Any]:
        """
        健康检查

        Args:
            environment: 环境名称

        Returns:
            健康状态
        """
        env = environment or self._current_environment

        try:
            client = self.get_client(env)
            is_healthy = client.ping()

            return {
                "environment": env,
                "status": "healthy" if is_healthy else "unhealthy",
                "authenticated": env in self._tokens
            }
        except AuthenticationError:
            return {
                "environment": env,
                "status": "unauthenticated",
                "authenticated": False
            }
        except Exception as e:
            return {
                "environment": env,
                "status": "error",
                "error": str(e),
                "authenticated": env in self._tokens
            }

    # ==================== 系统信息 ====================

    async def get_system_info(self, environment: Optional[str] = None) -> Dict[str, Any]:
        """
        获取系统信息

        Args:
            environment: 环境名称

        Returns:
            系统信息
        """
        env = environment or self._current_environment

        try:
            client = self.get_client(env)
            return client.get_system_info()
        except Exception as e:
            return {
                "error": str(e),
                "environment": env
            }


class ToolHandler:
    """MCP工具处理器"""

    def __init__(self, core_agent: CoreAgent):
        self.core_agent = core_agent

    async def handle_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        处理MCP工具调用

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            处理结果字符串
        """
        try:
            if tool_name == "auth_login":
                result = await self.core_agent.login(
                    environment=arguments.get("environment")
                )
                return self._format_result(result)

            elif tool_name == "auth_logout":
                result = await self.core_agent.logout(
                    environment=arguments.get("environment")
                )
                return self._format_result(result)

            elif tool_name == "auth_status":
                result = await self.core_agent.status()
                return self._format_result(result)

            elif tool_name == "environment_switch":
                result = await self.core_agent.switch_environment(
                    arguments.get("environment")
                )
                return self._format_result(result)

            elif tool_name == "environment_list":
                result = await self.core_agent.list_environments()
                return self._format_list(result)

            elif tool_name == "naming_convert":
                result = await self.core_agent.convert_name(
                    arguments.get("input"),
                    arguments.get("type", "schema_name"),
                    arguments.get("is_standard", False)
                )
                return result

            elif tool_name == "naming_validate":
                is_valid, error = await self.core_agent.validate_name(
                    arguments.get("name"),
                    arguments.get("type", "schema_name")
                )
                if is_valid:
                    return "Name is valid"
                else:
                    return f"Validation error: {error}"

            elif tool_name == "naming_bulk_convert":
                result = await self.core_agent.bulk_convert_names(
                    arguments.get("items", []),
                    arguments.get("type", "schema_name")
                )
                return self._format_list(result)

            elif tool_name == "naming_rules_list":
                result = await self.core_agent.list_naming_rules()
                return self._format_dict(result)

            elif tool_name == "health_check":
                result = await self.core_agent.health_check(
                    arguments.get("environment")
                )
                return self._format_result(result)

            else:
                return f"Unknown tool: {tool_name}"

        except Exception as e:
            logger.error(f"Error handling tool {tool_name}: {e}")
            return json.dumps({"error": str(e)}, indent=2, ensure_ascii=False)

    def _format_result(self, result: Dict[str, Any]) -> str:
        """格式化结果"""
        return json.dumps(result, indent=2, ensure_ascii=False)

    def _format_list(self, items: List[Dict[str, Any]]) -> str:
        """格式化列表"""
        return json.dumps(items, indent=2, ensure_ascii=False)

    def _format_dict(self, data: Dict[str, Any]) -> str:
        """格式化字典"""
        return json.dumps(data, indent=2, ensure_ascii=False)
