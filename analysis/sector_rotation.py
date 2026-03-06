"""
Sector Rotation & Relative Strength Analysis Module
Compares stock's performance vs its sector ETF and broader market.
Identifies if money is rotating INTO or OUT OF this sector.
"""

import yfinance as yf
import numpy as np


# Sector → representative ETF (US)
US_SECTOR_ETFS = {
    "Technology":              "XLK",
    "Communication Services":  "XLC",
    "Consumer Cyclical":       "XLY",
    "Consumer Defensive":      "XLP",
    "Healthcare":              "XLV",
    "Financial Services":      "XLF",
    "Industrials":             "XLI",
    "Energy":                  "XLE",
    "Utilities":               "XLU",
    "Real Estate":             "XLRE",
    "Basic Materials":         "XLB",
}

# India sector ETFs/indices
INDIA_SECTOR_ETFS = {
    "Technology":              "^CNXIT",
    "Financial Services":      "^NSEBANK",
    "Healthcare":              "^CNXPHARMA",
    "Consumer Cyclical":       "^CNXAUTO",
    "Energy":                  "^CNXENERGY",
    "Basic Materials":         "^CNXMETAL",
    "Consumer Defensive":      "^CNXFMCG",
    "Industrials":             "^CNXINFRA",
}

# US market benchmark
US_BENCHMARK = "^GSPC"  # S&P 500
INDIA_BENCHMARK = "^NSEI"  # Nifty 50


def _compute_returns(hist_df, periods_days=(5, 21, 63)):
    """Compute returns over multiple periods."""
    if hist_df is None or hist_df.empty or len(hist_df) < 5:
        return {}
    returns = {}
    current = float(hist_df["Close"].iloc[-1])
    period_names = ["1W", "1M", "3M"]
    for i, days in enumerate(periods_days):
        if len(hist_df) >= days:
            past = float(hist_df["Close"].iloc[-days])
            returns[period_names[i]] = round(((current - past) / past) * 100, 2)
    return returns


def _fetch_comparison_data(symbol, period="3mo"):
    """Fetch historical data for comparison."""
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period=period)
        if hist.empty or len(hist) < 10:
            return None
        return hist
    except Exception:
        return None


def _compute_relative_strength(stock_hist, benchmark_hist, period_days=21):
    """
    Relative Strength = stock return / benchmark return over period.
    RS > 1 = outperforming, RS < 1 = underperforming.
    """
    try:
        if len(stock_hist) < period_days or len(benchmark_hist) < period_days:
            return None
        stock_ret = (float(stock_hist["Close"].iloc[-1]) / float(stock_hist["Close"].iloc[-period_days]) - 1) * 100
        bench_ret = (float(benchmark_hist["Close"].iloc[-1]) / float(benchmark_hist["Close"].iloc[-period_days]) - 1) * 100
        return round(stock_ret - bench_ret, 2)  # Alpha vs benchmark
    except Exception:
        return None


def _score_relative_strength(alpha_1m, alpha_3m):
    """Score based on relative strength vs benchmark."""
    if alpha_1m is None and alpha_3m is None:
        return 50, "Relative strength data unavailable"

    score = 50
    signals = []

    if alpha_1m is not None:
        if alpha_1m > 10:
            score += 20
            signals.append(f"Strong outperformance vs benchmark (+{alpha_1m:.1f}% alpha in 1M)")
        elif alpha_1m > 4:
            score += 10
            signals.append(f"Outperforming benchmark (+{alpha_1m:.1f}% in 1M)")
        elif alpha_1m > 0:
            score += 4
            signals.append(f"Slightly outperforming (+{alpha_1m:.1f}% in 1M)")
        elif alpha_1m > -5:
            score -= 4
            signals.append(f"Slightly underperforming ({alpha_1m:.1f}% vs benchmark in 1M)")
        else:
            score -= 15
            signals.append(f"Underperforming benchmark ({alpha_1m:.1f}% in 1M) — laggard")

    if alpha_3m is not None:
        if alpha_3m > 15:
            score += 10
        elif alpha_3m > 5:
            score += 5
        elif alpha_3m < -10:
            score -= 10

    return max(0, min(100, score)), " | ".join(signals)


def _score_sector_rotation(stock_ret_1m, sector_ret_1m):
    """Is money flowing into or out of the sector?"""
    if sector_ret_1m is None:
        return 50, "Sector rotation data unavailable"

    signals = []
    score = 50

    if sector_ret_1m > 5:
        score = 68
        signals.append(f"Sector gaining {sector_ret_1m:.1f}% in 1M — money rotating IN")
    elif sector_ret_1m > 2:
        score = 60
        signals.append(f"Sector up {sector_ret_1m:.1f}% in 1M — mild inflow")
    elif sector_ret_1m > -2:
        score = 50
        signals.append(f"Sector flat ({sector_ret_1m:.1f}% in 1M) — sector neutral")
    elif sector_ret_1m > -5:
        score = 38
        signals.append(f"Sector down {sector_ret_1m:.1f}% in 1M — mild outflow")
    else:
        score = 22
        signals.append(f"Sector falling {sector_ret_1m:.1f}% in 1M — money rotating OUT")

    # Bonus: stock beating sector
    if stock_ret_1m is not None:
        diff = stock_ret_1m - sector_ret_1m
        if diff > 5:
            score = min(100, score + 10)
            signals.append(f"Stock beating its sector by {diff:.1f}% — sector leader")
        elif diff < -5:
            score = max(0, score - 5)
            signals.append(f"Stock lagging its sector by {abs(diff):.1f}% — sector laggard")

    return score, " | ".join(signals)


def run_sector_rotation_analysis(ticker_symbol, sector="", hist_df=None, is_india=False):
    """
    Run sector rotation analysis.
    Returns dict with relative strength score, sector momentum, and signals.
    """
    result = {
        "score": 50,
        "rotation_signal": "Neutral",
        "stock_returns": {},
        "sector_returns": {},
        "alpha_1m": None,
        "alpha_3m": None,
        "sector_etf": None,
        "signals": []
    }

    signals = []

    # Determine sector ETF
    if is_india:
        sector_etf = INDIA_SECTOR_ETFS.get(sector)
        benchmark = INDIA_BENCHMARK
    else:
        sector_etf = US_SECTOR_ETFS.get(sector)
        benchmark = US_BENCHMARK

    # Stock returns
    if hist_df is not None and not hist_df.empty:
        stock_returns = _compute_returns(hist_df, periods_days=(5, 21, 63))
        result["stock_returns"] = stock_returns
    else:
        stock_returns = {}

    stock_ret_1m = stock_returns.get("1M")

    # Sector ETF data
    sector_ret_1m = None
    if sector_etf:
        result["sector_etf"] = sector_etf
        sector_hist = _fetch_comparison_data(sector_etf, period="3mo")
        if sector_hist is not None:
            sector_returns = _compute_returns(sector_hist, periods_days=(5, 21, 63))
            result["sector_returns"] = sector_returns
            sector_ret_1m = sector_returns.get("1M")

    # Benchmark data
    benchmark_hist = _fetch_comparison_data(benchmark, period="3mo")
    alpha_1m = None
    alpha_3m = None

    if benchmark_hist is not None and hist_df is not None and not hist_df.empty:
        alpha_1m = _compute_relative_strength(hist_df, benchmark_hist, period_days=21)
        alpha_3m = _compute_relative_strength(hist_df, benchmark_hist, period_days=63)
        result["alpha_1m"] = alpha_1m
        result["alpha_3m"] = alpha_3m

    # Scores
    rs_score, rs_sig = _score_relative_strength(alpha_1m, alpha_3m)
    sr_score, sr_sig = _score_sector_rotation(stock_ret_1m, sector_ret_1m)

    if rs_sig:
        signals.append(rs_sig)
    if sr_sig:
        signals.append(sr_sig)

    # 1M/3M return context
    if stock_ret_1m is not None:
        signals.append(f"Stock 1M return: {'+' if stock_ret_1m > 0 else ''}{stock_ret_1m:.1f}%")
    if stock_returns.get("3M") is not None:
        signals.append(f"Stock 3M return: {'+' if stock_returns['3M'] > 0 else ''}{stock_returns['3M']:.1f}%")

    # Composite
    composite = rs_score * 0.55 + sr_score * 0.45
    final_score = max(0, min(100, round(composite)))
    result["score"] = final_score
    result["signals"] = signals

    if final_score >= 68:
        result["rotation_signal"] = "Strong Relative Strength — Sector Leader"
    elif final_score >= 57:
        result["rotation_signal"] = "Outperforming — Money Flowing In"
    elif final_score >= 43:
        result["rotation_signal"] = "Market-Perform — Neutral Rotation"
    elif final_score >= 30:
        result["rotation_signal"] = "Underperforming — Mild Outflow"
    else:
        result["rotation_signal"] = "Sector Laggard — Money Rotating Out"

    return result
