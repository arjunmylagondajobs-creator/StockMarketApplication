"""
Macro & Monetary Policy Analysis Module
Fetches and scores macroeconomic context:
- US: Fed rate direction, 10Y Treasury yield, VIX fear index, Dollar index
- India: USD/INR trend, Nifty50 regime, FII net flows (via yfinance proxies)
- Global: Oil price trend (Brent), Gold trend
Returns a composite macro score (0-100) and structured signals.
"""

import yfinance as yf


# ── Macro proxies: all fetchable via yfinance ──
MACRO_TICKERS = {
    "vix":       "^VIX",       # CBOE Volatility Index (fear gauge)
    "us10y":     "^TNX",       # US 10-Year Treasury Yield
    "dxy":       "DX-Y.NYB",   # US Dollar Index
    "nifty50":   "^NSEI",      # Nifty 50 (India)
    "usdinr":    "USDINR=X",   # USD/INR
    "oil_brent": "BZ=F",       # Brent Crude Oil
    "gold":      "GC=F",       # Gold Futures
    "sp500":     "^GSPC",      # S&P 500
}

# ── India-specific sector policy ETF proxies via NSE ──
INDIA_SECTOR_ETFS = {
    "IT":           "NIFTYIT.NS",
    "Banking":      "BANKNIFTY.NS",
    "Pharma":       "NIFTYPHARMA.NS",
}


def _fetch_ticker_data(symbol, period="3mo"):
    """Fetch recent price data for a macro ticker. Returns last price + pct change."""
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period=period)
        if hist.empty or len(hist) < 5:
            return None, None, None
        current = round(float(hist["Close"].iloc[-1]), 4)
        month_ago = round(float(hist["Close"].iloc[max(0, len(hist)-21)]), 4)
        pct_change = round(((current - month_ago) / month_ago) * 100, 2) if month_ago else None
        week_change = None
        if len(hist) >= 5:
            week_ago = float(hist["Close"].iloc[-5])
            week_change = round(((current - week_ago) / week_ago) * 100, 2) if week_ago else None
        return current, pct_change, week_change
    except Exception:
        return None, None, None


def _score_vix(vix_val):
    """VIX score: low VIX = bullish environment."""
    if vix_val is None:
        return 50, "VIX data unavailable"
    if vix_val < 12:
        return 80, f"VIX ({vix_val:.1f}) — very low fear, risk-on environment"
    elif vix_val < 18:
        return 70, f"VIX ({vix_val:.1f}) — calm markets, conducive for equities"
    elif vix_val < 25:
        return 50, f"VIX ({vix_val:.1f}) — moderate volatility"
    elif vix_val < 35:
        return 30, f"VIX ({vix_val:.1f}) — elevated fear, risk-off pressure"
    else:
        return 10, f"VIX ({vix_val:.1f}) — extreme fear/panic in markets"


def _score_us10y(yield_val, pct_change):
    """10Y yield: rising yields hurt equities (esp. growth/tech), falling = tailwind."""
    if yield_val is None:
        return 50, "US 10Y yield data unavailable"
    signal = f"US 10Y Yield: {yield_val:.2f}%"
    score = 50
    if yield_val > 5.0:
        score = 20
        signal += " — very high yields, significant equity headwind"
    elif yield_val > 4.5:
        score = 35
        signal += " — high yields, equity competition from bonds"
    elif yield_val > 4.0:
        score = 45
        signal += " — elevated yields, modest pressure on valuations"
    elif yield_val > 3.5:
        score = 55
        signal += " — moderate yields, equities still attractive"
    elif yield_val > 2.5:
        score = 65
        signal += " — low yields, equity-friendly environment"
    else:
        score = 75
        signal += " — very low yields, strong tailwind for equities"

    if pct_change is not None:
        if pct_change > 10:
            score = max(0, score - 15)
            signal += f" (rising sharply +{pct_change:.1f}% in 1M — hawkish pressure)"
        elif pct_change < -10:
            score = min(100, score + 10)
            signal += f" (falling {pct_change:.1f}% in 1M — dovish/rate-cut signal)"
    return score, signal


def _score_dxy(dxy_val, pct_change):
    """Dollar index: strong USD hurts emerging markets; weak USD = tailwind for EM/commodities."""
    if dxy_val is None:
        return 50, "US Dollar Index data unavailable"
    signal = f"DXY (Dollar Index): {dxy_val:.1f}"
    score = 50
    if dxy_val > 107:
        score = 30
        signal += " — strong dollar, headwind for EM/India/commodities"
    elif dxy_val > 103:
        score = 42
        signal += " — firm dollar, some EM pressure"
    elif dxy_val > 99:
        score = 55
        signal += " — neutral dollar level"
    else:
        score = 68
        signal += " — weak dollar, tailwind for EM equities & commodities"

    if pct_change is not None and abs(pct_change) > 3:
        if pct_change > 0:
            score = max(0, score - 8)
            signal += f" (strengthening +{pct_change:.1f}% in 1M)"
        else:
            score = min(100, score + 8)
            signal += f" (weakening {pct_change:.1f}% in 1M)"
    return score, signal


def _score_usdinr(usdinr_val, pct_change):
    """USD/INR: high = rupee weak = imported inflation / FII outflows for India."""
    if usdinr_val is None:
        return 50, "USD/INR data unavailable"
    signal = f"USD/INR: {usdinr_val:.2f}"
    score = 50
    if usdinr_val > 88:
        score = 20
        signal += " — rupee very weak, FII risk, imported inflation"
    elif usdinr_val > 85:
        score = 35
        signal += " — rupee weak, moderate pressure on India equities"
    elif usdinr_val > 83:
        score = 50
        signal += " — rupee stable range"
    elif usdinr_val > 80:
        score = 65
        signal += " — rupee firm, FII inflows supportive"
    else:
        score = 75
        signal += " — strong rupee, positive for India equities"
    if pct_change is not None and pct_change > 2:
        score = max(0, score - 10)
        signal += f" (depreciating {pct_change:.1f}% in 1M)"
    return score, signal


def _score_oil(oil_val, pct_change):
    """Oil (Brent): high oil = inflation risk / current account deficit for India oil importers."""
    if oil_val is None:
        return 50, "Brent crude data unavailable"
    signal = f"Brent Crude: ${oil_val:.1f}/bbl"
    score = 50
    if oil_val > 100:
        score = 20
        signal += " — very high oil, inflation pressure, India CAD risk"
    elif oil_val > 85:
        score = 35
        signal += " — elevated oil, moderate headwind"
    elif oil_val > 70:
        score = 60
        signal += " — moderate oil price, manageable"
    elif oil_val > 55:
        score = 72
        signal += " — low oil, benign for India, airlines, paints, chemicals"
    else:
        score = 80
        signal += " — very low oil, strong tailwind for oil-importing economies"
    if pct_change is not None and pct_change > 10:
        score = max(0, score - 12)
        signal += f" (surging +{pct_change:.1f}% in 1M)"
    return score, signal


def _score_nifty_regime(nifty_val, pct_1m):
    """Nifty50 regime: is the Indian market in bull/bear/correction?"""
    if nifty_val is None:
        return 50, "Nifty50 data unavailable"
    signal = f"Nifty50: {nifty_val:,.0f}"
    score = 50
    if pct_1m is not None:
        if pct_1m > 5:
            score = 75
            signal += f" (+{pct_1m:.1f}% in 1M — bullish momentum)"
        elif pct_1m > 2:
            score = 62
            signal += f" (+{pct_1m:.1f}% in 1M — steady uptrend)"
        elif pct_1m > -2:
            score = 50
            signal += f" ({pct_1m:.1f}% in 1M — consolidating)"
        elif pct_1m > -5:
            score = 38
            signal += f" ({pct_1m:.1f}% in 1M — correction underway)"
        else:
            score = 20
            signal += f" ({pct_1m:.1f}% in 1M — sharp correction / bear phase)"
    return score, signal


def _score_sp500_regime(sp500_val, pct_1m):
    """S&P 500 regime for US stocks."""
    if sp500_val is None:
        return 50, "S&P 500 data unavailable"
    signal = f"S&P 500: {sp500_val:,.0f}"
    score = 50
    if pct_1m is not None:
        if pct_1m > 4:
            score = 75
            signal += f" (+{pct_1m:.1f}% in 1M — bull market rally)"
        elif pct_1m > 1:
            score = 62
            signal += f" (+{pct_1m:.1f}% in 1M — steady)"
        elif pct_1m > -2:
            score = 50
            signal += f" ({pct_1m:.1f}% in 1M — range-bound)"
        elif pct_1m > -6:
            score = 35
            signal += f" ({pct_1m:.1f}% in 1M — correction)"
        else:
            score = 18
            signal += f" ({pct_1m:.1f}% in 1M — bear market pressure)"
    return score, signal


def run_macro_analysis(ticker_symbol="", is_india=False):
    """
    Run macroeconomic analysis.
    Returns dict with macro signals, sub-scores, and composite macro score (0-100).
    """
    result = {
        "score": 50,
        "environment": "Neutral",
        "signals": [],
        "sub_scores": {},
        "error": None
    }

    signals = []
    sub_scores = {}

    # ── VIX (global risk appetite) ──
    vix_val, vix_pct, _ = _fetch_ticker_data("^VIX")
    vix_score, vix_sig = _score_vix(vix_val)
    sub_scores["vix"] = vix_score
    signals.append(vix_sig)

    # ── US 10Y Treasury Yield ──
    us10y_val, us10y_pct, _ = _fetch_ticker_data("^TNX")
    us10y_score, us10y_sig = _score_us10y(us10y_val, us10y_pct)
    sub_scores["us10y"] = us10y_score
    signals.append(us10y_sig)

    # ── Dollar Index ──
    dxy_val, dxy_pct, _ = _fetch_ticker_data("DX-Y.NYB")
    dxy_score, dxy_sig = _score_dxy(dxy_val, dxy_pct)
    sub_scores["dxy"] = dxy_score
    signals.append(dxy_sig)

    # ── Oil ──
    oil_val, oil_pct, _ = _fetch_ticker_data("BZ=F")
    oil_score, oil_sig = _score_oil(oil_val, oil_pct)
    sub_scores["oil"] = oil_score
    signals.append(oil_sig)

    # ── India-specific ──
    if is_india:
        usdinr_val, usdinr_pct, _ = _fetch_ticker_data("USDINR=X")
        usdinr_score, usdinr_sig = _score_usdinr(usdinr_val, usdinr_pct)
        sub_scores["usdinr"] = usdinr_score
        signals.append(usdinr_sig)

        nifty_val, nifty_pct, _ = _fetch_ticker_data("^NSEI")
        nifty_score, nifty_sig = _score_nifty_regime(nifty_val, nifty_pct)
        sub_scores["index_regime"] = nifty_score
        signals.append(nifty_sig)

        # Weighted composite for India
        composite = (
            vix_score * 0.20 +
            us10y_score * 0.15 +
            dxy_score * 0.15 +
            usdinr_score * 0.20 +
            oil_score * 0.15 +
            nifty_score * 0.15
        )
    else:
        sp500_val, sp500_pct, _ = _fetch_ticker_data("^GSPC")
        sp500_score, sp500_sig = _score_sp500_regime(sp500_val, sp500_pct)
        sub_scores["index_regime"] = sp500_score
        signals.append(sp500_sig)

        # Weighted composite for US
        composite = (
            vix_score * 0.25 +
            us10y_score * 0.25 +
            dxy_score * 0.20 +
            oil_score * 0.10 +
            sp500_score * 0.20
        )

    macro_score = max(0, min(100, round(composite)))
    result["score"] = macro_score
    result["signals"] = [s for s in signals if s]
    result["sub_scores"] = sub_scores

    # Environment classification
    if macro_score >= 70:
        result["environment"] = "Risk-On / Bullish Macro"
    elif macro_score >= 58:
        result["environment"] = "Mildly Positive Macro"
    elif macro_score >= 42:
        result["environment"] = "Neutral Macro"
    elif macro_score >= 30:
        result["environment"] = "Cautious / Risk-Off"
    else:
        result["environment"] = "Bearish Macro / High Stress"

    return result
