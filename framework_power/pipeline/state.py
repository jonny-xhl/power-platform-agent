"""
Deployment state tracking for the pipeline engine.

Records each deployment (source or promote) to ``.pp-local/pipeline-state.json``
for history, rollback, and audit purposes.

State structure::

    {
      "deployments": [
        {
          "id": "20260723-200000-dev-source",
          "timestamp": "2026-07-23T20:00:00",
          "type": "source|promote",
          "branch": "develop",
          "environment": "dev",
          "source_environment": null,      // promote only
          "solution_name": "new_WorkflowSoln",
          "version": "1.0.42.0",
          "managed": false,
          "success": true,
          "export_path": null,             // promote only
          "stages": [...]
        }
      ]
    }
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .config import PipelineConfig

logger = logging.getLogger(__name__)

STATE_FILE = ".pp-local/pipeline-state.json"


@dataclass
class DeploymentRecord:
    """A single deployment record."""

    id: str = ""
    timestamp: str = ""
    type: str = ""               # "source" | "promote"
    branch: str = ""
    environment: str = ""
    source_environment: Optional[str] = None
    solution_name: str = ""
    version: str = ""
    managed: bool = False
    success: bool = True
    export_path: Optional[str] = None
    stages: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "type": self.type,
            "branch": self.branch,
            "environment": self.environment,
            "source_environment": self.source_environment,
            "solution_name": self.solution_name,
            "version": self.version,
            "managed": self.managed,
            "success": self.success,
            "export_path": self.export_path,
            "stages": self.stages,
        }


class PipelineState:
    """Manages deployment state persistence.

    Args:
        config: Pipeline configuration (for project_root and rollback settings).
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.state_path = Path(config.project_root) / STATE_FILE

    def load(self) -> dict[str, Any]:
        """Load the full state file."""
        if not self.state_path.exists():
            return {"deployments": []}
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"deployments": []}

    def save(self, state: dict[str, Any]) -> None:
        """Save the full state file."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False, default=str)

    def add_record(self, record: DeploymentRecord) -> None:
        """Add a deployment record and prune old entries."""
        state = self.load()
        deployments = state.get("deployments", [])
        deployments.append(record.to_dict())

        # prune: keep last N per environment
        keep = self.config.rollback.keep_history
        if keep > 0:
            # group by environment, keep last N of each
            by_env: dict[str, list[dict[str, Any]]] = {}
            for d in deployments:
                env = d.get("environment", "unknown")
                by_env.setdefault(env, []).append(d)
            pruned: list[dict[str, Any]] = []
            for env, recs in by_env.items():
                pruned.extend(recs[-keep:])
            deployments = pruned

        state["deployments"] = deployments
        self.save(state)

    def record_source(self, result: Any) -> None:
        """Record a source-mode deployment result."""
        record = DeploymentRecord(
            id=self._make_id(result.environment, "source"),
            timestamp=datetime.now().isoformat(),
            type="source",
            branch=result.branch,
            environment=result.environment,
            solution_name=result.compose_result.solution_name if result.compose_result else "",
            version=result.version,
            managed=False,
            success=result.success,
            stages=[s.to_dict() for s in result.stages],
        )
        self.add_record(record)

    def record_promotion(self, result: Any) -> None:
        """Record a promote-mode deployment result."""
        record = DeploymentRecord(
            id=self._make_id(result.environment, "promote"),
            timestamp=datetime.now().isoformat(),
            type="promote",
            branch=result.branch,
            environment=result.environment,
            source_environment=result.source_environment,
            solution_name=result.solution_name,
            version=result.version,
            managed=result.managed,
            success=result.success,
            export_path=result.export_path,
            stages=[s.to_dict() for s in result.stages],
        )
        self.add_record(record)

    def get_history(
        self, *, environment: Optional[str] = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Get deployment history, optionally filtered by environment."""
        state = self.load()
        deployments = state.get("deployments", [])
        if environment:
            deployments = [d for d in deployments if d.get("environment") == environment]
        # most recent first
        deployments = sorted(deployments, key=lambda d: d.get("timestamp", ""), reverse=True)
        return deployments[:limit]

    def get_rollback_target(
        self, environment: str, version: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """Find a previous successful deployment for rollback.

        Args:
            environment: Target environment.
            version: Specific version to rollback to (if None, find the previous successful one).
        """
        history = self.get_history(environment=environment, limit=50)
        if not history:
            return None

        successful = [d for d in history if d.get("success")]
        if not successful:
            return None

        if version:
            for d in successful:
                if d.get("version") == version:
                    return d
            return None

        # return the second most recent (the one before the latest)
        if len(successful) >= 2:
            return successful[1]
        return None

    @staticmethod
    def _make_id(env: str, deploy_type: str) -> str:
        """Generate a unique deployment ID."""
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{ts}-{env}-{deploy_type}"
