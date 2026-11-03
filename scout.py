"""Scout: read Solana USDC lending pools from DefiLlama's free yields API.

No API key required. Results are cached in-process (TTL) because several
endpoints surface the same pool list. On network failure we fall back to a
small static allowlist whose values are clearly marked `source=fallback-static`
— never presented as live data.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import requests

import config

POOLS_URL = "https://yields.llama.fi/pools"
CACHE_SECONDS = 600.0
FAILURE_COOLDOWN_SECONDS = 60.0
REQUEST_TIMEOUT = 10.0

# Deterministic fallback used ONLY when DefiLlama is unreachable. Values are
# conservative approximations and every pool returned carries
# source="fallback-static" so the UI can tell them apart from live reads.
FALLBACK_POOLS: list[dict[str, Any]] = [
    {
        "project": "kamino-lend",
        "symbol": "USDC",
        "apy": 4.50,
        "tvl_usd": 10_000_000.0,
        "pool_id": "fallback:kamino-lend:usdc",
        "source": "fallback-static",
    },
    {
        "project": "jupiter-lend",
        "symbol": "USDC",
        "apy": 4.20,
        "tvl_usd": 10_000_000.0,
        "pool_id": "fallback:jupiter-lend:usdc",
        "source": "fallback-static",
    },
    {
        "project": "save",
        "symbol": "USDC",
        "apy": 3.60,
        "tvl_usd": 10_000_000.0,
        "pool_id": "fallback:save:usdc",
        "source": "fallback-static",
    },
]

_cache: dict[str, Any] = {"at": 0.0, "pools": None, "source": None}
_lock = threading.Lock()


def _matches_symbol(symbol: str) -> bool:
    normalized = (symbol or "").upper()
    for allowed in config.ALLOWLIST_SYMBOLS:
        allowed = allowed.upper()
        if allowed in normalized.split("-") or normalized == allowed:
            return True
    return False


def _fetch_defillama() -> list[dict[str, Any]]:
    resp = requests.get(POOLS_URL, timeout=REQUEST_TIMEOUT, headers={"Accept": "application/json"})
    resp.raise_for_status()
    payload = resp.json()
    rows = payload.get("data") or []
    allow_projects = set(config.ALLOWLIST_PROJECTS)
    pools: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if (row.get("chain") or "").lower() != "solana":
            continue
        project = row.get("project") or ""
        if project not in allow_projects:
            continue
        if not _matches_symbol(row.get("symbol") or ""):
            continue
        tvl = row.get("tvlUsd")
        apy = row.get("apy")
        if tvl is None or apy is None:
            continue
        try:
            tvl_f = float(tvl)
            apy_f = float(apy)
        except (TypeError, ValueError):
            continue
        if tvl_f < config.MIN_TVL_USD:
            continue
        pools.append(
            {
                "project": project,
                "symbol": (row.get("symbol") or "USDC").upper(),
                "apy": round(apy_f, 2),
                "tvl_usd": round(tvl_f, 2),
                "pool_id": row.get("pool") or f"{project}:{row.get('symbol')}",
                "source": "defillama",
            }
        )
    pools.sort(key=lambda p: p["apy"], reverse=True)
    return pools


def read_pools(force: bool = False) -> tuple[list[dict[str, Any]], str]:
    """Returns (allowlisted pools sorted by APY desc, source label)."""
    now = time.time()
    with _lock:
        if not force and _cache["pools"] is not None:
            age = now - float(_cache["at"])
            if age < CACHE_SECONDS:
                return list(_cache["pools"]), str(_cache["source"])
            # After a failure, cool down before re-hitting the upstream API.
            if _cache["source"] == "fallback-static" and age < FAILURE_COOLDOWN_SECONDS:
                return list(_cache["pools"]), str(_cache["source"])

    source = "defillama"
    try:
        pools = _fetch_defillama()
        if not pools:
            # Reachable but no allowlisted pool passed the filters: still a real read.
            source = "defillama (no allowlisted pool met the filters)"
    except Exception as exc:
        print(f"scout: defillama unreachable ({type(exc).__name__}); using fallback-static pools")
        pools = [dict(p) for p in FALLBACK_POOLS if p["tvl_usd"] >= config.MIN_TVL_USD]
        source = "fallback-static (defillama unreachable)"

    with _lock:
        _cache["at"] = time.time()
        _cache["pools"] = pools
        _cache["source"] = source
    return list(pools), source


def allowed_pools(pools: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if pools is None:
        pools, _ = read_pools()
    return [p for p in pools if float(p.get("tvl_usd") or 0.0) >= config.MIN_TVL_USD]


def best(pools: list[dict[str, Any]]) -> dict[str, Any] | None:
    return pools[0] if pools else None
