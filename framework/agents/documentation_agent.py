"""
Documentation Agent - 文档更新代理

负责自动检测代码变更并更新相关文档
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 添加框架路径
import sys
framework_path = Path(__file__).parent.parent
if str(framework_path) not in sys.path:
    sys.path.insert(0, str(framework_path))

from framework.utils.change_detector import ChangeDetector, ChangeReport, ChangedFile
from framework.utils.impact_analyzer import ImpactAnalyzer, ImpactReport
from framework.llm.langchain_client import LangChainLLMClient, LLMResponse

logger = logging.getLogger(__name__)


class DocumentationAgent:
    """
    文档更新代理

    功能：
    1. 检测代码变更
    2. 分析对文档的影响
    3. 生成文档更新内容
    4. 应用文档更新
    """

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None
    ):
        """
        初始化文档代理

        Args:
            repo_root: 仓库根目录
            llm_provider: LLM 提供商
            llm_model: LLM 模型
        """
        self.repo_root = repo_root or self._find_repo_root()

        # 初始化组件
        self.change_detector = ChangeDetector(repo_root=self.repo_root)
        self.impact_analyzer = ImpactAnalyzer()

        # 初始化 LLM 客户端
        self.llm_client = LangChainLLMClient(
            provider=llm_provider,
            model=llm_model
        )

        # 加载提示词模板
        self.prompts_dir = Path(__file__).parent.parent / "prompts"
        self._load_prompts()

    def _find_repo_root(self) -> Path:
        """查找仓库根目录"""
        path = Path.cwd()
        while path != path.parent:
            if (path / ".git").exists():
                return path
            path = path.parent
        return Path.cwd()

    def _load_prompts(self):
        """加载提示词模板"""
        self.prompts = {}

        prompt_files = {
            "skill_update": "skill_update.md",
            "claude_md_update": "claude_md_update.md",
            "change_summary": "change_summary.md",
        }

        for key, filename in prompt_files.items():
            prompt_path = self.prompts_dir / filename
            if prompt_path.exists():
                with open(prompt_path, "r", encoding="utf-8") as f:
                    self.prompts[key] = f.read()
            else:
                logger.warning(f"Prompt file not found: {prompt_path}")
                self.prompts[key] = ""

    async def handle(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        处理 MCP 工具调用

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            处理结果
        """
        try:
            if tool_name == "doc_analyze_changes":
                return await self.analyze_changes(
                    arguments.get("scope", "staged"),
                    arguments.get("include_insignificant", False)
                )

            elif tool_name == "doc_update_skill":
                return await self.update_skill(
                    arguments.get("skill_path"),
                    arguments.get("apply", False)
                )

            elif tool_name == "doc_update_claude_md":
                return await self.update_claude_md(
                    arguments.get("apply", False)
                )

            elif tool_name == "doc_generate_summary":
                return await self.generate_summary(
                    arguments.get("scope", "staged"),
                    arguments.get("output_file")
                )

            elif tool_name == "doc_list_skills":
                return await self.list_skills()

            elif tool_name == "doc_get_mcp_tools":
                return await self.get_mcp_tools()

            elif tool_name == "doc_full_update":
                return await self.full_update(
                    arguments.get("scope", "staged"),
                    arguments.get("auto_apply", False)
                )

            else:
                return json.dumps({
                    "error": f"Unknown tool: {tool_name}"
                }, indent=2)

        except Exception as e:
            logger.error(f"Error handling tool {tool_name}: {e}", exc_info=True)
            return json.dumps({
                "error": str(e),
                "tool": tool_name
            }, indent=2, ensure_ascii=False)

    async def analyze_changes(
        self,
        scope: str = "staged",
        include_insignificant: bool = False
    ) -> str:
        """
        分析代码变更

        Args:
            scope: 变更范围 (staged, unstaged, head)
            include_insignificant: 是否包含无意义变更

        Returns:
            分析结果 JSON
        """
        # 获取变更
        if scope == "staged":
            changes = self.change_detector.get_staged_changes()
        elif scope == "unstaged":
            changes = self.change_detector.get_unstaged_changes()
        else:
            changes = self.change_detector.get_head_changes()

        # 分析影响
        impact = self.impact_analyzer.analyze(changes)

        # 构建结果
        result = {
            "timestamp": datetime.now().isoformat(),
            "commit": {
                "hash": changes.commit_hash,
                "message": changes.commit_message
            },
            "changes": {
                "total_files": len(changes.files),
                "significant_files": len(changes.significant_files),
                "by_type": {
                    "python": len(changes.python_files),
                    "yaml": len(changes.yaml_files),
                    "markdown": len([f for f in changes.files if f.is_markdown]),
                }
            },
            "impacts": {
                "total": len(impact.impacts),
                "high_confidence": len(impact.high_confidence_impacts),
                "medium_confidence": len(impact.medium_confidence_impacts),
                "affected_docs": impact.affected_docs
            },
            "details": {
                "files": [
                    {
                        "path": f.path,
                        "type": f.change_type.value,
                        "significance": f.significance.value,
                        "stats": f.stats
                    }
                    for f in changes.files if include_insignificant or f.significance.value != "insignificant"
                ],
                "impacts": [
                    {
                        "doc_path": i.doc_path,
                        "impact_type": i.impact_type,
                        "confidence": i.confidence,
                        "related_changes": i.related_changes,
                        "suggested_action": i.suggested_action
                    }
                    for i in impact.impacts
                ]
            }
        }

        return json.dumps(result, indent=2, ensure_ascii=False)

    async def update_skill(
        self,
        skill_path: Optional[str],
        apply: bool = False
    ) -> str:
        """
        更新 SKILL 文档

        Args:
            skill_path: SKILL 路径（如果为空，自动检测）
            apply: 是否应用更新

        Returns:
            更新结果
        """
        # 获取暂存区变更
        changes = self.change_detector.get_staged_changes()

        # 筛选 SKILL 相关变更
        skill_files = [f for f in changes.files if ".claude/skills/" in f.path]

        if not skill_files and not skill_path:
            return json.dumps({
                "success": False,
                "message": "No skill changes detected"
            }, indent=2)

        # 确定要更新的 SKILL
        if skill_path:
            skill_files_to_update = [skill_path]
        else:
            # 从变更文件中推断 SKILL 路径
            skill_files_to_update = set()
            for f in skill_files:
                parts = Path(f.path).parts
                if ".claude" in parts and "skills" in parts:
                    try:
                        skills_idx = parts.index("skills")
                        if skills_idx + 1 < len(parts):
                            skill_name = parts[skills_idx + 1]
                            skill_files_to_update.add(f".claude/skills/{skill_name}/SKILL.md")
                    except (ValueError, IndexError):
                        pass
            skill_files_to_update = list(skill_files_to_update)

        results = []

        for skill_file in skill_files_to_update:
            skill_full_path = self.repo_root / skill_file

            if not skill_full_path.exists():
                results.append({
                    "skill": skill_file,
                    "status": "skipped",
                    "reason": "File not found"
                })
                continue

            # 读取当前内容
            with open(skill_full_path, "r", encoding="utf-8") as f:
                current_content = f.read()

            # 准备 diff 内容
            related_diffs = [
                f.diff_content for f in skill_files
                if skill_file.replace("/SKILL.md", "") in f.path or
                   any(p in f.path for p in parts if ".claude" in p and "skills" in p)
            ]

            diff_content = "\n\n".join(related_diffs) if related_diffs else "No diff available"

            # 生成更新
            updated_content = await self._generate_skill_update(
                current_content,
                diff_content,
                skill_file,
                [f.path for f in skill_files]
            )

            if apply:
                # 应用更新
                with open(skill_full_path, "w", encoding="utf-8") as f:
                    f.write(updated_content)
                results.append({
                    "skill": skill_file,
                    "status": "updated",
                    "action": "applied"
                })
            else:
                # 生成建议文件
                suggest_path = self.repo_root / f"{skill_file}.suggest"
                suggest_path.parent.mkdir(parents=True, exist_ok=True)
                with open(suggest_path, "w", encoding="utf-8") as f:
                    f.write(updated_content)
                results.append({
                    "skill": skill_file,
                    "status": "suggestion_created",
                    "suggestion_file": str(suggest_path)
                })

        return json.dumps({
            "success": True,
            "results": results
        }, indent=2, ensure_ascii=False)

    async def _generate_skill_update(
        self,
        current_content: str,
        diff_content: str,
        skill_path: str,
        changed_files: List[str]
    ) -> str:
        """生成 SKILL 更新内容"""
        prompt_template = self.prompts.get("skill_update", "")

        prompt = prompt_template.format(
            current_content=current_content,
            diff_content=diff_content[:5000],  # 限制长度
            changed_files="\n".join(changed_files),
            skill_path=skill_path,
            timestamp=datetime.now().isoformat()
        )

        system_prompt = """你是一个技术文档专家，负责维护 Claude Code SKILL 文档。
请根据代码变更更新文档，保持格式一致，不要遗漏重要功能。"""

        response = self.llm_client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3
        )

        return response.content

    async def update_claude_md(self, apply: bool = False) -> str:
        """
        更新 CLAUDE.md 文档

        Args:
            apply: 是否应用更新

        Returns:
            更新结果
        """
        claude_md_path = self.repo_root / "CLAUDE.md"

        # 读取当前内容
        current_content = ""
        if claude_md_path.exists():
            with open(claude_md_path, "r", encoding="utf-8") as f:
                current_content = f.read()

        # 获取 MCP 工具列表
        mcp_tools = await self._get_mcp_tools_list()

        # 获取 SKILL 列表
        skills = await self._get_skills_list()

        # 生成更新
        updated_content = await self._generate_claude_md(
            current_content,
            mcp_tools,
            skills
        )

        if apply:
            # 应用更新
            claude_md_path.parent.mkdir(parents=True, exist_ok=True)
            with open(claude_md_path, "w", encoding="utf-8") as f:
                f.write(updated_content)
            return json.dumps({
                "success": True,
                "file": str(claude_md_path),
                "action": "updated"
            }, indent=2)
        else:
            # 生成建议文件
            suggest_path = self.repo_root / "CLAUDE.md.suggest"
            with open(suggest_path, "w", encoding="utf-8") as f:
                f.write(updated_content)
            return json.dumps({
                "success": True,
                "suggestion_file": str(suggest_path),
                "action": "suggestion_created"
            }, indent=2)

    async def _generate_claude_md(
        self,
        current_content: str,
        mcp_tools: List[Dict],
        skills: List[Dict]
    ) -> str:
        """生成 CLAUDE.md 内容"""
        prompt_template = self.prompts.get("claude_md_update", "")

        # 获取项目信息
        project_description = """Power Platform Agent 是一个为 Claude Code/Cursor 提供 Power Platform 访问能力的 MCP 服务器。
支持 Dataverse 元数据管理、插件部署、解决方案管理等核心功能。"""

        prompt = prompt_template.format(
            current_content=current_content,
            project_description=project_description,
            project_root=str(self.repo_root),
            mcp_tools=json.dumps(mcp_tools, ensure_ascii=False, indent=2),
            skills=json.dumps(skills, ensure_ascii=False, indent=2),
            timestamp=datetime.now().isoformat(),
            current_date=datetime.now().strftime("%Y-%m-%d")
        )

        system_prompt = """你是一个技术文档专家，负责生成和维护 Power Platform Agent 项目的 CLAUDE.md 文档。
请生成清晰、完整的项目文档，帮助开发者快速了解和使用该项目。"""

        response = self.llm_client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=6000
        )

        return response.content

    async def generate_summary(
        self,
        scope: str = "staged",
        output_file: Optional[str] = None
    ) -> str:
        """
        生成变更总结

        Args:
            scope: 变更范围
            output_file: 输出文件路径

        Returns:
            变更总结
        """
        # 获取变更
        if scope == "staged":
            changes = self.change_detector.get_staged_changes()
        else:
            changes = self.change_detector.get_unstaged_changes()

        # 准备变更详情
        changes_detail = []
        for f in changes.significant_files:
            changes_detail.append(f"""
### {f.path}
- 变更类型: {f.change_type.value}
- 重要性: {f.significance.value}
- 变更统计: {f.stats}
""")

        prompt = self.prompts.get("change_summary", "").format(
            commit_hash=changes.commit_hash or "N/A",
            commit_message=changes.commit_message or "N/A",
            timestamp=datetime.now().isoformat(),
            changed_files="\n".join([f"- {f.path} ({f.change_type.value})" for f in changes.files]),
            changes_detail="\n".join(changes_detail),
            date=datetime.now().strftime("%Y-%m-%d")
        )

        system_prompt = """你是一个技术文档专家，负责生成代码变更的总结文档。
请生成清晰、简洁的变更总结。"""

        response = self.llm_client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3
        )

        summary = response.content

        # 保存到文件
        if output_file:
            output_path = self.repo_root / output_file
        else:
            # 默认追加到 CHANGELOG.md
            output_path = self.repo_root / "CHANGELOG.md"

        if output_path.exists():
            with open(output_path, "r", encoding="utf-8") as f:
                existing_content = f.read()
            # 在头部插入新内容
            new_content = summary + "\n\n" + existing_content
        else:
            new_content = summary

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return json.dumps({
            "success": True,
            "summary": summary,
            "output_file": str(output_path)
        }, indent=2, ensure_ascii=False)

    async def list_skills(self) -> str:
        """列出所有 SKILL"""
        skills = await self._get_skills_list()
        return json.dumps({
            "skills": skills,
            "total": len(skills)
        }, indent=2, ensure_ascii=False)

    async def get_mcp_tools(self) -> str:
        """获取 MCP 工具列表"""
        tools = await self._get_mcp_tools_list()
        return json.dumps({
            "tools": tools,
            "total": len(tools)
        }, indent=2, ensure_ascii=False)

    async def full_update(
        self,
        scope: str = "staged",
        auto_apply: bool = False
    ) -> str:
        """
        执行完整的文档更新流程

        Args:
            scope: 变更范围
            auto_apply: 是否自动应用更新

        Returns:
            更新结果
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "actions": []
        }

        # 1. 分析变更
        analysis = json.loads(await self.analyze_changes(scope))
        results["analysis"] = analysis
        results["actions"].append({"action": "analyze_changes", "result": "completed"})

        # 2. 检查是否需要更新
        impacts = analysis.get("impacts", {})
        if impacts.get("total", 0) == 0:
            results["message"] = "No documentation updates needed"
            return json.dumps(results, indent=2)

        # 3. 更新 SKILL 文档
        skill_result = json.loads(await self.update_skill(apply=auto_apply))
        results["actions"].append({"action": "update_skill", "result": skill_result})

        # 4. 更新 CLAUDE.md
        claude_md_result = json.loads(await self.update_claude_md(apply=auto_apply))
        results["actions"].append({"action": "update_claude_md", "result": claude_md_result})

        # 5. 生成变更总结
        summary_result = json.loads(await self.generate_summary(scope))
        results["actions"].append({"action": "generate_summary", "result": summary_result})

        results["message"] = "Documentation update completed"

        return json.dumps(results, indent=2, ensure_ascii=False)

    async def _get_mcp_tools_list(self) -> List[Dict]:
        """获取 MCP 工具列表"""
        # 从 mcp_serve.py 解析工具定义
        mcp_serve_path = self.repo_root / "framework" / "mcp_serve.py"

        if not mcp_serve_path.exists():
            return []

        # 简单解析工具定义
        # 实际应该通过导入模块获取
        tools = []

        # 默认工具列表
        default_tools = [
            {"category": "认证与环境管理", "tools": [
                {"name": "auth_login", "description": "连接到Dataverse环境"},
                {"name": "auth_status", "description": "查看当前连接状态"},
                {"name": "auth_logout", "description": "断开环境连接"},
                {"name": "environment_switch", "description": "切换当前环境"},
                {"name": "environment_list", "description": "列出所有配置的环境"},
            ]},
            {"category": "元数据管理", "tools": [
                {"name": "metadata_parse", "description": "解析YAML元数据文件"},
                {"name": "metadata_validate", "description": "验证元数据定义"},
                {"name": "metadata_create_table", "description": "创建数据表"},
                {"name": "metadata_create_attribute", "description": "创建字段"},
                {"name": "metadata_export", "description": "导出云端元数据为YAML"},
            ]},
            {"category": "命名规则", "tools": [
                {"name": "naming_convert", "description": "命名转换"},
                {"name": "naming_validate", "description": "验证命名"},
                {"name": "naming_bulk_convert", "description": "批量转换命名"},
            ]},
            {"category": "插件管理", "tools": [
                {"name": "plugin_build", "description": "构建插件项目"},
                {"name": "plugin_deploy", "description": "部署插件"},
                {"name": "plugin_step_register", "description": "注册插件Step"},
            ]},
            {"category": "解决方案管理", "tools": [
                {"name": "solution_export", "description": "导出解决方案"},
                {"name": "solution_import", "description": "导入解决方案"},
                {"name": "solution_sync", "description": "执行同步"},
            ]},
        ]

        return default_tools

    async def _get_skills_list(self) -> List[Dict]:
        """获取 SKILL 列表"""
        skills_dir = self.repo_root / ".claude" / "skills"

        if not skills_dir.exists():
            return []

        skills = []

        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                # 读取 SKILL.md 获取描述
                with open(skill_md, "r", encoding="utf-8") as f:
                    content = f.read()

                # 解析 frontmatter
                name = skill_dir.name
                description = ""
                for line in content.split("\n"):
                    if line.startswith("description:"):
                        description = line.split(":", 1)[1].strip()
                        break

                skills.append({
                    "name": name,
                    "path": f".claude/skills/{name}/SKILL.md",
                    "description": description
                })

        return skills
