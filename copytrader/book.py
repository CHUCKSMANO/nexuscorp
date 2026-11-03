"""Copy book: follow list + copied paper positions/fills, state/copy_book.json.

Shape matches the recovered old copy book: wallets, seen signatures, positions
keyed by mint, fills, cash_usd / starting_cash_usd, realized_pnl_usd, last_scan.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from paths import STATE_DIR, state_lock

COPY_FILE = STATE_DIR / "copy_book.json"
STARTING_CASH_USD = 1000.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default() -> dict[str, Any]:
    return {
        "wallets": {},
        "seen": [],
        "positions": {},
        "fills": [],
        "cash_usd": STARTING_CASH_USD,
        "starting_cash_usd": STARTING_CASH_USD,
        "realized_pnl_usd": 0.0,
        "last_scan_at": None,
        "last_scan": None,
        "last_position_alert_at": None,
    }


def load() -> dict[str, Any]:
    with state_lock:
        if COPY_FILE.is_file():
            try:
                state = _default()
                state.update(json.loads(COPY_FILE.read_text(encoding="utf-8")))
                state.setdefault("wallets", {})
                state.setdefault("seen", [])
                state.setdefault("positions", {})
                state.setdefault("fills", [])
                return state
            except (OSError, ValueError):
                pass
    return _default()


def save(state: dict[str, Any]) -> None:
    with state_lock:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        COPY_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


# --- follow book ----------------------------------------------------------------

def follow(address: str, label: str = "") -> dict[str, Any]:
    state = load()
    existing = (state.get("wallets") or {}).get(address) or {}
    state.setdefault("wallets", {})[address] = {
        "label": label or existing.get("label") or "Wallet",
        "added_at": existing.get("added_at") or _now(),
        "bootstrapped": bool(existing.get("bootstrapped") or False),
        "last_signature": existing.get("last_signature"),
        "last_scan_at": existing.get("last_scan_at"),
    }
    save(state)
    return state["wallets"][address]


def unfollow(address: str) -> bool:
    state = load()
    removed = (state.get("wallets") or {}).pop(address, None)
    if removed is None:
        return False
    save(state)
    return True


# --- positions --------------------------------------------------------------------

def get_position(book: dict[str, Any], mint: str) -> dict[str, Any] | None:
    return (book.get("positions") or {}).get(mint)


def open_or_add_position(
    book: dict[str, Any],
    mint: str,
    symbol: str,
    token_amount: float,
    cost_usd: float,
    entry_price: float,
    pool_address: str = "",
    dex: str = "",
    signature: str = "",
) -> dict[str, Any]:
    positions = book.setdefault("positions", {})
    pos = positions.get(mint)
    if pos:
        prev_cost = float(pos.get("cost_usd") or 0.0)
        prev_amount = float(pos.get("amount") or 0.0)
        new_cost = prev_cost + float(cost_usd)
        new_amount = prev_amount + float(token_amount)
        pos["cost_usd"] = new_cost
        pos["amount"] = new_amount
        pos["entry_price"] = new_cost / new_amount if new_amount else float(entry_price)
        pos["mark_price"] = float(entry_price)
        pos["mark_usd"] = new_amount * float(entry_price)
        pos["unrealized_pnl_usd"] = float(pos["mark_usd"]) - new_cost
        pos["last_signature"] = signature or pos.get("last_signature")
    else:
        pos = {
            "mint": mint,
            "symbol": symbol,
            "desk": "copy",
            "amount": float(token_amount),
            "cost_usd": float(cost_usd),
            "entry_price": float(entry_price),
            "mark_price": float(entry_price),
            "mark_usd": float(token_amount) * float(entry_price),
            "unrealized_pnl_usd": 0.0,
            "stop_price": None,
            "take_price": None,
            "pool_address": pool_address,
            "dex": dex,
            "signature": signature,
            "opened_at": _now(),
        }
        positions[mint] = pos
    return pos


def reduce_or_close_position(
    book: dict[str, Any],
    mint: str,
    token_amount: float,
    exit_price: float,
    proceeds_usd: float,
    dex: str = "",
    signature: str = "",
) -> dict[str, Any] | None:
    positions = book.get("positions") or {}
    pos = positions.get(mint)
    if not pos:
        return None
    held = float(pos.get("amount") or 0.0)
    if held <= 0:
        positions.pop(mint, None)
        return {"realized_pnl_usd": 0.0, "pnl_pct": 0.0}

    sell_tokens = min(held, float(token_amount))
    frac = sell_tokens / held
    cost_out = float(pos.get("cost_usd") or 0.0) * frac
    realized = float(proceeds_usd) - cost_out
    entry = float(pos.get("entry_price") or 0.0)
    pnl_pct = ((float(exit_price) - entry) / entry * 100.0) if entry else 0.0

    book["cash_usd"] = float(book.get("cash_usd") or 0.0) + float(proceeds_usd)
    book["realized_pnl_usd"] = float(book.get("realized_pnl_usd") or 0.0) + realized

    if sell_tokens >= held * (1.0 - 1e-9):
        positions.pop(mint, None)
    else:
        remaining = held - sell_tokens
        pos["amount"] = remaining
        pos["cost_usd"] = float(pos.get("cost_usd") or 0.0) - cost_out
        pos["mark_price"] = float(exit_price)
        pos["mark_usd"] = remaining * float(exit_price)
        pos["unrealized_pnl_usd"] = float(pos["mark_usd"]) - float(pos["cost_usd"])
        pos["last_signature"] = signature or pos.get("last_signature")
    if dex:
        pos["dex"] = dex
    return {"realized_pnl_usd": realized, "pnl_pct": pnl_pct}


def append_fill(book: dict[str, Any], fill: dict[str, Any]) -> None:
    book.setdefault("fills", []).insert(0, fill)
    del book["fills"][500:]


def remember_signatures(book: dict[str, Any], signatures: list[str]) -> None:
    seen = book.setdefault("seen", [])
    for sig in signatures:
        if sig not in seen:
            seen.append(sig)
    del seen[1000:]


def open_mark_usd(book: dict[str, Any] | None = None) -> float:
    book = book if book is not None else load()
    total = 0.0
    for pos in (book.get("positions") or {}).values():
        mark = pos.get("mark_usd")
        if mark is None:
            mark = pos.get("cost_usd") or 0.0
        total += float(mark or 0.0)
    return total
