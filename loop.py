"""Yield desk loop: one decision pass. Sync (app.py wraps it in asyncio.to_thread).

Rules: accrue paper interest, refresh APY from live pools, ask treasurer.decide,
execute deploy / rebalance in paper, record outcome, persist runtime marker.
"""

from __future__ import annotations

import json
from typing import Any

import killswitch
import scout
import treasurer
import wallet
import yield_book
from runtime import mark_yield_tick


def _free_cash() -> float:
    state = wallet.load()
    return float(state.get("yield_cash_usd") or 0.0) + float(state.get("cash_usd") or 0.0)


def _refresh_position_apy(pools: list[dict[str, Any]]) -> dict[str, Any]:
    ystate = yield_book.load()
    position = ystate.get("position")
    if position and pools:
        match = next(
            (
                p
                for p in pools
                if p.get("pool_id") == position.get("pool_id")
                or p.get("project") == position.get("project")
            ),
            None,
        )
        if match:
            yield_book.refresh_apy(match)
            ystate = yield_book.load()
    return ystate


def _execute(decision: dict[str, Any], position: dict[str, Any] | None) -> dict[str, Any]:
    """Apply a deploy/rebalance decision to the paper books."""
    dest = decision.get("dest")
    amount = float(decision.get("amount_usd") or 0.0)
    action = decision.get("action")

    if action == "rebalance":
        try:
            unwound = yield_book.unwind_all()
            if unwound > 0:
                wallet.return_to_yield(
                    unwound, note=f"rebalance out of {position.get('project') if position else '?'}"
                )
            wallet.pull_for_yield(amount)
        except ValueError as exc:
            yield_book.set_outcome("hold", f"rebalance aborted: {exc}")
            return {"executed": "hold", "error": str(exc)}
        yield_book.deploy(dest, amount, decision.get("reason") or "")
        return {"executed": "rebalance", "amount_usd": amount}

    if action == "deploy":
        try:
            wallet.pull_for_yield(amount)
        except ValueError as exc:
            yield_book.set_outcome("hold", f"deploy aborted: {exc}")
            return {"executed": "hold", "error": str(exc)}
        yield_book.deploy(dest, amount, decision.get("reason") or "")
        return {"executed": "deploy", "amount_usd": amount}

    yield_book.set_outcome("hold", decision.get("reason") or "hold")
    return {"executed": "hold"}


def tick() -> dict[str, Any]:
    frozen = killswitch.frozen("yield")
    pools, source = scout.read_pools()
    yield_book.accrue()

    ystate = _refresh_position_apy(pools)
    position = ystate.get("position")
    position_value = yield_book.position_deployed_usd()
    free_cash = _free_cash()

    decision = treasurer.decide(pools, position, position_value, free_cash, source, frozen)
    result: dict[str, Any] = {}
    if decision.get("would_send") and decision.get("action") in ("deploy", "rebalance"):
        result = _execute(decision, position)
        ystate = yield_book.load()
    else:
        yield_book.set_outcome("hold", decision.get("reason") or "hold")
        ystate = yield_book.load()

    summary = {
        "action": decision.get("action"),
        "executed": result.get("executed") or decision.get("action"),
        "reason": ystate.get("last_reason") or decision.get("reason"),
        "amount_usd": decision.get("amount_usd"),
        "dest": (decision.get("dest") or {}).get("project"),
        "source": source,
        "blockers": decision.get("blockers") or [],
        "free_cash_usd": round(free_cash, 2),
        "position_value_usd": round(position_value, 2),
    }
    if result.get("error"):
        summary["error"] = result["error"]
    mark_yield_tick(summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(tick(), indent=2))
