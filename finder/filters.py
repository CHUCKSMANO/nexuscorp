"""Finder filters: thresholds for accepting a new mint, persisted + presets.

Defaults match the recovered state/finder_filters.json exactly.
"""

from __future__ import annotations

import json
from typing import Any

from paths import STATE_DIR, state_lock

FILTERS_FILE = STATE_DIR / "finder_filters.json"

DEFAULT_FILTERS: dict[str, float] = {
    "min_market_cap": 100000.0,
    "min_volume_24h": 25000.0,
    "min_txns_24h": 200.0,
    "min_liquidity": 25000.0,
    "max_age_hours": 144.0,
    "max_risk_score": 30.0,
    "min_buy_pressure": 0.35,
    "min_vol_liq_ratio": 0.2,
    "max_top10_holder_pct": 60.0,
}

PRESETS: dict[str, dict[str, float]] = {
    "default": dict(DEFAULT_FILTERS),
    "strict": {
        "min_market_cap": 500000.0,
        "min_volume_24h": 100000.0,
        "min_txns_24h": 500.0,
        "min_liquidity": 100000.0,
        "max_age_hours": 48.0,
        "max_risk_score": 15.0,
        "min_buy_pressure": 0.50,
        "min_vol_liq_ratio": 0.30,
        "max_top10_holder_pct": 40.0,
    },
    "loose": {
        "min_market_cap": 50000.0,
        "min_volume_24h": 10000.0,
        "min_txns_24h": 100.0,
        "min_liquidity": 10000.0,
        "max_age_hours": 168.0,
        "max_risk_score": 45.0,
        "min_buy_pressure": 0.30,
        "min_vol_liq_ratio": 0.10,
        "max_top10_holder_pct": 75.0,
    },
}


def load() -> dict[str, float]:
    with state_lock:
        if FILTERS_FILE.is_file():
            try:
                data = json.loads(FILTERS_FILE.read_text(encoding="utf-8"))
                merged = dict(DEFAULT_FILTERS)
                for key, value in data.items():
                    if key in merged:
                        merged[key] = float(value)
                return merged
            except (OSError, ValueError, TypeError):
                pass
    save(dict(DEFAULT_FILTERS))
    return dict(DEFAULT_FILTERS)


def save(filters: dict[str, float]) -> dict[str, float]:
    with state_lock:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        FILTERS_FILE.write_text(json.dumps(filters, indent=2) + "\n", encoding="utf-8")
    return filters


def set_filter(key: str, value: float) -> dict[str, float]:
    if key not in DEFAULT_FILTERS:
        raise KeyError(f"unknown filter {key!r}; valid keys: {sorted(DEFAULT_FILTERS)}")
    filters = load()
    filters[key] = float(value)
    return save(filters)


def apply_preset(name: str) -> dict[str, float]:
    preset = PRESETS.get((name or "").strip().lower())
    if preset is None:
        raise KeyError(f"unknown preset {name!r}; valid presets: {sorted(PRESETS)}")
    return save(dict(preset))
