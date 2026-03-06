"""
Earnings Calendar & Forward Outlook Module
Tracks upcoming earnings, historical EPS surprises, and analyst estimate revisions.
Produces an earnings momentum score (0-100) and forward outlook summary.
"""

import yfinance as yf
from datetime import datetime, timezone


def _safe_get(d, key, default=None):
    try:
        val = d.get(key, default)
        return val if val is not None else default
    except Exception:
        return default


def _fetch_next_earnings_date(ticker_obj):
    """Get next earnings date from ticker calendar."""
    try:
        cal = ticker_obj.calendar
        if cal is None:
            return None

        # calendar can be a dict or DataFrame
        if isinstance(cal, dict):
            # Try different key names
            for key in ["Earnings Date", "earningsDate", "Earnings Dates"]:
                if key in cal:
                    val = cal[key]
                    if hasattr(val, '__iter__') and not isinstance(val, str):
                        val = list(val)[0]
                    if hasattr(val, 'date'):
                        return val.date()
                    try:
                        return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
                    except Exception:
                        continue
        else:
            # DataFrame format
            try:
                if hasattr(cal, 'columns'):
                    for col in cal.columns:
                        if 'earn' in col.lower():
                            val = cal[col].iloc[0]
                            if hasattr(val, 'date'):
                                return val.date()
            except Exception:
                pass
    except Exception:
        pass
    return None


def _analyze_earnings_history(ticker_obj):
    """
    Analyze recent EPS surprise history.
    Returns (score, signals, beat_count, miss_count).
    """
    try:
        hist = ticker_obj.earnings_history
        if hist is None or (hasattr(hist, 'empty') and hist.empty):
            return 50, ["Earnings history unavailable"], 0, 0

        # Column names vary
        import pandas as pd
        df = hist.copy() if hasattr(hist, 'copy') else pd.DataFrame(hist)

        # Find relevant columns
        eps_actual_col = None
        eps_est_col = None
        for col in df.columns:
            cl = col.lower()
            if 'actual' in cl and 'eps' in cl:
                eps_actual_col = col
            elif 'estimate' in cl and 'eps' in cl:
                eps_est_col = col

        if eps_actual_col is None or eps_est_col is None:
            # Try simpler column names
            if "epsActual" in df.columns and "epsEstimate" in df.columns:
                eps_actual_col, eps_est_col = "epsActual", "epsEstimate"
            elif "Reported EPS" in df.columns and "EPS Estimate" in df.columns:
                eps_actual_col, eps_est_col = "Reported EPS", "EPS Estimate"
            else:
                return 50, ["EPS column format not recognized"], 0, 0

        beat_count = 0
        miss_count = 0
        beat_pcts = []
        signals = []

        recent = df.tail(8)  # Last 8 quarters
        for _, row in recent.iterrows():
            actual = _safe_get(row, eps_actual_col)
            estimate = _safe_get(row, eps_est_col)
            if actual is not None and estimate is not None:
                try:
                    actual_f = float(actual)
                    est_f = float(estimate)
                    if est_f != 0:
                        surprise_pct = ((actual_f - est_f) / abs(est_f)) * 100
                    else:
                        surprise_pct = 0
                    if surprise_pct > 0:
                        beat_count += 1
                        beat_pcts.append(surprise_pct)
                    else:
                        miss_count += 1
                except Exception:
                    continue

        total = beat_count + miss_count
        if total == 0:
            return 50, ["No EPS data found"], 0, 0

        beat_rate = beat_count / total
        avg_beat = sum(beat_pcts) / len(beat_pcts) if beat_pcts else 0

        score = 50
        if beat_rate >= 0.875:  # 7/8 beats
            score = 88
            signals.append(f"Exceptional earnings track record: {beat_count}/{total} quarters beat estimates (avg +{avg_beat:.1f}%)")
        elif beat_rate >= 0.75:
            score = 75
            signals.append(f"Strong earner: {beat_count}/{total} quarters beat estimates (avg +{avg_beat:.1f}%)")
        elif beat_rate >= 0.625:
            score = 62
            signals.append(f"Usually beats estimates: {beat_count}/{total} quarters")
        elif beat_rate >= 0.5:
            score = 52
            signals.append(f"Mixed earnings track record: {beat_count}/{total} beats")
        elif beat_rate >= 0.375:
            score = 38
            signals.append(f"Often misses estimates: {miss_count} misses vs {beat_count} beats")
        else:
            score = 22
            signals.append(f"Poor earnings track record: only {beat_count}/{total} beats")

        return max(0, min(100, score)), signals, beat_count, miss_count

    except Exception as e:
        return 50, [f"Earnings history parse error"], 0, 0


def _analyze_estimate_revisions(ticker_info):
    """
    Check if analysts are raising or lowering EPS estimates.
    Uses forward PE improvement as a proxy for estimate revision direction.
    """
    signals = []
    score = 50

    trailing_pe = _safe_get(ticker_info, "trailingPE")
    forward_pe = _safe_get(ticker_info, "forwardPE")
    rev_growth = _safe_get(ticker_info, "revenueGrowth")
    earn_growth = _safe_get(ticker_info, "earningsGrowth")
    earn_quarterly = _safe_get(ticker_info, "earningsQuarterlyGrowth")

    if trailing_pe and forward_pe and trailing_pe > 0 and forward_pe > 0:
        improvement = ((trailing_pe - forward_pe) / trailing_pe) * 100
        if improvement > 20:
            score += 20
            signals.append(f"Earnings estimates rising sharply — {improvement:.0f}% improvement in forward EPS expected")
        elif improvement > 8:
            score += 10
            signals.append(f"Earnings estimates improving — forward EPS expected to grow")
        elif improvement < -15:
            score -= 15
            signals.append(f"Earnings estimates declining — forward PE higher than trailing (EPS expected to fall)")
        elif improvement < -5:
            score -= 8
            signals.append(f"Mild downward earnings revision expected")

    if earn_quarterly is not None:
        qg = earn_quarterly * 100
        if qg > 30:
            score += 12
            signals.append(f"Strong quarterly earnings growth: {qg:.1f}% YoY")
        elif qg > 10:
            score += 6
            signals.append(f"Solid quarterly earnings growth: {qg:.1f}%")
        elif qg < 0:
            score -= 8
            signals.append(f"Earnings declining quarter-over-quarter: {qg:.1f}%")

    if not signals:
        signals.append("Estimate revision data limited")

    return max(0, min(100, score)), signals


def run_earnings_outlook(ticker_obj, ticker_info):
    """
    Full earnings calendar and forward outlook analysis.
    Returns dict with earnings score, next date, surprise history, estimate trend.
    """
    result = {
        "score": 50,
        "earnings_momentum": "Neutral",
        "next_earnings_date": None,
        "days_to_earnings": None,
        "earnings_urgency": "Normal",
        "beat_count": 0,
        "miss_count": 0,
        "signals": [],
        "estimate_signals": []
    }

    all_signals = []

    # 1. Next earnings date
    next_date = _fetch_next_earnings_date(ticker_obj)
    if next_date:
        result["next_earnings_date"] = str(next_date)
        today = datetime.now(timezone.utc).date()
        days_to = (next_date - today).days
        result["days_to_earnings"] = days_to
        if days_to <= 0:
            all_signals.append("⚠️ Earnings already passed or imminent — check recent reports")
            result["earnings_urgency"] = "Passed/Imminent"
        elif days_to <= 7:
            all_signals.append(f"🔔 Earnings in {days_to} days — high near-term event risk/opportunity")
            result["earnings_urgency"] = "Imminent (≤7 days)"
        elif days_to <= 21:
            all_signals.append(f"📅 Earnings in {days_to} days — watch for pre-earnings momentum")
            result["earnings_urgency"] = "Soon (≤21 days)"
        else:
            all_signals.append(f"Earnings due in {days_to} days")
            result["earnings_urgency"] = "Normal"
    else:
        all_signals.append("Earnings date not currently available")

    # 2. EPS surprise history
    hist_score, hist_sigs, beat_count, miss_count = _analyze_earnings_history(ticker_obj)
    result["beat_count"] = beat_count
    result["miss_count"] = miss_count
    all_signals.extend(hist_sigs)

    # 3. Estimate revisions
    rev_score, rev_sigs = _analyze_estimate_revisions(ticker_info)
    result["estimate_signals"] = rev_sigs
    all_signals.extend(rev_sigs)

    # Composite score
    composite = hist_score * 0.55 + rev_score * 0.45
    final_score = max(0, min(100, round(composite)))

    # Urgency modifier — approaching earnings raises stakes
    days_to = result.get("days_to_earnings")
    if days_to is not None and 0 < days_to <= 7:
        if final_score >= 65:
            final_score = min(100, final_score + 5)  # pre-earnings boost for strong earner
        elif final_score <= 35:
            final_score = max(0, final_score - 5)  # pre-earnings risk for weak earner

    result["score"] = final_score
    result["signals"] = all_signals

    if final_score >= 72:
        result["earnings_momentum"] = "Strong Earnings Momentum"
    elif final_score >= 58:
        result["earnings_momentum"] = "Positive Earnings Track Record"
    elif final_score >= 42:
        result["earnings_momentum"] = "Mixed Earnings History"
    elif final_score >= 28:
        result["earnings_momentum"] = "Weak Earnings Trend"
    else:
        result["earnings_momentum"] = "Poor Earnings Track Record"

    return result
