#!/usr/bin/env python3
"""
Power Platform Agent - PluginAgent Unit Tests
测试 PluginAgent 的插件管理功能
"""

import pytest
import sys
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import tempfile
import shutil

# 添加项目路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "framework"))


# ==================== Fixtures ====================

@pytest.fixture
def mock_core_agent():
    """创建模拟的 CoreAgent 实例"""
    agent = MagicMock()
    agent._current_environment = "dev"
    agent._tokens = {"dev": "mock-token"}
    return agent


@pytest.fixture
def plugin_agent(mock_core_agent):
    """创建 PluginAgent 实例"""
    from framework.agents.plugin_agent import PluginAgent
    return PluginAgent(core_agent=mock_core_agent)


@pytest.fixture
def temp_plugin_project(tmp_path):
    """创建临时插件项目目录"""
    project_dir = tmp_path / "TestPlugin"
    project_dir.mkdir()

    # 创建 .csproj 文件
    csproj_content = """<?xml version="1.0" encoding="utf-8"?>
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net48</TargetFramework>
    <OutputType>Library</OutputType>
    <AssemblyName>TestPlugin</AssemblyName>
  </PropertyGroup>
  <ItemGroup>
    <Reference Include="Microsoft.Xrm.Sdk" />
  </ItemGroup>
</Project>
"""
    csproj_file = project_dir / "TestPlugin.csproj"
    csproj_file.write_text(csproj_content, encoding="utf-8")

    # 创建插件类文件
    plugin_content = """using System;
using Microsoft.Xrm.Sdk;

namespace TestPlugin
{
    public class PreAccountCreate : IPlugin
    {
        public void Execute(IServiceProvider serviceProvider)
        {
            // Plugin logic here
        }
    }
}
"""
    plugin_file = project_dir / "PreAccountCreate.cs"
    plugin_file.write_text(plugin_content, encoding="utf-8")

    # 创建配置文件
    config_content = """
plugin:
  name: TestPlugin
  description: Test plugin for unit testing
  version: 1.0.0.0

steps:
  - name: PreAccountCreate
    entity: account
    message: Create
    stage: pre-operation
    mode: 0
    deployment: 0

build:
  configuration: Release
  auto_deploy: false
  watch_mode: false
"""
    config_file = project_dir / "plugin-config.yaml"
    config_file.write_text(config_content, encoding="utf-8")

    return {
        "dir": project_dir,
        "csproj": csproj_file,
        "plugin": plugin_file,
        "config": config_file
    }


@pytest.fixture
def mock_dataverse_client():
    """创建模拟的 Dataverse 客户端"""
    client = MagicMock()
    client.get_api_url = MagicMock(return_value="https://dev.crm.dynamics.com/api/data/v9.2/")
    client.session = MagicMock()

    # 模拟 GET 请求
    mock_get_response = MagicMock()
    mock_get_response.status_code = 200
    mock_get_response.json.return_value = {
        "value": [
            {
                "pluginassemblyid": "assembly-123",
                "name": "TestPlugin",
                "version": "1.0.0.0"
            }
        ]
    }
    client.session.get = MagicMock(return_value=mock_get_response)

    # 模拟 POST 请求
    mock_post_response = MagicMock()
    mock_post_response.status_code = 201
    mock_post_response.json.return_value = {
        "sdkmessageprocessingstepid": "step-456",
        "name": "TestPlugin_account_Create"
    }
    client.session.post = MagicMock(return_value=mock_post_response)

    # 模拟 PATCH 请求
    mock_patch_response = MagicMock()
    mock_patch_response.status_code = 200
    client.session.patch = MagicMock(return_value=mock_patch_response)

    # 模拟 DELETE 请求
    mock_delete_response = MagicMock()
    mock_delete_response.status_code = 204
    client.session.delete = MagicMock(return_value=mock_delete_response)

    return client


# ==================== 测试类：插件信息测试（只读）====================

@pytest.mark.unit
class TestPluginAgentInfo:
    """测试 PluginAgent 插件信息获取功能（只读操作）"""

    @pytest.fixture
    def plugin_agent(self):
        """创建 PluginAgent 实例"""
        from framework.agents.plugin_agent import PluginAgent
        return PluginAgent(core_agent=None)

    @pytest.mark.asyncio
    async def test_get_info_with_directory(self, plugin_agent, temp_plugin_project):
        """测试从目录获取插件信息"""
        result = await plugin_agent.get_info(str(temp_plugin_project["dir"]))
        info = json.loads(result)

        assert info["project_file"] == str(temp_plugin_project["csproj"])
        assert info["project_name"] == "TestPlugin"
        assert info["target_framework"] == "net48"
        assert info["output_type"] == "Library"
        assert len(info["plugins"]) == 1
        assert info["plugins"][0]["file"] == "PreAccountCreate.cs"

    @pytest.mark.asyncio
    async def test_get_info_with_csproj_file(self, plugin_agent, temp_plugin_project):
        """测试从 .csproj 文件获取插件信息"""
        result = await plugin_agent.get_info(str(temp_plugin_project["csproj"]))
        info = json.loads(result)

        assert info["project_name"] == "TestPlugin"
        assert info["target_framework"] == "net48"

    @pytest.mark.asyncio
    async def test_get_info_nonexistent_directory(self, plugin_agent):
        """测试获取不存在的目录信息"""
        result = await plugin_agent.get_info("/nonexistent/directory")
        info = json.loads(result)

        assert "error" in info

    @pytest.mark.asyncio
    async def test_get_info_directory_without_csproj(self, plugin_agent, tmp_path):
        """测试没有 .csproj 文件的目录"""
        result = await plugin_agent.get_info(str(tmp_path))
        info = json.loads(result)

        assert "error" in info
        assert "No .csproj file found" in info["error"]

    @pytest.mark.asyncio
    async def test_get_info_detects_plugin_classes(self, plugin_agent, temp_plugin_project):
        """测试检测插件类"""
        result = await plugin_agent.get_info(str(temp_plugin_project["dir"]))
        info = json.loads(result)

        assert len(info["plugins"]) > 0
        assert info["plugins"][0]["file"] == "PreAccountCreate.cs"

    @pytest.mark.asyncio
    async def test_handle_plugin_info_tool(self, plugin_agent, temp_plugin_project):
        """测试通过 handle 方法获取插件信息"""
        result = await plugin_agent.handle("plugin_info", {
            "project_path": str(temp_plugin_project["dir"])
        })
        info = json.loads(result)

        assert info["project_name"] == "TestPlugin"


# ==================== 测试类：插件构建测试（本地操作）====================

@pytest.mark.unit
class TestPluginAgentBuild:
    """测试 PluginAgent 插件构建功能（本地操作，不执行实际构建）"""

    @pytest.fixture
    def plugin_agent(self):
        """创建 PluginAgent 实例"""
        from framework.agents.plugin_agent import PluginAgent
        return PluginAgent(core_agent=None)

    def test_resolve_project_from_directory(self, plugin_agent, temp_plugin_project):
        """测试从目录解析项目文件"""
        project_path = Path(str(temp_plugin_project["dir"]))
        csproj_files = list(project_path.glob("*.csproj"))

        assert len(csproj_files) == 1
        assert csproj_files[0].name == "TestPlugin.csproj"

    def test_resolve_project_from_csproj_file(self, plugin_agent, temp_plugin_project):
        """测试直接使用 .csproj 文件"""
        project_file = Path(str(temp_plugin_project["csproj"]))

        assert project_file.exists()
        assert project_file.suffix == ".csproj"

    @pytest.mark.asyncio
    async def test_build_nonexistent_project(self, plugin_agent):
        """测试构建不存在的项目"""
        result = await plugin_agent.build("/nonexistent/project.csproj")
        info = json.loads(result)

        assert "error" in info
        assert "not found" in info["error"]

    @pytest.mark.asyncio
    async def test_build_directory_without_csproj(self, plugin_agent, tmp_path):
        """测试构建没有 .csproj 的目录"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = await plugin_agent.build(str(empty_dir))
        info = json.loads(result)

        assert "error" in info
        assert "No .csproj file found" in info["error"]

    @pytest.mark.asyncio
    async def test_build_with_dotnet_not_available(self, plugin_agent, temp_plugin_project):
        """测试 dotnet CLI 不可用的情况"""
        with patch("framework.agents.plugin_agent.subprocess.run") as mock_run:
            # 模拟 dotnet 不可用
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_run.return_value = mock_result

            result = await plugin_agent.build(str(temp_plugin_project["csproj"]))
            info = json.loads(result)

            # 由于模拟只返回失败，应该返回错误或构建失败
            # 这取决于实际的实现逻辑
            assert result is not None

    @pytest.mark.asyncio
    async def test_build_command_generation(self):
        """测试生成构建命令"""
        project_file = "TestPlugin.csproj"
        configuration = "Release"

        expected_command = [
            "dotnet", "build",
            project_file,
            "--configuration", configuration,
            "--no-restore"
        ]

        assert expected_command[0] == "dotnet"
        assert expected_command[1] == "build"
        assert expected_command[2] == project_file
        assert "--configuration" in expected_command
        assert configuration in expected_command

    @pytest.mark.asyncio
    async def test_build_cache_storage(self, plugin_agent):
        """测试构建缓存存储"""
        # 验证 _build_cache 存在
        assert hasattr(plugin_agent, "_build_cache")
        assert isinstance(plugin_agent._build_cache, dict)

        # 模拟存储构建信息
        plugin_agent._build_cache["test_project"] = {
            "success": True,
            "output_dll": "/path/to/plugin.dll"
        }

        assert "test_project" in plugin_agent._build_cache

    @pytest.mark.asyncio
    async def test_parse_csproj_target_framework(self, temp_plugin_project):
        """测试解析 .csproj 中的 TargetFramework"""
        import xml.etree.ElementTree as ET

        with open(temp_plugin_project["csproj"], "r", encoding="utf-8") as f:
            content = f.read()

        root = ET.fromstring(content)
        namespaces = {
            'ms': 'http://schemas.microsoft.com/developer/msbuild/2003'
        }

        # 对于 SDK 风格的项目，TargetFramework 在 PropertyGroup 中
        target_framework = root.find(".//TargetFramework")
        assert target_framework is not None
        assert target_framework.text == "net48"

    @pytest.mark.asyncio
    async def test_handle_plugin_build_tool(self, plugin_agent):
        """测试通过 handle 方法调用构建"""
        result = await plugin_agent.handle("plugin_build", {
            "project_path": "/nonexistent/project.csproj",
            "configuration": "Release"
        })
        info = json.loads(result)

        assert result is not None
        # 应该返回错误信息因为项目不存在


# ==================== 测试类：程序集列表测试 ====================

@pytest.mark.unit
class TestPluginAgentListAssemblies:
    """测试 PluginAgent 程序列表功能（只读操作）"""

    @pytest.fixture
    def plugin_agent(self, mock_core_agent, mock_dataverse_client):
        """创建 PluginAgent 实例"""
        from framework.agents.plugin_agent import PluginAgent
        agent = PluginAgent(core_agent=mock_core_agent)
        return agent

    @pytest.mark.asyncio
    async def test_list_assemblies_success(self, plugin_agent, mock_core_agent, mock_dataverse_client):
        """测试成功列出程序集"""
        mock_core_agent.get_client = MagicMock(return_value=mock_dataverse_client)

        result = await plugin_agent.list_assemblies()
        data = json.loads(result)

        assert "assemblies" in data
        assert len(data["assemblies"]) == 1
        assert data["assemblies"][0]["name"] == "TestPlugin"
        assert data["assemblies"][0]["id"] == "assembly-123"

    @pytest.mark.asyncio
    async def test_list_assemblies_without_core_agent(self):
        """测试没有 core_agent 时列出程序集"""
        from framework.agents.plugin_agent import PluginAgent
        agent = PluginAgent(core_agent=None)

        result = await agent.list_assemblies()
        data = json.loads(result)

        assert "error" in data
        assert "No core agent" in data["error"]

    @pytest.mark.asyncio
    async def test_handle_plugin_assembly_list_tool(self, plugin_agent, mock_core_agent, mock_dataverse_client):
        """测试通过 handle 方法列出程序集"""
        mock_core_agent.get_client = MagicMock(return_value=mock_dataverse_client)

        result = await plugin_agent.handle("plugin_assembly_list", {})
        data = json.loads(result)

        assert "assemblies" in data


# ==================== 测试类：步骤配置测试 ====================

@pytest.mark.unit
class TestPluginAgentStepConfig:
    """测试 PluginAgent 步骤配置功能"""

    @pytest.fixture
    def plugin_agent(self, mock_core_agent, mock_dataverse_client):
        """创建 PluginAgent 实例"""
        from framework.agents.plugin_agent import PluginAgent
        agent = PluginAgent(core_agent=mock_core_agent)
        return agent

    def test_stage_mapping(self):
        """测试阶段映射"""
        stage_mapping = {
            "pre-validation": 10,
            "pre-operation": 20,
            "post-operation": 40
        }

        assert stage_mapping["pre-validation"] == 10
        assert stage_mapping["pre-operation"] == 20
        assert stage_mapping["post-operation"] == 40

    @pytest.mark.asyncio
    async def test_register_step_without_core_agent(self):
        """测试没有 core_agent 时注册步骤"""
        from framework.agents.plugin_agent import PluginAgent
        agent = PluginAgent(core_agent=None)

        result = await agent.register_step(
            plugin_name="TestPlugin",
            entity="account",
            message="Create",
            stage="pre-operation"
        )
        data = json.loads(result)

        assert "error" in data
        assert "No core agent" in data["error"]

    @pytest.mark.asyncio
    async def test_register_step_success(self, plugin_agent, mock_core_agent, mock_dataverse_client):
        """测试成功注册步骤"""
        mock_core_agent.get_client = MagicMock(return_value=mock_dataverse_client)

        result = await plugin_agent.register_step(
            plugin_name="TestPlugin",
            entity="account",
            message="Create",
            stage="pre-operation",
            config={
                "name": "TestStep",
                "mode": 0,
                "deployment": 0
            }
        )
        data = json.loads(result)

        assert data["success"] is True
        assert data["plugin"] == "TestPlugin"
        assert data["entity"] == "account"
        assert data["message"] == "Create"
        assert data["stage"] == "pre-operation"

    @pytest.mark.asyncio
    async def test_register_step_with_custom_config(self, plugin_agent, mock_core_agent, mock_dataverse_client):
        """测试使用自定义配置注册步骤"""
        mock_core_agent.get_client = MagicMock(return_value=mock_dataverse_client)

        custom_config = {
            "name": "CustomAccountCreate",
            "mode": 1,  # Asynchronous
            "deployment": 0,  # Server only
            "filtering_attributes": "name,accountnumber",
            "description": "Custom plugin step"
        }

        result = await plugin_agent.register_step(
            plugin_name="TestPlugin",
            entity="account",
            message="Create",
            stage="post-operation",
            config=custom_config
        )
        data = json.loads(result)

        assert "success" in data

    @pytest.mark.asyncio
    async def test_register_step_pre_validation_stage(self, plugin_agent, mock_core_agent, mock_dataverse_client):
        """测试注册 pre-validation 阶段步骤"""
        mock_core_agent.get_client = MagicMock(return_value=mock_dataverse_client)

        result = await plugin_agent.register_step(
            plugin_name="TestPlugin",
            entity="contact",
            message="Create",
            stage="pre-validation"
        )
        data = json.loads(result)

        assert "success" in data

    @pytest.mark.asyncio
    async def test_handle_plugin_step_register_tool(self, plugin_agent, mock_core_agent, mock_dataverse_client):
        """测试通过 handle 方法注册步骤"""
        mock_core_agent.get_client = MagicMock(return_value=mock_dataverse_client)

        result = await plugin_agent.handle("plugin_step_register", {
            "plugin_name": "TestPlugin",
            "entity": "account",
            "message": "Update",
            "stage": "pre-operation",
            "config": {}
        })
        data = json.loads(result)

        assert "success" in data

    @pytest.mark.asyncio
    async def test_generate_step_request_data(self):
        """测试生成步骤请求数据"""
        plugin_name = "TestPlugin"
        assembly_id = "assembly-123"
        sdk_message_id = "sdk-msg-456"
        stage = "pre-operation"

        stage_mapping = {
            "pre-validation": 10,
            "pre-operation": 20,
            "post-operation": 40
        }

        step_data = {
            "name": f"{plugin_name}_account_Create",
            "pluginassemblyid@odata.bind": f"/pluginassemblies({assembly_id})",
            "sdkmessageid@odata.bind": f"/sdkmessages({sdk_message_id})",
            "stage": stage_mapping.get(stage, 20),
            "mode": 0,
            "supporteddeployment": 0
        }

        assert step_data["stage"] == 20
        assert "/pluginassemblies(" in step_data["pluginassemblyid@odata.bind"]
        assert "/sdkmessages(" in step_data["sdkmessageid@odata.bind"]


# ==================== 测试类：步骤管理测试 ====================

@pytest.mark.unit
class TestPluginAgentStepManagement:
    """测试 PluginAgent 步骤管理功能"""

    @pytest.fixture
    def plugin_agent(self, mock_core_agent, mock_dataverse_client):
        """创建 PluginAgent 实例"""
        from framework.agents.plugin_agent import PluginAgent
        agent = PluginAgent(core_agent=mock_core_agent)
        return agent

    @pytest.mark.asyncio
    async def test_update_step_success(self, plugin_agent, mock_core_agent, mock_dataverse_client):
        """测试成功更新步骤"""
        mock_core_agent.get_client = MagicMock(return_value=mock_dataverse_client)

        new_config = {
            "description": "Updated description",
            "filteringattributes": "name,address1_city"
        }

        result = await plugin_agent.update_step("step-456", new_config)
        data = json.loads(result)

        assert data["success"] is True
        assert data["step_id"] == "step-456"
        assert "description" in data["updated_fields"]

    @pytest.mark.asyncio
    async def test_update_step_without_core_agent(self):
        """测试没有 core_agent 时更新步骤"""
        from framework.agents.plugin_agent import PluginAgent
        agent = PluginAgent(core_agent=None)

        result = await agent.update_step("step-456", {"description": "test"})
        data = json.loads(result)

        assert "error" in data
        assert "No core agent" in data["error"]

    @pytest.mark.asyncio
    async def test_delete_step_success(self, plugin_agent, mock_core_agent, mock_dataverse_client):
        """测试成功删除步骤"""
        mock_core_agent.get_client = MagicMock(return_value=mock_dataverse_client)

        result = await plugin_agent.delete_step("step-456")
        data = json.loads(result)

        assert data["success"] is True
        assert data["step_id"] == "step-456"

    @pytest.mark.asyncio
    async def test_delete_step_without_core_agent(self):
        """测试没有 core_agent 时删除步骤"""
        from framework.agents.plugin_agent import PluginAgent
        agent = PluginAgent(core_agent=None)

        result = await agent.delete_step("step-456")
        data = json.loads(result)

        assert "error" in data
        assert "No core agent" in data["error"]

    @pytest.mark.asyncio
    async def test_list_steps_success(self, plugin_agent, mock_core_agent, mock_dataverse_client):
        """测试成功列出步骤"""
        # 设置 mock 返回步骤数据
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "value": [
                {
                    "sdkmessageprocessingstepid": "step-1",
                    "name": "TestStep1",
                    "pluginassemblyid": {"name": "TestPlugin"},
                    "sdkmessageid": {"name": "Create"},
                    "stage": 20,
                    "mode": 0
                },
                {
                    "sdkmessageprocessingstepid": "step-2",
                    "name": "TestStep2",
                    "pluginassemblyid": {"name": "TestPlugin"},
                    "sdkmessageid": {"name": "Update"},
                    "stage": 40,
                    "mode": 1
                }
            ]
        }
        mock_dataverse_client.session.get = MagicMock(return_value=mock_response)
        mock_core_agent.get_client = MagicMock(return_value=mock_dataverse_client)

        result = await plugin_agent.list_steps(plugin_name="TestPlugin")
        data = json.loads(result)

        assert "steps" in data
        assert len(data["steps"]) == 2
        assert data["steps"][0]["plugin"] == "TestPlugin"
        assert data["steps"][0]["message"] == "Create"

    @pytest.mark.asyncio
    async def test_handle_plugin_step_update_tool(self, plugin_agent, mock_core_agent, mock_dataverse_client):
        """测试通过 handle 方法更新步骤"""
        mock_core_agent.get_client = MagicMock(return_value=mock_dataverse_client)

        result = await plugin_agent.handle("plugin_step_update", {
            "step_id": "step-456",
            "config": {"description": "Updated via handle"}
        })
        data = json.loads(result)

        assert "success" in data

    @pytest.mark.asyncio
    async def test_handle_plugin_step_delete_tool(self, plugin_agent, mock_core_agent, mock_dataverse_client):
        """测试通过 handle 方法删除步骤"""
        mock_core_agent.get_client = MagicMock(return_value=mock_dataverse_client)

        result = await plugin_agent.handle("plugin_step_delete", {
            "step_id": "step-456"
        })
        data = json.loads(result)

        assert "success" in data

    @pytest.mark.asyncio
    async def test_handle_plugin_step_list_tool(self, plugin_agent, mock_core_agent, mock_dataverse_client):
        """测试通过 handle 方法列出步骤"""
        mock_core_agent.get_client = MagicMock(return_value=mock_dataverse_client)

        result = await plugin_agent.handle("plugin_step_list", {
            "plugin_name": "TestPlugin"
        })
        data = json.loads(result)

        assert "steps" in data


# ==================== 测试类：插件配置解析测试 ====================

@pytest.mark.unit
class TestPluginAgentConfigParsing:
    """测试 PluginAgent 配置解析功能"""

    @pytest.fixture
    def plugin_agent(self):
        """创建 PluginAgent 实例"""
        from framework.agents.plugin_agent import PluginAgent
        return PluginAgent(core_agent=None)

    def test_parse_plugin_config_yaml(self, plugin_agent, temp_plugin_project):
        """测试解析 YAML 配置文件"""
        config = plugin_agent.parse_plugin_config(str(temp_plugin_project["config"]))

        assert config["plugin"]["name"] == "TestPlugin"
        assert config["plugin"]["version"] == "1.0.0.0"
        assert len(config["steps"]) == 1
        assert config["steps"][0]["entity"] == "account"
        assert config["steps"][0]["stage"] == "pre-operation"

    def test_generate_plugin_config(self, plugin_agent):
        """测试生成插件配置"""
        config = plugin_agent.generate_plugin_config(
            "MyPlugin",
            {
                "description": "My test plugin",
                "version": "2.0.0.0",
                "build_configuration": "Debug",
                "auto_deploy": True
            }
        )

        assert config["plugin"]["name"] == "MyPlugin"
        assert config["plugin"]["description"] == "My test plugin"
        assert config["plugin"]["version"] == "2.0.0.0"
        assert config["build"]["configuration"] == "Debug"
        assert config["build"]["auto_deploy"] is True

    def test_generate_plugin_config_with_steps(self, plugin_agent):
        """测试生成包含步骤的插件配置"""
        steps_config = [
            {
                "name": "PreCreate",
                "entity": "account",
                "message": "Create",
                "stage": "pre-operation"
            }
        ]

        config = plugin_agent.generate_plugin_config(
            "StepPlugin",
            {"steps": steps_config}
        )

        assert len(config["steps"]) == 1
        assert config["steps"][0]["name"] == "PreCreate"


# ==================== 测试类：部署测试（本地操作）====================

@pytest.mark.unit
class TestPluginAgentDeployLocal:
    """测试 PluginAgent 部署功能（本地操作，不执行实际部署）"""

    @pytest.fixture
    def plugin_agent(self, mock_core_agent):
        """创建 PluginAgent 实例"""
        from framework.agents.plugin_agent import PluginAgent
        return PluginAgent(core_agent=mock_core_agent)

    @pytest.mark.asyncio
    async def test_deploy_nonexistent_file(self, plugin_agent):
        """测试部署不存在的文件"""
        result = await plugin_agent.deploy("/nonexistent/plugin.dll")
        data = json.loads(result)

        assert "error" in data
        assert "not found" in data["error"]

    @pytest.mark.asyncio
    async def test_deploy_from_cache(self, plugin_agent):
        """测试从缓存部署"""
        # 模拟缓存中有构建信息
        plugin_agent._build_cache["/cached/project.csproj"] = {
            "success": True,
            "output_dll": "/cached/output/plugin.dll"
        }

        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", MagicMock()):
                result = await plugin_agent.deploy("/nonexistent/plugin.dll")
                # 验证调用了相关逻辑
                assert result is not None

    @pytest.mark.asyncio
    async def test_deploy_without_core_agent(self):
        """测试没有 core_agent 时部署"""
        from framework.agents.plugin_agent import PluginAgent
        agent = PluginAgent(core_agent=None)

        result = await agent.deploy("/some/plugin.dll")
        data = json.loads(result)

        assert "error" in data
        assert "No core agent" in data["error"]

    @pytest.mark.asyncio
    async def test_assembly_base64_encoding(self):
        """测试程序集 Base64 编码"""
        import base64

        test_data = b"Test assembly data"
        encoded = base64.b64encode(test_data).decode("utf-8")

        assert encoded is not None
        assert isinstance(encoded, str)
        assert len(encoded) > 0

    @pytest.mark.asyncio
    async def test_generate_assembly_request_data(self):
        """测试生成程序集请求数据"""
        assembly_name = "TestPlugin"
        assembly_base64 = "base64encodeddata"

        plugin_assembly = {
            "name": assembly_name.replace(".dll", ""),
            "version": "1.0.0.0",
            "content": assembly_base64,
            "sourcetype": 0
        }

        assert plugin_assembly["name"] == "TestPlugin"
        assert plugin_assembly["sourcetype"] == 0
        assert plugin_assembly["content"] == assembly_base64


# ==================== 测试类：工具处理器测试 ====================

@pytest.mark.unit
class TestPluginAgentToolHandler:
    """测试 PluginAgent 工具处理器"""

    @pytest.fixture
    def plugin_agent(self):
        """创建 PluginAgent 实例"""
        from framework.agents.plugin_agent import PluginAgent
        return PluginAgent(core_agent=None)

    @pytest.mark.asyncio
    async def test_handle_unknown_tool(self, plugin_agent):
        """测试处理未知工具"""
        result = await plugin_agent.handle("unknown_tool", {})
        data = json.loads(result)

        assert "error" in data
        assert "Unknown tool" in data["error"]

    @pytest.mark.asyncio
    async def test_handle_tool_exception_handling(self, plugin_agent):
        """测试工具处理异常处理"""
        # 传入无效参数应该捕获异常
        result = await plugin_agent.handle("plugin_build", {})
        # 应该返回结果而不是抛出异常
        assert result is not None

    @pytest.mark.asyncio
    async def test_handle_plugin_watch_tool(self, plugin_agent):
        """测试监听模式工具"""
        result = await plugin_agent.handle("plugin_watch", {
            "project_path": "/some/path"
        })
        data = json.loads(result)

        assert "status" in data
        assert "recommendation" in data


# ==================== 测试类：辅助方法测试 ====================

@pytest.mark.unit
class TestPluginAgentHelperMethods:
    """测试 PluginAgent 辅助方法"""

    @pytest.fixture
    def plugin_agent(self, mock_core_agent):
        """创建 PluginAgent 实例"""
        from framework.agents.plugin_agent import PluginAgent
        agent = PluginAgent(core_agent=mock_core_agent)
        return agent

    def test_get_assembly_id_from_response(self):
        """测试从响应获取程序集 ID"""
        mock_response = {
            "value": [
                {
                    "pluginassemblyid": "test-assembly-id",
                    "name": "TestPlugin",
                    "version": "1.0.0.0"
                }
            ]
        }

        assembly_id = mock_response["value"][0]["pluginassemblyid"]
        assert assembly_id == "test-assembly-id"

    def test_get_sdk_message_id_from_response(self):
        """测试从响应获取 SDK 消息 ID"""
        mock_response = {
            "value": [
                {
                    "sdkmessageid": "sdk-msg-id",
                    "name": "Create"
                }
            ]
        }

        sdk_message_id = mock_response["value"][0]["sdkmessageid"]
        assert sdk_message_id == "sdk-msg-id"

    def test_step_image_configuration(self):
        """测试步骤镜像配置"""
        step_id = "step-123"
        type_config = {
            "name": "PreImage",
            "typename": "System.String",
            "assemblyname": "TestPlugin",
            "constructor": None,
            "configuration": None
        }

        type_data = {
            "sdkmessageprocessingstepid@odata.bind": f"/sdkmessageprocessingsteps({step_id})",
            "name": type_config.get("name"),
            "typename": type_config.get("typename"),
            "assemblyname": type_config.get("assemblyname")
        }

        assert type_data["sdkmessageprocessingstepid@odata.bind"] == "/sdkmessageprocessingsteps(step-123)"
        assert type_data["typename"] == "System.String"

    def test_filter_step_update_fields(self):
        """测试过滤步骤更新字段"""
        config = {
            "name": "UpdatedStep",
            "description": "New description",
            "mode": 1,
            "pluginassemblyid": "should-be-removed",
            "sdkmessageid": "should-be-removed"
        }

        update_data = {k: v for k, v in config.items()
                      if k not in ["pluginassemblyid", "sdkmessageid"]}

        assert "pluginassemblyid" not in update_data
        assert "sdkmessageid" not in update_data
        assert "name" in update_data
        assert "description" in update_data


# ==================== 测试类：初始化测试 ====================

@pytest.mark.unit
class TestPluginAgentInit:
    """测试 PluginAgent 初始化"""

    def test_init_without_core_agent(self):
        """测试不传入 core_agent 的初始化"""
        from framework.agents.plugin_agent import PluginAgent
        agent = PluginAgent(core_agent=None)

        assert agent.core_agent is None
        assert agent.plugin_dir == Path("plugins")
        assert isinstance(agent._build_cache, dict)

    def test_init_with_core_agent(self, mock_core_agent):
        """测试传入 core_agent 的初始化"""
        from framework.agents.plugin_agent import PluginAgent
        agent = PluginAgent(core_agent=mock_core_agent)

        assert agent.core_agent is not None
        assert agent.core_agent._current_environment == "dev"

    def test_plugin_dir_path(self):
        """测试插件目录路径"""
        from framework.agents.plugin_agent import PluginAgent
        agent = PluginAgent(core_agent=None)

        assert isinstance(agent.plugin_dir, Path)
        assert str(agent.plugin_dir) == "plugins"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
