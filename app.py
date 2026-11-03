#!/usr/bin/env python3
"""The Token Yielder — yield desk + finder desk, localhost FastAPI."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.copy_routes import router as copy_router
from api.finder_routes import router as finder_router
from api.ops_routes import router as ops_router
from api.trade_routes import router as trade_router
from api.wallet_routes import router as wallet_router
from api.yield_routes import router as yield_router
from config import (
    API_HOST,
    API_PORT,
    COPY_POLL_SECONDS,
    FINDER_SCAN_SECONDS,
    LOOP_SECONDS,
    TRADE_MARK_SECONDS,
)
from copytrader.engine import scan_all_followed_wallets
from finder.cycle import run_cycle
from loop import tick
from runtime import mark_started
from trader.engine import mark_all as mark_trades


ROOT_DIR = Path(__file__).resolve().parent
CONSOLE_DIR = ROOT_DIR / "nexus-console"


async def _repeat(stop: asyncio.Event, interval: float, job, name: str) -> None:
    while not stop.is_set():
        try:
            result = job()
            if asyncio.iscoroutine(result):
                await result
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"{name} failed: {exc}")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


async def _yield_job():
    await asyncio.to_thread(tick)


def create_app(*, schedule: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        mark_started()
        if not schedule:
            yield
            return
        stop = asyncio.Event()
        yield_task = asyncio.create_task(
            _repeat(stop, LOOP_SECONDS, _yield_job, "yield"),
            name="yield-scheduler",
        )
        finder_task = asyncio.create_task(
            _repeat(stop, FINDER_SCAN_SECONDS, run_cycle, "finder"),
            name="finder-scheduler",
        )
        copy_task = asyncio.create_task(
            _repeat(stop, COPY_POLL_SECONDS, scan_all_followed_wallets, "copy"),
            name="copy-scheduler",
        )
        trade_task = asyncio.create_task(
            _repeat(stop, TRADE_MARK_SECONDS, mark_trades, "trade"),
            name="trade-scheduler",
        )
        yield
        stop.set()
        yield_task.cancel()
        finder_task.cancel()
        copy_task.cancel()
        trade_task.cancel()
        await asyncio.gather(yield_task, finder_task, copy_task, trade_task, return_exceptions=True)

    app = FastAPI(title="NexusCorp Terminal", lifespan=lifespan)
    app.include_router(ops_router)
    app.include_router(yield_router)
    app.include_router(finder_router)
    app.include_router(copy_router)
    app.include_router(wallet_router)
    app.include_router(trade_router)
    if CONSOLE_DIR.exists():
        app.mount("/console", StaticFiles(directory=CONSOLE_DIR), name="console")

        @app.get("/", include_in_schema=False)
        def console_index():
            return FileResponse(CONSOLE_DIR / "index.html")

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=API_HOST, port=API_PORT, log_level="info")


if __name__ == "__main__":
    main()
