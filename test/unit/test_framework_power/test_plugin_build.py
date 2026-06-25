"""Unit tests for framework_power.client.plugin_build (gated on dotnet)."""

import pytest

from framework_power.client.plugin_build import build_plugin, dotnet_available

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
