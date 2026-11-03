"""One finder cycle: fetch newest mints, inspect them concurrently, alert passers.

v1 is alerts-only (FINDER_EXECUTION="alerts"): passing tokens are logged to
Discord/Telegram (no-op when tokens are blank) and added to the book — nothing
is ever bought from the finder desk.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

import killswitch
from agents import scribe
from config import DISCORD_FINDER_CHANNEL_ID, FINDER_EXECUTION, FINDER_MAX_TRACKED
from finder import alerts, book as finder_book, filters as finder_filters, momentum, scan
from runtime import mark_finder_scan

TIMEOUT = 20.0


async def _log(event: dict[str, Any]) -> None:
    await asyncio.to_thread(scribe.write_log, {"desk": "finder", **event})


async def _inspect_mint(
    client: httpx.AsyncClient, mint: str, filters: dict[str, float], sem: asyncio.Semaphore
) -> dict[str, Any] | None:
    try:
        async with sem:
            result = await scan.inspect(client, mint, filters)
        return result
    except Exception as exc:
        await _log({"mint": mint, "result": "error", "reason": f"{type(exc).__name__}: {exc}"})
        return None


async def run_cycle() -> dict:
    if FINDER_EXECUTION == "live":
        summary = {"ok": False, "error": "FINDER_EXECUTION=live is not wired; v1 is alerts-only"}
        mark_finder_scan(summary)
        return summary
    if killswitch.frozen("finder"):
        summary = {"ok": False, "error": "finder desk frozen", "fetched": 0, "checked": 0, "passed": 0}
        mark_finder_scan(summary)
        return summary

    filters = finder_filters.load()
    state = finder_book.load()
    alerted = set(state.get("alerted") or [])

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        mints = await scan.latest_solana_mints(client)
        candidates = [m for m in mints if m not in alerted]

        # Ensure any previously alerted tokens appearing in market feeds remain actively tracked up to cap
        tracked_set = set(state.get("tracked", {}).keys())
        for m in mints:
            if len(tracked_set) >= FINDER_MAX_TRACKED:
                break
            if m in alerted and m not in tracked_set:
                pair = await scan.best_pair(client, m)
                if pair:
                    symbol = (pair.get("baseToken") or {}).get("symbol") or "?"
                    momentum.start_tracking(book=state, mint=m, symbol=symbol, pair=pair)
                    tracked_set.add(m)

        checked = 0
        passed = 0
        passed_tokens = []
        sem = asyncio.Semaphore(6)

        # Inspect candidates concurrently in parallel batches
        tasks = [_inspect_mint(client, m, filters, sem) for m in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if not res or isinstance(res, Exception):
                continue
            checked += 1
            mint = res["mint"]
            pair = res["pair"]
            stats = res["stats"]
            sec = res["sec_report"]
            risk_flags = res["risk_flags"]

            if not res["ok"]:
                await _log({"mint": mint, "result": "reject", "reason": res["reason"], "stats": stats})
                continue

            passed += 1
            symbol = (pair.get("baseToken") or {}).get("symbol") or "?"
            passed_tokens.append({"mint": mint, "symbol": symbol, "score": stats.get("composite_score")})

            # 1. Discord alert
            embed = alerts.new_token_embed(
                pair=pair,
                risk_score=res["risk_score"],
                mint=mint,
                stats=stats,
                risk_flags=risk_flags,
                security=sec,
            )
            await asyncio.to_thread(
                scribe.discord, channel_id=DISCORD_FINDER_CHANNEL_ID, embed=embed
            )

            # 2. Telegram alert
            tg_text = alerts.new_token_telegram_text(
                pair=pair,
                risk_score=res["risk_score"],
                mint=mint,
                stats=stats,
                risk_flags=risk_flags,
            )
            await asyncio.to_thread(scribe.telegram, tg_text)

            # 3. Add to alerted book & momentum tracking
            alerted.add(mint)
            state["alerted"] = list(alerted)
            momentum.start_tracking(
                book=state,
                mint=mint,
                symbol=symbol,
                pair=pair,
            )
            await _log(
                {
                    "mint": mint,
                    "result": "pass",
                    "symbol": symbol,
                    "risk_score": res["risk_score"],
                    "composite_score": stats.get("composite_score"),
                }
            )

    state["last_scan_at"] = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).isoformat(timespec="seconds")
    finder_book.save(state)

    summary = {
        "ok": True,
        "execution": "alerts",
        "fetched": len(mints),
        "candidates": len(candidates),
        "checked": checked,
        "passed": passed,
        "passed_tokens": passed_tokens,
        "tracked": len(state.get("tracked") or {}),
        "alerted_total": len(state.get("alerted") or []),
    }
    mark_finder_scan(summary)
    return summary
