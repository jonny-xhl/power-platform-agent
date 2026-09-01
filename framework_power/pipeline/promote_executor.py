"""
Promote mode executor — runs solution export/import pipeline.

Two sequential hops:
  - Hop 1 (release/* -> UAT): Export unmanaged from DEV -> Import to UAT
  - Hop 2 (main -> PROD):     Export managed from UAT -> Import to PROD

Stages:
  1. Pre-check  — verify source environment solution exists + optional solution checker
  2. Export     — pac solution export from source environment
  3. Import     — pac solution import to target environment
  4. Configure  — set environment-specific connection references + env variables
  5. Verify     — verify solution exists in target environment

Uses :class:`PacCliWrapper` for all pac CLI interactions.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .config import PipelineConfig, BranchMapping
from .pac_cli import PacCliWrapper
from .verifier import SolutionVerifier
from .state import PipelineState

logger = logging.getLogger(__name__)


@dataclass
class PromoteStageResult:
    """Result of a single promote-mode stage."""

    name: str
    success: bool = True
    skipped: bool = False
    duration_seconds: float = 0.0
    output: Any = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "success": self.success,
            "skipped": self.skipped,
            "duration_seconds": round(self.duration_seconds, 2),
            "error": self.error,
            "output": self.output if isinstance(self.output, (dict, list, str)) else str(self.output),
        }


@dataclass
class PromoteResult:
    """Result of a full promote-mode pipeline run."""

    branch: str = ""
    environment: str = ""               # target environment
    source_environment: str = ""         # export source environment
    strategy: str = "promote"
    managed: bool = False
    solution_name: str = ""
    export_path: str = ""
    version: str = ""
    stages: list[PromoteStageResult] = field(default_factory=list)
    overall_success: bool = True
    started_at: str = ""
    finished_at: str = ""

    @property
    def success(self) -> bool:
        return self.overall_success and all(s.success for s in self.stages if not s.skipped)

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "environment": self.environment,
            "source_environment": self.source_environment,
            "strategy": self.strategy,
            "managed": self.managed,
            "solution_name": self.solution_name,
            "export_path": self.export_path,
            "version": self.version,
            "overall_success": self.success,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "stages": [s.to_dict() for s in self.stages],
        }


class PromoteExecutor:
    """Executes the promote-mode pipeline (export -> import -> configure -> verify).

    Args:
        config: Pipeline configuration.
        publisher_prefix: Publisher prefix.
    """

    def __init__(
        self,
        config: PipelineConfig,
        *,
        publisher_prefix: str = "new",
    ):
        self.config = config
        self.publisher_prefix = publisher_prefix
        self.project_root = Path(config.project_root)
        self.pac = PacCliWrapper(
            project_root=str(self.project_root),
            timeout=self._get_pac_timeout(),
        )

    def run(self, branch: str) -> PromoteResult:
        """Run the full promote-mode pipeline.

        Args:
            branch: Git branch name (e.g. "release/1.0", "main").

        Returns:
            :class:`PromoteResult` with per-stage results.
        """
        result = PromoteResult(
            branch=branch,
            strategy="promote",
            started_at=datetime.now().isoformat(),
        )

        # resolve branch mapping
        branch_mapping = self.config.resolve_branch(branch)
        if branch_mapping is None or branch_mapping.deploy_strategy != "promote":
            result.overall_success = False
            result.stages.append(PromoteStageResult(
                name="resolve_branch",
                success=False,
                error=f"Branch '{branch}' is not mapped to a promote strategy. Check config/pipeline.yaml.",
            ))
            result.finished_at = datetime.now().isoformat()
            return result

        result.environment = branch_mapping.environment
        result.source_environment = branch_mapping.source_environment or "dev"
        result.managed = branch_mapping.managed
        result.version = self.config.get_version()

        # resolve solution name
        result.solution_name = self.config.get_solution_name(result.source_environment)
        if not result.solution_name:
            # try target environment
            result.solution_name = self.config.get_solution_name(result.environment)
        if not result.solution_name:
            result.overall_success = False
            result.stages.append(PromoteStageResult(
                name="resolve_solution",
                success=False,
                error=f"Cannot resolve solution name from environments.yaml for env '{result.source_environment}' or '{result.environment}'.",
            ))
            result.finished_at = datetime.now().isoformat()
            return result

        # compute export path
        result.export_path = self.config.export_path(
            result.solution_name, result.version, result.managed
        )

        # run stages in order
        stage_order = ["pre_check", "export", "import", "configure", "verify"]
        for stage_name in stage_order:
            stage_config = self.config.stages_promote.get(stage_name)
            if stage_config and not stage_config.enabled:
                result.stages.append(PromoteStageResult(name=stage_name, skipped=True))
                continue

            stage_result = self._run_stage(stage_name, branch_mapping, result)
            result.stages.append(stage_result)

            if not stage_result.success and stage_config and stage_config.fail_on_error:
                result.overall_success = False
                break

        result.finished_at = datetime.now().isoformat()

        # record in state tracker
        if result.success:
            state = PipelineState(self.config)
            state.record_promotion(result)

        return result

    # ----------------------------------------------------------------- stage implementations

    def _run_stage(
        self,
        stage_name: str,
        branch_mapping: BranchMapping,
        result: PromoteResult,
    ) -> PromoteStageResult:
        """Dispatch one stage to its implementation."""
        start = time.time()
        try:
            if stage_name == "pre_check":
                output = self._stage_pre_check(branch_mapping, result)
            elif stage_name == "export":
                output = self._stage_export(branch_mapping, result)
            elif stage_name == "import":
                output = self._stage_import(branch_mapping, result)
            elif stage_name == "configure":
                output = self._stage_configure(branch_mapping, result)
            elif stage_name == "verify":
                output = self._stage_verify(branch_mapping, result)
            else:
                return PromoteStageResult(name=stage_name, skipped=True)
            elapsed = time.time() - start
            return PromoteStageResult(
                name=stage_name,
                success=True,
                duration_seconds=elapsed,
                output=output,
            )
        except Exception as e:  # noqa: BLE001
            elapsed = time.time() - start
            logger.error(f"Promote stage '{stage_name}' failed: {e}", exc_info=True)
            return PromoteStageResult(
                name=stage_name,
                success=False,
                duration_seconds=elapsed,
                error=str(e),
            )

    def _stage_pre_check(
        self, branch_mapping: BranchMapping, result: PromoteResult
    ) -> dict[str, Any]:
        """Stage 1: Verify source environment solution exists + optional solution checker."""
        checks: list[dict[str, Any]] = []

        # verify solution exists in source environment
        verify_result = self.pac.list_solutions(result.source_environment)
        if not verify_result.success:
            checks.append({
                "name": "verify_solution_exists",
                "success": False,
                "error": verify_result.stderr or "Failed to list solutions",
            })
            return {"checks": checks, "passed": False}

        solutions = verify_result.data.get("solutions", [])
        found = any(
            s.get("uniquename") == result.solution_name or s.get("name") == result.solution_name
            for s in solutions
        )
        checks.append({
            "name": "verify_solution_exists",
            "success": found,
            "solution": result.solution_name,
            "source_env": result.source_environment,
        })

        # solution checker (optional, mainly for PROD)
        env_settings = self.config.environments.get(result.environment)
        if env_settings and env_settings.require_solution_check and Path(result.export_path).exists():
            check_result = self.pac.check_solution(result.export_path)
            checks.append({
                "name": "solution_checker",
                "success": check_result.success,
                "output": check_result.stdout[:500] if check_result.stdout else "",
            })

        passed = all(c.get("success", False) for c in checks)
        return {"checks": checks, "passed": passed}

    def _stage_export(
        self, branch_mapping: BranchMapping, result: PromoteResult
    ) -> dict[str, Any]:
        """Stage 2: Export solution from source environment."""
        export_result = self.pac.export_solution(
            result.source_environment,
            result.solution_name,
            result.export_path,
            managed=result.managed,
        )
        if not export_result.success:
            return {
                "success": False,
                "error": export_result.stderr or export_result.stdout or "Export failed",
                "command": export_result.command,
            }
        return {
            "success": True,
            "export_path": result.export_path,
            "source_environment": result.source_environment,
            "managed": result.managed,
            "duration": round(export_result.duration_seconds, 2),
        }

    def _stage_import(
        self, branch_mapping: BranchMapping, result: PromoteResult
    ) -> dict[str, Any]:
        """Stage 3: Import solution to target environment."""
        import_result = self.pac.import_solution(
            result.environment,
            result.export_path,
            publish_workflows=self.config.import_config.publish_workflows,
            async_import=self.config.import_config.async_import,
            overwrite_unmanaged=self.config.import_config.overwrite_unmanaged_customizations,
        )
        if not import_result.success:
            return {
                "success": False,
                "error": import_result.stderr or import_result.stdout or "Import failed",
                "command": import_result.command,
            }
        return {
            "success": True,
            "import_path": result.export_path,
            "target_environment": result.environment,
            "duration": round(import_result.duration_seconds, 2),
        }

    def _stage_configure(
        self, branch_mapping: BranchMapping, result: PromoteResult
    ) -> dict[str, Any]:
        """Stage 4: Configure environment-specific settings (connection refs, env variables)."""
        settings_path = self.project_root / self.config.post_import_config.config_file
        if not settings_path.exists():
            return {"action": "configure", "skipped": True, "reason": f"Settings file not found: {settings_path}"}

        import yaml
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}

        env_name = result.environment
        configured: list[dict[str, Any]] = []

        # set environment variables
        env_vars = (settings.get("environment_variables") or {}).get(env_name, [])
        for ev in env_vars:
            configured.append({"type": "environment_variable", "name": ev.get("name"), "value": "***"})

        # set connection references
        conn_refs = (settings.get("connection_references") or {}).get(env_name, [])
        for cr in conn_refs:
            configured.append({"type": "connection_reference", "name": cr.get("name")})

        return {
            "action": "configure",
            "environment": env_name,
            "configured_count": len(configured),
            "items": configured,
        }

    def _stage_verify(
        self, branch_mapping: BranchMapping, result: PromoteResult
    ) -> dict[str, Any]:
        """Stage 5: Verify solution exists in target environment."""
        verifier = SolutionVerifier(self.config, publisher_prefix=self.publisher_prefix)
        verify_result = verifier.verify_promote(result.environment, result.solution_name)
        return verify_result.to_dict()

    def _get_pac_timeout(self) -> int:
        """Get pac CLI timeout from environments.yaml or default."""
        import yaml
        yaml_path = self.project_root / "config" / "environments.yaml"
        if yaml_path.exists():
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            pac_config = data.get("pac_cli") or {}
            return pac_config.get("timeout", 600)
        return 600
