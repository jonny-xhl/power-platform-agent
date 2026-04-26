"""
Power Platform 命名转换器
根据配置规则转换和验证命名
"""

import logging
import re
from pathlib import Path
from typing import Any
import yaml

# 设置日志
logger = logging.getLogger(__name__)


class NamingConverter:
    """命名转换器"""

    def __init__(self, config_path: str = None):
        """
        初始化命名转换器

        Args:
            config_path: 命名规则配置文件路径
        """
        self.config_path = config_path or "config/naming_rules.yaml"
        self._config = None
        self._standard_entities = set()

        self._load_config()

    @property
    def config(self) -> dict[str, Any]:
        """获取配置"""
        if self._config is None:
            self._load_config()
        return self._config

    @property
    def prefix(self) -> str:
        """获取发布商前缀"""
        return self.config.get("naming", {}).get("prefix", "new")

    @property
    def schema_name_style(self) -> str:
        """获取Schema名称风格"""
        return self.config.get("naming", {}).get("schema_name", {}).get("style", "lowercase")

    @property
    def separator(self) -> str:
        """获取分隔符"""
        return self.config.get("naming", {}).get("schema_name", {}).get("separator", "_")

    @property
    def auto_prefix(self) -> bool:
        """是否自动添加前缀"""
        return self.config.get("naming", {}).get("schema_name", {}).get("auto_prefix", True)

    # ==================== 配置加载 ====================

    def _load_config(self) -> None:
        """加载配置文件"""
        config_file = Path(self.config_path)
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)

            # 加载标准实体列表
            standard_entities = self.config.get("naming", {}).get("standard_entities", [])
            self._standard_entities = set(standard_entities)
        else:
            self._config = {"naming": {}}
            self._standard_entities = set()

    # ==================== Schema Name 转换 ====================

    def convert_schema_name(
        self,
        name: str,
        is_standard: bool = False
    ) -> str:
        """
        转换Schema名称

        Args:
            name: 原始名称
            is_standard: 是否为标准实体

        Returns:
            转换后的名称
        """
        # 标准实体不加前缀
        if is_standard or name.lower() in self._standard_entities:
            return self._apply_style(name)

        # 应用前缀
        result = name
        if self.auto_prefix and not name.startswith(self.prefix + "_"):
            result = f"{self.prefix}_{name}"

        return self._apply_style(result)

    def _apply_style(self, name: str) -> str:
        """应用命名风格"""
        style = self.schema_name_style

        if style == "lowercase":
            # 转为snake_case: AccountNumber -> account_number
            result = self._to_snake_case(name)
            return result.lower()

        elif style == "camelCase":
            # 转为camelCase: account_number -> accountNumber
            if "_" in name:
                parts = name.split("_")
                result = parts[0].lower() + "".join(p.capitalize() for p in parts[1:])
                return result
            return name[0].lower() + name[1:] if name else name

        elif style == "PascalCase":
            # 转为PascalCase: account_number -> AccountNumber
            if "_" in name:
                parts = name.split("_")
                result = "".join(p.capitalize() for p in parts)
                return result
            return name[0].upper() + name[1:] if name else name

        return name

    def _to_snake_case(self, name: str) -> str:
        """转换为snake_case"""
        # 处理PascalCase/camelCase
        result = re.sub(r'([a-z])([A-Z])', r'\1_\2', name)
        # 处理连续大写
        result = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', result)
        return result

    # ==================== Web Resource 命名 ====================

    def convert_webresource_name(
        self,
        name: str,
        resource_type: str
    ) -> str:
        """
        转换Web Resource名称

        Args:
            name: 原始名称
            resource_type: 资源类型 (css/js/html/png等)

        Returns:
            转换后的名称（包含前缀和扩展名）
        """
        naming_config = self.config.get("naming", {}).get("webresource", {})
        prefix = naming_config.get("prefix", f"{self.prefix}_")
        pattern = naming_config.get("naming_pattern", "{prefix}{category}/{name}.{ext}")

        # 类型到分类的映射
        category_map = {
            "css": "css",
            "js": "js",
            "javascript": "js",
            "html": "html",
            "png": "png",
            "jpg": "jpg",
            "jpeg": "jpg",
            "gif": "gif",
            "svg": "svg",
            "ico": "ico",
            "icon": "ico",
            "xap": "xap",
            "xml": "xml",
            "xslt": "xslt",
            "xsl": "xslt"
        }

        category = category_map.get(resource_type.lower(), resource_type.lower())

        # 扩展名
        ext = self._get_extension(resource_type)

        # 应用命名模式
        result = pattern.format(
            prefix=prefix,
            category=category,
            name=name,
            ext=ext
        )

        return result

    def _get_extension(self, resource_type: str) -> str:
        """获取文件扩展名"""
        ext_map = {
            "css": "css",
            "js": "js",
            "javascript": "js",
            "html": "html",
            "png": "png",
            "jpg": "jpg",
            "jpeg": "jpg",
            "gif": "gif",
            "svg": "svg",
            "ico": "ico",
            "icon": "ico",
            "xap": "xap",
            "xml": "xml",
            "xslt": "xslt",
            "xsl": "xsl"
        }
        return ext_map.get(resource_type.lower(), resource_type.lower())

    # ==================== 批量转换 ====================

    def convert_attributes(
        self,
        attributes: list[dict[str, Any]],
        entity_name: str
    ) -> list[dict[str, Any]]:
        """
        批量转换属性名称

        Args:
            attributes: 属性列表
            entity_name: 所属实体名称

        Returns:
            转换后的属性列表
        """
        result = []

        for attr in attributes:
            converted = attr.copy()
            name = attr.get("name", "")

            # 检查是否为标准属性（不转换）
            if not self._is_standard_attribute(entity_name, name):
                converted["name"] = self.convert_schema_name(name)

            result.append(converted)

        return result

    def convert_relationships(
        self,
        relationships: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        批量转换关系名称

        Args:
            relationships: 关系列表

        Returns:
            转换后的关系列表
        """
        result = []

        for rel in relationships:
            converted = rel.copy()
            name = rel.get("name", "")

            # 关系名称总是加前缀
            if not name.startswith(self.prefix + "_"):
                converted["name"] = f"{self.prefix}_{name}"

            result.append(converted)

        return result

    # ==================== 验证 ====================

    def validate_schema_name(self, name: str) -> tuple[bool, str | None]:
        """
        验证Schema名称

        Args:
            name: 要验证的名称

        Returns:
            (是否有效, 错误信息)
        """
        validation = self.config.get("naming", {}).get("validation", {})
        schema_validation = validation.get("schema_name", {})

        # 检查长度
        max_length = schema_validation.get("max_length", 100)
        min_length = schema_validation.get("min_length", 2)
        if len(name) > max_length:
            return False, f"Schema name exceeds maximum length of {max_length}"
        if len(name) < min_length:
            return False, f"Schema name below minimum length of {min_length}"

        # 检查禁止字符
        forbidden = schema_validation.get("forbidden_chars", [])
        for char in forbidden:
            if char in name:
                return False, f"Schema name contains forbidden character: '{char}'"

        # 检查起始字符
        must_start = schema_validation.get("must_start_with", "letter")
        if must_start == "letter" and not name[0].isalpha():
            return False, "Schema name must start with a letter"

        # 检查格式
        pattern = schema_validation.get("allowed_pattern", r"^[a-zA-Z][a-zA-Z0-9_]*$")
        if not re.match(pattern, name):
            return False, "Schema name does not match required pattern"

        return True, None

    def validate_webresource_name(self, name: str) -> tuple[bool, str | None]:
        """
        验证Web Resource名称

        Args:
            name: 要验证的名称

        Returns:
            (是否有效, 错误信息)
        """
        validation = self.config.get("naming", {}).get("validation", {})
        wr_validation = validation.get("webresource_name", {})

        # 检查长度
        max_length = wr_validation.get("max_length", 256)
        if len(name) > max_length:
            return False, f"Web Resource name exceeds maximum length of {max_length}"

        # 检查禁止字符
        forbidden = wr_validation.get("forbidden_chars", [])
        for char in forbidden:
            if char in name:
                return False, f"Web Resource name contains forbidden character: '{char}'"

        # 检查格式
        pattern = wr_validation.get("allowed_pattern", r"^[a-zA-Z0-9_./-]+$")
        if not re.match(pattern, name):
            return False, "Web Resource name contains invalid characters"

        return True, None

    # ==================== 辅助方法 ====================

    def is_standard_entity(self, name: str) -> bool:
        """
        检查是否为标准实体

        Args:
            name: 实体名称

        Returns:
            是否为标准实体
        """
        return name.lower() in self._standard_entities

    def _is_standard_attribute(self, entity_name: str, attribute_name: str) -> bool:
        """
        检查是否为标准属性

        Args:
            entity_name: 实体名称
            attribute_name: 属性名称

        Returns:
            是否为标准属性
        """
        # 标准属性通常不以发布商前缀开头
        if attribute_name.startswith(self.prefix + "_"):
            return False

        # 常见的标准属性
        standard_attributes = {
            "createdon", "createdby", "modifiedon", "modifiedby",
            "ownerid", "owningbusinessunit", "statecode", "statuscode",
            "name", "transactioncurrencyid", "exchangerate",
            "importsequencenumber", "overriddencreatedon",
            "timezonecod", "utcconversiontimezonecode",
            "versionnumber", "processid", "stageid"
        }

        return attribute_name.lower() in standard_attributes

    def strip_prefix(self, name: str) -> str:
        """
        移除前缀

        Args:
            name: 带前缀的名称

        Returns:
            无前缀的名称
        """
        if name.startswith(self.prefix + "_"):
            return name[len(self.prefix) + 1:]
        return name

    def add_prefix(self, name: str) -> str:
        """
        添加前缀

        Args:
            name: 无前缀的名称

        Returns:
            带前缀的名称
        """
        if name.startswith(self.prefix + "_"):
            return name
        return f"{self.prefix}_{name}"


class NamingValidator:
    """命名验证器（独立类，便于单独使用）"""

    def __init__(self, converter: NamingConverter = None):
        """
        初始化验证器

        Args:
            converter: 命名转换器实例
        """
        self.converter = converter or NamingConverter()

    def validate_table_metadata(
        self,
        metadata: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """
        验证表元数据的命名

        Args:
            metadata: 表元数据

        Returns:
            (是否有效, 错误列表)
        """
        errors = []
        schema = metadata.get("schema", {})

        # 验证表名
        schema_name = schema.get("schema_name", "")
        is_valid, msg = self.converter.validate_schema_name(schema_name)
        if not is_valid:
            errors.append(f"Table schema_name: {msg}")

        # 验证属性
        for attr in metadata.get("attributes", []):
            attr_name = attr.get("name", "")
            is_valid, msg = self.converter.validate_schema_name(attr_name)
            if not is_valid:
                errors.append(f"Attribute '{attr_name}': {msg}")

        # 验证关系
        for rel in metadata.get("relationships", []):
            rel_name = rel.get("name", "")
            is_valid, msg = self.converter.validate_schema_name(rel_name)
            if not is_valid:
                errors.append(f"Relationship '{rel_name}': {msg}")

        return len(errors) == 0, errors

    def validate_form_metadata(
        self,
        metadata: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """
        验证表单元数据的命名

        Args:
            metadata: 表单元数据

        Returns:
            (是否有效, 错误列表)
        """
        errors = []
        form = metadata.get("form", {})

        # 验证表单名
        schema_name = form.get("schema_name", "")
        is_valid, msg = self.converter.validate_schema_name(schema_name)
        if not is_valid:
            errors.append(f"Form schema_name: {msg}")

        return len(errors) == 0, errors

    def check_naming_consistency(
        self,
        metadata_files: list[str]
    ) -> list[str]:
        """
        检查多个元数据文件的命名一致性

        Args:
            metadata_files: 元数据文件路径列表

        Returns:
            警告列表
        """
        warnings = []

        for file_path in metadata_files:
            # 这里可以添加文件解析和名称检查逻辑
            pass

        return warnings
