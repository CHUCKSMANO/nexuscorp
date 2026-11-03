"""Yield desk routes: /yield/status, /yield/stands, /yield/plan, POST /yield/tick."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

import config
import killswitch
import loop as yield_loop
import scout
import treasurer
import wallet
import yield_book
from api.common import yield_status

router = APIRouter()


@router.get("/yield/status")
def get_status() -> dict:
    return yield_status()


@router.get("/yield/stands")
def get_stands() -> dict:
    from api.common import yield_stands

    return yield_stands()


@router.get("/yield/plan")
def get_plan() -> dict:
    frozen = killswitch.frozen("yield")
    pools, source = scout.read_pools()
    yield_book.accrue()
    position = yield_book.load().get("position")
    position_value = yield_book.position_deployed_usd()
    state = wallet.load()
    free_cash = float(state.get("yield_cash_usd") or 0.0) + float(state.get("cash_usd") or 0.0)

    decision = treasurer.decide(pools, position, position_value, free_cash, source, frozen)
    dest = decision.get("dest")
    chain = wallet.chain_balances()
    sol = chain.get("devnet_sol")
    if sol is None:
        sol = chain.get("mainnet_sol")
    usdc = chain.get("devnet_usdc")
    if usdc is None:
        usdc = chain.get("mainnet_usdc")

    return {
        "wallet": config.WALLET_PUBKEY,
        "sol": sol,
        "usdc": usdc,
        "amount_usd": decision.get("amount_usd"),
        "dest": None
        if not dest
        else {
            "project": dest.get("project"),
            "apy": dest.get("apy"),
            "tvl_usd": dest.get("tvl_usd"),
            "pool_id": dest.get("pool_id"),
        },
        "would_send": bool(decision.get("would_send")),
        "blockers": decision.get("blockers") or [],
    }


@router.post("/yield/tick")
def run_tick() -> dict:
    try:
        yield_loop.tick()
    except Exception as exc:  # surfaced to the UI as a 500 with the reason
        raise HTTPException(status_code=500, detail=f"yield tick failed: {exc}") from exc
    return yield_status()
