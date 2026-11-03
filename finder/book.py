"""Finder book: alerted mints + actively tracked tokens, state/finder_book.json."""

from __future__ import annotations

import json
from typing import Any

from paths import STATE_DIR, state_lock

FINDER_FILE = STATE_DIR / "finder_book.json"


def _default() -> dict[str, Any]:
    return {"alerted": [], "tracked": {}, "last_scan_at": None}


def load() -> dict[str, Any]:
    with state_lock:
        if FINDER_FILE.is_file():
            try:
                state = _default()
                state.update(json.loads(FINDER_FILE.read_text(encoding="utf-8")))
                state.setdefault("alerted", [])
                state.setdefault("tracked", {})
                return state
            except (OSError, ValueError):
                pass
    return _default()


def save(state: dict[str, Any]) -> None:
    with state_lock:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        FINDER_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
