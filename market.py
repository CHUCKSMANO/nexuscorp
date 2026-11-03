"""Market data: DexScreener's free public API (no key required).

Endpoints used:
  GET https://api.dexscreener.com/latest/dex/search?q=<query>
  GET https://api.dexscreener.com/latest/dex/tokens/<mint[,mint...]>
  GET https://api.dexscreener.com/token-boosts/latest/v1
  GET https://api.dexscreener.com/token-profiles/latest/v1

Everything returned is computed from those live responses; nothing is mocked.
Responses are cached in-process for a few seconds so the 30s mark scheduler and
the UI polling do not hammer the upstream API.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any

import requests

SEARCH_URL = "https://api.dexscreener.com/latest/dex/search"
TOKENS_URL = "https://api.dexscreener.com/latest/dex/tokens"
BOOSTS_URL = "https://api.dexscreener.com/token-boosts/latest/v1"
PROFILES_URL = "https://api.dexscreener.com/token-profiles/latest/v1"

REQUEST_TIMEOUT = 10.0
_MINT_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")

_cache: dict[str, tuple[float, Any]] = {}
_lock = threading.Lock()


class MarketUnavailable(RuntimeError):
    """Raised when DexScreener cannot be reached and no cached data exists."""


def _cached(key: str, ttl: float, fetch):
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    value = fetch()
    with _lock:
        _cache[key] = (time.time(), value)
        return value


def _get_json(url: str, params: dict[str, str] | None = None) -> Any:
    try:
        resp = requests.get(
            url,
            params=params,
            timeout=REQUEST_TIMEOUT,
            headers={"Accept": "application/json", "User-Agent": "nexuscorp-paper/1.0"},
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        raise MarketUnavailable(f"{type(exc).__name__} fetching {url}") from exc


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _solana_pairs(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [p for p in pairs if (p.get("chainId") or "solana") == "solana"]


def _best_pair(pairs: list[dict[str, Any]]) -> dict[str, Any] | None:
    sol = _solana_pairs(pairs)
    if not sol:
        return None
    return max(sol, key=lambda p: float(((p.get("liquidity") or {}).get("usd")) or 0.0))


def item_from_pair(pair: dict[str, Any]) -> dict[str, Any]:
    base = pair.get("baseToken") or {}
    liquidity = pair.get("liquidity") or {}
    volume = pair.get("volume") or {}
    change = pair.get("priceChange") or {}
    pair_address = pair.get("pairAddress") or ""
    chain = pair.get("chainId") or "solana"
    fdv = _f(pair.get("fdv"))
    market_cap = _f(pair.get("marketCap")) or fdv
    return {
        "mint": base.get("address") or "",
        "symbol": base.get("symbol"),
        "name": base.get("name"),
        "price_usd": _f(pair.get("priceUsd")),
        "price_change_5m": _f(change.get("m5")),
        "price_change_1h": _f(change.get("h1")),
        "price_change_6h": _f(change.get("h6")),
        "price_change_24h": _f(change.get("h24")),
        "liquidity_usd": _f(liquidity.get("usd")),
        "volume_24h": _f(volume.get("h24")),
        "fdv": fdv,
        "market_cap": market_cap,
        "dex": pair.get("dexId"),
        "pair_address": pair_address,
        "pair_url": pair.get("url") or (f"https://dexscreener.com/{chain}/{pair_address}" if pair_address else None),
        "chart_url": f"https://dexscreener.com/{chain}/{pair_address}" if pair_address else None,
    }


def search_pairs(query: str) -> list[dict[str, Any]]:
    payload = _cached(
        f"search:{query}",
        30.0,
        lambda: _get_json(SEARCH_URL, {"q": query}),
    )
    return list((payload or {}).get("pairs") or [])


def token_pairs(mint: str) -> list[dict[str, Any]]:
    payload = _cached(f"tokens:{mint}", 20.0, lambda: _get_json(f"{TOKENS_URL}/{mint}"))
    return list((payload or {}).get("pairs") or [])


def _latest_solana_addresses(limit: int) -> list[str]:
    addresses: list[str] = []
    seen: set[str] = set()

    def add_from(payload: Any) -> None:
        rows = payload if isinstance(payload, list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if (row.get("chainId") or "") != "solana":
                continue
            addr = row.get("tokenAddress")
            if addr and addr not in seen:
                seen.add(addr)
                addresses.append(addr)

    for url in (BOOSTS_URL, PROFILES_URL):
        try:
            add_from(_cached(f"feed:{url}", 60.0, lambda u=url: _get_json(u)))
        except MarketUnavailable:
            continue
    return addresses[:limit]


def markets(limit: int = 30) -> list[dict[str, Any]]:
    """Live Solana market list: boosted/profiled tokens priced via DexScreener."""
    limit = max(1, min(int(limit), 60))
    try:
        addrs = _latest_solana_addresses(limit)
        if addrs:
            pairs = _cached(
                f"batch:{','.join(addrs[:30])}",
                45.0,
                lambda: _get_json(f"{TOKENS_URL}/{','.join(addrs[:30])}"),
            ).get("pairs") or []
        else:
            pairs = search_pairs("SOL")
    except MarketUnavailable as exc:
        # Last resort: a plain search still yields real pairs.
        try:
            pairs = search_pairs("SOL")
        except MarketUnavailable:
            raise MarketUnavailable(f"dexscreener unavailable ({exc})") from exc

    best_by_mint: dict[str, dict[str, Any]] = {}
    for pair in _solana_pairs(list(pairs)):
        if not isinstance(pair, dict):
            continue
        mint = ((pair.get("baseToken") or {}).get("address")) or ""
        if not mint:
            continue
        current = best_by_mint.get(mint)
        if current is None or (
            float(((pair.get("liquidity") or {}).get("usd")) or 0.0)
            > float(((current.get("liquidity") or {}).get("usd")) or 0.0)
        ):
            best_by_mint[mint] = pair

    items = [item_from_pair(p) for p in best_by_mint.values()]
    items.sort(key=lambda i: i.get("liquidity_usd") or 0.0, reverse=True)
    return items[:limit]


def quote(query: str) -> dict[str, Any]:
    """Resolve a symbol or mint to one MarketItem. Raises KeyError when unknown."""
    q = (query or "").strip()
    if not q:
        raise KeyError("empty query")

    pairs: list[dict[str, Any]] = []
    if _MINT_RE.match(q):
        pairs = token_pairs(q)
        pair = _best_pair(pairs)
        if pair:
            return item_from_pair(pair)
        raise KeyError(f"no market data for mint {q}")

    pairs = search_pairs(q)
    sol = _solana_pairs(pairs)
    if not sol:
        raise KeyError(f"no market found for {q!r}")
    exact = [p for p in sol if ((p.get("baseToken") or {}).get("symbol") or "").lower() == q.lower()]
    pair = _best_pair(exact) or _best_pair(sol)
    if not pair:
        raise KeyError(f"no market found for {q!r}")
    return item_from_pair(pair)


def price_for(mint: str) -> tuple[float | None, dict[str, Any] | None]:
    """Best-pair price + item for a mint; (None, None) when DexScreener has nothing."""
    try:
        pairs = token_pairs(mint)
    except MarketUnavailable:
        return None, None
    pair = _best_pair(pairs)
    if not pair:
        return None, None
    item = item_from_pair(pair)
    return item.get("price_usd"), item


def prices_for(mints: list[str]) -> dict[str, dict[str, Any]]:
    """Batch mark prices for open positions: one upstream call for <=30 mints."""
    unique = [m for m in dict.fromkeys(mints) if m]
    out: dict[str, dict[str, Any]] = {}
    if not unique:
        return out
    for start in range(0, len(unique), 30):
        chunk = unique[start:start + 30]
        try:
            payload = _cached(
                f"batch:{','.join(chunk)}",
                20.0,
                lambda c=chunk: _get_json(f"{TOKENS_URL}/{','.join(c)}"),
            )
        except MarketUnavailable:
            continue
        pairs = list((payload or {}).get("pairs") or [])
        by_mint: dict[str, dict[str, Any]] = {}
        for pair in _solana_pairs(pairs):
            if not isinstance(pair, dict):
                continue
            mint = ((pair.get("baseToken") or {}).get("address")) or ""
            if not mint:
                continue
            current = by_mint.get(mint)
            if current is None or (
                float(((pair.get("liquidity") or {}).get("usd")) or 0.0)
                > float(((current.get("liquidity") or {}).get("usd")) or 0.0)
            ):
                by_mint[mint] = pair
        for mint, pair in by_mint.items():
            out[mint] = item_from_pair(pair)
    return out
