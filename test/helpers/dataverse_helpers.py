"""
Power Platform Agent - Dataverse Test Helpers
Dataverse测试辅助工具
"""

import base64
from typing import Any, Dict, List, Optional, Union
from unittest.mock import MagicMock, Mock
from datetime import datetime, timedelta


# =============================================================================
# Dataverse 模拟数据生成器
# =============================================================================

class DataverseMockDataGenerator:
    """
    Dataverse模拟数据生成器

    生成符合Dataverse API格式的测试数据
    """

    @staticmethod
    def generate_entity(
        logical_name: str,
        id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        生成实体数据

        Args:
            logical_name: 实体逻辑名称
            id: 实体ID（可选）
            attributes: 实体属性（可选）

        Returns:
            实体数据字典
        """
        import uuid

        if id is None:
            id = str(uuid.uuid4())

        entity = {
            "@odata.context": f"https://org.crm.dynamics.com/api/data/v9.2/$metadata#{logical_name}/$entity",
            "@odata.etag": f'W/"{uuid.uuid4()}"',
            logical_name.replace("_", "x002e"): f"{logical_name}s.{id}",
            f"{logical_name}id": id,
        }

        if attributes:
            entity.update(attributes)

        return entity

    @staticmethod
    def generate_account(name: str, account_number: Optional[str] = None) -> Dict[str, Any]:
        """生成账户实体数据"""
        import uuid

        return DataverseMockDataGenerator.generate_entity(
            logical_name="account",
            attributes={
                "name": name,
                "accountnumber": account_number or f"ACC-{uuid.uuid4().hex[:8].upper()}",
                "statecode": 0,
                "statuscode": 1,
                "customertypecode": 1,
            },
        )

    @staticmethod
    def generate_contact(
        first_name: str,
        last_name: str,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成联系人实体数据"""
        import uuid

        return DataverseMockDataGenerator.generate_entity(
            logical_name="contact",
            attributes={
                "firstname": first_name,
                "lastname": last_name,
                "emailaddress1": email or f"{first_name.lower()}.{last_name.lower()}@example.com",
                "statecode": 0,
                "statuscode": 1,
            },
        )

    @staticmethod
    def generate_solution(
        unique_name: str,
        version: str = "1.0.0.0",
        friendly_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成解决方案实体数据"""
        return DataverseMockDataGenerator.generate_entity(
            logical_name="solution",
            attributes={
                "uniquename": unique_name,
                "friendlyname": friendly_name or unique_name,
                "version": version,
                "ismanaged": False,
                "publisherid": DataverseMockDataGenerator.generate_entity(
                    logical_name="publisher",
                    id="fd140aaf-4df4-11db-8d3a-001124aebc3b",
                )["publisherid"],
            },
        )

    @staticmethod
    def generate_response(
        data: Any,
        status_code: int = 200,
        next_link: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        生成Dataverse API响应

        Args:
            data: 响应数据
            status_code: HTTP状态码
            next_link: 下一页链接（用于分页）

        Returns:
            API响应字典
        """
        response = {
            "response": data,
            "status": status_code,
        }

        if next_link:
            response["@odata.nextLink"] = next_link

        return response


# =============================================================================
# Dataverse 模拟服务器
# =============================================================================

class MockDataverseServer:
    """
    模拟Dataverse服务器

    提供模拟的Dataverse API响应，用于测试
    """

    def __init__(self, base_url: str = "https://org.crm.dynamics.com"):
        """
        初始化模拟服务器

        Args:
            base_url: 服务器基础URL
        """
        self.base_url = base_url
        self.api_version = "v9.2"
        self.api_url = f"{base_url}/api/data/{self.api_version}"
        self._entities: Dict[str, Dict[str, Dict]] = {}
        self._requests: List[Dict] = []

    @property
    def entities(self) -> Dict[str, Dict[str, Dict]]:
        """获取所有实体"""
        return self._entities

    @property
    def requests(self) -> List[Dict]:
        """获取所有请求记录"""
        return self._requests

    def add_entity(self, entity_logical_name: str, entity_id: str, data: Dict) -> None:
        """
        添加实体

        Args:
            entity_logical_name: 实体逻辑名称
            entity_id: 实体ID
            data: 实体数据
        """
        if entity_logical_name not in self._entities:
            self._entities[entity_logical_name] = {}
        self._entities[entity_logical_name][entity_id] = data

    def get_entity(self, entity_logical_name: str, entity_id: str) -> Optional[Dict]:
        """
        获取实体

        Args:
            entity_logical_name: 实体逻辑名称
            entity_id: 实体ID

        Returns:
            实体数据或None
        """
        return self._entities.get(entity_logical_name, {}).get(entity_id)

    def delete_entity(self, entity_logical_name: str, entity_id: str) -> bool:
        """
        删除实体

        Args:
            entity_logical_name: 实体逻辑名称
            entity_id: 实体ID

        Returns:
            是否删除成功
        """
        if entity_logical_name in self._entities:
            if entity_id in self._entities[entity_logical_name]:
                del self._entities[entity_logical_name][entity_id]
                return True
        return False

    def create_mock_client(self) -> Mock:
        """
        创建模拟的Dataverse客户端

        Returns:
            模拟客户端对象
        """
        mock_client = Mock()
        mock_client.base_url = self.base_url
        mock_client.api_url = self.api_url

        # 模拟获取实体
        def mock_get(entity_logical_name: str, entity_id: str, *args, **kwargs):
            entity = self.get_entity(entity_logical_name, entity_id)
            self._requests.append({
                "method": "GET",
                "entity": entity_logical_name,
                "id": entity_id,
                "timestamp": datetime.now().isoformat(),
            })
            if entity:
                return DataverseMockDataGenerator.generate_response(entity)
            return DataverseMockDataGenerator.generate_response(
                {"error": "Not Found"},
                status_code=404,
            )

        # 模拟创建实体
        def mock_create(entity_logical_name: str, data: Dict, *args, **kwargs):
            import uuid

            entity_id = str(uuid.uuid4())
            entity = DataverseMockDataGenerator.generate_entity(
                entity_logical_name,
                id=entity_id,
                attributes=data,
            )
            self.add_entity(entity_logical_name, entity_id, entity)
            self._requests.append({
                "method": "POST",
                "entity": entity_logical_name,
                "id": entity_id,
                "timestamp": datetime.now().isoformat(),
            })
            return DataverseMockDataGenerator.generate_response(
                {"@odata.context": f"...", f"{entity_logical_name}id": entity_id},
                status_code=201,
            )

        # 模拟更新实体
        def mock_update(entity_logical_name: str, entity_id: str, data: Dict, *args, **kwargs):
            entity = self.get_entity(entity_logical_name, entity_id)
            if entity:
                entity.update(data)
                self._requests.append({
                    "method": "PATCH",
                    "entity": entity_logical_name,
                    "id": entity_id,
                    "timestamp": datetime.now().isoformat(),
                })
                return DataverseMockDataGenerator.generate_response({"status": "OK"})
            return DataverseMockDataGenerator.generate_response(
                {"error": "Not Found"},
                status_code=404,
            )

        # 模拟删除实体
        def mock_delete(entity_logical_name: str, entity_id: str, *args, **kwargs):
            success = self.delete_entity(entity_logical_name, entity_id)
            self._requests.append({
                "method": "DELETE",
                "entity": entity_logical_name,
                "id": entity_id,
                "timestamp": datetime.now().isoformat(),
            })
            if success:
                return DataverseMockDataGenerator.generate_response({"status": "OK"})
            return DataverseMockDataGenerator.generate_response(
                {"error": "Not Found"},
                status_code=404,
            )

        # 模拟查询实体
        def mock_query(entity_logical_name: str, *args, **kwargs):
            entities = list(self._entities.get(entity_logical_name, {}).values())
            self._requests.append({
                "method": "GET",
                "entity": entity_logical_name,
                "query": "all",
                "timestamp": datetime.now().isoformat(),
            })
            return DataverseMockDataGenerator.generate_response({
                "value": entities,
            })

        mock_client.get = mock_get
        mock_client.create = mock_create
        mock_client.update = mock_update
        mock_client.delete = mock_delete
        mock_client.query = mock_query

        return mock_client

    def reset(self) -> None:
        """重置服务器状态"""
        self._entities.clear()
        self._requests.clear()


# =============================================================================
# Dataverse 认证模拟
# =============================================================================

def create_mock_auth_token(
    tenant_id: str = "test-tenant",
    client_id: str = "test-client",
    expires_in: int = 3600,
) -> str:
    """
    创建模拟的OAuth访问令牌

    Args:
        tenant_id: 租户ID
        client_id: 客户端ID
        expires_in: 过期时间（秒）

    Returns:
        模拟的JWT令牌字符串
    """
    import json
    import base64

    header = {
        "alg": "RS256",
        "typ": "JWT",
    }

    now = int(datetime.now().timestamp())

    payload = {
        "aud": f"https://{tenant_id}.crm.dynamics.com",
        "iss": f"https://sts.windows.net/{tenant_id}/",
        "iat": now,
        "exp": now + expires_in,
        "appid": client_id,
        "upn": "test@example.com",
    }

    header_b64 = base64.urlsafe_b64encode(
        json.dumps(header).encode()
    ).rstrip(b"=").decode()

    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=").decode()

    signature = "mock-signature"

    return f"{header_b64}.{payload_b64}.{signature}"


def create_mock_token_response(
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
    expires_in: int = 3600,
) -> Dict[str, Any]:
    """
    创建模拟的令牌响应

    Args:
        access_token: 访问令牌
        refresh_token: 刷新令牌
        expires_in: 过期时间（秒）

    Returns:
        令牌响应字典
    """
    import uuid

    return {
        "token_type": "Bearer",
        "scope": "user_impersonation",
        "expires_in": expires_in,
        "ext_expires_in": expires_in,
        "access_token": access_token or create_mock_auth_token(),
        "refresh_token": refresh_token or str(uuid.uuid4()),
    }


# =============================================================================
# Dataverse 错误模拟
# =============================================================================

class DataverseErrorFactory:
    """
    Dataverse错误工厂

    创建各种Dataverse API错误响应
    """

    @staticmethod
    def authentication_error(message: str = "Authentication failed") -> Dict:
        """创建认证错误响应"""
        return {
            "error": {
                "code": "AAsts90048",
                "message": message,
                "innerError": {"code": "AAsts90048"},
            }
        }

    @staticmethod
    def authorization_error(message: str = "Access denied") -> Dict:
        """创建授权错误响应"""
        return {
            "error": {
                "code": "0x80040220",
                "message": message,
                "innerError": {"code": "0x80040220"},
            }
        }

    @staticmethod
    def not_found_error(entity_name: str, entity_id: str) -> Dict:
        """创建未找到错误响应"""
        return {
            "error": {
                "code": "0x80040217",
                "message": f"{entity_name} With Id = {entity_id} Does Not Exist",
                "innerError": {"code": "0x80040217"},
            }
        }

    @staticmethod
    def validation_error(field_name: str, message: str) -> Dict:
        """创建验证错误响应"""
        return {
            "error": {
                "code": "0x80040203",
                "message": message,
                "innerError": {"code": "0x80040203"},
            }
        }

    @staticmethod
    def throttle_error(retry_after: int = 60) -> Dict:
        """创建限流错误响应"""
        return {
            "error": {
                "code": "0x8004f070",
                "message": "System busy, please try again later",
                "innerError": {"code": "0x8004f070"},
            },
            "Retry-After": str(retry_after),
        }

    @staticmethod
    def internal_error(message: str = "An internal error occurred") -> Dict:
        """创建内部错误响应"""
        return {
            "error": {
                "code": "0x80044150",
                "message": message,
                "innerError": {"code": "0x80044150"},
            }
        }
