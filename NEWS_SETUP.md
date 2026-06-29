# Market & News Data Setup

The dashboard's **Market Snapshot** and **News & Research** panels are populated by
the Streamlit app (`streamlit_portfolio.py`), which fetches data server-side and:

- injects it into the live page, and
- writes a `market_snapshot.js` file so your **local** `portfolio_dashboard.html`
  (double-clicked) shows the last fetched data too.

Everything degrades gracefully — with **no keys at all**, the app still runs and you
already get **free news** from the Federal Reserve and SEC EDGAR (no key required).
Add the two free keys below to light up the rest.

## Sources

| Panel | Source | Key needed? | Get it |
|---|---|---|---|
| Market tiles (S&P 500, 10Y, 2Y, Fed Funds) | **FRED** | Yes (free) | https://fred.stlouisfed.org/docs/api/api_key.html |
| Market news | **Finnhub** | Yes (free tier) | https://finnhub.io/ |
| Policy headlines | **Federal Reserve RSS** | No | — |
| Latest filings | **SEC EDGAR** | No (just a contact UA) | — |

## 1. Install dependencies

```
pip install -r requirements.txt
```

## 2. Add your keys (Streamlit secrets)

Create `.streamlit/secrets.toml` next to the app:

```toml
FRED_API_KEY    = "your_fred_key_here"
FINNHUB_API_KEY = "your_finnhub_key_here"
SEC_USER_AGENT  = "Your Name your.email@wyo.gov"   # SEC requires a contact string
```

> On Streamlit Community Cloud, paste the same keys under **App → Settings → Secrets**
> instead of committing the file. Never commit `secrets.toml` to git.

You can also use environment variables of the same names instead of secrets.

## 3. Run

```
streamlit run streamlit_portfolio.py
```

The panels refresh at most every 15 minutes (cached). To test the fetch alone:

```
python market_data.py
```

## Notes for a public agency (WRS)

- **FRED, Federal Reserve, and SEC EDGAR data are public-domain** — safe to display/share.
- **Finnhub's free tier** is fine for internal use; check their terms before redistributing
  headlines on a fully public page, or drop Finnhub and rely on the Fed/SEC feeds only.
- **Streamlit Community Cloud is public by default.** Host behind authentication (Streamlit
  SSO or your network) before exposing keyed data.
- **Bloomberg (BLPAPI)** can't run on shared cloud — it's tied to your desktop terminal license.
