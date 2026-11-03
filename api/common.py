"""Shared payload builders for the Swift contract (SystemHealth, StatusResponse, ...)."""

from __future__ import annotations

from typing import Any

import config
import killswitch
import scout
import wallet
import yield_book
from copytrader import book as copy_book
from finder import book as finder_book
from runtime import runtime_info


def frozen_state() -> dict[str, Any]:
    return killswitch.get_state()


def health_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "name": "The Token Yielder",
        "mode": config.MODE,
        "finder_execution": config.FINDER_EXECUTION,
        "copy_execution": config.COPY_EXECUTION,
        "frozen": frozen_state(),
        "runtime": runtime_info(),
    }


def yield_status() -> dict[str, Any]:
    yield_book.accrue()
    ystate = yield_book.load()
    position = ystate.get("position")
    pools, source = scout.read_pools()
    best_pool = pools[0] if pools else None

    pos_payload = None
    per_day = 0.0
    if position:
        amount = float(position.get("amount_usd") or 0.0)
        apy = float(position.get("apy") or 0.0)
        pos_payload = {
            "project": position.get("project"),
            "amount_usd": round(amount, 2),
            "apy": apy,
            "pool_id": position.get("pool_id"),
        }
        per_day = yield_book.paper_per_day(amount, apy)

    def pool_payload(pool: dict[str, Any] | None) -> dict[str, Any] | None:
        if not pool:
            return None
        return {
            "project": pool.get("project"),
            "symbol": pool.get("symbol"),
            "apy": pool.get("apy"),
            "tvl_usd": pool.get("tvl_usd"),
            "pool_id": pool.get("pool_id"),
            "source": pool.get("source"),
        }

    return {
        "desk": "yield",
        "mode": config.MODE,
        "frozen": killswitch.frozen("yield"),
        "wallet": config.WALLET_PUBKEY,
        "cash_usd": round(wallet.yield_cash(), 2),
        "position": pos_payload,
        "paper_per_day": round(per_day, 6),
        "lifetime_earned_usd": round(float(ystate.get("lifetime_earned_usd") or 0.0), 6),
        "best": pool_payload(best_pool),
        "source": source,
        "last_action": ystate.get("last_action"),
        "last_reason": ystate.get("last_reason"),
    }


def yield_stands() -> dict[str, Any]:
    pools, source = scout.read_pools()
    return {
        "source": source,
        "count": len(pools),
        "best": pools[0] if pools else None,
        "allowed": pools,
    }


def finder_status() -> dict[str, Any]:
    book = finder_book.load()
    return {
        "desk": "finder",
        "tracked_count": len(book.get("tracked") or {}),
        "last_scan_at": book.get("last_scan_at") or runtime_info().get("last_finder_scan_at"),
    }


def _copy_position_row(mint: str, pos: dict[str, Any]) -> dict[str, Any]:
    row = dict(pos)
    row["mint"] = row.get("mint") or mint
    row["desk"] = "copy"
    return row


def copy_status() -> dict[str, Any]:
    cstate = copy_book.load()
    positions = {
        mint: _copy_position_row(mint, pos)
        for mint, pos in (cstate.get("positions") or {}).items()
    }
    wallets = cstate.get("wallets") or {}
    recent_fills = list(cstate.get("fills") or [])[:50]
    return {
        "desk": "copy",
        "wallet_count": len(wallets),
        "wallets": wallets,
        "open_positions": len(positions),
        "positions": positions,
        "recent_fills": recent_fills,
        "fills": recent_fills,
        "cash_usd": round(float(cstate.get("cash_usd") or 0.0), 2),
    }


def aggregate_status() -> dict[str, Any]:
    return {
        "frozen": frozen_state(),
        "yield": yield_status(),
        "wallet": wallet.status(),
        "finder": finder_status(),
        "copy": copy_status(),
        "runtime": runtime_info(),
    }
