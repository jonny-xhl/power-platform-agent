"""
Plugin build helper (framework_power Phase 2, Wave 4).

Builds a .NET plugin project with ``dotnet`` and base64-encodes the output DLL so it
can be supplied as ``Plugin.content``. This is an authoring-time helper (separate
from deploy); it is self-contained and isolated from ``framework/``. Requires the
.NET SDK on PATH — offline tests skip when ``dotnet`` is unavailable.
"""

from __future__ import annotations

import base64
import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def dotnet_available() -> bool:
    """True if the ``dotnet`` CLI is on PATH and responds."""
    try:
        result = subprocess.run(["dotnet", "--version"], capture_output=True, timeout=10)
        return result.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def build_plugin(project_path: str | Path, configuration: str = "Release") -> dict[str, str]:
    """Build a .NET project and return ``{output_dll, content_base64}``.

    Args:
        project_path: path to a ``.csproj`` or a directory containing one.
        configuration: build configuration (default ``Release``).

    Raises:
        FileNotFoundError: If no ``.csproj`` is found under a directory path.
        RuntimeError: If the build fails or the output DLL cannot be located.
    """
    project = Path(project_path)
    if project.is_dir():
        csprojs = list(project.glob("*.csproj"))
        if not csprojs:
            raise FileNotFoundError(f"No .csproj under {project_path}")
        project = csprojs[0]

    cmd = ["dotnet", "build", str(project), "-c", configuration]
    logger.info(f"plugin_build: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"dotnet build failed:\n{result.stderr or result.stdout}")

    dll = _find_output_dll(project, configuration)
    if dll is None:
        raise RuntimeError(f"Could not locate built DLL for {project}")
    content = base64.b64encode(dll.read_bytes()).decode("ascii")
    return {"output_dll": str(dll), "content_base64": content}


def _find_output_dll(project: Path, configuration: str) -> Optional[Path]:
    """Locate ``<assembly-name>.dll`` under ``bin/<configuration>/net*/``."""
    base = project.parent / "bin" / configuration
    if not base.exists():
        return None
    # Prefer the newest target-framework subdirectory.
    for sub in sorted(base.glob("*/"), reverse=True):
        matches = list(sub.glob(f"{project.stem}.dll"))
        if matches:
            return matches[0]
    # Fallback: anywhere under bin/<configuration>.
    for dll in base.rglob(f"{project.stem}.dll"):
        return dll
    return None
