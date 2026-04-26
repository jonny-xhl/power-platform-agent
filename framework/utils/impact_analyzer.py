"""
Impact Analyzer - 影响分析器

分析代码变更对文档的影响，判断哪些文档需要更新
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from pathlib import Path


# 导入 change_detector 模块的类型
class ChangedFile:
    """变更文件（类型声明）"""
    pass


class ChangeReport:
    """变更报告（类型声明）"""
    pass


class Significance:
    """变更重要性（类型声明）"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSIGNIFICANT = "insignificant"


@dataclass
class ImpactRule:
    """影响规则"""
    name: str
    patterns: List[str]          # 文件路径模式
    affects: List[str]           # 影响的文档
    confidence: float            # 置信度 (0-1)
    impact_type: str             # 影响类型


@dataclass
class DocumentImpact:
    """文档影响"""
    doc_path: str                # 文档路径
    impact_type: str             # 影响类型
    confidence: float            # 置信度
    related_changes: List[str]   # 相关的变更文件
    suggested_action: str        # 建议操作


@dataclass
class ImpactReport:
    """影响报告"""
    impacts: List[DocumentImpact] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    @property
    def affected_docs(self) -> List[str]:
        """受影响的文档列表"""
        return [impact.doc_path for impact in self.impacts]

    @property
    def high_confidence_impacts(self) -> List[DocumentImpact]:
        """高置信度的影响"""
        return [i for i in self.impacts if i.confidence >= 0.7]

    @property
    def medium_confidence_impacts(self) -> List[DocumentImpact]:
        """中等置信度的影响"""
        return [i for i in self.impacts if 0.4 <= i.confidence < 0.7]


class ImpactAnalyzer:
    """影响分析器"""

    # 默认影响规则
    DEFAULT_RULES = [
        ImpactRule(
            name="mcp_tools",
            patterns=[r"framework/mcp_serve\.py"],
            affects=["CLAUDE.md"],
            confidence=0.9,
            impact_type="mcp_tools"
        ),
        ImpactRule(
            name="agent_api",
            patterns=[r"framework/agents/.*\.py"],
            affects=["CLAUDE.md", "docs/spec/architecture.md"],
            confidence=0.7,
            impact_type="agent_api"
        ),
        ImpactRule(
            name="skill_definition",
            patterns=[r"\.claude/skills/[^/]+/", r"\.claude/skills/[^/]+/SKILL\.md"],
            affects=["self", "CLAUDE.md"],
            confidence=0.8,
            impact_type="skill_definition"
        ),
        ImpactRule(
            name="skill_script",
            patterns=[r"\.claude/skills/[^/]+/scripts/.*\.py"],
            affects=["self"],
            confidence=0.6,
            impact_type="skill_implementation"
        ),
        ImpactRule(
            name="config_change",
            patterns=[r"config/.*\.yaml"],
            affects=["CLAUDE.md", "docs/guides/getting-started.md"],
            confidence=0.6,
            impact_type="configuration"
        ),
        ImpactRule(
            name="metadata_schema",
            patterns=[r"metadata/_schema/.*\.yaml"],
            affects=["docs/data_dictionary/", "CLAUDE.md"],
            confidence=0.7,
            impact_type="metadata_schema"
        ),
        ImpactRule(
            name="metadata_table",
            patterns=[r"metadata/tables/.*\.yaml"],
            affects=["docs/data_dictionary/"],
            confidence=0.5,
            impact_type="metadata_definition"
        ),
        ImpactRule(
            name="naming_rules",
            patterns=[r"config/naming_rules\.yaml", r"framework/utils/naming_converter\.py"],
            affects=["CLAUDE.md", "docs/spec/architecture.md"],
            confidence=0.8,
            impact_type="naming_rules"
        ),
        ImpactRule(
            name="dataverse_client",
            patterns=[r"framework/utils/dataverse_client\.py"],
            affects=["CLAUDE.md", "docs/spec/architecture.md"],
            confidence=0.7,
            impact_type="api_client"
        ),
        ImpactRule(
            name="hook_changes",
            patterns=[r"scripts/hooks/.*"],
            affects=["CLAUDE.md", "docs/guides/getting-started.md"],
            confidence=0.6,
            impact_type="hooks"
        ),
    ]

    def __init__(
        self,
        rules: Optional[List[ImpactRule]] = None,
        confidence_threshold: float = 0.5
    ):
        """
        初始化影响分析器

        Args:
            rules: 影响规则
            confidence_threshold: 置信度阈值
        """
        self.rules = rules or self.DEFAULT_RULES.copy()
        self.confidence_threshold = confidence_threshold
        self._compile_patterns()

    def _compile_patterns(self):
        """编译正则表达式模式"""
        for rule in self.rules:
            rule.compiled_patterns = [
                re.compile(pattern) for pattern in rule.patterns
            ]

    def analyze(self, changes: ChangeReport) -> ImpactReport:
        """
        分析代码变更对文档的影响

        Args:
            changes: 变更报告

        Returns:
            影响报告
        """
        report = ImpactReport()
        impacts_dict: Dict[str, DocumentImpact] = {}

        for changed_file in changes.files:
            # 跳过低重要性的变更
            if changed_file.significance == Significance.INSIGNIFICANT:
                continue

            for rule in self.rules:
                # 检查文件是否匹配规则
                if not self._matches_rule(changed_file.path, rule):
                    continue

                # 根据变更重要性调整置信度
                adjusted_confidence = self._adjust_confidence(
                    rule.confidence,
                    changed_file.significance
                )

                # 如果置信度低于阈值，跳过
                if adjusted_confidence < self.confidence_threshold:
                    continue

                # 处理影响的文档
                for doc_path in rule.affects:
                    if doc_path == "self":
                        # 特殊处理：SKILL 自更新
                        doc_path = self._find_skill_document(changed_file.path)

                    if not doc_path:
                        continue

                    # 合并或创建影响记录
                    if doc_path not in impacts_dict:
                        impacts_dict[doc_path] = DocumentImpact(
                            doc_path=doc_path,
                            impact_type=rule.impact_type,
                            confidence=adjusted_confidence,
                            related_changes=[changed_file.path],
                            suggested_action=self._get_suggested_action(
                                doc_path, rule.impact_type
                            )
                        )
                    else:
                        # 更新置信度（取最高值）
                        existing = impacts_dict[doc_path]
                        if adjusted_confidence > existing.confidence:
                            existing.confidence = adjusted_confidence
                            existing.impact_type = rule.impact_type
                            existing.suggested_action = self._get_suggested_action(
                                doc_path, rule.impact_type
                            )

                        # 添加相关变更
                        if changed_file.path not in existing.related_changes:
                            existing.related_changes.append(changed_file.path)

        report.impacts = sorted(
            list(impacts_dict.values()),
            key=lambda x: x.confidence,
            reverse=True
        )

        # 生成摘要
        report.summary = {
            "total_impacts": len(report.impacts),
            "high_confidence": len(report.high_confidence_impacts),
            "medium_confidence": len(report.medium_confidence_impacts),
            "affected_docs": report.affected_docs,
            "impact_types": list(set(i.impact_type for i in report.impacts))
        }

        return report

    def _matches_rule(self, file_path: str, rule: ImpactRule) -> bool:
        """
        检查文件是否匹配规则

        Args:
            file_path: 文件路径
            rule: 影响规则

        Returns:
            是否匹配
        """
        for pattern in getattr(rule, 'compiled_patterns', []):
            if pattern.search(file_path):
                return True
        return False

    def _adjust_confidence(
        self,
        base_confidence: float,
        significance: Significance
    ) -> float:
        """
        根据变更重要性调整置信度

        Args:
            base_confidence: 基础置信度
            significance: 变更重要性

        Returns:
            调整后的置信度
        """
        multipliers = {
            Significance.HIGH: 1.0,
            Significance.MEDIUM: 0.8,
            Significance.LOW: 0.5,
            Significance.INSIGNIFICANT: 0.0,
        }
        return base_confidence * multipliers.get(significance, 1.0)

    def _find_skill_document(self, file_path: str) -> Optional[str]:
        """
        查找 SKILL 文档路径

        Args:
            file_path: 变更文件路径

        Returns:
            SKILL 文档路径
        """
        path = Path(file_path)

        # 检查是否在技能目录中
        parts = path.parts
        if ".claude" in parts and "skills" in parts:
            try:
                skills_idx = parts.index("skills")
                if skills_idx + 1 < len(parts):
                    skill_name = parts[skills_idx + 1]
                    return f".claude/skills/{skill_name}/SKILL.md"
            except ValueError:
                pass

        return None

    def _get_suggested_action(self, doc_path: str, impact_type: str) -> str:
        """
        获取建议操作

        Args:
            doc_path: 文档路径
            impact_type: 影响类型

        Returns:
            建议操作
        """
        actions = {
            "mcp_tools": "更新 MCP 工具列表和描述",
            "agent_api": "更新代理 API 说明",
            "skill_definition": "更新 SKILL 文档",
            "skill_implementation": "检查 SKILL 实现与文档是否一致",
            "configuration": "更新配置说明",
            "metadata_schema": "更新元数据 schema 文档",
            "metadata_definition": "更新数据字典",
            "naming_rules": "更新命名规则说明",
            "api_client": "更新 API 客户端文档",
            "hooks": "更新 hooks 说明",
        }
        return actions.get(impact_type, "检查并更新相关文档")

    def load_rules_from_config(self, config_path: str) -> None:
        """
        从配置文件加载规则

        Args:
            config_path: 配置文件路径
        """
        import yaml

        config_file = Path(config_path)
        if not config_file.exists():
            return

        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        rules = []
        for rule_config in config.get("impact_rules", []):
            rules.append(ImpactRule(
                name=rule_config["name"],
                patterns=rule_config["patterns"],
                affects=rule_config["affects"],
                confidence=rule_config.get("confidence", 0.7),
                impact_type=rule_config.get("impact_type", "general")
            ))

        if rules:
            self.rules = rules
            self._compile_patterns()

    def get_doc_update_strategy(
        self,
        doc_path: str
    ) -> str:
        """
        获取文档更新策略

        Args:
            doc_path: 文档路径

        Returns:
            更新策略: auto, suggest, interactive
        """
        # 默认策略
        default_strategies = {
            "CLAUDE.md": "suggest",
            ".claude/skills/": "auto",
            "docs/data_dictionary/": "auto",
            "CHANGELOG.md": "auto",
        }

        for pattern, strategy in default_strategies.items():
            if doc_path.startswith(pattern) or pattern in doc_path:
                return strategy

        return "suggest"
