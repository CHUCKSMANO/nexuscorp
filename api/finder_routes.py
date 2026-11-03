"""Finder routes: /finder/filters (GET/POST), /finder/preset, POST /finder/scan."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from finder import filters as finder_filters
from finder.cycle import run_cycle

router = APIRouter()


class FilterBody(BaseModel):
    key: str
    value: float


class PresetBody(BaseModel):
    name: str


@router.get("/finder/filters")
def get_filters() -> dict:
    return {"filters": finder_filters.load()}


@router.post("/finder/filters")
def set_filter(body: FilterBody) -> dict:
    try:
        finder_filters.set_filter(body.key.strip(), body.value)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"filters": finder_filters.load()}


@router.post("/finder/preset")
def apply_preset(body: PresetBody) -> dict:
    try:
        finder_filters.apply_preset(body.name)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"filters": finder_filters.load()}


@router.post("/finder/scan")
async def scan() -> dict:
    try:
        return await run_cycle()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"finder scan failed: {exc}") from exc
