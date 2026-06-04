"""
Power Platform Agent - 元数据代理
处理表、表单、视图、Web Resource等元数据的管理
"""

import json
import logging
from pathlib import Path
from typing import Any

from framework.utils.yaml_parser import YAMLMetadataParser
from framework.utils.schema_validator import SchemaValidator
from framework.utils.naming_converter import NamingConverter, NamingValidator
from framework.utils.dataverse_client import EntityNotFoundError

# 设置日志
logger = logging.getLogger(__name__)

# 组件类型代码映射
COMPONENT_TYPE_CODES = {
    "table": 1,            # 实体 (table 别名)
    "entity": 1,
    "attribute": 2,
    "relationship": 3,
    "optionset": 4,
    "entity_key": 5,
    "stringmap": 6,
    "relationship_role": 7,
    "form": 10,
    "view": 11,
    "savedquery": 12,
    "query": 13,
    "report": 14,
    "dashboard": 15,
    "systemform": 16,
    "webresource": 21,
    "plugin": 90,
    "sdkmessage": 91,
    "sdkmessageprocessingstep": 92,
    "workflow": 93,
}


class MetadataAgent:
    """元数据代理 - 处理Power Platform元数据管理"""

    def __init__(
        self,
        core_agent=None,
        schema_dir: str = "metadata/_schema",
        metadata_dir: str = "metadata"
    ):
        """
        初始化元数据代理

        Args:
            core_agent: 核心代理实例
            schema_dir: Schema目录
            metadata_dir: 元数据目录
        """
        self.core_agent = core_agent
        self.schema_dir = Path(schema_dir)
        self.metadata_dir = Path(metadata_dir)

        # 初始化工具
        self.parser = YAMLMetadataParser(schema_dir)
        self.validator = SchemaValidator(schema_dir)
        self.naming_converter = NamingConverter()
        self.naming_validator = NamingValidator(self.naming_converter)

        # 缓存
        self._metadata_cache: dict[str, Any] = {}

    # ==================== 工具处理 ====================

    async def handle(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """
        处理MCP工具调用

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            处理结果
        """
        try:
            if tool_name == "metadata_parse":
                return await self.parse(
                    arguments.get("file_path"),  # type: ignore[arg-type]
                    arguments.get("type")  # type: ignore[arg-type]
                )

            elif tool_name == "metadata_validate":
                return await self.validate(
                    arguments.get("metadata_yaml"),  # type: ignore[arg-type]
                    arguments.get("schema")  # type: ignore[arg-type]
                )

            elif tool_name == "metadata_create_table":
                return await self.create_table(
                    arguments.get("table_yaml"),  # type: ignore[arg-type]
                    arguments.get("options", {})  # type: ignore[arg-type]
                )

            elif tool_name == "metadata_create_attribute":
                return await self.create_attribute(
                    arguments.get("attribute_yaml"),  # type: ignore[arg-type]
                    arguments.get("entity")  # type: ignore[arg-type]
                )

            elif tool_name == "metadata_create_form":
                return await self.create_form(
                    arguments.get("form_yaml"),
                    arguments.get("mode", "auto"),
                    arguments.get("target_form_id")
                )

            elif tool_name == "metadata_create_view":
                return await self.create_view(
                    arguments.get("view_yaml")  # type: ignore[arg-type]
                )

            elif tool_name == "metadata_export":
                return await self.export(
                    arguments.get("entity"),  # type: ignore[arg-type]
                    arguments.get("output_dir"),  # type: ignore[arg-type]
                    arguments.get("metadata_type", "table")  # type: ignore[arg-type]
                )

            elif tool_name == "metadata_diff":
                return await self.diff(
                    arguments.get("local_path"),  # type: ignore[arg-type]
                    arguments.get("entity")  # type: ignore[arg-type]
                )

            elif tool_name == "metadata_apply":
                return await self.apply(
                    arguments.get("metadata_type"),  # type: ignore[arg-type]
                    arguments.get("name"),  # type: ignore[arg-type]
                    arguments.get("environment")  # type: ignore[arg-type]
                )

            elif tool_name == "metadata_list":
                return await self.list_metadata(
                    arguments.get("type"),  # type: ignore[arg-type]
                    arguments.get("entity")  # type: ignore[arg-type]
                )

            elif tool_name == "metadata_get_form":
                return await self.get_form(
                    arguments.get("entity"),  # type: ignore[arg-type]
                    arguments.get("form_id"),  # type: ignore[arg-type]
                    arguments.get("form_type")  # type: ignore[arg-type]
                )

            elif tool_name == "metadata_list_views":
                return await self.list_views(
                    arguments.get("entity"),  # type: ignore[arg-type]
                    arguments.get("query_type")  # type: ignore[arg-type]
                )

            elif tool_name == "metadata_list_customizable_public_views":
                return await self.list_customizable_public_views(
                    arguments.get("entity")  # type: ignore[arg-type]
                )

            elif tool_name == "metadata_delete":
                return await self.delete_metadata(
                    arguments.get("metadata_type"),  # type: ignore[arg-type]
                    arguments.get("name")  # type: ignore[arg-type]
                )

            elif tool_name == "metadata_sync_webresource":
                return await self.sync_webresource(
                    arguments.get("file_path"),  # type: ignore[arg-type]
                    arguments.get("publisher"),
                    arguments.get("resource_type"),
                    arguments.get("display_name"),
                    arguments.get("environment"),
                    arguments.get("mode", "auto")
                )

            elif tool_name == "metadata_sync_webresource_batch":
                return await self.sync_webresource_batch(
                    arguments.get("source_dir"),  # type: ignore[arg-type]
                    arguments.get("publisher"),
                    arguments.get("file_pattern", "**/*"),
                    arguments.get("environment"),
                    arguments.get("mode", "auto")
                )

            elif tool_name == "metadata_list_webresources":
                return await self.list_webresources(
                    arguments.get("filter"),
                    arguments.get("resource_type")
                )

            elif tool_name == "metadata_export_dictionary":
                return await self.export_data_dictionary(
                    arguments.get("output_dir"),
                    arguments.get("environment"),
                    arguments.get("custom_only", True)
                )

            elif tool_name == "metadata_export_entity_dictionary":
                return await self.export_entity_dictionary(
                    arguments.get("entity_name"),  # type: ignore[arg-type]
                    arguments.get("output_dir"),
                    arguments.get("environment")
                )

            else:
                return json.dumps({
                    "error": f"Unknown tool: {tool_name}"
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": str(e),
                "tool": tool_name
            }, indent=2)

    # ==================== 解析和验证 ====================

    async def parse(
        self,
        file_path: str,
        metadata_type: str = None
    ) -> str:
        """
        解析YAML元数据文件

        Args:
            file_path: YAML文件路径
            metadata_type: 元数据类型

        Returns:
            解析结果
        """
        path = Path(file_path)

        if not path.exists():
            return json.dumps({
                "error": f"File not found: {file_path}"
            }, indent=2)

        try:
            metadata = self.parser.parse_metadata_file(file_path, metadata_type)

            # 缓存解析结果
            self._metadata_cache[str(path)] = metadata

            schema_name = None
            if "schema" in metadata:
                schema_name = metadata["schema"].get("schema_name")
            elif "view" in metadata:
                schema_name = metadata["view"].get("schema_name")
            elif "form" in metadata:
                schema_name = metadata["form"].get("schema_name")
            elif "sitemap" in metadata:
                schema_name = metadata["sitemap"].get("schema_name")

            return json.dumps({
                "success": True,
                "file": str(path),
                "type": metadata_type or "detected",
                "schema_name": schema_name,
                "metadata": metadata
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to parse: {str(e)}"
            }, indent=2)

    async def validate(
        self,
        metadata_yaml: str,
        schema: str
    ) -> str:
        """
        验证元数据

        Args:
            metadata_yaml: YAML文件路径或数据
            schema: Schema类型

        Returns:
            验证结果
        """
        try:
            # 判断是文件路径还是数据
            if isinstance(metadata_yaml, str) and Path(metadata_yaml).exists():
                data = self.parser.load_yaml(metadata_yaml)
            else:
                data = json.loads(metadata_yaml) if isinstance(metadata_yaml, str) else metadata_yaml

            is_valid, errors = self.validator.validate(data, schema)

            return json.dumps({
                "valid": is_valid,
                "errors": errors,
                "schema": schema
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Validation failed: {str(e)}"
            }, indent=2)

    # ==================== 表管理 ====================

    async def create_table(
        self,
        table_yaml: str,
        options: dict[str, Any] = None,
        mode: str = "auto"
    ) -> str:
        """
        创建或更新数据表

        Args:
            table_yaml: 表YAML文件路径或数据
            options: 创建选项
            mode: 操作模式
                - "auto": 自动判断（默认），实体不存在时创建，已存在时跳过
                - "create": 强制创建新表（如果表已存在则报错）
                - "update": 增量更新表（添加新属性、新关系，更新可修改的属性）

        Returns:
            创建/更新结果
        """
        options = options or {}

        try:
            # 解析表元数据
            if isinstance(table_yaml, str) and Path(table_yaml).exists():
                metadata = self.parser.parse_table_yaml(table_yaml)
            else:
                metadata = json.loads(table_yaml) if isinstance(table_yaml, str) else table_yaml

            # 应用命名转换
            schema_name = metadata.get("schema_name")
            is_standard = self.naming_converter.is_standard_entity(schema_name)
            converted_name = self.naming_converter.convert_schema_name(schema_name, is_standard)
            metadata["schema_name"] = converted_name

            # 转换属性名称
            if "attributes" in metadata:
                metadata["attributes"] = self.naming_converter.convert_attributes(
                    metadata["attributes"],
                    schema_name
                )

            # 转换关系名称
            if "relationships" in metadata:
                metadata["relationships"] = self.naming_converter.convert_relationships(
                    metadata["relationships"]
                )

            # 获取客户端
            if self.core_agent:
                client = self.core_agent.get_client(options.get("environment"))
            else:
                return json.dumps({
                    "error": "No core agent available for authentication"
                }, indent=2)

            # 检查实体是否已存在（使用快速检查方法，不重试）
            entity_exists = client.entity_exists(converted_name)
            existing_entity = None
            if entity_exists:
                try:
                    existing_entity = client.get_entity_metadata(converted_name)
                except Exception:
                    pass

            # ========== create 模式：强制创建 ==========
            if mode == "create":
                if entity_exists:
                    return json.dumps({
                        "error": f"Entity '{converted_name}' already exists. Use mode='update' to modify.",
                        "existing_id": existing_entity.get("MetadataId") if existing_entity else None
                    }, indent=2)
                result = client.create_entity(metadata)
                entity_exists = False  # 新创建

            # ========== update 模式：增量更新 ==========
            elif mode == "update":
                if not entity_exists:
                    # 实体不存在，创建新实体
                    result = client.create_entity(metadata)
                    entity_exists = False
                else:
                    # 实体已存在，执行增量更新
                    result = await self._update_entity_incremental(
                        client,
                        converted_name,
                        metadata,
                        existing_entity
                    )

            # ========== auto 模式：自动判断 ==========
            else:  # mode == "auto"
                if entity_exists:
                    result = {"status": "already_exists", "message": "Entity already exists"}
                else:
                    result = client.create_entity(metadata)

            # 创建关系（包含 Lookup 属性的 Deep Insert）
            relationships = metadata.get("relationships", [])
            lookup_attrs = metadata.get("lookup_attributes", [])
            relationship_results = []

            for rel in relationships:
                try:
                    # 检查关系是否已存在
                    rel_exists = False
                    if entity_exists:
                        existing_rels = client.get_relationships(converted_name)
                        rel_schema = rel.get("schema_name")
                        for existing_rel in existing_rels:
                            if existing_rel.get("SchemaName") == rel_schema:
                                rel_exists = True
                                break

                    if rel_exists:
                        relationship_results.append({
                            "relationship": rel.get("schema_name"),
                            "status": "already_exists",
                            "action": "skipped"
                        })
                        continue

                    # 找到对应的 lookup_attribute
                    ref_attr = rel.get("referencing_attribute")
                    lookup_attr = None
                    for attr in lookup_attrs:
                        attr_name = attr.get("schema_name")
                        if attr_name == ref_attr:
                            lookup_attr = attr
                            break

                    # 创建关系
                    rel_result = client.create_relationship(
                        converted_name,
                        rel,
                        lookup_attr
                    )
                    relationship_results.append({
                        "relationship": rel.get("schema_name"),
                        "status": "created",
                        "action": "created",
                        "result": rel_result
                    })
                except Exception as e:
                    relationship_results.append({
                        "relationship": rel.get("schema_name"),
                        "status": "failed",
                        "error": str(e)
                    })

            return json.dumps({
                "success": True,
                "schema_name": converted_name,
                "original_name": schema_name,
                "mode": mode,
                "entity_existed": entity_exists,
                "result": result,
                "relationships": relationship_results
            }, indent=2, ensure_ascii=False)

        except EntityNotFoundError as e:
            return json.dumps({
                "error": f"Entity not found: {str(e)}"
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "error": f"Failed to create table: {str(e)}"
            }, indent=2)

    async def _update_entity_incremental(
        self,
        client: Any,
        entity_name: str,
        metadata: dict[str, Any],
        existing_entity: dict[str, Any]
    ) -> dict[str, Any]:
        """
        增量更新实体元数据

        Args:
            client: Dataverse 客户端
            entity_name: 实体逻辑名称
            metadata: 新的元数据定义
            existing_entity: 现有实体元数据

        Returns:
            更新结果
        """
        import logging
        logger = logging.getLogger(__name__)

        result = {
            "action": "updated",
            "updates": []
        }

        # 1. 更新实体基础属性（可更新的字段）
        schema = metadata.get("schema", {})
        update_payload = {}

        # 可更新的实体属性
        updatable_fields = {
            "DisplayCollectionName": schema.get("display_collection_name"),
            "Description": schema.get("description"),
            "HasNotes": schema.get("has_notes"),
            "IsAuditEnabled": {"Value": schema.get("is_audit_enabled", False)},
        }

        for field, value in updatable_fields.items():
            if value is not None:
                if field == "DisplayCollectionName" and value:
                    update_payload[field] = client._convert_to_label(value)
                elif field == "Description" and value:
                    update_payload[field] = client._convert_to_label(value)
                elif field == "HasNotes":
                    update_payload[field] = value
                elif field == "IsAuditEnabled":
                    update_payload[field] = value

        if update_payload:
            try:
                metadata_id = existing_entity.get("MetadataId")
                url = client.get_api_url(f"EntityDefinitions({metadata_id})")
                response = client.session.patch(url, json=update_payload)
                response.raise_for_status()
                result["updates"].append({
                    "type": "entity_properties",
                    "fields": list(update_payload.keys()),
                    "status": "updated"
                })
            except Exception as e:
                result["updates"].append({
                    "type": "entity_properties",
                    "status": "failed",
                    "error": str(e)
                })

        # 2. 增量更新属性（只添加新属性，不修改现有属性）
        new_attributes = metadata.get("attributes", [])
        if new_attributes:
            existing_attrs = client.get_attributes(entity_name)
            existing_attr_names = {attr.get("LogicalName") for attr in existing_attrs}

            attr_results = []
            for attr in new_attributes:
                attr_type = attr.get("type")
                attr_name = attr.get("schema_name")

                # 跳过 Lookup 类型 - 必须通过关系创建
                if attr_type == "Lookup":
                    logger.info(f"Skipping Lookup attribute '{attr_name}' - must be created via relationship")
                    continue

                # 检查属性是否已存在
                if attr_name in existing_attr_names:
                    attr_results.append({
                        "attribute": attr_name,
                        "status": "already_exists",
                        "action": "skipped"
                    })
                    continue

                # 创建新属性
                try:
                    converted_attr = client._convert_attribute_metadata(attr, attr_type)
                    create_result = client.create_attribute(entity_name, converted_attr)

                    # 检查是否已存在
                    if create_result.get("status") == "already_exists":
                        attr_results.append({
                            "attribute": attr_name,
                            "status": "already_exists",
                            "action": "skipped"
                        })
                    else:
                        attr_results.append({
                            "attribute": attr_name,
                            "type": attr_type,
                            "status": "created",
                            "action": "created"
                        })
                except Exception as e:
                    error_str = str(e).lower()
                    # 检查是否是"已存在"错误
                    if any(x in error_str for x in ["already exists", "already been created", "duplicate", "cannot create duplicate"]):
                        attr_results.append({
                            "attribute": attr_name,
                            "status": "already_exists",
                            "action": "skipped",
                            "error": str(e)
                        })
                    else:
                        attr_results.append({
                            "attribute": attr_name,
                            "status": "failed",
                            "error": str(e)
                        })

            result["updates"].append({
                "type": "attributes",
                "results": attr_results
            })

        return result

    async def create_attribute(
        self,
        attribute_yaml: str,
        entity: str
    ) -> str:
        """
        创建字段

        Args:
            attribute_yaml: 属性YAML文件路径或数据
            entity: 实体名称

        Returns:
            创建结果
        """
        try:
            # 解析属性
            if isinstance(attribute_yaml, str) and Path(attribute_yaml).exists():
                data = self.parser.load_yaml(attribute_yaml)
                attribute = data if "schema_name" in data else data.get("attribute", {})
            else:
                attribute = json.loads(attribute_yaml) if isinstance(attribute_yaml, str) else attribute_yaml

            # 转换属性名
            name = attribute.get("schema_name")
            is_standard = self.naming_converter.is_standard_entity(entity)
            converted_name = self.naming_converter.convert_schema_name(name, is_standard)
            attribute["schema_name"] = converted_name

            # 转换为Dataverse格式
            attr_type = attribute.get("type")
            attribute_metadata = self._convert_attribute_metadata(attribute, attr_type)

            # 获取客户端
            if self.core_agent:
                client = self.core_agent.get_client()
            else:
                return json.dumps({
                    "error": "No core agent available"
                }, indent=2)

            # 创建属性
            result = client.create_attribute(entity, attribute_metadata)

            return json.dumps({
                "success": True,
                "attribute": converted_name,
                "entity": entity,
                "result": result
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to create attribute: {str(e)}"
            }, indent=2)

    def _convert_attribute_metadata(
        self,
        attribute: dict[str, Any],
        attribute_type: str
    ) -> dict[str, Any]:
        """转换属性元数据为Dataverse格式"""
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
        }

        metadata_type = type_mapping.get(attribute_type, type_mapping["String"])

        attribute_metadata = {
            "@odata.type": metadata_type,
            "SchemaName": attribute.get("schema_name"),
            "DisplayName": attribute.get("display_name"),
            "RequiredLevel": {
                "Value": "ApplicationRequired" if attribute.get("required") else "None"
            },
            "IsValidForCreate": True,
            "IsValidForRead": True,
            "IsValidForUpdate": True
        }

        # 类型特定属性
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

    # ==================== 表单查询 ====================

    async def get_form(
        self,
        entity: str,
        form_id: str = None,
        form_type: int = None
    ) -> str:
        """
        获取实体表单

        Args:
            entity: 实体名称
            form_id: 表单GUID（指定后返回单个表单完整数据）
            form_type: 表单类型过滤 (2=Main, 5=Mobile 等)

        Returns:
            表单数据
        """
        try:
            if not self.core_agent:
                return json.dumps({"error": "No core agent available"}, indent=2)

            client = self.core_agent.get_client()

            if form_id:
                form = client.get_form_by_id(form_id)
                return json.dumps({
                    "formid": form.get("formid"),
                    "name": form.get("name"),
                    "description": form.get("description"),
                    "type": form.get("type"),
                    "isdefault": form.get("isdefault"),
                    "formxml": form.get("formxml", ""),
                    "formjson": form.get("formjson")
                }, indent=2, ensure_ascii=False)

            forms = client.get_forms(entity, form_type=form_type)
            type_map = {2: "Main", 5: "Mobile", 6: "QuickCreate", 7: "QuickView", 11: "Card"}
            return json.dumps({
                "entity": entity,
                "count": len(forms),
                "forms": [
                    {
                        "formid": f.get("formid"),
                        "name": f.get("name"),
                        "description": f.get("description"),
                        "type": type_map.get(f.get("type", -1), str(f.get("type"))),
                        "isdefault": f.get("isdefault"),
                        "formxml_length": len(f.get("formxml", "")) if f.get("formxml") else 0
                    }
                    for f in forms
                ]
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": f"Failed to get form: {str(e)}"}, indent=2)

    # ==================== 表单管理 ====================

    async def update_form(self, form_yaml_path: str) -> str:
        """
        基于 YAML 设计更新 Dataverse Main 窗体（始终使用 formxml）。

        策略：
        - 自动检测已有 Main 窗体是否为 Dataverse 自动生成的默认窗体
        - 自动生成的默认窗体 (name="Information", formxml < 2KB) 无法 PATCH，
          自动 POST 新窗体替代
        - 已定制过的窗体直接 PATCH 更新
        - 如 YAML 未指定 form_id，自动查找实体首个 Main 窗体

        Args:
            form_yaml_path: 表单 YAML 文件路径

        Returns:
            执行结果
        """
        import yaml
        from framework.utils.form_xml_builder import FormXmlBuilder

        try:
            if not self.core_agent:
                return json.dumps({"error": "No core agent available"}, indent=2)

            client = self.core_agent.get_client()

            # 1. Parse YAML design
            yaml_file = Path(form_yaml_path)
            if not yaml_file.exists():
                return json.dumps({"error": f"File not found: {form_yaml_path}"}, indent=2)

            with open(yaml_file, "r", encoding="utf-8") as f:
                form_design = yaml.safe_load(f)

            form_meta = form_design.get("form", {})
            entity_name = form_meta.get("entity")
            form_id = form_meta.get("form_id")

            if not entity_name:
                return json.dumps({"error": "form.entity is required in YAML"}, indent=2)

            # 2. Get entity field types
            attrs = client.get_attributes(entity_name)
            entity_fields: dict[str, str] = {}
            for attr in attrs:
                name = attr.get("SchemaName")
                odata_type = attr.get("@odata.type", "")
                if "StringAttributeMetadata" in odata_type:
                    entity_fields[name] = "String"
                elif "LookupAttributeMetadata" in odata_type:
                    entity_fields[name] = "Lookup"
                elif "DateTimeAttributeMetadata" in odata_type:
                    entity_fields[name] = "DateTime"
                elif "MoneyAttributeMetadata" in odata_type:
                    entity_fields[name] = "Money"
                elif "PicklistAttributeMetadata" in odata_type:
                    entity_fields[name] = "Picklist"
                elif "MemoAttributeMetadata" in odata_type:
                    entity_fields[name] = "Memo"
                elif "OwnerAttributeMetadata" in odata_type:
                    entity_fields[name] = "Owner"
                elif "CustomerAttributeMetadata" in odata_type:
                    entity_fields[name] = "Customer"
                else:
                    entity_fields[name] = "Virtual"

            # 3. Build formxml
            builder = FormXmlBuilder(entity_fields)
            form_xml = builder.build(form_design)

            # 4. Resolve target form and decide PATCH vs POST
            if form_id:
                existing = client.get_form_by_id(form_id)
                if self._is_auto_generated_form(existing):
                    new_id = self._post_new_form(client, entity_name, form_meta, form_xml)
                    return json.dumps({
                        "success": True, "entity": entity_name,
                        "form_id": new_id, "action": "create",
                        "reason": "Auto-generated form cannot be patched",
                        "previous_form_id": form_id,
                        "form_xml_length": len(form_xml),
                        "tabs": len(form_design.get("tabs", [])),
                        "message": f"New form {new_id} created to replace auto-generated {form_id}"
                    }, indent=2, ensure_ascii=False)
                else:
                    client.update_form(form_id, {"formxml": form_xml})
                    return json.dumps({
                        "success": True, "entity": entity_name,
                        "form_id": form_id, "action": "update",
                        "form_xml_length": len(form_xml),
                        "tabs": len(form_design.get("tabs", [])),
                        "message": f"Form {form_id} updated via PATCH formxml"
                    }, indent=2, ensure_ascii=False)

            # No form_id: auto-find or create
            forms = client.get_forms(entity_name, form_type=2)
            if not forms:
                new_id = self._post_new_form(client, entity_name, form_meta, form_xml)
                return json.dumps({
                    "success": True, "entity": entity_name,
                    "form_id": new_id, "action": "create",
                    "form_xml_length": len(form_xml),
                    "tabs": len(form_design.get("tabs", [])),
                    "message": f"New form {new_id} created"
                }, indent=2, ensure_ascii=False)

            existing = client.get_form_by_id(forms[0]["formid"])
            if self._is_auto_generated_form(existing):
                new_id = self._post_new_form(client, entity_name, form_meta, form_xml)
                return json.dumps({
                    "success": True, "entity": entity_name,
                    "form_id": new_id, "action": "create",
                    "reason": "Auto-generated form cannot be patched",
                    "form_xml_length": len(form_xml),
                    "tabs": len(form_design.get("tabs", [])),
                    "message": f"New form {new_id} created"
                }, indent=2, ensure_ascii=False)

            form_id = forms[0]["formid"]
            client.update_form(form_id, {"formxml": form_xml})
            return json.dumps({
                "success": True, "entity": entity_name,
                "form_id": form_id, "action": "update",
                "form_xml_length": len(form_xml),
                "tabs": len(form_design.get("tabs", [])),
                "message": f"Form {form_id} updated via PATCH formxml"
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": f"Failed to update form: {str(e)}"}, indent=2)

    @staticmethod
    def _is_auto_generated_form(form: dict[str, Any]) -> bool:
        """Detect if a form is Dataverse auto-generated default form."""
        name = form.get("name", "")
        formxml = form.get("formxml", "")
        return name == "Information" and len(formxml) < 2000

    @staticmethod
    def _post_new_form(
        client: Any,
        entity_name: str,
        form_meta: dict[str, Any],
        form_xml: str,
    ) -> str:
        """POST a new Main form, return new form_id."""
        import uuid as _uuid

        # 验证实体存在并获取逻辑名
        entity_meta = client.get_entity_metadata(entity_name)
        logical_name = entity_meta.get("LogicalName")
        if not logical_name:
            raise ValueError(f"Entity '{entity_name}' not found")

        new_id = str(_uuid.uuid4())
        url = client.get_api_url("systemforms")
        payload = {
            "formid": new_id,
            "name": form_meta.get("display_name", "Main Form"),
            "objecttypecode": logical_name,
            "type": 2,
            "isdefault": True,
            "formxml": form_xml,
        }
        resp = client.session.post(url, json=payload)
        resp.raise_for_status()
        return new_id

    async def list_main_forms(self, entity: str) -> str:
        """
        列出实体的所有 Main 窗体，用于交互式选择

        Args:
            entity: 实体名称

        Returns:
            窗体列表，包含 form_id、name、isdefault、is_auto_generated 等信息
        """
        try:
            if not self.core_agent:
                return json.dumps({"error": "No core agent available"}, indent=2)

            client = self.core_agent.get_client()

            # 获取所有 Main 窗体 (form_type=2)
            forms = client.get_forms(entity, form_type=2)

            form_list = []
            for form in forms:
                form_id = form.get("formid")
                name = form.get("name")
                is_default = form.get("isdefault", False)
                formxml = form.get("formxml", "")

                # 检测是否为自动生成的默认窗体
                is_auto = self._is_auto_generated_form(form)

                form_list.append({
                    "form_id": form_id,
                    "name": name,
                    "is_default": is_default,
                    "is_auto_generated": is_auto,
                    "formxml_length": len(formxml) if formxml else 0,
                    "description": form.get("description", "")
                })

            return json.dumps({
                "entity": entity,
                "count": len(form_list),
                "forms": form_list
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to list forms: {str(e)}"
            }, indent=2)

    async def create_form(
        self,
        form_yaml: str,
        mode: str = "auto",
        target_form_id: str = None
    ) -> str:
        """
        创建或更新表单

        Args:
            form_yaml: 表单YAML文件路径
            mode: 操作模式
                - "auto": 自动判断（默认），根据现有窗体情况自动决定创建或更新
                - "list": 仅列出窗体，不执行创建/更新操作
                - "create_new": 强制创建新窗体
                - "update": 更新指定窗体（需配合 target_form_id）
            target_form_id: 目标窗体ID（mode="update" 时必填）

        Returns:
            执行结果
        """
        try:
            # 解析 YAML 获取实体名
            yaml_file = Path(form_yaml)
            if not yaml_file.exists():
                return json.dumps({"error": f"File not found: {form_yaml}"}, indent=2)

            import yaml
            with open(yaml_file, "r", encoding="utf-8") as f:
                form_design = yaml.safe_load(f)

            form_meta = form_design.get("form", {})
            entity_name = form_meta.get("entity")

            if not entity_name:
                return json.dumps({"error": "form.entity is required in YAML"}, indent=2)

            # list 模式：仅列出窗体
            if mode == "list":
                return await self.list_main_forms(entity_name)

            # create_new 模式：强制创建新窗体
            if mode == "create_new":
                # 临时移除 form_id 以强制创建
                if "form_id" in form_meta:
                    form_meta_copy = dict(form_design)
                    form_meta_copy["form"] = dict(form_meta)
                    del form_meta_copy["form"]["form_id"]
                    # 创建临时文件
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tf:
                        yaml.dump(form_meta_copy, tf, allow_unicode=True)
                        temp_path = tf.name
                    result = await self.update_form(temp_path)
                    Path(temp_path).unlink(missing_ok=True)
                    return result
                return await self.update_form(form_yaml)

            # update 模式：更新指定窗体
            if mode == "update":
                if not target_form_id:
                    return json.dumps({
                        "error": "target_form_id is required when mode='update'"
                    }, indent=2)
                # 在 YAML 中设置 form_id
                form_meta_copy = dict(form_design)
                form_meta_copy["form"] = dict(form_meta)
                form_meta_copy["form"]["form_id"] = target_form_id
                # 创建临时文件
                import tempfile
                with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tf:
                    yaml.dump(form_meta_copy, tf, allow_unicode=True)
                    temp_path = tf.name
                result = await self.update_form(temp_path)
                Path(temp_path).unlink(missing_ok=True)
                return result

            # auto 模式：默认行为
            return await self.update_form(form_yaml)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to create form: {str(e)}"
            }, indent=2)

    # ==================== 视图管理 ====================

    async def create_view(self, view_yaml: str, mode: str = "auto") -> str:
        """
        创建或更新视图

        Args:
            view_yaml: 视图YAML文件路径或数据
            mode: 操作模式
                - "auto": 自动判断（默认），检查视图是否存在后决定创建或更新
                - "create": 强制创建新视图
                - "update": 更新现有视图（需在 YAML 中指定 savedquery_id）
                - "list": 列出实体所有视图

        Returns:
            创建/更新结果
        """
        try:
            if not self.core_agent:
                return json.dumps({"error": "No core agent available"}, indent=2)

            client = self.core_agent.get_client()

            # 解析视图元数据
            if isinstance(view_yaml, str) and Path(view_yaml).exists():
                import yaml
                with open(view_yaml, "r", encoding="utf-8") as f:
                    view_data = yaml.safe_load(f)
                view_meta = view_data.get("view", {})
            else:
                view_data = json.loads(view_yaml) if isinstance(view_yaml, str) else view_yaml
                view_meta = view_data.get("view", {})

            view_name = view_meta.get("schema_name")
            entity = view_meta.get("entity")

            if not entity or not view_name:
                return json.dumps({
                    "error": "view.entity and view.schema_name are required"
                }, indent=2)

            # 验证实体存在
            entity_meta = client.get_entity_metadata(entity)
            logical_name = entity_meta.get("LogicalName")
            if not logical_name:
                return json.dumps({
                    "error": f"Entity '{entity}' not found"
                }, indent=2)

            # list 模式：仅列出可自定义的公共视图
            if mode == "list":
                views = client.get_views(logical_name, query_type=0, is_customizable_only=True)
                return json.dumps({
                    "entity": entity,
                    "query_type": "Public",
                    "customizable_only": True,
                    "count": len(views),
                    "views": [
                        {
                            "savedqueryid": v.get("savedqueryid"),
                            "name": v.get("name"),
                            "is_default": v.get("isdefault", False),
                            "is_customizable": v.get("iscustomizable", {}).get("Value", False),
                            "description": v.get("description", "")
                        }
                        for v in views
                    ]
                }, indent=2, ensure_ascii=False)

            # 检查视图是否已存在
            existing_view = client.get_view_by_name(logical_name, view_name)

            # 构建视图元数据
            view_metadata = self._build_view_metadata(view_meta, view_data, logical_name)

            # create 模式：强制创建
            if mode == "create":
                if existing_view:
                    return json.dumps({
                        "error": f"View '{view_name}' already exists. Use mode='update' to modify.",
                        "existing_id": existing_view.get("savedqueryid")
                    }, indent=2)
                result = client.create_view(view_metadata)
                return json.dumps({
                    "success": True,
                    "action": "create",
                    "entity": entity,
                    "view_name": view_name,
                    "savedqueryid": result.get("savedqueryid"),
                    "message": f"View '{view_name}' created successfully"
                }, indent=2, ensure_ascii=False)

            # update 模式：更新指定视图
            if mode == "update":
                savedquery_id = view_meta.get("savedquery_id")
                if not savedquery_id:
                    return json.dumps({
                        "error": "savedquery_id is required when mode='update'"
                    }, indent=2)

                # 只更新可变字段
                update_payload = {
                    "fetchxml": view_metadata.get("fetchxml"),
                    "layoutxml": view_metadata.get("layoutxml")
                }
                if view_meta.get("description"):
                    update_payload["description"] = view_meta["description"]

                client.update_view(savedquery_id, update_payload)
                return json.dumps({
                    "success": True,
                    "action": "update",
                    "entity": entity,
                    "view_name": view_name,
                    "savedqueryid": savedquery_id,
                    "message": f"View '{view_name}' updated successfully"
                }, indent=2, ensure_ascii=False)

            # auto 模式：自动判断
            if existing_view:
                # 已存在，更新
                savedquery_id = existing_view.get("savedqueryid")
                update_payload = {
                    "fetchxml": view_metadata.get("fetchxml"),
                    "layoutxml": view_metadata.get("layoutxml")
                }
                if view_meta.get("description"):
                    update_payload["description"] = view_meta["description"]

                client.update_view(savedquery_id, update_payload)
                return json.dumps({
                    "success": True,
                    "action": "update",
                    "entity": entity,
                    "view_name": view_name,
                    "savedqueryid": savedquery_id,
                    "message": f"View '{view_name}' updated (already existed)"
                }, indent=2, ensure_ascii=False)
            else:
                # 不存在，创建
                result = client.create_view(view_metadata)
                return json.dumps({
                    "success": True,
                    "action": "create",
                    "entity": entity,
                    "view_name": view_name,
                    "savedqueryid": result.get("savedqueryid"),
                    "message": f"View '{view_name}' created successfully"
                }, indent=2, ensure_ascii=False)

        except Exception as e:
            import traceback
            return json.dumps({
                "error": f"Failed to create view: {str(e)}",
                "traceback": traceback.format_exc()
            }, indent=2)

    def _build_view_metadata(
        self,
        view_meta: dict[str, Any],
        view_data: dict[str, Any],
        logical_name: str
    ) -> dict[str, Any]:
        """
        构建视图元数据用于 API 调用

        Args:
            view_meta: 视图元数据
            view_data: 完整视图数据（包含 columns）
            logical_name: 实体逻辑名称

        Returns:
            API 格式的视图元数据
        """
        # 处理 fetchxml
        fetchxml = view_meta.get("fetch_xml") or view_meta.get("fetchxml")

        # 如果没有提供 fetchxml，从 columns 构建
        if not fetchxml:
            columns = view_data.get("columns", [])
            attributes = [c.get("attribute") for c in columns if c.get("attribute")]

            # 获取排序
            sort_column = next(
                (c for c in columns if c.get("sort_order") == 1),
                None
            )
            order = None
            if sort_column:
                order = {
                    "attribute": sort_column.get("attribute"),
                    "descending": sort_column.get("sort", "asc") == "desc"
                }

            # 构建 fetchxml
            if not self.core_agent:
                raise ValueError("No core agent available for building fetchxml")
            client = self.core_agent.get_client()
            fetchxml = client.build_fetch_xml(logical_name, attributes, order)

        # 处理 layoutxml - 支持 layout_xml 和 layoutxml 两种命名
        layoutxml = view_meta.get("layout_xml") or view_meta.get("layoutxml")
        if not layoutxml:
            columns = view_data.get("columns", [])
            layout_columns = [
                {
                    "name": c.get("attribute"),
                    "width": c.get("width", 100)
                }
                for c in columns if c.get("attribute")
            ]
            if not self.core_agent:
                raise ValueError("No core agent available for building layoutxml")
            client = self.core_agent.get_client()
            layoutxml = client.build_layout_xml(layout_columns)

        # 映射视图类型
        view_type_map = {
            "PublicView": 0,
            "AdvancedFind": 1,
            "AssociatedView": 2,
            "QuickFindView": 4,
            "LookupView": 64
        }
        query_type = view_type_map.get(view_meta.get("type", "PublicView"), 0)

        # 视图名称：使用 display_name 作为显示名称
        # 注意：在 Dataverse 中，视图的 name 字段是显示名称
        view_name = view_meta.get("display_name") or view_meta.get("schema_name")

        # 构建元数据
        metadata = {
            "name": view_name,
            "returnedtypecode": logical_name,
            "querytype": query_type,
            "fetchxml": fetchxml,
            "layoutxml": layoutxml,
            "isdefault": view_meta.get("is_default", False),
            "isquickfindquery": query_type == 4
        }

        # 添加描述
        if view_meta.get("description"):
            metadata["description"] = view_meta["description"]

        return metadata

    async def list_views(self, entity: str, query_type: int = None) -> str:
        """
        列出实体的所有视图

        Args:
            entity: 实体名称
            query_type: 视图类型过滤 (0=Public, 1=AdvancedFind, 2=Associated, 4=QuickFind, 64=Lookup)

        Returns:
            视图列表
        """
        try:
            if not self.core_agent:
                return json.dumps({"error": "No core agent available"}, indent=2)

            client = self.core_agent.get_client()
            views = client.get_views(entity, query_type)

            type_names = {
                0: "Public", 1: "AdvancedFind", 2: "Associated",
                4: "QuickFind", 64: "Lookup"
            }

            return json.dumps({
                "entity": entity,
                "count": len(views),
                "views": [
                    {
                        "savedqueryid": v.get("savedqueryid"),
                        "name": v.get("name"),
                        "type": type_names.get(v.get("querytype", -1), str(v.get("querytype"))),
                        "is_default": v.get("isdefault", False),
                        "is_quick_find": v.get("isquickfindquery", False),
                        "is_customizable": v.get("iscustomizable", {}).get("Value", False)
                    }
                    for v in views
                ]
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to list views: {str(e)}"
            }, indent=2)

    async def list_customizable_public_views(self, entity: str) -> str:
        """
        列出实体的所有可自定义公共视图（IsCustomizable = true）

        用于同步时让用户选择是覆盖更新还是重新创建。

        Args:
            entity: 实体名称

        Returns:
            可自定义公共视图列表，包含 savedqueryid, name, is_default, is_customizable 等信息
        """
        try:
            if not self.core_agent:
                return json.dumps({"error": "No core agent available"}, indent=2)

            client = self.core_agent.get_client()

            # 只获取 Public 视图 (querytype=0) 且可自定义的
            views = client.get_views(entity, query_type=0, is_customizable_only=True)

            return json.dumps({
                "entity": entity,
                "count": len(views),
                "views": [
                    {
                        "savedqueryid": v.get("savedqueryid"),
                        "name": v.get("name"),
                        "is_default": v.get("isdefault", False),
                        "is_customizable": v.get("iscustomizable", {}).get("Value", False),
                        "description": v.get("description", "")
                    }
                    for v in views
                ]
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to list customizable views: {str(e)}"
            }, indent=2)

    # ==================== 导出 ====================

    async def export(
        self,
        entity: str,
        output_dir: str,
        metadata_type: str = "table"
    ) -> str:
        """
        导出元数据为YAML

        Args:
            entity: 实体名称
            output_dir: 输出目录
            metadata_type: 元数据类型

        Returns:
            导出结果
        """
        try:
            if not self.core_agent:
                return json.dumps({
                    "error": "No core agent available"
                }, indent=2)

            client = self.core_agent.get_client()

            if metadata_type == "table":
                # 获取实体元数据
                entity_metadata = client.get_entity_metadata(entity)

                # 转换为YAML格式
                yaml_data = self._export_entity_to_yaml(entity_metadata)

                # 保存文件
                output_path = Path(output_dir) / f"{entity}.yaml"
                self.parser.save_yaml(yaml_data, str(output_path))

                return json.dumps({
                    "success": True,
                    "entity": entity,
                    "output_file": str(output_path)
                }, indent=2, ensure_ascii=False)

            else:
                return json.dumps({
                    "error": f"Export for {metadata_type} not yet implemented"
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to export: {str(e)}"
            }, indent=2)

    def _export_entity_to_yaml(self, entity_metadata: dict[str, Any]) -> dict[str, Any]:
        """将实体元数据转换为YAML格式"""
        return {
            "$schema": "../_schema/table_schema.yaml",
            "schema": {
                "schema_name": entity_metadata.get("SchemaName"),
                "display_name": entity_metadata.get("DisplayName", {}).get("UserLocalizedLabel", {}).get("Label"),
                "description": entity_metadata.get("Description", {}).get("UserLocalizedLabel", {}).get("Label"),
                "ownership_type": entity_metadata.get("OwnershipType"),
                "has_activities": entity_metadata.get("IsActivity", False),
                "has_notes": entity_metadata.get("HasNotes", False)
            },
            "attributes": [],  # 需要额外获取
            "relationships": []  # 需要额外获取
        }

    # ==================== 差异对比 ====================

    async def diff(
        self,
        local_path: str,
        entity: str
    ) -> str:
        """
        对比本地与云端元数据差异

        Args:
            local_path: 本地元数据文件路径
            entity: 实体名称

        Returns:
            差异报告
        """
        try:
            # 解析本地元数据
            local_metadata = self.parser.parse_metadata_file(local_path)

            # 获取云端元数据
            if not self.core_agent:
                return json.dumps({
                    "error": "No core agent available"
                }, indent=2)

            client = self.core_agent.get_client()
            remote_metadata = client.get_entity_metadata(entity)

            # 对比差异
            differences = self._compare_metadata(local_metadata, remote_metadata)

            return json.dumps({
                "entity": entity,
                "local_file": local_path,
                "differences": differences
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to compare: {str(e)}"
            }, indent=2)

    def _compare_metadata(
        self,
        local: dict[str, Any],
        remote: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """对比元数据差异"""
        differences = []

        # 对比表名
        local_name = local.get("schema", {}).get("schema_name")
        remote_name = remote.get("SchemaName")

        if local_name != remote_name:
            differences.append({
                "type": "schema_name",
                "local": local_name,
                "remote": remote_name
            })

        # 对比属性
        local_attrs = local.get("attributes", [])
        remote_attrs = remote.get("Attributes", [])

        local_attr_names = {a.get("schema_name") for a in local_attrs}
        remote_attr_names = {a.get("SchemaName") for a in remote_attrs}

        # 本地有但远程没有的
        for name in local_attr_names - remote_attr_names:
            differences.append({
                "type": "attribute",
                "schema_name": name,
                "status": "local_only"
            })

        # 远程有但本地没有的
        for name in remote_attr_names - local_attr_names:
            differences.append({
                "type": "attribute",
                "schema_name": name,
                "status": "remote_only"
            })

        return differences

    # ==================== 应用元数据 ====================

    async def apply(
        self,
        metadata_type: str,
        name: str,
        environment: str = None
    ) -> str:
        """
        应用元数据到Dataverse

        Args:
            metadata_type: 元数据类型
            name: 名称（文件名或实体名）
            environment: 环境名称

        Returns:
            应用结果
        """
        try:
            # 构建文件路径
            if metadata_type == "table":
                file_path = self.metadata_dir / "tables" / f"{name}.yaml"
                result = await self.create_table(str(file_path), {"environment": environment})

                # 检查是否需要自动添加到解决方案
                await self._auto_add_to_solution(str(file_path), metadata_type, name)

                return result

            elif metadata_type == "form":
                file_path = self.metadata_dir / "forms" / f"{name}.yaml"
                result = await self.create_form(str(file_path))

                # 检查是否需要自动添加到解决方案
                await self._auto_add_to_solution(str(file_path), metadata_type, name)

                return result

            elif metadata_type == "view":
                file_path = self.metadata_dir / "views" / f"{name}.yaml"
                result = await self.create_view(str(file_path))

                # 检查是否需要自动添加到解决方案
                await self._auto_add_to_solution(str(file_path), metadata_type, name)

                return result

            else:
                return json.dumps({
                    "error": f"Unknown metadata type: {metadata_type}"
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to apply: {str(e)}"
            }, indent=2)

    async def _auto_add_to_solution(
        self,
        file_path: str,
        metadata_type: str,
        name: str
    ) -> None:
        """
        检查 YAML 中的 solution 声明，如果 auto_add=true 则自动添加组件到解决方案

        Args:
            file_path: 元数据文件路径
            metadata_type: 元数据类型
            name: 组件名称
        """
        try:
            import yaml

            yaml_file = Path(file_path)
            if not yaml_file.exists():
                return

            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            # 检查 solution 配置
            solution_config = data.get("solution")
            if not solution_config:
                return

            auto_add = solution_config.get("auto_add", False)
            if not auto_add:
                return

            solution_name = solution_config.get("schema_name")
            if not solution_name or not self.core_agent:
                return

            # 获取组件 ID
            client = self.core_agent.get_client()
            component_id = None
            component_type_code = None

            if metadata_type == "table":
                entity_meta = client.get_entity_metadata(name)
                component_id = entity_meta.get("MetadataId")
                component_type_code = COMPONENT_TYPE_CODES.get("entity", 1)

            elif metadata_type == "form":
                forms = client.get_forms(name, form_type=2)
                if forms:
                    component_id = forms[0].get("formid")
                component_type_code = COMPONENT_TYPE_CODES.get("form", 10)

            elif metadata_type == "view":
                entity_meta = client.get_entity_metadata(name)
                logical_name = entity_meta.get("LogicalName")
                if logical_name:
                    views = client.get_views(logical_name, query_type=0)
                    if views:
                        component_id = views[0].get("savedqueryid")
                component_type_code = COMPONENT_TYPE_CODES.get("view", 11)

            # 添加到解决方案
            if component_id and component_type_code and self.core_agent._solution_agent:
                solution_agent = self.core_agent._solution_agent
                await solution_agent.add_component(
                    component_type=metadata_type,
                    component_id=component_id,
                    solution_name=solution_name
                )

        except Exception as e:
            logger.warning(f"Failed to auto-add to solution: {e}")

    # ==================== 列出元数据 ====================

    async def list_metadata(
        self,
        type: str,
        entity: str = None
    ) -> str:
        """
        列出元数据

        Args:
            type: 元数据类型
            entity: 实体名称（可选）

        Returns:
            元数据列表
        """
        try:
            if not self.core_agent:
                return json.dumps({
                    "error": "No core agent available"
                }, indent=2)

            client = self.core_agent.get_client()

            if type == "table":
                entities = client.get_entity_metadata()
                return json.dumps({
                    "type": "table",
                    "items": [
                        {
                            "schema_name": e.get("SchemaName"),
                            "display_name": e.get("DisplayName", {}).get("UserLocalizedLabel", {}).get("Label"),
                            "ownership_type": e.get("OwnershipType")
                        }
                        for e in entities
                    ]
                }, indent=2, ensure_ascii=False)

            elif type == "attribute" and entity:
                attributes = client.get_attributes(entity)
                return json.dumps({
                    "type": "attribute",
                    "entity": entity,
                    "items": [
                        {
                            "schema_name": a.get("SchemaName"),
                            "display_name": a.get("DisplayName", {}).get("UserLocalizedLabel", {}).get("Label"),
                            "type": a.get("@odata.type", "").split(".")[-1]
                        }
                        for a in attributes
                    ]
                }, indent=2, ensure_ascii=False)

            elif type == "form" and entity:
                forms = client.get_forms(entity)
                type_map = {2: "Main", 5: "Mobile", 6: "QuickCreate", 7: "QuickView", 11: "Card"}
                return json.dumps({
                    "type": "form",
                    "entity": entity,
                    "items": [
                        {
                            "formid": f.get("formid"),
                            "name": f.get("name"),
                            "description": f.get("description"),
                            "type": type_map.get(f.get("type", -1), str(f.get("type"))),
                            "isdefault": f.get("isdefault"),
                            "formxml_length": len(f.get("formxml", "")) if f.get("formxml") else 0
                        }
                        for f in forms
                    ]
                }, indent=2, ensure_ascii=False)

            else:
                return json.dumps({
                    "error": f"Unknown type: {type}"
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to list: {str(e)}"
            }, indent=2)

    # ==================== 删除元数据 ====================

    async def delete_metadata(
        self,
        metadata_type: str,
        name: str
    ) -> str:
        """
        删除元数据

        Args:
            metadata_type: 元数据类型
            name: 名称

        Returns:
            删除结果
        """
        # 元数据删除通常需要PAC CLI或特殊API
        return json.dumps({
            "warning": (
                f"Metadata deletion requires careful consideration and "
                f"special handling for {metadata_type}: {name}"
            ),
            "recommendation": "Use solution management to remove components"
        }, indent=2)

    # ==================== Web Resource 同步 ====================

    async def sync_webresource(
        self,
        file_path: str,
        publisher: str = None,
        resource_type: str = None,
        display_name: str = None,
        environment: str = None,
        mode: str = "auto"
    ) -> str:
        """
        同步本地资源文件到 Dataverse

        Args:
            file_path: 本地文件路径
            publisher: 发布商前缀 (默认使用配置中的当前发布商)
            resource_type: 资源类型 (css/js/html/img等)，默认根据文件扩展名推断
            display_name: 显示名称 (默认使用文件名)
            environment: 目标环境
            mode: 操作模式
                - "auto": 自动判断（默认），检查资源是否存在后决定创建或更新
                - "create": 强制创建新资源
                - "update": 更新现有资源

        Returns:
            同步结果
        """
        import base64
        import mimetypes

        try:
            if not self.core_agent:
                return json.dumps({"error": "No core agent available"}, indent=2)

            client = self.core_agent.get_client(environment)

            # 读取文件
            local_file = Path(file_path)
            if not local_file.exists():
                return json.dumps({
                    "error": f"File not found: {file_path}"
                }, indent=2)

            file_name = local_file.name
            file_ext = local_file.suffix.lstrip(".").lower()

            # 获取发布商前缀
            if not publisher:
                publisher_info = self.naming_converter.get_current_publisher()
                if publisher_info:
                    publisher = publisher_info.get("prefix", "new")
                else:
                    publisher = self.naming_converter.prefix

            # 推断资源类型
            if not resource_type:
                type_map = {
                    "css": "css",
                    "js": "js",
                    "html": "html",
                    "htm": "html",
                    "png": "img",
                    "jpg": "img",
                    "jpeg": "img",
                    "gif": "img",
                    "svg": "img",
                    "ico": "img",
                    "xml": "xml",
                    "xslt": "xslt",
                    "xsl": "xslt"
                }
                resource_type = type_map.get(file_ext, file_ext)

            # 构建 Web Resource 名称：{publisher}/{type}/{file_name}
            webresource_name = f"{publisher}/{resource_type}/{file_name}"

            # 获取 Web Resource 类型代码
            wr_type_map = {
                "html": 1,      # HTML
                "css": 2,       # CSS
                "js": 3,        # JavaScript
                "xml": 4,       # XML
                "xslt": 5,      # XSLT
                "png": 6,       # PNG
                "jpg": 7,       # JPG
                "gif": 8,       # GIF
                "jpeg": 7,      # JPG (与 jpg 相同)
                "ico": 9,       # ICO
                "svg": 10,      # SVG
                "img": 6,       # 默认图片类型 (PNG)
                "resx": 11,     # RESX
                "string": 12    # String
            }

            webresource_type = wr_type_map.get(resource_type.lower(), 1)

            # 读取文件内容并编码
            with open(local_file, "rb") as f:
                content_bytes = f.read()

            # 检查是否为文本类型
            text_types = {"html", "css", "js", "xml", "xslt", "xsl"}
            if resource_type.lower() in text_types:
                # 文本类型：读取为 UTF-8 字符串，然后 Base64 编码
                with open(local_file, "r", encoding="utf-8") as f:
                    content_str = f.read()
                content = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
            else:
                # 二进制类型：直接 Base64 编码
                content = base64.b64encode(content_bytes).decode("utf-8")

            # 显示名称
            if not display_name:
                display_name = file_name

            # 检查资源是否已存在
            existing_resources = client.get_webresources(filter=f"name eq '{webresource_name}'")
            existing = existing_resources[0] if existing_resources else None

            # create 模式：强制创建
            if mode == "create":
                if existing:
                    return json.dumps({
                        "error": f"Web Resource '{webresource_name}' already exists. Use mode='update' to modify.",
                        "existing_id": existing.get("webresourceid")
                    }, indent=2)

                result = client.create_webresource(
                    name=webresource_name,
                    display_name=display_name,
                    content=content,
                    webresource_type=webresource_type
                )
                return json.dumps({
                    "success": True,
                    "action": "create",
                    "name": webresource_name,
                    "webresourceid": result.get("webresourceid"),
                    "type": resource_type,
                    "file_path": str(local_file),
                    "size_bytes": len(content_bytes),
                    "message": f"Web Resource '{webresource_name}' created successfully"
                }, indent=2, ensure_ascii=False)

            # update 模式：更新指定资源
            if mode == "update":
                if not existing:
                    return json.dumps({
                        "error": f"Web Resource '{webresource_name}' not found. Use mode='create' to create."
                    }, indent=2)

                webresource_id = existing.get("webresourceid")
                result = client.update_webresource(
                    webresource_id=webresource_id,
                    content=content
                )
                return json.dumps({
                    "success": True,
                    "action": "update",
                    "name": webresource_name,
                    "webresourceid": webresource_id,
                    "type": resource_type,
                    "file_path": str(local_file),
                    "size_bytes": len(content_bytes),
                    "message": f"Web Resource '{webresource_name}' updated successfully"
                }, indent=2, ensure_ascii=False)

            # auto 模式：自动判断
            if existing:
                webresource_id = existing.get("webresourceid")
                result = client.update_webresource(
                    webresource_id=webresource_id,
                    content=content
                )
                return json.dumps({
                    "success": True,
                    "action": "update",
                    "name": webresource_name,
                    "webresourceid": webresource_id,
                    "type": resource_type,
                    "file_path": str(local_file),
                    "size_bytes": len(content_bytes),
                    "message": f"Web Resource '{webresource_name}' updated (already existed)"
                }, indent=2, ensure_ascii=False)
            else:
                result = client.create_webresource(
                    name=webresource_name,
                    display_name=display_name,
                    content=content,
                    webresource_type=webresource_type
                )
                return json.dumps({
                    "success": True,
                    "action": "create",
                    "name": webresource_name,
                    "webresourceid": result.get("webresourceid"),
                    "type": resource_type,
                    "file_path": str(local_file),
                    "size_bytes": len(content_bytes),
                    "message": f"Web Resource '{webresource_name}' created successfully"
                }, indent=2, ensure_ascii=False)

        except Exception as e:
            import traceback
            return json.dumps({
                "error": f"Failed to sync webresource: {str(e)}",
                "traceback": traceback.format_exc()
            }, indent=2)

    async def sync_webresource_batch(
        self,
        source_dir: str,
        publisher: str = None,
        file_pattern: str = "**/*",
        environment: str = None,
        mode: str = "auto"
    ) -> str:
        """
        批量同步本地资源目录到 Dataverse

        Args:
            source_dir: 源目录路径
            publisher: 发布商前缀 (默认使用配置中的当前发布商)
            file_pattern: 文件匹配模式 (默认 **/*)
            environment: 目标环境
            mode: 操作模式 (auto/create/update)

        Returns:
            批量同步结果
        """
        from pathlib import Path

        try:
            source_path = Path(source_dir)
            if not source_path.exists() or not source_path.is_dir():
                return json.dumps({
                    "error": f"Source directory not found: {source_dir}"
                }, indent=2)

            # 支持的文件扩展名
            supported_exts = {
                ".html", ".htm", ".css", ".js",
                ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
                ".xml", ".xslt", ".xsl"
            }

            # 查找所有文件
            files = [
                f for f in source_path.glob(file_pattern)
                if f.is_file() and f.suffix.lower() in supported_exts
            ]

            if not files:
                return json.dumps({
                    "warning": f"No supported files found in {source_dir}",
                    "supported_extensions": list(supported_exts)
                }, indent=2)

            results = []
            success_count = 0
            failed_count = 0

            for file_path in files:
                # 计算相对路径，用于推断 resource_type
                rel_path = file_path.relative_to(source_path)
                parent_dir = rel_path.parent.name if rel_path.parent else ""

                # 推断 resource_type
                file_ext = file_path.suffix.lstrip(".").lower()
                type_map = {
                    "css": "css",
                    "js": "js",
                    "html": "html",
                    "htm": "html",
                    "png": "img",
                    "jpg": "img",
                    "jpeg": "img",
                    "gif": "img",
                    "svg": "img",
                    "ico": "img",
                    "xml": "xml",
                    "xslt": "xslt",
                    "xsl": "xslt"
                }

                # 如果父目录名是有效的类型，使用它
                if parent_dir in type_map.values():
                    resource_type = parent_dir
                else:
                    resource_type = type_map.get(file_ext, file_ext)

                result_str = await self.sync_webresource(
                    file_path=str(file_path),
                    publisher=publisher,
                    resource_type=resource_type,
                    display_name=file_path.name,
                    environment=environment,
                    mode=mode
                )

                result = json.loads(result_str)
                result["file"] = str(file_path)
                results.append(result)

                if result.get("success"):
                    success_count += 1
                else:
                    failed_count += 1

            return json.dumps({
                "success": True,
                "source_dir": str(source_path),
                "total_files": len(files),
                "success_count": success_count,
                "failed_count": failed_count,
                "results": results
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            import traceback
            return json.dumps({
                "error": f"Failed to sync webresources: {str(e)}",
                "traceback": traceback.format_exc()
            }, indent=2)

    async def list_webresources(
        self,
        filter: str = None,
        resource_type: str = None
    ) -> str:
        """
        列出 Web Resources

        Args:
            filter: 可选的过滤条件
            resource_type: 资源类型过滤

        Returns:
            Web Resource 列表
        """
        try:
            if not self.core_agent:
                return json.dumps({"error": "No core agent available"}, indent=2)

            client = self.core_agent.get_client()

            # 构建过滤条件
            odata_filter = filter
            if resource_type:
                # Web Resource 类型代码映射
                type_map = {
                    "html": 1,
                    "css": 2,
                    "js": 3,
                    "xml": 4,
                    "xslt": 5,
                    "png": 6,
                    "jpg": 7,
                    "gif": 8,
                    "ico": 9,
                    "svg": 10
                }
                type_code = type_map.get(resource_type.lower())
                if type_code:
                    type_filter = f"webresourcetype eq {type_code}"
                    if odata_filter:
                        odata_filter = f"{odata_filter} and {type_filter}"
                    else:
                        odata_filter = type_filter

            resources = client.get_webresources(filter=odata_filter)

            # 类型代码到名称的映射
            type_names = {
                1: "HTML", 2: "CSS", 3: "JavaScript", 4: "XML",
                5: "XSLT", 6: "PNG", 7: "JPG", 8: "GIF",
                9: "ICO", 10: "SVG", 11: "RESX", 12: "String"
            }

            return json.dumps({
                "count": len(resources),
                "resources": [
                    {
                        "webresourceid": r.get("webresourceid"),
                        "name": r.get("name"),
                        "displayname": r.get("displayname"),
                        "type": type_names.get(r.get("webresourcetype"), "Unknown"),
                        "type_code": r.get("webresourcetype"),
                        "createdon": r.get("createdon"),
                        "modifiedon": r.get("modifiedon")
                    }
                    for r in resources
                ]
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to list webresources: {str(e)}"
            }, indent=2)

    # ==================== 数据字典导出 ====================

    async def export_data_dictionary(
        self,
        output_dir: str = None,
        environment: str = None,
        custom_only: bool = True
    ) -> str:
        """
        从 Dataverse 环境导出数据字典

        Args:
            output_dir: 输出目录 (默认 docs/data_dictionary)
            environment: 目标环境
            custom_only: 是否只导出自定义表/字段 (默认 True，使用 IsCustomEntity 属性判断)

        Returns:
            导出结果
        """
        import re
        from datetime import datetime
        from pathlib import Path

        try:
            if not self.core_agent:
                return json.dumps({"error": "No core agent available"}, indent=2)

            client = self.core_agent.get_client(environment)

            # 设置输出目录
            if not output_dir:
                project_root = Path(__file__).parent.parent.parent
                output_dir = project_root / "docs" / "data_dictionary"
            else:
                output_dir = Path(output_dir)

            tables_dir = output_dir / "tables"
            tables_dir.mkdir(parents=True, exist_ok=True)

            # 获取所有实体
            entities = client.get_entity_metadata()

            # 过滤自定义实体
            if custom_only:
                filtered_entities = []
                for entity in entities:
                    # 直接使用 IsCustomEntity 属性判断
                    if entity.get("IsCustomEntity", False):
                        filtered_entities.append(entity)

                entities = filtered_entities

            results = {
                "total_entities": len(entities),
                "exported": 0,
                "skipped": 0,
                "tables": []
            }

            for entity in entities:
                schema_name = entity.get("SchemaName", "")
                logical_name = entity.get("LogicalName", "")

                # 获取属性（包括完整的选项集信息）
                try:
                    attributes = client.get_attributes_with_optionsets(logical_name)
                except Exception as e:
                    logger.warning(f"Failed to get attributes for {logical_name}: {e}")
                    results["skipped"] += 1
                    continue

                # 过滤自定义属性和虚拟字段
                filtered_attrs = []
                for attr in attributes:
                    # 过滤自定义属性
                    if custom_only and not attr.get("IsCustomAttribute", False):
                        # 检查 SchemaName 前缀作为备选判断
                        attr_schema = attr.get("SchemaName", "")
                        if not any(attr_schema.lower().startswith(p) for p in ["new_", "custom_"]):
                            continue

                    # 过滤虚拟字段
                    if self._is_virtual_attribute(attr, attributes):
                        continue

                    filtered_attrs.append(attr)

                if not filtered_attrs:
                    results["skipped"] += 1
                    continue

                # 生成文档
                doc_content = self._generate_table_dictionary(entity, filtered_attrs)
                # 使用 logical_name 作为文件名（小写，符合命名规范）
                output_path = tables_dir / f"{logical_name}.md"

                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(doc_content)

                results["exported"] += 1
                results["tables"].append({
                    "schema_name": schema_name,
                    "logical_name": logical_name,
                    "file": str(output_path),
                    "field_count": len(filtered_attrs)
                })

            # 生成汇总文档
            self._generate_dictionary_summary(entities, results, output_dir)

            return json.dumps({
                "success": True,
                "environment": environment or "default",
                "output_dir": str(output_dir),
                "results": results
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            import traceback
            return json.dumps({
                "error": f"Failed to export data dictionary: {str(e)}",
                "traceback": traceback.format_exc()
            }, indent=2)

    async def export_entity_dictionary(
        self,
        entity_name: str,
        output_dir: str = None,
        environment: str = None
    ) -> str:
        """
        导出单个实体的数据字典

        Args:
            entity_name: 实体名称
            output_dir: 输出目录
            environment: 目标环境

        Returns:
            导出结果
        """
        from datetime import datetime
        from pathlib import Path

        try:
            if not self.core_agent:
                return json.dumps({"error": "No core agent available"}, indent=2)

            client = self.core_agent.get_client(environment)

            # 设置输出目录
            if not output_dir:
                project_root = Path(__file__).parent.parent.parent
                output_dir = project_root / "docs" / "data_dictionary"
            else:
                output_dir = Path(output_dir)

            tables_dir = output_dir / "tables"
            tables_dir.mkdir(parents=True, exist_ok=True)

            # 获取实体元数据
            entity = client.get_entity_metadata(entity_name)
            if not entity:
                return json.dumps({
                    "error": f"Entity not found: {entity_name}"
                }, indent=2)

            logical_name = entity.get("LogicalName", "")
            schema_name = entity.get("SchemaName", "")

            # 获取属性（包括完整的选项集信息）
            attributes = client.get_attributes_with_optionsets(logical_name)

            # 过滤虚拟字段
            filtered_attrs = [
                attr for attr in attributes
                if not self._is_virtual_attribute(attr, attributes)
            ]

            # 生成文档
            doc_content = self._generate_table_dictionary(entity, filtered_attrs)
            # 使用 logical_name 作为文件名（小写，符合命名规范）
            output_path = tables_dir / f"{logical_name}.md"

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(doc_content)

            return json.dumps({
                "success": True,
                "entity": entity_name,
                "logical_name": logical_name,
                "schema_name": schema_name,
                "output_file": str(output_path),
                "field_count": len(filtered_attrs)
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            import traceback
            return json.dumps({
                "error": f"Failed to export entity dictionary: {str(e)}",
                "traceback": traceback.format_exc()
            }, indent=2)

    def _is_virtual_attribute(
        self,
        attr: dict[str, Any],
        all_attrs: list[dict[str, Any]]
    ) -> bool:
        """
        判断是否为虚拟属性

        使用 Dataverse API 返回的字段标识，而不是硬编码：
        - AttributeOf: 非空表示是另一个属性的关联字段
        - IsLogical: true 表示是逻辑/虚拟属性
        - IsValidForCreate: false 表示不能用于创建（虚拟字段特征）

        Args:
            attr: 属性元数据
            all_attrs: 所有属性列表（保留参数以兼容）

        Returns:
            True 表示虚拟字段
        """
        # 方法1: AttributeOf 非空表示是关联字段（如 createdbyname -> AttributeOf: createdby）
        if attr.get("AttributeOf"):
            return True

        # 方法2: IsLogical 为 true 表示是逻辑属性
        if attr.get("IsLogical"):
            return True

        # 方法3: 计算字段
        if attr.get("IsComputed"):
            return True

        # 方法4: Rollup 字段
        if attr.get("AggregateType"):
            return True

        # 方法5: Virtual 类型（显式声明为虚拟类型）
        odata_type = attr.get("@odata.type", "")
        if "VirtualAttributeMetadata" in odata_type:
            return True

        # 方法6: 系统虚拟字段（这些字段是 Dataverse 系统字段，通常不需要显示）
        logical_name = attr.get("LogicalName", "").lower()
        system_virtual_fields = {
            "createdon", "createdby", "modifiedon", "modifiedby",
            "createdonbehalfby", "modifiedonbehalfby",
            "ownerid", "owningbusinessunit", "owninguser", "owningteam",
            "statecode", "statuscode",
            "versionnumber", "importsequencenumber", "overriddencreatedon",
            "transactioncurrencyid", "exchangerate",
            "timezonecod", "utcconversiontimezonecode",
            "processid", "stageid",
            "timezoneruleversionnumber",
        }
        if logical_name in system_virtual_fields:
            return True

        return False

    def _get_display_label(self, label_obj: dict[str, Any]) -> str:
        """从 Label 对象获取显示名称"""
        if not label_obj:
            return ""

        # 检查 LocalizedLabels
        localized = label_obj.get("LocalizedLabels", [])
        if localized:
            # 优先使用中文
            for label in localized:
                if label.get("LanguageCode") == 2052:
                    return label.get("Label", "")
            return localized[0].get("Label", "")

        # 检查 UserLocalizedLabel
        user_label = label_obj.get("UserLocalizedLabel", {})
        if user_label:
            return user_label.get("Label", "")

        return ""

    def _get_attribute_type(self, attr: dict[str, Any]) -> str:
        """获取属性类型"""
        odata_type = attr.get("@odata.type", "")

        # 优先使用 AttributeType 字段（更简洁）
        attribute_type = attr.get("AttributeType")
        if attribute_type:
            return attribute_type

        # 先检查完整的类型名称（支持带/不带 # 前缀）
        type_map = {
            # 完整类型名称
            "#Microsoft.Dynamics.CRM.StringAttributeMetadata": "String",
            "Microsoft.Dynamics.CRM.StringAttributeMetadata": "String",
            "#Microsoft.Dynamics.CRM.IntegerAttributeMetadata": "Integer",
            "Microsoft.Dynamics.CRM.IntegerAttributeMetadata": "Integer",
            "#Microsoft.Dynamics.CRM.BigIntAttributeMetadata": "BigInt",
            "Microsoft.Dynamics.CRM.BigIntAttributeMetadata": "BigInt",
            "#Microsoft.Dynamics.CRM.DecimalAttributeMetadata": "Decimal",
            "Microsoft.Dynamics.CRM.DecimalAttributeMetadata": "Decimal",
            "#Microsoft.Dynamics.CRM.DoubleAttributeMetadata": "Double",
            "Microsoft.Dynamics.CRM.DoubleAttributeMetadata": "Double",
            "#Microsoft.Dynamics.CRM.MoneyAttributeMetadata": "Money",
            "Microsoft.Dynamics.CRM.MoneyAttributeMetadata": "Money",
            "#Microsoft.Dynamics.CRM.BooleanAttributeMetadata": "Boolean",
            "Microsoft.Dynamics.CRM.BooleanAttributeMetadata": "Boolean",
            "#Microsoft.Dynamics.CRM.DateTimeAttributeMetadata": "DateTime",
            "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata": "DateTime",
            "#Microsoft.Dynamics.CRM.LookupAttributeMetadata": "Lookup",
            "Microsoft.Dynamics.CRM.LookupAttributeMetadata": "Lookup",
            "#Microsoft.Dynamics.CRM.PicklistAttributeMetadata": "Picklist",
            "Microsoft.Dynamics.CRM.PicklistAttributeMetadata": "Picklist",
            "#Microsoft.Dynamics.CRM.MemoAttributeMetadata": "Memo",
            "Microsoft.Dynamics.CRM.MemoAttributeMetadata": "Memo",
            "#Microsoft.Dynamics.CRM.UniqueIdentifierAttributeMetadata": "Uniqueidentifier",
            "Microsoft.Dynamics.CRM.UniqueIdentifierAttributeMetadata": "Uniqueidentifier",
            "#Microsoft.Dynamics.CRM.CustomerAttributeMetadata": "Customer",
            "Microsoft.Dynamics.CRM.CustomerAttributeMetadata": "Customer",
            "#Microsoft.Dynamics.CRM.OwnerAttributeMetadata": "Owner",
            "Microsoft.Dynamics.CRM.OwnerAttributeMetadata": "Owner",
            "#Microsoft.Dynamics.CRM.StateAttributeMetadata": "State",
            "Microsoft.Dynamics.CRM.StateAttributeMetadata": "State",
            "#Microsoft.Dynamics.CRM.StatusAttributeMetadata": "Status",
            "Microsoft.Dynamics.CRM.StatusAttributeMetadata": "Status",
            "#Microsoft.Dynamics.CRM.MultiSelectPicklistAttributeMetadata": "MultiSelectPicklist",
            "Microsoft.Dynamics.CRM.MultiSelectPicklistAttributeMetadata": "MultiSelectPicklist",
            # 短格式类型名称（某些 API 返回格式）
            "StringAttributeMetadata": "String",
            "IntegerAttributeMetadata": "Integer",
            "BigIntAttributeMetadata": "BigInt",
            "DecimalAttributeMetadata": "Decimal",
            "DoubleAttributeMetadata": "Double",
            "MoneyAttributeMetadata": "Money",
            "BooleanAttributeMetadata": "Boolean",
            "DateTimeAttributeMetadata": "DateTime",
            "LookupAttributeMetadata": "Lookup",
            "PicklistAttributeMetadata": "Picklist",
            "MemoAttributeMetadata": "Memo",
            "UniqueIdentifierAttributeMetadata": "Uniqueidentifier",
            "CustomerAttributeMetadata": "Customer",
            "OwnerAttributeMetadata": "Owner",
            "StateAttributeMetadata": "State",
            "StatusAttributeMetadata": "Status",
            "MultiSelectPicklistAttributeMetadata": "MultiSelectPicklist",
        }

        # 先尝试完整匹配
        if odata_type in type_map:
            return type_map[odata_type]

        # 提取类型名称（去掉命名空间）
        type_name = odata_type.split(".")[-1] if odata_type else ""
        if type_name.endswith("AttributeMetadata"):
            type_name = type_name[:-17]  # 正确去掉 "AttributeMetadata" (17个字符)

        # 返回映射的类型或原始类型名称
        return type_map.get(type_name, type_name)

    def _get_required_level(self, attr: dict[str, Any]) -> str:
        """获取必填状态"""
        required_level = attr.get("RequiredLevel", {})
        if isinstance(required_level, dict):
            value = required_level.get("Value", "None")
        else:
            value = str(required_level)

        if value in ("ApplicationRequired", "SystemRequired", "None"):
            if value == "None":
                return "否"
            return "是" if value != "None" else "否"
        return "否"

    def _get_lookup_targets(self, attr: dict[str, Any]) -> str:
        """获取 Lookup 目标实体"""
        targets = attr.get("Targets", [])
        if targets:
            return ", ".join(f"`{t}`" for t in targets)
        return ""

    def _get_option_set_info(self, attr: dict[str, Any]) -> str:
        """
        获取选项集信息，格式化为 label:value; label:value

        支持全局选项集和本地选项集
        """
        option_set = attr.get("OptionSet", {})
        if not option_set:
            return ""

        options = option_set.get("Options", [])
        if not options:
            return ""

        # 格式化为 label:value; label:value
        parts = []
        for opt in options:
            value = opt.get("Value", "")
            label_obj = opt.get("Label", {})
            label = self._get_display_label(label_obj)

            if label and value is not None:
                parts.append(f"{label}:{value}")

        return "; ".join(parts) if parts else ""

    def _generate_table_dictionary(
        self,
        entity: dict[str, Any],
        attributes: list[dict[str, Any]]
    ) -> str:
        """生成表的数据字典内容"""
        from datetime import datetime

        schema_name = entity.get("SchemaName", "")
        logical_name = entity.get("LogicalName", "")
        display_name = self._get_display_label(entity.get("DisplayName", {}))
        description = self._get_display_label(entity.get("Description", {}))
        ownership_type = entity.get("OwnershipType", "UserOwned")

        lines = [
            f"# {display_name} (`{schema_name}`)",
            "",
            f"**Logical Name**: `{logical_name}`",
            "",
            f"**说明**: {description or '-'}",
            "",
            f"**所有权类型**: `{ownership_type}`",
            "",
            "---",
            "",
            "## 字段列表",
            "",
            "| Schema Name | 中文显示名称 | 类型 | 必填 | 说明 | Lookup对象 | 选项集引用 |",
            "|-------------|--------------|------|------|------|-----------|-----------|",
        ]

        for attr in attributes:
            attr_schema = attr.get("SchemaName", "")
            attr_display = self._get_display_label(attr.get("DisplayName", {}))
            attr_type = self._get_attribute_type(attr)
            required = self._get_required_level(attr)
            attr_desc = self._get_display_label(attr.get("Description", {}))
            lookup_targets = self._get_lookup_targets(attr)
            option_set_info = self._get_option_set_info(attr)

            # 处理说明中的换行
            if "\n" in attr_desc:
                attr_desc = attr_desc.replace("\n", "<br>")

            lines.append(
                f"| `{attr_schema}` | {attr_display} | `{attr_type}` | {required} | {attr_desc} | {lookup_targets} | {option_set_info} |"
            )

        # 添加元数据
        lines.extend([
            "",
            "---",
            "",
            "## 元数据",
            "",
            f"- **Schema Name**: `{schema_name}`",
            f"- **Logical Name**: `{logical_name}`",
            f"- **Entity Set Name**: `{entity.get('EntitySetName', '')}`",
            f"- **Primary Id Attribute**: `{entity.get('PrimaryIdAttribute', '')}`",
            f"- **Primary Name Attribute**: `{entity.get('PrimaryNameAttribute', '')}`",
            f"- **Is Custom Entity**: {entity.get('IsCustomEntity', False)}",
            f"- **导出时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        ])

        return "\n".join(lines)

    def _generate_dictionary_summary(
        self,
        entities: list[dict[str, Any]],
        results: dict[str, Any],
        output_dir: Path
    ) -> None:
        """生成汇总文档"""
        from datetime import datetime

        lines = [
            "# 数据字典 - 从环境导出",
            "",
            f"*导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            "---",
            "",
            "## 统计",
            "",
            f"- 总实体数: {len(entities)}",
            f"- 已导出: {results['exported']}",
            f"- 跳过: {results['skipped']}",
            "",
            "---",
            "",
            "## 表列表",
            "",
            "| 表名 | Schema Name | Logical Name | 字段数 |",
            "|------|-------------|--------------|--------|",
        ]

        for table_info in results.get("tables", []):
            schema_name = table_info.get("schema_name", "")
            logical_name = table_info.get("logical_name", "")
            # 从 entities 获取显示名称
            display_name = "-"
            for entity in entities:
                if entity.get("SchemaName") == schema_name:
                    display_name = self._get_display_label(entity.get("DisplayName", {}))
                    break

            field_count = table_info.get("field_count", 0)
            display_linked = f"[{display_name}](tables/{schema_name}.md)"
            lines.append(f"| {display_linked} | `{schema_name}` | `{logical_name}` | {field_count} |")

        output_path = output_dir / "from_env_tables.md"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
