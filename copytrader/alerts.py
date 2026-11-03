"""Copy desk alerts: Discord/Telegram notifications for replicated trades.

All scribe calls are blocking `requests` under the hood — callers running from
the async engine MUST wrap them in `asyncio.to_thread` (README warning).
Blank tokens make agents/scribe.py a no-op, so this is safe in paper mode.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agents import scribe
from config import DISCORD_COPY_CHANNEL_ID


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_copy_log(event: dict[str, Any]) -> None:
    scribe.write_log({"desk": "copy", **event})


def _trade_line(trade: dict[str, Any], label: str) -> str:
    side = str(trade.get("side") or "?").upper()
    symbol = trade.get("symbol") or (trade.get("mint") or "?")[:6]
    amount = trade.get("amount") or trade.get("token_amount")
    line = f"[copy] {label}: {side} {symbol}"
    if amount is not None:
        try:
            line += f" x{float(amount):,.4f}"
        except (TypeError, ValueError):
            pass
    return line


def send_copy_alert(
    trade: dict[str, Any],
    fill: dict[str, Any] | None = None,
    label: str = "",
    error_reason: str | None = None,
) -> None:
    """Notify about a replicated (or failed-to-replicate) copy trade."""
    label = label or "wallet"
    lines = [_trade_line(trade, label)]
    mint = trade.get("mint") or (fill or {}).get("mint")
    if mint:
        lines.append(f"mint: {mint}")

    if error_reason:
        lines.append(f"not copied: {error_reason}")
        text = "\n".join(lines)
        write_copy_log({"event": "copy_skipped", "trade": trade, "label": label, "error": error_reason})
        scribe.discord(text, channel_id=DISCORD_COPY_CHANNEL_ID)
        scribe.telegram(text)
        return

    if fill:
        side = str(fill.get("side") or trade.get("side") or "").lower()
        usd = fill.get("usd") if fill.get("usd") is not None else fill.get("cost_usd")
        price = fill.get("fill_price_usd") or fill.get("price")
        if usd is not None:
            lines.append(f"paper {side}: ${float(usd):,.2f}")
        if price is not None:
            try:
                lines.append(f"price: ${float(price):,.8g}")
            except (TypeError, ValueError):
                pass
        if fill.get("realized_pnl_usd") is not None:
            lines.append(f"realized PnL: ${float(fill['realized_pnl_usd']):,.2f}")
        lines.append("mode: PAPER")

    text = "\n".join(lines)
    write_copy_log({"event": "copy_trade", "trade": trade, "fill": fill, "label": label})
    embed = {
        "title": f"Copy trade: {str(trade.get('side') or 'trade').upper()} "
        f"{trade.get('symbol') or ''}".strip(),
        "description": "\n".join(lines)[:3800],
        "color": 3066993,
        "timestamp": _now(),
    }
    scribe.discord(channel_id=DISCORD_COPY_CHANNEL_ID, embed=embed)
    scribe.telegram(text)


def new_token_embed(
    mint: str,
    symbol: str | None = None,
    price_usd: float | None = None,
    pair: dict[str, Any] | None = None,
    stats: dict[str, Any] | None = None,
    desk: str = "copy",
) -> dict[str, Any]:
    """Discord embed for a token the copy desk just entered."""
    fields = [{"name": "mint", "value": mint, "inline": False}]
    if price_usd:
        fields.append({"name": "price", "value": f"${float(price_usd):.8g}", "inline": True})
    liquidity = (pair or {}).get("liquidity") or {}
    if liquidity.get("usd"):
        fields.append(
            {"name": "liquidity", "value": f"${float(liquidity['usd']):,.0f}", "inline": True}
        )
    if stats:
        for key in ("volume_24h", "market_cap"):
            if stats.get(key) is not None:
                fields.append(
                    {"name": key, "value": f"${float(stats[key]):,.0f}", "inline": True}
                )
    return {
        "title": f"{symbol or 'TOKEN'} — opened on the {desk} desk (paper)",
        "url": f"https://dexscreener.com/solana/{mint}",
        "description": f"Paper copy position opened for `{mint}`.",
        "color": 15844367,
        "fields": fields,
        "timestamp": _now(),
    }


def new_token_telegram_text(
    mint: str,
    symbol: str | None = None,
    price_usd: float | None = None,
    stats: dict[str, Any] | None = None,
    desk: str = "copy",
) -> str:
    lines = [f"[{desk}] paper position opened: {symbol or 'TOKEN'}"]
    if price_usd:
        lines.append(f"price: ${float(price_usd):.8g}")
    if stats and stats.get("liquidity_usd"):
        lines.append(f"liquidity: ${float(stats['liquidity_usd']):,.0f}")
    lines.append(f"mint: {mint}")
    return "\n".join(lines)
