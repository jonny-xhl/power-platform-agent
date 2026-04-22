"""
Power Platform Agent - 插件代理
处理.NET插件的构建、部署和Step注册
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

# 设置日志
logger = logging.getLogger(__name__)


class PluginAgent:
    """插件代理 - 处理Power Platform插件管理"""

    def __init__(self, core_agent=None):
        """
        初始化插件代理

        Args:
            core_agent: 核心代理实例
        """
        self.core_agent = core_agent
        self.plugin_dir = Path("plugins")
        self._build_cache = {}

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
            if tool_name == "plugin_build":
                return await self.build(
                    arguments.get("project_path"),
                    arguments.get("configuration", "Release")
                )

            elif tool_name == "plugin_deploy":
                return await self.deploy(
                    arguments.get("assembly_path"),
                    arguments.get("environment")
                )

            elif tool_name == "plugin_step_register":
                return await self.register_step(
                    arguments.get("plugin_name"),
                    arguments.get("entity"),
                    arguments.get("message"),
                    arguments.get("stage"),
                    arguments.get("config", {})
                )

            elif tool_name == "plugin_step_update":
                return await self.update_step(
                    arguments.get("step_id"),
                    arguments.get("config")
                )

            elif tool_name == "plugin_step_list":
                return await self.list_steps(
                    arguments.get("plugin_name"),
                    arguments.get("entity")
                )

            elif tool_name == "plugin_step_delete":
                return await self.delete_step(
                    arguments.get("step_id")
                )

            elif tool_name == "plugin_assembly_list":
                return await self.list_assemblies()

            elif tool_name == "plugin_watch":
                return await self.watch(
                    arguments.get("project_path")
                )

            elif tool_name == "plugin_info":
                return await self.get_info(
                    arguments.get("project_path")
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

    # ==================== 构建插件 ====================

    async def build(
        self,
        project_path: str,
        configuration: str = "Release"
    ) -> str:
        """
        构建插件项目

        Args:
            project_path: 项目路径（.csproj文件或目录）
            configuration: 构建配置（Debug/Release）

        Returns:
            构建结果
        """
        project_path = Path(project_path)

        # 如果是目录，查找.csproj文件
        if project_path.is_dir():
            csproj_files = list(project_path.glob("*.csproj"))
            if not csproj_files:
                return json.dumps({
                    "error": f"No .csproj file found in {project_path}"
                }, indent=2)
            project_file = csproj_files[0]
        else:
            project_file = project_path

        if not project_file.exists():
            return json.dumps({
                "error": f"Project file not found: {project_file}"
            }, indent=2)

        try:
            # 检查dotnet是否可用
            check_dotnet = subprocess.run(
                ["dotnet", "--version"],
                capture_output=True,
                text=True
            )

            if check_dotnet.returncode != 0:
                return json.dumps({
                    "error": "dotnet CLI not found. Please install .NET SDK."
                }, indent=2)

            # 执行构建
            result = subprocess.run(
                [
                    "dotnet", "build",
                    str(project_file),
                    "--configuration", configuration,
                    "--no-restore"
                ],
                capture_output=True,
                text=True,
                cwd=project_file.parent
            )

            # 解析输出
            success = result.returncode == 0

            # 查找生成的DLL
            bin_dir = project_file.parent / "bin" / configuration
            dll_files = list(bin_dir.glob("*.dll")) if bin_dir.exists() else []

            output_dll = None
            for dll in dll_files:
                if not dll.name.startswith("Microsoft.") and not dll.name.startswith("System."):
                    output_dll = str(dll)
                    break

            build_info = {
                "success": success,
                "project": str(project_file),
                "configuration": configuration,
                "output_dll": output_dll,
                "build_output": result.stdout,
                "build_errors": result.stderr if result.stderr else None
            }

            if success:
                # 缓存构建信息
                self._build_cache[str(project_file)] = build_info

            return json.dumps(build_info, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Build failed: {str(e)}"
            }, indent=2)

    # ==================== 部署插件 ====================

    async def deploy(
        self,
        assembly_path: str,
        environment: Optional[str] = None
    ) -> str:
        """
        部署插件程序集

        Args:
            assembly_path: 程序集路径（DLL文件）
            environment: 环境名称

        Returns:
            部署结果
        """
        assembly_path = Path(assembly_path)

        if not assembly_path.exists():
            # 尝试从缓存获取
            for build_info in self._build_cache.values():
                if build_info.get("output_dll"):
                    assembly_path = Path(build_info["output_dll"])
                    break
            else:
                return json.dumps({
                    "error": f"Assembly not found: {assembly_path}"
                }, indent=2)

        try:
            if not self.core_agent:
                return json.dumps({
                    "error": "No core agent available for authentication"
                }, indent=2)

            # 读取程序集
            with open(assembly_path, "rb") as f:
                assembly_data = f.read()

            # 转换为Base64
            import base64
            assembly_base64 = base64.b64encode(assembly_data).decode("utf-8")

            # 获取客户端并部署
            client = self.core_agent.get_client(environment)

            # 使用Plugin Registration API部署
            # 注意：这需要通过Plugin Registration Tool或专用API
            result = await self._deploy_assembly(client, assembly_path.name, assembly_base64)

            return json.dumps({
                "success": True,
                "assembly": assembly_path.name,
                "environment": environment or self.core_agent._current_environment,
                "result": result
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Deploy failed: {str(e)}"
            }, indent=2)

    async def _deploy_assembly(
        self,
        client,
        assembly_name: str,
        assembly_base64: str
    ) -> Dict[str, Any]:
        """部署程序集到Dataverse"""
        # 创建pluginassembly记录
        plugin_assembly = {
            "name": assembly_name.replace(".dll", ""),
            "version": "1.0.0.0",
            "content": assembly_base64,
            "sourcetype": 0  # Database
        }

        # 使用Web API创建
        url = client.get_api_url("pluginassemblies")
        response = client.session.post(url, json=plugin_assembly)
        response.raise_for_status()

        return response.json()

    # ==================== Step注册 ====================

    async def register_step(
        self,
        plugin_name: str,
        entity: str,
        message: str,
        stage: str,
        config: Dict[str, Any] = None
    ) -> str:
        """
        注册插件Step

        Args:
            plugin_name: 插件名称
            entity: 实体名称
            message: 消息名称（如Create, Update, Delete等）
            stage: 阶段（pre-validation, pre-operation, post-operation）
            config: 配置选项

        Returns:
            注册结果
        """
        config = config or {}

        try:
            if not self.core_agent:
                return json.dumps({
                    "error": "No core agent available"
                }, indent=2)

            client = self.core_agent.get_client()

            # 获取插件程序集ID
            assembly_id = await self._get_assembly_id(client, plugin_name)

            if not assembly_id:
                return json.dumps({
                    "error": f"Plugin assembly not found: {plugin_name}"
                }, indent=2)

            # 构建Step配置
            stage_mapping = {
                "pre-validation": 10,
                "pre-operation": 20,
                "post-operation": 40
            }

            sdk_message_id = await self._get_sdk_message_id(client, message, entity)

            step_data = {
                "name": config.get("name", f"{plugin_name}_{entity}_{message}"),
                "pluginassemblyid@odata.bind": f"/pluginassemblies({assembly_id})",
                "sdkmessageid@odata.bind": f"/sdkmessages({sdk_message_id})",
                "stage": stage_mapping.get(stage, 20),
                "mode": config.get("mode", 0),  # Synchronous
                "supporteddeployment": config.get("deployment", 0),  # Server
                "filteringattributes": config.get("filtering_attributes", ""),
                "impersonatinguserid": config.get("impersonate_user"),
                "description": config.get("description", "")
            }

            # 创建Step
            url = client.get_api_url("sdkmessageprocessingsteps")
            response = client.session.post(url, json=step_data)
            response.raise_for_status()

            result = response.json()

            # 注册Step类型（如果需要）
            if config.get("type"):
                await self._register_step_type(
                    client,
                    result["sdkmessageprocessingstepid"],
                    config["type"]
                )

            return json.dumps({
                "success": True,
                "step": result.get("name"),
                "step_id": result.get("sdkmessageprocessingstepid"),
                "plugin": plugin_name,
                "entity": entity,
                "message": message,
                "stage": stage
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Step registration failed: {str(e)}"
            }, indent=2)

    async def _get_assembly_id(self, client, plugin_name: str) -> Optional[str]:
        """获取程序集ID"""
        url = client.get_api_url("pluginassemblies")
        filter_expr = f"name eq '{plugin_name}'"
        response = client.session.get(f"{url}?$filter={filter_expr}")

        if response.status_code == 200:
            data = response.json()
            if data.get("value"):
                return data["value"][0]["pluginassemblyid"]
        return None

    async def _get_sdk_message_id(self, client, message: str, entity: str) -> Optional[str]:
        """获取SDK消息ID"""
        url = client.get_api_url("sdkmessages")
        filter_expr = f"name eq '{message}'"
        response = client.session.get(f"{url}?$filter={filter_expr}")

        if response.status_code == 200:
            data = response.json()
            if data.get("value"):
                return data["value"][0]["sdkmessageid"]
        return None

    async def _register_step_type(
        self,
        client,
        step_id: str,
        type_config: Dict[str, Any]
    ) -> None:
        """注册Step类型"""
        type_data = {
            "sdkmessageprocessingstepid@odata.bind": f"/sdkmessageprocessingsteps({step_id})",
            "name": type_config.get("name"),
            "typename": type_config.get("typename"),
            "assemblyname": type_config.get("assemblyname"),
            "constructor": type_config.get("constructor"),
            "configuration": type_config.get("configuration")
        }

        url = client.get_api_url("sdkmessageprocessingstepimages")
        client.session.post(url, json=type_data)

    # ==================== Step管理 ====================

    async def update_step(
        self,
        step_id: str,
        config: Dict[str, Any]
    ) -> str:
        """
        更新Step配置

        Args:
            step_id: Step ID
            config: 新配置

        Returns:
            更新结果
        """
        try:
            if not self.core_agent:
                return json.dumps({
                    "error": "No core agent available"
                }, indent=2)

            client = self.core_agent.get_client()

            url = client.get_api_url(f"sdkmessageprocessingsteps({step_id})")

            # 移除不允许更新的字段
            update_data = {k: v for k, v in config.items()
                          if k not in ["pluginassemblyid", "sdkmessageid"]}

            response = client.session.patch(url, json=update_data)
            response.raise_for_status()

            return json.dumps({
                "success": True,
                "step_id": step_id,
                "updated_fields": list(update_data.keys())
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": f"Step update failed: {str(e)}"
            }, indent=2)

    async def delete_step(self, step_id: str) -> str:
        """
        删除Step

        Args:
            step_id: Step ID

        Returns:
            删除结果
        """
        try:
            if not self.core_agent:
                return json.dumps({
                    "error": "No core agent available"
                }, indent=2)

            client = self.core_agent.get_client()
            url = client.get_api_url(f"sdkmessageprocessingsteps({step_id})")

            response = client.session.delete(url)
            response.raise_for_status()

            return json.dumps({
                "success": True,
                "step_id": step_id,
                "message": "Step deleted successfully"
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": f"Step deletion failed: {str(e)}"
            }, indent=2)

    async def list_steps(
        self,
        plugin_name: Optional[str] = None,
        entity: Optional[str] = None
    ) -> str:
        """
        列出Steps

        Args:
            plugin_name: 插件名称（可选）
            entity: 实体名称（可选）

        Returns:
            Step列表
        """
        try:
            if not self.core_agent:
                return json.dumps({
                    "error": "No core agent available"
                }, indent=2)

            client = self.core_agent.get_client()

            # 获取Steps
            url = client.get_api_url("sdkmessageprocessingsteps")
            expand = "$expand=pluginassemblyid,sdkmessageid"

            response = client.session.get(f"{url}?{expand}")
            response.raise_for_status()

            steps = response.json().get("value", [])

            # 过滤
            if plugin_name:
                steps = [s for s in steps if s.get("pluginassemblyid", {}).get("name") == plugin_name]

            # 格式化输出
            result_steps = []
            for step in steps:
                result_steps.append({
                    "step_id": step.get("sdkmessageprocessingstepid"),
                    "name": step.get("name"),
                    "plugin": step.get("pluginassemblyid", {}).get("name"),
                    "message": step.get("sdkmessageid", {}).get("name"),
                    "stage": step.get("stage"),
                    "mode": step.get("mode")
                })

            return json.dumps({
                "plugin": plugin_name,
                "entity": entity,
                "steps": result_steps
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to list steps: {str(e)}"
            }, indent=2)

    # ==================== 程序集管理 ====================

    async def list_assemblies(self) -> str:
        """
        列出已部署的程序集

        Returns:
            程序集列表
        """
        try:
            if not self.core_agent:
                return json.dumps({
                    "error": "No core agent available"
                }, indent=2)

            client = self.core_agent.get_client()

            url = client.get_api_url("pluginassemblies")

            response = client.session.get(url)
            response.raise_for_status()

            assemblies = response.json().get("value", [])

            result = []
            for asm in assemblies:
                result.append({
                    "id": asm.get("pluginassemblyid"),
                    "name": asm.get("name"),
                    "version": asm.get("version"),
                    "is_public": asm.get("ispublic"),
                    "is_visible": asm.get("isvisible")
                })

            return json.dumps({
                "assemblies": result
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to list assemblies: {str(e)}"
            }, indent=2)

    # ==================== 监听模式 ====================

    async def watch(self, project_path: str) -> str:
        """
        启动监听模式，自动构建和部署

        Args:
            project_path: 项目路径

        Returns:
            监听状态
        """
        return json.dumps({
            "status": "Watch mode requires background process",
            "recommendation": "Use file system watcher with callback to build/deploy",
            "project_path": project_path
        }, indent=2)

    # ==================== 插件信息 ====================

    async def get_info(self, project_path: str) -> str:
        """
        获取插件项目信息

        Args:
            project_path: 项目路径

        Returns:
            项目信息
        """
        project_path = Path(project_path)

        if project_path.is_dir():
            csproj_files = list(project_path.glob("*.csproj"))
            if not csproj_files:
                return json.dumps({
                    "error": f"No .csproj file found in {project_path}"
                }, indent=2)
            project_file = csproj_files[0]
        else:
            project_file = project_path

        if not project_file.exists():
            return json.dumps({
                "error": f"Project file not found: {project_file}"
            }, indent=2)

        try:
            # 解析.csproj文件
            with open(project_file, "r", encoding="utf-8") as f:
                content = f.read()

            # 提取基本信息
            import xml.etree.ElementTree as ET
            root = ET.fromstring(content)

            # 查找Project元素（带命名空间）
            namespaces = {
                'ms': 'http://schemas.microsoft.com/developer/msbuild/2003'
            }

            info = {
                "project_file": str(project_file),
                "project_name": project_file.stem,
                "target_framework": None,
                "output_type": None,
                "references": [],
                "plugins": []
            }

            # 提取TargetFramework
            for tf in root.findall(".//ms:TargetFramework", namespaces):
                info["target_framework"] = tf.text

            # 提取OutputType
            for ot in root.findall(".//ms:OutputType", namespaces):
                info["output_type"] = ot.text

            # 查找.cs文件（插件类）
            cs_files = list(project_file.parent.glob("**/*.cs"))
            for cs_file in cs_files:
                # 检查是否包含IPlugin接口
                try:
                    with open(cs_file, "r", encoding="utf-8") as f:
                        cs_content = f.read()
                    if "IPlugin" in cs_content and "Execute" in cs_content:
                        info["plugins"].append({
                            "file": cs_file.name,
                            "path": str(cs_file.relative_to(project_file.parent))
                        })
                except:
                    pass

            return json.dumps(info, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to get project info: {str(e)}"
            }, indent=2)

    # ==================== 插件配置 ====================

    def parse_plugin_config(self, config_path: str) -> Dict[str, Any]:
        """
        解析插件配置YAML

        Args:
            config_path: 配置文件路径

        Returns:
            配置字典
        """
        config_file = Path(config_path)

        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def generate_plugin_config(
        self,
        plugin_name: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成插件配置

        Args:
            plugin_name: 插件名称
            config: 配置选项

        Returns:
            配置字典
        """
        return {
            "plugin": {
                "name": plugin_name,
                "description": config.get("description", ""),
                "version": config.get("version", "1.0.0.0")
            },
            "steps": config.get("steps", []),
            "build": {
                "configuration": config.get("build_configuration", "Release"),
                "auto_deploy": config.get("auto_deploy", False),
                "watch_mode": config.get("watch_mode", False)
            }
        }
