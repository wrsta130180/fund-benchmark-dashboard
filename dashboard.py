import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import json, os

# ── Persistent user preferences ───────────────────────────────────────────────
_PREFS_FILE = os.path.join(os.path.dirname(__file__), "user_prefs.json")

def _load_prefs() -> dict:
    try:
        with open(_PREFS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_prefs(prefs: dict):
    try:
        with open(_PREFS_FILE, "w") as f:
            json.dump(prefs, f)
    except Exception:
        pass

_prefs = _load_prefs()

st.set_page_config(page_title="Fund Benchmark Dashboard", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1rem; padding-bottom: 1rem; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background-color: #0f1923;
    border-right: 1px solid #1e2d3d;
}
[data-testid="stSidebar"] * { color: #c9d6df !important; }
[data-testid="stSidebar"] .stRadio label { font-size: 0.95rem; padding: 4px 0; }
[data-testid="stSidebar"] hr { border-color: #1e2d3d; }

/* ── Sidebar title ── */
[data-testid="stSidebar"] h1 {
    font-size: 1.1rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    color: #ffffff !important;
    text-transform: uppercase;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #1e2d3d;
    margin-bottom: 1rem;
}

/* ── Page titles ── */
h1 { font-size: 1.6rem !important; font-weight: 700 !important; color: #0f1923 !important; letter-spacing: 0.02em; }
h2 { font-size: 1.1rem !important; font-weight: 600 !important; color: #1e2d3d !important; }
h3 { font-size: 0.95rem !important; color: #374151 !important; }

/* ── Metric cards ── */
[data-testid="stMetric"] {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 0.75rem 1rem;
}
[data-testid="stMetricLabel"] { font-size: 0.75rem !important; color: #64748b !important; text-transform: uppercase; letter-spacing: 0.05em; }
[data-testid="stMetricValue"] { font-size: 1.3rem !important; font-weight: 700 !important; color: #0f1923 !important; }
[data-testid="stMetricDelta"] { font-size: 0.85rem !important; }

/* ── Tabs ── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 2px;
    background: #f1f5f9;
    border-radius: 8px;
    padding: 3px;
    border: 1px solid #e2e8f0;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    border-radius: 6px;
    font-size: 0.82rem;
    font-weight: 500;
    color: #475569;
    padding: 6px 14px;
}
[data-testid="stTabs"] [aria-selected="true"] {
    background: #ffffff !important;
    color: #0f1923 !important;
    font-weight: 700;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

/* ── Multiselect & selectbox ── */
[data-testid="stMultiSelect"] > div, [data-testid="stSelectbox"] > div {
    border-radius: 6px;
}

/* ── Dividers ── */
hr { border-color: #e2e8f0 !important; margin: 1rem 0 !important; }

/* ── Caption text ── */
[data-testid="stCaptionContainer"] { color: #94a3b8 !important; font-size: 0.78rem !important; }

/* ── Download / action buttons ── */
[data-testid="stDownloadButton"] button, [data-testid="stButton"] button {
    border-radius: 6px !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    border: 1px solid #cbd5e1 !important;
    color: #0f1923 !important;
    background: #ffffff !important;
    padding: 0.35rem 1rem !important;
    transition: background 0.15s;
}
[data-testid="stDownloadButton"] button:hover, [data-testid="stButton"] button:hover {
    background: #f1f5f9 !important;
    border-color: #94a3b8 !important;
}
</style>
""", unsafe_allow_html=True)

# ── Index / ETF universe ──────────────────────────────────────────────────────
# Keys are display tickers shown in the UI. Add or remove entries here to
# expand the dashboard to additional benchmarks.

TICKERS = {
    "AGG US":     {"name": "BLOOMBERG US AGGREGATE INDEX",          "symbol": "AGG"},
    "GOVT US":    {"name": "BLOOMBERG US GOVERNMENT INDEX",         "symbol": "GOVT"},
    "HYG US":     {"name": "BLOOMBERG US HIGH YIELD",               "symbol": "HYG"},
    "BKLN US":    {"name": "BLOOMBERG US HIGH YIELD / LTRSA LEV LOANS", "symbol": "BKLN"},
    "STIP US":    {"name": "BLOOMBERG US TIPS 1-10 YEAR INDEX",     "symbol": "STIP"},
    "USHY US":    {"name": "CDX (US HY PROXY)",                     "symbol": "USHY"},
    "EMLC US":    {"name": "CHINA REAL ESTATE HIGH YIELD",          "symbol": "EMLC"},
    "QAI US":     {"name": "EQUITY MARKET NEUTRAL",                 "symbol": "QAI"},
    "MNA US":     {"name": "EVENT DRIVEN (EW)",                     "symbol": "MNA"},
    "IAUM US":    {"name": "IAUM GOLD TRUST MICRO",                 "symbol": "IAUM"},
    "BIL US":     {"name": "ICE BOFA 3-MONTH US T-BILL",            "symbol": "BIL"},
    "IAU US":     {"name": "ISHARES GOLD TRUST",                    "symbol": "IAU"},
    "IGSB US":    {"name": "ITRAXX (US IG PROXY)",                  "symbol": "IGSB"},
    "EMB US":     {"name": "JPM EMBI GLOBAL",                       "symbol": "EMB"},
    "AAXJ US":    {"name": "MSCI AC ASIA PACIFIC",                  "symbol": "AAXJ"},
    "ACWI US":    {"name": "MSCI AC WORLD IMI",                     "symbol": "ACWI"},
    "IPAC US":    {"name": "MSCI ASIA PACIFIC INDEX",               "symbol": "IPAC"},
    "IEFA US":    {"name": "MSCI EAFE IMI",                         "symbol": "IEFA"},
    "IEMG US":    {"name": "MSCI EMERGING MARKETS IMI",             "symbol": "IEMG"},
    "VLUE US":    {"name": "MSCI VALUE - GROWTH",                   "symbol": "VLUE"},
    "URTH US":    {"name": "MSCI WORLD",                            "symbol": "URTH"},
    "NDX Index":  {"name": "NASDAQ 100 TR",                         "symbol": "^NDX"},
    "RTY Index":  {"name": "RUSSELL 2000 INDEX",                    "symbol": "^RUT"},
    "IWV US":     {"name": "RUSSELL 3000 INDEX",                    "symbol": "IWV"},
    "XLE US":     {"name": "S&P 500 ENERGY",                        "symbol": "XLE"},
    "SPX Index":  {"name": "S&P 500 INDEX",                         "symbol": "^GSPC"},
    "XLU US":     {"name": "S&P 500 UTILITIES",                     "symbol": "XLU"},
    "XBI US":     {"name": "S&P BIOTECH INDEX",                     "symbol": "XBI"},
    "URNM US":    {"name": "SPROTT URANIUM MINERS",                 "symbol": "URNM"},
    "U-UN.TO":    {"name": "URANIUM PARTICIPATION (U/U CN)",        "symbol": "U-UN.TO"},
}

# Lookback offsets used by both heatmaps
WEEK_OFFSETS  = [7, 14, 21]
MONTH_OFFSETS = [30 * i for i in range(1, 13)]

# ── Data loading & indicator calculation ─────────────────────────────────────

FULL_FETCH_START = datetime(1950, 1, 1)


@st.cache_data(ttl=3600)
def load_data(symbol: str, start: datetime) -> pd.DataFrame:
    end = datetime.today()
    df = yf.download(symbol, start=start, end=end, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[["Close", "Volume"]].dropna().rename_axis("Date")


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    for n in [50, 100, 200]:
        d[f"SMA{n}"] = d["Close"].rolling(n).mean()
        d[f"EMA{n}"] = d["Close"].ewm(span=n, adjust=False).mean()
    for period in [3, 14, 30]:
        delta = d["Close"].diff()
        # Wilder's Smoothed RSI — matches Bloomberg, TradingView, and most platforms
        gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        d[f"RSI{period}"] = 100 - (100 / (1 + rs))
    return d


@st.cache_data(ttl=3600)
def load_all_tickers(ticker_keys: tuple) -> dict:
    result = {}
    for label in ticker_keys:
        raw = load_data(TICKERS[label]["symbol"], FULL_FETCH_START)
        result[label] = compute_indicators(raw)
    return result

# ── Indicator helpers ─────────────────────────────────────────────────────────

def val_at_offset(df: pd.DataFrame, offset_days: int, col: str):
    sub = df[df.index <= df.index[-1] - timedelta(days=offset_days)]
    return sub.iloc[-1][col] if not sub.empty else np.nan


def sma_pct_at_offset(df: pd.DataFrame, offset_days: int, sma_col: str):
    sub = df[df.index <= df.index[-1] - timedelta(days=offset_days)]
    if sub.empty:
        return np.nan
    r = sub.iloc[-1]
    sma = r[sma_col]
    return (r["Close"] - sma) / sma * 100 if not pd.isna(sma) and sma != 0 else np.nan

# ── Color scales ──────────────────────────────────────────────────────────────

def rsi_color(val) -> str:
    if pd.isna(val):   return "#f3f4f6"
    if val >= 70:      return "#c0392b"
    if val >= 60:      return "#e67e22"
    if val <= 30:      return "#27ae60"
    if val <= 40:      return "#2ecc71"
    return "#d1d5db"


def sma_color(pct) -> str:
    if pd.isna(pct):   return "#f3f4f6"
    if pct >= 10:      return "#c0392b"
    if pct >= 3:       return "#e67e22"
    if pct <= -10:     return "#27ae60"
    if pct <= -3:      return "#2ecc71"
    return "#d1d5db"


def cell_text_color(bg: str) -> str:
    return "#111111" if bg in ("#d1d5db", "#f3f4f6") else "#ffffff"


def fmt_rsi(v) -> str:
    return f"{v:.0f}" if not pd.isna(v) else "—"


def fmt_pct(v) -> str:
    return f"{v:+.1f}%" if not pd.isna(v) else "—"

# ── Chart Grid figure builder ─────────────────────────────────────────────────

def build_grid_fig(ticker_labels: list, all_dfs: dict, period_days) -> go.Figure:
    n      = len(ticker_labels)
    n_cols = min(3, n)
    n_rows = (n + n_cols - 1) // n_cols
    sma_colors = {"SMA50": "#f39c12", "SMA100": "#9b59b6", "SMA200": "#e74c3c"}
    ema_colors = {"EMA50": "#00bcd4", "EMA100": "#c9a800", "EMA200": "#e91e8c"}

    fig = make_subplots(
        rows=n_rows, cols=n_cols,
        subplot_titles=[TICKERS[l]["name"] for l in ticker_labels],
        vertical_spacing=0.08, horizontal_spacing=0.06,
    )
    for i, label in enumerate(ticker_labels):
        r, c   = divmod(i, n_cols)
        df     = all_dfs[label]
        cutoff = df.index[0] if period_days is None else datetime.today() - timedelta(days=period_days)
        view   = df[df.index >= cutoff]
        show   = (i == 0)  # only first subplot contributes legend entries
        fig.add_trace(go.Scatter(x=view.index, y=view["Close"], name="Price",
                                 line=dict(color="#3498db", width=1),
                                 legendgroup="Price", showlegend=show),
                      row=r+1, col=c+1)
        for s, color in sma_colors.items():
            fig.add_trace(go.Scatter(x=view.index, y=view[s], name=s,
                                     line=dict(color=color, width=0.8, dash="dot"),
                                     legendgroup=s, showlegend=show),
                          row=r+1, col=c+1)
        for e, color in ema_colors.items():
            fig.add_trace(go.Scatter(x=view.index, y=view[e], name=e,
                                     line=dict(color=color, width=0.8, dash="dash"),
                                     legendgroup=e, showlegend=show),
                          row=r+1, col=c+1)
    fig.update_layout(
        template="plotly_white", paper_bgcolor="white", plot_bgcolor="white",
        height=350 * n_rows, margin=dict(t=60, b=40, l=40, r=120),
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.01,
                    bgcolor="white", bordercolor="#dddddd", borderwidth=1),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#dddddd")
    return fig

# ── Heatmap Plotly Table builders ─────────────────────────────────────────────

def _build_heatmap_fig(ticker_data: dict, col_headers: list, row_builder, title: str = "") -> go.Figure:
    all_col_headers = ["#"] + col_headers
    cell_vals   = [[] for _ in all_col_headers]
    cell_colors = [[] for _ in all_col_headers]
    for row_num, (ticker_label, meta) in enumerate(ticker_data.items(), start=1):
        vals, colors = row_builder(ticker_label, meta)
        cell_vals[0].append(str(row_num));  cell_colors[0].append("#f8fafc")
        for i, (v, c) in enumerate(zip(vals, colors)):
            cell_vals[i + 1].append(v)
            cell_colors[i + 1].append(c)
    n_data  = len(ticker_data)
    align   = ["center", "left", "left"] + ["center"] * (len(col_headers) - 2)
    row_h   = 26
    hdr_h   = 34
    title_h = 44 if title else 0
    height  = title_h + hdr_h + row_h * n_data + 24
    fig = go.Figure(go.Table(
        columnwidth=[28, 80, 200] + [55] * (len(col_headers) - 2),
        header=dict(values=all_col_headers, fill_color="#dce6f1",
                    font=dict(color="#1e293b", size=13, family="Arial"),
                    align=align, height=hdr_h),
        cells=dict(values=cell_vals, fill_color=cell_colors,
                   font=dict(color="#111111", size=11),
                   align=align, height=row_h),
    ))
    fig.update_layout(
        paper_bgcolor="white",
        title=dict(text=title, font=dict(size=15, color="#0f1923", family="Arial"),
                   x=0, xanchor="left", pad=dict(b=4)) if title else {},
        margin=dict(t=title_h + 8 if title else 8, b=8, l=10, r=10),
        height=height,
    )
    return fig


def build_rsi_heatmap_fig(ticker_data: dict) -> go.Figure:
    col_headers = (
        ["Ticker", "Index", "RSI-3", "RSI-14", "RSI-30"] +
        [f"W-{i}" for i in range(1, 4)] +
        [f"M-{i}" for i in range(1, 13)]
    )
    def row_builder(ticker_label, meta):
        df   = meta["df"]
        vals = [ticker_label, meta["name"]]
        cols = ["#f8fafc", "#f8fafc"]
        for col in ["RSI3", "RSI14", "RSI30"]:
            v = val_at_offset(df, 0, col)
            vals.append(fmt_rsi(v)); cols.append(rsi_color(v))
        for offset in WEEK_OFFSETS:
            v = val_at_offset(df, offset, "RSI30")
            vals.append(fmt_rsi(v)); cols.append(rsi_color(v))
        for offset in MONTH_OFFSETS:
            v = val_at_offset(df, offset, "RSI30")
            vals.append(fmt_rsi(v)); cols.append(rsi_color(v))
        return vals, cols
    return _build_heatmap_fig(ticker_data, col_headers, row_builder,
                               title="Relative Strength Index Heatmap")


def build_sma_heatmap_fig(ticker_data: dict) -> go.Figure:
    col_headers = (
        ["Ticker", "Index", "SMA-50", "SMA-100", "SMA-200"] +
        [f"W-{i}" for i in range(1, 4)] +
        [f"M-{i}" for i in range(1, 13)]
    )
    def row_builder(ticker_label, meta):
        df   = meta["df"]
        vals = [ticker_label, meta["name"]]
        cols = ["#f8fafc", "#f8fafc"]
        for col in ["SMA50", "SMA100", "SMA200"]:
            v = sma_pct_at_offset(df, 0, col)
            vals.append(fmt_pct(v)); cols.append(sma_color(v))
        for offset in WEEK_OFFSETS:
            v = sma_pct_at_offset(df, offset, "SMA200")
            vals.append(fmt_pct(v)); cols.append(sma_color(v))
        for offset in MONTH_OFFSETS:
            v = sma_pct_at_offset(df, offset, "SMA200")
            vals.append(fmt_pct(v)); cols.append(sma_color(v))
        return vals, cols
    return _build_heatmap_fig(ticker_data, col_headers, row_builder,
                               title="Simple Moving Average Heatmap")

# ── App layout ────────────────────────────────────────────────────────────────

st.sidebar.markdown("## Fund Benchmark\nDashboard")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigation", ["Price Chart", "Chart Grid", "RSI Heatmap", "SMA Heatmap", "Insights"])
st.sidebar.markdown("---")
st.sidebar.caption(f"Data refreshed hourly  \nAs of {datetime.today().strftime('%B %d, %Y')}")

all_dfs = load_all_tickers(tuple(TICKERS.keys()))
ticker_data = {label: {"name": TICKERS[label]["name"], "df": all_dfs[label]} for label in TICKERS}

PERIOD_OPTIONS = {
    "1 Month":  30,
    "3 Months": 90,
    "1 Year":   365,
    "3 Years":  1095,
    "5 Years":  1825,
    "10 Years": 3650,
    "ITD":      None,
}
SNAPSHOT_CONFIG = lambda filename: {"toImageButtonOptions": {"format": "png", "filename": filename}}
DATE_STAMP = datetime.today().strftime("%Y-%m")

# ── PAGE: Price Chart ─────────────────────────────────────────────────────────

if page == "Price Chart":
    st.markdown(f"<p style='color:#94a3b8;font-size:0.78rem;margin-bottom:0.2rem;'>As of {datetime.today().strftime('%B %d, %Y')}</p>", unsafe_allow_html=True)
    st.title("Price & Indicators")

    all_labels    = list(TICKERS.keys())
    all_names     = [TICKERS[l]["name"] for l in all_labels]
    name_to_label = {TICKERS[l]["name"]: l for l in all_labels}

    valid_names = set(all_names)
    default_two = [TICKERS[l]["name"] for l in all_labels[:2]]

    if "chart_ms_store" not in st.session_state:
        saved = [n for n in _prefs.get("selected_indexes", default_two) if n in valid_names]
        st.session_state["chart_ms_store"] = saved or default_two
    else:
        st.session_state["chart_ms_store"] = [n for n in st.session_state["chart_ms_store"] if n in valid_names] or default_two

    if "chart_ms" not in st.session_state:
        st.session_state["chart_ms"] = st.session_state["chart_ms_store"]

    left_col, right_col = st.columns([3, 1])
    with left_col:
        selected_names = st.multiselect("Indexes / ETFs", options=all_names, key="chart_ms")
    with right_col:
        period_options = list(PERIOD_OPTIONS.keys()) + ["Custom Range"]
        if "shared_period_store" not in st.session_state:
            st.session_state["shared_period_store"] = _prefs.get("time_period", period_options[3])
        if "chart_period" not in st.session_state:
            st.session_state["chart_period"] = st.session_state["shared_period_store"]
        period_choice = st.selectbox("Time Period", period_options, key="chart_period")
        st.session_state["shared_period_store"] = st.session_state["chart_period"]

    # write selection back to store and persist to disk
    st.session_state["chart_ms_store"] = st.session_state["chart_ms"]
    _new_prefs = {"selected_indexes": st.session_state["chart_ms_store"],
                  "time_period":      st.session_state["shared_period_store"]}
    if _new_prefs != _prefs:
        _save_prefs(_new_prefs)
        _prefs.update(_new_prefs)
    selected_labels = [name_to_label[n] for n in selected_names]
    st.session_state.chart_indexes = selected_labels

    if period_choice == "Custom Range":
        today     = datetime.today().date()
        inception = min(all_dfs[l].index[0].date() for l in all_labels if l in all_dfs and len(all_dfs[l]) > 0)
        c1, c2   = st.columns(2)
        with c1:
            custom_start = st.date_input("Start Date", value=today.replace(year=today.year - 1),
                                         min_value=inception, max_value=today, key="chart_custom_start")
        with c2:
            custom_end = st.date_input("End Date", value=today,
                                       min_value=inception, max_value=today, key="chart_custom_end")
        period_days  = None
        custom_range = (datetime.combine(custom_start, datetime.min.time()),
                        datetime.combine(custom_end,   datetime.max.time()))
    else:
        period_days  = PERIOD_OPTIONS[period_choice]
        custom_range = None

    if not selected_labels:
        st.info("Select at least one index above to display a chart.")
        st.stop()

    sma_colors = {"SMA50": "#f39c12", "SMA100": "#9b59b6", "SMA200": "#e74c3c"}
    ema_colors = {"EMA50": "#00bcd4", "EMA100": "#c9a800", "EMA200": "#e91e8c"}

    for tab, ticker_label in zip(st.tabs([TICKERS[l]["name"] for l in selected_labels]), selected_labels):
        with tab:
            meta   = TICKERS[ticker_label]
            df     = all_dfs[ticker_label]
            if custom_range:
                view = df[(df.index >= custom_range[0]) & (df.index <= custom_range[1])].copy()
            elif period_days is None:
                view = df.copy()
            else:
                view = df[df.index >= datetime.today() - timedelta(days=period_days)].copy()

            fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                row_heights=[0.75, 0.25], vertical_spacing=0.03)
            fig.add_trace(go.Scatter(x=view.index, y=view["Close"], name="Price",
                                     line=dict(color="#3498db", width=1.5)), row=1, col=1)
            for s, color in sma_colors.items():
                fig.add_trace(go.Scatter(x=view.index, y=view[s], name=s,
                                         line=dict(color=color, width=1, dash="dot")), row=1, col=1)
            for e, color in ema_colors.items():
                fig.add_trace(go.Scatter(x=view.index, y=view[e], name=e,
                                         line=dict(color=color, width=1, dash="dash")), row=1, col=1)

            bar_colors = ["#e74c3c" if view["Close"].iloc[i] < view["Close"].iloc[i - 1]
                          else "#2ecc71" for i in range(len(view))]
            fig.add_trace(go.Bar(x=view.index, y=view["Volume"], name="Volume",
                                 marker_color=bar_colors, opacity=0.6), row=2, col=1)
            fig.update_layout(
                template="plotly_dark", height=650,
                title=dict(text=meta["name"], x=0.5, xanchor="center", font=dict(size=16)),
                legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.01),
                margin=dict(t=60, b=20),
                xaxis2_title="Date", yaxis_title="Price", yaxis2_title="Volume",
                hovermode="x unified",
            )
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(showgrid=True, gridcolor="#333")
            st.plotly_chart(fig, width="stretch", key=f"chart_{ticker_label}",
                            config=SNAPSHOT_CONFIG(f"{meta['name'].replace(' ', '_')}_{DATE_STAMP}"))

            c1, c2, c3 = st.columns(3)
            latest = view.iloc[-1]
            prev   = view.iloc[-2]
            chg    = (latest["Close"] - prev["Close"]) / prev["Close"] * 100
            c1.metric("Last Close",   f"${latest['Close']:,.2f}", f"{chg:+.2f}%")
            c2.metric("50-day SMA",   f"${latest['SMA50']:,.2f}"  if not pd.isna(latest["SMA50"])  else "—")
            c3.metric("200-day SMA",  f"${latest['SMA200']:,.2f}" if not pd.isna(latest["SMA200"]) else "—")

# ── PAGE: Chart Grid ──────────────────────────────────────────────────────────

elif page == "Chart Grid":
    st.markdown(f"<p style='color:#94a3b8;font-size:0.78rem;margin-bottom:0.2rem;'>As of {datetime.today().strftime('%B %d, %Y')}</p>", unsafe_allow_html=True)
    st.title("Chart Grid")

    all_labels    = list(TICKERS.keys())
    all_names     = [TICKERS[l]["name"] for l in all_labels]
    name_to_label = {TICKERS[l]["name"]: l for l in all_labels}

    if "grid_ms" not in st.session_state:
        fallback = st.session_state.get("chart_indexes", all_labels[:2])
        st.session_state["grid_ms"] = [TICKERS[l]["name"] for l in fallback][:9]

    left_col, right_col = st.columns([3, 1])
    with left_col:
        grid_names = st.multiselect("Select up to 9 Indexes", options=all_names,
                                    key="grid_ms", max_selections=9)
    with right_col:
        period_options = list(PERIOD_OPTIONS.keys()) + ["Custom Range"]
        if "shared_period_store" not in st.session_state:
            st.session_state["shared_period_store"] = _prefs.get("time_period", period_options[3])
        if "grid_period" not in st.session_state:
            st.session_state["grid_period"] = st.session_state["shared_period_store"]
        grid_period_choice = st.selectbox("Time Period", period_options, key="grid_period")
        st.session_state["shared_period_store"] = st.session_state["grid_period"]
        _new_prefs = {**_prefs, "time_period": st.session_state["shared_period_store"]}
        if _new_prefs != _prefs:
            _save_prefs(_new_prefs)
            _prefs.update(_new_prefs)

    if not grid_names:
        st.info("Select at least one index above.")
        st.stop()

    grid_labels = [name_to_label[n] for n in grid_names]

    if grid_period_choice == "Custom Range":
        today = datetime.today().date()
        inception_grid = min(all_dfs[l].index[0].date() for l in grid_labels if l in all_dfs and len(all_dfs[l]) > 0)
        gc1, gc2 = st.columns(2)
        with gc1:
            grid_custom_start = st.date_input("Start Date", value=today.replace(year=today.year - 1),
                                              min_value=inception_grid, max_value=today, key="grid_custom_start")
        with gc2:
            grid_custom_end = st.date_input("End Date", value=today,
                                            min_value=inception_grid, max_value=today, key="grid_custom_end")
        grid_period_days  = None
        grid_custom_range = (datetime.combine(grid_custom_start, datetime.min.time()),
                             datetime.combine(grid_custom_end,   datetime.max.time()))
    else:
        grid_period_days  = PERIOD_OPTIONS[grid_period_choice]
        grid_custom_range = None

    st.plotly_chart(build_grid_fig(grid_labels, all_dfs, grid_period_days),
                    width="stretch", key="grid_combined",
                    config=SNAPSHOT_CONFIG(f"Chart_Grid_{DATE_STAMP}"))

# ── PAGE: RSI Heatmap ─────────────────────────────────────────────────────────

elif page == "RSI Heatmap":
    _fig = build_rsi_heatmap_fig(ticker_data)
    st.plotly_chart(_fig, use_container_width=True, key="rsi_heatmap",
                    height=_fig.layout.height,
                    config=SNAPSHOT_CONFIG(f"RSI_Heatmap_{DATE_STAMP}"))

# ── PAGE: SMA Heatmap ─────────────────────────────────────────────────────────

elif page == "SMA Heatmap":
    _fig = build_sma_heatmap_fig(ticker_data)
    st.plotly_chart(_fig, use_container_width=True, key="sma_heatmap",
                    height=_fig.layout.height,
                    config=SNAPSHOT_CONFIG(f"SMA_Heatmap_{DATE_STAMP}"))

# ── PAGE: Insights ────────────────────────────────────────────────────────────

elif page == "Insights":
    today_str = datetime.today().strftime("%B %d, %Y")

    # ── helpers ──────────────────────────────────────────────────────────────
    def price_return(df, offset_days):
        """% return from offset_days ago to today."""
        sub = df[df.index <= df.index[-1] - timedelta(days=offset_days)]
        if sub.empty or pd.isna(df["Close"].iloc[-1]):
            return np.nan
        past = sub.iloc[-1]["Close"]
        return (df["Close"].iloc[-1] - past) / past * 100 if past and past != 0 else np.nan

    def trend_label(pct_vs_sma200):
        if pd.isna(pct_vs_sma200): return "—", "#f3f4f6"
        if pct_vs_sma200 >= 5:     return "Strong ▲", "#c0392b"
        if pct_vs_sma200 >= 0:     return "Above ▲",  "#e67e22"
        if pct_vs_sma200 >= -5:    return "Below ▼",  "#2ecc71"
        return "Weak ▼", "#27ae60"

    def rsi_label(rsi14):
        if pd.isna(rsi14): return "—", "#f3f4f6"
        if rsi14 >= 70:    return "Overbought", "#c0392b"
        if rsi14 >= 60:    return "Elevated",   "#e67e22"
        if rsi14 <= 30:    return "Oversold",   "#27ae60"
        if rsi14 <= 40:    return "Depressed",  "#2ecc71"
        return "Neutral", "#d1d5db"

    def ret_color(pct):
        if pd.isna(pct): return "#f3f4f6"
        if pct >=  5:    return "#c0392b"
        if pct >=  1:    return "#e67e22"
        if pct <= -5:    return "#27ae60"
        if pct <= -1:    return "#2ecc71"
        return "#d1d5db"

    def sma_cross_label(df):
        """How many of SMA50/100/200 is price currently above? Returns (n, color)."""
        row = df.iloc[-1]
        n = sum(1 for s in ["SMA50", "SMA100", "SMA200"]
                if not pd.isna(row.get(s)) and row["Close"] > row[s])
        colors = {0: "#27ae60", 1: "#2ecc71", 2: "#e67e22", 3: "#c0392b"}
        return f"{n}/3", colors[n]

    # ── build rows ───────────────────────────────────────────────────────────
    rows = []
    for label, meta in ticker_data.items():
        df = meta["df"]
        if df.empty:
            continue
        r1w  = price_return(df, 7)
        r1m  = price_return(df, 30)
        r3m  = price_return(df, 90)
        r1y  = price_return(df, 365)
        rsi3  = val_at_offset(df, 0, "RSI3")
        rsi14 = val_at_offset(df, 0, "RSI14")
        vs200 = sma_pct_at_offset(df, 0, "SMA200")
        rows.append({
            "label": label,
            "name":  meta["name"],
            "r1w":   r1w,  "r1m": r1m, "r3m": r3m, "r1y": r1y,
            "rsi3":  rsi3, "rsi14": rsi14, "vs200": vs200,
        })

    # ── SECTION 1: Signal Overview table ─────────────────────────────────────
    col_hdrs = ["#", "Ticker", "Index", "1W Ret", "1M Ret", "3M Ret", "1Y Ret",
                "RSI-3", "RSI-14", "vs SMA-200", "Above SMAs"]
    n = len(rows)
    cell_vals   = [[] for _ in col_hdrs]
    cell_colors = [[] for _ in col_hdrs]

    for i, r in enumerate(rows, 1):
        tl, tc  = trend_label(r["vs200"])
        df      = ticker_data[r["label"]]["df"]
        row = df.iloc[-1]
        n_above = sum(1 for s in ["SMA50","SMA100","SMA200"]
                      if not pd.isna(row.get(s, np.nan)) and row["Close"] > row[s])
        cross_colors = {0: "#27ae60", 1: "#2ecc71", 2: "#e67e22", 3: "#c0392b"}

        cell_vals[0].append(str(i));          cell_colors[0].append("#f8fafc")
        cell_vals[1].append(r["label"]);      cell_colors[1].append("#f8fafc")
        cell_vals[2].append(r["name"]);       cell_colors[2].append("#f8fafc")
        cell_vals[3].append(fmt_pct(r["r1w"]));  cell_colors[3].append(ret_color(r["r1w"]))
        cell_vals[4].append(fmt_pct(r["r1m"]));  cell_colors[4].append(ret_color(r["r1m"]))
        cell_vals[5].append(fmt_pct(r["r3m"]));  cell_colors[5].append(ret_color(r["r3m"]))
        cell_vals[6].append(fmt_pct(r["r1y"]));  cell_colors[6].append(ret_color(r["r1y"]))
        cell_vals[7].append(fmt_rsi(r["rsi3"])); cell_colors[7].append(rsi_color(r["rsi3"]))
        cell_vals[8].append(fmt_rsi(r["rsi14"]));cell_colors[8].append(rsi_color(r["rsi14"]))
        cell_vals[9].append(fmt_pct(r["vs200"]) + f"  {tl}"); cell_colors[9].append(tc)
        cell_vals[10].append(f"{n_above}/3"); cell_colors[10].append(cross_colors[n_above])

    align_sig = ["center","left","left"] + ["center"]*8
    row_h = 26; hdr_h = 34; title_h = 44
    sig_height = title_h + hdr_h + row_h * n + 24

    fig_sig = go.Figure(go.Table(
        columnwidth=[28, 70, 190, 55, 55, 55, 55, 50, 50, 95, 65],
        header=dict(values=col_hdrs, fill_color="#dce6f1",
                    font=dict(color="#1e293b", size=13, family="Arial"),
                    align=align_sig, height=hdr_h),
        cells=dict(values=cell_vals, fill_color=cell_colors,
                   font=dict(color="#111111", size=11),
                   align=align_sig, height=row_h),
    ))
    fig_sig.update_layout(
        paper_bgcolor="white",
        title=dict(text=f"Signal Overview  —  As of {today_str}",
                   font=dict(size=15, color="#0f1923", family="Arial"),
                   x=0, xanchor="left", pad=dict(b=4)),
        margin=dict(t=title_h + 8, b=8, l=10, r=10),
        height=sig_height,
    )
    st.plotly_chart(fig_sig, use_container_width=True, key="insights_sig",
                    height=sig_height,
                    config=SNAPSHOT_CONFIG(f"Signal_Overview_{DATE_STAMP}"))

    st.markdown("---")

    # ── SECTION 2: Top & Bottom Movers ───────────────────────────────────────
    left_col, right_col = st.columns(2)

    for period_label, field, col_obj in [("1-Month Movers", "r1m", left_col),
                                          ("1-Year Movers",  "r1y", right_col)]:
        valid = sorted([r for r in rows if not pd.isna(r[field])],
                       key=lambda r: r[field], reverse=True)
        top5 = valid[:5]
        bot5 = list(reversed(valid[-5:]))

        names  = [r["name"] for r in top5] + [""] + [r["name"] for r in bot5]
        values = [r[field]  for r in top5] + [0]  + [r[field]  for r in bot5]
        colors_bar = ["#c0392b" if v > 0 else "#27ae60" for v in values]
        colors_bar[5] = "rgba(0,0,0,0)"  # spacer

        fig_bar = go.Figure(go.Bar(
            x=values, y=names, orientation="h",
            marker_color=colors_bar,
            text=[f"{v:+.1f}%" if v != 0 else "" for v in values],
            textposition="outside",
        ))
        fig_bar.update_layout(
            title=dict(text=f"Top & Bottom 5  —  {period_label}",
                       font=dict(size=14, color="#0f1923"), x=0, xanchor="left"),
            paper_bgcolor="white", plot_bgcolor="white",
            height=380, margin=dict(t=50, b=20, l=10, r=60),
            xaxis=dict(showgrid=True, gridcolor="#e2e8f0", zeroline=True,
                       zerolinecolor="#94a3b8", ticksuffix="%"),
            yaxis=dict(autorange="reversed"),
            font=dict(size=11),
        )
        with col_obj:
            st.plotly_chart(fig_bar, use_container_width=True,
                            key=f"movers_{field}",
                            config=SNAPSHOT_CONFIG(f"Movers_{field}_{DATE_STAMP}"))

    st.markdown("---")

    # ── SECTION 3: RSI Alert Conditions ──────────────────────────────────────
    overbought = [r for r in rows if not pd.isna(r["rsi14"]) and r["rsi14"] >= 70]
    oversold   = [r for r in rows if not pd.isna(r["rsi14"]) and r["rsi14"] <= 30]
    diverging  = [r for r in rows
                  if not pd.isna(r["rsi14"]) and not pd.isna(r["r1m"])
                  and ((r["rsi14"] >= 60 and r["r1m"] < 0) or
                       (r["rsi14"] <= 40 and r["r1m"] > 0))]

    al, bl, cl = st.columns(3)
    for title_a, items, col_a, bg in [
        ("Overbought  (RSI-14 ≥ 70)",  overbought, al, "#fdecea"),
        ("Oversold  (RSI-14 ≤ 30)",    oversold,   bl, "#eafaf1"),
        ("Momentum Divergence",         diverging,  cl, "#fef9e7"),
    ]:
        with col_a:
            st.markdown(f"<p style='font-weight:700;font-size:0.9rem;margin-bottom:0.3rem;'>{title_a}</p>",
                        unsafe_allow_html=True)
            if not items:
                st.markdown("<p style='color:#94a3b8;font-size:0.85rem;'>None currently</p>",
                            unsafe_allow_html=True)
            else:
                for r in items:
                    rsi_val = f"{r['rsi14']:.0f}"
                    ret_val = fmt_pct(r["r1m"])
                    st.markdown(
                        f"<div style='background:{bg};border-radius:6px;padding:6px 10px;"
                        f"margin-bottom:4px;font-size:0.82rem;'>"
                        f"<b>{r['name']}</b><br/>"
                        f"<span style='color:#555;'>RSI-14: {rsi_val} &nbsp;|&nbsp; 1M: {ret_val}</span>"
                        f"</div>",
                        unsafe_allow_html=True)
