"""
Live financial validation tests.

These tests download real market data and compare our calculations against the
`ta` library (a well-tested independent reference implementation).

Run all tests:          python -m pytest tests/ -v
Run live tests only:    python -m pytest tests/test_live_validation.py -v
Skip live tests:        python -m pytest tests/test_calculations.py -v

Requires internet access.  Results are cached by yfinance for the session.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import pandas as pd
import pytest
import unittest.mock as mock

# ── Stub Streamlit so dashboard imports without running the app ───────────────
_st_stub = mock.MagicMock()
_st_stub.cache_data = lambda **kw: (lambda f: f)
_st_stub.set_page_config = mock.MagicMock()
_st_stub.markdown = mock.MagicMock()
sys.modules["streamlit"] = _st_stub

import importlib.util
spec = importlib.util.spec_from_file_location(
    "dashboard",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard.py"),
)
try:
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
except Exception:
    pass

from dashboard import compute_indicators

import yfinance as yf
import ta


# ── Shared fixture — downloaded once per session ──────────────────────────────

@pytest.fixture(scope="module")
def spx_raw():
    """Download ~2 years of S&P 500 daily closes."""
    df = yf.download("^GSPC", start="2022-01-01", auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Close", "Volume"]].dropna()
    assert len(df) > 200, "Not enough data fetched — check internet connection"
    return df


@pytest.fixture(scope="module")
def spx(spx_raw):
    return compute_indicators(spx_raw)


# ── SMA validation ────────────────────────────────────────────────────────────

class TestSMAvsReference:
    """SMA is unambiguous — every platform uses the same formula."""

    def test_sma50_matches_ta_library(self, spx):
        ref = ta.trend.sma_indicator(spx["Close"], window=50)
        pd.testing.assert_series_equal(
            spx["SMA50"].dropna(), ref.dropna(),
            check_names=False, rtol=1e-6,
        )

    def test_sma100_matches_ta_library(self, spx):
        ref = ta.trend.sma_indicator(spx["Close"], window=100)
        pd.testing.assert_series_equal(
            spx["SMA100"].dropna(), ref.dropna(),
            check_names=False, rtol=1e-6,
        )

    def test_sma200_matches_ta_library(self, spx):
        ref = ta.trend.sma_indicator(spx["Close"], window=200)
        pd.testing.assert_series_equal(
            spx["SMA200"].dropna(), ref.dropna(),
            check_names=False, rtol=1e-6,
        )


# ── EMA validation ────────────────────────────────────────────────────────────

class TestEMAvsReference:
    """
    The `ta` library requires `window` warmup rows before outputting EMA values
    (min_periods=window), while our ewm(adjust=False) outputs from row 1 using
    exponential weighting.  We compare only rows where both have a value.
    """

    def _compare_ema(self, spx, col, window):
        ref = ta.trend.ema_indicator(spx["Close"], window=window)
        ours, theirs = spx[col].align(ref, join="inner")
        both = pd.concat([ours, theirs], axis=1).dropna()
        pd.testing.assert_series_equal(
            both.iloc[:, 0], both.iloc[:, 1],
            check_names=False, rtol=1e-4,
        )

    def test_ema50_matches_ta_library(self, spx):
        self._compare_ema(spx, "EMA50", 50)

    def test_ema100_matches_ta_library(self, spx):
        self._compare_ema(spx, "EMA100", 100)

    def test_ema200_matches_ta_library(self, spx):
        self._compare_ema(spx, "EMA200", 200)


# ── RSI validation ────────────────────────────────────────────────────────────
#
# NOTE: Most professional platforms (Bloomberg, TradingView) use Wilder's
# Smoothed RSI which applies ewm(alpha=1/period) for gain/loss smoothing.
# Our dashboard uses a simple rolling mean, which diverges slightly.
#
# The test below measures the average absolute deviation so you can see
# exactly how large the discrepancy is on real SPX data.

class TestRSIvsReference:

    def _wilder_rsi(self, close: pd.Series, period: int) -> pd.Series:
        """Wilder's Smoothed RSI — industry standard used by Bloomberg/TradingView."""
        delta = close.diff()
        gain  = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
        loss  = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
        rs    = gain / loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def test_rsi14_matches_wilder(self, spx):
        """
        Dashboard RSI-14 should use Wilder's Smoothed RSI (ewm alpha=1/period)
        and match the reference implementation within 0.01 points.
        """
        wilder = self._wilder_rsi(spx["Close"], 14)
        our    = spx["RSI14"]
        both   = pd.concat([our, wilder], axis=1).dropna()
        mae    = (both.iloc[:, 0] - both.iloc[:, 1]).abs().mean()
        print(f"\n  RSI-14 mean absolute error vs Wilder's: {mae:.6f} pts")
        assert mae < 0.01, (
            f"RSI-14 deviates {mae:.4f} pts from Wilder's formula. "
            "Ensure compute_indicators() uses ewm(alpha=1/period, adjust=False)."
        )

    def test_rsi14_bounds_on_real_data(self, spx):
        valid = spx["RSI14"].dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_rsi_values_are_recent(self, spx):
        """Last RSI value should not be NaN — data is current."""
        assert not pd.isna(spx["RSI14"].iloc[-1])
        assert not pd.isna(spx["RSI30"].iloc[-1])


# ── Data quality checks ───────────────────────────────────────────────────────

class TestDataQuality:

    def test_prices_are_positive(self, spx_raw):
        assert (spx_raw["Close"] > 0).all()

    def test_no_missing_closes(self, spx_raw):
        assert spx_raw["Close"].isna().sum() == 0

    def test_data_is_recent(self, spx_raw):
        """Most recent row should be within 5 calendar days of today."""
        from datetime import datetime, timedelta
        last_date = spx_raw.index[-1]
        if hasattr(last_date, 'date'):
            last_date = last_date.date()
        gap = (datetime.today().date() - last_date).days
        assert gap <= 5, f"Most recent data is {gap} days old — yfinance may be stale"

    def test_no_zero_prices(self, spx_raw):
        assert (spx_raw["Close"] != 0).all()

    def test_no_extreme_single_day_moves(self, spx_raw):
        """Flag any single-day move > 20% as likely a data error."""
        pct_change = spx_raw["Close"].pct_change().abs()
        bad = pct_change[pct_change > 0.20]
        assert len(bad) == 0, f"Suspicious price jumps on: {bad.index.tolist()}"
