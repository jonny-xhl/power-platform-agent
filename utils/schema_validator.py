"""
Power Platform Schema验证器
验证YAML元数据是否符合Schema定义
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml

# 设置日志
logger = logging.getLogger(__name__)


class SchemaValidator:
    """Schema验证器"""

    def __init__(self, schema_dir: Optional[str] = None):
        """
        初始化验证器

        Args:
            schema_dir: Schema文件目录
        """
        self.schema_dir = Path(schema_dir or "metadata/_schema")
        self._schema_cache = {}

    # ==================== 加载Schema ====================

    def load_schema(self, schema_name: str) -> Dict[str, Any]:
        """
        加载Schema定义

        Args:
            schema_name: Schema名称

        Returns:
            Schema字典
        """
        if schema_name in self._schema_cache:
            return self._schema_cache[schema_name]

        schema_file = self.schema_dir / f"{schema_name}.yaml"
        if not schema_file.exists():
            raise FileNotFoundError(f"Schema not found: {schema_name}")

        with open(schema_file, "r", encoding="utf-8") as f:
            schema = yaml.safe_load(f)

        self._schema_cache[schema_name] = schema
        return schema

    # ==================== 验证方法 ====================

    def validate(
        self,
        data: Dict[str, Any],
        schema_name: str
    ) -> Tuple[bool, List[str]]:
        """
        验证数据是否符合Schema

        Args:
            data: 要验证的数据
            schema_name: Schema名称

        Returns:
            (是否有效, 错误列表)
        """
        errors = []

        try:
            schema = self.load_schema(schema_name)
        except FileNotFoundError:
            return False, [f"Schema not found: {schema_name}"]

        # 执行验证
        if schema_name == "table_schema":
            errors.extend(self._validate_table(data, schema))
        elif schema_name == "form_schema":
            errors.extend(self._validate_form(data, schema))
        elif schema_name == "view_schema":
            errors.extend(self._validate_view(data, schema))
        elif schema_name == "webresource_schema":
            errors.extend(self._validate_webresource(data, schema))
        elif schema_name == "ribbon_schema":
            errors.extend(self._validate_ribbon(data, schema))
        elif schema_name == "sitemap_schema":
            errors.extend(self._validate_sitemap(data, schema))
        else:
            errors.append(f"Unknown schema type: {schema_name}")

        return len(errors) == 0, errors

    # ==================== 表验证 ====================

    def _validate_table(
        self,
        data: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> List[str]:
        """验证表元数据"""
        errors = []

        # 检查必需字段
        if "schema" not in data:
            errors.append("Missing required field: schema")
            return errors

        schema_data = data["schema"]

        required_fields = ["schema_name", "display_name"]
        for field in required_fields:
            if field not in schema_data:
                errors.append(f"Missing required field in schema: {field}")

        # 验证schema_name格式
        if "schema_name" in schema_data:
            schema_name = schema_data["schema_name"]
            if not isinstance(schema_name, str):
                errors.append("schema_name must be a string")
            elif not self._is_valid_schema_name(schema_name):
                errors.append(f"Invalid schema_name format: {schema_name}")

        # 验证ownership_type
        if "ownership_type" in schema_data:
            valid_types = ["UserOwned", "OrganizationOwned", "BusinessOwned"]
            if schema_data["ownership_type"] not in valid_types:
                errors.append(f"Invalid ownership_type: {schema_data['ownership_type']}")

        # 验证属性
        if "attributes" in data:
            for i, attr in enumerate(data["attributes"]):
                attr_errors = self._validate_attribute(attr, i)
                errors.extend(attr_errors)

        # 验证关系
        if "relationships" in data:
            for i, rel in enumerate(data["relationships"]):
                rel_errors = self._validate_relationship(rel, i)
                errors.extend(rel_errors)

        return errors

    def _validate_attribute(
        self,
        attr: Dict[str, Any],
        index: int
    ) -> List[str]:
        """验证属性定义"""
        errors = []
        prefix = f"attributes[{index}]"

        required_fields = ["name", "type", "display_name"]
        for field in required_fields:
            if field not in attr:
                errors.append(f"{prefix}: Missing required field: {field}")

        # 验证类型
        if "type" in attr:
            valid_types = [
                "String", "Integer", "Money", "Picklist",
                "MultiSelectPicklist", "Lookup", "Customer", "Owner",
                "DateTime", "Boolean", "Memo", "Decimal",
                "Double", "BigInt", "State", "Status"
            ]
            if attr["type"] not in valid_types:
                errors.append(f"{prefix}: Invalid type: {attr['type']}")

        # 验证选项集
        if attr.get("type") in ["Picklist", "MultiSelectPicklist", "State", "Status"]:
            if "options" not in attr or not attr["options"]:
                errors.append(f"{prefix}: Options required for {attr['type']} type")

        return errors

    def _validate_relationship(
        self,
        rel: Dict[str, Any],
        index: int
    ) -> List[str]:
        """验证关系定义"""
        errors = []
        prefix = f"relationships[{index}]"

        required_fields = ["name", "related_entity", "relationship_type"]
        for field in required_fields:
            if field not in rel:
                errors.append(f"{prefix}: Missing required field: {field}")

        # 验证关系类型
        if "relationship_type" in rel:
            valid_types = ["OneToMany", "ManyToOne", "ManyToMany"]
            if rel["relationship_type"] not in valid_types:
                errors.append(f"{prefix}: Invalid relationship_type: {rel['relationship_type']}")

        return errors

    # ==================== 表单验证 ====================

    def _validate_form(
        self,
        data: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> List[str]:
        """验证表单元数据"""
        errors = []

        if "form" not in data:
            errors.append("Missing required field: form")
            return errors

        form_data = data["form"]

        # 检查必需字段
        required_fields = ["schema_name", "entity", "type", "display_name"]
        for field in required_fields:
            if field not in form_data:
                errors.append(f"Missing required field in form: {field}")

        # 验证类型
        if "type" in form_data:
            valid_types = ["Main", "QuickCreate", "QuickView", "Card", "MainInteraction"]
            if form_data["type"] not in valid_types:
                errors.append(f"Invalid form type: {form_data['type']}")

        # 验证选项卡
        if "tabs" in data:
            for i, tab in enumerate(data["tabs"]):
                tab_errors = self._validate_tab(tab, i)
                errors.extend(tab_errors)

        return errors

    def _validate_tab(
        self,
        tab: Dict[str, Any],
        index: int
    ) -> List[str]:
        """验证选项卡定义"""
        errors = []
        prefix = f"tabs[{index}]"

        required_fields = ["name", "display_name", "sections"]
        for field in required_fields:
            if field not in tab:
                errors.append(f"{prefix}: Missing required field: {field}")

        # 验证分区
        if "sections" in tab:
            for j, section in enumerate(tab["sections"]):
                section_errors = self._validate_section(section, index, j)
                errors.extend(section_errors)

        return errors

    def _validate_section(
        self,
        section: Dict[str, Any],
        tab_index: int,
        section_index: int
    ) -> List[str]:
        """验证分区定义"""
        errors = []
        prefix = f"tabs[{tab_index}].sections[{section_index}]"

        required_fields = ["name", "display_name", "rows"]
        for field in required_fields:
            if field not in section:
                errors.append(f"{prefix}: Missing required field: {field}")

        return errors

    # ==================== 视图验证 ====================

    def _validate_view(
        self,
        data: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> List[str]:
        """验证视图元数据"""
        errors = []

        if "view" not in data:
            errors.append("Missing required field: view")
            return errors

        view_data = data["view"]

        # 检查必需字段
        required_fields = ["schema_name", "entity", "type", "display_name"]
        for field in required_fields:
            if field not in view_data:
                errors.append(f"Missing required field in view: {field}")

        # 验证类型
        if "type" in view_data:
            valid_types = ["PublicView", "PrivateView", "AdvancedFind",
                          "AssociatedView", "QuickFindView", "LookupView"]
            if view_data["type"] not in valid_types:
                errors.append(f"Invalid view type: {view_data['type']}")

        return errors

    # ==================== Web Resource验证 ====================

    def _validate_webresource(
        self,
        data: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> List[str]:
        """验证Web Resource元数据"""
        errors = []

        if "resources" not in data:
            errors.append("Missing required field: resources")
            return errors

        # 验证资源列表
        for i, resource in enumerate(data["resources"]):
            required_fields = ["name", "type", "source_path"]
            for field in required_fields:
                if field not in resource:
                    errors.append(f"resources[{i}]: Missing required field: {field}")

            # 验证类型
            if "type" in resource:
                valid_types = [
                    "css", "js", "html", "png", "jpg", "gif",
                    "svg", "ico", "xap", "xml", "xslt", "xsl"
                ]
                if resource["type"] not in valid_types:
                    errors.append(f"resources[{i}]: Invalid type: {resource['type']}")

        return errors

    # ==================== Ribbon验证 ====================

    def _validate_ribbon(
        self,
        data: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> List[str]:
        """验证Ribbon元数据"""
        errors = []

        if "ribbon" not in data:
            errors.append("Missing required field: ribbon")
            return errors

        ribbon = data["ribbon"]

        # 检查必需字段
        if "entity" not in ribbon:
            errors.append("Missing required field in ribbon: entity")

        # 验证按钮
        if "buttons" in ribbon:
            for i, button in enumerate(ribbon["buttons"]):
                required_fields = ["name", "display_name", "location", "command"]
                for field in required_fields:
                    if field not in button:
                        errors.append(f"buttons[{i}]: Missing required field: {field}")

        return errors

    # ==================== Sitemap验证 ====================

    def _validate_sitemap(
        self,
        data: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> List[str]:
        """验证Sitemap元数据"""
        errors = []

        if "sitemap" not in data:
            errors.append("Missing required field: sitemap")
            return errors

        sitemap = data["sitemap"]

        # 检查必需字段
        required_fields = ["schema_name", "display_name", "areas"]
        for field in required_fields:
            if field not in sitemap:
                errors.append(f"Missing required field in sitemap: {field}")

        # 验证区域
        if "areas" in sitemap:
            for i, area in enumerate(sitemap["areas"]):
                area_errors = self._validate_area(area, i)
                errors.extend(area_errors)

        return errors

    def _validate_area(
        self,
        area: Dict[str, Any],
        index: int
    ) -> List[str]:
        """验证区域定义"""
        errors = []
        prefix = f"areas[{index}]"

        required_fields = ["name", "display_name", "groups"]
        for field in required_fields:
            if field not in area:
                errors.append(f"{prefix}: Missing required field: {field}")

        return errors

    # ==================== 工具方法 ====================

    def _is_valid_schema_name(self, name: str) -> bool:
        """验证Schema名称格式"""
        import re
        pattern = r"^[a-zA-Z][a-zA-Z0-9_]*$"
        return bool(re.match(pattern, name))

    def validate_file(
        self,
        file_path: str
    ) -> Tuple[bool, List[str]]:
        """
        验证YAML文件

        Args:
            file_path: YAML文件路径

        Returns:
            (是否有效, 错误列表)
        """
        path = Path(file_path)

        # 确定Schema类型
        if "tables" in path.parts:
            schema_type = "table_schema"
        elif "forms" in path.parts:
            schema_type = "form_schema"
        elif "views" in path.parts:
            schema_type = "view_schema"
        elif "webresources" in path.parts:
            schema_type = "webresource_schema"
        elif "ribbon" in path.parts:
            schema_type = "ribbon_schema"
        elif "sitemap" in path.parts:
            schema_type = "sitemap_schema"
        else:
            return False, ["Unknown metadata type"]

        # 加载数据
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            return False, [f"Failed to load YAML: {e}"]

        return self.validate(data, schema_type)

    def validate_directory(
        self,
        directory: str
    ) -> Dict[str, Tuple[bool, List[str]]]:
        """
        验证目录中的所有YAML文件

        Args:
            directory: 目录路径

        Returns:
            文件名到验证结果的映射
        """
        results = {}
        dir_path = Path(directory)

        for yaml_file in dir_path.glob("**/*.yaml"):
            is_valid, errors = self.validate_file(str(yaml_file))
            results[str(yaml_file)] = (is_valid, errors)

        return results


class QuickValidator:
    """快速验证器，用于基本检查"""

    @staticmethod
    def check_yaml_syntax(file_path: str) -> Tuple[bool, Optional[str]]:
        """
        检查YAML语法

        Args:
            file_path: YAML文件路径

        Returns:
            (是否有效, 错误信息)
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                yaml.safe_load(f)
            return True, None
        except yaml.YAMLError as e:
            return False, str(e)

    @staticmethod
    def check_required_fields(
        data: Dict[str, Any],
        required: List[str]
    ) -> List[str]:
        """
        检查必需字段

        Args:
            data: 数据字典
            required: 必需字段列表

        Returns:
            缺失字段列表
        """
        missing = []
        for field in required:
            if field not in data:
                missing.append(field)
        return missing

    @staticmethod
    def check_field_type(
        data: Dict[str, Any],
        field: str,
        expected_type: type
    ) -> bool:
        """
        检查字段类型

        Args:
            data: 数据字典
            field: 字段名
            expected_type: 期望类型

        Returns:
            是否符合类型
        """
        if field not in data:
            return False
        return isinstance(data[field], expected_type)
