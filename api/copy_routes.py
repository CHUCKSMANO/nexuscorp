"""Copy desk routes: status, wallets CRUD, scan, close."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.common import copy_status
from copytrader import book as copy_book
from copytrader.engine import close_position, scan_all_followed_wallets

router = APIRouter()

MINT_RE = r"^[1-9A-HJ-NP-Za-km-z]{32,44}$"


class FollowBody(BaseModel):
    address: str
    label: str = ""


class CloseBody(BaseModel):
    mint: str


def _valid_address(address: str) -> bool:
    import re

    return bool(re.match(MINT_RE, address.strip()))


@router.get("/copy/status")
def get_status() -> dict:
    return copy_status()


@router.get("/copy/wallets")
def get_wallets() -> dict:
    cstate = copy_book.load()
    return {"wallets": cstate.get("wallets") or {}}


@router.post("/copy/wallets")
def follow_wallet(body: FollowBody) -> dict:
    address = body.address.strip()
    if not _valid_address(address):
        raise HTTPException(status_code=400, detail="address is not a valid Solana public key")
    wallet_meta = copy_book.follow(address, body.label.strip())
    return {
        "ok": True,
        "address": address,
        "wallet": wallet_meta,
        "wallets": (copy_book.load().get("wallets") or {}),
    }


@router.delete("/copy/wallets/{address}")
def unfollow_wallet(address: str) -> dict:
    removed = copy_book.unfollow(address)
    if not removed:
        raise HTTPException(status_code=404, detail=f"wallet {address} is not followed")
    return {"ok": True, "address": address, "removed": True}


@router.post("/copy/scan")
async def trigger_scan() -> dict:
    try:
        return await scan_all_followed_wallets()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"copy scan failed: {exc}") from exc


@router.post("/copy/close")
def close(body: CloseBody) -> dict:
    mint = body.mint.strip()
    if not mint:
        raise HTTPException(status_code=400, detail="mint is required")
    try:
        return close_position(mint)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
