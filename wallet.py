"""Hub wallet: paper cash, desk allocations, ledger, and real chain reads.

Paper mode only: `cash_usd` is simulated USD. SOL/USDC balances under `chain`
are real RPC reads (or null when the RPC call fails — never fabricated).
"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import requests

import config
from paths import STATE_DIR, state_lock
from trader import book as trade_book
from copytrader import book as copy_book
from yield_book import (
    capacity_usd as yield_capacity_usd,
    position_deployed_usd,
    unwind as yield_unwind,
)

WALLET_FILE = STATE_DIR / "wallet.json"
STARTING_CASH_USD = 1000.0
DESKS = ("yield", "trade", "copy")
MAINNET_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
DEVNET_USDC_MINT = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
RPC_TIMEOUT = 4.0
CHAIN_CACHE_SECONDS = 30.0

_chain_cache: dict[str, Any] = {"at": 0.0, "value": None}
_chain_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default() -> dict[str, Any]:
    return {
        "cash_usd": STARTING_CASH_USD,
        "starting_cash_usd": STARTING_CASH_USD,
        "yield_cash_usd": 0.0,
        "ledger": [],
    }


def load() -> dict[str, Any]:
    with state_lock:
        if WALLET_FILE.is_file():
            try:
                state = _default()
                state.update(json.loads(WALLET_FILE.read_text(encoding="utf-8")))
                return state
            except (OSError, ValueError):
                pass
    return _default()


def save(state: dict[str, Any]) -> None:
    with state_lock:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        WALLET_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _ledger_entry(kind: str, amount_usd: float, from_: str, to: str, note: str = "") -> dict[str, Any]:
    return {
        "ts": _now(),
        "kind": kind,
        "amount_usd": round(float(amount_usd), 6),
        "from": from_,
        "to": to,
        "note": note,
    }


def _add_ledger(state: dict[str, Any], entry: dict[str, Any]) -> None:
    # Newest first; the UI renders ledger.prefix(12).
    state.setdefault("ledger", []).insert(0, entry)
    del state["ledger"][500:]


def receive(amount_usd: float, note: str = "") -> dict[str, Any]:
    if amount_usd <= 0:
        raise ValueError("amount_usd must be positive")
    with state_lock:
        state = load()
        state["cash_usd"] = float(state.get("cash_usd") or 0.0) + amount_usd
        _add_ledger(state, _ledger_entry("receive", amount_usd, "external", "hub", note))
        save(state)
    return state


def send(amount_usd: float, dest: str, note: str = "") -> dict[str, Any]:
    dest = (dest or "").strip()
    if amount_usd <= 0:
        raise ValueError("amount_usd must be positive")
    if not dest:
        raise ValueError("dest is required")
    with state_lock:
        state = load()
        cash = float(state.get("cash_usd") or 0.0)
        if amount_usd > cash + 1e-9:
            raise ValueError(f"insufficient hub cash (${cash:,.2f} available)")
        state["cash_usd"] = cash - amount_usd
        if dest == "yield":
            state["yield_cash_usd"] = float(state.get("yield_cash_usd") or 0.0) + amount_usd
        elif dest == "trade":
            tstate = trade_book.load()
            tstate["cash_usd"] = float(tstate.get("cash_usd") or 0.0) + amount_usd
            trade_book.save(tstate)
        elif dest == "copy":
            cstate = copy_book.load()
            cstate["cash_usd"] = float(cstate.get("cash_usd") or 0.0) + amount_usd
            copy_book.save(cstate)
        # else: paper send to an external wallet address (funds leave the desk system)
        _add_ledger(state, _ledger_entry("send", amount_usd, "hub", dest, note))
        save(state)
    return state


def withdraw(amount_usd: float, source: str) -> dict[str, Any]:
    source = (source or "").strip()
    if amount_usd <= 0:
        raise ValueError("amount_usd must be positive")
    if source not in DESKS:
        raise ValueError(f"unknown desk {source!r}; expected one of {DESKS}")
    with state_lock:
        state = load()
        remaining = float(amount_usd)

        if source == "yield":
            # Check capacity up front so a failed withdraw never mutates any book.
            bucket = float(state.get("yield_cash_usd") or 0.0)
            capacity = bucket + yield_capacity_usd()
            if capacity + 1e-9 < amount_usd:
                raise ValueError(
                    f"yield desk holds ${capacity:,.2f} "
                    f"(${bucket:,.2f} cash + pool position); cannot withdraw ${amount_usd:,.2f}"
                )
            take = min(bucket, remaining)
            state["yield_cash_usd"] = bucket - take
            remaining -= take
            if remaining > 1e-9:
                # Pull the rest out of the paper pool (partial unwind, principal + interest).
                unwound = yield_unwind(remaining)
                state["yield_cash_usd"] = float(state.get("yield_cash_usd") or 0.0) + unwound
                remaining -= unwound
        elif source == "trade":
            tstate = trade_book.load()
            bucket = float(tstate.get("cash_usd") or 0.0)
            if bucket + 1e-9 < remaining:
                raise ValueError(
                    f"trade desk has only ${bucket:,.2f} idle; sell open positions first"
                )
            tstate["cash_usd"] = bucket - remaining
            trade_book.save(tstate)
            remaining = 0.0
        elif source == "copy":
            cstate = copy_book.load()
            bucket = float(cstate.get("cash_usd") or 0.0)
            if bucket + 1e-9 < remaining:
                raise ValueError(
                    f"copy desk has only ${bucket:,.2f} idle; close copied positions first"
                )
            cstate["cash_usd"] = bucket - remaining
            copy_book.save(cstate)
            remaining = 0.0

        if remaining > 1e-6:
            raise ValueError(f"could not withdraw ${amount_usd:,.2f} from desk {source!r}")

        state["cash_usd"] = float(state.get("cash_usd") or 0.0) + amount_usd
        _add_ledger(state, _ledger_entry("withdraw", amount_usd, source, "hub", ""))
        save(state)
    return state


# --- yield desk cash plumbing (used by loop.tick) -----------------------------

def yield_cash() -> float:
    return float(load().get("yield_cash_usd") or 0.0)


def pull_for_yield(amount_usd: float) -> dict[str, float]:
    """Move `amount_usd` out of cash (yield bucket first, then hub) for pool deployment."""
    with state_lock:
        state = load()
        bucket = float(state.get("yield_cash_usd") or 0.0)
        hub = float(state.get("cash_usd") or 0.0)
        if bucket + hub + 1e-9 < amount_usd:
            raise ValueError(
                f"insufficient cash to deploy ${amount_usd:,.2f} "
                f"(yield bucket ${bucket:,.2f} + hub ${hub:,.2f})"
            )
        from_bucket = min(bucket, amount_usd)
        from_hub = amount_usd - from_bucket
        state["yield_cash_usd"] = bucket - from_bucket
        state["cash_usd"] = hub - from_hub
        save(state)
    return {"from_yield_cash": from_bucket, "from_hub": from_hub}


def return_to_yield(amount_usd: float, note: str = "") -> None:
    """Unwound pool principal + accrued paper interest lands back in the yield bucket."""
    if amount_usd <= 0:
        return
    with state_lock:
        state = load()
        state["yield_cash_usd"] = float(state.get("yield_cash_usd") or 0.0) + amount_usd
        _add_ledger(state, _ledger_entry("unwind", amount_usd, "pool", "yield", note))
        save(state)


def add_ledger(kind: str, amount_usd: float, from_: str, to: str, note: str = "") -> None:
    with state_lock:
        state = load()
        _add_ledger(state, _ledger_entry(kind, amount_usd, from_, to, note))
        save(state)


# --- chain reads (real RPC, null on failure) -----------------------------------

def _rpc(url: str, method: str, params: list[Any], timeout: float = RPC_TIMEOUT) -> Any:
    resp = requests.post(
        url,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=timeout,
        headers={"Accept": "application/json"},
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("error"):
        raise RuntimeError(f"rpc {method}: {payload['error'].get('code')}")
    return payload.get("result")


def _sol_balance(url: str, pubkey: str) -> float | None:
    try:
        result = _rpc(url, "getBalance", [pubkey, {"commitment": "confirmed"}])
        return float(result["value"]) / 1_000_000_000.0
    except Exception as exc:
        print(f"rpc fail getBalance: {type(exc).__name__}")
        return None


def _usdc_balance(url: str, pubkey: str, mint: str) -> float | None:
    try:
        result = _rpc(
            url,
            "getTokenAccountsByOwner",
            [pubkey, {"mint": mint}, {"encoding": "jsonParsed", "commitment": "confirmed"}],
        )
        accounts = ((result or {}).get("value")) or []
        if not accounts:
            return 0.0  # real read: the owner holds no account for this mint
        total = 0.0
        for acct in accounts:
            try:
                info = acct["account"]["data"]["parsed"]["info"]["tokenAmount"]
                total += float(info.get("uiAmount") or 0.0)
            except (KeyError, TypeError, ValueError):
                continue
        return total
    except Exception as exc:
        print(f"rpc fail getTokenAccountsByOwner: {type(exc).__name__}")
        return None


def chain_balances(force: bool = False) -> dict[str, Any]:
    """Devnet/mainnet SOL + USDC via RPC. Fields are null when a call fails."""
    pubkey = config.WALLET_PUBKEY
    info: dict[str, Any] = {
        "pubkey": pubkey,
        "devnet_sol": None,
        "devnet_usdc": None,
        "mainnet_sol": None,
        "mainnet_usdc": None,
    }
    if not pubkey:
        return info

    with _chain_lock:
        now = time.time()
        if not force and _chain_cache["value"] and now - _chain_cache["at"] < CHAIN_CACHE_SECONDS:
            cached = dict(_chain_cache["value"])
            cached["pubkey"] = pubkey
            return cached

    devnet_url = "https://api.devnet.solana.com"
    mainnet_url = config.RPC_URL
    with ThreadPoolExecutor(max_workers=4) as pool:
        devnet_sol = pool.submit(_sol_balance, devnet_url, pubkey)
        devnet_usdc = pool.submit(_usdc_balance, devnet_url, pubkey, DEVNET_USDC_MINT)
        mainnet_sol = pool.submit(_sol_balance, mainnet_url, pubkey)
        mainnet_usdc = pool.submit(_usdc_balance, mainnet_url, pubkey, MAINNET_USDC_MINT)
        info["devnet_sol"] = devnet_sol.result()
        info["devnet_usdc"] = devnet_usdc.result()
        info["mainnet_sol"] = mainnet_sol.result()
        info["mainnet_usdc"] = mainnet_usdc.result()

    with _chain_lock:
        _chain_cache["at"] = time.time()
        _chain_cache["value"] = dict(info)
    return info


# --- status --------------------------------------------------------------------

def allocations() -> dict[str, dict[str, float]]:
    state = load()
    tstate = trade_book.load()
    cstate = copy_book.load()

    yield_idle = float(state.get("yield_cash_usd") or 0.0)
    yield_deployed = position_deployed_usd()
    trade_idle = float(tstate.get("cash_usd") or 0.0)
    trade_deployed = trade_book.open_mark_usd(tstate)
    copy_idle = float(cstate.get("cash_usd") or 0.0)
    copy_deployed = copy_book.open_mark_usd(cstate)

    return {
        "yield": {
            "idle_usd": round(yield_idle, 2),
            "deployed_usd": round(yield_deployed, 2),
            "total_usd": round(yield_idle + yield_deployed, 2),
        },
        "trade": {
            "idle_usd": round(trade_idle, 2),
            "deployed_usd": round(trade_deployed, 2),
            "total_usd": round(trade_idle + trade_deployed, 2),
        },
        "copy": {
            "idle_usd": round(copy_idle, 2),
            "deployed_usd": round(copy_deployed, 2),
            "total_usd": round(copy_idle + copy_deployed, 2),
        },
    }


def status() -> dict[str, Any]:
    state = load()
    desks = allocations()
    hub_cash = float(state.get("cash_usd") or 0.0)
    idle = hub_cash + sum(d["idle_usd"] for d in desks.values())
    deployed = sum(d["deployed_usd"] for d in desks.values())
    return {
        "desk": "wallet",
        "mode": config.MODE,
        "live_enabled": bool(config.LIVE_ENABLED),
        "receive_address": config.WALLET_PUBKEY,
        "cash_usd": round(hub_cash, 2),
        "nav_usd": round(idle + deployed, 2),
        "idle_usd": round(idle, 2),
        "deployed_usd": round(deployed, 2),
        "desks": desks,
        "chain": chain_balances(),
        "ledger": state.get("ledger") or [],
    }
