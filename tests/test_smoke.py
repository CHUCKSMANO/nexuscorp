"""Smoke tests: contract shapes + paper book math (no network)."""

from __future__ import annotations

import app as app_module
from api.common import copy_status, finder_status, health_payload, yield_status
from copytrader import book as copy_book


def test_import_app():
    assert app_module.app is not None


def test_health_shape():
    health = health_payload()
    assert health["ok"] is True
    assert health["name"] == "The Token Yielder"
    assert {"all", "yield", "finder", "copy", "reason"} <= set(health["frozen"])
    assert {"started_at", "last_yield_tick_at"} <= set(health["runtime"])


def test_yield_status_shape():
    status = yield_status()
    assert status["desk"] == "yield"
    assert status["cash_usd"] >= 0
    assert status["paper_per_day"] >= 0
    assert "position" in status and "best" in status and "source" in status


def test_finder_status_shape():
    status = finder_status()
    assert status["desk"] == "finder"
    assert isinstance(status["tracked_count"], int)


def test_copy_status_shape():
    status = copy_status()
    assert status["desk"] == "copy"
    assert status["wallet_count"] == len(status["wallets"])


def test_routes_registered():
    # FastAPI >= 0.143 wraps include_router() results in _IncludedRouter objects
    # that intentionally hide .path; the OpenAPI schema is the reliable view.
    paths = set(app_module.app.openapi()["paths"])
    for path in (
        "/health",
        "/status",
        "/yield/status",
        "/yield/stands",
        "/yield/plan",
        "/yield/tick",
        "/wallet",
        "/wallet/receive",
        "/wallet/send",
        "/wallet/withdraw",
        "/trade/status",
        "/trade/markets",
        "/trade/quote",
        "/trade/buy",
        "/trade/sell",
        "/trade/mark",
        "/copy/status",
        "/copy/wallets",
        "/copy/scan",
        "/copy/close",
        "/finder/filters",
        "/finder/preset",
        "/finder/scan",
        "/ops/freeze",
        "/ops/thaw",
    ):
        assert path in paths, f"missing route {path}"


def test_copy_book_open_and_close():
    book = copy_book.load()
    cash_before = float(book["cash_usd"])
    copy_book.open_or_add_position(
        book=book,
        mint="TestMint11111111111111111111111111111111",
        symbol="TST",
        token_amount=10.0,
        cost_usd=25.0,
        entry_price=2.5,
        pool_address="pool",
        dex="test",
        signature="sig",
    )
    # buying leaves cash to the engine, which deducts cost before calling
    # open_or_add_position (copytrader/engine.py); only sells credit cash.
    assert float(book["cash_usd"]) == cash_before
    pos = copy_book.get_position(book, "TestMint11111111111111111111111111111111")
    assert pos is not None and pos["amount"] == 10.0
    res = copy_book.reduce_or_close_position(
        book=book,
        mint="TestMint11111111111111111111111111111111",
        token_amount=10.0,
        exit_price=3.0,
        proceeds_usd=30.0,
        dex="test",
        signature="sig2",
    )
    assert abs(res["realized_pnl_usd"] - 5.0) < 1e-6
    assert copy_book.get_position(book, "TestMint11111111111111111111111111111111") is None
    # restore starting cash so the on-disk book stays pristine for manual testing
    book["cash_usd"] = cash_before
    book["positions"].pop("TestMint11111111111111111111111111111111", None)
    if book["fills"]:
        book["fills"] = book["fills"][1:]
    copy_book.save(book)
