"""Wallet routes: /wallet and its receive / send / withdraw mutations."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import wallet

router = APIRouter()


class ReceiveBody(BaseModel):
    amount_usd: float
    note: str = ""


class SendBody(BaseModel):
    amount_usd: float
    dest: str
    note: str = ""


class WithdrawBody(BaseModel):
    amount_usd: float
    source: str


def _err(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/wallet")
def get_wallet() -> dict:
    return wallet.status()


@router.post("/wallet/receive")
def receive(body: ReceiveBody) -> dict:
    try:
        wallet.receive(body.amount_usd, body.note)
    except ValueError as exc:
        raise _err(exc) from exc
    return wallet.status()


@router.post("/wallet/send")
def send(body: SendBody) -> dict:
    try:
        wallet.send(body.amount_usd, body.dest, body.note)
    except ValueError as exc:
        raise _err(exc) from exc
    return wallet.status()


@router.post("/wallet/withdraw")
def withdraw(body: WithdrawBody) -> dict:
    try:
        wallet.withdraw(body.amount_usd, body.source)
    except ValueError as exc:
        raise _err(exc) from exc
    return wallet.status()
