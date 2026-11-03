"""Paper yield position persistence + tick math.

Interest is plain paper math: paper_per_day = amount_usd * apy / 100 / 365,
accrued pro-rata by elapsed wall-clock time. No real money moves.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from paths import STATE_DIR, state_lock

POSITION_FILE = STATE_DIR / "yield_position.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _now_epoch() -> float:
    return datetime.now(timezone.utc).timestamp()


def _parse_ts(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


def _default() -> dict[str, Any]:
    return {
        "position": None,
        "accrued_usd": 0.0,
        "lifetime_earned_usd": 0.0,
        "last_accrue_at": _now(),
        "last_action": "idle",
        "last_reason": "no tick run yet",
        "updated_at": _now(),
    }


def load() -> dict[str, Any]:
    with state_lock:
        if POSITION_FILE.is_file():
            try:
                state = _default()
                state.update(json.loads(POSITION_FILE.read_text(encoding="utf-8")))
                return state
            except (OSError, ValueError):
                pass
    return _default()


def save(state: dict[str, Any]) -> None:
    with state_lock:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        POSITION_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def paper_per_day(amount_usd: float, apy: float) -> float:
    return float(amount_usd) * (float(apy) / 100.0) / 365.0


def accrue(state: dict[str, Any] | None = None) -> float:
    """Fold elapsed paper interest into accrued_usd. Returns interest accrued now."""
    own = state is None
    state = state if state is not None else load()
    position = state.get("position")
    if not position:
        state["last_accrue_at"] = _now()
        if own:
            save(state)
        return 0.0
    last = _parse_ts(state.get("last_accrue_at")) or _now_epoch()
    elapsed = max(0.0, _now_epoch() - last)
    daily = paper_per_day(float(position.get("amount_usd") or 0.0), float(position.get("apy") or 0.0))
    interest = daily * (elapsed / 86400.0)
    if interest > 0:
        state["accrued_usd"] = float(state.get("accrued_usd") or 0.0) + interest
        state["lifetime_earned_usd"] = float(state.get("lifetime_earned_usd") or 0.0) + interest
    state["last_accrue_at"] = _now()
    if own:
        save(state)
    return interest


def position_deployed_usd() -> float:
    state = load()
    position = state.get("position")
    if not position:
        return 0.0
    return float(position.get("amount_usd") or 0.0) + float(state.get("accrued_usd") or 0.0)


def capacity_usd() -> float:
    """Total USD the yield desk could pull out of the pool right now."""
    return position_deployed_usd()


def deploy(pool: dict[str, Any], amount_usd: float, reason: str = "") -> dict[str, Any]:
    """Put cash into (or add to) a paper pool position. Caller must have moved the cash."""
    state = load()
    accrue(state)
    position = state.get("position")
    same_pool = position and position.get("pool_id") == pool.get("pool_id")
    if same_pool:
        position["amount_usd"] = float(position.get("amount_usd") or 0.0) + amount_usd
        position["apy"] = float(pool.get("apy") or position.get("apy") or 0.0)
    else:
        # Caller is expected to unwind the old position first (rebalance).
        state["position"] = {
            "project": pool.get("project"),
            "symbol": pool.get("symbol") or "USDC",
            "amount_usd": float(amount_usd),
            "apy": float(pool.get("apy") or 0.0),
            "pool_id": pool.get("pool_id"),
        }
        state["accrued_usd"] = 0.0
    state["last_action"] = "deploy"
    state["last_reason"] = reason or f"deploy ${amount_usd:,.2f} to {pool.get('project')}"
    state["updated_at"] = _now()
    save(state)
    return state


def unwind(target_usd: float) -> float:
    """Take cash out of the paper pool. Returns the USD actually unwound.

    Reduces accrued interest first, then principal. Realizes nothing into
    lifetime_earned (accrual already counted it).
    """
    state = load()
    if not state.get("position"):
        return 0.0
    accrue(state)
    position = state["position"]
    capacity = float(position.get("amount_usd") or 0.0) + float(state.get("accrued_usd") or 0.0)
    take = min(max(0.0, float(target_usd)), capacity)

    from_accrued = min(float(state.get("accrued_usd") or 0.0), take)
    state["accrued_usd"] = float(state.get("accrued_usd") or 0.0) - from_accrued
    take -= from_accrued
    position["amount_usd"] = max(0.0, float(position.get("amount_usd") or 0.0) - take)

    if float(position.get("amount_usd") or 0.0) <= 1e-9 and float(state.get("accrued_usd") or 0.0) <= 1e-9:
        state["position"] = None
        state["accrued_usd"] = 0.0

    pos = state.get("position")
    remaining = 0.0
    if pos:
        remaining = float(pos.get("amount_usd") or 0.0) + float(state.get("accrued_usd") or 0.0)
    state["updated_at"] = _now()
    save(state)
    return capacity - remaining


def unwind_all() -> float:
    return unwind(position_deployed_usd())


def refresh_apy(pool: dict[str, Any]) -> None:
    """Keep the position's APY in step with the live pool it sits in."""
    state = load()
    position = state.get("position")
    if not position:
        return
    if position.get("pool_id") == pool.get("pool_id") or position.get("project") == pool.get("project"):
        position["apy"] = float(pool.get("apy") or position.get("apy") or 0.0)
        state["updated_at"] = _now()
        save(state)


def set_outcome(action: str, reason: str) -> None:
    state = load()
    state["last_action"] = action
    state["last_reason"] = reason
    state["updated_at"] = _now()
    save(state)
