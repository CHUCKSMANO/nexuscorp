"""Scribe: writes logs and optional Telegram alerts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import requests

from config import (
    LOG_FILE,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    DISCORD_BOT_TOKEN,
    DISCORD_CHANNEL_ID,
    DISCORD_FINDER_CHANNEL_ID,
    DISCORD_YIELD_CHANNEL_ID,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_log(event: dict[str, Any]) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    event = {"ts": _now(), **event}
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def print_tick(markets, decision, portfolio, wallet=None) -> None:
    best = markets.get("best")
    print("\n======== THE TOKEN YIELDER ========")
    print(f"allowlisted USDC pools: {markets.get('count', 0)}")
    if best:
        print(f"best: {best['project']}  {best['apy']:.2f}%  TVL ${best['tvl_usd']:,.0f}")
    print(f"decision: {decision.get('action')} — {decision.get('reason')}")
    pos = portfolio.get("position") or {}
    print(
        f"position: {pos.get('project', 'cash')} "
        f"${float(pos.get('amount_usd') or 0):,.2f} @ {float(pos.get('apy') or 0):.2f}%"
    )
    if wallet and wallet.get("pubkey"):
        print(f"wallet: {wallet['pubkey']}")
        print(f"devnet SOL: {wallet.get('devnet_sol')}")
        print(f"mainnet SOL: {wallet.get('mainnet_sol')}")
    print("======================\n")


def telegram(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
        r.raise_for_status()
    except Exception as exc:
        print(f"telegram alert failed: {exc}")


def daily_pnl_line(portfolio: dict[str, Any]) -> str:
    pos = portfolio.get("position") or {}
    amount = float(pos.get("amount_usd") or 0)
    apy = float(pos.get("apy") or 0)
    per_day = amount * (apy / 100.0) / 365.0
    return (
        f"paper position {pos.get('project', 'none')} ${amount:,.0f} "
        f"at {apy:.2f}% ≈ ${per_day:.2f}/day"
    )


def discord(text: str | None = None, channel_id: str | None = None, embed: dict | None = None) -> None:
    dest = str(channel_id or DISCORD_FINDER_CHANNEL_ID or DISCORD_YIELD_CHANNEL_ID or DISCORD_CHANNEL_ID or "").strip()
    if not DISCORD_BOT_TOKEN or not dest:
        return
    payload: dict[str, Any] = {}
    if text:
        payload["content"] = text
    if embed:
        payload["embeds"] = [embed]
    if not payload:
        return
    url = f"https://discord.com/api/v10/channels/{dest}/messages"
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"},
            json=payload,
            timeout=10,
        )
        r.raise_for_status()
    except Exception as exc:
        print(f"discord alert failed: {exc}")
