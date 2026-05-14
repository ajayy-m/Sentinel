from __future__ import annotations

import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::([^}]*))?\}")


class ConfigError(ValueError):
    """Raised when required configuration is invalid."""


def _resolve_env(value: str) -> str:
    def replacer(match: re.Match[str]) -> str:
        env_key = match.group(1)
        default = match.group(2)
        env_value = os.getenv(env_key)
        if env_value is None:
            if default is not None:
                return default
            raise ConfigError(f"Missing required environment variable: {env_key}")
        return env_value

    return _ENV_PATTERN.sub(replacer, value)


def _walk_and_resolve(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _walk_and_resolve(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_walk_and_resolve(v) for v in value]
    if isinstance(value, str):
        return _resolve_env(value)
    return value


def _validate(config: dict[str, Any]) -> None:
    required_paths = (
        ("system", "protocol_version"),
        ("transport", "mode"),
        ("transport", "endpoint"),
    )

    for path in required_paths:
        current: Any = config
        for key in path:
            if not isinstance(current, dict) or key not in current:
                dotted = ".".join(path)
                raise ConfigError(f"Missing required config value: {dotted}")
            current = current[key]


def load_config(config_path: str) -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    with path.open("r", encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle) or {}

    if not isinstance(raw_config, dict):
        raise ConfigError("Top-level YAML structure must be a mapping")

    resolved_config = _walk_and_resolve(deepcopy(raw_config))
    _validate(resolved_config)
    return resolved_config
