"""Killswitch: per-desk freeze state, persisted to state/FROZEN.json (gitignored)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from paths import STATE_DIR, state_lock

DESKS = ("all", "yield", "finder", "copy")
_STATE_FILE = STATE_DIR / "FROZEN.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default() -> dict[str, Any]:
    return {
        "all": False,
        "yield": False,
        "finder": False,
        "copy": False,
        "reason": None,
        "reasons": {},
        "frozen_at": {},
    }


state: dict[str, Any] = _default()


def _load_locked() -> dict[str, Any]:
    if _STATE_FILE.is_file():
        try:
            loaded = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            merged = _default()
            merged.update({k: loaded.get(k, merged.get(k)) for k in merged})
            return merged
        except (OSError, ValueError):
            pass
    return _default()


def _save_locked() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _refresh_reason_locked() -> None:
    if state.get("all"):
        state["reason"] = (state.get("reasons") or {}).get("all")
        return
    reasons = state.get("reasons") or {}
    for desk in ("yield", "finder", "copy"):
        if state.get(desk) and reasons.get(desk):
            state["reason"] = reasons[desk]
            return
    state["reason"] = None


def reload() -> dict[str, Any]:
    global state
    with state_lock:
        state = _load_locked()
    return state


def freeze(desk: str, reason: str = "") -> dict[str, Any]:
    if desk not in DESKS:
        raise ValueError(f"unknown desk {desk!r}; expected one of {DESKS}")
    with state_lock:
        state.update(_load_locked())
        state[desk] = True
        state.setdefault("reasons", {})[desk] = reason or "frozen by operator"
        state.setdefault("frozen_at", {})[desk] = _now()
        _refresh_reason_locked()
        _save_locked()
        _log_event("freeze", desk, reason)
    return dict(state)


def thaw(desk: str) -> dict[str, Any]:
    if desk not in DESKS:
        raise ValueError(f"unknown desk {desk!r}; expected one of {DESKS}")
    with state_lock:
        state.update(_load_locked())
        if desk == "all":
            for key in DESKS:
                state[key] = False
            state["reasons"] = {}
            state["frozen_at"] = {}
        else:
            state[desk] = False
            (state.get("reasons") or {}).pop(desk, None)
            (state.get("frozen_at") or {}).pop(desk, None)
            if not any(state.get(k) for k in DESKS):
                state["reasons"] = {}
                state["frozen_at"] = {}
        _refresh_reason_locked()
        _save_locked()
        _log_event("thaw", desk, "")
    return dict(state)


def frozen(desk: str) -> bool:
    with state_lock:
        current = _load_locked()
    if current.get("all"):
        return True
    if desk in ("all",):
        return bool(current.get("all"))
    return bool(current.get(desk))


def get_state() -> dict[str, Any]:
    """FrozenState shape for the API: {all, yield, finder, copy, reason} (+ extras)."""
    with state_lock:
        current = _load_locked()
    return {
        "all": bool(current.get("all")),
        "yield": bool(current.get("yield")),
        "finder": bool(current.get("finder")),
        "copy": bool(current.get("copy")),
        "reason": current.get("reason"),
        "frozen_at": current.get("frozen_at") or {},
    }


def _log_event(action: str, desk: str, reason: str) -> None:
    # Kept local to avoid an import cycle with agents.scribe (which imports config).
    try:
        from agents import scribe

        scribe.write_log({"desk": "ops", "action": action, "target": desk, "reason": reason})
    except Exception:
        pass


reload()
