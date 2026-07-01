"""Unit tests for framework_power.client.plugin_build (gated on dotnet)."""

import pytest

from framework_power.client.plugin_build import (
    _read_target_framework,
    _resolve_deploy_mode,
    build_plugin,
    dotnet_available,
)
from framework_power.components.models import (
    ContentKind,
    DeployMode,
    Plugin,
    PluginProject,
)

pytestmark = pytest.mark.unit


def test_dotnet_available_returns_bool():
    assert isinstance(dotnet_available(), bool)


@pytest.mark.skipif(not dotnet_available(), reason="dotnet SDK not available")
def test_build_plugin_smoke(tmp_path):
    """Real build smoke — only runs when the .NET SDK is installed."""
    # A trivial classlib project has no IPlugin, but build_plugin only builds +
    # base64-encodes; it does not validate the DLL. We just need a buildable DLL.
    import subprocess

    name = "SmokyPlugin"
    subprocess.run(["dotnet", "new", "classlib", "-n", name, "-o", str(tmp_path)], check=True,
                   capture_output=True)
    result = build_plugin(tmp_path)
    assert result["content_base64"]


# ---- Phase 8: deploy-mode resolution + dynamic naming (offline, no dotnet) ----


def test_resolve_deploy_mode_auto_by_tfm():
    # env plugin package runtime: net462/net471 → Package; net48 → Assembly
    assert _resolve_deploy_mode(DeployMode.Auto, "net462") == DeployMode.Package
    assert _resolve_deploy_mode(DeployMode.Auto, "net471") == DeployMode.Package
    assert _resolve_deploy_mode(DeployMode.Auto, "net48") == DeployMode.Assembly
    # net6/net8/netstandard are UNSUPPORTED on this env → Auto raises
    for bad in ("net6.0", "net8.0", "netstandard2.0"):
        with pytest.raises(ValueError, match="unsupported plugin target framework"):
            _resolve_deploy_mode(DeployMode.Auto, bad)


def test_resolve_deploy_mode_explicit_passthrough():
    for mode in (DeployMode.Package, DeployMode.Assembly):
        assert _resolve_deploy_mode(mode, "net48") == mode
        assert _resolve_deploy_mode(mode, "net6.0") == mode  # explicit; validated separately


def test_validate_tfm_for_mode():
    from framework_power.client.plugin_build import _validate_tfm_for_mode
    _validate_tfm_for_mode(DeployMode.Package, "net462")  # ok
    _validate_tfm_for_mode(DeployMode.Assembly, "net48")  # ok
    with pytest.raises(ValueError, match="package deploy path requires"):
        _validate_tfm_for_mode(DeployMode.Package, "net6.0")  # package rejects net6
    with pytest.raises(ValueError, match="assembly deploy path requires"):
        _validate_tfm_for_mode(DeployMode.Assembly, "net8.0")


def test_read_target_framework(tmp_path):
    csproj = tmp_path / "P.csproj"
    csproj.write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net471</TargetFramework>'
                      "</PropertyGroup></Project>", encoding="utf-8")
    assert _read_target_framework(csproj) == "net471"
    multi = tmp_path / "M.csproj"
    multi.write_text("<PropertyGroup><TargetFrameworks>net6.0;net471</TargetFrameworks></PropertyGroup>",
                     encoding="utf-8")
    assert _read_target_framework(multi) == "net6.0"


def test_plugin_project_assembly_name_dynamic():
    assert PluginProject(module="smoke_order", company="PP", project="Crm", kind="Plugin").assembly_name \
        == "PP.Crm.Plugin.SmokeOrder"
    assert PluginProject(module="account", kind="Action").assembly_name == "PP.Crm.Action.Account"
    # dynamic — a different project overrides company/project
    assert PluginProject(module="x", company="Acme", project="CrmX", kind="Plugin").assembly_name \
        == "Acme.CrmX.Plugin.X"


def test_plugin_package_name_has_publisher_prefix():
    plugin = Plugin(name="PP.Crm.Plugin.Smoke", content="abcd", prefix="new",
                    content_kind=ContentKind.Package)
    assert plugin.package_name == "new_PP.Crm.Plugin.Smoke"
    assert Plugin(name="X", content="abcd").package_name == "new_X"

