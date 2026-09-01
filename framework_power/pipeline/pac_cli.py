"""
Wrapper for PAC CLI (Microsoft Power Platform CLI) subprocess calls.

Handles:
  - ``pac auth create/select`` — multi-environment auth profiles
  - ``pac solution export`` — export solution (managed/unmanaged) from source env
  - ``pac solution import`` — import solution to target env
  - ``pac solution check`` — run solution checker
  - ``pac solution list`` — list solutions in an environment

The wrapper resolves environment URLs and credentials from ``config/environments.yaml``
and creates named pac auth profiles for each environment.

Requires: ``pac`` CLI installed (``dotnet tool install -g Microsoft.PowerApps.CLI.Tool``).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class PacCliResult:
    """Result of a pac CLI command execution."""

    success: bool
    command: str = ""
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    duration_seconds: float = 0.0
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "command": self.command,
            "return_code": self.return_code,
            "duration_seconds": round(self.duration_seconds, 2),
            "stdout": self.stdout[:2000] if self.stdout else "",
            "stderr": self.stderr[:2000] if self.stderr else "",
            "data": self.data,
        }


class PacCliWrapper:
    """Wraps ``pac`` CLI commands for solution export/import/check/auth.

    Args:
        environments_yaml_path: Path to config/environments.yaml.
        project_root: Project root directory.
        pac_path: Path to the pac binary (default: auto-detect or "pac").
        timeout: Default command timeout in seconds.
    """

    def __init__(
        self,
        environments_yaml_path: str = "config/environments.yaml",
        *,
        project_root: str = ".",
        pac_path: Optional[str] = None,
        timeout: int = 600,
    ):
        self.environments_yaml_path = environments_yaml_path
        self.project_root = Path(project_root)
        self.timeout = timeout
        self.pac_path = pac_path or self._find_pac()
        self._env_config: Optional[dict[str, Any]] = None
        self._auth_profiles: dict[str, str] = {}  # env_name -> pac auth profile name

    # ----------------------------------------------------------------- public API

    def ensure_auth(self, env_name: str) -> PacCliResult:
        """Ensure a pac auth profile exists for the given environment.

        Creates one if missing, using credentials from environments.yaml.
        The profile name is ``pp-{env_name}`` (e.g. ``pp-dev``, ``pp-test``).
        """
        profile_name = self._profile_name(env_name)
        env_data = self._get_env_data(env_name)
        if not env_data:
            return PacCliResult(
                success=False,
                command=f"ensure_auth({env_name})",
                stderr=f"Environment '{env_name}' not found in {self.environments_yaml_path}",
            )

        url = env_data.get("url", "")
        client_id = env_data.get("client_id", "")
        client_secret = env_data.get("client_secret", "")
        tenant_id = env_data.get("tenant_id", "")

        if not url or not client_id or not client_secret:
            return PacCliResult(
                success=False,
                command=f"ensure_auth({env_name})",
                stderr=f"Missing credentials for environment '{env_name}' (need url, client_id, client_secret).",
            )

        # resolve ${VAR} patterns from environment
        url = self._resolve_env_var(url)
        client_id = self._resolve_env_var(client_id)
        client_secret = self._resolve_env_var(client_secret)
        tenant_id = self._resolve_env_var(tenant_id) if tenant_id else ""

        cmd = [
            self.pac_path, "auth", "create",
            "--name", profile_name,
            "--url", url,
            "--applicationId", client_id,
            "--clientSecret", client_secret,
        ]
        if tenant_id:
            cmd.extend(["--tenant", tenant_id])

        result = self._run(cmd)
        if result.success:
            self._auth_profiles[env_name] = profile_name
            logger.info(f"pac auth profile '{profile_name}' created for env '{env_name}'")
        return result

    def select_auth(self, env_name: str) -> PacCliResult:
        """Select the pac auth profile for the given environment."""
        profile_name = self._profile_name(env_name)
        if env_name not in self._auth_profiles:
            # try to ensure first
            ensure_result = self.ensure_auth(env_name)
            if not ensure_result.success:
                return ensure_result
        cmd = [self.pac_path, "auth", "select", "--name", profile_name]
        return self._run(cmd)

    def export_solution(
        self,
        env_name: str,
        solution_name: str,
        output_path: str,
        *,
        managed: bool = False,
    ) -> PacCliResult:
        """Export a solution from an environment.

        Args:
            env_name: Source environment (e.g. "dev" for UAT, "test" for PROD).
            solution_name: Solution unique name.
            output_path: Where to save the zip file.
            managed: If True, export as managed solution.
        """
        # ensure auth profile selected
        select_result = self.select_auth(env_name)
        if not select_result.success:
            return select_result

        # ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.pac_path, "solution", "export",
            "--name", solution_name,
            "--path", output_path,
        ]
        if managed:
            cmd.append("--managed")

        result = self._run(cmd, timeout=self.timeout)
        if result.success:
            result.data["export_path"] = output_path
            result.data["managed"] = managed
            result.data["solution_name"] = solution_name
            result.data["source_environment"] = env_name
        return result

    def import_solution(
        self,
        env_name: str,
        solution_path: str,
        *,
        publish_workflows: bool = True,
        async_import: bool = True,
        overwrite_unmanaged: bool = False,
    ) -> PacCliResult:
        """Import a solution zip to an environment.

        Args:
            env_name: Target environment.
            solution_path: Path to the solution zip file.
            publish_workflows: Activate processes after import.
            async_import: Use async import (recommended for large solutions).
            overwrite_unmanaged: Overwrite unmanaged customizations.
        """
        select_result = self.select_auth(env_name)
        if not select_result.success:
            return select_result

        if not Path(solution_path).exists():
            return PacCliResult(
                success=False,
                command=f"import_solution({env_name})",
                stderr=f"Solution zip not found: {solution_path}",
            )

        cmd = [
            self.pac_path, "solution", "import",
            "--path", solution_path,
        ]
        if publish_workflows:
            cmd.append("--publish-workflows")
        if async_import:
            cmd.append("--async")
        if overwrite_unmanaged:
            cmd.append("--overwrite-unmanaged-customizations")

        result = self._run(cmd, timeout=self.timeout)
        if result.success:
            result.data["import_path"] = solution_path
            result.data["target_environment"] = env_name
        return result

    def check_solution(self, solution_path: str, *, geo: str = "UnitedStates") -> PacCliResult:
        """Run the Power Platform Solution Checker on a solution zip."""
        if not Path(solution_path).exists():
            return PacCliResult(
                success=False,
                command="check_solution",
                stderr=f"Solution zip not found: {solution_path}",
            )
        cmd = [
            self.pac_path, "solution", "check",
            "--path", solution_path,
            "--geo", geo,
        ]
        return self._run(cmd, timeout=self.timeout)

    def list_solutions(self, env_name: str) -> PacCliResult:
        """List solutions in an environment (returns JSON)."""
        select_result = self.select_auth(env_name)
        if not select_result.success:
            return select_result
        cmd = [self.pac_path, "solution", "list", "--output", "json"]
        result = self._run(cmd)
        if result.success and result.stdout:
            try:
                result.data["solutions"] = json.loads(result.stdout)
            except json.JSONDecodeError:
                pass
        return result

    # ----------------------------------------------------------------- internals

    def _run(self, cmd: list[str], *, timeout: Optional[int] = None) -> PacCliResult:
        """Execute a pac CLI command and return a PacCliResult."""
        cmd_str = " ".join(cmd)
        logger.debug(f"Running: {cmd_str}")
        start = time.time()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
                cwd=str(self.project_root),
            )
            elapsed = time.time() - start
            success = proc.returncode == 0
            return PacCliResult(
                success=success,
                command=cmd_str,
                stdout=proc.stdout,
                stderr=proc.stderr,
                return_code=proc.returncode,
                duration_seconds=elapsed,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            return PacCliResult(
                success=False,
                command=cmd_str,
                stderr=f"Command timed out after {timeout or self.timeout}s",
                return_code=-1,
                duration_seconds=elapsed,
            )
        except FileNotFoundError:
            elapsed = time.time() - start
            return PacCliResult(
                success=False,
                command=cmd_str,
                stderr=f"pac CLI not found at '{self.pac_path}'. Install: dotnet tool install -g Microsoft.PowerApps.CLI.Tool",
                return_code=-2,
                duration_seconds=elapsed,
            )

    def _find_pac(self) -> str:
        """Find the pac binary on the system."""
        found = shutil.which("pac")
        if found:
            return found
        # common install locations
        candidates = [
            os.path.expanduser("~/.dotnet/tools/pac"),
            os.path.expanduser("~/.dotnet/tools/pac.exe"),
            "/usr/local/bin/pac",
        ]
        for c in candidates:
            if Path(c).exists():
                return c
        return "pac"  # fallback, will error on use

    def _profile_name(self, env_name: str) -> str:
        """Generate a pac auth profile name for an environment."""
        return f"pp-{env_name}"

    def _get_env_data(self, env_name: str) -> dict[str, Any]:
        """Get environment config from environments.yaml."""
        if self._env_config is None:
            yaml_path = self.project_root / self.environments_yaml_path
            if not yaml_path.exists():
                return {}
            with open(yaml_path, "r", encoding="utf-8") as f:
                self._env_config = yaml.safe_load(f) or {}
        envs = self._env_config.get("environments", {})
        return envs.get(env_name, {})

    @staticmethod
    def _resolve_env_var(value: str) -> str:
        """Resolve ``${VAR}`` patterns from environment variables."""
        if not value or not value.startswith("${"):
            return value
        var_name = value.strip("${}")
        return os.environ.get(var_name, value)
