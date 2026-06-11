"""Configuration loading: .env (secrets) + config.yaml (everything else)."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


class ConfigError(RuntimeError):
    pass


def load_config() -> dict:
    load_dotenv(ROOT / ".env")
    cfg_path = ROOT / "config.yaml"
    if not cfg_path.exists():
        raise ConfigError(
            "config.yaml not found. Run:  cp config.yaml.example config.yaml  and edit it."
        )
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f) or {}
    return cfg


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(
            f"{name} is not set. Copy .env.example to .env and fill it in."
        )
    return value
