"""
Tests for the CandleCache service (T22 § 8. Candle Cache Verification).
Covers:
 - store_candles → rows written to DB
 - get_cached_candles → returns stored rows in date order
 - find_missing_ranges → gap detection
 - Full cache hit (no missing ranges after full store)
 - Today's candle is not cached during market hours
 - Historical data is immutable (store_candles doesn't update existing rows)
"""
import pytest
from datetime import datetime, date
from zoneinfo import ZoneInfo
from unittest.mock import patch

from app.services.candle_cache import store_candles, get_cached_candles, find_missing_ranges
from app.models.candle import CandleCache

IST = ZoneInfo("Asia/Kolkata")


def _make_candle(trade_date: str, close: float = 100.0) -> dict:
    return {"date": trade_date, "open": 99.0, "high": 101.0, "low": 98.0,
            "close": close, "volume": 5000}


# ── store_candles ─────────────────────────────────────────────────────────────

def test_store_candles_writes_rows(db):
    candles = [
        _make_candle("2023-06-01"),
        _make_candle("2023-06-02"),
        _make_candle("2023-06-05"),
    ]
    count = store_candles(db, "2885", candles)
    assert count == 3

    rows = db.query(CandleCache).filter_by(security_id="2885").all()
    assert len(rows) == 3
    dates = {r.trade_date for r in rows}
    assert "2023-06-01" in dates
    assert "2023-06-02" in dates
    assert "2023-06-05" in dates


def test_store_candles_does_not_update_existing(db):
    """Historical candles are immutable — re-storing should be a no-op."""
    store_candles(db, "2885", [_make_candle("2023-06-01", close=100.0)])

    # Store same date with different close — existing row should NOT change
    store_candles(db, "2885", [_make_candle("2023-06-01", close=200.0)])

    rows = db.query(CandleCache).filter_by(security_id="2885", trade_date="2023-06-01").all()
    assert len(rows) == 1
    assert rows[0].close == 100.0  # original value preserved


def test_store_candles_skips_today_during_market_hours(db):
    today = datetime.now(IST).strftime("%Y-%m-%d")
    candle = _make_candle(today)

    # Simulate market still open (before 15:30 IST)
    with patch("app.services.candle_cache._market_closed_today", return_value=False):
        count = store_candles(db, "2885", [candle])

    assert count == 0
    rows = db.query(CandleCache).filter_by(security_id="2885", trade_date=today).all()
    assert len(rows) == 0


def test_store_candles_allows_today_after_market_close(db):
    today = datetime.now(IST).strftime("%Y-%m-%d")
    candle = _make_candle(today)

    with patch("app.services.candle_cache._market_closed_today", return_value=True):
        count = store_candles(db, "2885", [candle])

    assert count == 1


# ── get_cached_candles ────────────────────────────────────────────────────────

def test_get_cached_candles_empty(db):
    result = get_cached_candles(db, "2885", "2023-01-01", "2023-12-31")
    assert result == []


def test_get_cached_candles_returns_correct_range(db):
    all_candles = [_make_candle(f"2023-0{m}-01") for m in range(1, 7)]
    store_candles(db, "2885", all_candles)

    result = get_cached_candles(db, "2885", "2023-02-01", "2023-04-01")
    dates = [c["date"] for c in result]
    assert "2023-02-01" in dates
    assert "2023-03-01" in dates
    assert "2023-04-01" in dates
    assert "2023-01-01" not in dates  # before from_date
    assert "2023-05-01" not in dates  # after to_date


def test_get_cached_candles_sorted_by_date(db):
    candles = [_make_candle("2023-06-05"), _make_candle("2023-06-01"), _make_candle("2023-06-02")]
    store_candles(db, "2885", candles)

    result = get_cached_candles(db, "2885", "2023-06-01", "2023-06-05")
    dates = [c["date"] for c in result]
    assert dates == sorted(dates)


def test_get_cached_candles_correct_fields(db):
    store_candles(db, "9999", [{"date": "2023-07-01", "open": 10.5, "high": 11.0,
                                 "low": 10.0, "close": 10.8, "volume": 1234}])
    result = get_cached_candles(db, "9999", "2023-07-01", "2023-07-01")
    assert len(result) == 1
    c = result[0]
    assert c["date"] == "2023-07-01"
    assert c["open"] == pytest.approx(10.5)
    assert c["close"] == pytest.approx(10.8)
    assert c["volume"] == 1234


# ── find_missing_ranges ───────────────────────────────────────────────────────

def test_find_missing_ranges_all_missing(db):
    """Nothing cached → all weekdays in the range are reported as missing."""
    # 2023-06-01 (Thu) to 2023-06-07 (Wed) — weekdays: Thu, Fri, Mon, Tue, Wed
    # The weekend (Sat 06-03, Sun 06-04) splits this into two contiguous ranges.
    ranges = find_missing_ranges(db, "2885", "2023-06-01", "2023-06-07")
    assert len(ranges) >= 1

    # Collect every missing weekday across all returned ranges
    all_missing = set()
    for gap_start, gap_end in ranges:
        d = date.fromisoformat(gap_start)
        while d.isoformat() <= gap_end:
            if d.weekday() < 5:
                all_missing.add(d.isoformat())
            d = date.fromordinal(d.toordinal() + 1)

    # All weekdays from the input range must be flagged as missing
    assert "2023-06-01" in all_missing  # Thu
    assert "2023-06-02" in all_missing  # Fri
    assert "2023-06-05" in all_missing  # Mon
    assert "2023-06-06" in all_missing  # Tue
    assert "2023-06-07" in all_missing  # Wed
    # Weekend should not appear
    assert "2023-06-03" not in all_missing
    assert "2023-06-04" not in all_missing


def test_find_missing_ranges_none_missing(db):
    """All weekdays cached → no missing ranges."""
    # Week: Mon 2023-06-05 to Fri 2023-06-09 (5 trading days)
    weekdays = ["2023-06-05", "2023-06-06", "2023-06-07", "2023-06-08", "2023-06-09"]
    store_candles(db, "2885", [_make_candle(d) for d in weekdays])

    ranges = find_missing_ranges(db, "2885", "2023-06-05", "2023-06-09")
    assert ranges == []


def test_find_missing_ranges_gap_in_middle(db):
    """Cache has first and last days but not middle."""
    store_candles(db, "2885", [_make_candle("2023-06-05")])  # Monday
    # Tuesday 2023-06-06, Wednesday 2023-06-07 are missing
    store_candles(db, "2885", [_make_candle("2023-06-08")])  # Thursday

    ranges = find_missing_ranges(db, "2885", "2023-06-05", "2023-06-08")
    # The gap is 2023-06-06 to 2023-06-07
    assert len(ranges) >= 1
    all_gaps = set()
    for start, end in ranges:
        d = date.fromisoformat(start)
        while d.isoformat() <= end:
            if d.weekday() < 5:
                all_gaps.add(d.isoformat())
            d = date.fromordinal(d.toordinal() + 1)
    assert "2023-06-06" in all_gaps
    assert "2023-06-07" in all_gaps
    assert "2023-06-05" not in all_gaps  # cached
    assert "2023-06-08" not in all_gaps  # cached


def test_find_missing_ranges_excludes_weekends(db):
    """Weekends should not appear as missing ranges even when uncached."""
    # 2023-06-09 is Friday, 2023-06-12 is Monday
    store_candles(db, "2885", [_make_candle("2023-06-09"), _make_candle("2023-06-12")])

    ranges = find_missing_ranges(db, "2885", "2023-06-09", "2023-06-12")
    # Sat/Sun are not trading days → no gap between Fri and Mon
    assert ranges == []
