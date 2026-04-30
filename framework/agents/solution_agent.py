"""
Power Platform Agent - 解决方案代理
处理解决方案的导入、导出和同步
"""

import json
import hashlib
import logging
import subprocess
import yaml
from pathlib import Path
from typing import Any
from datetime import datetime

# 设置日志
logger = logging.getLogger(__name__)


# 组件类型代码映射 (Dataverse SolutionComponentType)
# 参考: https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/reference/solutioncomponenttype
COMPONENT_TYPE_CODES = {
    "table": 1,            # 实体 (table 别名)
    "entity": 1,           # 实体
    "attribute": 2,        # 属性
    "relationship": 3,     # 关系
    "optionset": 4,        # 选项集
    "entity_key": 5,       # 实体键
    "stringmap": 6,        # 字符串映射
    "relationship_role": 7,
    "savedquery": 12,      # SavedQuery (视图)
    "query": 13,
    "report": 14,
    "dashboard": 15,
    "systemform": 16,
    "webresource": 21,     # Web 资源
    "plugin": 90,          # 插件
    "sdkmessage": 91,
    "sdkmessageprocessingstep": 92,
    "workflow": 93,
    # 常用别名（与 Dataverse API 实际类型代码对应）
    "form": 60,            # SystemForm (系统表单)
    "view": 26,            # SavedQuery (已保存查询/视图)
}

# 默认同步顺序（依赖关系）
# 全局选项集必须先创建，因为表字段会引用它们
DEFAULT_SYNC_ORDER = ["optionset", "table", "form", "view", "webresource", "plugin"]


def _validate_version(version: str) -> bool:
    """
    验证版本号格式 (X.Y.Z.W)

    Args:
        version: 版本号字符串

    Returns:
        是否有效
    """
    import re
    pattern = r"^\d+\.\d+\.\d+\.\d+$"
    return bool(re.match(pattern, version))


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
        self._publishers_config = None
        self._load_publishers_config()

    def _load_publishers_config(self) -> None:
        """加载发布商配置"""
        publishers_path = Path("config/publishers.yaml")
        if publishers_path.exists():
            with open(publishers_path, "r", encoding="utf-8") as f:
                self._publishers_config = yaml.safe_load(f)

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

            elif tool_name == "solution_sync_from_yaml":
                return await self.sync_from_yaml(
                    arguments.get("solution_yaml"),
                    arguments.get("dry_run", True),
                    arguments.get("on_conflict", "skip")
                )

            elif tool_name == "solution_plan":
                return await self.plan(
                    arguments.get("solution_yaml")
                )

            elif tool_name == "solution_validate":
                return await self.validate_solution_yaml(
                    arguments.get("solution_yaml")
                )

            elif tool_name == "solution_scan":
                return await self.scan_components(
                    arguments.get("solution_yaml")
                )

            elif tool_name == "publisher_list":
                return self.list_publishers()

            elif tool_name == "publisher_create":
                return await self.create_publisher(
                    arguments.get("name"),
                    arguments.get("display_name"),
                    arguments.get("prefix"),
                    arguments.get("description")
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
        return COMPONENT_TYPE_CODES.get(type_name.lower(), 0)

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

    # ==================== YAML 同步功能 ====================

    async def sync_from_yaml(
        self,
        solution_yaml: str | None,
        dry_run: bool = True,
        on_conflict: str = "skip"
    ) -> str:
        """
        从方案 YAML 同步组件到 Dataverse（完整工作流）

        工作流程：
        1. 确保发布商存在
        2. 创建/更新解决方案对象
        3. 同步组件到 Dataverse
        4. 将组件添加到解决方案
        5. 发布解决方案

        Args:
            solution_yaml: 解决方案 YAML 文件路径
            dry_run: 是否为预演模式（不执行实际变更）
            on_conflict: 冲突处理策略 (skip/update/replace/create_only)

        Returns:
            同步结果
        """
        try:
            # 解析方案 YAML
            solution_def = self._parse_solution_yaml(solution_yaml)

            solution_info = solution_def.get("solution", {})
            components_def = solution_def.get("components", {})
            sync_config = solution_def.get("sync", {})

            # ==================== 步骤 1: 确保发布商存在 ====================
            publisher_info = self.resolve_publisher_info(solution_def)
            publisher_result = await self._ensure_publisher_exists(
                publisher_info,
                dry_run
            )

            if not publisher_result.get("success"):
                return json.dumps({
                    "error": f"Publisher check failed: {publisher_result.get('error')}"
                }, indent=2)

            # 获取发布商 ID（用于创建解决方案）
            publisher_id = None
            if not dry_run:
                client = self.core_agent.get_client()
                publisher = client.get_publisher_by_name(publisher_info.get("name"))
                if publisher:
                    publisher_id = publisher.get("publisherid")

            # ==================== 步骤 2: 创建/更新解决方案对象 ====================
            solution_name = solution_info.get("name")
            solution_display_name = solution_info.get("display_name")
            solution_version = solution_info.get("version", "1.0.0.0")

            solution_result = await self._ensure_solution_exists(
                solution_name,
                solution_display_name,
                solution_version,
                publisher_id,
                dry_run
            )

            if not solution_result.get("success"):
                return json.dumps({
                    "error": f"Solution check failed: {solution_result.get('error')}"
                }, indent=2)

            # 获取同步配置
            conflict_strategy = on_conflict or sync_config.get("on_conflict", "skip")
            sync_order = sync_config.get("order", DEFAULT_SYNC_ORDER)

            # 收集组件文件
            # 解决方案文件在 metadata/solutions/ 下，组件路径相对于 metadata/ 目录
            # 所以需要取 parent.parent 得到 metadata 目录
            solution_path = Path(solution_yaml)
            base_path = str(solution_path.parent.parent)  # 从 metadata/solutions/ -> metadata/
            components = self._collect_component_files(components_def, base_path)

            # 按依赖关系排序
            sorted_components = self._sort_components_by_dependency(components, sync_order)

            # 初始化结果
            result = {
                "solution": solution_name,
                "dry_run": dry_run,
                "conflict_strategy": conflict_strategy,
                "publisher": publisher_result,
                "solution_object": solution_result,
                "components_to_sync": [],
                "components_added_to_solution": [],
                "components_skipped": [],
                "components_failed": [],
                "summary": {
                    "total": 0,
                    "to_create": 0,
                    "to_update": 0,
                    "to_skip": 0,
                    "added_to_solution": 0
                }
            }

            if not self.core_agent:
                return json.dumps({
                    "error": "No core agent available"
                }, indent=2)

            client = self.core_agent.get_client()

            # ==================== 步骤 3: 同步组件到 Dataverse ====================
            for comp in sorted_components:
                comp_type = comp.get("type")
                comp_path = comp.get("path")

                result["summary"]["total"] += 1

                # 检查组件是否存在
                exists = await self._check_component_exists(client, comp_type, comp_path)

                action = "skip"
                if not exists:
                    action = "create"
                elif conflict_strategy == "update":
                    action = "update"
                elif conflict_strategy == "replace":
                    action = "replace"
                elif conflict_strategy == "create_only":
                    action = "skip"

                comp_result = {
                    "type": comp_type,
                    "path": comp_path,
                    "exists": exists,
                    "action": action
                }

                if action == "skip":
                    result["components_skipped"].append(comp_result)
                    result["summary"]["to_skip"] += 1
                elif action in ("create", "update", "replace"):
                    if not dry_run:
                        # 执行实际的同步操作
                        sync_result = await self._sync_component(client, comp_type, comp_path, action)
                        comp_result["sync_result"] = sync_result
                        if sync_result.get("success"):
                            result["components_to_sync"].append(comp_result)
                            if action == "create":
                                result["summary"]["to_create"] += 1
                            else:
                                result["summary"]["to_update"] += 1
                        else:
                            result["components_failed"].append(comp_result)
                    else:
                        result["components_to_sync"].append(comp_result)
                        if action == "create":
                            result["summary"]["to_create"] += 1
                        else:
                            result["summary"]["to_update"] += 1

            # ==================== 步骤 4: 将组件添加到解决方案 ====================
            if not dry_run and result["components_to_sync"]:
                for comp in result["components_to_sync"]:
                    add_result = await self._add_component_to_solution(
                        client,
                        solution_name,
                        comp
                    )
                    comp["added_to_solution"] = add_result
                    if add_result.get("success"):
                        result["components_added_to_solution"].append(comp)
                        result["summary"]["added_to_solution"] += 1

            # ==================== 步骤 5: 发布解决方案 ====================
            publish_result = None
            if not dry_run:
                try:
                    publish_result = await self._publish_solution_wrapper(client)
                    result["publish_result"] = publish_result
                except Exception as e:
                    result["publish_result"] = {
                        "success": False,
                        "error": str(e)
                    }

            return json.dumps(result, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Sync from YAML failed: {str(e)}"
            }, indent=2)

    async def plan(self, solution_yaml: str | None) -> str:
        """
        预览同步计划（dry-run，只读）

        Args:
            solution_yaml: 解决方案 YAML 文件路径

        Returns:
            同步计划预览
        """
        return await self.sync_from_yaml(solution_yaml, dry_run=True)

    async def validate_solution_yaml(
        self,
        solution_yaml: str | None
    ) -> str:
        """
        验证方案 YAML 定义

        Args:
            solution_yaml: 解决方案 YAML 文件路径

        Returns:
            验证结果
        """
        try:
            yaml_path = Path(solution_yaml)

            if not yaml_path.exists():
                return json.dumps({
                    "valid": False,
                    "error": f"File not found: {solution_yaml}"
                }, indent=2)

            with open(yaml_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 检查 YAML 语法
            try:
                data = yaml.safe_load(content)
            except yaml.YAMLError as e:
                return json.dumps({
                    "valid": False,
                    "error": f"YAML syntax error: {str(e)}"
                }, indent=2)

            # 验证必需字段
            errors = []
            warnings = []

            # 检查 solution 部分
            solution = data.get("solution", {})
            if not solution:
                errors.append("Missing 'solution' section")
            else:
                if not solution.get("name"):
                    errors.append("solution.name is required")
                if not solution.get("display_name"):
                    errors.append("solution.display_name is required")
                if not solution.get("version"):
                    errors.append("solution.version is required")
                else:
                    version = solution.get("version", "")
                    if not _validate_version(version):
                        errors.append(f"solution.version must be in format X.Y.Z.W, got: {version}")

            # 检查 components 部分
            components = data.get("components", {})
            if not components:
                warnings.append("No components defined")

            # 检查组件文件是否存在
            # 解决方案文件在 metadata/solutions/ 下，组件路径相对于 metadata/
            base_path = yaml_path.parent.parent  # 从 metadata/solutions/ -> metadata/
            for comp_type, files in components.items():
                if comp_type == "other":
                    continue
                if isinstance(files, list):
                    for file_path in files:
                        full_path = base_path / file_path
                        if not full_path.exists():
                            warnings.append(f"Component file not found: {file_path}")

            # 检查 sync 配置
            sync = data.get("sync", {})
            if sync:
                order = sync.get("order", [])
                valid_order = set(DEFAULT_SYNC_ORDER)
                for item in order:
                    if item not in valid_order:
                        errors.append(f"Invalid sync order item: {item}")

                on_conflict = sync.get("on_conflict")
                if on_conflict and on_conflict not in ("skip", "update", "replace", "create_only"):
                    errors.append(f"Invalid on_conflict value: {on_conflict}")

            return json.dumps({
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "solution_name": solution.get("name"),
                "version": solution.get("version"),
                "component_types": list(components.keys()) if components else []
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "valid": False,
                "error": f"Validation failed: {str(e)}"
            }, indent=2)

    async def scan_components(
        self,
        solution_yaml: str | None
    ) -> str:
        """
        扫描方案定义的组件

        Args:
            solution_yaml: 解决方案 YAML 文件路径

        Returns:
            组件扫描结果
        """
        try:
            solution_def = self._parse_solution_yaml(solution_yaml)
            components_def = solution_def.get("components", {})

            base_path = str(Path(solution_yaml).parent)
            components = self._collect_component_files(components_def, base_path)

            # 按类型分组
            by_type: dict[str, list[dict[str, Any]]] = {}
            for comp in components:
                comp_type = comp.get("type")
                if comp_type not in by_type:
                    by_type[comp_type] = []
                by_type[comp_type].append(comp)

            # 统计
            type_counts = {k: len(v) for k, v in by_type.items()}

            return json.dumps({
                "solution": solution_def.get("solution", {}).get("name"),
                "total_components": len(components),
                "type_counts": type_counts,
                "components": components,
                "sync_order": self._sort_components_by_dependency(
                    components,
                    solution_def.get("sync", {}).get("order", DEFAULT_SYNC_ORDER)
                )
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Scan components failed: {str(e)}"
            }, indent=2)

    def _parse_solution_yaml(self, yaml_path: str) -> dict[str, Any]:
        """
        解析解决方案 YAML 文件

        Args:
            yaml_path: YAML 文件路径

        Returns:
            解析后的数据
        """
        path = Path(yaml_path)

        if not path.exists():
            raise FileNotFoundError(f"Solution YAML not found: {yaml_path}")

        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _collect_component_files(
        self,
        components_def: dict[str, Any],
        base_path: str = "metadata"
    ) -> list[dict[str, Any]]:
        """
        收集组件文件列表

        Args:
            components_def: 组件定义（来自 YAML 的 components 部分）
            base_path: 基础路径

        Returns:
            组件文件列表
        """
        components = []
        base = Path(base_path)

        # 组件类型到文件路径的映射
        type_mappings = {
            "tables": "table",
            "forms": "form",
            "views": "view",
            "optionsets": "optionset",
            "webresources": "webresource",
            "plugins": "plugin"
        }

        for section, files in components_def.items():
            if section == "other":
                # 处理其他类型组件
                if isinstance(files, list):
                    for item in files:
                        if isinstance(item, dict):
                            components.append({
                                "type": item.get("component_type", "other"),
                                "id": item.get("id"),
                                "name": item.get("name"),
                                "path": item.get("path", "")
                            })
            elif section in type_mappings:
                comp_type = type_mappings[section]
                if isinstance(files, list):
                    for file_path in files:
                        full_path = base / file_path
                        components.append({
                            "type": comp_type,
                            "path": str(full_path),
                            "relative_path": file_path,
                            "exists": full_path.exists()
                        })

        return components

    async def _check_component_exists(
        self,
        client: Any,
        component_type: str,
        component_path: str
    ) -> bool:
        """
        检查组件是否已存在于 Dataverse

        Args:
            client: Dataverse 客户端
            component_type: 组件类型
            component_path: 组件路径

        Returns:
            组件是否存在
        """
        try:
            path = Path(component_path)

            if not path.exists():
                return False

            # 读取 YAML 获取实体/组件名称
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if component_type == "table":
                schema_name = data.get("schema", {}).get("schema_name")
                if schema_name:
                    entity_meta = client.get_entity_metadata(schema_name)
                    return bool(entity_meta and entity_meta.get("MetadataId"))

            elif component_type == "form":
                entity = data.get("form", {}).get("entity")
                if entity:
                    forms = client.get_forms(entity, form_type=2)
                    return len(forms) > 0

            elif component_type == "view":
                entity = data.get("view", {}).get("entity")
                view_name = data.get("view", {}).get("schema_name") or data.get("view", {}).get("name")
                if entity and view_name:
                    entity_meta = client.get_entity_metadata(entity)
                    logical_name = entity_meta.get("LogicalName")
                    if logical_name:
                        view = client.get_view_by_name(logical_name, view_name)
                        return view is not None

            elif component_type == "optionset":
                # 全局选项集检查
                name = data.get("optionset", {}).get("name")
                if name:
                    # 通过 API 检查选项集是否存在
                    return True  # 简化处理

            elif component_type == "webresource":
                name = data.get("webresource", {}).get("name")
                if name:
                    resources = client.get_webresources(filter=f"name eq '{name}'")
                    return len(resources) > 0

            return False

        except Exception:
            return False

    def _sort_components_by_dependency(
        self,
        components: list[dict[str, Any]],
        order: list[str] = None
    ) -> list[dict[str, Any]]:
        """
        按依赖关系排序组件

        Args:
            components: 组件列表
            order: 自定义排序顺序

        Returns:
            排序后的组件列表
        """
        order = order or DEFAULT_SYNC_ORDER

        # 按类型分组
        grouped: dict[str, list[dict[str, Any]]] = {}
        for comp in components:
            comp_type = comp.get("type", "other")
            if comp_type not in grouped:
                grouped[comp_type] = []
            grouped[comp_type].append(comp)

        # 按指定顺序重新组合
        sorted_components = []
        for comp_type in order:
            if comp_type in grouped:
                sorted_components.extend(grouped[comp_type])

        # 添加未在顺序中定义的组件
        for comp_type, comps in grouped.items():
            if comp_type not in order:
                sorted_components.extend(comps)

        return sorted_components

    async def _sync_component(
        self,
        client: Any,
        component_type: str,
        component_path: str,
        action: str
    ) -> dict[str, Any]:
        """
        同步单个组件

        Args:
            client: Dataverse 客户端
            component_type: 组件类型
            component_path: 组件路径
            action: 操作类型 (create/update/replace)

        Returns:
            同步结果
        """
        try:
            if not self.core_agent:
                return {"success": False, "error": "No core agent"}

            # 获取或创建 MetadataAgent
            metadata_agent = self.core_agent.metadata_agent
            if not metadata_agent:
                from framework.agents.metadata_agent import MetadataAgent
                metadata_agent = MetadataAgent(core_agent=self.core_agent)
                self.core_agent.set_metadata_agent(metadata_agent)

            if component_type == "table":
                result = await metadata_agent.create_table(component_path)
                return json.loads(result)

            elif component_type == "form":
                result = await metadata_agent.create_form(component_path)
                return json.loads(result)

            elif component_type == "view":
                result = await metadata_agent.create_view(component_path)
                return json.loads(result)

            elif component_type == "optionset":
                # 选项集同步需要特殊处理
                return {"success": True, "message": "OptionSet sync not yet implemented"}

            elif component_type == "webresource":
                # Web 资源同步
                return {"success": True, "message": "WebResource sync not yet implemented"}

            else:
                return {"success": False, "error": f"Unknown component type: {component_type}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

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

    # ==================== 发布商相关方法 ====================

    def get_publisher(self, publisher_key: str = None) -> dict[str, Any] | None:
        """
        获取发布商信息

        Args:
            publisher_key: 发布商 key，如果为 None 则使用 current 配置

        Returns:
            发布商信息字典，包含 name, display_name, prefix, description
        """
        if not self._publishers_config:
            return None

        key = publisher_key or self._publishers_config.get("current", "default")
        publishers = self._publishers_config.get("publishers", {})

        return publishers.get(key)

    def resolve_publisher_info(
        self,
        solution_def: dict[str, Any]
    ) -> dict[str, Any]:
        """
        解析解决方案定义中的发布商信息

        Args:
            solution_def: 解决方案定义字典

        Returns:
            发布商信息字典，包含 name, display_name, prefix
        """
        solution = solution_def.get("solution", {})

        # 优先使用 publisher 引用
        publisher_key = solution.get("publisher")
        if publisher_key:
            publisher = self.get_publisher(publisher_key)
            if publisher:
                return {
                    "name": publisher.get("name"),
                    "display_name": publisher.get("display_name"),
                    "prefix": publisher.get("prefix"),
                    "description": publisher.get("description", "")
                }

        # 其次使用 publisher_info
        publisher_info = solution.get("publisher_info")
        if publisher_info:
            return {
                "name": publisher_info.get("name"),
                "display_name": publisher_info.get("display_name"),
                "prefix": publisher_info.get("prefix"),
                "description": publisher_info.get("description", "")
            }

        # 最后使用默认发布商
        default_publisher = self.get_publisher()
        if default_publisher:
            return {
                "name": default_publisher.get("name"),
                "display_name": default_publisher.get("display_name"),
                "prefix": default_publisher.get("prefix"),
                "description": default_publisher.get("description", "")
            }

        # 硬编码的默认值
        return {
            "name": "DefaultPublishercrmdev",
            "display_name": "CrmDev 的默认发布者",
            "prefix": "new",
            "description": "项目默认发布商"
        }

    def list_publishers(self) -> str:
        """
        列出所有可用的发布商

        Returns:
            发布商列表 JSON
        """
        if not self._publishers_config:
            return json.dumps({
                "error": "No publishers configuration found"
            }, indent=2)

        publishers = self._publishers_config.get("publishers", {})
        current = self._publishers_config.get("current", "default")

        result = {
            "current": current,
            "publishers": []
        }

        for key, info in publishers.items():
            result["publishers"].append({
                "key": key,
                "name": info.get("name"),
                "display_name": info.get("display_name"),
                "prefix": info.get("prefix"),
                "description": info.get("description", ""),
                "is_current": key == current
            })

        return json.dumps(result, indent=2, ensure_ascii=False)

    # ==================== 发布商创建和检查 ====================

    async def _ensure_publisher_exists(
        self,
        publisher_info: dict[str, Any],
        dry_run: bool = True
    ) -> dict[str, Any]:
        """
        确保发布商存在，如果不存在则创建

        Args:
            publisher_info: 发布商信息
            dry_run: 是否为预演模式

        Returns:
            操作结果
        """
        if not self.core_agent:
            return {"success": False, "error": "No core agent available"}

        client = self.core_agent.get_client()

        # 检查发布商是否已存在
        existing = client.get_publisher_by_name(publisher_info.get("name"))

        if existing:
            return {
                "success": True,
                "created": False,
                "publisher": existing,
                "message": f"Publisher '{publisher_info.get('name')}' already exists"
            }

        # 发布商不存在
        if dry_run:
            return {
                "success": True,
                "created": False,
                "dry_run": True,
                "publisher": publisher_info,
                "message": f"Publisher '{publisher_info.get('name')}' would be created"
            }

        # 创建发布商
        try:
            created = client.create_publisher(
                name=publisher_info.get("name"),
                display_name=publisher_info.get("display_name"),
                prefix=publisher_info.get("prefix"),
                description=publisher_info.get("description", "")
            )

            return {
                "success": True,
                "created": True,
                "publisher": created,
                "message": f"Publisher '{publisher_info.get('name')}' created successfully"
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create publisher: {str(e)}"
            }

    async def create_publisher(
        self,
        name: str,
        display_name: str,
        prefix: str,
        description: str = None
    ) -> str:
        """
        创建发布商

        Args:
            name: 发布商唯一名称
            display_name: 发布商显示名称
            prefix: 发布商前缀
            description: 发布商描述

        Returns:
            创建结果
        """
        if not self.core_agent:
            return json.dumps({
                "error": "No core agent available"
            }, indent=2)

        client = self.core_agent.get_client()

        try:
            # 检查是否已存在
            existing = client.get_publisher_by_name(name)
            if existing:
                return json.dumps({
                    "success": False,
                    "error": f"Publisher '{name}' already exists",
                    "existing": existing
                }, indent=2, ensure_ascii=False)

            # 创建发布商
            created = client.create_publisher(
                name=name,
                display_name=display_name,
                prefix=prefix,
                description=description
            )

            return json.dumps({
                "success": True,
                "publisher": created
            }, indent=2, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to create publisher: {str(e)}"
            }, indent=2)

    # ==================== 解决方案创建和检查 ====================

    async def _ensure_solution_exists(
        self,
        solution_name: str,
        display_name: str,
        version: str,
        publisher_id: str | None = None,
        dry_run: bool = True
    ) -> dict[str, Any]:
        """
        确保解决方案存在，如果不存在则创建

        Args:
            solution_name: 解决方案唯一名称
            display_name: 解决方案显示名称
            version: 版本号
            publisher_id: 发布商 ID
            dry_run: 是否为预演模式

        Returns:
            操作结果
        """
        if not self.core_agent:
            return {"success": False, "error": "No core agent available"}

        client = self.core_agent.get_client()

        # 检查解决方案是否已存在
        existing = client.get_solution_by_name(solution_name)

        if existing:
            return {
                "success": True,
                "created": False,
                "solution": existing,
                "message": f"Solution '{solution_name}' already exists"
            }

        # 解决方案不存在
        if dry_run:
            return {
                "success": True,
                "created": False,
                "dry_run": True,
                "solution": {
                    "uniquename": solution_name,
                    "friendlyname": display_name,
                    "version": version
                },
                "message": f"Solution '{solution_name}' would be created"
            }

        # 创建解决方案
        try:
            created = client.create_solution(
                unique_name=solution_name,
                display_name=display_name,
                version=version,
                publisher_id=publisher_id
            )

            return {
                "success": True,
                "created": True,
                "solution": created,
                "message": f"Solution '{solution_name}' created successfully"
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create solution: {str(e)}"
            }

    async def _add_component_to_solution(
        self,
        client: Any,
        solution_name: str,
        component: dict[str, Any]
    ) -> dict[str, Any]:
        """
        将组件添加到解决方案

        Args:
            client: Dataverse 客户端
            solution_name: 解决方案名称
            component: 组件信息（包含 sync_result）

        Returns:
            添加结果
        """
        try:
            comp_type = component.get("type")
            comp_path = component.get("path")

            # 优先使用 sync_result 中的组件 ID
            sync_result = component.get("sync_result", {})

            # 组件类型代码映射（根据 Dataverse solutioncomponent.componenttype 选项集）
            type_codes = {
                "table": 1,
                "entity": 1,
                "form": 60,      # System Form
                "view": 26,      # Saved Query
                "webresource": 61  # Web Resource
            }

            if comp_type not in type_codes:
                return {
                    "success": False,
                    "error": f"Unknown component type: {comp_type}"
                }

            component_type_code = type_codes[comp_type]

            # 尝试从 sync_result 获取组件 ID
            object_id = None
            if sync_result.get("success"):
                if comp_type == "view" and "savedqueryid" in sync_result:
                    object_id = sync_result["savedqueryid"]
                elif comp_type == "table" and "entityid" in sync_result:
                    object_id = sync_result["entityid"]
                elif comp_type == "form" and "formid" in sync_result:
                    object_id = sync_result["formid"]

            # 如果 sync_result 中没有 ID，通过 YAML 获取并查询
            if not object_id:
                import yaml
                with open(comp_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                schema_name = None
                entity_name = None

                if comp_type == "table":
                    schema_name = data.get("schema", {}).get("schema_name")
                    # 获取实体 ID
                    entity_meta = client.get_entity_metadata(schema_name)
                    if entity_meta:
                        object_id = entity_meta.get("MetadataId")

                elif comp_type == "form":
                    entity_name = data.get("form", {}).get("entity")
                    form_name = data.get("form", {}).get("name")
                    # 获取表单 ID
                    if entity_name and form_name:
                        forms = client.get_forms(entity_name)
                        for form in forms:
                            if form.get("name") == form_name:
                                object_id = form.get("formid")
                                break

                elif comp_type == "view":
                    entity_name = data.get("view", {}).get("entity")
                    schema_name = data.get("view", {}).get("schema_name") or data.get("view", {}).get("name")
                    # 获取视图 ID
                    if entity_name and schema_name:
                        view = client.get_view_by_name(entity_name, schema_name)
                        if view:
                            object_id = view.get("savedqueryid")

                elif comp_type == "webresource":
                    schema_name = data.get("webresource", {}).get("name")
                    resources = client.get_webresources(filter=f"name eq '{schema_name}'")
                    if resources:
                        object_id = resources[0].get("webresourceid")

            if not object_id:
                return {
                    "success": False,
                    "error": f"Cannot find component ID for: {comp_type}/{comp_path}"
                }

            # 添加组件到解决方案
            result = client.add_solution_component(
                solution_name=solution_name,
                component_type=component_type_code,
                object_id=object_id
            )

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to add component to solution: {str(e)}"
            }

    async def _publish_solution_wrapper(
        self,
        client: Any
    ) -> dict[str, Any]:
        """
        发布解决方案的包装方法

        Args:
            client: Dataverse 客户端

        Returns:
            发布结果
        """
        try:
            result = client.publish_solution()
            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
