"""Plugin sync standalone flow (framework_power Phase 8).

Builds a .NET plugin project (NuGet PluginPackage preferred, signed/merged assembly fallback), deploys it
(registering steps + best-effort custom actions), and optionally adds the resulting solution components to a
solution. Mirrors the form/view/ribbon standalone-flow shape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .client import plugin_build
from .components import plugin as plugin_component
from .components.models import Plugin, PluginProject
from .deployer import _is_already_exists

DEFAULT_DEF_FILENAME = "plugin_def.py"


def _ensure_solution(client: Any, solution_name: str, prefix: str) -> None:
    """Create the solution if it doesn't exist (uses the publisher matching ``prefix``)."""
    if client.get_solution_by_name(solution_name) is not None:
        return
    pubs = client.session.get(
        client.get_api_url("publishers?$select=uniquename,publisherid,customizationprefix&$top=50")
    ).json().get("value", [])
    pub = next((p for p in pubs if p.get("customizationprefix") == prefix), None)
    if pub is None:
        raise RuntimeError(f"no publisher with prefix '{prefix}' to create solution '{solution_name}'")
    client.create_solution({
        "uniquename": solution_name,
        "friendlyname": solution_name,
        "version": "1.0.0.0",
        "publisherid@odata.bind": f"/publishers({pub['publisherid']})",
    })


def deploy_plugin(
    client: Any,
    project_dir: str | Path,
    *,
    def_path: Optional[str | Path] = None,
    config: Optional[PluginProject] = None,
    prefix: str = "new",
    solution: Optional[str] = None,
) -> dict[str, Any]:
    """Build + deploy a plugin project. ``config`` wins; else load ``def_path`` (default ``<dir>/plugin_def.py``)."""
    project_dir = Path(project_dir)
    cfg = config or plugin_build.load_plugin_project(def_path or (project_dir / DEFAULT_DEF_FILENAME))
    plugin = plugin_build.build_plugin_project(project_dir, config=cfg)
    result = plugin_component.deploy(client, plugin, prefix=prefix)
    result["name"] = plugin.name
    result["content_kind"] = plugin.content_kind.value

    added: list[dict[str, Any]] = []
    if solution:
        _ensure_solution(client, solution, prefix)
        for code, oid, name in result.get("add_targets", []):
            try:
                client.add_solution_component(solution, code, oid)
                added.append({"code": code, "name": name, "action": "added"})
            except Exception as e:  # noqa: BLE001
                added.append({"code": code, "name": name,
                              "action": "exists" if _is_already_exists(e) else "failed", "error": str(e)[:160]})
    result["solution"] = {"name": solution, "added": added} if solution else None
    return result


def list_plugins(client: Any, *, include_system: bool = False) -> dict[str, Any]:
    """List plugin assemblies + packages. System assemblies (Microsoft.*) are filtered out unless requested."""
    assemblies = [
        {"pluginassemblyid": a.get("pluginassemblyid"), "name": a.get("name"), "version": a.get("version")}
        for a in client.get_plugin_assemblies()
        if include_system or not (a.get("name") or "").startswith(("Microsoft.", "System."))
    ]
    packages = [
        {"pluginpackageid": p.get("pluginpackageid"), "name": p.get("name"), "version": p.get("version")}
        for p in client.list_plugin_packages()
    ]
    return {"assemblies": assemblies, "packages": packages}


def reverse_plugin(client: Any, name: str) -> Plugin:
    """Reverse a plugin assembly (+ its steps) into a :class:`Plugin` model."""
    asm = client.get_plugin_assembly_by_name(name)
    if not asm:
        raise RuntimeError(f"no plugin assembly named '{name}'")
    return plugin_component.reverse(client, asm["pluginassemblyid"])


__all__ = ["deploy_plugin", "list_plugins", "reverse_plugin"]
