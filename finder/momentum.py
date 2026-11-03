"""Momentum tracking: keep a bounded snapshot of alerted tokens for follow-up."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import config
from finder import book as finder_book


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def start_tracking(book: dict[str, Any], mint: str, symbol: str, pair: dict[str, Any]) -> None:
    """Add (or refresh) a tracked token. Evicts the oldest beyond FINDER_MAX_TRACKED."""
    tracked = book.setdefault("tracked", {})
    liquidity = ((pair or {}).get("liquidity") or {}).get("usd")
    volume = ((pair or {}).get("volume") or {}).get("h24")

    existing = tracked.get(mint) or {}
    tracked[mint] = {
        "mint": mint,
        "symbol": symbol or existing.get("symbol") or "?",
        "pair_address": (pair or {}).get("pair_address") or existing.get("pair_address"),
        "dex": (pair or {}).get("dexId") or existing.get("dex"),
        "price_usd": (pair or {}).get("priceUsd") or existing.get("price_usd"),
        "liquidity_usd": float(liquidity) if liquidity is not None else existing.get("liquidity_usd"),
        "volume_24h": float(volume) if volume is not None else existing.get("volume_24h"),
        "added_at": existing.get("added_at") or _now(),
        "last_seen_at": _now(),
        "last_seen_epoch": time.time(),
    }

    cap = max(1, int(config.FINDER_MAX_TRACKED))
    while len(tracked) > cap:
        oldest = min(tracked.items(), key=lambda kv: kv[1].get("last_seen_epoch") or 0.0)
        tracked.pop(oldest[0], None)

    book["tracked"] = tracked
    finder_book.save(book)
