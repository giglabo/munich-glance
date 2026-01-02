"""
Configuration Loader

Loads settings from YAML files with environment variable substitution.
Supports ${ENV_VAR:default_value} pattern for sensitive values.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml


class ConfigLoader:
    """
    Configuration loader supporting YAML with env var substitution.

    Supports ${ENV_VAR:default_value} pattern for sensitive values like API keys.
    Non-sensitive configuration lives in the YAML file directly.
    """

    ENV_VAR_PATTERN = re.compile(r".*?\$\{(.+?)\}.*?")

    def __init__(
        self,
        config_file: str | None = None,
        config_file_env: str = "APP_CONFIG",
        default_paths: list[str] | None = None,
        logger: logging.Logger | None = None,
    ):
        """
        Initialize configuration loader.

        Args:
            config_file: Path to configuration file
            config_file_env: Environment variable containing config file path
            default_paths: List of default paths to search for config file
            logger: Logger instance (creates one if not provided)
        """
        self._cfg: dict[str, Any] = {}
        self._config_file_env = config_file_env
        self._default_paths = default_paths or [
            "config/app-config.yaml",
            "config/application.yml",
            "app-config.yaml",
        ]
        self._logger = logger or logging.getLogger(__name__)
        self._config_file_path: str | None = None
        self._load(config_file)

    def _load(self, config_file_param: str | None = None) -> None:
        """Load configuration from file."""
        try:
            config_file = self._resolve_config_path(config_file_param)

            if not config_file or not Path(config_file).exists():
                self._logger.warning(
                    f"Config file not found: {config_file}. Using defaults."
                )
                return

            self._config_file_path = config_file
            self._cfg = self._load_yaml(config_file)
            self._logger.info(f"Configuration loaded from: {config_file}")

        except Exception as e:
            self._logger.error(f"Failed to load configuration: {e}")
            raise

    def _resolve_config_path(self, config_file_param: str | None) -> str | None:
        """Resolve configuration file path from parameter or environment."""
        if config_file_param and Path(config_file_param).exists():
            return config_file_param

        env_path = os.getenv(self._config_file_env)
        if env_path and Path(env_path).exists():
            return env_path

        project_root = Path(__file__).parent.parent
        for path_str in self._default_paths:
            path = project_root / path_str
            if path.exists():
                return str(path)

        return None

    def _load_yaml(self, config_file: str) -> dict[str, Any]:
        """Load YAML file and process environment variables."""
        with open(config_file) as yml_file:
            cfg = yaml.safe_load(yml_file) or {}
            self._post_process(cfg)
            return cfg

    def _post_process(self, obj: Any) -> None:
        """Recursively process configuration to replace environment variables."""
        if obj and isinstance(obj, dict):
            for d_key, d_value in obj.copy().items():
                if isinstance(d_value, str):
                    obj[d_key] = self._replace_env_var(d_value)
                else:
                    self._post_process(d_value)
        elif obj and isinstance(obj, list):
            for i, d_value in enumerate(obj):
                if isinstance(d_value, str):
                    obj[i] = self._replace_env_var(d_value)
                else:
                    self._post_process(d_value)

    def _replace_env_var(self, value: str) -> str:
        """
        Replace environment variable placeholders in string.

        Supports format: ${ENV_VAR:default_value}
        If no default is provided and env var is missing, returns empty string.
        """
        matches = self.ENV_VAR_PATTERN.findall(value)
        if matches:
            full_value = value
            for match in matches:
                parts = match.split(":", 1)
                env_key = parts[0]
                default_value = parts[1] if len(parts) == 2 else ""

                env_value = os.environ.get(env_key, default_value)
                full_value = full_value.replace(f"${{{match}}}", env_value)

            return full_value

        return value

    def get(self, section: str, option_name: str, default: Any = None) -> Any:
        """
        Get configuration value from a section.

        Args:
            section: Top-level configuration section
            option_name: Configuration key within section
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self._cfg.get(section, {}).get(option_name, default)

    def get_nested(self, *keys: str, default: Any = None) -> Any:
        """
        Get nested configuration value.

        Args:
            *keys: Path to nested configuration value
            default: Default value if key not found

        Returns:
            Configuration value or default

        Example:
            config.get_nested('server', 'host', default='0.0.0.0')
        """
        value = self._cfg
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        return value if value is not None else default

    def get_section(self, section: str) -> dict[str, Any]:
        """Get entire configuration section."""
        return self._cfg.get(section, {})

    @property
    def config(self) -> dict[str, Any]:
        """Get full configuration dictionary."""
        return self._cfg

    def reload(self, config_file: str | None = None) -> None:
        """Reload configuration from file."""
        self._load(config_file or self._config_file_path)


class InvalidConfigError(Exception):
    """Exception raised for invalid configuration."""

    pass


# Global configuration loader instance
_loader: ConfigLoader | None = None


def get_config_loader(
    config_file: str | None = None,
    force_reload: bool = False,
) -> ConfigLoader:
    """
    Get or create global configuration loader instance.

    Args:
        config_file: Path to configuration file (only used on first call)
        force_reload: Force reload configuration

    Returns:
        ConfigLoader instance
    """
    global _loader

    if _loader is None or force_reload:
        _loader = ConfigLoader(config_file=config_file)

    return _loader


def reset_config_loader() -> None:
    """Reset the global configuration loader. Useful for testing."""
    global _loader
    _loader = None
