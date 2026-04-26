#!/usr/bin/env python3
"""
Power Platform Agent - Import Test
测试项目所有模块是否可以正确导入
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "framework"))


@pytest.mark.unit
class TestModuleImports:
    """测试所有模块导入"""

    def test_utils_imports(self):
        """测试工具模块导入"""
        # 测试基本导入
        from framework.utils import (
            DataverseClient,
            YAMLMetadataParser,
        )

        assert DataverseClient is not None
        assert YAMLMetadataParser is not None

    def test_utils_schema_validator_import(self):
        """测试schema_validator模块导入"""
        from framework.utils.schema_validator import (
            SchemaValidator,
            QuickValidator,
        )

        assert SchemaValidator is not None
        assert QuickValidator is not None

    def test_utils_naming_converter_import(self):
        """测试naming_converter模块导入"""
        from framework.utils.naming_converter import (
            NamingConverter,
            NamingValidator,
        )

        assert NamingConverter is not None
        assert NamingValidator is not None

    def test_agents_imports(self):
        """测试代理模块导入"""
        from framework.agents.core_agent import CoreAgent

        assert CoreAgent is not None

    @pytest.mark.skipif(
        sys.version_info < (3, 10),
        reason="requires Python 3.10 or higher"
    )
    def test_mcp_module_available(self):
        """测试MCP模块可用性"""
        try:
            import mcp
            assert mcp is not None
        except ImportError:
            pytest.skip("mcp module not installed (expected in some environments)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
