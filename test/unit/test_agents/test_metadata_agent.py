#!/usr/bin/env python3
"""
Power Platform Agent - MetadataAgent Unit Tests
测试 MetadataAgent 的元数据处理功能
"""

import pytest
import sys
import json
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import Dict, Any

# 添加项目路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "framework"))

from framework.agents.metadata_agent import MetadataAgent
from framework.utils.yaml_parser import YAMLMetadataParser
from framework.utils.schema_validator import SchemaValidator


# ==================== YAML 解析测试 ====================

@pytest.mark.unit
class TestYAMLParsing:
    """测试 YAML 元数据解析功能"""

    @pytest.fixture
    def temp_metadata_dir(self, tmp_path):
        """创建临时元数据目录和文件"""
        # 创建 schema 目录
        schema_dir = tmp_path / "_schema"
        schema_dir.mkdir()

        # 创建表 schema 文件
        table_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "table_schema": {
                "type": "object",
                "required": ["schema"]
            }
        }
        with open(schema_dir / "table_schema.yaml", "w", encoding="utf-8") as f:
            yaml.dump(table_schema, f)

        # 创建表单 schema 文件
        form_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "form_schema": {
                "type": "object",
                "required": ["form"]
            }
        }
        with open(schema_dir / "form_schema.yaml", "w", encoding="utf-8") as f:
            yaml.dump(form_schema, f)

        # 创建视图 schema 文件
        view_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "view_schema": {
                "type": "object",
                "required": ["view"]
            }
        }
        with open(schema_dir / "view_schema.yaml", "w", encoding="utf-8") as f:
            yaml.dump(view_schema, f)

        # 创建元数据目录
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()

        # 创建测试表元数据文件
        table_metadata = {
            "$schema": "../_schema/table_schema.yaml",
            "schema": {
                "schema_name": "test_account",
                "display_name": "测试账户",
                "description": "测试账户表",
                "ownership_type": "UserOwned",
                "has_activities": False,
                "has_notes": True,
                "is_audit_enabled": True,
                "options": {
                    "import_dependencies": False,
                    "enable_quick_create": True
                }
            },
            "attributes": [
                {
                    "name": "accountNumber",
                    "type": "String",
                    "display_name": "账户编号",
                    "description": "唯一账户编号",
                    "max_length": 50,
                    "required": True,
                    "is_primary_name": True
                },
                {
                    "name": "balance",
                    "type": "Money",
                    "display_name": "账户余额",
                    "min_value": 0,
                    "precision": 2
                },
                {
                    "name": "status",
                    "type": "Picklist",
                    "display_name": "状态",
                    "options": [
                        {"value": 100000000, "label": "活跃"},
                        {"value": 100000001, "label": "冻结"},
                        {"value": 100000002, "label": "关闭"}
                    ]
                }
            ],
            "relationships": [
                {
                    "name": "test_account_contact",
                    "related_entity": "contact",
                    "relationship_type": "OneToMany",
                    "display_name": "账户联系人",
                    "cascade_delete": "RemoveLink"
                }
            ]
        }
        with open(tables_dir / "test_account.yaml", "w", encoding="utf-8") as f:
            yaml.dump(table_metadata, f)

        # 创建测试属性元数据文件
        attribute_metadata = {
            "attribute": {
                "name": "emailAddress",
                "type": "String",
                "display_name": "电子邮件",
                "max_length": 100,
                "required": True
            }
        }
        with open(tables_dir / "test_attribute.yaml", "w", encoding="utf-8") as f:
            yaml.dump(attribute_metadata, f)

        # 创建测试表单元数据文件
        forms_dir = tmp_path / "forms"
        forms_dir.mkdir()

        form_metadata = {
            "$schema": "../_schema/form_schema.yaml",
            "form": {
                "schema_name": "test_account_main_form",
                "entity": "test_account",
                "type": "Main",
                "display_name": "测试账户主表单",
                "description": "测试账户主表单",
                "is_default": True,
                "options": {
                    "use_field_display_label": True,
                    "enable_security": False,
                    "show_image": False
                }
            },
            "tabs": [
                {
                    "name": "general",
                    "display_name": "常规",
                    "visible": True,
                    "expand_by_default": True,
                    "sections": [
                        {
                            "name": "basicInfo",
                            "display_name": "基本信息",
                            "visible": True,
                            "rows": [
                                {
                                    "cells": [
                                        {"attribute": "accountNumber", "width": "1"},
                                        {"attribute": "status", "width": "1"}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ],
            "webresources": [
                {
                    "name": "test_form_css",
                    "type": "css",
                    "path": "css/test.css",
                    "load_method": "inline"
                }
            ],
            "events": [
                {
                    "name": "onload",
                    "handlers": [
                        {
                            "function_name": "handleOnLoad",
                            "library": "test_form_handler",
                            "enabled": True
                        }
                    ]
                }
            ]
        }
        with open(forms_dir / "test_account_main.yaml", "w", encoding="utf-8") as f:
            yaml.dump(form_metadata, f)

        # 创建测试视图元数据文件
        views_dir = tmp_path / "views"
        views_dir.mkdir()

        view_metadata = {
            "$schema": "../_schema/view_schema.yaml",
            "view": {
                "schema_name": "test_account_active_view",
                "entity": "test_account",
                "type": "PublicView",
                "display_name": "活跃账户视图",
                "description": "显示活跃账户",
                "is_default": True,
                "fetch_xml": '''<fetch version="1.0" mapping="logical">
  <entity name="test_account">
    <attribute name="accountNumber" />
    <attribute name="balance" />
    <order attribute="accountNumber" descending="false" />
  </entity>
</fetch>'''
            },
            "columns": [
                {"attribute": "accountNumber", "width": 150, "sort_order": 1},
                {"attribute": "balance", "width": 100, "format": "money"}
            ],
            "layout": {
                "columns": 4,
                "cell_height": 30
            }
        }
        with open(views_dir / "test_account_active.yaml", "w", encoding="utf-8") as f:
            yaml.dump(view_metadata, f)

        return {
            "base": tmp_path,
            "schema": schema_dir,
            "tables": tables_dir,
            "forms": forms_dir,
            "views": views_dir
        }

    @pytest.fixture
    def parser(self, temp_metadata_dir):
        """创建 YAMLMetadataParser 实例"""
        return YAMLMetadataParser(str(temp_metadata_dir["schema"]))

    @pytest.fixture
    def validator(self, temp_metadata_dir):
        """创建 SchemaValidator 实例"""
        return SchemaValidator(str(temp_metadata_dir["schema"]))

    @pytest.fixture
    def metadata_agent(self, temp_metadata_dir):
        """创建 MetadataAgent 实例"""
        return MetadataAgent(
            schema_dir=str(temp_metadata_dir["schema"]),
            metadata_dir=str(temp_metadata_dir["base"])
        )

    # ==================== 表元数据解析测试 ====================

    def test_parse_table_yaml_success(self, parser, temp_metadata_dir):
        """测试成功解析表元数据"""
        table_file = temp_metadata_dir["tables"] / "test_account.yaml"

        result = parser.parse_table_yaml(str(table_file))

        assert result is not None
        assert result["schema_name"] == "test_account"
        assert result["display_name"] == "测试账户"
        assert result["description"] == "测试账户表"
        assert result["ownership_type"] == "UserOwned"
        assert result["has_activities"] is False
        assert result["has_notes"] is True
        assert result["is_audit_enabled"] is True
        assert len(result["attributes"]) == 3
        assert len(result["relationships"]) == 1

    def test_parse_table_attributes(self, parser, temp_metadata_dir):
        """测试解析表属性"""
        table_file = temp_metadata_dir["tables"] / "test_account.yaml"

        result = parser.parse_table_yaml(str(table_file))
        attributes = result["attributes"]

        # 检查第一个属性
        attr1 = attributes[0]
        assert attr1["name"] == "accountNumber"
        assert attr1["type"] == "String"
        assert attr1["display_name"] == "账户编号"
        assert attr1["max_length"] == 50
        assert attr1["required"] is True
        assert attr1["is_primary_name"] is True

        # 检查 Money 类型属性
        attr2 = attributes[1]
        assert attr2["name"] == "balance"
        assert attr2["type"] == "Money"
        assert attr2["min_value"] == 0
        assert attr2["precision"] == 2

        # 检查 Picklist 类型属性
        attr3 = attributes[2]
        assert attr3["name"] == "status"
        assert attr3["type"] == "Picklist"
        assert len(attr3["options"]) == 3
        assert attr3["options"][0]["value"] == 100000000
        assert attr3["options"][0]["label"] == "活跃"

    def test_parse_table_relationships(self, parser, temp_metadata_dir):
        """测试解析表关系"""
        table_file = temp_metadata_dir["tables"] / "test_account.yaml"

        result = parser.parse_table_yaml(str(table_file))
        relationships = result["relationships"]

        assert len(relationships) == 1
        rel = relationships[0]
        assert rel["name"] == "test_account_contact"
        assert rel["related_entity"] == "contact"
        assert rel["relationship_type"] == "OneToMany"
        assert rel["display_name"] == "账户联系人"
        assert rel["cascade_delete"] == "RemoveLink"

    def test_parse_table_with_options(self, parser, temp_metadata_dir):
        """测试解析表选项配置"""
        table_file = temp_metadata_dir["tables"] / "test_account.yaml"

        result = parser.parse_table_yaml(str(table_file))
        options = result["options"]

        assert options["import_dependencies"] is False
        assert options["enable_quick_create"] is True

    def test_parse_table_file_not_found(self, parser):
        """测试解析不存在的文件"""
        with pytest.raises(FileNotFoundError):
            parser.parse_table_yaml("non_existent_file.yaml")

    # ==================== 属性元数据解析测试 ====================

    def test_parse_attribute_success(self, parser):
        """测试成功解析属性元数据"""
        attribute_data = {
            "name": "testField",
            "type": "String",
            "display_name": "测试字段",
            "description": "测试字段描述",
            "required": True,
            "max_length": 100
        }

        result = parser.parse_attribute(attribute_data)

        assert result["name"] == "testField"
        assert result["type"] == "String"
        assert result["display_name"] == "测试字段"
        assert result["description"] == "测试字段描述"
        assert result["required"] is True
        assert result["max_length"] == 100

    def test_parse_attribute_with_lookup(self, parser):
        """测试解析 Lookup 类型属性"""
        attribute_data = {
            "name": "customerId",
            "type": "Lookup",
            "display_name": "客户",
            "entity": "account",
            "relationship_name": "test_customer_account"
        }

        result = parser.parse_attribute(attribute_data)

        assert result["name"] == "customerId"
        assert result["type"] == "Lookup"
        assert result["entity"] == "account"
        assert result["relationship_name"] == "test_customer_account"

    def test_parse_attribute_with_options(self, parser):
        """测试解析带选项集的属性"""
        attribute_data = {
            "name": "priority",
            "type": "Picklist",
            "display_name": "优先级",
            "options": [
                {"value": 1, "label": "低"},
                {"value": 2, "label": "中"},
                {"value": 3, "label": "高"}
            ]
        }

        result = parser.parse_attribute(attribute_data)

        assert result["type"] == "Picklist"
        assert len(result["options"]) == 3
        assert result["options"][0]["label"] == "低"

    # ==================== 表单元数据解析测试 ====================

    def test_parse_form_yaml_success(self, parser, temp_metadata_dir):
        """测试成功解析表单元数据"""
        form_file = temp_metadata_dir["forms"] / "test_account_main.yaml"

        result = parser.parse_form_yaml(str(form_file))

        assert result is not None
        assert result["schema_name"] == "test_account_main_form"
        assert result["entity"] == "test_account"
        assert result["type"] == "Main"
        assert result["display_name"] == "测试账户主表单"
        assert result["is_default"] is True

    def test_parse_form_tabs(self, parser, temp_metadata_dir):
        """测试解析表单选项卡"""
        form_file = temp_metadata_dir["forms"] / "test_account_main.yaml"

        result = parser.parse_form_yaml(str(form_file))
        tabs = result["tabs"]

        assert len(tabs) == 1
        tab = tabs[0]
        assert tab["name"] == "general"
        assert tab["display_name"] == "常规"
        assert tab["visible"] is True
        assert tab["expand_by_default"] is True

    def test_parse_form_sections(self, parser, temp_metadata_dir):
        """测试解析表单分区"""
        form_file = temp_metadata_dir["forms"] / "test_account_main.yaml"

        result = parser.parse_form_yaml(str(form_file))
        sections = result["tabs"][0]["sections"]

        assert len(sections) == 1
        section = sections[0]
        assert section["name"] == "basicInfo"
        assert section["display_name"] == "基本信息"

    def test_parse_form_cells(self, parser, temp_metadata_dir):
        """测试解析表单单元格"""
        form_file = temp_metadata_dir["forms"] / "test_account_main.yaml"

        result = parser.parse_form_yaml(str(form_file))
        cells = result["tabs"][0]["sections"][0]["rows"][0]["cells"]

        assert len(cells) == 2
        assert cells[0]["attribute"] == "accountNumber"
        assert cells[0]["width"] == "1"

    def test_parse_form_webresources(self, parser, temp_metadata_dir):
        """测试解析表单 Web Resource"""
        form_file = temp_metadata_dir["forms"] / "test_account_main.yaml"

        result = parser.parse_form_yaml(str(form_file))
        webresources = result["webresources"]

        assert len(webresources) == 1
        assert webresources[0]["name"] == "test_form_css"
        assert webresources[0]["type"] == "css"
        assert webresources[0]["load_method"] == "inline"

    def test_parse_form_events(self, parser, temp_metadata_dir):
        """测试解析表单事件"""
        form_file = temp_metadata_dir["forms"] / "test_account_main.yaml"

        result = parser.parse_form_yaml(str(form_file))
        events = result["events"]

        assert len(events) == 1
        assert events[0]["name"] == "onload"
        assert len(events[0]["handlers"]) == 1
        assert events[0]["handlers"][0]["function_name"] == "handleOnLoad"

    # ==================== 视图元数据解析测试 ====================

    def test_parse_view_yaml_success(self, parser, temp_metadata_dir):
        """测试成功解析视图元数据"""
        view_file = temp_metadata_dir["views"] / "test_account_active.yaml"

        result = parser.parse_view_yaml(str(view_file))

        assert result is not None
        assert result["schema_name"] == "test_account_active_view"
        assert result["entity"] == "test_account"
        assert result["type"] == "PublicView"
        assert result["display_name"] == "活跃账户视图"
        assert result["is_default"] is True

    def test_parse_view_fetch_xml(self, parser, temp_metadata_dir):
        """测试解析视图 Fetch XML"""
        view_file = temp_metadata_dir["views"] / "test_account_active.yaml"

        result = parser.parse_view_yaml(str(view_file))
        fetch_xml = result["fetch_xml"]

        assert fetch_xml is not None
        assert '<fetch version="1.0"' in fetch_xml
        assert 'test_account' in fetch_xml
        assert 'accountNumber' in fetch_xml

    def test_parse_view_columns(self, parser, temp_metadata_dir):
        """测试解析视图列"""
        view_file = temp_metadata_dir["views"] / "test_account_active.yaml"

        result = parser.parse_view_yaml(str(view_file))
        columns = result["columns"]

        assert len(columns) == 2
        assert columns[0]["attribute"] == "accountNumber"
        assert columns[0]["width"] == 150
        assert columns[0]["sort_order"] == 1
        assert columns[1]["format"] == "money"

    def test_parse_view_layout(self, parser, temp_metadata_dir):
        """测试解析视图布局"""
        view_file = temp_metadata_dir["views"] / "test_account_active.yaml"

        result = parser.parse_view_yaml(str(view_file))
        layout = result["layout"]

        assert layout["columns"] == 4
        assert layout["cell_height"] == 30

    # ==================== 元数据类型检测测试 ====================

    def test_detect_metadata_type_table(self, parser, temp_metadata_dir):
        """测试检测表元数据类型"""
        table_file = temp_metadata_dir["tables"] / "test_account.yaml"
        data = parser.load_yaml(str(table_file))

        detected_type = parser._detect_metadata_type(data, str(table_file))
        assert detected_type == "table"

    def test_detect_metadata_type_form(self, parser, temp_metadata_dir):
        """测试检测表单元数据类型"""
        form_file = temp_metadata_dir["forms"] / "test_account_main.yaml"
        data = parser.load_yaml(str(form_file))

        detected_type = parser._detect_metadata_type(data, str(form_file))
        assert detected_type == "form"

    def test_detect_metadata_type_view(self, parser, temp_metadata_dir):
        """测试检测视图元数据类型"""
        view_file = temp_metadata_dir["views"] / "test_account_active.yaml"
        data = parser.load_yaml(str(view_file))

        detected_type = parser._detect_metadata_type(data, str(view_file))
        assert detected_type == "view"


# ==================== Schema 验证测试 ====================

@pytest.mark.unit
class TestSchemaValidation:
    """测试 Schema 验证功能"""

    @pytest.fixture
    def temp_schema_dir(self, tmp_path):
        """创建临时 Schema 目录"""
        schema_dir = tmp_path / "_schema"
        schema_dir.mkdir()

        # 创建完整的表 schema
        table_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["schema"],
            "properties": {
                "$schema": {"type": "string"},
                "schema": {
                    "type": "object",
                    "required": ["schema_name", "display_name"],
                    "properties": {
                        "schema_name": {"type": "string"},
                        "display_name": {"type": "string"},
                        "description": {"type": "string"},
                        "ownership_type": {"type": "string"}
                    }
                },
                "attributes": {"type": "array"},
                "relationships": {"type": "array"}
            }
        }
        with open(schema_dir / "table_schema.yaml", "w", encoding="utf-8") as f:
            yaml.dump(table_schema, f)

        # 创建表单 schema
        form_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["form"],
            "properties": {
                "form": {
                    "type": "object",
                    "required": ["schema_name", "entity", "type", "display_name"],
                    "properties": {
                        "schema_name": {"type": "string"},
                        "entity": {"type": "string"},
                        "type": {"type": "string"},
                        "display_name": {"type": "string"}
                    }
                },
                "tabs": {"type": "array"}
            }
        }
        with open(schema_dir / "form_schema.yaml", "w", encoding="utf-8") as f:
            yaml.dump(form_schema, f)

        return schema_dir

    @pytest.fixture
    def validator(self, temp_schema_dir):
        """创建 SchemaValidator 实例"""
        return SchemaValidator(str(temp_schema_dir))

    # ==================== 有效元数据验证测试 ====================

    def test_validate_valid_table_metadata(self, validator):
        """测试验证有效的表元数据"""
        valid_data = {
            "schema": {
                "schema_name": "test_entity",
                "display_name": "测试实体",
                "description": "测试描述",
                "ownership_type": "UserOwned"
            },
            "attributes": [
                {
                    "name": "testField",
                    "type": "String",
                    "display_name": "测试字段"
                }
            ],
            "relationships": []
        }

        is_valid, errors = validator.validate(valid_data, "table_schema")

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_valid_form_metadata(self, validator):
        """测试验证有效的表单元数据"""
        valid_data = {
            "form": {
                "schema_name": "test_form",
                "entity": "test_entity",
                "type": "Main",
                "display_name": "测试表单"
            },
            "tabs": []
        }

        is_valid, errors = validator.validate(valid_data, "form_schema")

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_metadata_with_all_optional_fields(self, validator):
        """测试验证包含所有可选字段的元数据"""
        complete_data = {
            "schema": {
                "schema_name": "complete_entity",
                "display_name": "完整实体",
                "description": "这是一个完整的实体描述",
                "ownership_type": "OrganizationOwned",
                "has_activities": True,
                "has_notes": True,
                "is_audit_enabled": True
            },
            "attributes": [
                {
                    "name": "field1",
                    "type": "String",
                    "display_name": "字段1",
                    "required": True,
                    "max_length": 100,
                    "description": "字段描述"
                },
                {
                    "name": "field2",
                    "type": "Money",
                    "display_name": "字段2",
                    "min_value": 0,
                    "max_value": 1000000,
                    "precision": 2
                }
            ],
            "relationships": [
                {
                    "name": "test_rel",
                    "related_entity": "related_entity",
                    "relationship_type": "OneToMany"
                }
            ]
        }

        is_valid, errors = validator.validate(complete_data, "table_schema")

        assert is_valid is True

    # ==================== 无效元数据检测测试 ====================

    def test_validate_missing_required_schema_field(self, validator):
        """测试检测缺少必需的 schema 字段"""
        invalid_data = {
            "attributes": []
        }

        is_valid, errors = validator.validate(invalid_data, "table_schema")

        assert is_valid is False
        assert any("schema" in error for error in errors)

    def test_validate_missing_schema_name(self, validator):
        """测试检测缺少 schema_name"""
        invalid_data = {
            "schema": {
                "display_name": "测试实体"
            }
        }

        is_valid, errors = validator.validate(invalid_data, "table_schema")

        assert is_valid is False
        assert any("schema_name" in error for error in errors)

    def test_validate_missing_display_name(self, validator):
        """测试检测缺少 display_name"""
        invalid_data = {
            "schema": {
                "schema_name": "test_entity"
            }
        }

        is_valid, errors = validator.validate(invalid_data, "table_schema")

        assert is_valid is False
        assert any("display_name" in error for error in errors)

    def test_validate_invalid_schema_name_format(self, validator):
        """测试检测无效的 schema_name 格式"""
        invalid_data = {
            "schema": {
                "schema_name": "123_invalid",  # 以数字开头
                "display_name": "测试实体"
            }
        }

        is_valid, errors = validator.validate(invalid_data, "table_schema")

        assert is_valid is False
        assert any("schema_name" in error or "Invalid" in error for error in errors)

    def test_validate_invalid_ownership_type(self, validator):
        """测试检测无效的 ownership_type"""
        invalid_data = {
            "schema": {
                "schema_name": "test_entity",
                "display_name": "测试实体",
                "ownership_type": "InvalidType"
            }
        }

        is_valid, errors = validator.validate(invalid_data, "table_schema")

        assert is_valid is False
        assert any("ownership_type" in error for error in errors)

    def test_validate_missing_attribute_required_fields(self, validator):
        """测试检测属性缺少必需字段"""
        invalid_data = {
            "schema": {
                "schema_name": "test_entity",
                "display_name": "测试实体"
            },
            "attributes": [
                {
                    "name": "incomplete_field"
                    # 缺少 type 和 display_name
                }
            ]
        }

        is_valid, errors = validator.validate(invalid_data, "table_schema")

        assert is_valid is False
        assert any("attributes" in error for error in errors)

    def test_validate_invalid_attribute_type(self, validator):
        """测试检测无效的属性类型"""
        invalid_data = {
            "schema": {
                "schema_name": "test_entity",
                "display_name": "测试实体"
            },
            "attributes": [
                {
                    "name": "test_field",
                    "type": "InvalidType",
                    "display_name": "测试字段"
                }
            ]
        }

        is_valid, errors = validator.validate(invalid_data, "table_schema")

        assert is_valid is False
        assert any("type" in error for error in errors)

    def test_validate_picklist_without_options(self, validator):
        """测试检测 Picklist 类型缺少选项"""
        invalid_data = {
            "schema": {
                "schema_name": "test_entity",
                "display_name": "测试实体"
            },
            "attributes": [
                {
                    "name": "status",
                    "type": "Picklist",
                    "display_name": "状态"
                    # 缺少 options
                }
            ]
        }

        is_valid, errors = validator.validate(invalid_data, "table_schema")

        assert is_valid is False
        assert any("Options required" in error for error in errors)

    def test_validate_missing_relationship_required_fields(self, validator):
        """测试检测关系缺少必需字段"""
        invalid_data = {
            "schema": {
                "schema_name": "test_entity",
                "display_name": "测试实体"
            },
            "relationships": [
                {
                    "name": "incomplete_rel"
                    # 缺少 related_entity 和 relationship_type
                }
            ]
        }

        is_valid, errors = validator.validate(invalid_data, "table_schema")

        assert is_valid is False
        assert any("relationships" in error for error in errors)

    def test_validate_invalid_relationship_type(self, validator):
        """测试检测无效的关系类型"""
        invalid_data = {
            "schema": {
                "schema_name": "test_entity",
                "display_name": "测试实体"
            },
            "relationships": [
                {
                    "name": "test_rel",
                    "related_entity": "related",
                    "relationship_type": "InvalidType"
                }
            ]
        }

        is_valid, errors = validator.validate(invalid_data, "table_schema")

        assert is_valid is False
        assert any("relationship_type" in error for error in errors)

    def test_validate_form_missing_required_fields(self, validator):
        """测试检测表单缺少必需字段"""
        invalid_data = {
            "form": {
                "schema_name": "test_form"
                # 缺少 entity, type, display_name
            }
        }

        is_valid, errors = validator.validate(invalid_data, "form_schema")

        assert is_valid is False
        assert len(errors) > 0

    def test_validate_invalid_form_type(self, validator):
        """测试检测无效的表单类型"""
        invalid_data = {
            "form": {
                "schema_name": "test_form",
                "entity": "test_entity",
                "type": "InvalidType",
                "display_name": "测试表单"
            }
        }

        is_valid, errors = validator.validate(invalid_data, "form_schema")

        assert is_valid is False
        assert any("type" in error for error in errors)

    # ==================== 自定义 Schema 验证测试 ====================

    def test_validate_custom_schema_not_found(self, validator, tmp_path):
        """测试验证不存在的 Schema"""
        # 删除 schema 文件模拟不存在的情况
        import shutil
        shutil.rmtree(tmp_path / "_schema")

        invalid_data = {"schema": {"schema_name": "test"}}

        is_valid, errors = validator.validate(invalid_data, "nonexistent_schema")

        assert is_valid is False
        assert any("not found" in error.lower() for error in errors)

    def test_validate_multiple_errors(self, validator):
        """测试检测多个验证错误"""
        invalid_data = {
            "schema": {
                # 缺少 schema_name 和 display_name
            },
            "attributes": [
                {
                    "name": "field"
                    # 缺少 type 和 display_name
                }
            ]
        }

        is_valid, errors = validator.validate(invalid_data, "table_schema")

        assert is_valid is False
        # Schema validation returns at least 2 errors: missing schema_name and display_name
        # Plus attribute errors for missing type and display_name
        assert len(errors) >= 2  # 至少有两个错误

    def test_validate_empty_metadata(self, validator):
        """测试验证空元数据"""
        empty_data = {}

        is_valid, errors = validator.validate(empty_data, "table_schema")

        assert is_valid is False
        assert len(errors) > 0

    def test_validate_with_minimal_valid_data(self, validator):
        """测试验证最小有效数据"""
        minimal_data = {
            "schema": {
                "schema_name": "min_entity",
                "display_name": "最小实体"
            }
        }

        is_valid, errors = validator.validate(minimal_data, "table_schema")

        assert is_valid is True


# ==================== 本地元数据管理测试 ====================

@pytest.mark.unit
class TestLocalMetadataManagement:
    """测试本地元数据管理功能"""

    @pytest.fixture
    def temp_metadata_dirs(self, tmp_path):
        """创建临时元数据目录结构"""
        # 创建 schema 目录
        schema_dir = tmp_path / "_schema"
        schema_dir.mkdir()

        # 创建简单 schema 文件
        table_schema = {
            "type": "object",
            "required": ["schema"],
            "properties": {
                "schema": {
                    "type": "object",
                    "required": ["schema_name", "display_name"]
                }
            }
        }
        with open(schema_dir / "table_schema.yaml", "w") as f:
            yaml.dump(table_schema, f)

        # 创建元数据目录
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()

        export_dir = tmp_path / "export"
        export_dir.mkdir()

        return {
            "schema": schema_dir,
            "tables": tables_dir,
            "export": export_dir,
            "base": tmp_path
        }

    @pytest.fixture
    def sample_table_metadata(self):
        """创建示例表元数据"""
        return {
            "$schema": "../_schema/table_schema.yaml",
            "schema": {
                "schema_name": "exported_account",
                "display_name": "导出账户",
                "description": "用于导出测试的账户表",
                "ownership_type": "UserOwned"
            },
            "attributes": [
                {
                    "name": "accountNumber",
                    "type": "String",
                    "display_name": "账户编号",
                    "max_length": 50,
                    "required": True
                },
                {
                    "name": "balance",
                    "type": "Money",
                    "display_name": "余额"
                }
            ]
        }

    @pytest.fixture
    def metadata_agent(self, temp_metadata_dirs):
        """创建 MetadataAgent 实例"""
        return MetadataAgent(
            schema_dir=str(temp_metadata_dirs["schema"]),
            metadata_dir=str(temp_metadata_dirs["base"])
        )

    # ==================== 元数据导出测试 ====================

    def test_export_metadata_to_yaml(self, temp_metadata_dirs, sample_table_metadata):
        """测试导出元数据到 YAML 文件"""
        parser = YAMLMetadataParser(str(temp_metadata_dirs["schema"]))
        output_file = temp_metadata_dirs["export"] / "exported_account.yaml"

        parser.save_yaml(sample_table_metadata, str(output_file))

        assert output_file.exists()

        # 验证导出的内容
        loaded_data = parser.load_yaml(str(output_file))
        assert loaded_data["schema"]["schema_name"] == "exported_account"
        assert loaded_data["schema"]["display_name"] == "导出账户"
        assert len(loaded_data["attributes"]) == 2

    def test_export_metadata_preserves_structure(self, temp_metadata_dirs, sample_table_metadata):
        """测试导出保持元数据结构"""
        parser = YAMLMetadataParser(str(temp_metadata_dirs["schema"]))
        output_file = temp_metadata_dirs["export"] / "structure_test.yaml"

        parser.save_yaml(sample_table_metadata, str(output_file))

        loaded_data = parser.load_yaml(str(output_file))

        # 验证所有关键字段都存在
        assert "$schema" in loaded_data
        assert "schema" in loaded_data
        assert "attributes" in loaded_data
        assert loaded_data["schema"]["ownership_type"] == "UserOwned"
        assert loaded_data["attributes"][0]["required"] is True

    def test_export_metadata_creates_directories(self, temp_metadata_dirs, sample_table_metadata):
        """测试导出时自动创建目录"""
        parser = YAMLMetadataParser(str(temp_metadata_dirs["schema"]))
        nested_dir = temp_metadata_dirs["export"] / "nested" / "deep" / "dir"
        output_file = nested_dir / "nested_export.yaml"

        parser.save_yaml(sample_table_metadata, str(output_file))

        assert nested_dir.exists()
        assert output_file.exists()

    def test_export_metadata_overwrites_existing(self, temp_metadata_dirs, sample_table_metadata):
        """测试导出覆盖已存在的文件"""
        parser = YAMLMetadataParser(str(temp_metadata_dirs["schema"]))
        output_file = temp_metadata_dirs["export"] / "overwrite_test.yaml"

        # 第一次写入
        original_data = {
            "schema": {
                "schema_name": "original",
                "display_name": "原始"
            }
        }
        parser.save_yaml(original_data, str(output_file))

        # 第二次写入（覆盖）
        parser.save_yaml(sample_table_metadata, str(output_file))

        loaded_data = parser.load_yaml(str(output_file))
        assert loaded_data["schema"]["schema_name"] == "exported_account"
        assert loaded_data["schema"]["display_name"] == "导出账户"

    def test_export_metadata_with_unicode(self, temp_metadata_dirs):
        """测试导出包含 Unicode 字符的元数据"""
        parser = YAMLMetadataParser(str(temp_metadata_dirs["schema"]))
        output_file = temp_metadata_dirs["export"] / "unicode_test.yaml"

        unicode_data = {
            "schema": {
                "schema_name": "test_entity",
                "display_name": "测试实体 - 测试漢字 Машина",
                "description": "包含 Emoji: [测试] 特殊字符"
            }
        }

        parser.save_yaml(unicode_data, str(output_file))

        loaded_data = parser.load_yaml(str(output_file))
        assert "测试实体" in loaded_data["schema"]["display_name"]
        assert "测试漢字" in loaded_data["schema"]["display_name"]
        assert "Машина" in loaded_data["schema"]["display_name"]

    # ==================== 元数据缓存测试 ====================

    @pytest.mark.asyncio
    async def test_parse_caches_result(self, metadata_agent, temp_metadata_dirs):
        """测试解析结果被缓存"""
        # 创建测试文件
        test_file = temp_metadata_dirs["tables"] / "cache_test.yaml"
        test_data = {
            "schema": {
                "schema_name": "cached_entity",
                "display_name": "缓存测试"
            }
        }
        with open(test_file, "w", encoding="utf-8") as f:
            yaml.dump(test_data, f)

        # 第一次解析
        result1 = await metadata_agent.parse(str(test_file), "table")
        data1 = json.loads(result1)

        # 第二次解析（应该从缓存读取）
        result2 = await metadata_agent.parse(str(test_file), "table")
        data2 = json.loads(result2)

        assert data1["success"] is True
        assert data2["success"] is True
        assert data1["metadata"] == data2["metadata"]

        # 验证缓存存在
        assert str(test_file) in metadata_agent._metadata_cache

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_file_change(self, metadata_agent, temp_metadata_dirs):
        """测试文件变化时缓存处理"""
        test_file = temp_metadata_dirs["tables"] / "cache_invalidate.yaml"

        # 写入初始数据
        initial_data = {
            "schema": {
                "schema_name": "initial",
                "display_name": "初始版本"
            }
        }
        with open(test_file, "w", encoding="utf-8") as f:
            yaml.dump(initial_data, f)

        # 第一次解析
        result1 = await metadata_agent.parse(str(test_file), "table")

        # 修改文件
        modified_data = {
            "schema": {
                "schema_name": "modified",
                "display_name": "修改版本"
            }
        }
        with open(test_file, "w", encoding="utf-8") as f:
            yaml.dump(modified_data, f)

        # 再次解析（当前实现会重新解析并更新缓存）
        result2 = await metadata_agent.parse(str(test_file), "table")
        data2 = json.loads(result2)

        assert data2["metadata"]["schema_name"] == "modified"

    def test_cache_multiple_files(self, metadata_agent, temp_metadata_dirs):
        """测试缓存多个文件"""
        cache = metadata_agent._metadata_cache

        # 添加多个文件到缓存
        cache["file1.yaml"] = {"schema_name": "entity1"}
        cache["file2.yaml"] = {"schema_name": "entity2"}
        cache["file3.yaml"] = {"schema_name": "entity3"}

        assert len(cache) == 3
        assert cache["file1.yaml"]["schema_name"] == "entity1"
        assert cache["file2.yaml"]["schema_name"] == "entity2"
        assert cache["file3.yaml"]["schema_name"] == "entity3"

    def test_clear_metadata_cache(self, metadata_agent):
        """测试清除元数据缓存"""
        # 添加缓存数据
        metadata_agent._metadata_cache["test.yaml"] = {"schema_name": "test"}

        # 清除缓存
        metadata_agent._metadata_cache.clear()

        assert len(metadata_agent._metadata_cache) == 0

    # ==================== 批量元数据操作测试 ====================

    def test_parse_metadata_directory(self, temp_metadata_dirs):
        """测试批量解析目录中的元数据文件"""
        # 创建多个测试文件
        parser = YAMLMetadataParser(str(temp_metadata_dirs["schema"]))

        for i in range(3):
            test_data = {
                "schema": {
                    "schema_name": f"bulk_entity_{i}",
                    "display_name": f"批量实体 {i}"
                }
            }
            test_file = temp_metadata_dirs["tables"] / f"bulk_{i}.yaml"
            with open(test_file, "w", encoding="utf-8") as f:
                yaml.dump(test_data, f)

        # 批量解析
        results = parser.parse_metadata_directory(str(temp_metadata_dirs["tables"]), "table")

        assert len(results) == 3
        assert "bulk_0" in results
        assert "bulk_1" in results
        assert "bulk_2" in results

    def test_export_entity_to_yaml_structure(self, metadata_agent):
        """测试将实体元数据转换为 YAML 结构"""
        entity_metadata = {
            "SchemaName": "test_entity",
            "DisplayName": {
                "UserLocalizedLabel": {
                    "Label": "测试实体"
                }
            },
            "Description": {
                "UserLocalizedLabel": {
                    "Label": "测试描述"
                }
            },
            "OwnershipType": "UserOwned",
            "IsActivity": False,
            "HasNotes": True
        }

        yaml_data = metadata_agent._export_entity_to_yaml(entity_metadata)

        assert yaml_data["schema"]["schema_name"] == "test_entity"
        assert yaml_data["schema"]["display_name"] == "测试实体"
        assert yaml_data["schema"]["ownership_type"] == "UserOwned"
        assert yaml_data["schema"]["has_activities"] is False
        assert yaml_data["schema"]["has_notes"] is True
        assert "attributes" in yaml_data
        assert "relationships" in yaml_data

    def test_extract_schema_name(self, temp_metadata_dirs):
        """测试从文件提取 schema_name"""
        parser = YAMLMetadataParser(str(temp_metadata_dirs["schema"]))

        # 创建测试文件
        test_file = temp_metadata_dirs["tables"] / "extract_test.yaml"
        test_data = {
            "schema": {
                "schema_name": "extracted_entity",
                "display_name": "提取测试"
            }
        }
        with open(test_file, "w") as f:
            yaml.dump(test_data, f)

        schema_name = parser.extract_schema_name(str(test_file))

        assert schema_name == "extracted_entity"

    def test_get_display_name(self):
        """测试从元数据获取显示名称"""
        parser = YAMLMetadataParser()

        # 测试表元数据
        table_metadata = {"schema": {"display_name": "表显示名"}}
        assert parser.get_display_name(table_metadata) == "表显示名"

        # 测试视图元数据
        view_metadata = {"view": {"display_name": "视图显示名"}}
        assert parser.get_display_name(view_metadata) == "视图显示名"

        # 测试表单元数据
        form_metadata = {"form": {"display_name": "表单显示名"}}
        assert parser.get_display_name(form_metadata) == "表单显示名"

        # 测试无显示名称
        no_display = {"other": "data"}
        assert parser.get_display_name(no_display) is None


# ==================== MetadataAgent 工具处理测试 ====================

@pytest.mark.unit
class TestMetadataAgentTools:
    """测试 MetadataAgent 工具处理功能"""

    @pytest.fixture
    def temp_dirs(self, tmp_path):
        """创建临时目录"""
        schema_dir = tmp_path / "_schema"
        schema_dir.mkdir()

        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()

        # 创建 schema 文件
        table_schema = {
            "type": "object",
            "required": ["schema"]
        }
        with open(schema_dir / "table_schema.yaml", "w") as f:
            yaml.dump(table_schema, f)

        return {"schema": schema_dir, "tables": tables_dir, "base": tmp_path}

    @pytest.fixture
    def metadata_agent(self, temp_dirs):
        """创建 MetadataAgent 实例"""
        return MetadataAgent(
            schema_dir=str(temp_dirs["schema"]),
            metadata_dir=str(temp_dirs["base"])
        )

    # ==================== parse 工具测试 ====================

    @pytest.mark.asyncio
    async def test_handle_parse_success(self, metadata_agent, temp_dirs):
        """测试成功处理 parse 工具"""
        # 创建测试文件
        test_file = temp_dirs["tables"] / "parse_test.yaml"
        test_data = {
            "schema": {
                "schema_name": "parsed_entity",
                "display_name": "解析测试"
            }
        }
        with open(test_file, "w") as f:
            yaml.dump(test_data, f)

        result = await metadata_agent.parse(str(test_file), "table")
        data = json.loads(result)

        assert data["success"] is True
        assert data["type"] == "table"
        # schema_name is extracted from the parsed metadata
        assert data["metadata"]["schema_name"] == "parsed_entity"

    @pytest.mark.asyncio
    async def test_handle_parse_file_not_found(self, metadata_agent):
        """测试解析不存在的文件"""
        result = await metadata_agent.parse("non_existent.yaml", "table")
        data = json.loads(result)

        assert "error" in data
        assert "not found" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_handle_parse_without_type(self, metadata_agent, temp_dirs):
        """测试不指定类型自动检测"""
        test_file = temp_dirs["tables"] / "auto_detect.yaml"
        test_data = {
            "schema": {
                "schema_name": "auto_entity",
                "display_name": "自动检测"
            }
        }
        with open(test_file, "w") as f:
            yaml.dump(test_data, f)

        result = await metadata_agent.parse(str(test_file), None)
        data = json.loads(result)

        assert data["success"] is True

    # ==================== validate 工具测试 ====================

    @pytest.mark.asyncio
    async def test_handle_validate_success(self, metadata_agent):
        """测试成功验证元数据"""
        valid_data = {
            "schema": {
                "schema_name": "valid_entity",
                "display_name": "有效实体"
            }
        }

        result = await metadata_agent.validate(json.dumps(valid_data), "table_schema")
        data = json.loads(result)

        assert data["valid"] is True
        assert len(data["errors"]) == 0

    @pytest.mark.asyncio
    async def test_handle_validate_failure(self, metadata_agent):
        """测试验证失败的元数据"""
        invalid_data = {
            "schema": {
                # 缺少 schema_name 和 display_name
            }
        }

        result = await metadata_agent.validate(json.dumps(invalid_data), "table_schema")
        data = json.loads(result)

        assert data["valid"] is False
        assert len(data["errors"]) > 0

    @pytest.mark.asyncio
    async def test_handle_validate_from_file(self, metadata_agent, temp_dirs):
        """测试从文件验证"""
        test_file = temp_dirs["tables"] / "validate_file.yaml"
        test_data = {
            "schema": {
                "schema_name": "file_entity",
                "display_name": "文件验证"
            }
        }
        with open(test_file, "w") as f:
            yaml.dump(test_data, f)

        result = await metadata_agent.validate(str(test_file), "table_schema")
        data = json.loads(result)

        assert data["valid"] is True

    @pytest.mark.asyncio
    async def test_handle_validate_schema_not_found(self, metadata_agent):
        """测试验证时 schema 不存在"""
        result = await metadata_agent.validate("{}", "nonexistent_schema")
        data = json.loads(result)

        # The validate method returns valid=False with errors list when schema not found
        assert data["valid"] is False
        assert len(data["errors"]) > 0
        assert any("not found" in error.lower() for error in data["errors"])

    # ==================== create_form 工具测试 ====================

    @pytest.mark.asyncio
    async def test_handle_create_form(self, metadata_agent):
        """测试创建表单"""
        form_data = {
            "schema_name": "test_form",
            "entity": "test_entity",
            "type": "Main",
            "display_name": "测试表单"
        }

        result = await metadata_agent.create_form(json.dumps(form_data))
        data = json.loads(result)

        assert data["success"] is True
        assert data["schema_name"] == "test_form"
        assert data["entity"] == "test_entity"

    @pytest.mark.asyncio
    async def test_handle_create_form_from_file(self, metadata_agent, temp_dirs):
        """测试从文件创建表单"""
        forms_dir = temp_dirs["base"] / "forms"
        forms_dir.mkdir()

        test_file = forms_dir / "test_form.yaml"
        form_data = {
            "form": {
                "schema_name": "file_form",
                "entity": "test_entity",
                "type": "Main",
                "display_name": "文件表单"
            }
        }
        with open(test_file, "w") as f:
            yaml.dump(form_data, f)

        result = await metadata_agent.create_form(str(test_file))
        data = json.loads(result)

        assert data["success"] is True
        assert data["schema_name"] == "file_form"

    # ==================== create_view 工具测试 ====================

    @pytest.mark.asyncio
    async def test_handle_create_view(self, metadata_agent):
        """测试创建视图"""
        view_data = {
            "schema_name": "test_view",
            "entity": "test_entity",
            "type": "PublicView",
            "display_name": "测试视图"
        }

        result = await metadata_agent.create_view(json.dumps(view_data))
        data = json.loads(result)

        assert data["success"] is True
        assert data["schema_name"] == "test_view"
        assert data["entity"] == "test_entity"

    # ==================== delete_metadata 工具测试 ====================

    @pytest.mark.asyncio
    async def test_handle_delete_metadata(self, metadata_agent):
        """测试删除元数据"""
        result = await metadata_agent.delete_metadata("table", "test_entity")
        data = json.loads(result)

        assert "warning" in data
        assert "test_entity" in data["warning"]
        assert "solution" in data["recommendation"].lower()

    # ==================== 未知工具测试 ====================

    @pytest.mark.asyncio
    async def test_handle_unknown_tool(self, metadata_agent):
        """测试处理未知工具"""
        result = await metadata_agent.handle("unknown_tool", {})
        data = json.loads(result)

        assert "error" in data
        assert "Unknown tool" in data["error"]


# ==================== 辅助方法测试 ====================

@pytest.mark.unit
class TestHelperMethods:
    """测试 MetadataAgent 辅助方法"""

    @pytest.fixture
    def metadata_agent(self):
        """创建 MetadataAgent 实例"""
        return MetadataAgent()

    def test_convert_attribute_metadata_string(self, metadata_agent):
        """测试转换 String 类型属性元数据"""
        attribute = {
            "name": "testField",
            "display_name": "测试字段",
            "required": True,
            "max_length": 100
        }

        result = metadata_agent._convert_attribute_metadata(attribute, "String")

        assert result["@odata.type"] == "Microsoft.Dynamics.CRM.StringAttributeMetadata"
        assert result["SchemaName"] == "testField"
        assert result["DisplayName"] == "测试字段"
        assert result["RequiredLevel"]["Value"] == "ApplicationRequired"
        assert result["MaxLength"] == 100

    def test_convert_attribute_metadata_money(self, metadata_agent):
        """测试转换 Money 类型属性元数据"""
        attribute = {
            "name": "amount",
            "display_name": "金额",
            "precision": 4
        }

        result = metadata_agent._convert_attribute_metadata(attribute, "Money")

        assert result["@odata.type"] == "Microsoft.Dynamics.CRM.MoneyAttributeMetadata"
        assert result["Precision"] == 4
        assert result["PrecisionSource"] == 2

    def test_convert_attribute_metadata_picklist(self, metadata_agent):
        """测试转换 Picklist 类型属性元数据"""
        attribute = {
            "name": "status",
            "display_name": "状态",
            "options": [
                {"value": 1, "label": "选项1"},
                {"value": 2, "label": "选项2"}
            ]
        }

        result = metadata_agent._convert_attribute_metadata(attribute, "Picklist")

        assert result["@odata.type"] == "Microsoft.Dynamics.CRM.PicklistAttributeMetadata"
        assert "OptionSet" in result
        assert len(result["OptionSet"]["Options"]) == 2
        assert result["OptionSet"]["Options"][0]["Value"] == 1

    def test_convert_attribute_metadata_memo(self, metadata_agent):
        """测试转换 Memo 类型属性元数据"""
        attribute = {
            "name": "description",
            "display_name": "描述",
            "max_length": 500
        }

        result = metadata_agent._convert_attribute_metadata(attribute, "Memo")

        assert result["@odata.type"] == "Microsoft.Dynamics.CRM.MemoAttributeMetadata"
        assert result["MaxLength"] == 500

    def test_build_fetch_xml(self):
        """测试构建 Fetch XML"""
        parser = YAMLMetadataParser()

        fetch_xml = parser.build_fetch_xml(
            entity="account",
            attributes=["name", "accountnumber"],
            filter_conditions=[
                {"attribute": "status", "operator": "eq", "value": "1"}
            ],
            order_by="name"
        )

        assert '<fetch version="1.0"' in fetch_xml
        assert 'entity name="account"' in fetch_xml
        assert 'attribute name="name"' in fetch_xml
        assert 'attribute name="accountnumber"' in fetch_xml
        assert 'condition attribute="status" operator="eq" value="1"' in fetch_xml
        assert 'order attribute="name"' in fetch_xml

    def test_compare_metadata_differences(self, metadata_agent):
        """测试元数据差异对比"""
        local = {
            "schema": {"schema_name": "test_entity"},
            "attributes": [
                {"name": "field1"},
                {"name": "field2"}
            ]
        }

        remote = {
            "SchemaName": "test_entity",
            "Attributes": [
                {"SchemaName": "field1"},
                {"SchemaName": "field3"}
            ]
        }

        differences = metadata_agent._compare_metadata(local, remote)

        # field2 只在本地
        local_only = [d for d in differences if d.get("status") == "local_only"]
        assert any(d["name"] == "field2" for d in local_only)

        # field3 只在远程
        remote_only = [d for d in differences if d.get("status") == "remote_only"]
        assert any(d["name"] == "field3" for d in remote_only)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
