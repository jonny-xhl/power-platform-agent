"""
Power Platform Dataverse Client
提供与Dataverse Web API交互的核心功能
"""

import json
import logging
import uuid
from typing import Any, Union
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 设置日志
logger = logging.getLogger(__name__)


class DataverseClient:
    """Dataverse Web API客户端"""

    def __init__(
        self,
        environment: str = "dev",
        config_path: str = None,
        access_token: str = None
    ):
        """
        初始化Dataverse客户端

        Args:
            environment: 环境名称 (dev/test/production)
            config_path: 配置文件路径
            access_token: 可选的访问令牌
        """
        self.environment = environment
        self.config_path = config_path or "config/environments.yaml"
        self.access_token = access_token
        self._config: dict[str, Any] | None = None
        self._session: requests.Session | None = None
        self._base_url: str | None = None
        self._api_version = "9.2"

    @property
    def config(self) -> dict[str, Any]:
        """获取环境配置"""
        if self._config is None:
            self._load_config()
        return self._config  # type: ignore[return-value]

    @property
    def base_url(self) -> str:
        """获取API基础URL"""
        if self._base_url is None:
            env_config = self.config.get("environments", {}).get(self.environment, {})
            self._base_url = env_config.get("url", "")
        return self._base_url  # type: ignore[return-value]

    @property
    def session(self) -> requests.Session:
        """获取配置好的会话对象"""
        if self._session is None:
            self._create_session()
        return self._session

    def _load_config(self) -> None:
        """加载配置文件"""
        import yaml
        config_file = Path(self.config_path)
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
        else:
            self._config = {"environments": {}}

    def _create_session(self) -> None:
        """创建带有重试策略的会话"""
        self._session = requests.Session()

        # 配置重试策略
        retry_strategy = Retry(
            total=self.config.get("environments", {})
            .get(self.environment, {})
            .get("settings", {})
            .get("retry_count", 3),
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "PATCH", "DELETE"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

        # 设置默认头
        self._session.headers.update({
            "OData-Version": "4.0",
            "OData-MaxVersion": "4.0",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "Prefer": "odata.include-annotations=*"
        })

        if self.access_token:
            self._session.headers.update({
                "Authorization": f"Bearer {self.access_token}"
            })

    def set_token(self, access_token: str) -> None:
        """设置访问令牌"""
        self.access_token = access_token
        if self._session:
            self._session.headers.update({
                "Authorization": f"Bearer {access_token}"
            })

    def get_api_url(self, endpoint: str) -> str:
        """
        构建完整的API URL

        Args:
            endpoint: API端点路径

        Returns:
            完整的API URL
        """
        base = self.base_url.rstrip("/")
        endpoint = endpoint.lstrip("/")
        return f"{base}/api/data/v{self._api_version}/{endpoint}"

    # ==================== 实体操作 ====================

    def create_record(
        self,
        entity_name: str,
        data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        创建实体记录

        Args:
            entity_name: 实体逻辑名称
            data: 记录数据

        Returns:
            创建的记录数据，包含记录ID
        """
        url = self.get_api_url(entity_name)
        response = self.session.post(url, json=data)
        response.raise_for_status()

        record_id = response.headers.get("OData-EntityId", "").split("(")[-1].rstrip(")")
        return {"id": record_id, "status": "created"}

    def get_record(
        self,
        entity_name: str,
        record_id: str,
        select: list[str] = None
    ) -> dict[str, Any]:
        """
        获取单条记录

        Args:
            entity_name: 实体逻辑名称
            record_id: 记录ID
            select: 要选择的字段列表

        Returns:
            记录数据
        """
        url = self.get_api_url(f"{entity_name}({record_id})")
        if select:
            url += f"?$select={','.join(select)}"

        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def update_record(
        self,
        entity_name: str,
        record_id: str,
        data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        更新记录

        Args:
            entity_name: 实体逻辑名称
            record_id: 记录ID
            data: 要更新的数据

        Returns:
            更新结果
        """
        url = self.get_api_url(f"{entity_name}({record_id})")
        response = self.session.patch(url, json=data)
        response.raise_for_status()
        return {"status": "updated"}

    def delete_record(
        self,
        entity_name: str,
        record_id: str
    ) -> dict[str, Any]:
        """
        删除记录

        Args:
            entity_name: 实体逻辑名称
            record_id: 记录ID

        Returns:
            删除结果
        """
        url = self.get_api_url(f"{entity_name}({record_id})")
        response = self.session.delete(url)
        response.raise_for_status()
        return {"status": "deleted"}

    def query_records(
        self,
        entity_name: str,
        select: list[str] = None,
        filter: str = None,
        order_by: str = None,
        top: int = None,
        expand: list[str] = None
    ) -> list[dict[str, Any]]:
        """
        查询记录

        Args:
            entity_name: 实体逻辑名称
            select: 要选择的字段列表
            filter: OData过滤表达式
            order_by: 排序字段
            top: 返回记录数
            expand: 要展开的导航属性

        Returns:
            记录列表
        """
        url = self.get_api_url(entity_name)
        params = []

        if select:
            params.append(f"$select={','.join(select)}")
        if filter:
            params.append(f"$filter={filter}")
        if order_by:
            params.append(f"$orderby={order_by}")
        if top:
            params.append(f"$top={top}")
        if expand:
            params.append(f"$expand={','.join(expand)}")

        if params:
            url += "?" + "&".join(params)

        response = self.session.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get("value", [])

    # ==================== 元数据操作 ====================

    def get_entity_metadata(
        self,
        entity_name: str = None
    ) -> Union[dict[str, Any], list[dict[str, Any]]]:
        """
        获取实体元数据

        Args:
            entity_name: 实体逻辑名称，如果为None则返回所有实体

        Returns:
            实体元数据
        """
        if entity_name:
            url = self.get_api_url(f"EntityDefinitions(LogicalName='{entity_name}')")
        else:
            url = self.get_api_url("EntityDefinitions")

        response = self.session.get(url)
        response.raise_for_status()

        if entity_name:
            return response.json()
        return response.json().get("value", [])

    def create_entity(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """
        创建自定义实体

        Args:
            metadata: 实体元数据

        Returns:
            创建的实体元数据
        """
        url = self.get_api_url("EntityDefinitions")

        # 转换元数据格式
        entity_definition = self._convert_entity_metadata(metadata)

        response = self.session.post(url, json=entity_definition)
        response.raise_for_status()

        return response.json()

    def update_entity(
        self,
        entity_name: str,
        metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """
        更新实体元数据

        Args:
            entity_name: 实体逻辑名称
            metadata: 更新的元数据

        Returns:
            更新后的实体元数据
        """
        entity_metadata = self.get_entity_metadata(entity_name)
        metadata_id = entity_metadata.get("MetadataId")

        if not metadata_id:
            raise ValueError(f"Entity {entity_name} not found")

        url = self.get_api_url(f"EntityDefinitions({metadata_id})")

        response = self.session.patch(url, json=metadata)
        response.raise_for_status()

        return response.json()

    def create_attribute(
        self,
        entity_name: str,
        attribute_metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """
        创建实体属性

        Args:
            entity_name: 实体逻辑名称
            attribute_metadata: 属性元数据

        Returns:
            创建的属性元数据
        """
        entity_metadata = self.get_entity_metadata(entity_name)
        metadata_id = entity_metadata.get("MetadataId")

        if not metadata_id:
            raise ValueError(f"Entity {entity_name} not found")

        url = self.get_api_url(
            f"EntityDefinitions({metadata_id})/Attributes"
        )

        response = self.session.post(url, json=attribute_metadata)
        response.raise_for_status()

        return response.json()

    def get_attributes(
        self,
        entity_name: str
    ) -> list[dict[str, Any]]:
        """
        获取实体的所有属性

        Args:
            entity_name: 实体逻辑名称

        Returns:
            属性列表
        """
        entity_metadata = self.get_entity_metadata(entity_name)
        metadata_id = entity_metadata.get("MetadataId")

        if not metadata_id:
            raise ValueError(f"Entity {entity_name} not found")

        url = self.get_api_url(
            f"EntityDefinitions({metadata_id})/Attributes"
        )

        response = self.session.get(url)
        response.raise_for_status()

        return response.json().get("value", [])

    def get_relationships(
        self,
        entity_name: str
    ) -> list[dict[str, Any]]:
        """
        获取实体的所有关系

        Args:
            entity_name: 实体逻辑名称

        Returns:
            关系列表
        """
        entity_metadata = self.get_entity_metadata(entity_name)
        metadata_id = entity_metadata.get("MetadataId")

        if not metadata_id:
            raise ValueError(f"Entity {entity_name} not found")

        # 获取一对多关系
        one_to_many_url = self.get_api_url(
            f"EntityDefinitions({metadata_id})/OneToManyRelationships"
        )

        # 获取多对一关系
        many_to_one_url = self.get_api_url(
            f"EntityDefinitions({metadata_id})/ManyToOneRelationships"
        )

        # 获取多对多关系
        many_to_many_url = self.get_api_url(
            f"EntityDefinitions({metadata_id})/ManyToManyRelationships"
        )

        relationships = []

        for url in [one_to_many_url, many_to_one_url, many_to_many_url]:
            response = self.session.get(url)
            response.raise_for_status()
            relationships.extend(response.json().get("value", []))

        return relationships

    # ==================== Web Resource操作 ====================

    def get_webresources(
        self,
        filter: str = None
    ) -> list[dict[str, Any]]:
        """
        获取Web Resources

        Args:
            filter: 可选的过滤条件

        Returns:
            Web Resource列表
        """
        url = self.get_api_url("webresourceset")
        if filter:
            url += f"?$filter={filter}"

        response = self.session.get(url)
        response.raise_for_status()

        return response.json().get("value", [])

    def get_forms(
        self,
        entity_name: str,
        form_type: int = None
    ) -> list[dict[str, Any]]:
        """
        获取实体的表单列表

        Args:
            entity_name: 实体逻辑名称
            form_type: 表单类型过滤 (2=Main, 5=Mobile, 6=QuickCreate, 7=QuickView, 11=Card)

        Returns:
            表单列表，包含 formid, name, formxml, isdefault 等字段
        """
        # 查询实体元数据获取逻辑名，验证实体存在
        entity_meta = self.get_entity_metadata(entity_name)
        logical_name = entity_meta.get("LogicalName")
        if not logical_name:
            raise ValueError(f"Entity '{entity_name}' not found")

        # systemforms.objecttypecode 是 Edm.String，存储实体逻辑名称
        filter_parts = [f"objecttypecode eq '{logical_name}'"]
        if form_type is not None:
            filter_parts.append(f"type eq {form_type}")

        url = self.get_api_url("systemforms")
        params: dict[str, Any] = {"$filter": " and ".join(filter_parts)}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json().get("value", [])

    def get_form_by_id(self, form_id: str) -> dict[str, Any]:
        """
        获取单个表单的完整数据（包含 FormXml）

        Args:
            form_id: 表单 GUID

        Returns:
            表单完整数据
        """
        url = self.get_api_url(f"systemforms({form_id})")
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def update_form(self, form_id: str, payload: dict[str, Any]) -> None:
        """
        更新表单（PATCH SystemForm）

        Args:
            form_id: 表单 GUID
            payload: 要更新的字段，如 {"formxml": "<form>...</form>"}
        """
        url = self.get_api_url(f"systemforms({form_id})")
        response = self.session.patch(url, json=payload)
        response.raise_for_status()

    # ==================== 视图操作 ====================

    # 视图类型常量
    VIEW_TYPE_PUBLIC = 0
    VIEW_TYPE_ADVANCED_FIND = 1
    VIEW_TYPE_ASSOCIATED = 2
    VIEW_TYPE_QUICK_FIND = 4
    VIEW_TYPE_LOOKUP = 64

    def get_views(
        self,
        entity_name: str,
        query_type: int = None
    ) -> list[dict[str, Any]]:
        """
        获取实体的视图列表

        Args:
            entity_name: 实体逻辑名称
            query_type: 视图类型过滤 (0=Public, 1=AdvancedFind, 2=Associated, 4=QuickFind, 64=Lookup)

        Returns:
            视图列表，包含 savedqueryid, name, querytype, isdefault, fetchxml 等字段
        """
        # 验证实体存在
        entity_meta = self.get_entity_metadata(entity_name)
        logical_name = entity_meta.get("LogicalName")
        if not logical_name:
            raise ValueError(f"Entity '{entity_name}' not found")

        # 构建 OData 查询
        filter_parts = [f"returnedtypecode eq '{logical_name}'"]
        if query_type is not None:
            filter_parts.append(f"querytype eq {query_type}")

        url = self.get_api_url("savedqueries")
        params: dict[str, Any] = {"$filter": " and ".join(filter_parts)}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json().get("value", [])

    def get_view_by_id(self, savedquery_id: str) -> dict[str, Any]:
        """
        获取单个视图的完整数据（包含 FetchXml 和 LayoutXml）

        Args:
            savedquery_id: 视图 GUID

        Returns:
            视图完整数据
        """
        url = self.get_api_url(f"savedqueries({savedquery_id})")
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_view_by_name(
        self,
        entity_name: str,
        view_name: str
    ) -> dict[str, Any] | None:
        """
        通过视图名称获取视图

        Args:
            entity_name: 实体逻辑名称
            view_name: 视图名称 (name 属性)

        Returns:
            视图数据，未找到时返回 None
        """
        # 验证实体存在
        entity_meta = self.get_entity_metadata(entity_name)
        logical_name = entity_meta.get("LogicalName")
        if not logical_name:
            raise ValueError(f"Entity '{entity_name}' not found")

        url = self.get_api_url("savedqueries")
        params = {
            "$filter": f"returnedtypecode eq '{logical_name}' and name eq '{view_name}'"
        }
        response = self.session.get(url, params=params)
        response.raise_for_status()
        results = response.json().get("value", [])
        return results[0] if results else None

    def create_view(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """
        创建公共视图（Public View, QueryType=0）

        Args:
            metadata: 视图元数据，包含:
                - name: 视图名称（唯一标识）
                - returnedtypecode: 实体逻辑名称
                - fetchxml: Fetch XML 查询
                - layoutxml: 布局 XML
                - isdefault: 是否为默认视图
                - description: 视图描述

        Returns:
            创建的视图数据
        """
        import uuid as _uuid

        # 验证实体存在
        entity_name = metadata.get("returnedtypecode")
        entity_meta = self.get_entity_metadata(entity_name)
        if not entity_meta.get("LogicalName"):
            raise ValueError(f"Entity '{entity_name}' not found")

        # 生成新的 savedqueryid
        savedquery_id = str(_uuid.uuid4())

        # 构建请求体
        data = {
            "savedqueryid": savedquery_id,
            "name": metadata.get("name"),
            "returnedtypecode": entity_meta.get("LogicalName"),
            "querytype": self.VIEW_TYPE_PUBLIC,  # 公共视图必须是 0
            "fetchxml": metadata.get("fetchxml"),
            "layoutxml": metadata.get("layoutxml"),
            "isdefault": metadata.get("isdefault", False),
            "isquickfindquery": metadata.get("isquickfindquery", False)
        }

        # 可选字段
        if metadata.get("description"):
            data["description"] = metadata["description"]
        if metadata.get("layoutjson"):
            data["layoutjson"] = metadata["layoutjson"]

        url = self.get_api_url("savedqueries")
        response = self.session.post(url, json=data)
        response.raise_for_status()

        return response.json()

    def update_view(
        self,
        savedquery_id: str,
        payload: dict[str, Any]
    ) -> None:
        """
        更新视图（PATCH SavedQuery）

        注意：公共视图可以更新，但其他类型视图（AdvancedFind、Associated、QuickFind、Lookup）
        只能更新，不能删除

        Args:
            savedquery_id: 视图 GUID
            payload: 要更新的字段，如 {"fetchxml": "...", "layoutxml": "..."}
        """
        url = self.get_api_url(f"savedqueries({savedquery_id})")
        response = self.session.patch(url, json=payload)
        response.raise_for_status()

    def delete_view(self, savedquery_id: str) -> None:
        """
        删除视图

        注意：只能删除公共视图（QueryType=0），其他类型视图无法删除

        Args:
            savedquery_id: 视图 GUID
        """
        url = self.get_api_url(f"savedqueries({savedquery_id})")
        response = self.session.delete(url)
        response.raise_for_status()

    def build_fetch_xml(
        self,
        entity: str,
        attributes: list[str],
        order: dict[str, str] = None,
        filter_conditions: list[dict[str, Any]] = None
    ) -> str:
        """
        构建 Fetch XML 查询

        Args:
            entity: 实体逻辑名称
            attributes: 属性列表
            order: 排序，格式 {"attribute": "name", "descending": false}
            filter_conditions: 过滤条件列表

        Returns:
            Fetch XML 字符串
        """
        lines = ['<fetch version="1.0" mapping="logical">']
        lines.append(f'  <entity name="{entity}">')

        # 属性
        for attr in attributes:
            lines.append(f'    <attribute name="{attr}" />')

        # 排序
        if order:
            descending = "true" if order.get("descending") else "false"
            lines.append(f'    <order attribute="{order["attribute"]}" descending="{descending}" />')

        # 过滤
        if filter_conditions:
            lines.append('    <filter type="and">')
            for cond in filter_conditions:
                attr = cond.get("attribute")
                op = cond.get("operator", "eq")
                val = cond.get("value", "")
                lines.append(f'      <condition attribute="{attr}" operator="{op}" value="{val}" />')
            lines.append('    </filter>')

        lines.append('  </entity>')
        lines.append('</fetch>')

        return "\n".join(lines)

    def build_layout_xml(
        self,
        columns: list[dict[str, Any]]
    ) -> str:
        """
        构建布局 XML

        Args:
            columns: 列配置列表，每项包含:
                - name: 属性名称
                - width: 列宽度

        Returns:
            Layout XML 字符串
        """
        lines = ['<grid name="resultset" object="1" jump="name" select="1" preview="1" icon="1">']
        lines.append('  <row name="resultset" id="resultsetId">')

        for col in columns:
            width = col.get("width", 100)
            lines.append(f'    <cell name="{col["name"]}" width="{width}" />')

        lines.append('  </row>')
        lines.append('</grid>')

        return "\n".join(lines)

    def create_webresource(
        self,
        name: str,
        display_name: str,
        content: str,
        webresource_type: int
    ) -> dict[str, Any]:
        """
        创建Web Resource

        Args:
            name: Web Resource名称
            display_name: 显示名称
            content: Base64编码的内容
            webresource_type: 类型代码

        Returns:
            创建的Web Resource数据
        """
        import base64

        # 将内容转换为Base64
        if not content.startswith("/9j/") and not content.startswith("PH"):
            content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        url = self.get_api_url("webresourceset")

        data = {
            "name": name,
            "displayname": display_name,
            "content": content,
            "webresourcetype": webresource_type
        }

        response = self.session.post(url, json=data)
        response.raise_for_status()

        return response.json()

    def update_webresource(
        self,
        webresource_id: str,
        content: str
    ) -> dict[str, Any]:
        """
        更新Web Resource内容

        Args:
            webresource_id: Web Resource ID
            content: 新内容

        Returns:
            更新结果
        """
        import base64

        # 将内容转换为Base64
        if not content.startswith("/9j/") and not content.startswith("PH"):
            content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        url = self.get_api_url(f"webresourceset({webresource_id})")

        data = {"content": content}

        response = self.session.patch(url, json=data)
        response.raise_for_status()

        return {"status": "updated"}

    # ==================== 解决方案操作 ====================

    def get_solutions(self) -> list[dict[str, Any]]:
        """获取所有解决方案"""
        url = self.get_api_url("solutions")
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get("value", [])

    def get_solution_components(
        self,
        solution_unique_name: str
    ) -> list[dict[str, Any]]:
        """
        获取解决方案组件

        Args:
            solution_unique_name: 解决方案唯一名称

        Returns:
            解决方案组件列表
        """
        url = self.get_api_url(
            f"solutions(unique_name='{solution_unique_name}')/SolutionComponents"
        )
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get("value", [])

    # ==================== 批处理操作 ====================

    def execute_batch(
        self,
        batch_requests: list[dict[str, Any]],
        batch_id: str = None
    ) -> list[dict[str, Any]]:
        """
        执行批处理请求

        Args:
            batch_requests: 请求列表
            batch_id: 可选的批次ID

        Returns:
            响应列表
        """
        if batch_id is None:
            batch_id = str(uuid.uuid4())

        batch_url = self.get_api_url("$batch")
        batch_url = batch_url.replace("/api/data/", "/api/data/$batch")

        # 构建批处理请求体
        batch_body = self._build_batch_body(batch_requests, batch_id)

        headers = {
            "Content-Type": f"multipart/mixed; boundary=batch_{batch_id}"
        }

        response = self.session.post(batch_url, data=batch_body, headers=headers)
        response.raise_for_status()

        return self._parse_batch_response(response.text, batch_id)

    def _build_batch_body(
        self,
        batch_requests: list[dict[str, Any]],
        batch_id: str
    ) -> str:
        """构建批处理请求体"""
        lines = []

        for i, req in enumerate(batch_requests, 1):
            lines.append(f"--batch_{batch_id}")
            lines.append("Content-Type: application/http")
            lines.append("Content-Transfer-Encoding: binary")
            lines.append(f"Content-ID: {i}")
            lines.append("")
            lines.append(f"{req['method']} {req['url']} HTTP/1.1")
            lines.append("Content-Type: application/json; type=entry")
            lines.append("")

            if req.get("body"):
                lines.append(json.dumps(req["body"]))

        lines.append(f"--batch_{batch_id}--")

        return "\r\n".join(lines)

    def _parse_batch_response(
        self,
        response_text: str,
        batch_id: str
    ) -> list[dict[str, Any]]:
        """解析批处理响应"""
        # 简化的批处理响应解析
        results = []
        parts = response_text.split(f"--batch_{batch_id}")

        for part in parts[1:-1]:  # 跳过第一个和最后一个
            if "HTTP/1.1 200" in part or "HTTP/1.1 201" in part or "HTTP/1.1 204" in part:
                results.append({"status": "success"})
            else:
                results.append({"status": "error", "details": part.strip()})

        return results

    # ==================== 辅助方法 ====================

    def _convert_entity_metadata(
        self,
        metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """
        转换元数据格式为Dataverse API格式

        Args:
            metadata: 原始元数据

        Returns:
            Dataverse API格式的元数据
        """
        schema = metadata.get("schema", {})

        entity_definition = {
            "SchemaName": schema.get("schema_name"),
            "DisplayName": schema.get("display_name"),
            "Description": schema.get("description"),
            "OwnershipType": schema.get("ownership_type", "UserOwned"),
            "IsActivity": schema.get("has_activities", False),
            "HasNotes": schema.get("has_notes", False),
            "IsAuditEnabled": {"Value": schema.get("is_audit_enabled", False)},
            "IsQuickCreateEnabled": {"Value": schema.get("options", {}).get("enable_quick_create", False)}
        }

        # 移除空值
        return {k: v for k, v in entity_definition.items() if v is not None}

    def _convert_attribute_metadata(
        self,
        attribute: dict[str, Any],
        attribute_type: str
    ) -> dict[str, Any]:
        """
        转换属性元数据

        Args:
            attribute: 原始属性定义
            attribute_type: 属性类型

        Returns:
            Dataverse API格式的属性元数据
        """
        type_mapping = {
            "String": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
            "Integer": "Microsoft.Dynamics.CRM.IntegerAttributeMetadata",
            "Money": "Microsoft.Dynamics.CRM.MoneyAttributeMetadata",
            "Picklist": "Microsoft.Dynamics.CRM.PicklistAttributeMetadata",
            "Lookup": "Microsoft.Dynamics.CRM.LookupAttributeMetadata",
            "DateTime": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata",
            "Boolean": "Microsoft.Dynamics.CRM.BooleanAttributeMetadata",
            "Memo": "Microsoft.Dynamics.CRM.MemoAttributeMetadata",
            "Decimal": "Microsoft.Dynamics.CRM.DecimalAttributeMetadata",
            "Double": "Microsoft.Dynamics.CRM.DoubleAttributeMetadata",
            "BigInt": "Microsoft.Dynamics.CRM.BigIntAttributeMetadata",
        }

        metadata_type = type_mapping.get(attribute_type, type_mapping["String"])

        attribute_metadata = {
            "@odata.type": metadata_type,
            "SchemaName": attribute.get("name"),
            "DisplayName": attribute.get("display_name"),
            "Description": attribute.get("description"),
            "RequiredLevel": {
                "Value": "ApplicationRequired" if attribute.get("required") else "None"
            },
            "IsValidForCreate": True,
            "IsValidForRead": True,
            "IsValidForUpdate": True
        }

        # 类型特定的属性
        if attribute_type == "String":
            attribute_metadata["MaxLength"] = attribute.get("max_length", 100)

        elif attribute_type == "Money":
            attribute_metadata["Precision"] = attribute.get("precision", 2)
            attribute_metadata["PrecisionSource"] = 2

        elif attribute_type == "Picklist":
            options = attribute.get("options", [])
            attribute_metadata["OptionSet"] = {
                "Options": [
                    {
                        "Value": opt.get("value"),
                        "Label": {"UserLocalizedLabel": {"Label": opt.get("label")}}
                    }
                    for opt in options
                ]
            }

        elif attribute_type == "Memo":
            attribute_metadata["MaxLength"] = attribute.get("max_length", 2000)
            attribute_metadata["@odata.type"] = "Microsoft.Dynamics.CRM.MemoAttributeMetadata"

        # 移除空值
        return {k: v for k, v in attribute_metadata.items() if v is not None}

    # ==================== 状态和健康检查 ====================

    def ping(self) -> bool:
        """
        检查连接状态

        Returns:
            连接是否正常
        """
        try:
            url = self.get_api_url("EntityDefinitions")
            response = self.session.head(url, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Ping failed: {e}")
            return False

    def get_system_info(self) -> dict[str, Any]:
        """
        获取系统信息

        Returns:
            系统信息字典
        """
        url = self.get_api_url("RetrieveCurrentOrganization")
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()


class DataverseClientError(Exception):
    """Dataverse客户端错误基类"""
    pass


class AuthenticationError(DataverseClientError):
    """认证错误"""
    pass


class RateLimitError(DataverseClientError):
    """请求限流错误"""
    pass


class EntityNotFoundError(DataverseClientError):
    """实体未找到错误"""
    pass
