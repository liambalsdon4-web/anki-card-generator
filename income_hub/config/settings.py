"""Income Hub config + persisted settings.

Reuses the study_app approach: a JSON settings file next to the app, with the
Gemini API key overridable by the GEMINI_API_KEY env var (already set on this PC).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
RENDER_DIR = DATA_DIR / "renders"
RENDER_DIR.mkdir(exist_ok=True)

CONFIG_PATH = DATA_DIR / "config.json"
DB_PATH = DATA_DIR / "income_hub.db"

HOST = "127.0.0.1"
PORT = 8007
APP_NAME = "Income Hub"

DEFAULTS = {
    "api_key": "",
    "model": "gemini-flash-latest",
    "tts_voice": "en-US-AndrewNeural",   # edge-tts default voice
    "video_resolution": "1920x1080",
    "upload_privacy": "unlisted",        # private | unlisted | public — used by auto-upload
    "odds_api_key": "",                  # the-odds-api.com key for the arb scanner
}


def _load() -> dict:
    if CONFIG_PATH.exists():
        try:
            return {**DEFAULTS, **json.loads(CONFIG_PATH.read_text(encoding="utf-8"))}
        except (json.JSONDecodeError, OSError):
            return dict(DEFAULTS)
    return dict(DEFAULTS)


def get_settings() -> dict:
    cfg = _load()
    return {
        "model": cfg["model"],
        "tts_voice": cfg["tts_voice"],
        "video_resolution": cfg["video_resolution"],
        "upload_privacy": cfg["upload_privacy"],
        "odds_api_key_set": bool(get_odds_api_key()),
        "api_key_set": bool(get_api_key()),
        "api_key_source": "file" if cfg["api_key"] else ("env" if os.environ.get("GEMINI_API_KEY") else "none"),
    }


def save_settings(**kwargs) -> None:
    cfg = _load()
    for k, v in kwargs.items():
        if v is not None and str(v).strip():
            cfg[k] = v.strip() if isinstance(v, str) else v
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def get_api_key() -> str:
    return _load()["api_key"].strip() or os.environ.get("GEMINI_API_KEY", "").strip()


def get_model() -> str:
    return _load()["model"]


def get_voice() -> str:
    return _load()["tts_voice"]


def get_resolution() -> tuple[int, int]:
    w, h = _load()["video_resolution"].split("x")
    return int(w), int(h)


def get_upload_privacy() -> str:
    p = _load()["upload_privacy"]
    return p if p in ("private", "unlisted", "public") else "unlisted"


def get_odds_api_key() -> str:
    return _load()["odds_api_key"].strip() or os.environ.get("ODDS_API_KEY", "").strip()
