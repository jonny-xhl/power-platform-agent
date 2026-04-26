"""
Power Platform Agent - Mock Dataverse Server
模拟Dataverse服务器，用于测试
"""

import json
from typing import Any, Dict, List, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time


class MockDataverseHandler(BaseHTTPRequestHandler):
    """
    模拟Dataverse服务器的HTTP请求处理器
    """

    # 类变量，用于存储服务器状态
    entities = {}
    requests = []
    auth_tokens = set()
    response_delay = 0  # 响应延迟（秒）

    def log_message(self, format: str, *args: Any) -> None:
        """禁用默认日志"""
        pass

    def _send_response(
        self,
        status_code: int,
        body: Any,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """发送HTTP响应"""
        self.send_response(status_code)

        # 默认响应头
        self.send_header("Content-Type", "application/json; odata.metadata=minimal")
        self.send_header("OData-Version", "4.0")

        # 自定义响应头
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)

        self.end_headers()

        if body:
            response_body = json.dumps(body) if isinstance(body, (dict, list)) else body
            self.wfile.write(response_body.encode("utf-8"))

    def _authenticate(self) -> bool:
        """验证请求认证"""
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return token in self.auth_tokens or token == "mock-valid-token"
        return False

    def _parse_url(self) -> tuple:
        """解析请求URL"""
        parsed = urlparse(self.path)
        path_parts = parsed.path.strip("/").split("/")
        query = parse_qs(parsed.query)
        return path_parts, query

    def _get_entity_name_and_id(self, path_parts: List[str]) -> tuple:
        """从URL路径中提取实体名称和ID"""
        # 格式: api/data/v9.2/entity_name(id)
        if len(path_parts) >= 5 and path_parts[0] == "api":
            entity_name = path_parts[4]
            entity_id = None

            if len(path_parts) > 5 and path_parts[5].startswith("("):
                # 提取ID: (guid) 或 (guid)/property
                id_part = path_parts[5][1:]
                if ")" in id_part:
                    entity_id = id_part.split(")")[0]

            return entity_name, entity_id

        return None, None

    def do_GET(self) -> None:
        """处理GET请求"""
        if MockDataverseHandler.response_delay > 0:
            time.sleep(MockDataverseHandler.response_delay)

        path_parts, query = self._parse_url()

        # 记录请求
        MockDataverseHandler.requests.append({
            "method": "GET",
            "path": self.path,
            "headers": dict(self.headers),
        })

        # 检查认证
        if not self._authenticate():
            self._send_response(401, {
                "error": {
                    "code": "AAsts90048",
                    "message": "Authentication failed",
                }
            })
            return

        entity_name, entity_id = self._get_entity_name_and_id(path_parts)

        if entity_name:
            if entity_id:
                # 获取单个实体
                if entity_name in MockDataverseHandler.entities:
                    if entity_id in MockDataverseHandler.entities[entity_name]:
                        self._send_response(
                            200,
                            MockDataverseHandler.entities[entity_name][entity_id]
                        )
                    else:
                        self._send_response(404, {
                            "error": {
                                "code": "0x80040217",
                                "message": f"{entity_name} With Id = {entity_id} Does Not Exist",
                            }
                        })
                else:
                    self._send_response(404, {
                        "error": {
                            "code": "0x80040217",
                            "message": f"Entity '{entity_name}' not found",
                        }
                    })
            else:
                # 查询实体列表
                if entity_name in MockDataverseHandler.entities:
                    entities = list(MockDataverseHandler.entities[entity_name].values())
                    self._send_response(200, {"value": entities})
                else:
                    self._send_response(200, {"value": []})
        else:
            self._send_response(404, {"error": {"message": "Not found"}})

    def do_POST(self) -> None:
        """处理POST请求"""
        if MockDataverseHandler.response_delay > 0:
            time.sleep(MockDataverseHandler.response_delay)

        path_parts, query = self._parse_url()

        # 记录请求
        MockDataverseHandler.requests.append({
            "method": "POST",
            "path": self.path,
            "headers": dict(self.headers),
        })

        # 检查认证
        if not self._authenticate():
            self._send_response(401, {
                "error": {
                    "code": "AAsts90048",
                    "message": "Authentication failed",
                }
            })
            return

        entity_name, _ = self._get_entity_name_and_id(path_parts)

        if entity_name:
            import uuid

            # 读取请求体
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8")) if body else {}

            # 创建新实体
            entity_id = str(uuid.uuid4())

            entity = {
                "@odata.context": f"$metadata#{entity_name}/$entity",
                f"{entity_name}id": entity_id,
                **data,
            }

            if entity_name not in MockDataverseHandler.entities:
                MockDataverseHandler.entities[entity_name] = {}

            MockDataverseHandler.entities[entity_name][entity_id] = entity

            self._send_response(
                201,
                {
                    "@odata.context": f"$metadata#{entity_name}/$entity",
                    f"{entity_name}id": entity_id,
                },
                headers={"OData-EntityId": f"{entity_name}s({entity_id})"},
            )
        else:
            self._send_response(400, {"error": {"message": "Invalid request"}})

    def do_PATCH(self) -> None:
        """处理PATCH请求（更新实体）"""
        if MockDataverseHandler.response_delay > 0:
            time.sleep(MockDataverseHandler.response_delay)

        path_parts, query = self._parse_url()

        # 记录请求
        MockDataverseHandler.requests.append({
            "method": "PATCH",
            "path": self.path,
            "headers": dict(self.headers),
        })

        # 检查认证
        if not self._authenticate():
            self._send_response(401, {
                "error": {
                    "code": "AAsts90048",
                    "message": "Authentication failed",
                }
            })
            return

        entity_name, entity_id = self._get_entity_name_and_id(path_parts)

        if entity_name and entity_id:
            # 读取请求体
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8")) if body else {}

            # 更新实体
            if entity_name in MockDataverseHandler.entities:
                if entity_id in MockDataverseHandler.entities[entity_name]:
                    MockDataverseHandler.entities[entity_name][entity_id].update(data)
                    self._send_response(204, None)
                else:
                    self._send_response(404, {
                        "error": {
                            "code": "0x80040217",
                            "message": f"{entity_name} With Id = {entity_id} Does Not Exist",
                        }
                    })
            else:
                self._send_response(404, {
                    "error": {
                        "code": "0x80040217",
                        "message": f"Entity '{entity_name}' not found",
                    }
                })
        else:
            self._send_response(400, {"error": {"message": "Invalid request"}})

    def do_DELETE(self) -> None:
        """处理DELETE请求"""
        if MockDataverseHandler.response_delay > 0:
            time.sleep(MockDataverseHandler.response_delay)

        path_parts, query = self._parse_url()

        # 记录请求
        MockDataverseHandler.requests.append({
            "method": "DELETE",
            "path": self.path,
            "headers": dict(self.headers),
        })

        # 检查认证
        if not self._authenticate():
            self._send_response(401, {
                "error": {
                    "code": "AAsts90048",
                    "message": "Authentication failed",
                }
            })
            return

        entity_name, entity_id = self._get_entity_name_and_id(path_parts)

        if entity_name and entity_id:
            # 删除实体
            if entity_name in MockDataverseHandler.entities:
                if entity_id in MockDataverseHandler.entities[entity_name]:
                    del MockDataverseHandler.entities[entity_name][entity_id]
                    self._send_response(204, None)
                else:
                    self._send_response(404, {
                        "error": {
                            "code": "0x80040217",
                            "message": f"{entity_name} With Id = {entity_id} Does Not Exist",
                        }
                    })
            else:
                self._send_response(404, {
                    "error": {
                        "code": "0x80040217",
                        "message": f"Entity '{entity_name}' not found",
                    }
                })
        else:
            self._send_response(400, {"error": {"message": "Invalid request"}})


class MockDataverseServer:
    """
    模拟Dataverse服务器

    在本地线程中运行HTTP服务器，模拟Dataverse API
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 0,  # 0 表示自动分配端口
    ):
        """
        初始化模拟服务器

        Args:
            host: 服务器主机
            port: 服务器端口（0表示自动分配）
        """
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False

    def start(self) -> int:
        """
        启动模拟服务器

        Returns:
            服务器实际监听的端口
        """
        if self.running:
            return self.server.server_address[1]

        # 创建服务器
        self.server = HTTPServer((self.host, self.port), MockDataverseHandler)

        # 启动服务器线程
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.running = True

        # 清理状态
        MockDataverseHandler.entities.clear()
        MockDataverseHandler.requests.clear()
        MockDataverseHandler.auth_tokens.clear()

        return self.server.server_address[1]

    def stop(self) -> None:
        """停止模拟服务器"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.running = False

        if self.thread:
            self.thread.join(timeout=5)

    @property
    def base_url(self) -> str:
        """获取服务器基础URL"""
        if self.server:
            port = self.server.server_address[1]
            return f"http://{self.host}:{port}"
        return ""

    @property
    def api_url(self) -> str:
        """获取服务器API URL"""
        return f"{self.base_url}/api/data/v9.2"

    def add_auth_token(self, token: str) -> None:
        """添加有效的认证令牌"""
        MockDataverseHandler.auth_tokens.add(token)

    def set_response_delay(self, delay: float) -> None:
        """设置响应延迟"""
        MockDataverseHandler.response_delay = delay

    def get_requests(self) -> List[Dict]:
        """获取所有请求记录"""
        return MockDataverseHandler.requests.copy()

    def get_entities(self, entity_name: Optional[str] = None) -> Dict:
        """获取实体数据"""
        if entity_name:
            return MockDataverseHandler.entities.get(entity_name, {})
        return MockDataverseHandler.entities.copy()

    def reset(self) -> None:
        """重置服务器状态"""
        MockDataverseHandler.entities.clear()
        MockDataverseHandler.requests.clear()
