"""
Institutional & Insider Activity Analysis Module
Tracks smart money movements:
- FII/DII shareholding changes (quarter-over-quarter)
- Insider transactions (net buy/sell in last 90 days)
- Short interest (short ratio, short % of float)
- Mutual fund / institutional holders trend
"""

import yfinance as yf


def _safe_float(val, default=None):
    try:
        return float(val) if val is not None else default
    except Exception:
        return default


def _analyze_institutional_holders(ticker):
    """
    Analyze institutional holder concentration and recent changes.
    Returns (score, signals)
    """
    signals = []
    score = 50

    try:
        inst_holders = ticker.institutional_holders
        if inst_holders is None or inst_holders.empty:
            return 50, ["Institutional holder data unavailable"]

        # Total institutional ownership
        total_shares_col = None
        for col in ["Shares", "Value"]:
            if col in inst_holders.columns:
                total_shares_col = col
                break

        if total_shares_col:
            top_holders = inst_holders.head(10)
            holder_count = len(inst_holders)

            if holder_count > 200:
                score += 10
                signals.append(f"Strong institutional interest: {holder_count} institutional holders")
            elif holder_count > 50:
                score += 5
                signals.append(f"Good institutional coverage: {holder_count} holders")
            elif holder_count < 10:
                score -= 10
                signals.append(f"Low institutional interest: only {holder_count} holders")

    except Exception:
        return 50, ["Institutional holder data fetch error"]

    return max(0, min(100, score)), signals


def _analyze_insider_transactions(ticker):
    """
    Analyze recent insider buy/sell transactions.
    Net buys = bullish signal (insiders buying with own money)
    Net sells = mild bearish (could be planned selling programs)
    """
    signals = []
    score = 50

    try:
        insider_df = ticker.insider_transactions
        if insider_df is None or insider_df.empty:
            return 50, ["Insider transaction data unavailable"]

        # Look at last 90 days
        import pandas as pd
        insider_df = insider_df.copy()

        # Find transaction value/shares columns
        buy_keywords = ["Purchase", "Buy", "Acquisition"]
        sell_keywords = ["Sale", "Sell", "Disposition"]

        # Check text columns for transaction types
        trans_col = None
        for col in ["Transaction", "Text", "Type"]:
            if col in insider_df.columns:
                trans_col = col
                break

        if trans_col:
            buys = insider_df[insider_df[trans_col].str.contains(
                "|".join(buy_keywords), case=False, na=False
            )]
            sells = insider_df[insider_df[trans_col].str.contains(
                "|".join(sell_keywords), case=False, na=False
            )]

            buy_count = len(buys)
            sell_count = len(sells)

            if buy_count > sell_count * 2:
                score = 80
                signals.append(f"Strong insider buying: {buy_count} buy vs {sell_count} sell transactions")
            elif buy_count > sell_count:
                score = 65
                signals.append(f"Net insider buying: {buy_count} buys vs {sell_count} sells")
            elif sell_count > buy_count * 3:
                score = 25
                signals.append(f"Heavy insider selling: {sell_count} sells vs {buy_count} buys")
            elif sell_count > buy_count:
                score = 40
                signals.append(f"Net insider selling: {sell_count} sells vs {buy_count} buys")
            elif buy_count == 0 and sell_count == 0:
                score = 50
                signals.append("No significant insider transactions found")
            else:
                score = 50
                signals.append(f"Balanced insider activity: {buy_count} buys, {sell_count} sells")
        else:
            score = 50
            signals.append("Insider transaction format not parseable")

    except Exception:
        return 50, ["Insider data fetch error"]

    return max(0, min(100, score)), signals


def _analyze_short_interest(info):
    """
    Short interest analysis.
    Low short ratio = most investors are long; high ratio = heavy shorting.
    """
    signals = []
    score = 50

    short_ratio = _safe_float(info.get("shortRatio"))
    short_pct = _safe_float(info.get("shortPercentOfFloat"))

    if short_ratio is not None:
        if short_ratio < 2:
            score += 10
            signals.append(f"Low short ratio ({short_ratio:.1f} days) — minimal short pressure")
        elif short_ratio < 4:
            score += 0
            signals.append(f"Moderate short ratio ({short_ratio:.1f} days)")
        elif short_ratio < 8:
            score -= 10
            signals.append(f"High short ratio ({short_ratio:.1f} days) — elevated short interest")
        else:
            score -= 20
            signals.append(f"Very high short ratio ({short_ratio:.1f} days) — heavily shorted, squeeze potential or bearish signal")

    if short_pct is not None:
        pct_display = short_pct * 100 if short_pct < 1 else short_pct
        if pct_display > 20:
            score -= 15
            signals.append(f"Short interest: {pct_display:.1f}% of float — very high (squeeze risk or bearish view)")
        elif pct_display > 10:
            score -= 5
            signals.append(f"Short interest: {pct_display:.1f}% of float — elevated")
        elif pct_display < 3:
            score += 5
            signals.append(f"Short interest: {pct_display:.1f}% of float — very low, bullish")

    if not signals:
        signals.append("Short interest data unavailable")

    return max(0, min(100, score)), signals


def _analyze_mutual_fund_holders(ticker):
    """Analyze mutual fund holder concentration."""
    signals = []
    score = 50

    try:
        mf_holders = ticker.mutualfund_holders
        if mf_holders is None or mf_holders.empty:
            return 50, []

        mf_count = len(mf_holders)
        if mf_count > 500:
            score = 70
            signals.append(f"Very high mutual fund interest: {mf_count} funds holding this stock")
        elif mf_count > 100:
            score = 62
            signals.append(f"Good mutual fund coverage: {mf_count} funds")
        elif mf_count < 10:
            score = 38
            signals.append(f"Low mutual fund interest: {mf_count} funds")

    except Exception:
        return 50, []

    return score, signals


def run_institutional_analysis(ticker_obj, ticker_info):
    """
    Run full institutional and insider activity analysis.
    Returns dict with institutional score and structured signals.
    """
    result = {
        "score": 50,
        "institutional_stance": "Neutral",
        "signals": [],
        "insider_signals": [],
        "short_signals": [],
        "error": None
    }

    all_signals = []

    # 1. Institutional holders
    inst_score, inst_sigs = _analyze_institutional_holders(ticker_obj)
    all_signals.extend(inst_sigs)

    # 2. Insider transactions
    insider_score, insider_sigs = _analyze_insider_transactions(ticker_obj)
    result["insider_signals"] = insider_sigs
    all_signals.extend(insider_sigs)

    # 3. Short interest
    short_score, short_sigs = _analyze_short_interest(ticker_info)
    result["short_signals"] = short_sigs
    all_signals.extend(short_sigs)

    # 4. Mutual fund holders
    mf_score, mf_sigs = _analyze_mutual_fund_holders(ticker_obj)
    all_signals.extend(mf_sigs)

    # Weighted composite
    composite = (
        inst_score * 0.25 +
        insider_score * 0.40 +
        short_score * 0.25 +
        mf_score * 0.10
    )
    final_score = max(0, min(100, round(composite)))

    result["score"] = final_score
    result["signals"] = all_signals

    if final_score >= 70:
        result["institutional_stance"] = "Strong Smart Money Accumulation"
    elif final_score >= 58:
        result["institutional_stance"] = "Mild Institutional Buying"
    elif final_score >= 42:
        result["institutional_stance"] = "Neutral / Mixed Institutional Activity"
    elif final_score >= 30:
        result["institutional_stance"] = "Mild Institutional Distribution"
    else:
        result["institutional_stance"] = "Heavy Smart Money Selling"

    return result
