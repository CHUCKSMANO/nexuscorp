"""Trade desk routes: status, markets, quote, buy, sell, mark."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import market
from trader import engine as trade_engine

router = APIRouter()


class BuyBody(BaseModel):
    mint: str
    amount_usd: float
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None


class SellBody(BaseModel):
    mint: str
    amount_usd: float | None = None


@router.get("/trade/status")
def get_status() -> dict:
    return trade_engine.status()


@router.get("/trade/markets")
def markets(limit: int = 30) -> dict:
    limit = max(1, min(int(limit), 100))
    try:
        return {"markets": market.markets(limit)}
    except market.MarketUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"market data unavailable: {exc}") from exc


@router.get("/trade/quote")
def quote(q: str) -> dict:
    query = (q or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="q is required")
    try:
        return market.quote(query)
    except market.MarketUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"market data unavailable: {exc}") from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/trade/buy")
def buy(body: BuyBody) -> dict:
    try:
        return trade_engine.buy(
            body.mint,
            body.amount_usd,
            stop_loss_pct=body.stop_loss_pct,
            take_profit_pct=body.take_profit_pct,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except market.MarketUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"market data unavailable: {exc}") from exc


@router.post("/trade/sell")
def sell(body: SellBody) -> dict:
    try:
        return trade_engine.sell(body.mint, body.amount_usd)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except market.MarketUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"market data unavailable: {exc}") from exc


@router.post("/trade/mark")
async def mark() -> dict:
    try:
        return await trade_engine.mark_all()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"mark failed: {exc}") from exc
