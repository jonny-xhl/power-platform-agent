"""
Source mode executor — runs the full DEV deployment pipeline.

Stages (in order):
  1. Lint      — offline convention checks (no network)
  2. Build     — compile .NET plugins
  3. Compose   — auto-discover components from source, build dynamic Project
  4. Plan      — read-only dry-run against DEV
  5. Deploy    — write to DEV (framework_power workflow deploy)
  6. Verify    — check solution components match source
  7. Publish   — PublishAllXml

Only used for DEV environment. UAT/PROD use :class:`PromoteExecutor`.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .config import PipelineConfig, BranchMapping
from .composer import SolutionComposer, ComposeResult
from .verifier import SolutionVerifier
from .state import PipelineState

logger = logging.getLogger(__name__)


@dataclass
class StageResult:
    """Result of a single pipeline stage."""

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
class SourceResult:
    """Result of a full source-mode pipeline run."""

    branch: str = ""
    environment: str = ""
    strategy: str = "source"
    version: str = ""
    stages: list[StageResult] = field(default_factory=list)
    compose_result: Optional[ComposeResult] = None
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
            "strategy": self.strategy,
            "version": self.version,
            "overall_success": self.success,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "stages": [s.to_dict() for s in self.stages],
            "compose_result": self.compose_result.to_dict() if self.compose_result else None,
        }


class SourceExecutor:
    """Executes the source-mode pipeline (lint -> build -> compose -> plan -> deploy -> verify -> publish).

    Args:
        config: Pipeline configuration.
        publisher_prefix: Publisher prefix for custom component filtering.
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

    def run(
        self,
        branch: str,
        *,
        stop_after: Optional[str] = None,
        skip_stages: Optional[set[str]] = None,
    ) -> SourceResult:
        """Run the full source-mode pipeline.

        Args:
            branch: Git branch name (e.g. "develop", "feature/CPQ").
            stop_after: Stop after this stage (e.g. "plan" for dry-run).
            skip_stages: Set of stage names to skip.

        Returns:
            :class:`SourceResult` with per-stage results.
        """
        result = SourceResult(
            branch=branch,
            strategy="source",
            started_at=datetime.now().isoformat(),
        )

        branch_mapping = self.config.resolve_branch(branch)
        if branch_mapping is None:
            result.overall_success = False
            result.stages.append(StageResult(
                name="resolve_branch",
                success=False,
                error=f"No pipeline mapping for branch '{branch}'. Check config/pipeline.yaml.",
            ))
            result.finished_at = datetime.now().isoformat()
            return result

        result.environment = branch_mapping.environment
        plan_only = branch_mapping.plan_only

        skip = skip_stages or set()
        if plan_only:
            # feature branches: stop after plan
            stop_after = "plan"

        # stage order
        stage_order = ["lint", "build", "compose", "plan", "deploy", "verify", "publish"]

        for stage_name in stage_order:
            if stage_name in skip:
                result.stages.append(StageResult(name=stage_name, skipped=True))
                continue

            stage_config = self.config.stages_source.get(stage_name)
            if stage_config and not stage_config.enabled:
                result.stages.append(StageResult(name=stage_name, skipped=True))
                continue

            stage_result = self._run_stage(stage_name, branch, branch_mapping, result)
            result.stages.append(stage_result)

            if not stage_result.success and stage_config and stage_config.fail_on_error:
                result.overall_success = False
                break

            if stop_after and stage_name == stop_after:
                break

        result.finished_at = datetime.now().isoformat()
        return result

    # ----------------------------------------------------------------- stage implementations

    def _run_stage(
        self,
        stage_name: str,
        branch: str,
        branch_mapping: BranchMapping,
        result: SourceResult,
    ) -> StageResult:
        """Dispatch one stage to its implementation."""
        start = time.time()
        try:
            if stage_name == "lint":
                output = self._stage_lint()
            elif stage_name == "build":
                output = self._stage_build()
            elif stage_name == "compose":
                compose_result = self._stage_compose(branch)
                result.compose_result = compose_result
                output = compose_result.to_dict()
            elif stage_name == "plan":
                output = self._stage_plan(branch_mapping.environment, result.compose_result)
            elif stage_name == "deploy":
                output = self._stage_deploy(branch_mapping.environment, result.compose_result)
            elif stage_name == "verify":
                output = self._stage_verify(branch_mapping.environment, result.compose_result)
            elif stage_name == "publish":
                output = self._stage_publish(branch_mapping.environment)
            else:
                return StageResult(name=stage_name, skipped=True)
            elapsed = time.time() - start
            return StageResult(
                name=stage_name,
                success=True,
                duration_seconds=elapsed,
                output=output,
            )
        except Exception as e:  # noqa: BLE001
            elapsed = time.time() - start
            logger.error(f"Stage '{stage_name}' failed: {e}", exc_info=True)
            return StageResult(
                name=stage_name,
                success=False,
                duration_seconds=elapsed,
                error=str(e),
            )

    def _stage_lint(self) -> dict[str, Any]:
        """Stage 1: Offline lint checks."""
        from ..workflow import lint_workflow, load_project
        from ..lint import has_errors

        project_path = self.project_root / "metadata_py" / "project.py"
        if project_path.exists():
            project = load_project(str(project_path))
            issues = lint_workflow(project, prefix=self.publisher_prefix)
            errors = [i for i in issues if i.severity == "ERROR"]
            return {
                "action": "lint",
                "issues_count": len(issues),
                "errors_count": len(errors),
                "has_errors": has_errors(issues),
            }
        return {"action": "lint", "note": "No project.py found, skipping workflow lint"}

    def _stage_build(self) -> dict[str, Any]:
        """Stage 2: Build .NET plugins (if any plugin projects exist)."""
        plugins_dir = self.project_root / "plugins"
        if not plugins_dir.is_dir():
            return {"action": "build", "note": "No plugins/ directory, skipping build"}

        built = []
        errors = []
        for plugin_dir in sorted(plugins_dir.iterdir()):
            if not plugin_dir.is_dir():
                continue
            def_file = plugin_dir / "plugin_def.py"
            if not def_file.exists():
                continue
            try:
                from ..client.plugin_build import build_plugin_project, load_plugin_project
                cfg = load_plugin_project(def_file)
                plugin = build_plugin_project(str(plugin_dir), config=cfg)
                built.append({
                    "name": plugin.name,
                    "version": plugin.version,
                    "steps": len(plugin.steps),
                })
            except Exception as e:  # noqa: BLE001
                errors.append({"project": str(plugin_dir), "error": str(e)})

        return {"action": "build", "built": built, "errors": errors}

    def _stage_compose(self, branch: str) -> ComposeResult:
        """Stage 3: Dynamic component discovery."""
        composer = SolutionComposer(self.config, publisher_prefix=self.publisher_prefix)
        return composer.compose(branch)

    def _stage_plan(
        self, env: str, compose_result: Optional[ComposeResult]
    ) -> dict[str, Any]:
        """Stage 4: Read-only dry-run against DEV."""
        from ..runtime import get_client
        from ..workflow import plan_workflow

        if compose_result is None:
            return {"action": "plan", "error": "No compose result — compose stage must run first"}

        composer = SolutionComposer(self.config, publisher_prefix=self.publisher_prefix)
        project = composer.to_project(compose_result)
        client = get_client(env)
        return plan_workflow(client, project, prefix=self.publisher_prefix)

    def _stage_deploy(
        self, env: str, compose_result: Optional[ComposeResult]
    ) -> dict[str, Any]:
        """Stage 5: Deploy to DEV (source code -> unmanaged solution)."""
        from ..runtime import get_client
        from ..workflow import deploy_workflow

        if compose_result is None:
            return {"action": "deploy", "error": "No compose result — compose stage must run first"}

        composer = SolutionComposer(self.config, publisher_prefix=self.publisher_prefix)
        project = composer.to_project(compose_result)
        client = get_client(env)
        return deploy_workflow(client, project, prefix=self.publisher_prefix)

    def _stage_verify(
        self, env: str, compose_result: Optional[ComposeResult]
    ) -> dict[str, Any]:
        """Stage 6: Verify solution components match source."""
        if compose_result is None:
            return {"action": "verify", "error": "No compose result"}

        verifier = SolutionVerifier(self.config, publisher_prefix=self.publisher_prefix)
        verify_result = verifier.verify_source(env, compose_result)
        return verify_result.to_dict()

    def _stage_publish(self, env: str) -> dict[str, Any]:
        """Stage 7: PublishAllXml."""
        from ..runtime import get_client

        client = get_client(env)
        return client.publish_all_xml()
