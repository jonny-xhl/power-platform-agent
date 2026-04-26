"""
Documentation Agent - 文档更新代理

负责自动检测代码变更并更新相关文档

安全机制：
- 原子写入：通过临时文件 + os.replace 保证文件不会处于半写状态
- 备份机制：每次覆盖前自动备份到 .claude/backups/，保留最近 10 份
- 增量更新：LLM 输出 JSON section patches，按节合并而非全量覆盖
- 内容校验：写入前验证内容比例、结构完整性、Markdown 格式
"""

import json
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# 添加框架路径
import sys
framework_path = Path(__file__).parent.parent
if str(framework_path) not in sys.path:
    sys.path.insert(0, str(framework_path))

from framework.utils.change_detector import ChangeDetector, ChangeReport, ChangedFile
from framework.utils.impact_analyzer import ImpactAnalyzer, ImpactReport
from framework.llm.langchain_client import LangChainLLMClient, LLMResponse

logger = logging.getLogger(__name__)

# 备份保留数量
MAX_BACKUPS = 10


class DocumentationAgent:
    """
    文档更新代理

    功能：
    1. 检测代码变更
    2. 分析对文档的影响
    3. 生成文档更新内容（增量 JSON patches）
    4. 安全地应用文档更新（原子写入 + 备份）
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

        # 备份目录
        self.backup_dir = self.repo_root / ".claude" / "backups"

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

    # ==================== 原子写入 + 备份机制 ====================

    def _atomic_write(
        self,
        target_path: Path,
        content: str,
        validation_fn: Optional[Callable[[str], Tuple[bool, str]]] = None
    ) -> Dict[str, Any]:
        """
        原子写入文件：通过临时文件 + os.replace 保证安全

        流程:
        1. 写入临时文件 {target_path}.tmp
        2. 调用 validation_fn 校验内容
           - 通过 → 备份原文件 → os.replace(tmp, target)
           - 失败 → 删除 .tmp，原文件不变
        3. 备份到 .claude/backups/ (保留最近 MAX_BACKUPS 份)

        Args:
            target_path: 目标文件路径
            content: 要写入的内容
            validation_fn: 可选校验函数，接收内容字符串，返回 (is_valid, error_message)

        Returns:
            {"success": bool, "message": str, "backup_path": str|None}
        """
        tmp_path = target_path.parent / f"{target_path.name}.tmp"

        try:
            # 1. 写入临时文件
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)

            # 2. 校验内容
            if validation_fn:
                is_valid, error_msg = validation_fn(content)
                if not is_valid:
                    # 校验失败：保留 .suggest 文件供人工审阅，删除 .tmp
                    suggest_path = target_path.parent / f"{target_path.name}.suggest"
                    shutil.move(str(tmp_path), str(suggest_path))
                    return {
                        "success": False,
                        "message": f"Validation failed: {error_msg}",
                        "suggest_file": str(suggest_path)
                    }

            # 3. 备份原文件
            backup_path = None
            if target_path.exists():
                backup_path = self._create_backup(target_path)

            # 4. 原子替换
            os.replace(str(tmp_path), str(target_path))

            return {
                "success": True,
                "message": "File written atomically",
                "backup_path": str(backup_path) if backup_path else None
            }

        except Exception as e:
            # 清理临时文件
            if tmp_path.exists():
                tmp_path.unlink()
            logger.error(f"Atomic write failed for {target_path}: {e}")
            return {
                "success": False,
                "message": f"Write error: {str(e)}"
            }

    def _create_backup(self, file_path: Path) -> Path:
        """
        创建文件备份

        Args:
            file_path: 要备份的文件路径

        Returns:
            备份文件路径
        """
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}.{timestamp}.bak"
        backup_path = self.backup_dir / backup_name

        shutil.copy2(str(file_path), str(backup_path))

        # 清理旧备份，保留最近 MAX_BACKUPS 份
        self._cleanup_backups(file_path.name)

        return backup_path

    def _cleanup_backups(self, original_name: str):
        """清理旧备份，保留最近 MAX_BACKUPS 份"""
        if not self.backup_dir.exists():
            return

        pattern = f"{original_name}.*.bak"
        backups = sorted(
            self.backup_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        for old_backup in backups[MAX_BACKUPS:]:
            old_backup.unlink()

    # ==================== 内容校验 ====================

    def _validate_content(
        self,
        original_content: str,
        new_content: str,
        required_sections: Optional[List[str]] = None
    ) -> Tuple[bool, str]:
        """
        校验 LLM 生成的内容是否安全

        规则:
        1. 内容比例：新内容不应 < 原文的 50% 或 > 200%
        2. 结构完整性：必选 section 不能消失
        3. Markdown 格式：代码块必须闭合，表格格式正确

        Args:
            original_content: 原文件内容
            new_content: 新内容
            required_sections: 必须保留的 section 标题列表

        Returns:
            (is_valid, error_message)
        """
        if not new_content or not new_content.strip():
            return False, "New content is empty"

        # 规则 1: 内容比例检查（仅当原文非空时）
        if original_content and original_content.strip():
            original_len = len(original_content)
            new_len = len(new_content)
            ratio = new_len / original_len

            if ratio < 0.5:
                return False, f"New content is too short ({ratio:.0%} of original, minimum 50%)"
            if ratio > 2.0:
                return False, f"New content is too long ({ratio:.0%} of original, maximum 200%)"

        # 规则 2: 结构完整性检查
        if required_sections:
            for section in required_sections:
                # 检查 ## 级别标题
                if section not in new_content:
                    return False, f"Required section '{section}' is missing"

        # 规则 3: Markdown 格式检查
        # 代码块闭合检查
        code_block_count = new_content.count("```")
        if code_block_count % 2 != 0:
            return False, f"Unclosed code block (found {code_block_count} backtick fences, expected even number)"

        # YAML frontmatter 检查（如果原文有 frontmatter）
        if original_content and original_content.strip().startswith("---"):
            if not new_content.strip().startswith("---"):
                return False, "YAML frontmatter was removed (original had frontmatter)"
            # 检查 frontmatter 闭合
            fm_end = new_content.find("---", 3)
            if fm_end == -1:
                return False, "YAML frontmatter is not properly closed"

        return True, ""

    # ==================== 增量合并 ====================

    def _apply_section_patches(
        self,
        original_content: str,
        patches: Dict[str, Any]
    ) -> str:
        """
        将 JSON section patches 增量合并到原文档

        Args:
            original_content: 原文档内容
            patches: {"sections_to_update": {"section_title": "new_content"}, "sections_to_add": {"section_title": "content"}}

        Returns:
            合并后的文档内容
        """
        if not patches:
            return original_content

        sections_to_update = patches.get("sections_to_update", {})
        sections_to_add = patches.get("sections_to_add", {})

        result = original_content

        # 解析原文档的 section 结构
        lines = result.split("\n")
        section_ranges = {}  # {section_title: (start_line, end_line)}

        current_section = None
        current_level = 0
        section_start = 0

        for i, line in enumerate(lines):
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if header_match:
                level = len(header_match.group(1))
                title = header_match.group(2).strip()

                # 保存上一个 section 的范围
                if current_section is not None:
                    section_ranges[current_section] = (section_start, i)

                current_section = title
                current_level = level
                section_start = i

        # 保存最后一个 section
        if current_section is not None:
            section_ranges[current_section] = (section_start, len(lines))

        # 应用更新
        for title, new_content in sections_to_update.items():
            if title in section_ranges:
                start, end = section_ranges[title]
                lines[start:end] = [new_content]
                # 重新解析，因为行号已变
                result = "\n".join(lines)
                lines = result.split("\n")
                section_ranges = {}
                current_section = None
                for i, line in enumerate(lines):
                    header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
                    if header_match:
                        title_match = header_match.group(2).strip()
                        if current_section is not None:
                            section_ranges[current_section] = (section_start, i)
                        current_section = title_match
                        section_start = i
                if current_section is not None:
                    section_ranges[current_section] = (section_start, len(lines))

        # 添加新 section（追加到文档末尾）
        for title, content in sections_to_add.items():
            result += f"\n\n## {title}\n\n{content}\n"

        return result

    # ==================== MCP 工具处理 ====================

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

            # 生成增量更新 patches
            patches = await self._generate_skill_update(
                current_content,
                diff_content,
                skill_file,
                [f.path for f in skill_files]
            )

            if apply:
                # 尝试解析 JSON patches，回退到全量内容
                merged_content = self._try_merge_patches(current_content, patches)

                # 构建校验函数
                required = ["name:", "description:"]  # frontmatter 必选项
                def validate_fn(content: str) -> Tuple[bool, str]:
                    return self._validate_content(
                        current_content, content, required_sections=required
                    )

                # 原子写入
                write_result = self._atomic_write(skill_full_path, merged_content, validate_fn)

                if write_result["success"]:
                    results.append({
                        "skill": skill_file,
                        "status": "updated",
                        "action": "applied",
                        "backup_path": write_result.get("backup_path")
                    })
                else:
                    results.append({
                        "skill": skill_file,
                        "status": "validation_failed",
                        "message": write_result["message"],
                        "suggest_file": write_result.get("suggest_file")
                    })
            else:
                # 生成建议文件
                suggest_path = self.repo_root / f"{skill_file}.suggest"
                suggest_path.parent.mkdir(parents=True, exist_ok=True)
                with open(suggest_path, "w", encoding="utf-8") as f:
                    f.write(patches)
                results.append({
                    "skill": skill_file,
                    "status": "suggestion_created",
                    "suggestion_file": str(suggest_path)
                })

        return json.dumps({
            "success": True,
            "results": results
        }, indent=2, ensure_ascii=False)

    def _try_merge_patches(self, original_content: str, llm_output: str) -> str:
        """
        尝试将 LLM 输出解析为 JSON patches 并增量合并，
        如果解析失败则回退为使用 LLM 输出作为完整内容
        """
        # 尝试提取 JSON（LLM 可能在 ```json ... ``` 中包裹）
        json_str = llm_output.strip()
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', llm_output, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)

        try:
            patches = json.loads(json_str)
            if isinstance(patches, dict) and ("sections_to_update" in patches or "sections_to_add" in patches):
                return self._apply_section_patches(original_content, patches)
        except (json.JSONDecodeError, ValueError):
            pass

        # 回退：使用 LLM 输出作为完整内容
        return llm_output

    async def _generate_skill_update(
        self,
        current_content: str,
        diff_content: str,
        skill_path: str,
        changed_files: List[str]
    ) -> str:
        """生成 SKILL 更新内容（JSON section patches 格式）"""
        prompt_template = self.prompts.get("skill_update", "")

        prompt = prompt_template.format(
            current_content=current_content,
            diff_content=diff_content[:5000],  # 限制长度
            changed_files="\n".join(changed_files),
            skill_path=skill_path,
            timestamp=datetime.now().isoformat()
        )

        system_prompt = """你是一个技术文档专家，负责维护 Claude Code SKILL 文档。
请根据代码变更更新文档，保持格式一致，不要遗漏重要功能。
你必须输出 JSON 格式的 section patches，而不是完整的 Markdown 文档。"""

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
        patches = await self._generate_claude_md(
            current_content,
            mcp_tools,
            skills
        )

        if apply:
            # 尝试增量合并
            merged_content = self._try_merge_patches(current_content, patches)

            # 构建校验函数
            required_sections = ["项目概述", "MCP 工具列表", "架构说明"]
            def validate_fn(content: str) -> Tuple[bool, str]:
                return self._validate_content(
                    current_content, content, required_sections=required_sections
                )

            # 原子写入
            write_result = self._atomic_write(claude_md_path, merged_content, validate_fn)

            if write_result["success"]:
                return json.dumps({
                    "success": True,
                    "file": str(claude_md_path),
                    "action": "updated",
                    "backup_path": write_result.get("backup_path")
                }, indent=2)
            else:
                return json.dumps({
                    "success": False,
                    "file": str(claude_md_path),
                    "action": "validation_failed",
                    "message": write_result["message"],
                    "suggest_file": write_result.get("suggest_file")
                }, indent=2)
        else:
            # 生成建议文件
            suggest_path = self.repo_root / "CLAUDE.md.suggest"
            with open(suggest_path, "w", encoding="utf-8") as f:
                f.write(patches)
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
        """生成 CLAUDE.md 更新内容（JSON section patches 格式）"""
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
你必须输出 JSON 格式的 section patches，而不是完整的 Markdown 文档。"""

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

        # 准备变更详情（包含实际 diff 内容）
        changes_detail = []
        for f in changes.significant_files:
            diff_snippet = ""
            if hasattr(f, 'diff_content') and f.diff_content:
                diff_snippet = f"\n\n**代码 diff:**\n```\n{f.diff_content[:5000]}\n```"

            changes_detail.append(f"""
### {f.path}
- 变更类型: {f.change_type.value}
- 重要性: {f.significance.value}
- 变更统计: {f.stats}{diff_snippet}
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
请生成清晰、简洁的变更总结。

重要：你必须基于提供的 diff 内容和变更信息进行分析，不要推测代码变更的具体内容。
只描述你能从提供的信息中确认的变更。"""

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

        # 使用原子写入
        write_result = self._atomic_write(output_path, new_content)

        return json.dumps({
            "success": write_result["success"],
            "summary": summary,
            "output_file": str(output_path),
            "write_result": write_result
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
        """
        动态从 mcp_serve.py 解析 Tool 定义

        使用正则匹配 Tool(name="...", description="...") 模式，
        替代硬编码的工具列表，确保与实际代码同步。

        Returns:
            按功能分组的工具列表
        """
        mcp_serve_path = self.repo_root / "framework" / "mcp_serve.py"

        if not mcp_serve_path.exists():
            return []

        try:
            with open(mcp_serve_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 解析所有 Tool(name="...", description="...")
            tool_pattern = re.compile(
                r'Tool\(\s*name="([^"]+)"\s*,\s*description="([^"]+)"',
                re.MULTILINE
            )

            raw_tools = []
            for match in tool_pattern.finditer(content):
                raw_tools.append({
                    "name": match.group(1),
                    "description": match.group(2)
                })

            if not raw_tools:
                logger.warning("No tools parsed from mcp_serve.py")
                return []

            # 按前缀分组
            category_map = {
                "auth_": "认证与环境管理",
                "environment_": "认证与环境管理",
                "metadata_": "元数据管理",
                "naming_": "命名规则",
                "plugin_": "插件管理",
                "solution_": "解决方案管理",
                "doc_": "文档自动更新",
                "extension_": "其他",
                "health_": "其他",
            }

            categories: Dict[str, List[Dict]] = {}
            for tool in raw_tools:
                name = tool["name"]
                category = "其他"
                for prefix, cat_name in category_map.items():
                    if name.startswith(prefix):
                        category = cat_name
                        break

                if category not in categories:
                    categories[category] = []
                categories[category].append(tool)

            result = [
                {"category": cat, "tools": tools}
                for cat, tools in categories.items()
            ]

            return result

        except Exception as e:
            logger.error(f"Failed to parse mcp_serve.py: {e}")
            return []

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
