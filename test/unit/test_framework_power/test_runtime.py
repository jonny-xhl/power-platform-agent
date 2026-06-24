"""Unit tests for framework_power.runtime (MSAL/config monkeypatched)."""

import pytest

from framework_power import runtime
from framework_power.client.dataverse_client import DataverseClient

pytestmark = pytest.mark.unit


_CONFIG = {
    "environments": {
        "dev": {
            "url": "https://example.crm.dynamics.com",
            "tenant_id": "tid",
            "client_id": "cid",
            "client_secret": "secret",
        },
        "test": {
            "url": "https://test.crm.dynamics.com",
            "tenant_id": "tid",
            "client_id": "cid",
            "client_secret": "secret",
        },
    },
    "current": "dev",
}


class _FakeAuth:
    def __init__(self, config_path: str = "") -> None:
        self.config_path = config_path

    def get_cached_or_refresh_token(self, environment, env_config):  # noqa: ANN001
        return "fake-token"


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    monkeypatch.setattr(runtime, "load_env_file", lambda *a, **k: None)
    monkeypatch.setattr(runtime, "load_yaml_with_env", lambda *a, **k: _CONFIG)
    monkeypatch.setattr(runtime, "AutoAuthenticator", _FakeAuth)
    # DataverseClient loads its own config from file (CWD-relative); stub it so the
    # test does not depend on the real config/environments.yaml location.
    def _fake_load_config(self):
        self._config = _CONFIG

    monkeypatch.setattr(DataverseClient, "_load_config", _fake_load_config)


def test_get_client_returns_authenticated_client():
    client = runtime.get_client("dev")
    assert isinstance(client, DataverseClient)
    assert client.access_token == "fake-token"
    assert client.base_url == "https://example.crm.dynamics.com"


def test_get_client_defaults_to_current_env():
    client = runtime.get_client(None)
    assert client.environment == "dev"


def test_get_client_unknown_env_raises():
    with pytest.raises(SystemExit):
        runtime.get_client("prod")


def test_argparse_env_returns_default(monkeypatch):
    monkeypatch.setattr("sys.argv", ["prog"])
    assert runtime.argparse_env() is None
    monkeypatch.setattr("sys.argv", ["prog", "--env", "test"])
    assert runtime.argparse_env() == "test"
