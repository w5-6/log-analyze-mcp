"""配置加载模块：环境变量优先，其次读取项目根目录 config.json，最后使用默认值。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# 项目根目录（src 的上一级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"

_DEFAULTS: dict[str, Any] = {
    "ollama_base_url": "http://localhost:11434",
    "ollama_model": "qwen2.5:7b",
    "ollama_timeout": 120,
    "max_log_lines": 400,
    "log_extensions": [".log", ".txt", ".out", ".err", ".trace", ".gz", ".zip"],
}


def _load_json() -> dict[str, Any]:
    """读取 config.json，文件不存在或格式错误时返回空字典。"""
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _cast(value: str, target_type: type) -> Any:
    """把环境变量字符串转换为目标类型。"""
    if target_type is int:
        return int(value)
    if target_type is bool:
        return value.strip().lower() in ("1", "true", "yes", "on")
    return value


def get_config() -> dict[str, Any]:
    """获取最终配置：默认值 < config.json < 环境变量。"""
    cfg = dict(_DEFAULTS)
    cfg.update(_load_json())

    env_map = {
        "ollama_base_url": ("OLLAMA_BASE_URL", str),
        "ollama_model": ("OLLAMA_MODEL", str),
        "ollama_timeout": ("OLLAMA_TIMEOUT", int),
        "max_log_lines": ("MAX_LOG_LINES", int),
    }
    for key, (env_name, env_type) in env_map.items():
        env_val = os.environ.get(env_name)
        if env_val not in (None, ""):
            try:
                cfg[key] = _cast(env_val, env_type)
            except ValueError:
                pass
    return cfg


CONFIG = get_config()
