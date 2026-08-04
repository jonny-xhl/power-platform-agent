"""
Runtime bootstrap for standalone deploy scripts (framework_power).

Provides ``get_client(environment)`` (reuse of the copied client-secret auth flow) and
``argparse_env()`` so each AI-authored ``setup_<entity>.py`` stays a one-liner entrypoint.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from .client.auth import AutoAuthenticator
from .client.dataverse_client import DataverseClient
from .client.env_config import load_env_file, load_yaml_with_env

CONFIG_PATH = "config/environments.yaml"


def get_client(environment: Optional[str] = None, *, config_path: str = CONFIG_PATH) -> DataverseClient:
    """Build an authenticated ``DataverseClient`` for ``environment``.

    Reads ``config/environments.yaml`` (with ``${VAR}`` expansion from ``.env``) and
    acquires a token via the client-credentials flow (cache-first). Defaults to the
    ``current`` environment from the config.

    Args:
        environment: Environment name (dev/test/production). Defaults to config's ``current``.
        config_path: Path to the environments YAML.

    Returns:
        An authenticated ``DataverseClient``.

    Raises:
        SystemExit: If the environment is unknown or credentials are missing.
    """
    load_env_file()
    config = load_yaml_with_env(config_path)
    envs = config.get("environments", {})

    env = environment or config.get("current", "dev")
    if env not in envs:
        raise SystemExit(f"Unknown environment {env!r}. Available: {list(envs)}")

    env_config = envs[env]
    try:
        token = AutoAuthenticator(config_path).get_cached_or_refresh_token(env, env_config)
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"Authentication failed for environment {env!r}: {e}") from e

    client = DataverseClient(env, config_path=config_path, access_token=token)
    client.set_token(token)
    return client


def get_client_from_workspace(ws, environment: Optional[str] = None) -> DataverseClient:
    """Build an authenticated client using a workspace's environments config.

    Args:
        ws: A :class:`framework_power.workspace.Workspace` instance.
        environment: Environment name. Defaults to config's ``current``.

    Returns:
        An authenticated ``DataverseClient``.
    """
    return get_client(environment, config_path=str(ws.environments_config))


def argparse_env(description: str = "Deploy Dataverse metadata") -> str:
    """Parse a ``--env`` argument (default: from config / ``dev``) and return it."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--env",
        default=None,
        help="Target environment (dev/test/production). Defaults to config 'current'.",
    )
    args, _ = parser.parse_known_args()
    return args.env


def main() -> int:
    """Tiny CLI: print the resolved environment + base URL (smoke check)."""
    env = argparse_env()
    client = get_client(env)
    print(f"environment={client.environment!r} base_url={client.base_url!r}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
