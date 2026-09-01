"""
Pipeline configuration model and YAML loader.

Parses ``config/pipeline.yaml`` into typed dataclasses:
  - Branch -> environment -> deploy_strategy mapping
  - Source mode discovery rules (auto-discover components from source)
  - Promote mode export/import settings
  - Stage configurations for both modes
  - Rollback / notification settings

The config is project-agnostic: all paths are relative to the project root
(the working directory where the pipeline is invoked), not hardcoded to any
specific repository.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

DEFAULT_PIPELINE_CONFIG = "config/pipeline.yaml"


# ----------------------------------------------------------------- branch mapping


@dataclass
class BranchMapping:
    """Resolved branch -> environment -> strategy mapping."""

    branch_pattern: str           # e.g. "develop", "feature/*", "release/*", "main"
    environment: str              # e.g. "dev", "test", "production"
    deploy_strategy: str          # "source" | "promote"
    auto_run: bool = True
    plan_only: bool = False
    require_approval: bool = False
    approvers: list[str] = field(default_factory=list)
    managed: bool = False
    source_environment: Optional[str] = None   # for promote mode: where to export from
    pre_deploy_hooks: list[str] = field(default_factory=list)
    post_deploy_hooks: list[str] = field(default_factory=list)


# ----------------------------------------------------------------- discovery rules


@dataclass
class DiscoveryRule:
    """How to discover one component type from source."""

    source: str                   # relative path, e.g. "metadata_py/tables/"
    pattern: str = "*.py"
    exclude: list[str] = field(default_factory=lambda: ["__init__.py"])
    filter_custom: bool = False   # skip files not starting with publisher prefix
    sync_all: bool = False        # for webresources: sync the whole dir
    detect_by: Optional[str] = None  # for plugins: detect subdirs containing this file


@dataclass
class SolutionSplit:
    """Solution splitting strategy."""

    strategy: str = "two_solution"  # "single" | "two_solution"
    main_solution_template: str = "{publisher}_{project}"
    ribbon_solution_template: str = "{publisher}_{project}_Ribbon"


@dataclass
class VersioningConfig:
    """Version strategy for solutions."""

    strategy: str = "manual"        # "manual" | "git_tags" | "file_tracking"
    git_tag_pattern: str = "v*"
    default_version: str = "1.0.0.0"


# ----------------------------------------------------------------- stage configs


@dataclass
class StageConfig:
    """Configuration for a single pipeline stage."""

    name: str
    enabled: bool = True
    fail_on_error: bool = True
    command: Optional[str] = None
    save_output: Optional[str] = None
    checks: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)


# ----------------------------------------------------------------- promote config


@dataclass
class ExportConfig:
    """Solution export configuration (promote mode)."""

    output_dir: str = ".pp-local/exports/"
    filename_template: str = "{solution_name}_{version}_{managed_or_unmanaged}.zip"
    run_checker: bool = False


@dataclass
class ImportConfig:
    """Solution import configuration (promote mode)."""

    async_import: bool = True
    publish_workflows: bool = True
    overwrite_unmanaged_customizations: bool = False
    skip_dependency_check: bool = False


@dataclass
class PostImportConfig:
    """Post-import environment configuration."""

    config_file: str = "config/environment_settings.yaml"


# ----------------------------------------------------------------- environment settings


@dataclass
class EnvironmentSettings:
    """Per-environment pipeline settings."""

    deploy_on_merge: bool = True
    deploy_strategy: str = "source"
    managed: bool = False
    source_environment: Optional[str] = None
    notify_on_success: bool = False
    notify_on_failure: bool = True
    require_approval: bool = False
    require_solution_check: bool = False
    backup_before_deploy: bool = False
    backup_path: str = ".pp-local/backups/"


# ----------------------------------------------------------------- rollback config


@dataclass
class RollbackConfig:
    """Rollback configuration."""

    enabled: bool = True
    strategy: str = "solution_reimport"
    keep_history: int = 5
    auto_rollback: bool = False


# ----------------------------------------------------------------- main config


@dataclass
class PipelineConfig:
    """Full pipeline configuration parsed from config/pipeline.yaml."""

    branches: dict[str, BranchMapping] = field(default_factory=dict)
    # source mode
    discovery: dict[str, DiscoveryRule] = field(default_factory=dict)
    solution_split: SolutionSplit = field(default_factory=SolutionSplit)
    versioning: VersioningConfig = field(default_factory=VersioningConfig)
    source_overrides: dict[str, Any] = field(default_factory=dict)
    # promote mode
    export_config: ExportConfig = field(default_factory=ExportConfig)
    import_config: ImportConfig = field(default_factory=ImportConfig)
    post_import_config: PostImportConfig = field(default_factory=PostImportConfig)
    # stages
    stages_source: dict[str, StageConfig] = field(default_factory=dict)
    stages_promote: dict[str, StageConfig] = field(default_factory=dict)
    # environments
    environments: dict[str, EnvironmentSettings] = field(default_factory=dict)
    # rollback
    rollback: RollbackConfig = field(default_factory=RollbackConfig)
    # raw config for reference
    raw: dict[str, Any] = field(default_factory=dict)
    # project root (cwd where pipeline is invoked)
    project_root: str = "."

    # ----- branch resolution -----

    def resolve_branch(self, branch: str) -> Optional[BranchMapping]:
        """Resolve a branch name to its BranchMapping.

        Supports glob patterns: ``feature/*`` matches ``feature/CPQ-module``.
        Exact matches take priority over glob patterns.
        """
        # 1. exact match
        if branch in self.branches:
            return self.branches[branch]
        # 2. glob match
        for pattern, mapping in self.branches.items():
            if "*" in pattern or "?" in pattern:
                if fnmatch.fnmatch(branch, pattern):
                    return mapping
        return None

    def get_solution_name(self, env_name: str, environments_yaml_path: str = "config/environments.yaml") -> str:
        """Read solution name from environments.yaml for a given environment."""
        env_path = Path(self.project_root) / environments_yaml_path
        if not env_path.exists():
            return ""
        with open(env_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        envs = data.get("environments", {})
        env_config = envs.get(env_name, {})
        sol = env_config.get("solution", {})
        return sol.get("name", "")

    def get_version(self) -> str:
        """Get solution version based on versioning strategy."""
        if self.versioning.strategy == "git_tags":
            return self._version_from_git_tags()
        return self.versioning.default_version

    def _version_from_git_tags(self) -> str:
        """Extract version from latest git tag matching the pattern."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                capture_output=True, text=True, timeout=10,
                cwd=self.project_root,
            )
            if result.returncode == 0:
                tag = result.stdout.strip()
                # strip leading 'v' if present
                version = tag.lstrip("v")
                # ensure 4-part version
                parts = version.split(".")
                while len(parts) < 4:
                    parts.append("0")
                return ".".join(parts[:4])
        except Exception:  # noqa: BLE001
            pass
        return self.versioning.default_version

    def export_path(self, solution_name: str, version: str, managed: bool) -> str:
        """Build the export file path for a solution."""
        managed_str = "managed" if managed else "unmanaged"
        filename = self.export_config.filename_template.format(
            solution_name=solution_name,
            version=version,
            managed_or_unmanaged=managed_str,
        )
        return str(Path(self.project_root) / self.export_config.output_dir / filename)


# ----------------------------------------------------------------- loader


def load_pipeline_config(
    config_path: str = DEFAULT_PIPELINE_CONFIG,
    *,
    project_root: str = ".",
) -> PipelineConfig:
    """Load pipeline configuration from YAML.

    Args:
        config_path: Path to pipeline.yaml (relative to project_root or absolute).
        project_root: The project root directory (usually cwd).

    Returns:
        Parsed :class:`PipelineConfig`.
    """
    full_path = Path(project_root) / config_path if not Path(config_path).is_absolute() else Path(config_path)
    if not full_path.exists():
        raise FileNotFoundError(
            f"Pipeline config not found: {full_path}\n"
            "Create config/pipeline.yaml — see docs/references/pac-cli/cicd-pipeline-enhancement-plan.md"
        )

    with open(full_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    config = PipelineConfig(raw=raw, project_root=str(project_root))

    # parse branches
    for pattern, bdata in (raw.get("branches") or {}).items():
        config.branches[pattern] = BranchMapping(
            branch_pattern=pattern,
            environment=bdata.get("environment", "dev"),
            deploy_strategy=bdata.get("deploy_strategy", "source"),
            auto_run=bdata.get("auto_run", True),
            plan_only=bdata.get("plan_only", False),
            require_approval=bdata.get("require_approval", False),
            approvers=bdata.get("approvers", []),
            managed=bdata.get("managed", False),
            source_environment=bdata.get("source_environment"),
            pre_deploy_hooks=bdata.get("pre_deploy_hooks", []),
            post_deploy_hooks=bdata.get("post_deploy_hooks", []),
        )

    # parse source mode discovery
    source_mode = raw.get("source_mode") or {}
    discovery = source_mode.get("discovery") or {}
    for comp_type, drules in discovery.items():
        config.discovery[comp_type] = DiscoveryRule(
            source=drules.get("source", ""),
            pattern=drules.get("pattern", "*.py"),
            exclude=drules.get("exclude", ["__init__.py"]),
            filter_custom=drules.get("filter_custom", False),
            sync_all=drules.get("sync_all", False),
            detect_by=drules.get("detect_by"),
        )
    config.source_overrides = source_mode.get("overrides") or {}

    # solution split
    split = source_mode.get("solution_split") or {}
    config.solution_split = SolutionSplit(
        strategy=split.get("strategy", "two_solution"),
        main_solution_template=split.get("two_solution", {}).get("main_solution", {}).get(
            "name_template", "{publisher}_{project}"
        ),
        ribbon_solution_template=split.get("two_solution", {}).get("ribbon_solution", {}).get(
            "name_template", "{publisher}_{project}_Ribbon"
        ),
    )

    # versioning
    ver = source_mode.get("versioning") or {}
    config.versioning = VersioningConfig(
        strategy=ver.get("strategy", "manual"),
        git_tag_pattern=ver.get("git_tags", {}).get("pattern", "v*"),
        default_version=ver.get("git_tags", {}).get("default", "1.0.0.0"),
    )

    # promote mode
    promote_mode = raw.get("promote_mode") or {}
    exp = promote_mode.get("export") or {}
    config.export_config = ExportConfig(
        output_dir=exp.get("output_dir", ".pp-local/exports/"),
        filename_template=exp.get("filename_template", "{solution_name}_{version}_{managed_or_unmanaged}.zip"),
        run_checker=exp.get("run_checker", False),
    )
    imp = promote_mode.get("import") or {}
    config.import_config = ImportConfig(
        async_import=imp.get("async", True),
        publish_workflows=imp.get("publish_workflows", True),
        overwrite_unmanaged_customizations=imp.get("overwrite_unmanaged_customizations", False),
        skip_dependency_check=imp.get("skip_dependency_check", False),
    )
    pic = promote_mode.get("post_import_config") or {}
    config.post_import_config = PostImportConfig(
        config_file=pic.get("config_file", "config/environment_settings.yaml"),
    )

    # stages
    for name, sdata in (raw.get("stages_source") or {}).items():
        config.stages_source[name] = _parse_stage(name, sdata)
    for name, sdata in (raw.get("stages_promote") or {}).items():
        config.stages_promote[name] = _parse_stage(name, sdata)

    # environments
    for env_name, edata in (raw.get("environments") or {}).items():
        config.environments[env_name] = EnvironmentSettings(
            deploy_on_merge=edata.get("deploy_on_merge", True),
            deploy_strategy=edata.get("deploy_strategy", "source"),
            managed=edata.get("managed", False),
            source_environment=edata.get("source_environment"),
            notify_on_success=edata.get("notify_on_success", False),
            notify_on_failure=edata.get("notify_on_failure", True),
            require_approval=edata.get("require_approval", False),
            require_solution_check=edata.get("require_solution_check", False),
            backup_before_deploy=edata.get("backup_before_deploy", False),
            backup_path=edata.get("backup_path", ".pp-local/backups/"),
        )

    # rollback
    rb = raw.get("rollback") or {}
    config.rollback = RollbackConfig(
        enabled=rb.get("enabled", True),
        strategy=rb.get("strategy", "solution_reimport"),
        keep_history=rb.get("keep_history", 5),
        auto_rollback=rb.get("auto_rollback", False),
    )

    return config


def _parse_stage(name: str, sdata: dict[str, Any]) -> StageConfig:
    """Parse a stage config dict into StageConfig."""
    return StageConfig(
        name=name,
        enabled=sdata.get("enabled", True),
        fail_on_error=sdata.get("fail_on_error", True),
        command=sdata.get("command"),
        save_output=sdata.get("save_output"),
        checks=sdata.get("checks", []),
        steps=sdata.get("steps", []),
    )
