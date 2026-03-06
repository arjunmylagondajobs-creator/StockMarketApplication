"""
Technical Analysis Module — Institutional Grade
Computes indicators: SMA, EMA, RSI, Stochastic RSI, MACD, Bollinger Bands,
ADX, OBV, ATR, Volume trends. Returns a weighted composite score (0-100).
"""

import pandas as pd
import numpy as np


# ═══════════════════════════════════════════════════════════
# INDICATOR CALCULATIONS
# ═══════════════════════════════════════════════════════════

def compute_sma(df, periods=[20, 50, 200]):
    """Compute Simple Moving Averages."""
    result = {}
    for p in periods:
        col = f"SMA_{p}"
        if len(df) >= p:
            df[col] = df["Close"].rolling(window=p).mean()
            result[col] = round(df[col].iloc[-1], 2)
        else:
            result[col] = None
    return result


def compute_ema(df, periods=[9, 21]):
    """Compute Exponential Moving Averages for EMA ribbon."""
    result = {}
    for p in periods:
        col = f"EMA_{p}"
        if len(df) >= p:
            df[col] = df["Close"].ewm(span=p, adjust=False).mean()
            result[col] = round(df[col].iloc[-1], 2)
        else:
            result[col] = None
    return result


def compute_rsi(df, period=14):
    """Compute RSI using Wilder's smoothing (institutional standard)."""
    if len(df) < period + 1:
        return None, "Insufficient data"

    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    for i in range(period, len(avg_gain)):
        avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    df["RSI"] = rsi

    current_rsi = round(rsi.iloc[-1], 2)

    if current_rsi > 70:
        signal = "Overbought — potential reversal downward"
    elif current_rsi < 30:
        signal = "Oversold — potential reversal upward"
    elif current_rsi > 60:
        signal = "Bullish momentum"
    elif current_rsi < 40:
        signal = "Bearish momentum"
    else:
        signal = "Neutral"

    return current_rsi, signal


def compute_stochastic_rsi(df, rsi_period=14, stoch_period=14, k_smooth=3, d_smooth=3):
    """
    Stochastic RSI — more sensitive than standard RSI.
    Used by institutional traders to catch earlier reversals.
    """
    if "RSI" not in df.columns or len(df) < rsi_period + stoch_period:
        return None, None, "Insufficient data"

    rsi = df["RSI"].dropna()
    if len(rsi) < stoch_period:
        return None, None, "Insufficient data"

    rsi_min = rsi.rolling(window=stoch_period).min()
    rsi_max = rsi.rolling(window=stoch_period).max()
    rsi_range = rsi_max - rsi_min

    stoch_rsi = ((rsi - rsi_min) / rsi_range.replace(0, np.nan)) * 100
    k_line = stoch_rsi.rolling(window=k_smooth).mean()
    d_line = k_line.rolling(window=d_smooth).mean()

    k_val = round(k_line.iloc[-1], 2) if not pd.isna(k_line.iloc[-1]) else None
    d_val = round(d_line.iloc[-1], 2) if not pd.isna(d_line.iloc[-1]) else None

    if k_val is not None and d_val is not None:
        if k_val > 80 and d_val > 80:
            signal = "Overbought zone"
        elif k_val < 20 and d_val < 20:
            signal = "Oversold zone — potential bounce"
        elif k_val > d_val and k_val < 50:
            signal = "Bullish crossover from oversold"
        elif k_val < d_val and k_val > 50:
            signal = "Bearish crossover from overbought"
        else:
            signal = "Neutral"
    else:
        signal = "N/A"

    return k_val, d_val, signal


def compute_macd(df, fast=12, slow=26, signal_period=9):
    """Compute MACD, Signal line, and Histogram."""
    if len(df) < slow + signal_period:
        return None, None, None, "Insufficient data"

    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line

    df["MACD"] = macd_line
    df["MACD_Signal"] = signal_line
    df["MACD_Hist"] = histogram

    current_macd = round(macd_line.iloc[-1], 4)
    current_signal = round(signal_line.iloc[-1], 4)
    current_hist = round(histogram.iloc[-1], 4)

    # Check for recent crossover (last 3 days)
    recent_cross = False
    if len(histogram) > 3:
        for i in range(-3, -1):
            if histogram.iloc[i-1] * histogram.iloc[i] < 0:
                recent_cross = True

    if current_macd > current_signal and current_hist > 0:
        if recent_cross:
            trend = "Fresh bullish crossover — strong buy signal"
        else:
            trend = "Bullish — upward momentum"
    elif current_macd < current_signal and current_hist < 0:
        if recent_cross:
            trend = "Fresh bearish crossover — sell signal"
        else:
            trend = "Bearish — downward momentum"
    else:
        trend = "Neutral / transitioning"

    return current_macd, current_signal, current_hist, trend


def compute_bollinger_bands(df, period=20, std_dev=2):
    """Compute Bollinger Bands with bandwidth and %B."""
    if len(df) < period:
        return None, None, None, "Insufficient data"

    sma = df["Close"].rolling(window=period).mean()
    std = df["Close"].rolling(window=period).std()

    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)

    df["BB_Upper"] = upper
    df["BB_Middle"] = sma
    df["BB_Lower"] = lower

    current_price = df["Close"].iloc[-1]
    bb_upper = round(upper.iloc[-1], 2)
    bb_lower = round(lower.iloc[-1], 2)
    bb_middle = round(sma.iloc[-1], 2)

    bb_width = bb_upper - bb_lower
    if bb_width > 0:
        position = round((current_price - bb_lower) / bb_width, 2)
        # Bandwidth (volatility measure)
        bandwidth = round(bb_width / bb_middle * 100, 2) if bb_middle > 0 else 0
    else:
        position = 0.5
        bandwidth = 0

    if position > 0.95:
        signal = "Near upper band — potentially overbought"
    elif position < 0.05:
        signal = "Near lower band — potentially oversold"
    elif position > 0.7:
        signal = "Upper range — bullish but watch for resistance"
    elif position < 0.3:
        signal = "Lower range — bearish but watch for support"
    else:
        signal = "Mid-range — neutral"

    return {"upper": bb_upper, "middle": bb_middle, "lower": bb_lower,
            "position": position, "bandwidth": bandwidth}, signal


def compute_adx(df, period=14):
    """
    Average Directional Index — measures trend STRENGTH (not direction).
    ADX > 25 = trending market, < 20 = ranging market.
    Institutional standard for trend quality assessment.
    """
    if len(df) < period * 2:
        return None, None, None, "Insufficient data"

    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    # True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Directional Movement
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    # Smoothed averages
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)

    # ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()

    current_adx = round(adx.iloc[-1], 2) if not pd.isna(adx.iloc[-1]) else None
    current_plus_di = round(plus_di.iloc[-1], 2) if not pd.isna(plus_di.iloc[-1]) else None
    current_minus_di = round(minus_di.iloc[-1], 2) if not pd.isna(minus_di.iloc[-1]) else None

    if current_adx is not None:
        if current_adx > 40:
            signal = "Very strong trend"
        elif current_adx > 25:
            signal = "Trending market"
        elif current_adx > 20:
            signal = "Weak trend / transitioning"
        else:
            signal = "Range-bound / no clear trend"

        # Direction
        if current_plus_di and current_minus_di:
            if current_plus_di > current_minus_di:
                signal += " (bullish direction)"
            else:
                signal += " (bearish direction)"
    else:
        signal = "N/A"

    return current_adx, current_plus_di, current_minus_di, signal


def compute_obv(df):
    """
    On-Balance Volume — confirms if price moves are supported by volume.
    Divergence between OBV and price = potential reversal signal.
    """
    if len(df) < 20 or "Volume" not in df.columns:
        return None, "Insufficient data"

    obv = pd.Series(0, index=df.index, dtype=float)
    for i in range(1, len(df)):
        if df["Close"].iloc[i] > df["Close"].iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] + df["Volume"].iloc[i]
        elif df["Close"].iloc[i] < df["Close"].iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] - df["Volume"].iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i-1]

    # Check OBV trend vs price trend (last 20 days)
    obv_recent = obv.tail(20)
    price_recent = df["Close"].tail(20)

    obv_slope = (obv_recent.iloc[-1] - obv_recent.iloc[0])
    price_slope = (price_recent.iloc[-1] - price_recent.iloc[0])

    if obv_slope > 0 and price_slope > 0:
        signal = "Confirmed uptrend — volume supports price rise"
    elif obv_slope < 0 and price_slope < 0:
        signal = "Confirmed downtrend — volume supports price fall"
    elif obv_slope > 0 and price_slope < 0:
        signal = "Bullish divergence — accumulation despite price drop (smart money buying)"
    elif obv_slope < 0 and price_slope > 0:
        signal = "Bearish divergence — distribution despite price rise (smart money selling)"
    else:
        signal = "Neutral"

    return round(obv_slope, 0), signal


def compute_atr(df, period=14):
    """Average True Range — measures volatility for position sizing."""
    if len(df) < period + 1:
        return None, None, "Insufficient data"

    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    current_atr = round(atr.iloc[-1], 2)
    current_price = df["Close"].iloc[-1]
    atr_pct = round((current_atr / current_price) * 100, 2) if current_price > 0 else 0

    if atr_pct > 4:
        signal = "Very high volatility — wide stops needed"
    elif atr_pct > 2.5:
        signal = "Elevated volatility"
    elif atr_pct > 1.5:
        signal = "Normal volatility"
    else:
        signal = "Low volatility — potential breakout setup"

    return current_atr, atr_pct, signal


def analyze_volume(df, period=20):
    """Analyze volume trends."""
    if len(df) < period or "Volume" not in df.columns:
        return None, "Insufficient data"

    avg_vol = df["Volume"].rolling(window=period).mean()
    current_vol = df["Volume"].iloc[-1]
    avg_vol_val = avg_vol.iloc[-1]

    if avg_vol_val == 0:
        return None, "No volume data"

    vol_ratio = round(current_vol / avg_vol_val, 2)

    if vol_ratio > 2.0:
        signal = "Very high volume — strong conviction in current move"
    elif vol_ratio > 1.3:
        signal = "Above average volume — increased interest"
    elif vol_ratio < 0.5:
        signal = "Very low volume — lack of conviction"
    elif vol_ratio < 0.7:
        signal = "Below average volume — reduced interest"
    else:
        signal = "Normal volume"

    return vol_ratio, signal


def detect_crossovers(df):
    """Detect Golden Cross and Death Cross."""
    signals = []

    if "SMA_50" not in df.columns or "SMA_200" not in df.columns:
        return signals

    sma50 = df["SMA_50"].dropna()
    sma200 = df["SMA_200"].dropna()

    if len(sma50) < 2 or len(sma200) < 2:
        return signals

    common_idx = sma50.index.intersection(sma200.index)
    if len(common_idx) < 2:
        return signals

    recent = common_idx[-10:]
    for i in range(1, len(recent)):
        prev_diff = sma50.loc[recent[i - 1]] - sma200.loc[recent[i - 1]]
        curr_diff = sma50.loc[recent[i]] - sma200.loc[recent[i]]

        if prev_diff <= 0 and curr_diff > 0:
            signals.append({"type": "Golden Cross", "date": str(recent[i].date()), "bias": "Bullish"})
        elif prev_diff >= 0 and curr_diff < 0:
            signals.append({"type": "Death Cross", "date": str(recent[i].date()), "bias": "Bearish"})

    return signals


# ═══════════════════════════════════════════════════════════
# WEIGHTED SCORING ENGINE
# ═══════════════════════════════════════════════════════════

def _score_rsi(rsi):
    """Normalize RSI to a 0-100 favorability score."""
    if rsi is None:
        return 50
    if rsi < 25:
        return 90    # Deep oversold = strong buy opportunity
    elif rsi < 35:
        return 75
    elif rsi < 45:
        return 60
    elif rsi < 55:
        return 50    # Neutral
    elif rsi < 65:
        return 55    # Slightly bullish momentum
    elif rsi < 75:
        return 40    # Getting overbought
    else:
        return 20    # Deep overbought = risky


def _score_macd(macd_val, signal_val, histogram):
    """Score MACD based on crossover and momentum."""
    if macd_val is None or histogram is None:
        return 50

    score = 50
    if histogram > 0:
        score += min(25, int(abs(histogram) * 800))  # Bullish
    else:
        score -= min(25, int(abs(histogram) * 800))  # Bearish

    # Crossover freshness (macd vs signal)
    if macd_val > signal_val:
        score += 5
    else:
        score -= 5

    return max(0, min(100, score))


def _score_bollinger(position):
    """Score BB position — lower = better buying opportunity."""
    if position is None:
        return 50
    if position < 0.1:
        return 85   # Near lower band — oversold bounce potential
    elif position < 0.3:
        return 70
    elif position < 0.5:
        return 55
    elif position < 0.7:
        return 50
    elif position < 0.9:
        return 40
    else:
        return 20   # Near upper band — overbought


def _score_adx(adx, plus_di, minus_di):
    """Score ADX — strong bull trend = high score, strong bear = low."""
    if adx is None or plus_di is None or minus_di is None:
        return 50

    is_bullish = plus_di > minus_di

    if adx > 30:
        return 80 if is_bullish else 20    # Strong trending
    elif adx > 25:
        return 70 if is_bullish else 30
    elif adx > 20:
        return 60 if is_bullish else 40
    else:
        return 50  # No trend


def _score_obv(obv_signal):
    """Score OBV based on divergence/confirmation."""
    if obv_signal is None:
        return 50
    if "Confirmed uptrend" in obv_signal:
        return 75
    elif "Bullish divergence" in obv_signal:
        return 85   # Smart money buying — very bullish
    elif "Confirmed downtrend" in obv_signal:
        return 25
    elif "Bearish divergence" in obv_signal:
        return 15   # Smart money selling — very bearish
    return 50


def _score_ema_ribbon(ema_data, current_price):
    """Score EMA 9/21 ribbon — price above both = bullish."""
    ema9 = ema_data.get("EMA_9")
    ema21 = ema_data.get("EMA_21")
    if not ema9 or not ema21 or not current_price:
        return 50

    if current_price > ema9 > ema21:
        return 80   # Perfect bullish alignment
    elif current_price > ema21 and ema9 > ema21:
        return 65   # Bullish but pulled back
    elif current_price < ema9 < ema21:
        return 20   # Perfect bearish alignment
    elif current_price < ema21 and ema9 < ema21:
        return 35   # Bearish but might bounce
    else:
        return 50   # Mixed


def _score_sma_trend(sma_data, current_price):
    """Score SMA arrangement and price position."""
    sma50 = sma_data.get("SMA_50")
    sma200 = sma_data.get("SMA_200")
    sma20 = sma_data.get("SMA_20")
    if not current_price:
        return 50

    score = 50

    # Price above/below key SMAs
    if sma20 and current_price > sma20:
        score += 5
    elif sma20:
        score -= 5

    if sma50 and current_price > sma50:
        score += 8
    elif sma50:
        score -= 8

    if sma200 and current_price > sma200:
        score += 10
    elif sma200:
        score -= 10

    # Golden arrangement (50 > 200)
    if sma50 and sma200:
        if sma50 > sma200:
            score += 7  # Bullish structure
        else:
            score -= 7  # Bearish structure

    return max(0, min(100, score))


def _score_volume(vol_ratio):
    """Score volume — higher volume on up moves is positive."""
    if vol_ratio is None:
        return 50
    if vol_ratio > 2.0:
        return 70
    elif vol_ratio > 1.3:
        return 60
    elif vol_ratio < 0.5:
        return 35
    return 50


def compute_technical_score(indicators, adx_val):
    """
    Institutional-grade weighted composite scoring.
    Dynamic weights: trending markets weight MACD/ADX higher; ranging markets weight RSI/BB higher.
    """
    is_trending = adx_val is not None and adx_val > 25

    if is_trending:
        # Trending market — momentum indicators matter more
        weights = {
            "macd": 0.20,
            "adx": 0.18,
            "ema_ribbon": 0.15,
            "sma_trend": 0.15,
            "obv": 0.12,
            "rsi": 0.08,
            "bollinger": 0.05,
            "volume": 0.07,
        }
    else:
        # Range-bound — mean-reversion indicators matter more
        weights = {
            "rsi": 0.18,
            "bollinger": 0.15,
            "macd": 0.15,
            "obv": 0.14,
            "ema_ribbon": 0.12,
            "sma_trend": 0.12,
            "adx": 0.07,
            "volume": 0.07,
        }

    total = 0
    for key, weight in weights.items():
        total += indicators.get(key, 50) * weight

    return max(0, min(100, round(total)))


# ═══════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════

def run_technical_analysis(df):
    """
    Run institutional-grade technical analysis.
    Returns dict with all indicators, signals, and weighted composite score.
    """
    result = {
        "sma": {},
        "ema": {},
        "rsi": {"value": None, "signal": "N/A"},
        "stoch_rsi": {"k": None, "d": None, "signal": "N/A"},
        "macd": {"macd": None, "signal_line": None, "histogram": None, "trend": "N/A"},
        "bollinger_bands": {"bands": None, "signal": "N/A"},
        "adx": {"value": None, "plus_di": None, "minus_di": None, "signal": "N/A"},
        "obv": {"trend": None, "signal": "N/A"},
        "atr": {"value": None, "pct": None, "signal": "N/A"},
        "volume": {"ratio": None, "signal": "N/A"},
        "crossovers": [],
        "score": 50,
        "market_regime": "Unknown",
        "chart_data": {}
    }

    if df is None or df.empty or len(df) < 20:
        result["error"] = "Insufficient historical data for technical analysis"
        return result

    current_price = df["Close"].iloc[-1]

    # ── Compute all indicators ──
    sma_data = compute_sma(df)
    result["sma"] = sma_data

    ema_data = compute_ema(df)
    result["ema"] = ema_data

    rsi_val, rsi_signal = compute_rsi(df)
    result["rsi"] = {"value": rsi_val, "signal": rsi_signal}

    stoch_k, stoch_d, stoch_signal = compute_stochastic_rsi(df)
    result["stoch_rsi"] = {"k": stoch_k, "d": stoch_d, "signal": stoch_signal}

    macd_val, macd_sig, macd_hist, macd_trend = compute_macd(df)
    result["macd"] = {"macd": macd_val, "signal_line": macd_sig, "histogram": macd_hist, "trend": macd_trend}

    bb_data, bb_signal = compute_bollinger_bands(df)
    result["bollinger_bands"] = {"bands": bb_data, "signal": bb_signal}

    adx_val, plus_di, minus_di, adx_signal = compute_adx(df)
    result["adx"] = {"value": adx_val, "plus_di": plus_di, "minus_di": minus_di, "signal": adx_signal}

    obv_trend, obv_signal = compute_obv(df)
    result["obv"] = {"trend": obv_trend, "signal": obv_signal}

    atr_val, atr_pct, atr_signal = compute_atr(df)
    result["atr"] = {"value": atr_val, "pct": atr_pct, "signal": atr_signal}

    vol_ratio, vol_signal = analyze_volume(df)
    result["volume"] = {"ratio": vol_ratio, "signal": vol_signal}

    crossovers = detect_crossovers(df)
    result["crossovers"] = crossovers

    # ── Market regime detection ──
    if adx_val and adx_val > 25:
        if plus_di and minus_di and plus_di > minus_di:
            result["market_regime"] = "Bullish Trend"
        else:
            result["market_regime"] = "Bearish Trend"
    elif adx_val and adx_val < 20:
        result["market_regime"] = "Range-Bound"
    else:
        result["market_regime"] = "Transitioning"

    # ── Compute normalized sub-scores ──
    bb_pos = bb_data["position"] if bb_data else None
    indicator_scores = {
        "rsi": _score_rsi(rsi_val),
        "macd": _score_macd(macd_val, macd_sig, macd_hist),
        "bollinger": _score_bollinger(bb_pos),
        "adx": _score_adx(adx_val, plus_di, minus_di),
        "obv": _score_obv(obv_signal),
        "ema_ribbon": _score_ema_ribbon(ema_data, current_price),
        "sma_trend": _score_sma_trend(sma_data, current_price),
        "volume": _score_volume(vol_ratio),
    }

    # ── Crossover bonus ──
    crossover_bonus = 0
    for cross in crossovers:
        if cross["bias"] == "Bullish":
            crossover_bonus += 5
        else:
            crossover_bonus -= 5

    # ── Weighted composite score ──
    base_score = compute_technical_score(indicator_scores, adx_val)
    result["score"] = max(0, min(100, base_score + crossover_bonus))

    # ── Chart data (last 120 days) ──
    chart_df = df.tail(120).copy()
    chart_df.index = chart_df.index.strftime("%Y-%m-%d")

    result["chart_data"] = {
        "dates": chart_df.index.tolist(),
        "close": [round(v, 2) for v in chart_df["Close"].tolist()],
        "sma_20": [round(v, 2) if not pd.isna(v) else None for v in chart_df.get("SMA_20", pd.Series([None] * len(chart_df))).tolist()],
        "sma_50": [round(v, 2) if not pd.isna(v) else None for v in chart_df.get("SMA_50", pd.Series([None] * len(chart_df))).tolist()],
        "bb_upper": [round(v, 2) if not pd.isna(v) else None for v in chart_df.get("BB_Upper", pd.Series([None] * len(chart_df))).tolist()],
        "bb_lower": [round(v, 2) if not pd.isna(v) else None for v in chart_df.get("BB_Lower", pd.Series([None] * len(chart_df))).tolist()],
        "rsi": [round(v, 2) if not pd.isna(v) else None for v in chart_df.get("RSI", pd.Series([None] * len(chart_df))).tolist()],
        "macd": [round(v, 4) if not pd.isna(v) else None for v in chart_df.get("MACD", pd.Series([None] * len(chart_df))).tolist()],
        "macd_signal": [round(v, 4) if not pd.isna(v) else None for v in chart_df.get("MACD_Signal", pd.Series([None] * len(chart_df))).tolist()],
        "macd_hist": [round(v, 4) if not pd.isna(v) else None for v in chart_df.get("MACD_Hist", pd.Series([None] * len(chart_df))).tolist()],
        "volume": chart_df.get("Volume", pd.Series([0] * len(chart_df))).tolist(),
    }

    return result
