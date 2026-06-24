"""
Environment configuration utilities (self-contained copy for framework_power).

Loads ``.env`` and expands ``${VAR}`` references in YAML config files. Only the
helpers needed by the metadata deploy runtime are copied here.
"""

import os
import re
from pathlib import Path
from typing import Any, Optional


def load_env_file(env_file: Optional[str] = None) -> None:
    """Load environment variables from a ``.env`` file.

    Args:
        env_file: Explicit path to a ``.env`` file. If ``None``, the project
            root is searched (cwd, then parents up to 3 levels).
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    if env_file:
        load_dotenv(env_file)
        return

    current_dir = Path.cwd()
    if (current_dir / ".env").exists():
        load_dotenv(current_dir / ".env")
        return

    parent_dir = current_dir.parent
    if (parent_dir / ".env").exists():
        load_dotenv(parent_dir / ".env")
        return

    search_dir = current_dir
    for _ in range(3):
        if (search_dir / ".env").exists():
            load_dotenv(search_dir / ".env")
            return
        search_dir = search_dir.parent
        if search_dir == search_dir.parent:
            break


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
