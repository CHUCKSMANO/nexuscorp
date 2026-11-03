"""Ops + health/status routes: /health, /status, /ops/freeze, /ops/thaw."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import killswitch
from api.common import aggregate_status, health_payload

router = APIRouter()


class FreezeBody(BaseModel):
    desk: str
    reason: str = ""


class ThawBody(BaseModel):
    desk: str


@router.get("/health")
def health() -> dict:
    return health_payload()


@router.get("/status")
def status() -> dict:
    return aggregate_status()


@router.post("/ops/freeze")
def freeze(body: FreezeBody) -> dict:
    try:
        killswitch.freeze(body.desk.strip(), body.reason.strip())
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return killswitch.get_state()


@router.post("/ops/thaw")
def thaw(body: ThawBody) -> dict:
    try:
        killswitch.thaw(body.desk.strip())
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return killswitch.get_state()
