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

from .retry_helper import retry_on_metadata_error, retry_on_404

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

    @retry_on_404(max_retries=5, initial_delay=2.0)
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

    @retry_on_metadata_error(
        max_retries=4,
        initial_delay=2.0,
        error_patterns=["not found", "cannot be found", "invalid entity"]
    )
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

    @retry_on_metadata_error(
        max_retries=4,
        initial_delay=2.0,
        error_patterns=["not found", "invalid entity"]
    )
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

    @retry_on_metadata_error(
        max_retries=4,
        initial_delay=1.5,
        error_patterns=["not found", "cannot be found"]
    )
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
        query_type: int = None,
        is_customizable_only: bool = False
    ) -> list[dict[str, Any]]:
        """
        获取实体的视图列表

        Args:
            entity_name: 实体逻辑名称
            query_type: 视图类型过滤 (0=Public, 1=AdvancedFind, 2=Associated, 4=QuickFind, 64=Lookup)
            is_customizable_only: 是否只返回可自定义的视图 (IsCustomizable/CanBeModified=True)

        Returns:
            视图列表，包含 savedqueryid, name, querytype, isdefault, fetchxml, iscustomizable 等字段
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
        if is_customizable_only:
            # IsCustomizable 的 Value 为 true 表示可自定义
            filter_parts.append("iscustomizable/Value eq true")

        # 请求字段包含 iscustomizable
        select_fields = "savedqueryid,name,querytype,isdefault,isquickfindquery,description,iscustomizable"

        url = self.get_api_url("savedqueries")
        params: dict[str, Any] = {
            "$filter": " and ".join(filter_parts),
            "$select": select_fields
        }
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

    @retry_on_404(max_retries=4, initial_delay=1.5)
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
                - layoutxml: 布局 XML（可选，如果不提供则从 columns 生成）
                - columns: 列定义（可选，用于自动生成 LayoutXML）
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

        # 处理 LayoutXML：如果提供了 layoutxml，使用它；否则从 columns 生成
        layoutxml = metadata.get("layoutxml")
        if not layoutxml:
            columns = metadata.get("columns", [])
            if columns:
                layoutxml = self.build_layout_xml(entity_name, columns)

        # 构建请求体
        # 注意：在 Dataverse 中，name 字段是视图的显示名称
        # display_name 是 YAML 中的显示名称，映射到 API 的 name 字段
        display_name = metadata.get("display_name")
        data = {
            "savedqueryid": savedquery_id,
            "name": display_name,
            "returnedtypecode": entity_meta.get("LogicalName"),
            "querytype": self.VIEW_TYPE_PUBLIC,  # 公共视图必须是 0
            "fetchxml": metadata.get("fetchxml"),
            "layoutxml": layoutxml,
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

        # 打印请求和响应用于调试
        import json as _json
        logger.error(f"create_view request: {_json.dumps(data, ensure_ascii=False)[:2000]}...")
        logger.error(f"create_view response status: {response.status_code}")
        if response.status_code >= 400:
            logger.error(f"create_view error response: {response.text}")

        response.raise_for_status()

        # Dataverse 可能返回 204 No Content 或空响应
        if response.status_code == 204 or not response.text:
            return {"savedqueryid": savedquery_id}
        return response.json()

    @retry_on_metadata_error(
        max_retries=4,
        initial_delay=1.5,
        error_patterns=["not found", "cannot be found"]
    )
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
        entity_name: str,
        columns: list[dict[str, Any]]
    ) -> str:
        """
        构建布局 XML（新版本 Dataverse 格式）

        Args:
            entity_name: 实体逻辑名称
            columns: 列配置列表，每项包含:
                - attribute: 属性名称
                - width: 列宽度（可选）

        Returns:
            Layout XML 字符串
        """
        # 获取实体元数据
        entity_meta = self.get_entity_metadata(entity_name)
        object_type_code = entity_meta.get("ObjectTypeCode", "1")
        primary_id_attr = entity_meta.get("PrimaryIdAttribute", f"{entity_name}id")
        primary_name_attr = entity_meta.get("PrimaryNameAttribute", "name")

        lines = [
            f'<grid name="resultset" object="{object_type_code}" '
            f'jump="{primary_name_attr}" select="1" preview="1" icon="1">'
        ]
        lines.append(f'  <row name="resultset" id="{primary_id_attr}">')

        for col in columns:
            attr_name = col.get("attribute") or col.get("name", "")
            width = col.get("width", 100)
            if attr_name:
                lines.append(f'    <cell name="{attr_name}" width="{width}" />')

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
        from urllib.parse import quote
        # 使用 URL 编码和双引号格式
        encoded_name = quote(solution_unique_name, safe='')
        url = self.get_api_url(
            f"solutions(unique_name=%22{encoded_name}%22)/SolutionComponents"
        )
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get("value", [])

    def get_solution_by_name(
        self,
        solution_name: str
    ) -> dict[str, Any] | None:
        """
        根据名称获取解决方案

        Args:
            solution_name: 解决方案唯一名称

        Returns:
            解决方案信息，如果不存在返回 None
        """
        solutions = self.get_solutions()
        for sol in solutions:
            if sol.get("uniquename") == solution_name:
                return sol
        return None

    def create_solution(
        self,
        unique_name: str,
        display_name: str,
        version: str = "1.0.0.0",
        publisher_id: str | None = None,
        description: str = None
    ) -> dict[str, Any]:
        """
        创建解决方案

        Args:
            unique_name: 解决方案唯一名称
            display_name: 解决方案显示名称
            version: 版本号
            publisher_id: 发布商 ID
            description: 解决方案描述

        Returns:
            创建的解决方案信息
        """
        url = self.get_api_url("solutions")

        solution_data = {
            "uniquename": unique_name,
            "friendlyname": display_name,
            "version": version,
            "ismanaged": False,
            "isvisible": True,
            "description": description or f"Solution: {display_name}"
        }

        # publisherid 需要使用 OData 导航属性格式
        if publisher_id:
            solution_data["publisherid@odata.bind"] = f"/publishers({publisher_id})"

        response = self.session.post(url, json=solution_data)
        response.raise_for_status()

        # 获取创建的解决方案 ID
        solution_id = response.headers.get("OData-EntityId", "").split("(")[-1].rstrip(")")

        return {
            "solutionid": solution_id,
            "uniquename": unique_name,
            "friendlyname": display_name,
            "version": version
        }

    def update_solution_version(
        self,
        solution_name: str,
        version: str
    ) -> dict[str, Any]:
        """
        更新解决方案版本

        Args:
            solution_name: 解决方案唯一名称
            version: 新版本号

        Returns:
            更新结果
        """
        solution = self.get_solution_by_name(solution_name)
        if not solution:
            raise ValueError(f"Solution not found: {solution_name}")

        solution_id = solution.get("solutionid")
        url = self.get_api_url(f"solutions({solution_id})")

        update_data = {"version": version}
        response = self.session.patch(url, json=update_data)
        response.raise_for_status()

        return {"success": True, "version": version}

    def add_solution_component(
        self,
        solution_name: str,
        component_type: int,
        object_id: str
    ) -> dict[str, Any]:
        """
        添加组件到解决方案

        使用 AddSolutionComponent Action（solutioncomponent 实体不支持 Create）

        Args:
            solution_name: 解决方案唯一名称
            component_type: 组件类型代码 (1=实体, 10=表单, 11=视图, etc.)
            object_id: 组件对象 ID

        Returns:
            添加结果
        """
        # 使用无绑定的 AddSolutionComponent Action
        # URL 格式: /api/data/v9.2/AddSolutionComponent
        url = self.get_api_url("AddSolutionComponent")

        component_data = {
            "SolutionUniqueName": solution_name,
            "ComponentType": component_type,
            "ComponentId": object_id,
            "AddRequiredComponents": False,
            "DoNotIncludeSubcomponents": False
        }

        response = self.session.post(url, json=component_data)
        response.raise_for_status()

        return {
            "success": True,
            "solution": solution_name,
            "component_type": component_type,
            "object_id": object_id
        }

    def add_component_by_schema_name(
        self,
        solution_name: str,
        component_type: str,
        schema_name: str,
        entity_name: str | None = None
    ) -> dict[str, Any]:
        """
        通过 Schema Name 添加组件到解决方案

        Args:
            solution_name: 解决方案唯一名称
            component_type: 组件类型 (table/entity, form, view, etc.)
            schema_name: 组件的 Schema Name
            entity_name: 实体名称（用于 form、view 等）

        Returns:
            添加结果
        """
        # 组件类型到代码的映射（根据 Dataverse solutioncomponent.componenttype 选项集）
        type_codes = {
            "table": 1,
            "entity": 1,
            "attribute": 2,
            "relationship": 3,
            "optionset": 9,
            "form": 60,      # System Form
            "view": 26,      # Saved Query
            "webresource": 61  # Web Resource
        }

        if component_type not in type_codes:
            raise ValueError(f"Unknown component type: {component_type}")

        component_type_code = type_codes[component_type]

        # 使用 get_component_id 获取组件 ID
        object_id = self.get_component_id(component_type, schema_name, entity_name)

        if not object_id:
            return {
                "success": False,
                "error": f"Component not found: {component_type}/{schema_name} (entity: {entity_name})"
            }

        return self.add_solution_component(
            solution_name,
            component_type_code,
            object_id
        )

    def publish_solution(self, solution_name: str | None = None) -> dict[str, Any]:
        """
        发布解决方案或所有自定义项

        Args:
            solution_name: 解决方案唯一名称，如果为 None 则发布所有

        Returns:
            发布结果
        """
        # PublishAllXml 发布所有自定义项
        url = self.get_api_url("PublishAllXml")
        response = self.session.post(url)
        response.raise_for_status()

        return {
            "success": True,
            "solution": solution_name or "all",
            "message": "Customizations published successfully"
        }

    def get_component_id(
        self,
        component_type: str,
        schema_name: str,
        entity_name: str | None = None
    ) -> str | None:
        """
        获取组件的 Object ID

        Args:
            component_type: 组件类型
            schema_name: Schema Name
            entity_name: 实体名称（用于表单、视图等）

        Returns:
            组件 ID，如果不存在返回 None
        """
        if component_type in ("table", "entity"):
            meta = self.get_entity_metadata(schema_name)
            return meta.get("MetadataId") if meta else None

        elif component_type == "form":
            if entity_name:
                forms = self.get_forms(entity_name)
                for form in forms:
                    if form.get("name") == schema_name:
                        return form.get("formid")
            return None

        elif component_type == "view":
            if entity_name:
                view = self.get_view_by_name(entity_name, schema_name)
                return view.get("savedqueryid") if view else None
            return None

        elif component_type == "webresource":
            resources = self.get_webresources(filter=f"name eq '{schema_name}'")
            return resources[0].get("webresourceid") if resources else None

        return None

    # ==================== 发布商操作 ====================

    def get_publishers(self) -> list[dict[str, Any]]:
        """
        获取所有发布商

        Returns:
            发布商列表
        """
        url = self.get_api_url("publishers")
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get("value", [])

    def get_publisher_by_name(
        self,
        publisher_name: str
    ) -> dict[str, Any] | None:
        """
        根据名称获取发布商

        Args:
            publisher_name: 发布商唯一名称

        Returns:
            发布商信息，如果不存在返回 None
        """
        publishers = self.get_publishers()
        for pub in publishers:
            if pub.get("uniquename") == publisher_name:
                return pub
        return None

    def create_publisher(
        self,
        name: str,
        display_name: str,
        prefix: str,
        description: str = None
    ) -> dict[str, Any]:
        """
        创建发布商

        Args:
            name: 发布商唯一名称
            display_name: 发布商显示名称
            prefix: 发布商前缀
            description: 发布商描述

        Returns:
            创建的发布商信息
        """
        url = self.get_api_url("publishers")

        publisher_data = {
            "uniquename": name,
            "friendlyname": display_name,
            "customizationprefix": prefix,
            "description": description or f"Publisher: {display_name}"
        }

        response = self.session.post(url, json=publisher_data)
        response.raise_for_status()

        # 获取创建的发布商 ID
        publisher_id = response.headers.get("OData-EntityId", "").split("(")[-1].rstrip(")")

        return {
            "publisherid": publisher_id,
            "uniquename": name,
            "friendlyname": display_name,
            "customizationprefix": prefix
        }

    def ensure_publisher_exists(
        self,
        name: str,
        display_name: str = None,
        prefix: str = None,
        description: str = None
    ) -> dict[str, Any]:
        """
        确保发布商存在，如果不存在则创建

        Args:
            name: 发布商唯一名称
            display_name: 发布商显示名称
            prefix: 发布商前缀
            description: 发布商描述

        Returns:
            发布商信息及是否为新创建
        """
        existing = self.get_publisher_by_name(name)

        if existing:
            return {
                "publisher": existing,
                "created": False,
                "message": "Publisher already exists"
            }

        # 创建发布商
        created = self.create_publisher(
            name=name,
            display_name=display_name or name,
            prefix=prefix or "new",
            description=description
        )

        return {
            "publisher": created,
            "created": True,
            "message": "Publisher created successfully"
        }

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

    def _convert_to_label(
        self,
        text: str,
        language_code: int = 2052
    ) -> dict[str, Any]:
        """
        将文本转换为 Dataverse Label 格式

        Args:
            text: 显示文本
            language_code: 语言代码（默认 2052 = 中文简体）

        Returns:
            Dataverse Label 格式的字典
        """
        if not text:
            return None

        return {
            "@odata.type": "Microsoft.Dynamics.CRM.Label",
            "LocalizedLabels": [
                {
                    "@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel",
                    "Label": text,
                    "LanguageCode": language_code
                }
            ]
        }

    def _convert_entity_metadata(
        self,
        metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """
        转换元数据格式为Dataverse API格式

        Args:
            metadata: 原始元数据，包含 schema 和 attributes

        Returns:
            Dataverse API格式的元数据，包含 Attributes 数组
        """
        schema = metadata.get("schema", {})

        # 基本实体定义
        entity_definition = {
            "@odata.type": "Microsoft.Dynamics.CRM.EntityMetadata",
            "SchemaName": schema.get("schema_name"),
            "DisplayName": self._convert_to_label(schema.get("display_name", "")),
            "DisplayCollectionName": self._convert_to_label(
                schema.get("display_collection_name") or f"{schema.get('display_name', '')}s"
            ),
            "Description": self._convert_to_label(schema.get("description", "")),
            "OwnershipType": schema.get("ownership_type", "UserOwned"),
            "IsActivity": schema.get("has_activities", False),
            "HasNotes": schema.get("has_notes", False),
            "IsAuditEnabled": {"Value": schema.get("is_audit_enabled", False)},
            "IsQuickCreateEnabled": {"Value": schema.get("options", {}).get("enable_quick_create", False)}
        }

        # 处理属性数组
        attributes = metadata.get("attributes", [])
        if attributes:
            converted_attributes = []

            for attr in attributes:
                attr_type = attr.get("type", "String")

                # 跳过 Lookup 类型 - 必须通过关系创建
                if attr_type == "Lookup":
                    logger.info(f"Skipping Lookup attribute '{attr.get('name')}' - must be created via relationship")
                    continue

                # 转换属性元数据
                converted_attr = self._convert_attribute_metadata(attr, attr_type)

                # 处理主名称属性
                if attr.get("is_primary_name"):
                    if attr_type == "String":
                        converted_attr["IsPrimaryName"] = True
                    else:
                        logger.warning(
                            f"Attribute '{attr.get('name')}' marked as primary name but is not String type. "
                            "Primary name attribute must be String type."
                        )

                converted_attributes.append(converted_attr)

            # 验证主名称属性存在
            has_primary_name = any(
                a.get("is_primary_name") for a in attributes
                if a.get("type") == "String"
            )
            if not has_primary_name:
                # 尝试自动选择第一个 String 属性
                for i, attr in enumerate(attributes):
                    if attr.get("type") == "String":
                        converted_attributes[i]["IsPrimaryName"] = True
                        logger.info(
                            f"Auto-marked '{attr.get('name')}' as primary name attribute"
                        )
                        break

            if converted_attributes:
                entity_definition["Attributes"] = converted_attributes

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
            "AttributeType": attribute_type,
            "AttributeTypeName": {"Value": f"{attribute_type}Type"},
            "SchemaName": attribute.get("schema_name") or attribute.get("name"),
            "DisplayName": self._convert_to_label(attribute.get("display_name", "")),
            "Description": self._convert_to_label(attribute.get("description", "")),
            "RequiredLevel": {
                "Value": "ApplicationRequired" if attribute.get("required") else "None"
            }
        }

        # 类型特定的属性
        if attribute_type == "String":
            attribute_metadata["FormatName"] = {"Value": "Text"}
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
                        "Label": {
                            "@odata.type": "Microsoft.Dynamics.CRM.Label",
                            "LocalizedLabels": [
                                {
                                    "@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel",
                                    "Label": opt.get("label"),
                                    "LanguageCode": 2052
                                }
                            ]
                        }
                    }
                    for opt in options
                ]
            }

        elif attribute_type == "Memo":
            attribute_metadata["MaxLength"] = attribute.get("max_length", 2000)

        elif attribute_type == "DateTime":
            attribute_metadata["Format"] = "DateOnly"

        # 移除空值
        return {k: v for k, v in attribute_metadata.items() if v is not None}

    def _convert_cascade_config(
        self,
        rel_def: dict[str, Any]
    ) -> dict[str, str]:
        """
        转换级联配置

        Args:
            rel_def: 关系定义

        Returns:
            Dataverse 级联配置字典
        """
        # 映射 YAML 配置到 Dataverse 值
        cascade_map = {
            "Active": "Active",       # Parental
            "Cascade": "Cascade",     # 级联
            "NoCascade": "NoCascade",
            "RemoveLink": "RemoveLink",
            "Restrict": "Restrict"
        }

        return {
            "Assign": cascade_map.get(rel_def.get("cascade_assign", "NoCascade")),
            "Delete": cascade_map.get(rel_def.get("cascade_delete", "RemoveLink")),
            "Merge": cascade_map.get(rel_def.get("cascade_merge", "Cascade")),
            "Reparent": cascade_map.get(rel_def.get("cascade_reparent", "NoCascade")),
            "Share": cascade_map.get(rel_def.get("cascade_share", "NoCascade")),
            "Unshare": cascade_map.get(rel_def.get("cascade_unshare", "NoCascade"))
        }

    def _convert_relationship_metadata(
        self,
        entity_name: str,
        rel_def: dict[str, Any],
        lookup_attr_def: dict[str, Any] = None
    ) -> dict[str, Any]:
        """
        转换关系元数据为 Dataverse API 格式

        Args:
            entity_name: 当前实体名称（引用实体/"多"的一方）
            rel_def: 关系定义
            lookup_attr_def: Lookup 属性定义（用于 OneToMany 关系）

        Returns:
            Dataverse API 格式的关系元数据
        """
        rel_type = rel_def.get("relationship_type", "ManyToOne")
        related_entity = rel_def.get("related_entity")

        if rel_type == "ManyToMany":
            # 多对多关系
            return {
                "@odata.type": "Microsoft.Dynamics.CRM.ManyToManyRelationshipMetadata",
                "SchemaName": rel_def.get("schema_name"),
                "Entity1LogicalName": entity_name,
                "Entity2LogicalName": related_entity,
                "IntersectEntityName": rel_def.get("schema_name") or rel_def.get("name"),
                "Entity1AssociatedMenuConfiguration": {
                    "Behavior": "UseLabel",
                    "Group": "Details",
                    "Label": self._convert_to_label(rel_def.get("display_name", entity_name)),
                    "Order": 10000
                },
                "Entity2AssociatedMenuConfiguration": {
                    "Behavior": "UseLabel",
                    "Group": "Details",
                    "Label": self._convert_to_label(rel_def.get("display_name", related_entity)),
                    "Order": 10000
                }
            }
        else:
            # OneToMany 关系（包括 ManyToOne，从对方实体角度创建）
            # ManyToOne 关系实际上是反向的 OneToMany

            # 获取被引用实体的主键
            # 对于标准实体，通常是 entityname + "id"
            # 对于自定义实体，需要查询获取
            referenced_attr = self._get_primary_key_attribute(related_entity)

            # 构建关系定义
            relationship = {
                "@odata.type": "Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata",
                "SchemaName": rel_def.get("schema_name"),
                "ReferencedAttribute": referenced_attr,
                "ReferencedEntity": related_entity,
                "ReferencingEntity": entity_name,
                "AssociatedMenuConfiguration": {
                    "Behavior": "UseCollectionName",
                    "Group": "Details",
                    "Label": self._convert_to_label(rel_def.get("display_name", related_entity)),
                    "Order": 10000
                },
                "CascadeConfiguration": self._convert_cascade_config(rel_def)
            }

            # 添加 Lookup 属性定义（Deep Insert）
            if lookup_attr_def:
                # 使用原始名称（snake_case）
                attr_name = lookup_attr_def.get("name", "")

                relationship["Lookup"] = {
                    "@odata.type": "Microsoft.Dynamics.CRM.LookupAttributeMetadata",
                    "SchemaName": attr_name,
                    "AttributeType": "Lookup",
                    "AttributeTypeName": {"Value": "LookupType"},
                    "DisplayName": self._convert_to_label(lookup_attr_def.get("display_name", "")),
                    "Description": self._convert_to_label(lookup_attr_def.get("description", "")),
                    "RequiredLevel": {
                        "Value": "ApplicationRequired" if lookup_attr_def.get("required") else "None",
                        "CanBeChanged": True,
                        "ManagedPropertyLogicalName": "canmodifyrequirementlevelsettings"
                    },
                    # 关键：指定目标实体（被引用实体）
                    "Targets": [lookup_attr_def.get("target", related_entity)]
                }

            return relationship

    def _get_primary_key_attribute(
        self,
        entity_name: str
    ) -> str:
        """
        获取实体的主键属性名称

        Args:
            entity_name: 实体名称

        Returns:
            主键属性名称（通常是 entityname + "id"）
        """
        # 标准实体和自定义实体的主键通常是 logical_name + "id"
        # 先尝试获取实体元数据
        try:
            entity_meta = self.get_entity_metadata(entity_name)
            primary_id = entity_meta.get("PrimaryIdAttribute")
            if primary_id:
                return primary_id
        except Exception:
            pass

        # 回退到默认规则
        return f"{entity_name}id"

    @retry_on_metadata_error(
        max_retries=5,
        initial_delay=2.5,
        error_patterns=[
            "not found",
            "cannot be found",
            "does not exist",
            "invalid entity",
            "depends on",
            "referenced"
        ]
    )
    def create_relationship(
        self,
        entity_name: str,
        rel_def: dict[str, Any],
        lookup_attr_def: dict[str, Any] = None
    ) -> dict[str, Any]:
        """
        创建关系（包含 Lookup 属性的 Deep Insert）

        Args:
            entity_name: 当前实体名称（引用实体/"多"的一方）
            rel_def: 关系定义
            lookup_attr_def: Lookup 属性定义

        Returns:
            创建的关系元数据
        """
        url = self.get_api_url("RelationshipDefinitions")

        # 转换关系元数据
        relationship_metadata = self._convert_relationship_metadata(
            entity_name,
            rel_def,
            lookup_attr_def
        )

        # 调试日志
        import json as _json
        logger.error(f"create_relationship request: {_json.dumps(relationship_metadata, ensure_ascii=False)[:2000]}...")

        response = self.session.post(url, json=relationship_metadata)

        # 错误时打印响应
        if response.status_code >= 400:
            logger.error(f"create_relationship error response: {response.text}")

        response.raise_for_status()

        # 返回关系信息
        return {
            "schema_name": rel_def.get("schema_name"),
            "type": rel_def.get("relationship_type"),
            "status": "created"
        }

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
