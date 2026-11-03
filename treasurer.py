"""Treasurer: pure decision function for the yield desk.

Rules (README): only allowlisted projects/symbols, move only when a pool beats
the current position by >= MIN_EDGE_APY, only move >= MIN_MOVE_USD, keep
GAS_BUFFER_USD undeployed, ignore pools below MIN_TVL_USD.
"""

from __future__ import annotations

from typing import Any

import config


def decide(
    pools: list[dict[str, Any]],
    position: dict[str, Any] | None,
    position_value: float,
    free_cash: float,
    source: str,
    frozen: bool = False,
) -> dict[str, Any]:
    """Return {action, reason, amount_usd, dest, would_send, blockers}.

    action is one of: deploy, rebalance, hold.
    free_cash is cash available to the yield desk (hub + yield bucket).
    """
    blockers: list[str] = []
    best_pool = pools[0] if pools else None

    if frozen:
        blockers.append("yield desk frozen by killswitch")
    if not pools:
        blockers.append(f"no allowlisted USDC pool available (source: {source})")

    available = max(0.0, float(free_cash) - config.GAS_BUFFER_USD)

    hold: dict[str, Any] = {
        "action": "hold",
        "reason": "",
        "amount_usd": 0.0,
        "dest": best_pool,
        "would_send": False,
        "blockers": blockers,
    }

    if frozen:
        hold["reason"] = "hold — yield desk frozen"
        return hold
    if not best_pool:
        hold["reason"] = "hold — no allowlisted pool to send to"
        return hold
    if float(best_pool.get("tvl_usd") or 0.0) < config.MIN_TVL_USD:
        blockers.append(
            f"best pool TVL ${float(best_pool.get('tvl_usd') or 0):,.0f} "
            f"< MIN_TVL_USD ${config.MIN_TVL_USD:,.0f}"
        )
        hold["reason"] = "hold — best pool below MIN_TVL_USD"
        return hold

    if position:
        matching = [p for p in pools if p.get("pool_id") == position.get("pool_id")]
        if not matching:
            matching = [p for p in pools if p.get("project") == position.get("project")]
        pos_apy = float(position.get("apy") or 0.0)
        pos_project = position.get("project") or "position"

        if matching and matching[0].get("pool_id") == best_pool.get("pool_id"):
            hold["reason"] = "hold — position already in the best allowlisted pool"
            hold["blockers"] = blockers
            return hold

        edge = float(best_pool.get("apy") or 0.0) - pos_apy
        if not matching:
            reason = (
                f"rebalance — {pos_project} no longer allowlisted, "
                f"move ${position_value:,.2f} -> {best_pool['project']} "
                f"{float(best_pool.get('apy') or 0):.2f}%"
            )
        elif edge >= config.MIN_EDGE_APY:
            reason = (
                f"rebalance — move ${position_value + available:,.2f} from {pos_project} "
                f"{pos_apy:.2f}% -> {best_pool['project']} "
                f"{float(best_pool.get('apy') or 0):.2f}% (edge {edge:.2f}% >= "
                f"MIN_EDGE_APY {config.MIN_EDGE_APY:.2f}%)"
            )
        else:
            blockers.append(
                f"best pool beats position by {edge:+.2f}% APY "
                f"< MIN_EDGE_APY {config.MIN_EDGE_APY:.2f}%"
            )
            hold["reason"] = (
                f"hold — edge {edge:+.2f}% below MIN_EDGE_APY {config.MIN_EDGE_APY:.2f}%"
            )
            hold["blockers"] = blockers
            return hold

        return {
            "action": "rebalance",
            "reason": reason,
            "amount_usd": round(position_value + available, 2),
            "dest": best_pool,
            "would_send": True,
            "blockers": blockers,
        }

    # No position yet: fresh deployment.
    if available < config.MIN_MOVE_USD:
        blockers.append(
            f"available ${available:,.2f} < MIN_MOVE_USD ${config.MIN_MOVE_USD:,.2f} "
            f"(GAS_BUFFER_USD ${config.GAS_BUFFER_USD:,.2f} stays undeployed)"
        )
        hold["reason"] = "hold — not enough free cash to move"
        hold["blockers"] = blockers
        return hold

    return {
        "action": "deploy",
        "reason": (
            f"deploy — move ${available:,.2f} from cash 0.00% -> "
            f"{best_pool['project']} {float(best_pool.get('apy') or 0):.2f}%"
        ),
        "amount_usd": round(available, 2),
        "dest": best_pool,
        "would_send": True,
        "blockers": blockers,
    }
