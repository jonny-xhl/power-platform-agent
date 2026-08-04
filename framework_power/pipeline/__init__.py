"""
CI/CD Pipeline engine for Power Platform solution management.

Two execution modes:
  - **Source mode** (DEV): ``framework_power deploy`` from source code -> unmanaged solution
  - **Promote mode** (UAT/PROD): ``pac solution export/import`` along the chain DEV -> UAT -> PROD

Usage (external projects)::

    python -m framework_power pipeline map
    python -m framework_power pipeline compose --branch develop
    python -m framework_power pipeline run --branch develop
    python -m framework_power pipeline promote --branch release/1.0

The pipeline reads ``config/pipeline.yaml`` for branch->environment mapping and
``config/environments.yaml`` for Dataverse connection details.
"""

from .config import (
    BranchMapping,
    PipelineConfig,
    load_pipeline_config,
)
from .composer import SolutionComposer, ComposeResult
from .pac_cli import PacCliWrapper, PacCliResult
from .source_executor import SourceExecutor, SourceResult
from .promote_executor import PromoteExecutor, PromoteResult
from .state import PipelineState, DeploymentRecord
from .verifier import SolutionVerifier, VerifyResult

__all__ = [
    # config
    "BranchMapping",
    "PipelineConfig",
    "load_pipeline_config",
    # composer
    "SolutionComposer",
    "ComposeResult",
    # pac cli
    "PacCliWrapper",
    "PacCliResult",
    # executors
    "SourceExecutor",
    "SourceResult",
    "PromoteExecutor",
    "PromoteResult",
    # state + verify
    "PipelineState",
    "DeploymentRecord",
    "SolutionVerifier",
    "VerifyResult",
]
