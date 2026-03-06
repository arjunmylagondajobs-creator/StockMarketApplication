"""
Stock Scanner Module
Uses batch downloading for speed. Scans popular stocks and returns top picks.
"""

import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from analysis.technical import run_technical_analysis
from analysis.fundamental import run_fundamental_analysis
from analysis.recommendation import compute_recommendation


# Curated universe — kept lean for speed
STOCK_UNIVERSE = {
    "us": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
        "JPM", "V", "HD", "MA", "NFLX", "CRM", "AMD",
        "AVGO", "COST", "ABBV", "MRK", "ADBE", "ORCL"
    ],
    "india": [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
        "BHARTIARTL.NS", "ITC.NS", "SBIN.NS", "LT.NS", "HCLTECH.NS",
        "WIPRO.NS", "TATAMOTORS.NS", "BAJFINANCE.NS", "MARUTI.NS",
        "SUNPHARMA.NS", "TITAN.NS", "TATASTEEL.NS", "POWERGRID.NS",
        "NTPC.NS", "ADANIENT.NS"
    ]
}


def _quick_analyze(symbol, hist_data):
    """Quick-score a single stock using pre-fetched history."""
    try:
        if hist_data is None or hist_data.empty or len(hist_data) < 20:
            return None

        ticker = yf.Ticker(symbol)
        try:
            info = ticker.info
        except Exception:
            info = {}

        company_name = info.get("longName") or info.get("shortName") or symbol
        current_price = round(float(hist_data["Close"].iloc[-1]), 2)

        prev_close = None
        daily_change = None
        daily_change_pct = None
        if len(hist_data) >= 2:
            prev_close = round(float(hist_data["Close"].iloc[-2]), 2)
            daily_change = round(current_price - prev_close, 2)
            daily_change_pct = round((daily_change / prev_close) * 100, 2)

        # Run analysis
        technical = run_technical_analysis(hist_data.copy())
        fundamental = run_fundamental_analysis(info)

        recommendation = compute_recommendation(
            technical["score"],
            fundamental["score"],
            50  # neutral sentiment — skip for speed
        )

        return {
            "ticker": symbol,
            "companyName": company_name,
            "currentPrice": current_price,
            "dailyChange": daily_change,
            "dailyChangePct": daily_change_pct,
            "currency": info.get("currency", "USD"),
            "technicalScore": technical["score"],
            "fundamentalScore": fundamental["score"],
            "finalScore": recommendation["final_score"],
            "verdict": recommendation["verdict"],
            "color": recommendation["color"],
            "sector": info.get("sector", "N/A"),
            "rsiSignal": technical.get("rsi", {}).get("signal", "N/A"),
            "macdTrend": technical.get("macd", {}).get("trend", "N/A"),
            "keySignals": _extract_signals(technical, fundamental),
        }
    except Exception:
        return None


def _extract_signals(technical, fundamental):
    """Extract top 3 key signals for display."""
    signals = []
    rsi = technical.get("rsi", {})
    if rsi.get("signal") and rsi["signal"] != "N/A":
        signals.append(f"RSI: {rsi['signal']}")
    macd = technical.get("macd", {})
    if macd.get("trend") and macd["trend"] != "N/A":
        signals.append(f"MACD: {macd['trend']}")
    for s in fundamental.get("signals", [])[:2]:
        signals.append(s)
    return signals[:3]


def scan_top_picks(market="all", top_n=5):
    """
    Scan stocks and return top N picks.
    Uses yf.download() for fast batch price fetching, then threads for info.
    """
    # Determine tickers
    if market == "us":
        tickers = STOCK_UNIVERSE["us"]
    elif market == "india":
        tickers = STOCK_UNIVERSE["india"]
    else:
        tickers = STOCK_UNIVERSE["us"] + STOCK_UNIVERSE["india"]

    # BATCH download all price history at once — this is the big speed win
    print(f"[Scanner] Batch downloading {len(tickers)} stocks...")
    all_data = yf.download(tickers, period="1y", group_by="ticker", threads=True)

    # Extract individual stock histories from the batch result
    stock_histories = {}
    for symbol in tickers:
        try:
            if len(tickers) == 1:
                hist = all_data
            else:
                hist = all_data[symbol].dropna(how="all")
            if not hist.empty and len(hist) > 20:
                stock_histories[symbol] = hist
        except Exception:
            continue

    print(f"[Scanner] Got data for {len(stock_histories)} stocks, analyzing...")

    # Now run analysis in parallel (only the info + scoring part)
    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(_quick_analyze, symbol, hist): symbol
            for symbol, hist in stock_histories.items()
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                if result and result["finalScore"] >= 55:
                    results.append(result)
            except Exception:
                continue

    results.sort(key=lambda x: x["finalScore"], reverse=True)
    print(f"[Scanner] Found {len(results)} picks above threshold")
    return results[:top_n]
