"""Configuration: loads .env (python-dotenv when available, tiny parser otherwise).

Secrets are never printed anywhere in this codebase. os.environ wins over .env.
"""

from __future__ import annotations

import os

from paths import LOG_FILE, ROOT, STATE_DIR  # re-exported for callers

__all__ = [
    "ROOT", "STATE_DIR", "LOG_FILE",
    "MODE", "LIVE_ENABLED", "WALLET_PUBKEY", "RPC_URL",
    "API_HOST", "API_PORT",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
    "DISCORD_BOT_TOKEN", "DISCORD_CHANNEL_ID",
    "DISCORD_FINDER_CHANNEL_ID", "DISCORD_YIELD_CHANNEL_ID", "DISCORD_COPY_CHANNEL_ID",
    "MIN_EDGE_APY", "MIN_MOVE_USD", "MIN_TVL_USD", "GAS_BUFFER_USD",
    "LOOP_SECONDS", "FINDER_SCAN_SECONDS", "COPY_POLL_SECONDS", "TRADE_MARK_SECONDS",
    "FINDER_MAX_TRACKED", "FINDER_EXECUTION", "COPY_EXECUTION",
    "MAX_LIVE_USD", "KEYFILE", "ALLOWED_DISCORD_USER_ID",
    "ALLOWLIST_PROJECTS", "ALLOWLIST_SYMBOLS", "BIRDEYE_API_KEY", "COPY_TRADE_USD",
]


def _load_env_file() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(env_path)  # does not override existing os.environ entries
        return
    except ImportError:
        pass
    # Tiny fallback parser: KEY=VALUE lines, comments skipped, env wins.
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()


def _get(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


def _float(name: str, default: float) -> float:
    try:
        return float(_get(name, str(default)))
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(float(_get(name, str(default))))
    except ValueError:
        return default


def _bool(name: str, default: bool = False) -> bool:
    raw = _get(name, "true" if default else "false").lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off", ""):
        return False
    return default


def _list(name: str, default: list[str]) -> list[str]:
    raw = _get(name, "")
    if not raw:
        return list(default)
    return [part.strip() for part in raw.split(",") if part.strip()]


# Mode / identity -------------------------------------------------------------
MODE = _get("MODE", "paper") or "paper"
LIVE_ENABLED = _bool("LIVE_ENABLED", False) and MODE == "live"
WALLET_PUBKEY = _get("WALLET_PUBKEY") or None
RPC_URL = _get("RPC_URL", "https://api.mainnet-beta.solana.com") or "https://api.mainnet-beta.solana.com"

# HTTP server -----------------------------------------------------------------
# Local default stays loopback; hosts that inject PORT (Render/Railway/Fly)
# and containers that need 0.0.0.0 can override without editing code.
API_HOST = _get("API_HOST", "127.0.0.1") or "127.0.0.1"
API_PORT = _int("PORT", _int("API_PORT", 8000))

# Alert channels (blank tokens make agents/scribe.py a no-op) -----------------
TELEGRAM_BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _get("TELEGRAM_CHAT_ID")
DISCORD_BOT_TOKEN = _get("DISCORD_BOT_TOKEN") or _get("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = _get("DISCORD_CHANNEL_ID")
DISCORD_YIELD_CHANNEL_ID = _get("DISCORD_YIELD_CHANNEL_ID") or DISCORD_CHANNEL_ID
DISCORD_FINDER_CHANNEL_ID = (
    _get("DISCORD_FINDER_CHANNEL_ID") or _get("ALERT_CHANNEL_ID") or DISCORD_CHANNEL_ID
)
DISCORD_COPY_CHANNEL_ID = _get("DISCORD_COPY_CHANNEL_ID") or DISCORD_CHANNEL_ID
ALLOWED_DISCORD_USER_ID = _int("ALLOWED_DISCORD_USER_ID", 0)

# Decision rules ---------------------------------------------------------------
MIN_EDGE_APY = _float("MIN_EDGE_APY", 0.40)
MIN_MOVE_USD = _float("MIN_MOVE_USD", 200.0)
MIN_TVL_USD = _float("MIN_TVL_USD", 250000.0)
GAS_BUFFER_USD = _float("GAS_BUFFER_USD", 200.0)

# Schedulers -------------------------------------------------------------------
LOOP_SECONDS = _float("LOOP_SECONDS", 3600.0)
FINDER_SCAN_SECONDS = _float("FINDER_SCAN_SECONDS", 90.0)
COPY_POLL_SECONDS = _float("COPY_POLL_SECONDS", 45.0)
TRADE_MARK_SECONDS = _float("TRADE_MARK_SECONDS", 30.0)

# Desks ------------------------------------------------------------------------
FINDER_MAX_TRACKED = _int("FINDER_MAX_TRACKED", 40)
FINDER_EXECUTION = _get("FINDER_EXECUTION", "alerts") or "alerts"
COPY_EXECUTION = _get("COPY_EXECUTION", "paper") or "paper"
MAX_LIVE_USD = _float("MAX_LIVE_USD", 100.0)
COPY_TRADE_USD = _float("COPY_TRADE_USD", 25.0)
KEYFILE = _get("KEYFILE")

# Yield allowlist ---------------------------------------------------------------
ALLOWLIST_PROJECTS = _list("ALLOWLIST_PROJECTS", ["kamino-lend", "jupiter-lend", "save"])
ALLOWLIST_SYMBOLS = _list("ALLOWLIST_SYMBOLS", ["USDC"])

# Optional market-data key (DexScreener is the keyless primary source) ----------
BIRDEYE_API_KEY = _get("BIRDEYE_API_KEY")
