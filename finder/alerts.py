"""Finder alerts: Discord embed + Telegram text for a passing new token.

Called from finder/cycle.py via asyncio.to_thread (blocking scribe I/O).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fmt_usd(value: Any) -> str | None:
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return None


def new_token_embed(
    pair: dict[str, Any],
    risk_score: Any = None,
    mint: str = "",
    stats: dict[str, Any] | None = None,
    risk_flags: list[str] | None = None,
    security: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = (pair or {}).get("baseToken") or {}
    symbol = base.get("symbol") or "TOKEN"
    name = base.get("name") or symbol
    stats = stats or {}

    fields: list[dict[str, Any]] = [{"name": "mint", "value": mint or base.get("address") or "?", "inline": False}]
    price = stats.get("price_usd") or (pair or {}).get("priceUsd")
    if price:
        fields.append({"name": "price", "value": f"${float(price):.8g}", "inline": True})
    for label, key in (
        ("liquidity", "liquidity_usd"),
        ("volume 24h", "volume_24h"),
        ("market cap", "market_cap"),
    ):
        rendered = _fmt_usd(stats.get(key))
        if rendered:
            fields.append({"name": label, "value": rendered, "inline": True})
    if stats.get("buy_pressure") is not None:
        fields.append(
            {"name": "buy pressure", "value": f"{float(stats['buy_pressure']):.0%}", "inline": True}
        )
    if stats.get("composite_score") is not None:
        fields.append(
            {"name": "composite score", "value": f"{float(stats['composite_score']):.1f}/100", "inline": True}
        )
    if risk_score is not None:
        fields.append({"name": "risk score", "value": f"{float(risk_score):.0f}/100", "inline": True})
    if risk_flags:
        fields.append({"name": "risk flags", "value": ", ".join(risk_flags)[:256], "inline": False})
    if security:
        unmeasurable = security.get("unmeasurable") or []
        note = security.get("note")
        detail = note or ""
        if unmeasurable:
            detail = (detail + " | " if detail else "") + "; ".join(unmeasurable)
        if detail:
            fields.append({"name": "security", "value": detail[:500], "inline": False})

    pair_address = (pair or {}).get("pairAddress") or ""
    url = f"https://dexscreener.com/solana/{pair_address}" if pair_address else None
    return {
        "title": f"New token alert: {symbol} ({name})",
        "url": url,
        "description": f"Finder passed `{mint or base.get('address')}` on the new-mint scan (alerts-only, no execution).",
        "color": 15158332,
        "fields": fields,
        "timestamp": _now(),
    }


def new_token_telegram_text(
    pair: dict[str, Any],
    risk_score: Any = None,
    mint: str = "",
    stats: dict[str, Any] | None = None,
    risk_flags: list[str] | None = None,
) -> str:
    base = (pair or {}).get("baseToken") or {}
    stats = stats or {}
    symbol = base.get("symbol") or "TOKEN"
    lines = [f"[finder] new token: {symbol}"]

    price = stats.get("price_usd") or (pair or {}).get("priceUsd")
    if price:
        lines.append(f"price: ${float(price):.8g}")
    liq = _fmt_usd(stats.get("liquidity_usd"))
    if liq:
        lines.append(f"liquidity: {liq}")
    vol = _fmt_usd(stats.get("volume_24h"))
    if vol:
        lines.append(f"volume24h: {vol}")
    if stats.get("buy_pressure") is not None:
        lines.append(f"buy pressure: {float(stats['buy_pressure']):.0%}")
    if risk_score is not None:
        lines.append(f"risk: {float(risk_score):.0f}/100")
    if risk_flags:
        lines.append(f"flags: {', '.join(risk_flags)}")
    lines.append(f"mint: {mint or base.get('address')}")
    lines.append("mode: alerts-only (no trade sent)")
    return "\n".join(lines)
