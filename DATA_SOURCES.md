# Fund Benchmark Dashboard — Data Sources & Methodology

## Overview

This document explains exactly where every number in the dashboard comes from, how it is calculated, and what limitations apply. It is intended for due diligence review of the tool's data integrity.

---

## 1. Primary Data Source

**All price and volume data is sourced from Yahoo Finance via the `yfinance` Python library (v0.2.40+).**

- Yahoo Finance aggregates data from exchange feeds and third-party providers.
- Data is fetched with `auto_adjust=True`, meaning prices are adjusted for splits and dividends automatically.
- Only `Close` (adjusted closing price) and `Volume` are used in all calculations.
- Data is requested from January 1, 1950 forward (or the instrument's inception, whichever is later).
- Data is **cached for 1 hour** — the dashboard will not show intraday moves; it reflects the prior day's closing prices until the cache refreshes.

### Reliability Notes
- Yahoo Finance is a free, non-institutional data source. It is generally accurate for ETF and index prices but can occasionally have gaps, split-adjustment errors, or delayed updates.
- For production-grade validation, cross-reference key figures against Bloomberg or FactSet.
- The dashboard displays an "As of [date]" timestamp on every page reflecting when data was last loaded.

---

## 2. Index & ETF Universe

Each instrument in the dashboard is tracked via a publicly traded ETF or index ticker on Yahoo Finance. The mapping is as follows:

| Display Name | Yahoo Finance Symbol | Underlying Benchmark | Notes |
|---|---|---|---|
| BLOOMBERG US AGGREGATE INDEX | AGG | iShares Core US Aggregate Bond ETF | Tracks Bloomberg US Aggregate Bond Index |
| BLOOMBERG US GOVERNMENT INDEX | GOVT | iShares US Treasury Bond ETF | Tracks Bloomberg US Government Bond Index |
| BLOOMBERG US HIGH YIELD | HYG | iShares iBoxx $ High Yield Corporate Bond ETF | Tracks Markit iBoxx USD Liquid High Yield Index |
| BLOOMBERG US HIGH YIELD / LTRSA LEV LOANS | BKLN | Invesco Senior Loan ETF | Tracks the leveraged loan component; ETF proxy for Morningstar LSTA US Leveraged Loan Index |
| BLOOMBERG US TIPS 1-10 YEAR INDEX | STIP | iShares 0-5 Year TIPS Bond ETF | Proxy for short-to-mid duration TIPS; not an exact 1-10yr match |
| CDX (US HY PROXY) | USHY | iShares Broad USD High Yield Corporate Bond ETF | Broader HY proxy than HYG |
| CHINA REAL ESTATE HIGH YIELD | EMLC | VanEck EM Local Currency Bond ETF | Proxy only — not a pure China RE HY instrument |
| EQUITY MARKET NEUTRAL | QAI | IQ Hedge Multi-Strategy Tracker ETF | ETF proxy for equity market neutral strategy |
| EVENT DRIVEN (EW) | MNA | IQ Merger Arbitrage ETF | ETF proxy for event-driven/merger arb strategy |
| IAUM GOLD TRUST MICRO | IAUM | iShares Gold Trust Micro | Direct gold price exposure (fractional share size) |
| ICE BOFA 3-MONTH US T-BILL | BIL | SPDR Bloomberg 1-3 Month T-Bill ETF | Tracks 1-3 month US Treasury Bills |
| ISHARES GOLD TRUST | IAU | iShares Gold Trust | Direct gold price exposure (standard) |
| ITRAXX (US IG PROXY) | IGSB | iShares 1-5 Year Investment Grade Corporate Bond ETF | Proxy for investment grade credit; not a true iTraxx instrument |
| JPM EMBI GLOBAL | EMB | iShares JP Morgan USD Emerging Markets Bond ETF | Tracks the JPMorgan EMBI Global Core Index |
| MSCI AC ASIA PACIFIC | AAXJ | iShares MSCI All Country Asia ex Japan ETF | Excludes Japan |
| MSCI AC WORLD IMI | ACWI | iShares MSCI ACWI ETF | Tracks MSCI All Country World Index |
| MSCI ASIA PACIFIC INDEX | IPAC | iShares Core MSCI Pacific ETF | Includes Japan, Australia, and other Pacific markets |
| MSCI EAFE IMI | IEFA | iShares Core MSCI EAFE ETF | Tracks developed markets ex-US and Canada |
| MSCI EMERGING MARKETS IMI | IEMG | iShares Core MSCI Emerging Markets ETF | Tracks MSCI Emerging Markets Investable Market Index |
| MSCI VALUE - GROWTH | VLUE | iShares MSCI USA Value Factor ETF | Value tilt; not a pure value-minus-growth spread |
| MSCI WORLD | URTH | iShares MSCI World ETF | Tracks MSCI World Index (developed markets only) |
| NASDAQ 100 TR | ^NDX | NASDAQ-100 Index (direct) | Direct index level from Yahoo Finance |
| RUSSELL 2000 INDEX | ^RUT | Russell 2000 Index (direct) | Direct index level from Yahoo Finance |
| RUSSELL 3000 INDEX | IWV | iShares Russell 3000 ETF | Tracks the full Russell 3000 Index |
| S&P 500 ENERGY | XLE | Energy Select Sector SPDR Fund | S&P 500 energy sector only |
| S&P 500 INDEX | ^GSPC | S&P 500 Index (direct) | Direct index level from Yahoo Finance |
| S&P 500 UTILITIES | XLU | Utilities Select Sector SPDR Fund | S&P 500 utilities sector only |
| S&P BIOTECH INDEX | XBI | SPDR S&P Biotech ETF | Tracks the S&P Biotechnology Select Industry Index |
| SPROTT URANIUM MINERS | URNM | Sprott Uranium Miners ETF | Tracks North Shore Global Uranium Mining Index |
| URANIUM PARTICIPATION (U/U CN) | U-UN.TO | Uranium Participation Corp (Toronto) | Physical uranium fund; traded in CAD on TSX |

### Important Proxy Disclaimer
Several instruments on the dashboard are **ETF proxies**, not the exact index. This means:
- The ETF may have a management fee drag (typically 0.03%–0.65% annually) that causes it to slightly underperform the underlying index over time.
- ETF prices reflect market supply/demand and can trade at a small premium or discount to NAV.
- Cambridge Associates Global Private Equity and Cambridge Private Debt indexes were requested but **excluded** — they are private, quarterly-reported benchmarks with no publicly traded equivalent. They cannot be sourced via any real-time market data feed.

---

## 3. Indicator Calculations

### Simple Moving Average (SMA)
- **Formula:** Arithmetic mean of the prior N closing prices.
- **Periods computed:** 50, 100, 200 days.
- **Requires:** N trading days of history before producing a value (e.g., SMA-200 is blank for the first 200 trading days of an instrument's history).
- **Source:** Calculated in-house from Yahoo Finance closing prices using `pandas.Series.rolling(N).mean()`.
- **Reference match:** Identical to Bloomberg, FactSet, and TradingView SMA implementations.

### Exponential Moving Average (EMA)
- **Formula:** Exponentially weighted mean where recent prices receive greater weight. Smoothing factor = 2 / (N + 1).
- **Periods computed:** 50, 100, 200 days.
- **Source:** Calculated using `pandas.Series.ewm(span=N, adjust=False).mean()`.
- **Reference match:** Matches standard EMA as displayed on TradingView and Bloomberg. Note: EMA produces values from day 1 (using all available history), while some platforms only display EMA after N warmup periods — values converge after ~3× the span.

### Relative Strength Index (RSI)
- **Formula:** Wilder's Smoothed RSI — the industry standard used by Bloomberg, TradingView, and most professional platforms.
  - Daily price change: `Δ = Close(t) − Close(t−1)`
  - Average Gain: exponential moving average of positive Δ with `alpha = 1/N`
  - Average Loss: exponential moving average of absolute negative Δ with `alpha = 1/N`
  - RS = Average Gain / Average Loss
  - RSI = 100 − (100 / (1 + RS))
- **Periods computed:** RSI-3, RSI-14, RSI-30.
- **Interpretation:**
  - RSI > 70: Overbought (red in heatmap)
  - RSI 60–70: Elevated (orange)
  - RSI 40–50: Neutral (grey)
  - RSI 30–40: Depressed (light green)
  - RSI < 30: Oversold (green)
- **Source:** Calculated in-house. Validated against the `ta` Python library on live S&P 500 data — mean absolute error of 0.000000 points (exact match).

### Price Return (Insights Page)
- **Formula:** `(Close(today) − Close(N days ago)) / Close(N days ago) × 100`
- **Lookback periods shown:** 1 Week (7 days), 1 Month (30 days), 3 Months (90 days), 1 Year (365 days).
- **Note:** "N days ago" means N calendar days, not N trading days. The last available trading day on or before that calendar date is used.

### % vs SMA (Heatmap & Insights)
- **Formula:** `(Close − SMA) / SMA × 100`
- **Interpretation:** Positive = price is above the moving average; negative = price is below.
- **Heatmap color scale:**
  - > +10%: Red (far extended above SMA — historically mean-reverting)
  - +3% to +10%: Orange
  - −3% to +3%: Grey (neutral)
  - −10% to −3%: Light green
  - < −10%: Green (far below SMA — potential oversold)

---

## 4. Heatmap Lookback Columns

Both the RSI Heatmap and SMA Heatmap show values at historical points in time, not just today.

| Column Label | What It Shows |
|---|---|
| RSI-3 / RSI-14 / RSI-30 | Current RSI at each period |
| W-1 | Value as of 7 calendar days ago |
| W-2 | Value as of 14 calendar days ago |
| W-3 | Value as of 21 calendar days ago |
| M-1 through M-12 | Value as of 30, 60, 90 ... 360 calendar days ago |

For the **RSI Heatmap**, all week/month columns show the **RSI-30** value at that point in time.
For the **SMA Heatmap**, all week/month columns show the **% vs SMA-200** value at that point in time.

---

## 5. Data Refresh & Caching

- Data is fetched from Yahoo Finance **once per hour** and cached.
- On the first load of each session, all 30 tickers are fetched simultaneously. This takes approximately 15–30 seconds.
- Subsequent page navigations within the same session use the cached data instantly.
- The "As of [date]" caption on each page reflects the current calendar date, not the timestamp of the last data fetch. The most recent price available is always the prior trading day's close (Yahoo Finance does not provide real-time intraday data on the free tier).

---

## 6. Automated Data Integrity Tests

A suite of 55 automated tests runs daily at 7:00 AM to verify calculation correctness:

- **SMA** is verified to exactly match `pandas.rolling().mean()` on both synthetic and live S&P 500 data.
- **EMA** is verified to exactly match the `ta` reference library on live S&P 500 data.
- **RSI** is verified to exactly match Wilder's Smoothed RSI (the Bloomberg/TradingView standard) on live S&P 500 data — confirmed zero mean absolute error.
- **Price returns** are verified with a known-answer test (100 → 110 = exactly +10%).
- **Data quality** checks confirm prices are positive, non-zero, non-missing, and that the most recent data is no more than 5 calendar days old.

A popup alert will appear on the workstation if any test fails.

---

## 7. Known Limitations

1. **ETF proxy tracking error** — Most instruments are ETFs, not the underlying index. ETF prices include fee drag and NAV premium/discount.
2. **No intraday data** — All prices are prior-day closing prices. The dashboard is not suitable for intraday monitoring.
3. **Yahoo Finance reliability** — Yahoo Finance is a free data source. Occasional data errors, split-adjustment mistakes, or feed outages are possible. Critical decisions should be cross-referenced against a paid institutional data provider.
4. **Calendar-day lookbacks** — Week and month lookbacks use calendar days (7, 30, 60... days), not trading days. A "1 month" lookback will always land on the nearest available trading day on or before 30 calendar days ago.
5. **Cambridge indexes excluded** — Cambridge Associates Global Private Equity and Cambridge Private Debt are private, quarterly benchmarks. No public market data exists for these indexes and they are not represented in the dashboard.
6. **EMLC proxy** — EMLC (VanEck EM Local Currency Bond ETF) is labeled "China Real Estate High Yield" but is a broad EM local currency bond fund. It is not a precise proxy for China real estate high yield credit.
