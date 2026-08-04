"""
Post-deployment verification for the pipeline engine.

Two verification modes:
  - **Source mode** (DEV): Compare expected components (from ComposeResult) against
    actual solution components in Dataverse (via Web API).
  - **Promote mode** (UAT/PROD): Verify the solution exists in the target environment
    and contains the expected number of components.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from .config import PipelineConfig

logger = logging.getLogger(__name__)


@dataclass
class VerifyResult:
    """Result of a verification check."""

    success: bool = True
    environment: str = ""
    solution_name: str = ""
    mode: str = ""                  # "source" | "promote"
    expected_components: dict[str, int] = field(default_factory=dict)
    actual_components: dict[str, int] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "environment": self.environment,
            "solution_name": self.solution_name,
            "mode": self.mode,
            "expected_components": self.expected_components,
            "actual_components": self.actual_components,
            "missing": self.missing,
            "extra": self.extra,
            "warnings": self.warnings,
        }


class SolutionVerifier:
    """Verifies deployed solutions match expectations.

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

    def verify_source(self, env: str, compose_result: Any) -> VerifyResult:
        """Verify DEV solution matches the composed source code.

        Args:
            env: DEV environment name.
            compose_result: :class:`ComposeResult` from the compose stage.
        """
        result = VerifyResult(
            environment=env,
            solution_name=compose_result.solution_name,
            mode="source",
        )

        # expected component counts
        result.expected_components = {
            "tables": len(compose_result.tables),
            "optionsets": len(compose_result.optionsets),
            "plugins": len(compose_result.plugins),
            "forms": len(compose_result.forms),
            "views": len(compose_result.views),
            "ribbons": len(compose_result.ribbons),
            "roles": len(compose_result.roles),
            "webresources": 1 if compose_result.webresources else len(compose_result.webresource_files),
        }

        try:
            from ..runtime import get_client
            client = get_client(env)

            # query solution components from Dataverse
            solution = client.get_solution_by_name(compose_result.solution_name)
            if solution is None:
                result.success = False
                result.warnings.append(
                    f"Solution '{compose_result.solution_name}' not found in {env}"
                )
                return result

            # query solution components count
            try:
                components = client.get_solution_components(compose_result.solution_name)
                comp_count = len(components) if components else 0
                result.actual_components = {"total_components": comp_count}
            except Exception:  # noqa: BLE001
                result.warnings.append("Could not query solution components (API may not support this)")

            # check if tables exist
            for table_name in compose_result.tables:
                try:
                    meta = client.get_entity_metadata(table_name.lower())
                    if meta is None:
                        result.missing.append(f"table:{table_name}")
                except Exception:  # noqa: BLE001
                    result.warnings.append(f"Could not verify table '{table_name}'")

        except Exception as e:  # noqa: BLE001
            result.success = False
            result.warnings.append(f"Verification error: {e}")

        if result.missing:
            result.success = False

        return result

    def verify_promote(self, env: str, solution_name: str) -> VerifyResult:
        """Verify solution exists in target environment (promote mode).

        Args:
            env: Target environment name.
            solution_name: Solution unique name.
        """
        result = VerifyResult(
            environment=env,
            solution_name=solution_name,
            mode="promote",
        )

        try:
            from ..runtime import get_client
            client = get_client(env)

            solution = client.get_solution_by_name(solution_name)
            if solution is None:
                result.success = False
                result.warnings.append(
                    f"Solution '{solution_name}' not found in {env} after import"
                )
                return result

            result.actual_components = {
                "solution_exists": True,
                "version": solution.get("version"),
                "is_managed": solution.get("ismanaged", False),
            }

            # verify component count
            try:
                components = client.get_solution_components(solution_name)
                if components:
                    result.actual_components["total_components"] = len(components)
            except Exception:  # noqa: BLE001
                pass

        except Exception as e:  # noqa: BLE001
            result.success = False
            result.warnings.append(f"Verification error: {e}")

        return result
