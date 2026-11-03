"""Filesystem locations for the backend: project root, state dir, log file."""

from __future__ import annotations

import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / "state"
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "loop.jsonl"

# Single-process guard for read-modify-write cycles on state/*.json.
state_lock = threading.RLock()


def ensure_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def state_path(name: str) -> Path:
    return STATE_DIR / name


ensure_dirs()
