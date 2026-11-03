"""Copy engine: scan followed wallets on Solana and mirror trades in PAPER.

Rebuilt around the recovered fragment: the buy branch still sizes with
min(trade_size_usd, cash), refuses below $5, opens positions through
copy_book.open_or_add_position, and every replication notifies
alerts.send_copy_alert via asyncio.to_thread; the sell branch still closes the
whole paper position through copy_book.reduce_or_close_position and feeds
realized_pnl_usd / pnl_pct back into the fill.

What changed from the original: fills are priced from DexScreener marks instead
of Meteora on-chain execution (this desk is PAPER — no swap ever executes), and
wallet trades are read from the public Solana RPC (getSignaturesForAddress +
getParsedTransaction) instead of a Helius-specific feed. On RPC failure the
scan records the error honestly instead of inventing activity.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx

import config
import killswitch
import market
from agents import scribe
from copytrader import alerts, book as copy_book
from runtime import mark_copy_scan

RPC_URL = config.RPC_URL
RPC_TIMEOUT = 15.0
WSOL_MINT = "So11111111111111111111111111111111111111112"
MAX_SEEN_SIGS = 1000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _rpc(client: httpx.AsyncClient, method: str, params: list[Any]) -> Any:
    resp = await client.post(
        RPC_URL,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        headers={"Accept": "application/json"},
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("error"):
        raise RuntimeError(f"rpc {method}: {payload['error']}")
    return payload.get("result")


async def fetch_wallet_signatures(
    client: httpx.AsyncClient, address: str, limit: int = 10
) -> list[str]:
    result = await _rpc(
        client, "getSignaturesForAddress", [address, {"limit": limit}]
    )
    return [entry.get("signature") for entry in (result or []) if entry.get("signature")]


def _parse_trades(tx: dict[str, Any], owner: str) -> list[dict[str, Any]]:
    """Derive buys/sells from pre/post token balance deltas for `owner`."""
    meta = tx.get("meta") or {}

    def index(rows: list[dict[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
        out: dict[tuple[int, str], dict[str, Any]] = {}
        for row in rows:
            key = (row.get("accountIndex"), row.get("mint") or "")
            amount_info = row.get("uiTokenAmount") or {}
            out[key] = {
                "mint": row.get("mint") or "",
                "amount": float(amount_info.get("amount") or 0.0),
                "decimals": int(amount_info.get("decimals") or 0),
                "owner": row.get("owner"),
            }
        return out

    pre = index(meta.get("preTokenBalances") or [])
    post = index(meta.get("postTokenBalances") or [])
    deltas: dict[str, float] = {}
    for key in set(pre) | set(post):
        before = pre.get(key)
        after = post.get(key)
        if (before and before.get("owner") == owner) or (after and after.get("owner") == owner):
            ref = after or before
            mint = ref.get("mint") or ""
            if not mint or mint == WSOL_MINT:
                continue
            delta = (after["amount"] if after else 0.0) - (before["amount"] if before else 0.0)
            if abs(delta) < 1e-9:
                continue
            scale = 10 ** int(ref.get("decimals") or 0)
            deltas[mint] = deltas.get(mint, 0.0) + delta / scale

    trades = []
    for mint, delta in sorted(deltas.items()):
        trades.append({"side": "buy" if delta > 0 else "sell", "mint": mint, "amount": abs(delta)})
    return trades


async def fetch_wallet_transactions(
    client: httpx.AsyncClient, address: str, signatures: list[str]
) -> list[dict[str, Any]]:
    """Parse the given signatures into {signature, trades[]} (oldest first)."""
    out: list[dict[str, Any]] = []
    for sig in reversed(signatures):
        try:
            tx = await _rpc(
                client,
                "getParsedTransaction",
                [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
            )
        except Exception:
            continue
        if not tx:
            continue
        trades = _parse_trades(tx, address)
        if trades:
            out.append({"signature": sig, "trades": trades})
    return out


async def _paper_price(mint: str) -> tuple[float | None, dict[str, Any] | None]:
    return await asyncio.to_thread(market.price_for, mint)


async def process_wallet(
    client: httpx.AsyncClient, address: str, meta: dict[str, Any], book: dict[str, Any]
) -> dict[str, Any]:
    """One followed wallet: bootstrap once, then replicate NEW trades in paper."""
    label = meta.get("label") or address[:4]
    mode = config.MODE
    trade_size_usd = float(config.COPY_TRADE_USD or 0.0)
    executed: list[dict[str, Any]] = []

    signatures = await fetch_wallet_signatures(client, address, limit=15)
    seen: set[str] = set(book.get("seen") or [])

    if not meta.get("bootstrapped"):
        # First sight of the wallet: remember history but copy nothing old.
        copy_book.remember_signatures(book, signatures)
        meta["bootstrapped"] = True
        meta["last_signature"] = signatures[0] if signatures else meta.get("last_signature")
        meta["last_scan_at"] = _now()
        return {
            "address": address,
            "label": label,
            "bootstrapped": True,
            "replications": [],
            "note": "history baselined; only new trades will be copied",
        }

    new_sigs = [s for s in signatures if s not in seen]  # signatures are newest-first
    transactions = await fetch_wallet_transactions(client, address, new_sigs)  # oldest-first

    for item in transactions:
        sig = item["signature"]
        for trade in item["trades"]:
            side = trade.get("side")
            mint = trade.get("mint")
            symbol = trade.get("symbol") or "TOKEN"

            if not mint:
                continue

            if side == "buy":
                cash = float(book.get("cash_usd") or 0.0)
                if cash < 5.0:
                    await asyncio.to_thread(
                        alerts.send_copy_alert,
                        trade=trade,
                        label=label,
                        error_reason=f"Insufficient copy cash (${cash:,.2f} available)",
                    )
                    continue

                actual_buy_usd = min(trade_size_usd, cash)
                price, item_market = await _paper_price(mint)
                if not price or price <= 0:
                    await asyncio.to_thread(
                        alerts.send_copy_alert,
                        trade=trade,
                        label=label,
                        error_reason="No live market data to price the copy buy",
                    )
                    continue

                symbol = (item_market or {}).get("symbol") or symbol
                token_amount = actual_buy_usd / price
                fill = {
                    "ok": True,
                    "side": "buy",
                    "mint": mint,
                    "symbol": symbol,
                    "token_amount": token_amount,
                    "cost_usd": actual_buy_usd,
                    "fill_price_usd": price,
                    "dex": (item_market or {}).get("dex") or "dexscreener",
                    "pool_address": (item_market or {}).get("pair_address") or "",
                    "mode": mode,
                }
                book["cash_usd"] = float(book.get("cash_usd") or 0.0) - actual_buy_usd
                pos = copy_book.open_or_add_position(
                    book=book,
                    mint=mint,
                    symbol=symbol,
                    token_amount=token_amount,
                    cost_usd=actual_buy_usd,
                    entry_price=price,
                    pool_address=fill["pool_address"],
                    dex=fill["dex"],
                    signature=sig,
                )
                copy_book.append_fill(
                    book,
                    {
                        "ts": _now(),
                        "side": "buy",
                        "symbol": symbol,
                        "mint": mint,
                        "usd": actual_buy_usd,
                        "cost_usd": actual_buy_usd,
                        "proceeds_usd": None,
                        "price": price,
                        "entry_price": pos.get("entry_price"),
                        "reason": f"copy of {label}",
                        "dex": fill["dex"],
                        "desk": "copy",
                    },
                )
                await asyncio.to_thread(
                    alerts.send_copy_alert, trade=trade, fill=fill, label=label
                )
                executed.append({"side": "buy", "mint": mint, "usd": actual_buy_usd})

            elif side == "sell":
                existing_pos = copy_book.get_position(book, mint)
                if existing_pos and float(existing_pos.get("amount") or 0.0) > 0:
                    held_amount = float(existing_pos["amount"])
                    price, item_market = await _paper_price(mint)
                    if not price or price <= 0:
                        price = existing_pos.get("mark_price") or existing_pos.get("entry_price")
                    if not price:
                        await asyncio.to_thread(
                            alerts.send_copy_alert,
                            trade=trade,
                            label=label,
                            error_reason="No price available to close the copy position",
                        )
                        continue
                    proceeds_usd = held_amount * float(price)
                    fill = {
                        "ok": True,
                        "side": "sell",
                        "mint": mint,
                        "symbol": existing_pos.get("symbol") or symbol,
                        "token_amount": held_amount,
                        "proceeds_usd": proceeds_usd,
                        "fill_price_usd": float(price),
                        "dex": (item_market or {}).get("dex") or existing_pos.get("dex") or "dexscreener",
                        "mode": mode,
                    }
                    close_res = copy_book.reduce_or_close_position(
                        book=book,
                        mint=mint,
                        token_amount=held_amount,
                        exit_price=float(price),
                        proceeds_usd=proceeds_usd,
                        dex=fill["dex"],
                        signature=sig,
                    )
                    fill["realized_pnl_usd"] = close_res.get("realized_pnl_usd") if close_res else 0.0
                    fill["pnl_pct"] = close_res.get("pnl_pct") if close_res else 0.0
                    copy_book.append_fill(
                        book,
                        {
                            "ts": _now(),
                            "side": "sell",
                            "symbol": fill["symbol"],
                            "mint": mint,
                            "usd": proceeds_usd,
                            "cost_usd": None,
                            "proceeds_usd": proceeds_usd,
                            "price": float(price),
                            "entry_price": existing_pos.get("entry_price"),
                            "reason": f"copy of {label} (closed)",
                            "dex": fill["dex"],
                            "desk": "copy",
                        },
                    )
                    await asyncio.to_thread(
                        alerts.send_copy_alert, trade=trade, fill=fill, label=label
                    )
                    executed.append(
                        {"side": "sell", "mint": mint, "usd": proceeds_usd, "fill": fill}
                    )
                else:
                    await asyncio.to_thread(
                        alerts.send_copy_alert,
                        trade=trade,
                        label=label,
                        error_reason="Position: None held in copy book",
                    )

        meta["last_signature"] = sig

    copy_book.remember_signatures(book, new_sigs)
    meta["last_scan_at"] = _now()
    return {"address": address, "label": label, "replications": executed}


async def _mark_copy_positions(book: dict[str, Any]) -> int:
    positions = book.get("positions") or {}
    if not positions:
        return 0
    marks = await asyncio.to_thread(market.prices_for, list(positions.keys()))
    marked = 0
    for mint, pos in positions.items():
        item = marks.get(mint)
        price = (item or {}).get("price_usd")
        if price and price > 0:
            pos["mark_price"] = price
            pos["mark_usd"] = float(pos.get("amount") or 0.0) * price
            pos["unrealized_pnl_usd"] = float(pos["mark_usd"]) - float(pos.get("cost_usd") or 0.0)
            marked += 1
    return marked


async def scan_all_followed_wallets() -> dict[str, Any]:
    """One copy scan: read followed wallets, replicate new trades, re-mark positions."""
    if killswitch.frozen("copy"):
        summary = {
            "ok": False,
            "error": "copy desk frozen",
            "wallets_scanned": 0,
            "replications_count": 0,
            "replications": [],
        }
        mark_copy_scan(summary)
        return summary

    book = copy_book.load()
    wallets: dict[str, Any] = book.get("wallets") or {}

    if not wallets:
        summary = {
            "ok": True,
            "wallets_scanned": 0,
            "replications_count": 0,
            "replications": [],
            "note": "no followed wallets configured",
        }
        book["last_scan"] = summary
        book["last_scan_at"] = _now()
        copy_book.save(book)
        mark_copy_scan(summary)
        return summary

    replications: list[dict[str, Any]] = []
    wallet_errors: dict[str, str] = {}
    scanned = 0

    async with httpx.AsyncClient(timeout=RPC_TIMEOUT, headers={"Accept": "application/json"}) as client:
        for address, meta in list(wallets.items()):
            try:
                result = await process_wallet(client, address, meta, book)
                scanned += 1
                replications.extend(result.get("replications") or [])
            except Exception as exc:
                wallet_errors[address] = f"{type(exc).__name__}: {exc}"
        marked = await _mark_copy_positions(book)

    summary = {
        "ok": not wallet_errors,
        "wallets_scanned": scanned,
        "replications_count": len(replications),
        "replications": replications,
        "positions_marked": marked,
        "mode": "paper",
    }
    if wallet_errors:
        summary["wallet_errors"] = wallet_errors

    book["last_scan"] = summary
    book["last_scan_at"] = _now()
    copy_book.save(book)
    mark_copy_scan(summary)
    await asyncio.to_thread(
        scribe.write_log,
        {"desk": "copy", "event": "scan", **{k: v for k, v in summary.items() if k != "replications"}},
    )
    return summary


def close_position(mint: str) -> dict[str, Any]:
    """Close a copied paper position at its live (or last real) mark."""
    book = copy_book.load()
    pos = copy_book.get_position(book, mint)
    if not pos or float(pos.get("amount") or 0.0) <= 0:
        raise ValueError(f"no open copy position for mint {mint}")

    price = None
    live, item = market.price_for(mint)
    if live and live > 0:
        price = live
        source = "live dexscreener"
    else:
        price = pos.get("mark_price") or pos.get("entry_price")
        source = "last stored mark (dexscreener unavailable)"
    if not price:
        raise ValueError(f"no price available to close {mint}")

    held = float(pos["amount"])
    proceeds = held * float(price)
    close_res = copy_book.reduce_or_close_position(
        book=book,
        mint=mint,
        token_amount=held,
        exit_price=float(price),
        proceeds_usd=proceeds,
        dex=(item or {}).get("dex") or pos.get("dex") or "dexscreener",
        signature="manual-close",
    )
    copy_book.append_fill(
        book,
        {
            "ts": _now(),
            "side": "sell",
            "symbol": pos.get("symbol"),
            "mint": mint,
            "usd": proceeds,
            "proceeds_usd": proceeds,
            "price": float(price),
            "entry_price": pos.get("entry_price"),
            "reason": f"manual copy close [{source}]",
            "dex": pos.get("dex"),
            "desk": "copy",
        },
    )
    copy_book.save(book)
    return {
        "ok": True,
        "mint": mint,
        "proceeds_usd": round(proceeds, 2),
        "realized_pnl_usd": round((close_res or {}).get("realized_pnl_usd") or 0.0, 2),
        "pnl_pct": round((close_res or {}).get("pnl_pct") or 0.0, 2),
        "price_source": source,
        "cash_usd": round(float(book.get("cash_usd") or 0.0), 2),
    }
