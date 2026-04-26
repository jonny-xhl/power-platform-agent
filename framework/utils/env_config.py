"""
Environment Configuration Utility

Provides utilities for loading and expanding environment variables in configuration files.
"""

import os
import re
from pathlib import Path
from typing import Any


def load_env_file(env_file: str = None) -> None:
    """
    Load environment variables from .env file

    Args:
        env_file: Path to .env file. If None, searches for .env in project root.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        # python-dotenv not available, return silently
        return

    if env_file:
        load_dotenv(env_file)
    else:
        # Try common locations
        project_root = Path.cwd()
        for path in [".env", ".env.local", "../.env"]:
            if (project_root / path).exists():
                load_dotenv(project_root / path)
                break


def expand_env_vars(value: Any) -> Any:
    """
    Expand environment variables in a value

    Supports ${VAR_NAME} and $VAR_NAME syntax

    Args:
        value: Value to expand (string, dict, list, or other)

    Returns:
        Value with expanded environment variables
    """
    if isinstance(value, str):
        # Match ${VAR_NAME} and $VAR_NAME patterns
        pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'

        def replace_var(match):
            var_name = match.group(1) or match.group(2)
            return os.getenv(var_name, match.group(0))

        return re.sub(pattern, replace_var, value)

    elif isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}

    elif isinstance(value, list):
        return [expand_env_vars(item) for item in value]

    else:
        return value


def load_yaml_with_env(yaml_path: str) -> dict[str, Any]:
    """
    Load YAML file with environment variable expansion

    Args:
        yaml_path: Path to YAML file

    Returns:
        Parsed and expanded YAML content
    """
    import yaml

    # Load .env file first
    load_env_file()

    # Load and parse YAML
    with open(yaml_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse YAML
    data = yaml.safe_load(content)

    # Expand environment variables recursively
    return expand_env_vars(data) if data else {}


def get_env_config(
    env_file: str = None,
    config_file: str = None
) -> dict[str, Any]:
    """
    Get complete environment configuration

    Loads from .env file and optionally merges with YAML config

    Args:
        env_file: Path to .env file
        config_file: Path to YAML config file

    Returns:
        Combined configuration dictionary
    """
    # Load .env file
    load_env_file(env_file)

    config = {}

    # Load YAML config if provided
    if config_file:
        config = load_yaml_with_env(config_file)

    # Add direct environment variables (not in YAML)
    env_vars = {
        "LLM_PROVIDER": os.getenv("LLM_PROVIDER"),
        "LLM_MODEL": os.getenv("LLM_MODEL"),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "ANTHROPIC_MODEL": os.getenv("ANTHROPIC_MODEL"),
        "ZHIPUAI_API_KEY": os.getenv("ZHIPUAI_API_KEY"),
        "ZHIPU_MODEL": os.getenv("ZHIPU_MODEL"),
        "DASHSCOPE_API_KEY": os.getenv("DASHSCOPE_API_KEY"),
        "QWEN_MODEL": os.getenv("QWEN_MODEL"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL"),
    }

    # Remove None values
    env_vars = {k: v for k, v in env_vars.items() if v is not None}

    if "env" not in config:
        config["env"] = {}

    config["env"].update(env_vars)

    return config


class EnvConfig:
    """
    Environment configuration manager

    Provides a clean interface for accessing configuration with
    automatic environment variable expansion.
    """

    def __init__(
        self,
        env_file: str = None,
        config_dir: str = None
    ):
        """
        Initialize environment configuration

        Args:
            env_file: Path to .env file
            config_dir: Path to config directory (default: config/)
        """
        self.env_file = env_file
        self.config_dir = config_dir or "config"
        self._cache: dict[str, Any] = {}

        # Load .env file immediately
        load_env_file(env_file)

    def get(
        self,
        key: str,
        default: Any = None,
        required: bool = False
    ) -> Any:
        """
        Get configuration value

        Args:
            key: Configuration key (supports dot notation for nested access)
            default: Default value if not found
            required: If True, raises error when key is not found

        Returns:
            Configuration value
        """
        # Check cache first
        if key in self._cache:
            return self._cache[key]

        # Check environment variable
        env_value = os.getenv(key.upper().replace(".", "_"))
        if env_value is not None:
            self._cache[key] = env_value
            return env_value

        # Check YAML config files
        for config_file in ["environments.yaml", "hermes_profile.yaml", "naming_rules.yaml"]:
            config_path = Path(self.config_dir) / config_file
            if config_path.exists():
                try:
                    config = load_yaml_with_env(str(config_path))
                    value = self._get_nested_value(config, key)
                    if value is not None:
                        self._cache[key] = value
                        return value
                except Exception:
                    pass

        if required and default is None:
            raise ValueError(f"Required configuration key '{key}' not found")

        return default

    def _get_nested_value(self, data: dict, key: str) -> Any:
        """Get value from nested dictionary using dot notation"""
        keys = key.split(".")
        value = data

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None

        return value

    def get_all(self) -> dict[str, Any]:
        """Get all configuration as a dictionary"""
        config = {}

        # Load all YAML configs
        for config_file in ["environments.yaml", "hermes_profile.yaml", "naming_rules.yaml"]:
            config_path = Path(self.config_dir) / config_file
            if config_path.exists():
                try:
                    file_config = load_yaml_with_env(str(config_path))
                    config.update(file_config)
                except Exception:
                    pass

        return config

    def reload(self):
        """Clear cache and reload configuration"""
        self._cache.clear()
        load_env_file(self.env_file)
