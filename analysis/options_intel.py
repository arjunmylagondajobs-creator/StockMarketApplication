"""
Options Market Intelligence Module
Analyzes options market signals for US stocks (yfinance options data).
For India/non-US tickers, returns graceful N/A fallback.

Signals:
- Put/Call ratio (PCR): > 1.0 = bearish sentiment; < 0.7 = bullish
- Implied Volatility (IV) vs Historical Volatility → IV premium / crush
- Max Pain price level (where most options expire worthless)
- Key open interest strikes (support/resistance levels)
"""

import yfinance as yf
import numpy as np


def _compute_historical_volatility(hist_df, period=20):
    """Compute 20-day historical volatility from price history."""
    try:
        log_returns = np.log(hist_df["Close"] / hist_df["Close"].shift(1)).dropna()
        if len(log_returns) < period:
            return None
        hv = log_returns.tail(period).std() * np.sqrt(252) * 100  # annualized %
        return round(float(hv), 2)
    except Exception:
        return None


def _fetch_options_data(ticker_obj):
    """
    Fetch the nearest-expiry options chain.
    Returns (calls_df, puts_df, expiry_date) or (None, None, None).
    """
    try:
        expirations = ticker_obj.options
        if not expirations:
            return None, None, None
        # Use nearest expiry
        nearest = expirations[0]
        chain = ticker_obj.option_chain(nearest)
        return chain.calls, chain.puts, nearest
    except Exception:
        return None, None, None


def _compute_put_call_ratio(calls_df, puts_df):
    """Compute volume-based Put/Call ratio."""
    try:
        call_vol = calls_df["volume"].fillna(0).sum()
        put_vol = puts_df["volume"].fillna(0).sum()
        if call_vol <= 0:
            return None
        pcr = round(put_vol / call_vol, 3)
        return pcr
    except Exception:
        return None


def _score_put_call_ratio(pcr):
    """Score PCR: low = bullish (calls dominate), high = bearish."""
    if pcr is None:
        return 50, "Put/Call ratio unavailable"
    if pcr < 0.5:
        return 75, f"Put/Call ratio ({pcr:.2f}) — extremely bullish sentiment, high call activity"
    elif pcr < 0.7:
        return 65, f"Put/Call ratio ({pcr:.2f}) — bullish sentiment"
    elif pcr < 1.0:
        return 55, f"Put/Call ratio ({pcr:.2f}) — mildly bullish"
    elif pcr < 1.3:
        return 45, f"Put/Call ratio ({pcr:.2f}) — mildly bearish hedge activity"
    elif pcr < 1.8:
        return 32, f"Put/Call ratio ({pcr:.2f}) — elevated puts, bearish sentiment"
    else:
        return 20, f"Put/Call ratio ({pcr:.2f}) — heavy put buying, strong bearish bets or hedge"


def _compute_max_pain(calls_df, puts_df):
    """
    Max Pain = strike where total option losses are maximized for buyers.
    This is where market makers want price to settle on expiry.
    """
    try:
        all_strikes = sorted(set(calls_df["strike"].tolist() + puts_df["strike"].tolist()))
        if not all_strikes:
            return None

        max_pain_losses = {}
        for strike in all_strikes:
            call_loss = 0
            for _, row in calls_df.iterrows():
                if row["strike"] < strike:
                    call_loss += (strike - row["strike"]) * row.get("openInterest", 0)
            put_loss = 0
            for _, row in puts_df.iterrows():
                if row["strike"] > strike:
                    put_loss += (row["strike"] - strike) * row.get("openInterest", 0)
            max_pain_losses[strike] = call_loss + put_loss

        if max_pain_losses:
            max_pain_strike = min(max_pain_losses, key=max_pain_losses.get)
            return round(float(max_pain_strike), 2)
    except Exception:
        return None
    return None


def _analyze_iv_vs_hv(calls_df, puts_df, hist_df):
    """
    Compare implied volatility (average IV from options) vs historical volatility.
    IV > HV = options expensive, potential IV crush after event.
    IV < HV = options cheap, potential for expansion.
    """
    try:
        all_iv = []
        for df in [calls_df, puts_df]:
            iv_col = "impliedVolatility"
            if iv_col in df.columns:
                iv_vals = df[iv_col].dropna()
                iv_vals = iv_vals[(iv_vals > 0) & (iv_vals < 5)]  # filter outliers
                all_iv.extend(iv_vals.tolist())

        if not all_iv:
            return None, None, "IV data unavailable"

        avg_iv = round(np.median(all_iv) * 100, 2)  # as percentage
        hv = _compute_historical_volatility(hist_df)

        if hv is None:
            return avg_iv, None, f"IV: {avg_iv:.1f}% (HV unavailable for comparison)"

        iv_premium = round(avg_iv - hv, 2)
        if iv_premium > 20:
            signal = f"IV ({avg_iv:.1f}%) >> HV ({hv:.1f}%) — options very expensive, IV crush likely after catalyst"
        elif iv_premium > 8:
            signal = f"IV ({avg_iv:.1f}%) > HV ({hv:.1f}%) — elevated premium, options pricing in event risk"
        elif iv_premium > -5:
            signal = f"IV ({avg_iv:.1f}%) ≈ HV ({hv:.1f}%) — fair options pricing"
        else:
            signal = f"IV ({avg_iv:.1f}%) < HV ({hv:.1f}%) — options cheap, potential for IV expansion"

        return avg_iv, hv, signal
    except Exception:
        return None, None, "IV analysis error"


def _get_key_oi_levels(calls_df, puts_df, current_price):
    """Find top open interest call/put strikes — these act as support/resistance."""
    levels = {"call_wall": None, "put_wall": None}
    try:
        if "openInterest" in calls_df.columns and "strike" in calls_df.columns:
            # Calls above current price
            calls_above = calls_df[calls_df["strike"] >= current_price]
            if not calls_above.empty:
                top_call = calls_above.nlargest(1, "openInterest")
                levels["call_wall"] = round(float(top_call["strike"].iloc[0]), 2)

        if "openInterest" in puts_df.columns and "strike" in puts_df.columns:
            # Puts below current price
            puts_below = puts_df[puts_df["strike"] <= current_price]
            if not puts_below.empty:
                top_put = puts_below.nlargest(1, "openInterest")
                levels["put_wall"] = round(float(top_put["strike"].iloc[0]), 2)
    except Exception:
        pass
    return levels


def run_options_analysis(ticker_obj, ticker_symbol, hist_df, current_price=None):
    """
    Run options market intelligence analysis.
    For India stocks (suffix .NS/.BO) or unavailable options, returns N/A result.
    """
    result = {
        "available": False,
        "score": 50,
        "put_call_ratio": None,
        "implied_volatility": None,
        "historical_volatility": None,
        "max_pain": None,
        "call_wall": None,
        "put_wall": None,
        "signals": [],
        "options_sentiment": "N/A"
    }

    # India stocks don't have options data via yfinance
    is_india = ".NS" in ticker_symbol or ".BO" in ticker_symbol
    if is_india:
        result["signals"] = ["Options intelligence not available for India-listed stocks"]
        return result

    calls_df, puts_df, expiry = _fetch_options_data(ticker_obj)

    if calls_df is None or puts_df is None:
        result["signals"] = ["Options data unavailable for this ticker"]
        return result

    result["available"] = True
    signals = [f"Options expiry analyzed: {expiry}"]

    # 1. Put/Call ratio
    pcr = _compute_put_call_ratio(calls_df, puts_df)
    pcr_score, pcr_sig = _score_put_call_ratio(pcr)
    result["put_call_ratio"] = pcr
    signals.append(pcr_sig)

    # 2. IV vs HV
    if hist_df is not None and not hist_df.empty:
        avg_iv, hv, iv_sig = _analyze_iv_vs_hv(calls_df, puts_df, hist_df)
        result["implied_volatility"] = avg_iv
        result["historical_volatility"] = hv
        signals.append(iv_sig)
    else:
        iv_sig = None

    # 3. Max Pain
    mp = _compute_max_pain(calls_df, puts_df)
    result["max_pain"] = mp
    if mp and current_price:
        pct_diff = round(((mp - current_price) / current_price) * 100, 1)
        if pct_diff > 0:
            signals.append(f"Max Pain: ${mp:,.2f} (+{pct_diff}% above current) — expiry gravity pulling upward")
        else:
            signals.append(f"Max Pain: ${mp:,.2f} ({pct_diff}% below current) — expiry gravity pulling downward")

    # 4. Key OI levels
    if current_price:
        oi_levels = _get_key_oi_levels(calls_df, puts_df, current_price)
        result["call_wall"] = oi_levels.get("call_wall")
        result["put_wall"] = oi_levels.get("put_wall")
        if oi_levels.get("call_wall"):
            signals.append(f"Call Wall (resistance): ${oi_levels['call_wall']:,} — heavy call OI here")
        if oi_levels.get("put_wall"):
            signals.append(f"Put Wall (support): ${oi_levels['put_wall']:,} — strong put OI floor")

    # Composite score (primarily driven by PCR)
    final_score = pcr_score
    result["score"] = max(0, min(100, final_score))
    result["signals"] = [s for s in signals if s]

    if final_score >= 65:
        result["options_sentiment"] = "Bullish (Options Markets)"
    elif final_score >= 52:
        result["options_sentiment"] = "Mildly Bullish"
    elif final_score >= 42:
        result["options_sentiment"] = "Neutral"
    elif final_score >= 30:
        result["options_sentiment"] = "Mildly Bearish"
    else:
        result["options_sentiment"] = "Bearish (Heavy Put Buying)"

    return result
