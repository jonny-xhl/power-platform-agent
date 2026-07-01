"""
Plugin build helper (framework_power Phase 2 Wave 4 + Phase 8).

Phase 8 adds :func:`build_plugin_project` which builds a .NET plugin project and emits a
:class:`~framework_power.components.models.Plugin` ready for deploy, choosing the path by target framework:
- **Package** (preferred, .NET 6+): ``dotnet build`` + ``dotnet pack`` → base64 ``.nupkg`` → deployed via the
  ``pluginpackages`` entity (no ILMerge, no strong-name signing; deps bundled).
- **Assembly** (fallback, .NET Framework): ``dotnet build`` → base64 ``.dll`` → deployed via ``pluginassemblies``
  (the .csproj is responsible for strong-name signing + ILMerge/ILRepack of layered deps into one DLL).

Naming follows the project-wide rule ``{company}.{project}.{kind}.{Module}`` (dynamic per project; defaults
``Ninebot.Crm``). Self-contained; isolated from ``framework/``. Requires the .NET SDK on PATH.
"""

from __future__ import annotations

import base64
import importlib.util
import logging
import re
import subprocess
from pathlib import Path
from typing import Optional

from ..components.models import (
    ContentKind,
    DeployMode,
    Plugin,
    PluginProject,
)

logger = logging.getLogger(__name__)


def dotnet_available() -> bool:
    """True if the ``dotnet`` CLI is on PATH and responds."""
    try:
        result = subprocess.run(["dotnet", "--version"], capture_output=True, timeout=10)
        return result.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def build_plugin(project_path: str | Path, configuration: str = "Release") -> dict[str, str]:
    """Build a .NET project and return ``{output_dll, content_base64}`` (Phase 2 helper, assembly path)."""
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


def load_plugin_project(path: str | Path) -> PluginProject:
    """Load a :class:`PluginProject` from a Python module that exports ``PROJECT``."""
    path = Path(path)
    spec = importlib.util.spec_from_file_location(f"_plugin_proj_{path.stem}", str(path))
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load plugin project config: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    project = getattr(mod, "PROJECT", None)
    if not isinstance(project, PluginProject):
        raise ValueError(f"{path} does not export a PluginProject as `PROJECT`")
    return project


def build_plugin_project(project_dir: str | Path, *, config: PluginProject,
                         configuration: str = "Release") -> Plugin:
    """Build a .NET plugin project → :class:`Plugin` (Phase 8).

    Resolves the deploy path by target framework (``DeployMode.Auto``: net6+⇒Package, else Assembly), builds,
    and base64-encodes the artifact (``.nupkg`` for Package, ``.dll`` for Assembly). The output DLL/`.nupkg` are
    named from ``config.assembly_name`` (``{company}.{project}.{kind}.{Module}``) — the build passes
    ``-p:AssemblyName``/``-p:PackageId`` so the .csproj's own ``<AssemblyName>``/``<PackageId>`` are IGNORED
    (config is the single source of truth → fully dynamic per-project naming).
    """
    project_dir = Path(project_dir)
    csproj = _find_csproj(project_dir)
    tfm = _read_target_framework(csproj) or config.target_framework
    mode = _resolve_deploy_mode(config.deploy_mode, tfm)
    _validate_tfm_for_mode(mode, tfm)  # fail fast with a clear message before the cryptic Dataverse error
    assembly_name = config.assembly_name  # the single source of truth for the output DLL/package name
    # Clean bin/obj first — a TFM change (e.g. net6.0→net471) leaves stale output that `dotnet pack` would
    # otherwise re-package (wrong lib/<tfm>/ folder → Dataverse rejects with "no supported target framework").
    import shutil
    for stale in (project_dir / "bin", project_dir / "obj"):
        if stale.exists():
            shutil.rmtree(stale)
    # Override <AssemblyName> so the OUTPUT DLL is named per config ({company}.{project}.{kind}.{Module}),
    # independent of whatever the .csproj declares → fully dynamic naming (the .csproj AssemblyName is ignored).
    _run(["dotnet", "build", str(csproj), "-c", configuration, f"-p:AssemblyName={assembly_name}"])

    if mode == DeployMode.Package:
        # Dataverse requires the pluginpackage name (.nupkg filename) to CONTAIN the publisher prefix, so the
        # PackageId is prefixed while the assembly name inside the package follows the {company}.{project}.… rule.
        package_id = f"{config.prefix}_{assembly_name}"
        _run(["dotnet", "pack", str(csproj), "-c", configuration, f"-p:PackageVersion={config.version}",
              f"-p:PackageId={package_id}", f"-p:AssemblyName={assembly_name}"])
        nupkg = _find_nupkg(project_dir, configuration, package_id, config.version)
        if nupkg is None:
            raise RuntimeError(f"Could not locate built .nupkg for {package_id} under {project_dir}")
        content = base64.b64encode(nupkg.read_bytes()).decode("ascii")
        content_kind = ContentKind.Package
    else:
        dll = _find_output_dll(csproj, configuration, assembly_name)
        if dll is None:
            raise RuntimeError(f"Could not locate built DLL {assembly_name}.dll for {csproj}")
        content = base64.b64encode(dll.read_bytes()).decode("ascii")
        content_kind = ContentKind.Assembly

    logger.info(f"plugin_build: {config.assembly_name} ({tfm}) via {mode.value} → {content_kind.value}")
    return Plugin(
        name=config.assembly_name,
        content=content,
        version=config.version,
        content_kind=content_kind,
        target_framework=tfm,
        prefix=config.prefix,
        steps=list(config.steps),
        custom_actions=list(config.custom_actions),
    )


# --------------------------------------------------------------------------- internals


def _find_csproj(project_dir: Path) -> Path:
    csprojs = list(project_dir.glob("*.csproj"))
    if not csprojs:
        raise FileNotFoundError(f"No .csproj under {project_dir}")
    return csprojs[0]


def _read_target_framework(csproj: Path) -> str:
    text = csproj.read_text(encoding="utf-8")
    m = re.search(r"<TargetFrameworks?\b[^>]*>\s*([^<]+?)\s*</TargetFrameworks?>", text, re.IGNORECASE)
    tfm = m.group(1).split(";")[0].strip() if m else ""
    return tfm


# TFM constraints (live-pinned on dev): the PluginPackage runtime accepts ONLY .NET Framework 4.6.2 / 4.7.1
# (it rejects net6/net8/netstandard with "No supported target framework folder … 'net471' and 'net462'").
# net462 is the canonical/most-compatible target. The classic pluginassembly path accepts net462/net471/net48.
PACKAGE_TFMS = ("net462", "net471")
ASSEMBLY_TFMS = ("net462", "net471", "net48")
DEFAULT_TARGET_FRAMEWORK = "net462"


def _resolve_deploy_mode(deploy_mode: DeployMode, target_framework: str) -> DeployMode:
    """``Auto`` → Package for net462/net471, Assembly for net48; raise for anything else (net6/net8/netstandard
    are unsupported on this env's plugin runtime). Explicit modes pass through (validated separately)."""
    if deploy_mode != DeployMode.Auto:
        return deploy_mode
    tfm = (target_framework or "").lower()
    if tfm in PACKAGE_TFMS:
        return DeployMode.Package
    if tfm in ASSEMBLY_TFMS:  # net48 (net462/net471 already matched Package above)
        return DeployMode.Assembly
    raise ValueError(
        f"unsupported plugin target framework {tfm!r}: this env's plugin runtime accepts only .NET Framework "
        f"{PACKAGE_TFMS} (NuGet package) or net48 (assembly) — NOT net6/net8/netstandard. "
        f"Set <TargetFramework>net462</TargetFramework>.")


def _validate_tfm_for_mode(mode: DeployMode, target_framework: str) -> None:
    """Raise early with a clear message if the TFM isn't valid for the chosen deploy path (so the failure shows
    up at build time, not as a cryptic Dataverse 'no supported target framework' error at deploy time)."""
    tfm = (target_framework or "").lower()
    ok = PACKAGE_TFMS if mode == DeployMode.Package else ASSEMBLY_TFMS
    if tfm not in ok:
        raise ValueError(
            f"{mode.value} deploy path requires target framework in {ok}; got {tfm!r}. "
            f"Use <TargetFramework>net462</TargetFramework> for the (preferred) NuGet package path.")


def _run(cmd: list[str]) -> None:
    logger.info("plugin_build: " + " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{result.stderr or result.stdout}")


def _find_nupkg(project_dir: Path, configuration: str, package_id: str, version: str) -> Optional[Path]:
    """Locate ``<package_id>.<version>.nupkg`` (or the single .nupkg) under ``bin/<configuration>/``."""
    base = project_dir / "bin" / configuration
    if not base.exists():
        return None
    expected = base / f"{package_id}.{version}.nupkg"
    if expected.exists():
        return expected
    nupkgs = sorted(base.rglob("*.nupkg"))
    return nupkgs[-1] if nupkgs else None


def _find_output_dll(project: Path, configuration: str, assembly_name: Optional[str] = None) -> Optional[Path]:
    """Locate ``<assembly-name>.dll`` under ``bin/<configuration>/net*/``.

    ``assembly_name`` (from the PluginProject config, overriding the .csproj) wins; defaults to the .csproj
    filename stem for the legacy Phase-2 ``build_plugin`` helper.
    """
    name = assembly_name or project.stem
    base = project.parent / "bin" / configuration
    if not base.exists():
        return None
    # Prefer the newest target-framework subdirectory.
    for sub in sorted(base.glob("*/"), reverse=True):
        matches = list(sub.glob(f"{name}.dll"))
        if matches:
            return matches[0]
    # Fallback: anywhere under bin/<configuration>.
    for dll in base.rglob(f"{name}.dll"):
        return dll
    return None


__all__ = [
    "dotnet_available", "build_plugin", "build_plugin_project", "load_plugin_project",
    "_resolve_deploy_mode", "_read_target_framework",
]
