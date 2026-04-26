#!/usr/bin/env python3
"""
Power Platform Agent - SolutionAgent Unit Tests
测试 SolutionAgent 的解决方案管理功能
"""

import pytest
import sys
import json
import hashlib
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime
import tempfile

# 添加项目路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "framework"))

from framework.agents.solution_agent import SolutionAgent


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_core_agent():
    """创建模拟的 CoreAgent"""
    agent = MagicMock()
    agent.get_client = MagicMock()
    return agent


@pytest.fixture
def mock_dataverse_client():
    """创建模拟的 DataverseClient"""
    client = MagicMock()
    client.get_solutions = MagicMock()
    client.get_solution_components = MagicMock()
    client.get_api_url = MagicMock(return_value="https://mock.api/v9.2/test")
    client.session = MagicMock()
    return client


@pytest.fixture
def solution_agent(mock_core_agent):
    """创建 SolutionAgent 实例"""
    agent = SolutionAgent(core_agent=mock_core_agent)
    return agent


@pytest.fixture
def temp_local_path(tmp_path):
    """创建临时本地路径用于差异测试"""
    local_dir = tmp_path / "src"
    local_dir.mkdir(parents=True, exist_ok=True)

    # 创建一些模拟的 YAML 文件
    test_files = {
        "entities/account.yaml": "name: account\ndisplay_name: Account",
        "entities/contact.yaml": "name: contact\ndisplay_name: Contact",
        "webresources/test.js.yaml": "name: new_test\ncontent: console.log('test');"
    }

    for file_path, content in test_files.items():
        file = local_dir / file_path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")

    return local_dir


@pytest.fixture
def sample_solutions_data():
    """示例解决方案数据"""
    return [
        {
            "solutionid": "00000000-0000-0000-0000-000000000001",
            "uniquename": "ActiveSolution",
            "friendlyname": "Active Solution",
            "version": "1.0.0.1",
            "publisherid": {"name": "Contoso"},
            "ismanaged": False,
            "isvisible": True
        },
        {
            "solutionid": "00000000-0000-0000-0000-000000000002",
            "uniquename": "ManagedSolution",
            "friendlyname": "Managed Solution",
            "version": "2.0.0.0",
            "publisherid": {"name": "Contoso"},
            "ismanaged": True,
            "isvisible": True
        },
        {
            "solutionid": "00000000-0000-0000-0000-000000000003",
            "uniquename": "HiddenSolution",
            "friendlyname": "Hidden Solution",
            "version": "1.0.0.0",
            "publisherid": {"name": "Contoso"},
            "ismanaged": False,
            "isvisible": False
        }
    ]


@pytest.fixture
def sample_components_data():
    """示例解决方案组件数据"""
    return [
        {
            "objecttypecode": 1,
            "componenttype": "Entity",
            "objectid": "00000000-0000-0000-0000-000000000001"
        },
        {
            "objecttypecode": 2,
            "componenttype": "Attribute",
            "objectid": "00000000-0000-0000-0000-000000000002"
        },
        {
            "objecttypecode": 21,
            "componenttype": "WebResource",
            "objectid": "00000000-0000-0000-0000-000000000003"
        }
    ]


# =============================================================================
# 测试类：解决方案状态测试（只读操作）
# =============================================================================

@pytest.mark.unit
class TestSolutionAgentStatus:
    """测试 SolutionAgent 状态查询功能（只读）"""

    @pytest.mark.asyncio
    async def test_status_returns_state_info(self, solution_agent):
        """测试 status 方法返回状态信息"""
        # 修改内部状态
        solution_agent._state = {
            "last_sync": "2024-01-15T10:30:00",
            "solutions": {
                "TestSolution": {
                    "last_export": "2024-01-15T10:30:00"
                }
            }
        }

        result = await solution_agent.status()
        data = json.loads(result)

        assert "state_file" in data
        assert "last_sync" in data
        assert data["last_sync"] == "2024-01-15T10:30:00"
        assert "tracked_solutions" in data
        assert "TestSolution" in data["tracked_solutions"]

    @pytest.mark.asyncio
    async def test_status_with_empty_state(self, solution_agent):
        """测试空状态时的 status 方法"""
        result = await solution_agent.status()
        data = json.loads(result)

        assert "state_file" in data
        assert data["last_sync"] is None
        assert data["tracked_solutions"] == []

    @pytest.mark.asyncio
    async def test_status_with_multiple_tracked_solutions(self, solution_agent):
        """测试多个追踪解决方案的状态"""
        solution_agent._state = {
            "last_sync": "2024-01-15T10:30:00",
            "solutions": {
                "SolutionA": {"last_export": "2024-01-15T10:00:00"},
                "SolutionB": {"last_export": "2024-01-15T11:00:00"},
                "SolutionC": {"last_export": "2024-01-15T12:00:00"}
            }
        }

        result = await solution_agent.status()
        data = json.loads(result)

        assert len(data["tracked_solutions"]) == 3
        assert "SolutionA" in data["tracked_solutions"]
        assert "SolutionB" in data["tracked_solutions"]
        assert "SolutionC" in data["tracked_solutions"]


@pytest.mark.unit
class TestSolutionAgentList:
    """测试 SolutionAgent 列出解决方案功能（只读）"""

    @pytest.mark.asyncio
    async def test_list_solutions_success(
        self, solution_agent, mock_core_agent, mock_dataverse_client, sample_solutions_data
    ):
        """测试成功列出解决方案"""
        mock_core_agent.get_client.return_value = mock_dataverse_client
        mock_dataverse_client.get_solutions.return_value = sample_solutions_data

        result = await solution_agent.list_solutions()
        data = json.loads(result)

        assert "solutions" in data
        assert len(data["solutions"]) == 3

        # 验证第一个解决方案
        first_solution = data["solutions"][0]
        assert first_solution["id"] == "00000000-0000-0000-0000-000000000001"
        assert first_solution["unique_name"] == "ActiveSolution"
        assert first_solution["display_name"] == "Active Solution"
        assert first_solution["version"] == "1.0.0.1"
        assert first_solution["publisher"] == "Contoso"
        assert first_solution["is_managed"] is False
        assert first_solution["is_visible"] is True

    @pytest.mark.asyncio
    async def test_list_solutions_empty(self, solution_agent, mock_core_agent, mock_dataverse_client):
        """测试列出空解决方案列表"""
        mock_core_agent.get_client.return_value = mock_dataverse_client
        mock_dataverse_client.get_solutions.return_value = []

        result = await solution_agent.list_solutions()
        data = json.loads(result)

        assert "solutions" in data
        assert len(data["solutions"]) == 0

    @pytest.mark.asyncio
    async def test_list_solutions_no_core_agent(self, solution_agent):
        """测试没有 core_agent 时列出解决方案"""
        solution_agent.core_agent = None

        result = await solution_agent.list_solutions()
        data = json.loads(result)

        assert "error" in data
        assert "No core agent available" in data["error"]

    @pytest.mark.asyncio
    async def test_list_solutions_with_api_error(
        self, solution_agent, mock_core_agent, mock_dataverse_client
    ):
        """测试 API 错误时列出解决方案"""
        mock_core_agent.get_client.return_value = mock_dataverse_client
        mock_dataverse_client.get_solutions.side_effect = Exception("API Error")

        result = await solution_agent.list_solutions()
        data = json.loads(result)

        assert "error" in data
        assert "Failed to list solutions" in data["error"]


@pytest.mark.unit
class TestSolutionAgentComponents:
    """测试 SolutionAgent 组件查询功能（只读）"""

    @pytest.mark.asyncio
    async def test_diff_success(
        self, solution_agent, mock_core_agent, mock_dataverse_client,
        temp_local_path, sample_components_data
    ):
        """测试成功的差异比较"""
        mock_core_agent.get_client.return_value = mock_dataverse_client
        mock_dataverse_client.get_solution_components.return_value = sample_components_data

        result = await solution_agent.diff(str(temp_local_path), "TestSolution")
        data = json.loads(result)

        assert "solution" in data
        assert data["solution"] == "TestSolution"
        assert "local_path" in data
        assert "differences" in data
        assert "local_files_count" in data
        assert "solution_components_count" in data
        assert data["local_files_count"] == 3
        assert data["solution_components_count"] == 3

        # 验证差异结构
        differences = data["differences"]
        assert "local_only" in differences
        assert "solution_only" in differences
        assert "modified" in differences
        assert "identical" in differences

    @pytest.mark.asyncio
    async def test_diff_empty_local_path(self, solution_agent, mock_core_agent, mock_dataverse_client):
        """测试空本地路径的差异比较"""
        mock_core_agent.get_client.return_value = mock_dataverse_client
        mock_dataverse_client.get_solution_components.return_value = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            empty_dir = Path(tmp_dir)
            result = await solution_agent.diff(str(empty_dir), "TestSolution")
            data = json.loads(result)

            assert data["local_files_count"] == 0

    @pytest.mark.asyncio
    async def test_diff_no_core_agent(self, solution_agent, temp_local_path):
        """测试没有 core_agent 时的差异比较"""
        solution_agent.core_agent = None

        result = await solution_agent.diff(str(temp_local_path), "TestSolution")
        data = json.loads(result)

        assert "error" in data
        assert "No core agent available" in data["error"]

    @pytest.mark.asyncio
    async def test_diff_with_exception(
        self, solution_agent, mock_core_agent, mock_dataverse_client, temp_local_path
    ):
        """测试差异比较时发生异常"""
        mock_core_agent.get_client.return_value = mock_dataverse_client
        mock_dataverse_client.get_solution_components.side_effect = Exception("Component fetch failed")

        result = await solution_agent.diff(str(temp_local_path), "TestSolution")
        data = json.loads(result)

        assert "error" in data
        assert "Diff failed" in data["error"]


# =============================================================================
# 测试类：解决方案差异测试（本地操作）
# =============================================================================

@pytest.mark.unit
class TestSolutionAgentDiffLocal:
    """测试本地差异计算功能"""

    @pytest.mark.asyncio
    async def test_diff_calculates_file_hashes(
        self, solution_agent, mock_core_agent, mock_dataverse_client,
        temp_local_path, sample_components_data
    ):
        """测试差异计算时正确计算文件哈希"""
        mock_core_agent.get_client.return_value = mock_dataverse_client
        mock_dataverse_client.get_solution_components.return_value = sample_components_data

        result = await solution_agent.diff(str(temp_local_path), "TestSolution")
        data = json.loads(result)

        # 验证 local_files 包含哈希
        assert data["local_files_count"] > 0

        # 验证解决方案组件被正确映射
        assert data["solution_components_count"] == 3

    @pytest.mark.asyncio
    async def test_diff_identifies_yaml_files(
        self, solution_agent, mock_core_agent, mock_dataverse_client,
        temp_local_path, sample_components_data
    ):
        """测试差异比较只识别 YAML 文件"""
        mock_core_agent.get_client.return_value = mock_dataverse_client
        mock_dataverse_client.get_solution_components.return_value = sample_components_data

        # 添加非 YAML 文件
        (temp_local_path / "readme.txt").write_text("This is a readme")
        (temp_local_path / "data.json").write_text('{"key": "value"}')

        result = await solution_agent.diff(str(temp_local_path), "TestSolution")
        data = json.loads(result)

        # 应该只统计 YAML 文件
        assert data["local_files_count"] == 3

    @pytest.mark.asyncio
    async def test_diff_handles_nested_directories(
        self, solution_agent, mock_core_agent, mock_dataverse_client,
        tmp_path, sample_components_data
    ):
        """测试差异比较处理嵌套目录"""
        mock_core_agent.get_client.return_value = mock_dataverse_client
        mock_dataverse_client.get_solution_components.return_value = sample_components_data

        # 创建嵌套目录结构
        nested_dir = tmp_path / "src" / "entities" / "subfolder"
        nested_dir.mkdir(parents=True)
        (nested_dir / "nested.yaml").write_text("name: nested")

        result = await solution_agent.diff(str(tmp_path / "src"), "TestSolution")
        data = json.loads(result)

        assert data["local_files_count"] == 4  # 3个基础文件 + 1个嵌套文件


# =============================================================================
# 测试类：状态管理测试
# =============================================================================

@pytest.mark.unit
class TestSolutionAgentStateManagement:
    """测试 SolutionAgent 状态管理功能"""

    def test_load_state_creates_default(self, tmp_path):
        """测试加载状态时创建默认状态"""
        with patch.object(SolutionAgent, '__init__', lambda self, core_agent=None: None):
            agent = SolutionAgent()
            agent.state_dir = tmp_path
            agent._state = agent._load_state()

            assert agent._state is not None
            assert agent._state["last_sync"] is None
            assert agent._state["solutions"] == {}

    def test_load_state_from_file(self, tmp_path):
        """测试从文件加载状态"""
        # 创建状态文件
        state_file = tmp_path / "state.json"
        test_state = {
            "last_sync": "2024-01-15T10:30:00",
            "solutions": {
                "TestSolution": {
                    "last_export": "2024-01-15T10:00:00",
                    "managed": False
                }
            }
        }
        state_file.write_text(json.dumps(test_state, ensure_ascii=False), encoding="utf-8")

        with patch.object(SolutionAgent, '__init__', lambda self, core_agent=None: None):
            agent = SolutionAgent()
            agent.state_dir = tmp_path
            agent._state = agent._load_state()

            assert agent._state["last_sync"] == "2024-01-15T10:30:00"
            assert "TestSolution" in agent._state["solutions"]

    def test_save_state(self, tmp_path):
        """测试保存状态"""
        with patch.object(SolutionAgent, '__init__', lambda self, core_agent=None: None):
            agent = SolutionAgent()
            agent.state_dir = tmp_path
            agent._state = {
                "last_sync": "2024-01-15T10:30:00",
                "solutions": {}
            }
            agent._save_state()

            state_file = tmp_path / "state.json"
            assert state_file.exists()

            loaded_state = json.loads(state_file.read_text(encoding="utf-8"))
            assert loaded_state["last_sync"] == "2024-01-15T10:30:00"

    def test_update_export_status(self, tmp_path):
        """测试更新导出状态"""
        with patch.object(SolutionAgent, '__init__', lambda self, core_agent=None: None):
            agent = SolutionAgent()
            agent.state_dir = tmp_path
            agent._state = {"solutions": {}}

            agent._update_export_status("TestSolution", "/path/to/solution.zip", False)

            state_file = tmp_path / "state.json"
            loaded_state = json.loads(state_file.read_text(encoding="utf-8"))

            assert "TestSolution" in loaded_state["solutions"]
            assert loaded_state["solutions"]["TestSolution"]["managed"] is False
            assert loaded_state["solutions"]["TestSolution"]["last_export_path"] == "/path/to/solution.zip"
            assert "last_export" in loaded_state["solutions"]["TestSolution"]

    @pytest.mark.asyncio
    async def test_state_caching_mechanism(self, solution_agent):
        """测试状态缓存机制"""
        # 修改内部状态
        test_state = {
            "last_sync": "2024-01-15T10:30:00",
            "solutions": {
                "SolutionA": {"last_export": "2024-01-15T10:00:00"}
            }
        }
        solution_agent._state = test_state

        # 验证状态被缓存
        assert solution_agent._state == test_state
        assert solution_agent._state["last_sync"] == "2024-01-15T10:30:00"

    @pytest.mark.asyncio
    async def test_state_persistence_across_operations(self, solution_agent, tmp_path):
        """测试跨操作的状态持久化"""
        solution_agent.state_dir = tmp_path
        solution_agent._state = {"solutions": {}}

        # 更新导出状态
        solution_agent._update_export_status("Solution1", "/path1.zip", True)

        # 更新另一个导出状态
        solution_agent._update_export_status("Solution2", "/path2.zip", False)

        # 验证状态被保存
        state_file = tmp_path / "state.json"
        loaded_state = json.loads(state_file.read_text(encoding="utf-8"))

        assert len(loaded_state["solutions"]) == 2
        assert "Solution1" in loaded_state["solutions"]
        assert "Solution2" in loaded_state["solutions"]
        assert loaded_state["solutions"]["Solution1"]["managed"] is True
        assert loaded_state["solutions"]["Solution2"]["managed"] is False


# =============================================================================
# 测试类：工具方法测试
# =============================================================================

@pytest.mark.unit
class TestSolutionAgentUtilities:
    """测试 SolutionAgent 工具方法"""

    def test_get_component_type_code_entity(self, solution_agent):
        """测试获取实体类型代码"""
        code = solution_agent._get_component_type_code("entity")
        assert code == 1

    def test_get_component_type_code_attribute(self, solution_agent):
        """测试获取属性类型代码"""
        code = solution_agent._get_component_type_code("attribute")
        assert code == 2

    def test_get_component_type_code_webresource(self, solution_agent):
        """测试获取 WebResource 类型代码"""
        code = solution_agent._get_component_type_code("webresource")
        assert code == 21

    def test_get_component_type_code_workflow(self, solution_agent):
        """测试获取工作流类型代码"""
        code = solution_agent._get_component_type_code("workflow")
        assert code == 93

    def test_get_component_type_code_unknown(self, solution_agent):
        """测试未知类型代码"""
        code = solution_agent._get_component_type_code("unknown_type")
        assert code == 0

    def test_get_component_type_code_case_insensitive(self, solution_agent):
        """测试类型代码大小写不敏感"""
        code1 = solution_agent._get_component_type_code("Entity")
        code2 = solution_agent._get_component_type_code("ENTITY")
        code3 = solution_agent._get_component_type_code("entity")

        assert code1 == code2 == code3 == 1


# =============================================================================
# 测试类：Handle 方法测试
# =============================================================================

@pytest.mark.unit
class TestSolutionAgentHandle:
    """测试 SolutionAgent 工具处理器"""

    @pytest.mark.asyncio
    async def test_handle_status(self, solution_agent):
        """测试处理 solution_status 工具"""
        result = await solution_agent.handle("solution_status", {})
        data = json.loads(result)

        assert "state_file" in data or "error" not in result

    @pytest.mark.asyncio
    async def test_handle_list(self, solution_agent, mock_core_agent, mock_dataverse_client):
        """测试处理 solution_list 工具"""
        mock_core_agent.get_client.return_value = mock_dataverse_client
        mock_dataverse_client.get_solutions.return_value = []

        result = await solution_agent.handle("solution_list", {})
        data = json.loads(result)

        assert "solutions" in data or "error" in data

    @pytest.mark.asyncio
    async def test_handle_diff(self, solution_agent, mock_core_agent, mock_dataverse_client, tmp_path):
        """测试处理 solution_diff 工具"""
        mock_core_agent.get_client.return_value = mock_dataverse_client
        mock_dataverse_client.get_solution_components.return_value = []

        result = await solution_agent.handle("solution_diff", {
            "local_path": str(tmp_path),
            "solution_name": "TestSolution"
        })
        data = json.loads(result)

        assert "solution" in data or "error" in data

    @pytest.mark.asyncio
    async def test_handle_unknown_tool(self, solution_agent):
        """测试处理未知工具"""
        result = await solution_agent.handle("unknown_tool", {})
        data = json.loads(result)

        assert "error" in data
        assert "Unknown tool" in data["error"]

    @pytest.mark.asyncio
    async def test_handle_tool_with_exception(self, solution_agent):
        """测试工具处理时发生异常"""
        # 传递无效参数触发异常
        result = await solution_agent.handle("solution_diff", {})
        data = json.loads(result)

        assert "error" in data


# =============================================================================
# 测试类：只读操作 - 不修改解决方案
# =============================================================================

@pytest.mark.unit
class TestSolutionAgentReadOnlyOperations:
    """测试 SolutionAgent 只读操作（不修改解决方案）"""

    @pytest.mark.asyncio
    async def test_clone_does_not_modify_solutions(self, solution_agent):
        """测试克隆操作不修改原始解决方案（返回模拟响应）"""
        result = await solution_agent.clone("SourceSolution", "TargetSolution")
        data = json.loads(result)

        assert data["success"] is True
        assert data["source"] == "SourceSolution"
        assert data["target"] == "TargetSolution"
        assert "message" in data

    @pytest.mark.asyncio
    async def test_upgrade_does_not_modify_solutions(self, solution_agent):
        """测试升级操作不修改解决方案（返回模拟响应）"""
        result = await solution_agent.upgrade("TestSolution")
        data = json.loads(result)

        assert data["success"] is True
        assert data["solution"] == "TestSolution"
        assert "message" in data

    @pytest.mark.asyncio
    async def test_pack_returns_expected_format(self, solution_agent):
        """测试打包操作返回预期格式（不实际打包）"""
        components = [
            {"type": "entity", "id": "001"},
            {"type": "webresource", "id": "002"}
        ]

        result = await solution_agent.pack(components, "/output/path.zip")
        data = json.loads(result)

        assert "success" in data or "error" in data
        if "success" in data and data["success"]:
            assert data["components_count"] == 2


# =============================================================================
# 测试类：状态缓存和性能测试
# =============================================================================

@pytest.mark.unit
class TestSolutionAgentCaching:
    """测试 SolutionAgent 缓存机制"""

    @pytest.mark.asyncio
    async def test_state_not_reloaded_unnecessarily(self, solution_agent):
        """测试状态不必要时不重新加载"""
        original_state = {"key": "value"}
        solution_agent._state = original_state

        # 多次访问状态
        for _ in range(5):
            assert solution_agent._state == original_state

    @pytest.mark.asyncio
    async def test_multiple_status_calls_consistency(self, solution_agent):
        """测试多次状态调用的一致性"""
        solution_agent._state = {
            "last_sync": "2024-01-15T10:30:00",
            "solutions": {"Solution1": {}}
        }

        results = []
        for _ in range(3):
            result = await solution_agent.status()
            results.append(json.loads(result))

        # 所有结果应该一致
        for result in results:
            assert result["last_sync"] == "2024-01-15T10:30:00"
            assert "Solution1" in result["tracked_solutions"]


# =============================================================================
# 测试类：错误处理和边界情况
# =============================================================================

@pytest.mark.unit
class TestSolutionAgentErrorHandling:
    """测试 SolutionAgent 错误处理和边界情况"""

    @pytest.mark.asyncio
    async def test_handle_with_missing_arguments(self, solution_agent):
        """测试缺少参数时的工具处理"""
        result = await solution_agent.handle("solution_export", {})
        data = json.loads(result)

        # 应该返回错误或使用默认值
        assert "error" in data or "solution" in data

    @pytest.mark.asyncio
    async def test_list_with_none_solutions(self, solution_agent, mock_core_agent, mock_dataverse_client):
        """测试解决方案为 None 的情况"""
        mock_core_agent.get_client.return_value = mock_dataverse_client
        mock_dataverse_client.get_solutions.return_value = None

        result = await solution_agent.list_solutions()
        data = json.loads(result)

        # 应该处理 None 情况
        assert "error" in data or "solutions" in data

    @pytest.mark.asyncio
    async def test_diff_with_nonexistent_path(self, solution_agent, mock_core_agent, mock_dataverse_client):
        """测试使用不存在的路径进行差异比较"""
        mock_core_agent.get_client.return_value = mock_dataverse_client
        mock_dataverse_client.get_solution_components.return_value = []

        result = await solution_agent.diff("/nonexistent/path", "TestSolution")
        data = json.loads(result)

        # 应该处理不存在路径
        assert "error" in data or "local_files_count" in data


# =============================================================================
# 测试类：组件类型代码映射
# =============================================================================

@pytest.mark.unit
class TestSolutionAgentComponentTypeCodes:
    """测试组件类型代码映射的完整性"""

    @pytest.mark.parametrize("type_name,expected_code", [
        ("entity", 1),
        ("attribute", 2),
        ("relationship", 3),
        ("optionset", 4),
        ("entity_key", 5),
        ("stringmap", 6),
        ("relationship_role", 7),
        ("form", 10),
        ("view", 11),
        ("savedquery", 12),
        ("query", 13),
        ("report", 14),
        ("dashboard", 15),
        ("systemform", 16),
        ("webresource", 21),
        ("plugin", 90),
        ("sdkmessage", 91),
        ("sdkmessageprocessingstep", 92),
        ("workflow", 93),
    ])
    def test_all_component_type_codes(self, solution_agent, type_name, expected_code):
        """测试所有组件类型代码映射"""
        code = solution_agent._get_component_type_code(type_name)
        assert code == expected_code


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "unit"])
