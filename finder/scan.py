"""Finder scan: latest Solana mints (GeckoTerminal new pools) + DexScreener stats.

Sources are real, keyless, public APIs:
  GET https://api.geckoterminal.com/api/v2/networks/solana/new_pools   (newest mints)
  GET https://api.dexscreener.com/latest/dex/tokens/<mint>            (pair stats)

Not everything a filter asks for is measurable from a market feed: top-holder
concentration and mint/freeze authority are not exposed by these APIs, so
`max_top10_holder_pct` is skipped and the security report says so explicitly
(an absent field is never treated as a passing check — it is reported as
unmeasurable).
"""

from __future__ import annotations

from typing import Any

import httpx

NEW_POOLS_URL = "https://api.geckoterminal.com/api/v2/networks/solana/new_pools"
DEXScreener_TOKENS_URL = "https://api.dexscreener.com/latest/dex/tokens"
HEADERS = {"Accept": "application/json", "User-Agent": "nexuscorp-paper/1.0"}
REQUEST_TIMEOUT = 15.0


async def _get_json(client: httpx.AsyncClient, url: str) -> Any:
    resp = await client.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


async def latest_solana_mints(client: httpx.AsyncClient, limit: int = 40) -> list[str]:
    """Newest mint addresses on Solana, in discovery order (deduplicated).

    Primary source: GeckoTerminal new-pool feed. Fallback: DexScreener's
    latest token-profile feed (still real data, slightly older tokens).
    """
    mints: list[str] = []
    seen: set[str] = set()

    def add(mint: str | None) -> None:
        if mint and mint not in seen:
            seen.add(mint)
            mints.append(mint)

    try:
        payload = await _get_json(client, NEW_POOLS_URL)
        for item in payload.get("data") or []:
            rel = ((item.get("relationships") or {}).get("base_token") or {}).get("data") or {}
            node_id = rel.get("id") or ""
            if node_id.startswith("solana_"):
                add(node_id[len("solana_"):])
            if len(mints) >= limit:
                break
    except Exception as exc:
        print(f"finder: geckoterminal new_pools failed ({type(exc).__name__}); trying dexscreener feed")

    if not mints:
        try:
            payload = await _get_json(client, "https://api.dexscreener.com/token-profiles/latest/v1")
            rows = payload if isinstance(payload, list) else []
            for row in rows:
                if isinstance(row, dict) and row.get("chainId") == "solana":
                    add(row.get("tokenAddress"))
                if len(mints) >= limit:
                    break
        except Exception as exc:
            print(f"finder: dexscreener token-profiles failed ({type(exc).__name__})")

    return mints[:limit]


async def best_pair(client: httpx.AsyncClient, mint: str) -> dict[str, Any] | None:
    """Highest-liquidity DexScreener pair for a mint (Solana only)."""
    try:
        payload = await _get_json(client, f"{DEXScreener_TOKENS_URL}/{mint}")
    except Exception:
        return None
    pairs = [
        p
        for p in (payload.get("pairs") or [])
        if isinstance(p, dict) and (p.get("chainId") or "solana") == "solana"
    ]
    if not pairs:
        return None
    return max(pairs, key=lambda p: float(((p.get("liquidity") or {}).get("usd")) or 0.0))


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _age_hours(pair: dict[str, Any]) -> float | None:
    created = pair.get("pairCreatedAt")
    if not created:
        return None
    try:
        import time

        created_s = float(created) / 1000.0
        return max(0.0, (time.time() - created_s) / 3600.0)
    except (TypeError, ValueError):
        return None


def build_stats(pair: dict[str, Any]) -> dict[str, Any]:
    liquidity = pair.get("liquidity") or {}
    volume = pair.get("volume") or {}
    txns = ((pair.get("txns") or {}).get("h24")) or {}
    change = pair.get("priceChange") or {}

    liquidity_usd = _f(liquidity.get("usd")) or 0.0
    volume_24h = _f(volume.get("h24")) or 0.0
    buys = float(txns.get("buys") or 0.0)
    sells = float(txns.get("sells") or 0.0)
    txns_24h = buys + sells
    buy_pressure = (buys / txns_24h) if txns_24h > 0 else 0.0
    vol_liq_ratio = (volume_24h / liquidity_usd) if liquidity_usd > 0 else 0.0
    market_cap = _f(pair.get("marketCap")) or _f(pair.get("fdv"))

    return {
        "price_usd": _f(pair.get("priceUsd")),
        "liquidity_usd": liquidity_usd,
        "volume_24h": volume_24h,
        "buys_24h": buys,
        "sells_24h": sells,
        "txns_24h": txns_24h,
        "buy_pressure": round(buy_pressure, 4),
        "vol_liq_ratio": round(vol_liq_ratio, 4),
        "market_cap": market_cap,
        "fdv": _f(pair.get("fdv")),
        "age_hours": _age_hours(pair),
        "price_change_24h": _f(change.get("h24")),
        "composite_score": 0.0,
    }


def composite_score(stats: dict[str, Any], filters: dict[str, float]) -> float:
    """0-100 blend of measurable strengths (higher = stronger setup)."""
    def frac(value: float, reference: float) -> float:
        if reference <= 0:
            return 0.0
        return max(0.0, min(1.0, value / reference))

    liq = frac(float(stats.get("liquidity_usd") or 0.0), float(filters.get("min_liquidity") or 1) * 4)
    vol = frac(float(stats.get("volume_24h") or 0.0), float(filters.get("min_volume_24h") or 1) * 4)
    txns = frac(float(stats.get("txns_24h") or 0.0), float(filters.get("min_txns_24h") or 1) * 4)
    bp = max(0.0, min(1.0, float(stats.get("buy_pressure") or 0.0)))
    chg = stats.get("price_change_24h")
    chg_component = 0.5
    if chg is not None:
        chg_component = max(0.0, min(1.0, (float(chg) + 50.0) / 100.0))
    score = liq * 25 + vol * 25 + txns * 15 + bp * 20 + chg_component * 15
    return round(score, 1)


async def inspect(
    client: httpx.AsyncClient, mint: str, filters: dict[str, float]
) -> dict[str, Any]:
    """Fetch the best pair for `mint` and evaluate it against the filter set."""
    pair = await best_pair(client, mint)
    if not pair:
        return {
            "mint": mint,
            "pair": None,
            "stats": {},
            "sec_report": _security_report(),
            "risk_flags": ["no_pair"],
            "risk_score": 100.0,
            "ok": False,
            "reason": "no Solana pair found on dexscreener",
        }

    stats = build_stats(pair)
    stats["composite_score"] = composite_score(stats, filters)

    fails: list[str] = []
    flags: list[str] = []
    risk = 0.0

    def check(name: str, passed: bool, detail: str, weight: float) -> None:
        nonlocal risk
        if not passed:
            fails.append(detail)
            flags.append(name)
            risk += weight

    mcap = stats.get("market_cap")
    check(
        "low_market_cap",
        mcap is not None and mcap >= float(filters.get("min_market_cap") or 0),
        f"market cap {mcap if mcap is not None else 'n/a'} < min {filters.get('min_market_cap')}",
        15.0,
    )
    check(
        "low_volume",
        float(stats.get("volume_24h") or 0) >= float(filters.get("min_volume_24h") or 0),
        f"volume24h ${float(stats.get('volume_24h') or 0):,.0f} < min ${float(filters.get('min_volume_24h') or 0):,.0f}",
        20.0,
    )
    check(
        "low_txns",
        float(stats.get("txns_24h") or 0) >= float(filters.get("min_txns_24h") or 0),
        f"txns24h {float(stats.get('txns_24h') or 0):,.0f} < min {float(filters.get('min_txns_24h') or 0):,.0f}",
        15.0,
    )
    check(
        "low_liquidity",
        float(stats.get("liquidity_usd") or 0) >= float(filters.get("min_liquidity") or 0),
        f"liquidity ${float(stats.get('liquidity_usd') or 0):,.0f} < min ${float(filters.get('min_liquidity') or 0):,.0f}",
        25.0,
    )
    age = stats.get("age_hours")
    check(
        "too_old",
        age is not None and age <= float(filters.get("max_age_hours") or 1e9),
        f"age {age if age is not None else 'n/a'}h > max {filters.get('max_age_hours')}h",
        10.0,
    )
    check(
        "low_buy_pressure",
        float(stats.get("buy_pressure") or 0) >= float(filters.get("min_buy_pressure") or 0),
        f"buy pressure {float(stats.get('buy_pressure') or 0):.2f} < min {float(filters.get('min_buy_pressure') or 0):.2f}",
        10.0,
    )
    check(
        "weak_vol_liq",
        float(stats.get("vol_liq_ratio") or 0) >= float(filters.get("min_vol_liq_ratio") or 0),
        f"vol/liq {float(stats.get('vol_liq_ratio') or 0):.2f} < min {float(filters.get('min_vol_liq_ratio') or 0):.2f}",
        5.0,
    )

    risk = min(100.0, risk)
    max_risk = float(filters.get("max_risk_score") or 0)
    ok = not fails and risk <= max_risk
    reason = "passed all filters" if ok else (fails[0] if fails else f"risk {risk} > max {max_risk}")

    return {
        "mint": mint,
        "pair": pair,
        "stats": stats,
        "sec_report": _security_report(),
        "risk_flags": flags,
        "risk_score": round(risk, 1),
        "ok": ok,
        "reason": reason,
    }


def _security_report() -> dict[str, Any]:
    """Honest report: these fields are NOT measurable from the market feeds we use."""
    return {
        "source": "dexscreener market feed",
        "top10_holder_pct": None,
        "mint_authority": None,
        "freeze_authority": None,
        "honeypot": None,
        "unmeasurable": [
            "max_top10_holder_pct (holder list not exposed by this source)",
            "mint/freeze authority (on-chain audit not available without an RPC audit call)",
        ],
        "note": "market-stats only; absence of a security field is never counted as a pass",
    }
