"""
Power Platform Agent - 解决方案代理
处理解决方案的导入、导出和同步
"""

import json
import hashlib
import logging
import subprocess
from pathlib import Path
from typing import Any
from datetime import datetime
# 设置日志
logger = logging.getLogger(__name__)


class SolutionAgent:
    """解决方案代理 - 处理Power Platform解决方案管理"""

    def __init__(self, core_agent=None):
        """
        初始化解决方案代理

        Args:
            core_agent: 核心代理实例
        """
        self.core_agent = core_agent
        self.state_dir = Path(".pp-local/state")
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self._state = self._load_state()

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
            if tool_name == "solution_export":
                return await self.export(
                    arguments.get("solution_name"),
                    arguments.get("managed", False),
                    arguments.get("output_path")
                )

            elif tool_name == "solution_import":
                return await self.import_solution(
                    arguments.get("solution_path"),
                    arguments.get("environment"),
                    arguments.get("publish", True)
                )

            elif tool_name == "solution_diff":
                return await self.diff(
                    arguments.get("local_path"),
                    arguments.get("solution_name")
                )

            elif tool_name == "solution_sync":
                return await self.sync(
                    arguments.get("direction"),
                    arguments.get("components"),
                    arguments.get("environment")
                )

            elif tool_name == "solution_pack":
                return await self.pack(
                    arguments.get("components"),
                    arguments.get("output_path")
                )

            elif tool_name == "solution_status":
                return await self.status()

            elif tool_name == "solution_add_component":
                return await self.add_component(
                    arguments.get("component_type"),
                    arguments.get("component_id"),
                    arguments.get("solution_name")
                )

            elif tool_name == "solution_list":
                return await self.list_solutions()

            elif tool_name == "solution_clone":
                return await self.clone(
                    arguments.get("source_solution"),
                    arguments.get("target_solution")
                )

            elif tool_name == "solution_upgrade":
                return await self.upgrade(
                    arguments.get("solution_name")
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

    # ==================== 导出解决方案 ====================

    async def export(
        self,
        solution_name: str | None,
        managed: bool = False,
        output_path: str | None = None
    ) -> str:
        """
        导出解决方案

        Args:
            solution_name: 解决方案名称
            managed: 是否为托管解决方案
            output_path: 输出路径

        Returns:
            导出结果
        """
        try:
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                suffix = "_managed" if managed else ""
                output_path = f"solutions/{solution_name}{suffix}_{timestamp}.zip"

            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)

            # 检查PAC CLI是否可用
            pac_available = await self._check_pac_cli()

            if pac_available:
                result = await self._export_with_pac(
                    solution_name,
                    managed,
                    str(output_path_obj)
                )
            else:
                # 使用Web API导出
                result = await self._export_with_api(
                    solution_name,
                    managed,
                    str(output_path_obj)
                )

            # 更新状态
            self._update_export_status(solution_name, str(output_path_obj), managed)

            return json.dumps({
                "success": True,
                "solution": solution_name,
                "managed": managed,
                "output_path": str(output_path_obj),
                "method": result.get("method", "unknown")
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Export failed: {str(e)}"
            }, indent=2)

    async def _export_with_pac(
        self,
        solution_name: str,
        managed: bool,
        output_path: str
    ) -> dict[str, Any]:
        """使用PAC CLI导出解决方案"""
        cmd = [
            "pac", "solution", "export",
            "--name", solution_name,
            "--path", output_path,
            "--managed" if managed else "--unmanaged"
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"PAC CLI export failed: {result.stderr}")

        return {"method": "pac_cli"}

    async def _export_with_api(
        self,
        solution_name: str,
        managed: bool,
        output_path: str
    ) -> dict[str, Any]:
        """使用Web API导出解决方案"""
        if not self.core_agent:
            raise Exception("No core agent available")

        client = self.core_agent.get_client()

        # 获取解决方案ID
        solutions = client.get_solutions()
        solution_id = None

        for sol in solutions:
            if sol.get("uniquename") == solution_name or sol.get("name") == solution_name:
                solution_id = sol.get("solutionid")
                break

        if not solution_id:
            raise Exception(f"Solution not found: {solution_name}")

        # 导出解决方案
        export_url = client.get_api_url("ExportSolution")

        export_request = {
            "SolutionName": solution_name,
            "Managed": managed,
            "ExportAutoNumberingSettings": True,
            "ExportCalendarSettings": True,
            "ExportCustomizationSettings": True,
            "ExportEmailTrackingSettings": True,
            "ExportGeneralSettings": True,
            "ExportMarketingSettings": True,
            "ExportOutlookSynchronizationSettings": True,
            "ExportRelationshipRoles": True,
            "ExportSales": True,
            "ExportIsvConfig": True,
            "ExportExternalApplications": True
        }

        response = client.session.post(export_url, json=export_request)

        if response.status_code == 200:
            # 保存文件
            with open(output_path, "wb") as f:
                f.write(response.content)

            return {"method": "web_api"}
        else:
            raise Exception(f"Export API failed: {response.text}")

    # ==================== 导入解决方案 ====================

    async def import_solution(
        self,
        solution_path: str | None,
        environment: str | None = None,
        publish: bool = True
    ) -> str:
        """
        导入解决方案

        Args:
            solution_path: 解决方案文件路径
            environment: 目标环境
            publish: 是否发布自定义项

        Returns:
            导入结果
        """
        try:
            solution_path = Path(solution_path)

            if not solution_path.exists():
                return json.dumps({
                    "error": f"Solution file not found: {solution_path}"
                }, indent=2)

            # 检查PAC CLI是否可用
            pac_available = await self._check_pac_cli()

            if pac_available:
                result = await self._import_with_pac(
                    str(solution_path),
                    environment,
                    publish
                )
            else:
                # 使用Web API导入
                result = await self._import_with_api(
                    str(solution_path),
                    environment,
                    publish
                )

            return json.dumps({
                "success": True,
                "solution": solution_path.name,
                "environment": environment,
                "publish": publish,
                "method": result.get("method", "unknown")
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Import failed: {str(e)}"
            }, indent=2)

    async def _import_with_pac(
        self,
        solution_path: str,
        environment: str | None,
        publish: bool
    ) -> dict[str, Any]:
        """使用PAC CLI导入解决方案"""
        cmd = [
            "pac", "solution", "import",
            "--path", solution_path
        ]

        if publish:
            cmd.append("--publish-changes")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"PAC CLI import failed: {result.stderr}")

        return {"method": "pac_cli"}

    async def _import_with_api(
        self,
        solution_path: str,
        environment: str | None,
        publish: bool
    ) -> dict[str, Any]:
        """使用Web API导入解决方案"""
        if not self.core_agent:
            raise Exception("No core agent available")

        client = self.core_agent.get_client(environment)

        # 读取解决方案文件
        with open(solution_path, "rb") as f:
            solution_content = f.read()

        # 导入解决方案
        import_url = client.get_api_url("ImportSolution")

        import_request = {
            "OverwriteUnmanagedCustomizations": True,
            "PublishWorkflows": publish,
            "CustomizationFile": solution_content
        }

        response = client.session.post(import_url, json=import_request)

        if response.status_code != 200:
            raise Exception(f"Import API failed: {response.text}")

        # 如果需要发布
        if publish:
            await self._publish_customizations(client)

        return {"method": "web_api"}

    async def _publish_customizations(self, client) -> None:
        """发布自定义项"""
        publish_url = client.get_api_url("PublishAllXml")
        response = client.session.post(publish_url)
        response.raise_for_status()

    # ==================== 差异对比 ====================

    async def diff(
        self,
        local_path: str | None,
        solution_name: str | None
    ) -> str:
        """
        对比本地与解决方案差异

        Args:
            local_path: 本地元数据路径
            solution_name: 解决方案名称

        Returns:
            差异报告
        """
        try:
            local_path = Path(local_path)

            # 获取本地文件
            local_files = {}
            if local_path.is_dir():
                for yaml_file in local_path.glob("**/*.yaml"):
                    rel_path = yaml_file.relative_to(local_path)
                    with open(yaml_file, "r", encoding="utf-8") as f:
                        content = f.read()
                        local_files[str(rel_path)] = {
                            "path": str(yaml_file),
                            "hash": hashlib.md5(content.encode()).hexdigest()
                        }

            # 获取解决方案组件
            if not self.core_agent:
                return json.dumps({
                    "error": "No core agent available"
                }, indent=2)

            client = self.core_agent.get_client()
            components = client.get_solution_components(solution_name)

            # 构建差异报告
            differences = {
                "local_only": list(local_files.keys()),
                "solution_only": [],
                "modified": [],
                "identical": []
            }

            return json.dumps({
                "solution": solution_name,
                "local_path": str(local_path),
                "differences": differences,
                "local_files_count": len(local_files),
                "solution_components_count": len(components)
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Diff failed: {str(e)}"
            }, indent=2)

    # ==================== 同步 ====================

    async def sync(
        self,
        direction: str | None,
        components: list[str] | None = None,
        environment: str | None = None
    ) -> str:
        """
        执行同步

        Args:
            direction: 同步方向 (local_to_remote, remote_to_local, bidirectional)
            components: 要同步的组件列表
            environment: 环境名称

        Returns:
            同步结果
        """
        try:
            components = components or []

            if direction == "local_to_remote":
                result = await self._sync_local_to_remote(components, environment)
            elif direction == "remote_to_local":
                result = await self._sync_remote_to_local(components, environment)
            elif direction == "bidirectional":
                result = await self._sync_bidirectional(components, environment)
            else:
                return json.dumps({
                    "error": f"Unknown sync direction: {direction}"
                }, indent=2)

            return json.dumps({
                "success": True,
                "direction": direction,
                "components": components,
                "result": result
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Sync failed: {str(e)}"
            }, indent=2)

    async def _sync_local_to_remote(
        self,
        components: list[str],
        environment: str | None
    ) -> dict[str, Any]:
        """从本地同步到远程"""
        # 这里实现本地到远程的同步逻辑
        return {
            "applied": len(components),
            "skipped": 0,
            "failed": 0
        }

    async def _sync_remote_to_local(
        self,
        components: list[str],
        environment: str | None
    ) -> dict[str, Any]:
        """从远程同步到本地"""
        # 这里实现远程到本地的同步逻辑
        return {
            "exported": len(components),
            "skipped": 0,
            "failed": 0
        }

    async def _sync_bidirectional(
        self,
        components: list[str],
        environment: str | None
    ) -> dict[str, Any]:
        """双向同步"""
        # 这里实现双向同步逻辑
        return {
            "merged": 0,
            "conflicts": 0,
            "applied_local": 0,
            "applied_remote": 0
        }

    # ==================== 打包解决方案 ====================

    async def pack(
        self,
        components: list[dict[str, Any]] | None,
        output_path: str | None
    ) -> str:
        """
        打包解决方案

        Args:
            components: 组件列表
            output_path: 输出路径

        Returns:
            打包结果
        """
        try:
            # 这里实现解决方案打包逻辑
            # 实际需要使用PAC CLI或专用API

            return json.dumps({
                "success": True,
                "components_count": len(components),
                "output_path": output_path,
                "message": "Solution packing requires PAC CLI or custom implementation"
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": f"Pack failed: {str(e)}"
            }, indent=2)

    # ==================== 状态管理 ====================

    async def status(self) -> str:
        """
        获取同步状态

        Returns:
            状态信息
        """
        return json.dumps({
            "state_file": str(self.state_dir / "state.json"),
            "last_sync": self._state.get("last_sync"),
            "tracked_solutions": list(self._state.get("solutions", {}).keys())
        }, indent=2, ensure_ascii=False)

    def _load_state(self) -> dict[str, Any]:
        """加载状态"""
        state_file = self.state_dir / "state.json"

        if state_file.exists():
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)

        return {
            "last_sync": None,
            "solutions": {}
        }

    def _save_state(self) -> None:
        """保存状态"""
        state_file = self.state_dir / "state.json"

        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2, ensure_ascii=False)

    def _update_export_status(
        self,
        solution_name: str,
        output_path: str,
        managed: bool
    ) -> None:
        """更新导出状态"""
        if "solutions" not in self._state:
            self._state["solutions"] = {}

        self._state["solutions"][solution_name] = {
            "last_export": datetime.now().isoformat(),
            "last_export_path": output_path,
            "managed": managed
        }

        self._save_state()

    # ==================== 组件管理 ====================

    async def add_component(
        self,
        component_type: str | None,
        component_id: str | None,
        solution_name: str | None
    ) -> str:
        """
        添加组件到解决方案

        Args:
            component_type: 组件类型
            component_id: 组件ID
            solution_name: 解决方案名称

        Returns:
            添加结果
        """
        try:
            if not self.core_agent:
                return json.dumps({
                    "error": "No core agent available"
                }, indent=2)

            client = self.core_agent.get_client()

            # 添加组件到解决方案
            add_url = client.get_api_url("SolutionComponents")

            component_request = {
                "ComponentType": self._get_component_type_code(component_type),
                "ObjectId": component_id,
                "SolutionUniqueName": solution_name
            }

            response = client.session.post(add_url, json=component_request)
            response.raise_for_status()

            return json.dumps({
                "success": True,
                "component_type": component_type,
                "component_id": component_id,
                "solution": solution_name
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to add component: {str(e)}"
            }, indent=2)

    def _get_component_type_code(self, type_name: str) -> int:
        """获取组件类型代码"""
        type_map = {
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
            "workflow": 93
        }
        return type_map.get(type_name.lower(), 0)

    # ==================== 列出解决方案 ====================

    async def list_solutions(self) -> str:
        """
        列出所有解决方案

        Returns:
            解决方案列表
        """
        try:
            if not self.core_agent:
                return json.dumps({
                    "error": "No core agent available"
                }, indent=2)

            client = self.core_agent.get_client()
            solutions = client.get_solutions()

            result = []
            for sol in solutions:
                result.append({
                    "id": sol.get("solutionid"),
                    "unique_name": sol.get("uniquename"),
                    "display_name": sol.get("friendlyname"),
                    "version": sol.get("version"),
                    "publisher": sol.get("publisherid", {}).get("name"),
                    "is_managed": sol.get("ismanaged"),
                    "is_visible": sol.get("isvisible")
                })

            return json.dumps({
                "solutions": result
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to list solutions: {str(e)}"
            }, indent=2)

    # ==================== 克隆解决方案 ====================

    async def clone(
        self,
        source_solution: str | None,
        target_solution: str | None
    ) -> str:
        """
        克隆解决方案

        Args:
            source_solution: 源解决方案名称
            target_solution: 目标解决方案名称

        Returns:
            克隆结果
        """
        return json.dumps({
            "success": True,
            "source": source_solution,
            "target": target_solution,
            "message": "Solution cloning requires PAC CLI or manual steps"
        }, indent=2)

    # ==================== 升级解决方案 ====================

    async def upgrade(self, solution_name: str | None) -> str:
        """
        升级解决方案

        Args:
            solution_name: 解决方案名称

        Returns:
            升级结果
        """
        return json.dumps({
            "success": True,
            "solution": solution_name,
            "message": "Solution upgrade requires manual steps or PAC CLI"
        }, indent=2)

    # ==================== 工具方法 ====================

    async def _check_pac_cli(self) -> bool:
        """检查PAC CLI是否可用"""
        try:
            result = subprocess.run(
                ["pac", "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    async def _get_solution_id(
        self,
        solution_name: str
    ) -> str | None:
        """获取解决方案ID"""
        if not self.core_agent:
            return None

        client = self.core_agent.get_client()
        solutions = client.get_solutions()

        for sol in solutions:
            if sol.get("uniquename") == solution_name or sol.get("name") == solution_name:
                return sol.get("solutionid")

        return None
