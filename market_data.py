"""
Market & news data for the WRS Portfolio Dashboard.

Sources:
  • FRED (St. Louis Fed)  -> rates / macro tiles            (free key)
  • Finnhub               -> market news                    (free key)
  • Federal Reserve RSS   -> policy / press headlines        (no key)
  • SEC EDGAR Atom        -> latest filings                  (no key, UA required)

Everything is optional and fault-tolerant: a missing key or a network error
just yields an empty result for that piece, and the dashboard falls back to
placeholders. Nothing here raises to the caller.

Keys live in Streamlit secrets (.streamlit/secrets.toml) or environment vars:
  FRED_API_KEY     -> https://fred.stlouisfed.org/docs/api/api_key.html  (free)
  FINNHUB_API_KEY  -> https://finnhub.io/  (free tier)
  SEC_USER_AGENT   -> "Your Name your.email@wyo.gov"  (SEC requires a contact UA)

See NEWS_SETUP.md for step-by-step setup.
"""
import os
import time
import datetime as dt

import requests

try:
    import feedparser
except Exception:  # feedparser optional; RSS sources simply disabled if missing
    feedparser = None

TIMEOUT = 8  # seconds per request


# ── secrets / config ────────────────────────────────────────────────────────
def _secret(name, default=""):
    """Read from Streamlit secrets if available, else environment, else default."""
    try:
        import streamlit as st
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


FRED_API_KEY = _secret("FRED_API_KEY")
FINNHUB_API_KEY = _secret("FINNHUB_API_KEY")
SEC_USER_AGENT = _secret("SEC_USER_AGENT", "WRS Portfolio Dashboard contact@wyo.gov")


# ── market tiles (FRED) ──────────────────────────────────────────────────────
# (label, FRED series id, is_percent)
FRED_TILES = [
    ("S&P 500",  "SP500", False),
    ("US 10Y",   "DGS10", True),
    ("US 2Y",    "DGS2",  True),
    ("Fed Funds", "DFF",  True),
]


def _fred_latest(series_id):
    """Return (latest, previous_or_None, date_str) of the two most recent
    non-missing observations, or None on failure / no key."""
    if not FRED_API_KEY:
        return None
    r = requests.get(
        "https://api.stlouisfed.org/fred/series/observations",
        params={
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 6,
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    obs = [o for o in r.json().get("observations", []) if o.get("value") not in (".", "", None)]
    if not obs:
        return None
    latest = float(obs[0]["value"])
    prev = float(obs[1]["value"]) if len(obs) > 1 else None
    return latest, prev, obs[0]["date"]


def get_tiles():
    tiles = []
    for label, series, is_pct in FRED_TILES:
        try:
            res = _fred_latest(series)
        except Exception:
            res = None
        if not res:
            tiles.append({"name": label})  # placeholder tile
            continue
        latest, prev, _date = res
        value = f"{latest:.2f}%" if is_pct else f"{latest:,.2f}"
        change = direction = None
        if prev is not None:
            diff = latest - prev
            direction = "up" if diff > 0 else ("down" if diff < 0 else "flat")
            if is_pct:
                change = f"{diff:+.2f} pp"
            else:
                change = f"{(diff / prev * 100):+.2f}%" if prev else None
        tiles.append({"name": label, "value": value, "change": change, "dir": direction})
    return tiles


# ── news ─────────────────────────────────────────────────────────────────────
def _finnhub_news(limit=6):
    if not FINNHUB_API_KEY:
        return []
    r = requests.get(
        "https://finnhub.io/api/v1/news",
        params={"category": "general", "token": FINNHUB_API_KEY},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    out = []
    for a in r.json()[:limit]:
        out.append({
            "tag": "Markets",
            "source": a.get("source") or "Finnhub",
            "title": a.get("headline", ""),
            "url": a.get("url", ""),
            "ts": int(a.get("datetime", 0) or 0),
        })
    return out


def _rss(url, tag, source, limit=3):
    if not feedparser:
        return []
    try:
        resp = requests.get(url, headers={"User-Agent": SEC_USER_AGENT}, timeout=TIMEOUT)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception:
        return []
    out = []
    for e in feed.entries[:limit]:
        ts = 0
        if getattr(e, "published_parsed", None):
            try:
                ts = int(time.mktime(e.published_parsed))
            except Exception:
                ts = 0
        out.append({
            "tag": tag, "source": source,
            "title": e.get("title", ""), "url": e.get("link", ""), "ts": ts,
        })
    return out


def _fmt_ago(ts):
    if not ts:
        return ""
    delta = time.time() - ts
    if delta < 0:
        return ""
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


def get_news(limit=8):
    items = []
    try:
        items += _finnhub_news(6)
    except Exception:
        pass
    items += _rss("https://www.federalreserve.gov/feeds/press_all.xml", "Fed", "Federal Reserve", 3)
    items += _rss(
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&output=atom",
        "SEC", "EDGAR", 3,
    )
    items.sort(key=lambda x: x.get("ts", 0), reverse=True)
    for it in items:
        it["time"] = _fmt_ago(it.get("ts", 0))
        it.pop("ts", None)
    return items[:limit]


# ── top-level ─────────────────────────────────────────────────────────────────
def get_market_data():
    now = dt.datetime.now(dt.timezone.utc)
    return {
        "asOf": now.isoformat(),
        "asOfLabel": now.strftime("%b %d, %Y %H:%M UTC"),
        "tiles": get_tiles(),
        "news": get_news(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(get_market_data(), indent=2))
