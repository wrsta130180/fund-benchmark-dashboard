"""
Regression tests for dashboard calculation functions.

Run with:  python -m pytest tests/ -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta

# ── Import pure functions from dashboard (no Streamlit execution) ─────────────
# Patch st so the module-level Streamlit calls don't error on import
import unittest.mock as mock
import types

_st_stub = mock.MagicMock()
_st_stub.cache_data = lambda **kw: (lambda f: f)   # pass-through decorator
_st_stub.set_page_config = mock.MagicMock()
_st_stub.markdown = mock.MagicMock()
sys.modules["streamlit"] = _st_stub

import importlib.util
spec = importlib.util.spec_from_file_location(
    "dashboard",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard.py"),
)
# Execute only up to the point we need; stop before Streamlit app layout
# by catching the AttributeError that the stub raises on st.sidebar
try:
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
except Exception:
    pass  # layout code fails on stub — functions are already defined

from dashboard import (
    compute_indicators,
    val_at_offset,
    sma_pct_at_offset,
    rsi_color,
    sma_color,
    fmt_rsi,
    fmt_pct,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_df(prices, start="2020-01-01"):
    """Build a minimal Close/Volume DataFrame from a price list."""
    idx = pd.date_range(start=start, periods=len(prices), freq="B")
    return pd.DataFrame({"Close": prices, "Volume": [1_000_000] * len(prices)}, index=idx)


def _trending_up(n=300):
    """Rising prices with small daily oscillation so RSI is defined (no zero-loss issue)."""
    rng = [100 + i * 0.5 + (1 if i % 3 != 0 else -0.1) for i in range(n)]
    return _make_df(rng)


def _trending_down(n=300):
    return _make_df([250 - i * 0.5 for i in range(n)])


def _flat(n=300):
    return _make_df([150.0] * n)


# ── SMA / EMA ─────────────────────────────────────────────────────────────────

class TestMovingAverages:

    def test_sma50_matches_pandas_rolling(self):
        df = compute_indicators(_trending_up())
        expected = df["Close"].rolling(50).mean()
        pd.testing.assert_series_equal(df["SMA50"], expected, check_names=False)

    def test_sma100_matches_pandas_rolling(self):
        df = compute_indicators(_trending_up())
        expected = df["Close"].rolling(100).mean()
        pd.testing.assert_series_equal(df["SMA100"], expected, check_names=False)

    def test_sma200_matches_pandas_rolling(self):
        df = compute_indicators(_trending_up())
        expected = df["Close"].rolling(200).mean()
        pd.testing.assert_series_equal(df["SMA200"], expected, check_names=False)

    def test_ema50_matches_pandas_ewm(self):
        df = compute_indicators(_trending_up())
        expected = df["Close"].ewm(span=50, adjust=False).mean()
        pd.testing.assert_series_equal(df["EMA50"], expected, check_names=False)

    def test_ema100_matches_pandas_ewm(self):
        df = compute_indicators(_trending_up())
        expected = df["Close"].ewm(span=100, adjust=False).mean()
        pd.testing.assert_series_equal(df["EMA100"], expected, check_names=False)

    def test_ema200_matches_pandas_ewm(self):
        df = compute_indicators(_trending_up())
        expected = df["Close"].ewm(span=200, adjust=False).mean()
        pd.testing.assert_series_equal(df["EMA200"], expected, check_names=False)

    def test_price_above_all_smas_in_uptrend(self):
        df = compute_indicators(_trending_up())
        last = df.iloc[-1]
        assert last["Close"] > last["SMA50"]
        assert last["Close"] > last["SMA100"]
        assert last["Close"] > last["SMA200"]

    def test_price_below_all_smas_in_downtrend(self):
        df = compute_indicators(_trending_down())
        last = df.iloc[-1]
        assert last["Close"] < last["SMA50"]
        assert last["Close"] < last["SMA100"]
        assert last["Close"] < last["SMA200"]

    def test_sma_equals_price_when_flat(self):
        df = compute_indicators(_flat())
        last = df.iloc[-1]
        assert abs(last["SMA50"]  - last["Close"]) < 1e-9
        assert abs(last["SMA200"] - last["Close"]) < 1e-9


# ── RSI ───────────────────────────────────────────────────────────────────────

class TestRSI:

    def test_rsi_bounds(self):
        """RSI must always be in [0, 100]."""
        for df_fn in [_trending_up, _trending_down, _flat]:
            df = compute_indicators(df_fn())
            for col in ["RSI3", "RSI14", "RSI30"]:
                valid = df[col].dropna()
                assert (valid >= 0).all() and (valid <= 100).all(), \
                    f"{col} out of [0,100] range"

    def test_rsi_high_in_uptrend(self):
        """Sustained uptrend should produce RSI-14 well above 50."""
        df = compute_indicators(_trending_up())
        assert df["RSI14"].dropna().iloc[-1] > 60

    def test_rsi_low_in_downtrend(self):
        """Sustained downtrend should produce RSI-14 well below 50."""
        df = compute_indicators(_trending_down())
        assert df["RSI14"].dropna().iloc[-1] < 40

    def test_rsi_near_50_when_flat(self):
        """Flat price (no gain/loss) → RSI converges toward 50."""
        prices = [150.0] * 5 + [150.5, 149.5] * 148  # tiny oscillation
        df = compute_indicators(_make_df(prices))
        rsi = df["RSI14"].dropna().iloc[-1]
        assert 40 < rsi < 60

    def test_rsi3_more_reactive_than_rsi30(self):
        """After a sudden surge RSI-3 should spike higher than RSI-30."""
        # flat then sharp 3-day rally — RSI-3 captures it fully, RSI-30 is dampened
        prices = [100.0] * 100 + [100.5, 99.8] * 50 + [110.0, 112.0, 115.0]
        df = compute_indicators(_make_df(prices))
        assert df["RSI3"].dropna().iloc[-1] > df["RSI30"].dropna().iloc[-1]


# ── val_at_offset / sma_pct_at_offset ────────────────────────────────────────

class TestHelpers:

    def setup_method(self):
        self.df = compute_indicators(_trending_up())

    def test_val_at_offset_zero_returns_last_row(self):
        v = val_at_offset(self.df, 0, "Close")
        assert v == pytest.approx(self.df["Close"].iloc[-1])

    def test_val_at_offset_lookback(self):
        """7-day offset should return a value before the last row."""
        v0 = val_at_offset(self.df, 0,  "Close")
        v7 = val_at_offset(self.df, 7,  "Close")
        assert v7 < v0  # uptrend, so older price is lower

    def test_val_at_offset_beyond_history_returns_nan(self):
        v = val_at_offset(self.df, 99_999, "Close")
        assert pd.isna(v)

    def test_sma_pct_positive_when_price_above_sma(self):
        pct = sma_pct_at_offset(self.df, 0, "SMA200")
        assert pct > 0  # uptrend → price > SMA200

    def test_sma_pct_negative_when_price_below_sma(self):
        df = compute_indicators(_trending_down())
        pct = sma_pct_at_offset(df, 0, "SMA200")
        assert pct < 0

    def test_sma_pct_zero_when_flat(self):
        df = compute_indicators(_flat())
        pct = sma_pct_at_offset(df, 0, "SMA50")
        assert abs(pct) < 1e-6


# ── Color scales ──────────────────────────────────────────────────────────────

class TestColorScales:

    # RSI colors
    def test_rsi_overbought(self):
        assert rsi_color(70)  == "#c0392b"
        assert rsi_color(85)  == "#c0392b"
        assert rsi_color(100) == "#c0392b"

    def test_rsi_elevated(self):
        assert rsi_color(60) == "#e67e22"
        assert rsi_color(65) == "#e67e22"

    def test_rsi_oversold(self):
        assert rsi_color(30) == "#27ae60"
        assert rsi_color(15) == "#27ae60"
        assert rsi_color(0)  == "#27ae60"

    def test_rsi_depressed(self):
        assert rsi_color(40) == "#2ecc71"
        assert rsi_color(35) == "#2ecc71"

    def test_rsi_neutral(self):
        assert rsi_color(50) == "#d1d5db"
        assert rsi_color(55) == "#d1d5db"

    def test_rsi_nan_returns_grey(self):
        assert rsi_color(np.nan) == "#f3f4f6"

    # SMA colors
    def test_sma_far_above(self):
        assert sma_color(10)  == "#c0392b"
        assert sma_color(20)  == "#c0392b"

    def test_sma_slightly_above(self):
        assert sma_color(3)   == "#e67e22"
        assert sma_color(7)   == "#e67e22"

    def test_sma_far_below(self):
        assert sma_color(-10) == "#27ae60"
        assert sma_color(-20) == "#27ae60"

    def test_sma_slightly_below(self):
        assert sma_color(-3)  == "#2ecc71"
        assert sma_color(-7)  == "#2ecc71"

    def test_sma_neutral(self):
        assert sma_color(0)   == "#d1d5db"
        assert sma_color(2)   == "#d1d5db"
        assert sma_color(-2)  == "#d1d5db"

    def test_sma_nan_returns_grey(self):
        assert sma_color(np.nan) == "#f3f4f6"


# ── Formatters ────────────────────────────────────────────────────────────────

class TestFormatters:

    def test_fmt_rsi_rounds_to_integer(self):
        assert fmt_rsi(55.7) == "56"   # standard rounding
        assert fmt_rsi(55.4) == "55"
        assert fmt_rsi(30.0) == "30"

    def test_fmt_rsi_nan_returns_dash(self):
        assert fmt_rsi(np.nan) == "—"

    def test_fmt_pct_positive(self):
        assert fmt_pct(3.456) == "+3.5%"

    def test_fmt_pct_negative(self):
        assert fmt_pct(-1.2) == "-1.2%"

    def test_fmt_pct_nan_returns_dash(self):
        assert fmt_pct(np.nan) == "—"


# ── Price return (Insights page helper) ──────────────────────────────────────

class TestPriceReturn:
    """Validate the inline price_return logic used on the Insights page."""

    def _price_return(self, df, offset_days):
        sub = df[df.index <= df.index[-1] - timedelta(days=offset_days)]
        if sub.empty or pd.isna(df["Close"].iloc[-1]):
            return np.nan
        past = sub.iloc[-1]["Close"]
        return (df["Close"].iloc[-1] - past) / past * 100 if past else np.nan

    def test_positive_return_in_uptrend(self):
        df = compute_indicators(_trending_up())
        assert self._price_return(df, 30) > 0

    def test_negative_return_in_downtrend(self):
        df = compute_indicators(_trending_down())
        assert self._price_return(df, 30) < 0

    def test_zero_return_when_flat(self):
        df = compute_indicators(_flat())
        assert abs(self._price_return(df, 30)) < 1e-9

    def test_known_return(self):
        """100 → 110: lookback of 90 calendar days spans the step → exactly +10%."""
        # 50 biz days in 100-block then 50 biz days in 110-block.
        # 90 calendar days ≈ 64 biz days, landing solidly in the 100-block.
        prices = [100.0] * 100 + [110.0] * 50
        df = compute_indicators(_make_df(prices))
        ret = self._price_return(df, 90)
        assert ret == pytest.approx(10.0, rel=1e-6)
