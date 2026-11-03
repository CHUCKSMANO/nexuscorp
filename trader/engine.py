"""Paper trade engine: buy, sell, and mark-to-market against live DexScreener prices.

Everything is PAPER: fills move simulated cash in state/trade_book.json.
Prices always come from DexScreener (live) or, when DexScreener is unreachable,
from the last real mark stored on the position — never from invented numbers.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import config
import killswitch
import market
from trader import book as trade_book


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _check_frozen() -> None:
    if killswitch.frozen("all"):
        raise ValueError("trade desk frozen by killswitch")


def _require_price(mint: str) -> tuple[float, dict[str, Any]]:
    price, item = market.price_for(mint)
    if price is None or price <= 0:
        raise ValueError(f"no live market data for mint {mint}")
    return price, item or {}


def _fill(
    side: str,
    mint: str,
    symbol: str | None,
    *,
    usd: float | None = None,
    cost_usd: float | None = None,
    proceeds_usd: float | None = None,
    price: float | None = None,
    entry_price: float | None = None,
    reason: str = "",
    dex: str | None = None,
) -> dict[str, Any]:
    return {
        "ts": _now(),
        "side": side,
        "symbol": symbol,
        "mint": mint,
        "usd": usd,
        "cost_usd": cost_usd,
        "proceeds_usd": proceeds_usd,
        "price": price,
        "entry_price": entry_price,
        "reason": reason,
        "dex": dex,
        "desk": "trade",
    }


def buy(
    mint: str,
    amount_usd: float,
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
) -> dict[str, Any]:
    _check_frozen()
    mint = (mint or "").strip()
    if not mint:
        raise ValueError("mint is required")
    if amount_usd is None or amount_usd <= 0:
        raise ValueError("amount_usd must be positive")
    max_trade = float(config.MAX_LIVE_USD or 0.0)
    if max_trade > 0 and amount_usd > max_trade + 1e-9:
        raise ValueError(
            f"amount_usd ${amount_usd:,.2f} exceeds max_trade_usd ${max_trade:,.2f}"
        )

    price, item = _require_price(mint)

    state = trade_book.load()
    cash = float(state.get("cash_usd") or 0.0)
    if amount_usd > cash + 1e-9:
        raise ValueError(
            f"insufficient trade desk cash (${cash:,.2f} available); "
            "fund the desk from the wallet first"
        )

    token_amount = amount_usd / price
    positions = state.setdefault("positions", {})
    pos = positions.get(mint)
    symbol = item.get("symbol")
    dex = item.get("dex")

    if pos:
        prev_cost = float(pos.get("cost_usd") or 0.0)
        prev_amount = float(pos.get("amount") or 0.0)
        new_cost = prev_cost + amount_usd
        new_amount = prev_amount + token_amount
        pos["cost_usd"] = new_cost
        pos["amount"] = new_amount
        pos["entry_price"] = new_cost / new_amount if new_amount else price
        if symbol and not pos.get("symbol"):
            pos["symbol"] = symbol
    else:
        stop_price = None
        take_price = None
        if stop_loss_pct is not None and stop_loss_pct > 0:
            stop_price = price * (1.0 - float(stop_loss_pct) / 100.0)
        if take_profit_pct is not None and take_profit_pct > 0:
            take_price = price * (1.0 + float(take_profit_pct) / 100.0)
        pos = {
            "mint": mint,
            "symbol": symbol,
            "desk": "trade",
            "amount": token_amount,
            "cost_usd": amount_usd,
            "entry_price": price,
            "stop_price": stop_price,
            "take_price": take_price,
            "dex": dex,
            "opened_at": _now(),
        }
        positions[mint] = pos

    pos["mark_price"] = price
    pos["mark_usd"] = float(pos.get("amount") or 0.0) * price
    pos["unrealized_pnl_usd"] = float(pos["mark_usd"]) - float(pos.get("cost_usd") or 0.0)

    state["cash_usd"] = cash - amount_usd
    trade_book.append_fill(
        state,
        _fill(
            "buy",
            mint,
            pos.get("symbol") or symbol,
            usd=amount_usd,
            cost_usd=amount_usd,
            price=price,
            entry_price=pos.get("entry_price"),
            reason="manual buy",
            dex=dex,
        ),
    )
    trade_book.track(state, mint)
    state["updated_at"] = _now()
    trade_book.save(state)
    return status()


def _sell_internal(
    state: dict[str, Any],
    mint: str,
    amount_usd: float | None,
    price_hint: float | None,
    reason: str,
) -> dict[str, Any]:
    positions = state.get("positions") or {}
    pos = positions.get(mint)
    if not pos:
        raise ValueError(f"no open position for mint {mint}")

    price = price_hint
    dex = pos.get("dex")
    price_source = "live dexscreener"
    if price is None or price <= 0:
        live_price, item = market.price_for(mint)
        if live_price and live_price > 0:
            price = live_price
            dex = item.get("dex") or dex
        else:
            price = pos.get("mark_price") or pos.get("entry_price")
            price_source = "last stored mark (dexscreener unavailable)"
    if not price or price <= 0:
        raise ValueError(f"no price available to sell mint {mint}")

    held = float(pos.get("amount") or 0.0)
    if held <= 0:
        raise ValueError(f"position for {mint} is empty")
    cost = float(pos.get("cost_usd") or 0.0)

    if amount_usd is None or amount_usd <= 0:
        sell_tokens = held
    else:
        sell_tokens = min(held, float(amount_usd) / price)
    if sell_tokens <= 0:
        raise ValueError("amount_usd too small to sell any tokens")

    proceeds = sell_tokens * price
    frac = sell_tokens / held
    cost_out = cost * frac
    realized_delta = proceeds - cost_out

    state["cash_usd"] = float(state.get("cash_usd") or 0.0) + proceeds
    state["realized_pnl_usd"] = float(state.get("realized_pnl_usd") or 0.0) + realized_delta

    fill_reason = reason if price_source == "live dexscreener" else f"{reason} [{price_source}]"
    trade_book.append_fill(
        state,
        _fill(
            "sell",
            mint,
            pos.get("symbol"),
            usd=proceeds,
            cost_usd=cost_out,
            proceeds_usd=proceeds,
            price=price,
            entry_price=pos.get("entry_price"),
            reason=fill_reason,
            dex=dex,
        ),
    )

    if sell_tokens >= held * (1.0 - 1e-9):
        positions.pop(mint, None)
    else:
        remaining = held - sell_tokens
        pos["amount"] = remaining
        pos["cost_usd"] = cost - cost_out
        pos["mark_price"] = price
        pos["mark_usd"] = remaining * price
        pos["unrealized_pnl_usd"] = pos["mark_usd"] - pos["cost_usd"]
    state["updated_at"] = _now()
    return {"proceeds_usd": proceeds, "realized_delta": realized_delta}


def sell(mint: str, amount_usd: float | None = None) -> dict[str, Any]:
    _check_frozen()
    mint = (mint or "").strip()
    if not mint:
        raise ValueError("mint is required")
    state = trade_book.load()
    _sell_internal(state, mint, amount_usd, None, "manual sell")
    trade_book.save(state)
    return status()


async def mark_all() -> dict[str, Any]:
    """Re-price open positions from live market data; enforce stop/take orders."""
    state = trade_book.load()
    positions = state.get("positions") or {}
    if positions:
        marks = await asyncio.to_thread(market.prices_for, list(positions.keys()))
        triggers: list[tuple[str, str]] = []
        for mint, pos in list(positions.items()):
            item = marks.get(mint)
            price = (item or {}).get("price_usd")
            if price and price > 0:
                pos["mark_price"] = price
                pos["mark_usd"] = float(pos.get("amount") or 0.0) * price
                pos["unrealized_pnl_usd"] = float(pos["mark_usd"]) - float(pos.get("cost_usd") or 0.0)
            mark = pos.get("mark_price")
            if mark is None:
                continue
            stop = pos.get("stop_price")
            take = pos.get("take_price")
            if stop is not None and mark <= float(stop):
                triggers.append((mint, "stop loss hit"))
            elif take is not None and mark >= float(take):
                triggers.append((mint, "take profit hit"))

        for mint, reason in triggers:
            if mint not in (state.get("positions") or {}):
                continue
            pos = state["positions"][mint]
            try:
                _sell_internal(
                    state, mint, None, pos.get("mark_price"), reason
                )
            except ValueError:
                continue
        state["updated_at"] = _now()
        trade_book.save(state)
    return status()


def status() -> dict[str, Any]:
    state = trade_book.load()
    positions = state.get("positions") or {}
    open_mark = 0.0
    unrealized = 0.0
    rows: list[dict[str, Any]] = []
    for pos in positions.values():
        mark_usd = pos.get("mark_usd")
        if mark_usd is None:
            mark_usd = float(pos.get("cost_usd") or 0.0)
        open_mark += float(mark_usd)
        unrealized += float(pos.get("unrealized_pnl_usd") or 0.0)
        rows.append(dict(pos))
    rows.sort(key=lambda p: float(p.get("mark_usd") or 0.0), reverse=True)

    cash = float(state.get("cash_usd") or 0.0)
    fills = list(state.get("fills") or [])
    tracked = set(state.get("watchlist") or []) | set(positions.keys())
    max_trade = float(config.MAX_LIVE_USD or 0.0)
    return {
        "desk": "trade",
        "mode": config.MODE,
        "live_enabled": bool(config.LIVE_ENABLED),
        "frozen": killswitch.frozen("all"),
        "cash_usd": round(cash, 2),
        "open_mark_usd": round(open_mark, 2),
        "unrealized_pnl_usd": round(unrealized, 2),
        "realized_pnl_usd": round(float(state.get("realized_pnl_usd") or 0.0), 2),
        "equity_usd": round(cash + open_mark, 2),
        "open_positions": len(rows),
        "positions": rows,
        "fills": fills[:200],
        "tracked_count": len(tracked),
        "max_trade_usd": max_trade,
    }
