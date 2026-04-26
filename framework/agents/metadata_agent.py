"""
Power Platform Agent - 元数据代理
处理表、表单、视图、Web Resource等元数据的管理
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.yaml_parser import YAMLMetadataParser
from utils.schema_validator import SchemaValidator
from utils.naming_converter import NamingConverter, NamingValidator
from utils.dataverse_client import EntityNotFoundError

# 设置日志
logger = logging.getLogger(__name__)


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
        self._metadata_cache = {}

    # ==================== 工具处理 ====================

    async def handle(self, tool_name: str, arguments: Dict[str, Any]) -> str:
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
                    arguments.get("file_path"),
                    arguments.get("type")
                )

            elif tool_name == "metadata_validate":
                return await self.validate(
                    arguments.get("metadata_yaml"),
                    arguments.get("schema")
                )

            elif tool_name == "metadata_create_table":
                return await self.create_table(
                    arguments.get("table_yaml"),
                    arguments.get("options", {})
                )

            elif tool_name == "metadata_create_attribute":
                return await self.create_attribute(
                    arguments.get("attribute_yaml"),
                    arguments.get("entity")
                )

            elif tool_name == "metadata_create_form":
                return await self.create_form(
                    arguments.get("form_yaml")
                )

            elif tool_name == "metadata_create_view":
                return await self.create_view(
                    arguments.get("view_yaml")
                )

            elif tool_name == "metadata_export":
                return await self.export(
                    arguments.get("entity"),
                    arguments.get("output_dir"),
                    arguments.get("metadata_type", "table")
                )

            elif tool_name == "metadata_diff":
                return await self.diff(
                    arguments.get("local_path"),
                    arguments.get("entity")
                )

            elif tool_name == "metadata_apply":
                return await self.apply(
                    arguments.get("metadata_type"),
                    arguments.get("name"),
                    arguments.get("environment")
                )

            elif tool_name == "metadata_list":
                return await self.list_metadata(
                    arguments.get("type"),
                    arguments.get("entity")
                )

            elif tool_name == "metadata_get_form":
                return await self.get_form(
                    arguments.get("entity"),
                    arguments.get("form_id"),
                    arguments.get("form_type")
                )

            elif tool_name == "metadata_delete":
                return await self.delete_metadata(
                    arguments.get("metadata_type"),
                    arguments.get("name")
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
        metadata_type: Optional[str] = None
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
        options: Dict[str, Any] = None
    ) -> str:
        """
        创建数据表

        Args:
            table_yaml: 表YAML文件路径或数据
            options: 创建选项

        Returns:
            创建结果
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

            # 创建表
            result = client.create_entity(metadata)

            return json.dumps({
                "success": True,
                "schema_name": converted_name,
                "original_name": schema_name,
                "result": result
            }, indent=2, ensure_ascii=False)

        except EntityNotFoundError as e:
            return json.dumps({
                "error": f"Entity not found: {str(e)}"
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "error": f"Failed to create table: {str(e)}"
            }, indent=2)

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
                attribute = data if "name" in data else data.get("attribute", {})
            else:
                attribute = json.loads(attribute_yaml) if isinstance(attribute_yaml, str) else attribute_yaml

            # 转换属性名
            name = attribute.get("name")
            is_standard = self.naming_converter.is_standard_entity(entity)
            converted_name = self.naming_converter.convert_schema_name(name, is_standard)
            attribute["name"] = converted_name

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
        attribute: Dict[str, Any],
        attribute_type: str
    ) -> Dict[str, Any]:
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
            "SchemaName": attribute.get("name"),
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
        form_id: Optional[str] = None,
        form_type: Optional[int] = None
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
        import uuid as _uuid
        from utils.form_xml_builder import FormXmlBuilder

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
            entity_fields: Dict[str, str] = {}
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
    def _is_auto_generated_form(form: Dict[str, Any]) -> bool:
        """Detect if a form is Dataverse auto-generated default form."""
        name = form.get("name", "")
        formxml = form.get("formxml", "")
        return name == "Information" and len(formxml) < 2000

    @staticmethod
    def _post_new_form(
        client: Any,
        entity_name: str,
        form_meta: Dict[str, Any],
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

    async def create_form(self, form_yaml: str) -> str:
        """
        创建或更新表单（委托给 update_form）

        Args:
            form_yaml: 表单YAML文件路径

        Returns:
            执行结果
        """
        if isinstance(form_yaml, str) and Path(form_yaml).exists():
            return await self.update_form(form_yaml)
        return json.dumps({
            "error": "create_form requires a YAML file path argument"
        }, indent=2)

    # ==================== 视图管理 ====================

    async def create_view(self, view_yaml: str) -> str:
        """
        创建视图

        Args:
            view_yaml: 视图YAML文件路径或数据

        Returns:
            创建结果
        """
        try:
            # 解析视图元数据
            if isinstance(view_yaml, str) and Path(view_yaml).exists():
                metadata = self.parser.parse_view_yaml(view_yaml)
            else:
                metadata = json.loads(view_yaml) if isinstance(view_yaml, str) else view_yaml

            schema_name = metadata.get("schema_name")
            entity = metadata.get("entity")

            return json.dumps({
                "success": True,
                "schema_name": schema_name,
                "entity": entity,
                "message": "View creation requires additional implementation via PAC CLI or direct API"
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to create view: {str(e)}"
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

    def _export_entity_to_yaml(self, entity_metadata: Dict[str, Any]) -> Dict[str, Any]:
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
        local: Dict[str, Any],
        remote: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
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

        local_attr_names = {a.get("name") for a in local_attrs}
        remote_attr_names = {a.get("SchemaName") for a in remote_attrs}

        # 本地有但远程没有的
        for name in local_attr_names - remote_attr_names:
            differences.append({
                "type": "attribute",
                "name": name,
                "status": "local_only"
            })

        # 远程有但本地没有的
        for name in remote_attr_names - local_attr_names:
            differences.append({
                "type": "attribute",
                "name": name,
                "status": "remote_only"
            })

        return differences

    # ==================== 应用元数据 ====================

    async def apply(
        self,
        metadata_type: str,
        name: str,
        environment: Optional[str] = None
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
                return await self.create_table(str(file_path), {"environment": environment})

            elif metadata_type == "form":
                file_path = self.metadata_dir / "forms" / f"{name}.yaml"
                return await self.create_form(str(file_path))

            elif metadata_type == "view":
                file_path = self.metadata_dir / "views" / f"{name}.yaml"
                return await self.create_view(str(file_path))

            else:
                return json.dumps({
                    "error": f"Unknown metadata type: {metadata_type}"
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to apply: {str(e)}"
            }, indent=2)

    # ==================== 列出元数据 ====================

    async def list_metadata(
        self,
        type: str,
        entity: Optional[str] = None
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
