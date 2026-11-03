"""Paper trade book: open positions + fill history, persisted to state/trade_book.json."""

from __future__ import annotations

import json
from typing import Any

from paths import STATE_DIR, state_lock

TRADE_FILE = STATE_DIR / "trade_book.json"


def _default() -> dict[str, Any]:
    return {
        "cash_usd": 0.0,
        "starting_cash_usd": 0.0,
        "positions": {},
        "fills": [],
        "realized_pnl_usd": 0.0,
        "watchlist": [],
        "updated_at": None,
    }


def load() -> dict[str, Any]:
    with state_lock:
        if TRADE_FILE.is_file():
            try:
                state = _default()
                state.update(json.loads(TRADE_FILE.read_text(encoding="utf-8")))
                state.setdefault("positions", {})
                state.setdefault("fills", [])
                state.setdefault("watchlist", [])
                return state
            except (OSError, ValueError):
                pass
    return _default()


def save(state: dict[str, Any]) -> None:
    with state_lock:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        TRADE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def open_mark_usd(state: dict[str, Any] | None = None) -> float:
    state = state if state is not None else load()
    total = 0.0
    for pos in (state.get("positions") or {}).values():
        mark = pos.get("mark_usd")
        if mark is None:
            mark = pos.get("cost_usd") or 0.0
        total += float(mark or 0.0)
    return total


def append_fill(state: dict[str, Any], fill: dict[str, Any]) -> None:
    state.setdefault("fills", []).insert(0, fill)
    del state["fills"][500:]


def track(state: dict[str, Any], mint: str) -> None:
    watch = state.setdefault("watchlist", [])
    if mint not in watch:
        watch.append(mint)
    del watch[500:]
