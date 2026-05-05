"""
Application configuration — load / save JSON settings.

The config file lives in the system temp directory so the compiled .exe
never needs write access to its own installation folder.
"""

import json
import os
import tempfile
from typing import Any, Dict

CONFIG_FILE: str = os.path.join(tempfile.gettempdir(), "frt_config.json")


def load_config() -> Dict[str, Any]:
    """Return the saved config dict, or an empty dict if none exists."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
    except Exception as exc:
        print(f"[config] Failed to load config: {exc}")
    return {}


def save_config(data: Dict[str, Any]) -> bool:
    """
    Persist *data* to the config file.
    Returns True on success, False on failure.
    """
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        return True
    except Exception as exc:
        print(f"[config] Failed to save config: {exc}")
        return False
