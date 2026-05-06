"""
Power Platform YAML元数据解析器
解析和生成Power Platform元数据的YAML格式
"""

import logging
from pathlib import Path
from typing import Any
import yaml

# 设置日志
logger = logging.getLogger(__name__)


class YAMLMetadataParser:
    """YAML元数据解析器"""

    def __init__(self, schema_dir: str = None):
        """
        初始化解析器

        Args:
            schema_dir: Schema文件目录
        """
        self.schema_dir = Path(schema_dir or "metadata/_schema")
        self._schema_cache = {}

    # ==================== 通用方法 ====================

    def load_yaml(self, file_path: str) -> dict[str, Any]:
        """
        加载YAML文件

        Args:
            file_path: YAML文件路径

        Returns:
            解析后的数据字典
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"YAML file not found: {file_path}")

        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def save_yaml(
        self,
        data: dict[str, Any],
        file_path: str,
        sort_keys: bool = False
    ) -> None:
        """
        保存为YAML文件

        Args:
            data: 要保存的数据
            file_path: 目标文件路径
            sort_keys: 是否排序键
        """
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(
                data,
                f,
                allow_unicode=True,
                sort_keys=sort_keys,
                default_flow_style=False,
                width=120
            )

    def parse_metadata_file(
        self,
        file_path: str,
        metadata_type: str = None
    ) -> dict[str, Any]:
        """
        解析元数据文件

        Args:
            file_path: 元数据文件路径
            metadata_type: 元数据类型（table/form/view/webresource等）

        Returns:
            解析后的元数据
        """
        data = self.load_yaml(file_path)

        # 自动检测类型
        if metadata_type is None:
            metadata_type = self._detect_metadata_type(data, file_path)

        # 验证并返回
        return self._process_metadata(data, metadata_type)

    def _detect_metadata_type(
        self,
        data: dict[str, Any],
        file_path: str
    ) -> str:
        """从文件路径和内容检测元数据类型"""
        path = Path(file_path)

        # 从路径检测
        if "tables" in path.parts or "schema" in data:
            return "table"
        elif "forms" in path.parts or "form" in data:
            return "form"
        elif "views" in path.parts or "view" in data:
            return "view"
        elif "solutions" in path.parts or "solution" in data:
            return "solution"
        elif "webresources" in path.parts or "resources" in data:
            return "webresource"
        elif "ribbon" in path.parts or "ribbon" in data:
            return "ribbon"
        elif "sitemap" in path.parts or "sitemap" in data:
            return "sitemap"
        elif "plugin" in path.parts:
            return "plugin"

        # 从内容检测
        if "schema" in data and "attributes" in data:
            return "table"
        elif "form" in data and "tabs" in data:
            return "form"
        elif "view" in data and "columns" in data:
            return "view"
        elif "resources" in data:
            return "webresource"
        elif "ribbon" in data:
            return "ribbon"
        elif "sitemap" in data:
            return "sitemap"

        return "unknown"

    def _process_metadata(
        self,
        data: dict[str, Any],
        metadata_type: str
    ) -> dict[str, Any]:
        """处理元数据"""
        if metadata_type == "table":
            return self._process_table_metadata(data)
        elif metadata_type == "form":
            return self._process_form_metadata(data)
        elif metadata_type == "view":
            return self._process_view_metadata(data)
        elif metadata_type == "solution":
            return self._process_solution_metadata(data)
        elif metadata_type == "webresource":
            return self._process_webresource_metadata(data)
        elif metadata_type == "ribbon":
            return self._process_ribbon_metadata(data)
        elif metadata_type == "sitemap":
            return self._process_sitemap_metadata(data)
        elif metadata_type == "plugin":
            return self._process_plugin_metadata(data)
        else:
            return data

    # ==================== 表元数据 ====================

    def parse_table_yaml(self, file_path: str) -> dict[str, Any]:
        """
        解析表元数据YAML文件

        Args:
            file_path: YAML文件路径

        Returns:
            表元数据字典
        """
        data = self.load_yaml(file_path)
        return self._process_table_metadata(data)

    def _process_table_metadata(
        self,
        data: dict[str, Any]
    ) -> dict[str, Any]:
        """处理表元数据"""
        schema = data.get("schema", {})

        return {
            "schema_name": schema.get("schema_name"),
            "display_name": schema.get("display_name"),
            "description": schema.get("description"),
            "ownership_type": schema.get("ownership_type", "UserOwned"),
            "has_activities": schema.get("has_activities", False),
            "has_notes": schema.get("has_notes", False),
            "is_audit_enabled": schema.get("is_audit_enabled", False),
            "options": schema.get("options", {}),
            "attributes": data.get("attributes", []),
            "lookup_attributes": data.get("lookup_attributes", []),
            "relationships": data.get("relationships", [])
        }

    def generate_table_yaml(
        self,
        schema_name: str,
        display_name: str,
        attributes: list[dict[str, Any]] = None,
        **kwargs
    ) -> dict[str, Any]:
        """
        生成表元数据YAML

        Args:
            schema_name: Schema名称
            display_name: 显示名称
            attributes: 属性列表
            **kwargs: 其他属性

        Returns:
            表元数据字典
        """
        data = {
            "$schema": "../_schema/table_schema.yaml",
            "schema": {
                "schema_name": schema_name,
                "display_name": display_name
            }
        }

        # 添加可选字段
        for key in ["description", "ownership_type", "has_activities", "has_notes", "is_audit_enabled"]:
            if key in kwargs:
                data["schema"][key] = kwargs[key]

        if attributes:
            data["attributes"] = attributes

        if "relationships" in kwargs:
            data["relationships"] = kwargs["relationships"]

        if "options" in kwargs:
            data["schema"]["options"] = kwargs["options"]

        return data

    # ==================== 表单元数据 ====================

    def parse_form_yaml(self, file_path: str) -> dict[str, Any]:
        """
        解析表单元数据YAML文件

        Args:
            file_path: YAML文件路径

        Returns:
            表单元数据字典
        """
        data = self.load_yaml(file_path)
        return self._process_form_metadata(data)

    def _process_form_metadata(
        self,
        data: dict[str, Any]
    ) -> dict[str, Any]:
        """处理表单元数据"""
        form = data.get("form", {})

        return {
            "schema_name": form.get("schema_name"),
            "entity": form.get("entity"),
            "type": form.get("type"),
            "display_name": form.get("display_name"),
            "description": form.get("description"),
            "is_default": form.get("is_default", False),
            "options": form.get("options", {}),
            "tabs": data.get("tabs", []),
            "webresources": data.get("webresources", []),
            "events": data.get("events", [])
        }

    # ==================== 视图元数据 ====================

    def parse_view_yaml(self, file_path: str) -> dict[str, Any]:
        """
        解析视图元数据YAML文件

        Args:
            file_path: YAML文件路径

        Returns:
            视图元数据字典
        """
        data = self.load_yaml(file_path)
        return self._process_view_metadata(data)

    def _process_view_metadata(
        self,
        data: dict[str, Any]
    ) -> dict[str, Any]:
        """处理视图元数据"""
        view = data.get("view", {})

        return {
            "schema_name": view.get("schema_name"),
            "entity": view.get("entity"),
            "type": view.get("type"),
            "display_name": view.get("display_name"),
            "description": view.get("description"),
            "is_default": view.get("is_default", False),
            "fetch_xml": view.get("fetch_xml"),
            "fetchxml": view.get("fetchxml"),
            "columns": data.get("columns", []),
            "layout": data.get("layout", {}),
            "charts": data.get("charts", [])
        }

    # ==================== 解决方案元数据 ====================

    def parse_solution_yaml(self, file_path: str) -> dict[str, Any]:
        """
        解析解决方案元数据YAML文件

        Args:
            file_path: YAML文件路径

        Returns:
            解决方案元数据字典
        """
        data = self.load_yaml(file_path)
        return self._process_solution_metadata(data)

    def _process_solution_metadata(
        self,
        data: dict[str, Any]
    ) -> dict[str, Any]:
        """处理解决方案元数据"""
        solution = data.get("solution", {})

        return {
            "schema_name": solution.get("schema_name"),
            "display_name": solution.get("display_name"),
            "description": solution.get("description"),
            "version": solution.get("version"),
            "publisher": solution.get("publisher"),
            "type": solution.get("type", "Unmanaged"),
            "components": data.get("components", {}),
            "sync": data.get("sync", {}),
            "validation": data.get("validation", {}),
            "build": data.get("build", {})
        }

    def generate_solution_yaml(
        self,
        schema_name: str,
        display_name: str,
        version: str = "1.0.0.0",
        **kwargs
    ) -> dict[str, Any]:
        """
        生成解决方案元数据YAML

        Args:
            schema_name: 解决方案唯一名称（SolutionUniqueName）
            display_name: 显示名称
            version: 版本号
            **kwargs: 其他属性

        Returns:
            解决方案元数据字典
        """
        data = {
            "$schema": "../_schema/solution_schema.yaml",
            "solution": {
                "schema_name": schema_name,
                "display_name": display_name,
                "version": version
            },
            "components": {
                "tables": [],
                "forms": [],
                "views": [],
                "optionsets": [],
                "webresources": [],
                "plugins": [],
                "other": []
            },
            "sync": {
                "enabled": True,
                "direction": "local_to_remote",
                "on_conflict": "skip",
                "order": ["table", "optionset", "form", "view", "webresource", "plugin"]
            },
            "validation": {
                "strict_mode": False,
                "check_dependencies": True,
                "check_naming": True
            },
            "build": {
                "auto_increment_version": False,
                "export_as_managed": False,
                "include_dependencies": True
            }
        }

        # 添加可选字段
        if "description" in kwargs:
            data["solution"]["description"] = kwargs["description"]
        if "publisher" in kwargs:
            data["solution"]["publisher"] = kwargs["publisher"]
        if "type" in kwargs:
            data["solution"]["type"] = kwargs["type"]
        if "components" in kwargs:
            data["components"].update(kwargs["components"])

        return data

    # ==================== Web Resource元数据 ====================

    def parse_webresource_yaml(self, file_path: str) -> dict[str, Any]:
        """
        解析Web Resource元数据YAML文件

        Args:
            file_path: YAML文件路径

        Returns:
            Web Resource元数据字典
        """
        data = self.load_yaml(file_path)
        return self._process_webresource_metadata(data)

    def _process_webresource_metadata(
        self,
        data: dict[str, Any]
    ) -> dict[str, Any]:
        """处理Web Resource元数据"""
        return {
            "naming": data.get("naming", {}),
            "resources": data.get("resources", []),
            "icons": data.get("icons", []),
            "type_mapping": data.get("type_mapping", {})
        }

    # ==================== Ribbon元数据 ====================

    def parse_ribbon_yaml(self, file_path: str) -> dict[str, Any]:
        """
        解析Ribbon元数据YAML文件

        Args:
            file_path: YAML文件路径

        Returns:
            Ribbon元数据字典
        """
        data = self.load_yaml(file_path)
        return self._process_ribbon_metadata(data)

    def _process_ribbon_metadata(
        self,
        data: dict[str, Any]
    ) -> dict[str, Any]:
        """处理Ribbon元数据"""
        ribbon = data.get("ribbon", {})

        return {
            "schema_name": ribbon.get("schema_name"),
            "entity": ribbon.get("entity"),
            "display_name": ribbon.get("display_name"),
            "description": ribbon.get("description"),
            "buttons": ribbon.get("buttons", []),
            "menus": ribbon.get("menus", []),
            "groups": ribbon.get("groups", []),
            "tabs": ribbon.get("tabs", []),
            "scaling": ribbon.get("scaling", [])
        }

    # ==================== Sitemap元数据 ====================

    def parse_sitemap_yaml(self, file_path: str) -> dict[str, Any]:
        """
        解析Sitemap元数据YAML文件

        Args:
            file_path: YAML文件路径

        Returns:
            Sitemap元数据字典
        """
        data = self.load_yaml(file_path)
        return self._process_sitemap_metadata(data)

    def _process_sitemap_metadata(
        self,
        data: dict[str, Any]
    ) -> dict[str, Any]:
        """处理Sitemap元数据"""
        sitemap = data.get("sitemap", {})

        return {
            "schema_name": sitemap.get("schema_name"),
            "display_name": sitemap.get("display_name"),
            "description": sitemap.get("description"),
            "version": sitemap.get("version"),
            "areas": sitemap.get("areas", []),
            "settings": sitemap.get("settings", {}),
            "properties": sitemap.get("properties", {})
        }

    # ==================== Plugin元数据 ====================

    def parse_plugin_yaml(self, file_path: str) -> dict[str, Any]:
        """
        解析Plugin元数据YAML文件

        Args:
            file_path: YAML文件路径

        Returns:
            Plugin元数据字典
        """
        data = self.load_yaml(file_path)
        return self._process_plugin_metadata(data)

    def _process_plugin_metadata(
        self,
        data: dict[str, Any]
    ) -> dict[str, Any]:
        """处理Plugin元数据"""
        assembly = data.get("assembly", {})

        return {
            "solution": data.get("solution", {}),
            "assembly": {
                "schema_name": assembly.get("schema_name"),
                "display_name": assembly.get("display_name"),
                "description": assembly.get("description"),
                "version": assembly.get("version"),
                "project_path": assembly.get("project_path"),
                "build_configuration": assembly.get("build_configuration", "Release"),
                "source_type": assembly.get("source_type", 0)
            },
            "steps": data.get("steps", []),
            "custom_actions": data.get("custom_actions", [])
        }

    # ==================== 属性处理 ====================

    def parse_attribute(
        self,
        attribute_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        解析单个属性定义

        Args:
            attribute_data: 属性数据

        Returns:
            标准化的属性字典
        """
        return {
            "schema_name": attribute_data.get("schema_name"),
            "type": attribute_data.get("type"),
            "display_name": attribute_data.get("display_name"),
            "description": attribute_data.get("description"),
            "required": attribute_data.get("required", False),
            "max_length": attribute_data.get("max_length"),
            "min_value": attribute_data.get("min_value"),
            "max_value": attribute_data.get("max_value"),
            "precision": attribute_data.get("precision"),
            "default_value": attribute_data.get("default_value"),
            "is_primary_name": attribute_data.get("is_primary_name", False),
            "options": attribute_data.get("options", []),
            "entity": attribute_data.get("entity"),
            "relationship_name": attribute_data.get("relationship_name")
        }

    # ==================== FetchXML处理 ====================

    def build_fetch_xml(
        self,
        entity: str,
        attributes: list[str],
        filter_conditions: list[dict[str, Any]] = None,
        order_by: str = None,
        top: int = None
    ) -> str:
        """
        构建Fetch XML查询

        Args:
            entity: 实体名称
            attributes: 属性列表
            filter_conditions: 过滤条件
            order_by: 排序字段
            top: 返回记录数

        Returns:
            Fetch XML字符串
        """
        lines = ['<fetch version="1.0" mapping="logical">']
        lines.append(f'  <entity name="{entity}">')

        # 属性
        for attr in attributes:
            lines.append(f'    <attribute name="{attr}" />')

        # 排序
        if order_by:
            desc = order_by.startswith("-")
            attr = order_by.lstrip("-")
            lines.append(f'    <order attribute="{attr}" descending="{str(desc).lower()}" />')

        # 过滤
        if filter_conditions:
            lines.append('    <filter type="and">')
            for condition in filter_conditions:
                attr = condition.get("attribute")
                op = condition.get("operator", "eq")
                val = condition.get("value")
                lines.append(f'      <condition attribute="{attr}" operator="{op}" value="{val}" />')
            lines.append('    </filter>')

        lines.append('  </entity>')
        lines.append('</fetch>')

        return "\n".join(lines)

    # ==================== 批处理 ====================

    def parse_metadata_directory(
        self,
        directory: str,
        metadata_type: str = None
    ) -> dict[str, dict[str, Any]]:
        """
        解析目录中的所有元数据文件

        Args:
            directory: 目录路径
            metadata_type: 元数据类型（可选）

        Returns:
            文件名到元数据的映射
        """
        dir_path = Path(directory)
        result = {}

        for yaml_file in dir_path.glob("**/*.yaml"):
            try:
                metadata = self.parse_metadata_file(
                    str(yaml_file),
                    metadata_type
                )
                result[yaml_file.stem] = metadata
            except Exception as e:
                logger.warning(f"Failed to parse {yaml_file}: {e}")

        return result

    # ==================== 工具方法 ====================

    def extract_schema_name(self, file_path: str) -> str | None:
        """
        从文件路径提取Schema名称

        Args:
            file_path: 文件路径

        Returns:
            Schema名称或None
        """
        try:
            data = self.load_yaml(file_path)
            return (data.get("schema", {}).get("schema_name")
                    or data.get("view", {}).get("schema_name")
                    or data.get("form", {}).get("schema_name")
                    or data.get("sitemap", {}).get("schema_name"))
        except Exception:
            return None

    def get_display_name(self, metadata: dict[str, Any]) -> str | None:
        """
        从元数据获取显示名称

        Args:
            metadata: 元数据字典

        Returns:
            显示名称或None
        """
        if "schema" in metadata:
            return metadata["schema"].get("display_name")
        if "view" in metadata:
            return metadata["view"].get("display_name")
        if "form" in metadata:
            return metadata["form"].get("display_name")
        if "ribbon" in metadata:
            return metadata["ribbon"].get("display_name")
        if "sitemap" in metadata:
            return metadata["sitemap"].get("display_name")
        return None


class TemplateGenerator:
    """YAML元数据模板生成器"""

    def __init__(self):
        self.parser = YAMLMetadataParser()

    def generate_table_template(
        self,
        schema_name: str,
        display_name: str,
        description: str = ""
    ) -> str:
        """生成表元数据模板"""
        data = {
            "$schema": "../_schema/table_schema.yaml",
            "schema": {
                "schema_name": schema_name,
                "display_name": display_name,
                "description": description,
                "ownership_type": "UserOwned",
                "has_activities": False,
                "has_notes": False,
                "options": {
                    "import_dependencies": False,
                    "import_subcomponents": False,
                    "create_audit_fields": False,
                    "enable_quick_create": False
                }
            },
            "attributes": [
                {
                    "schema_name": schema_name + "Name",
                    "type": "String",
                    "display_name": "名称",
                    "required": True,
                    "is_primary_name": True,
                    "max_length": 100
                }
            ]
        }

        import yaml
        return yaml.dump(data, allow_unicode=True, sort_keys=False, width=120)

    def generate_form_template(
        self,
        schema_name: str,
        entity: str,
        display_name: str
    ) -> str:
        """生成表单元数据模板"""
        data = {
            "$schema": "../_schema/form_schema.yaml",
            "form": {
                "schema_name": schema_name,
                "entity": entity,
                "type": "Main",
                "display_name": display_name,
                "options": {
                    "use_field_display_label": True,
                    "enable_security": False,
                    "show_image": False
                },
                "tabs": [
                    {
                        "schema_name": "general",
                        "display_name": "常规",
                        "sections": [
                            {
                                "schema_name": "section1",
                                "display_name": "第一节",
                                "rows": [
                                    {
                                        "cells": [
                                            {"attribute": "name", "width": "1"}
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        }

        import yaml
        return yaml.dump(data, allow_unicode=True, sort_keys=False, width=120)

    def generate_view_template(
        self,
        schema_name: str,
        entity: str,
        display_name: str
    ) -> str:
        """生成视图元数据模板"""
        data = {
            "$schema": "../_schema/view_schema.yaml",
            "view": {
                "schema_name": schema_name,
                "entity": entity,
                "type": "PublicView",
                "display_name": display_name,
                "is_default": False,
                "fetch_xml": f'''<fetch version="1.0" mapping="logical">
  <entity name="{entity}">
    <attribute name="name" />
    <order attribute="name" descending="false" />
  </entity>
</fetch>'''
            },
            "columns": [
                {"attribute": "name", "width": 200}
            ]
        }

        import yaml
        return yaml.dump(data, allow_unicode=True, sort_keys=False, width=120)
