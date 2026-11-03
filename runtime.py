"""Runtime markers: process start + last scheduler activity, persisted to state/runtime.json."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from paths import STATE_DIR, state_lock

_RUNTIME_FILE = STATE_DIR / "runtime.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load() -> dict[str, Any]:
    with state_lock:
        if _RUNTIME_FILE.is_file():
            try:
                return json.loads(_RUNTIME_FILE.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
    return {}


def _save(data: dict[str, Any]) -> None:
    with state_lock:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        _RUNTIME_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _set(key: str, value: Any) -> dict[str, Any]:
    data = _load()
    data[key] = value
    _save(data)
    return data


def mark_started() -> None:
    """Called once per process start (app lifespan)."""
    _set("started_at", _now())


def mark_yield_tick(summary: dict[str, Any] | None = None) -> None:
    data = _load()
    data["last_yield_tick_at"] = _now()
    if summary is not None:
        data["last_yield_tick"] = summary
    _save(data)


def mark_finder_scan(summary: dict[str, Any] | None = None) -> None:
    data = _load()
    data["last_finder_scan_at"] = _now()
    if summary is not None:
        data["last_finder_scan"] = summary
    _save(data)


def mark_copy_scan(summary: dict[str, Any] | None = None) -> None:
    data = _load()
    data["last_copy_scan_at"] = _now()
    if summary is not None:
        data["last_copy_scan"] = summary
    _save(data)


def runtime_info() -> dict[str, Any]:
    """The RuntimeInfo shape decoded by NexusCore (extra keys are ignored by Swift)."""
    data = _load()
    return {
        "started_at": data.get("started_at") or _now(),
        "last_yield_tick_at": data.get("last_yield_tick_at"),
        "last_finder_scan_at": data.get("last_finder_scan_at"),
        "last_copy_scan_at": data.get("last_copy_scan_at"),
    }


def snapshot() -> dict[str, Any]:
    """Full runtime picture including the last scheduler summaries."""
    data = _load()
    info = runtime_info()
    info.update(
        {
            "last_yield_tick": data.get("last_yield_tick"),
            "last_finder_scan": data.get("last_finder_scan"),
            "last_copy_scan": data.get("last_copy_scan"),
        }
    )
    return info
