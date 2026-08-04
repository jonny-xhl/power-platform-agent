"""
Environment configuration utilities (self-contained copy for framework_power).

Loads ``.env`` and expands ``${VAR}`` references in YAML config files. Only the
helpers needed by the metadata deploy runtime are copied here.

Env file loading priority (workspace-aware):

1. Explicit ``env_file`` argument (always wins)
2. Workspace ``.env`` — ``ws.root / .env`` (per-project Dataverse credentials)
3. User-level ``.env`` — ``~/.power-platform-agent/.env`` (LLM API keys, etc.)
4. CWD ``.env`` — backward compatibility
5. Parent search — walk up 3 levels from CWD (legacy fallback)
"""

import os
import re
from pathlib import Path
from typing import Any, Optional


# User-level .env location for cross-project settings (LLM keys, etc.).
_USER_ENV_DIR = Path.home() / ".power-platform-agent"


def load_env_file(env_file: Optional[str] = None) -> None:
    """Load environment variables from ``.env`` files (workspace-aware).

    Loading order (later files do NOT override already-set variables, matching
    python-dotenv's default ``override=False`` semantics):

    1. ``env_file`` — explicit path if provided
    2. Workspace ``.env`` — discovered via ``pp-workspace.yaml`` upward search
    3. User-level ``.env`` — ``~/.power-platform-agent/.env``
    4. CWD ``.env`` — backward compatibility
    5. Parent search — walk up 3 levels from CWD (legacy)

    Args:
        env_file: Explicit path to a ``.env`` file. Takes precedence over all
            automatic discovery.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    candidates: list[Path] = []

    if env_file:
        candidates.append(Path(env_file))
    else:
        # 2. Workspace .env — find pp-workspace.yaml upward from CWD
        ws_env = _find_workspace_env()
        if ws_env:
            candidates.append(ws_env)

        # 3. User-level .env (cross-project LLM keys, etc.)
        user_env = _USER_ENV_DIR / ".env"
        candidates.append(user_env)

        # 4. CWD .env (backward compat)
        candidates.append(Path.cwd() / ".env")

        # 5. Parent search (legacy — walk up 3 levels)
        search_dir = Path.cwd()
        for _ in range(3):
            candidates.append(search_dir / ".env")
            search_dir = search_dir.parent
            if search_dir == search_dir.parent:
                break

    for candidate in candidates:
        if candidate.exists():
            load_dotenv(candidate, override=False)


def _find_workspace_env() -> Optional[Path]:
    """Find the ``.env`` in the nearest workspace root (has ``pp-workspace.yaml``).

    Returns ``None`` if no workspace is found.
    """
    cwd = Path.cwd()
    for d in [cwd, *cwd.parents]:
        if (d / "pp-workspace.yaml").exists():
            env_path = d / ".env"
            if env_path.exists():
                return env_path
            return None  # Found workspace but no .env — don't search parents
    return None


def expand_env_vars(value: Any) -> Any:
    """Expand ``${VAR_NAME}`` and ``$VAR_NAME`` references using ``os.environ``.

    Args:
        value: A string, dict, list, or scalar to expand recursively.

    Returns:
        The value with environment variables expanded (unchanged for non-strings).
    """
    if isinstance(value, str):
        pattern = r"\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)"

        def replace_var(match: re.Match) -> str:
            var_name = match.group(1) or match.group(2)
            return os.getenv(var_name, match.group(0))

        return re.sub(pattern, replace_var, value)

    if isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}

    if isinstance(value, list):
        return [expand_env_vars(item) for item in value]

    return value


def load_yaml_with_env(yaml_path: str) -> dict[str, Any]:
    """Load a YAML file with ``${VAR}`` expansion applied recursively.

    Args:
        yaml_path: Path to the YAML file.

    Returns:
        Parsed and expanded YAML content (empty dict if the file is empty).
    """
    import yaml

    load_env_file()

    with open(yaml_path, "r", encoding="utf-8") as f:
        content = f.read()

    data = yaml.safe_load(content)
    return expand_env_vars(data) if data else {}
