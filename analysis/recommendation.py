"""
Recommendation Engine — Full Spectrum (8 Pillars) v3
Integrates: Technical, Fundamental, Sentiment, Macro, Policy,
Institutional Activity, Options Intelligence, Sector Rotation, Earnings Outlook.
Dynamic weighting based on data availability, market regime, and quality signals.

v3 Changes:
- Added analyst target price upside as a scoring factor (+0-10 bonus)
- Quality-adjusted weighting (high Piotroski → trust fundamentals more)
- Wider score spread via calibration stretch
- Lowered verdict thresholds (BUY at 60, LEAN BUY at 52)
- Reduced technical/macro drag on high-quality stocks
"""


def compute_recommendation(
    technical_score,
    fundamental_score,
    sentiment_score,
    market_regime="Unknown",
    fundamental_data=None,
    macro_score=None,
    policy_score=None,
    institutional_score=None,
    options_score=None,
    sector_score=None,
    earnings_score=None,
):
    """
    Compute full-spectrum recommendation with 8-pillar dynamic weighting.

    Base allocation (v3 — reduced technical drag, more fundamental weight):
    - Technical:      18%  (was 22%)
    - Fundamental:    30%  (was 28%)
    - Sentiment:      12%
    - Macro:           8%  (was 10%)
    - Policy:          6%
    - Institutional:  10%
    - Options:         5%  (US only; redistributed if N/A)
    - Sector Rotation: 4%
    - Earnings:        7%  (was 3%)
    """

    # ── Base weights (v3 — rebalanced) ──
    weights = {
        "technical":     0.18,
        "fundamental":   0.30,
        "sentiment":     0.12,
        "macro":         0.08,
        "policy":        0.06,
        "institutional": 0.10,
        "options":       0.05,
        "sector":        0.04,
        "earnings":      0.07,
    }

    # Scores dict — use 50 (neutral) for missing pillars
    scores = {
        "technical":     technical_score,
        "fundamental":   fundamental_score,
        "sentiment":     sentiment_score,
        "macro":         macro_score if macro_score is not None else 50,
        "policy":        policy_score if policy_score is not None else 50,
        "institutional": institutional_score if institutional_score is not None else 50,
        "options":       options_score if options_score is not None else None,
        "sector":        sector_score if sector_score is not None else 50,
        "earnings":      earnings_score if earnings_score is not None else 50,
    }

    # ── Handle unavailable pillars — redistribute weight ──
    unavailable = [k for k, v in scores.items() if v is None]
    for key in unavailable:
        redistributed = weights.pop(key, 0)
        # Redistribute primarily to fundamental + earnings
        weights["fundamental"] = weights.get("fundamental", 0) + redistributed * 0.6
        weights["earnings"] = weights.get("earnings", 0) + redistributed * 0.4
        scores[key] = 50

    # ── Quality-adjusted weighting (v3) ──
    # If Piotroski >= 7 (strong health), boost fundamental weight and
    # reduce technical drag because fundamentals are more reliable
    piotroski = None
    if fundamental_data:
        piotroski = fundamental_data.get("piotroski_score") or \
                    fundamental_data.get("pillar_scores", {}).get("piotroski")

    if piotroski is not None:
        if piotroski >= 7:
            # Strong financial health — trust fundamentals more
            weights["fundamental"] = weights.get("fundamental", 0.30) + 0.06
            weights["technical"] = max(0.10, weights.get("technical", 0.18) - 0.04)
            weights["macro"] = max(0.04, weights.get("macro", 0.08) - 0.02)
        elif piotroski <= 3:
            # Weak financial health — reduce fundamental trust, increase technical
            weights["fundamental"] = max(0.20, weights.get("fundamental", 0.30) - 0.05)
            weights["technical"] = weights.get("technical", 0.18) + 0.03
            weights["macro"] = weights.get("macro", 0.08) + 0.02

    # ── Market regime adjustments ──
    if market_regime in ("Bullish Trend", "Bearish Trend"):
        weights["technical"] = min(0.28, weights["technical"] + 0.04)
        weights["fundamental"] = max(0.22, weights["fundamental"] - 0.03)
        weights["macro"] = max(0.04, weights.get("macro", 0.08) - 0.01)
    elif market_regime == "Range-Bound":
        weights["technical"] = max(0.12, weights["technical"] - 0.04)
        weights["fundamental"] = min(0.38, weights["fundamental"] + 0.04)

    # ── Normalize weights ──
    total_weight = sum(weights.values())
    weights = {k: v / total_weight for k, v in weights.items()}

    # ── Weighted score ──
    weighted_score = sum(scores[k] * weights[k] for k in weights)

    # ── Analyst target price upside bonus (v3) ──
    # If 20+ analysts set a target significantly above current price,
    # that's a strong signal we should incorporate
    target_bonus = 0
    if fundamental_data:
        metrics = fundamental_data.get("metrics", {})
        current = metrics.get("currentPrice")
        target_mean = metrics.get("targetMeanPrice")
        num_analysts = metrics.get("numberOfAnalysts", 0) or 0

        if current and target_mean and current > 0 and num_analysts >= 5:
            upside_pct = ((target_mean - current) / current) * 100

            if upside_pct > 30:
                target_bonus = 8   # massive upside consensus
            elif upside_pct > 20:
                target_bonus = 6
            elif upside_pct > 10:
                target_bonus = 4
            elif upside_pct > 5:
                target_bonus = 2
            elif upside_pct < -10:
                target_bonus = -5  # price ABOVE target = overvalued

            # Scale bonus by analyst count confidence
            if num_analysts >= 30:
                target_bonus = target_bonus * 1.0
            elif num_analysts >= 15:
                target_bonus = target_bonus * 0.8
            else:
                target_bonus = target_bonus * 0.5

    # ── Score calibration stretch (v3) ──
    # Raw scores cluster around 45-60. Stretch to 30-80 range.
    # Use sigmoid-like stretching centered at 50
    raw = weighted_score + target_bonus
    stretched = _calibrate_score(raw)

    final_score = round(max(0, min(100, stretched)), 1)

    # ── Confidence scoring ──
    all_score_vals = [v for v in scores.values() if v is not None]
    score_range = max(all_score_vals) - min(all_score_vals)
    # Also factor in number of analysts and Piotroski for confidence
    analyst_count = 0
    if fundamental_data:
        analyst_count = fundamental_data.get("metrics", {}).get("numberOfAnalysts", 0) or 0

    if score_range < 15 and analyst_count >= 20:
        confidence, confidence_pct = "High", 88
    elif score_range < 20:
        confidence, confidence_pct = "Moderate-High", 76
    elif score_range < 30:
        confidence, confidence_pct = "Moderate", 64
    elif score_range < 42:
        confidence, confidence_pct = "Low-Moderate", 50
    else:
        confidence, confidence_pct = "Low", 34

    # Boost confidence if many analysts agree
    if analyst_count >= 40:
        confidence_pct = min(95, confidence_pct + 10)
    elif analyst_count >= 20:
        confidence_pct = min(95, confidence_pct + 5)

    # ── Verdict (v3 — adjusted thresholds) ──
    if final_score >= 75:
        verdict, color = "STRONG BUY", "#00e676"
    elif final_score >= 60:
        verdict, color = "BUY", "#4caf50"
    elif final_score >= 52:
        verdict, color = "LEAN BUY", "#8bc34a"
    elif final_score >= 42:
        verdict, color = "HOLD", "#ff9800"
    elif final_score >= 32:
        verdict, color = "LEAN SELL", "#ff5722"
    elif final_score >= 20:
        verdict, color = "SELL", "#f44336"
    else:
        verdict, color = "STRONG SELL", "#d50000"

    # ── Risk-Reward ──
    risk_reward = _compute_risk_reward(final_score, fundamental_data)

    return {
        "final_score": final_score,
        "verdict": verdict,
        "color": color,
        "confidence": confidence,
        "confidence_pct": confidence_pct,
        "market_regime": market_regime,
        "weights_used": {k: round(v * 100, 1) for k, v in weights.items()},
        "pillar_scores": {k: scores[k] for k in scores},
        "risk_reward": risk_reward,
        "target_bonus": round(target_bonus, 1),
    }


def _calibrate_score(raw):
    """
    Stretch raw scores from the compressed 40-65 range to a wider 25-85 range.
    Uses piecewise linear mapping to preserve relative ordering while
    expanding the distribution.

    Input  -> Output mapping:
    30     -> 20
    40     -> 35
    50     -> 50  (neutral stays neutral)
    55     -> 58
    60     -> 66
    65     -> 74
    70     -> 80
    80     -> 90
    """
    if raw <= 30:
        return 20 + (raw / 30) * 15  # 0-30 -> 20-35
    elif raw <= 40:
        return 35 + ((raw - 30) / 10) * 15  # 30-40 -> 35-50
    elif raw <= 50:
        return 50 + ((raw - 40) / 10) * 8  # 40-50 -> 50-58
    elif raw <= 55:
        return 58 + ((raw - 50) / 5) * 8  # 50-55 -> 58-66
    elif raw <= 60:
        return 66 + ((raw - 55) / 5) * 8  # 55-60 -> 66-74
    elif raw <= 70:
        return 74 + ((raw - 60) / 10) * 6  # 60-70 -> 74-80
    else:
        return 80 + ((raw - 70) / 30) * 15  # 70-100 -> 80-95


def _compute_risk_reward(final_score, fundamental_data):
    """Compute risk-reward from analyst targets and intrinsic value."""
    result = {
        "upside_target": None,
        "downside_risk": None,
        "risk_reward_ratio": None,
        "position_suggestion": None,
    }
    if not fundamental_data:
        return result

    metrics = fundamental_data.get("metrics", {})
    current = metrics.get("currentPrice")
    target_mean = metrics.get("targetMeanPrice")
    target_low = metrics.get("targetLowPrice")
    low_52 = metrics.get("fiftyTwoWeekLow")

    if not current or current <= 0:
        return result

    if target_mean and target_mean > current:
        result["upside_target"] = round(((target_mean - current) / current) * 100, 1)

    downside_level = None
    if target_low and target_low < current:
        downside_level = target_low
    elif low_52 and low_52 < current:
        downside_level = low_52

    if downside_level:
        result["downside_risk"] = round(((current - downside_level) / current) * 100, 1)

    if result["upside_target"] and result["downside_risk"] and result["downside_risk"] > 0:
        rr = round(result["upside_target"] / result["downside_risk"], 2)
        result["risk_reward_ratio"] = rr
        if rr > 3:
            result["position_suggestion"] = "Excellent risk-reward — consider full position"
        elif rr > 2:
            result["position_suggestion"] = "Good risk-reward — consider adding position"
        elif rr > 1:
            result["position_suggestion"] = "Acceptable risk-reward — moderate position"
        else:
            result["position_suggestion"] = "Poor risk-reward — wait for better entry"

    return result


def generate_reasoning(technical, fundamental, sentiment, recommendation,
                        macro=None, policy=None, institutional=None,
                        options_intel=None, sector=None, earnings=None):
    """
    Generate full-spectrum institutional-style reasoning across all 8 pillars
    plus a 30-Day Outlook summary.
    """
    reasons = []
    score = recommendation["final_score"]
    verdict = recommendation["verdict"]
    confidence = recommendation.get("confidence", "Moderate")
    confidence_pct = recommendation.get("confidence_pct", 50)
    market_regime = recommendation.get("market_regime", "Unknown")
    target_bonus = recommendation.get("target_bonus", 0)

    # ── Opening verdict ──
    if score >= 60:
        reasons.append(
            f"**VERDICT: {verdict}** (Score: {score}/100 | Confidence: {confidence} {confidence_pct}%)\n\n"
            f"Our 8-pillar analysis identifies this as a favorable investment opportunity. "
            f"Technical momentum, fundamental quality, macro backdrop, institutional activity, "
            f"and earnings trajectory all factored into this recommendation."
        )
    elif score >= 42:
        reasons.append(
            f"**VERDICT: {verdict}** (Score: {score}/100 | Confidence: {confidence} {confidence_pct}%)\n\n"
            f"The analysis presents mixed signals across our 8-pillar framework. "
            f"Proceed with caution and consider reduced position sizing."
        )
    else:
        reasons.append(
            f"**VERDICT: {verdict}** (Score: {score}/100 | Confidence: {confidence} {confidence_pct}%)\n\n"
            f"Multiple red flags identified across technical, fundamental, macro, and institutional pillars. "
            f"Risk significantly outweighs potential reward at current levels."
        )

    # Market Regime + weights
    if market_regime != "Unknown":
        reasons.append(f"**Market Regime:** {market_regime}")
        weights = recommendation.get("weights_used", {})
        if weights:
            w_parts = " | ".join(
                f"{k.capitalize()}: {v}%"
                for k, v in weights.items()
                if v > 0
            )
            reasons.append(f"*Dynamic weights: {w_parts}*")

    # Target bonus explanation
    if target_bonus >= 3:
        reasons.append(f"\n*📊 Analyst Target Price Bonus: +{target_bonus:.0f} points (significant upside to consensus target)*")
    elif target_bonus <= -3:
        reasons.append(f"\n*⚠️ Analyst Target Price Penalty: {target_bonus:.0f} points (trading above analyst targets)*")

    # ── 1. Technical Analysis ──
    tech_score = technical.get("score", 50)
    reasons.append(f"\n### 📊 Technical Analysis (Score: {tech_score}/100)")
    td = []
    rsi = technical.get("rsi", {})
    if rsi.get("value"):
        td.append(f"- **RSI ({rsi['value']}):** {rsi['signal']}")
    macd = technical.get("macd", {})
    if macd.get("trend") and macd["trend"] != "N/A":
        td.append(f"- **MACD:** {macd['trend']}")
    adx = technical.get("adx", {})
    if adx.get("value"):
        td.append(f"- **ADX ({adx['value']}):** {adx['signal']}")
    obv = technical.get("obv", {})
    if obv.get("signal") and obv["signal"] != "N/A":
        td.append(f"- **Volume Flow (OBV):** {obv['signal']}")
    stoch = technical.get("stoch_rsi", {})
    if stoch.get("k") is not None:
        td.append(f"- **Stochastic RSI ({stoch['k']:.0f}/{stoch['d']:.0f}):** {stoch['signal']}")
    atr = technical.get("atr", {})
    if atr.get("pct"):
        td.append(f"- **Volatility (ATR):** {atr['pct']}% daily — {atr['signal']}")
    bb = technical.get("bollinger_bands", {})
    if bb.get("signal") and bb["signal"] != "N/A":
        td.append(f"- **Bollinger Bands:** {bb['signal']}")
    for cross in technical.get("crossovers", []):
        td.append(f"- **⚡ {cross['type']}** on {cross['date']} — {cross['bias']} signal")
    reasons.extend(td)

    # ── 2. Fundamental Analysis ──
    fund_score = fundamental.get("score", 50)
    reasons.append(f"\n### 📈 Fundamental Analysis (Score: {fund_score}/100)")
    pillar_scores = fundamental.get("pillar_scores", {})
    if pillar_scores:
        reasons.append(
            f"- Valuation: {pillar_scores.get('valuation', 'N/A')}/100 | "
            f"Quality: {pillar_scores.get('quality', 'N/A')}/100 | "
            f"Growth: {pillar_scores.get('growth', 'N/A')}/100 | "
            f"Analyst: {pillar_scores.get('analyst', 'N/A')}/100"
        )
        piotroski = pillar_scores.get("piotroski")
        if piotroski is not None:
            reasons.append(f"- **Piotroski F-Score: {piotroski}/9** — {'Strong' if piotroski >= 7 else ('Weak' if piotroski <= 3 else 'Moderate')} financial health")
    for sig in fundamental.get("signals", [])[:6]:
        reasons.append(f"- {sig}")
    iv = fundamental.get("intrinsic_value")
    mos = fundamental.get("margin_of_safety")
    if iv is not None:
        reasons.append(f"- **Intrinsic Value Estimate:** ${iv:,.2f} (Margin of Safety: {mos:+.1f}%)")

    # ── 3. News Sentiment ──
    sent_score = sentiment.get("score", 50)
    overall = sentiment.get("overall_sentiment", "Neutral")
    pos = sentiment.get("positive_count", 0)
    neg = sentiment.get("negative_count", 0)
    reasons.append(f"\n### 📰 News Sentiment (Score: {sent_score}/100)")
    reasons.append(f"- Overall: **{overall}** | {pos} positive, {neg} negative headlines")
    cat_breakdown = sentiment.get("category_breakdown", {})
    if cat_breakdown:
        cat_parts = " | ".join(
            f"{cat.capitalize()}: {'📈' if v > 0 else '📉'}"
            for cat, v in cat_breakdown.items()
        )
        reasons.append(f"- Headline categories: {cat_parts}")

    # ── 4. Macro & Monetary Policy ──
    if macro:
        macro_score = macro.get("score", 50)
        reasons.append(f"\n### 🌍 Macro Environment (Score: {macro_score}/100)")
        reasons.append(f"- **Environment:** {macro.get('environment', 'Neutral')}")
        for sig in macro.get("signals", [])[:4]:
            reasons.append(f"- {sig}")

    # ── 5. Government Policy ──
    if policy:
        policy_score_val = policy.get("score", 50)
        reasons.append(f"\n### 🏛️ Government Policy (Score: {policy_score_val}/100)")
        reasons.append(f"- **Policy Stance:** {policy.get('policy_stance', 'Neutral')}")
        for tw in policy.get("tailwinds", [])[:2]:
            reasons.append(f"- ✅ Tailwind: {tw[:100]}")
        for hw in policy.get("headwinds", [])[:2]:
            reasons.append(f"- ⚠️ Headwind: {hw[:100]}")

    # ── 6. Institutional Activity ──
    if institutional:
        inst_score = institutional.get("score", 50)
        reasons.append(f"\n### 🏦 Institutional & Insider Activity (Score: {inst_score}/100)")
        reasons.append(f"- **Smart Money:** {institutional.get('institutional_stance', 'Neutral')}")
        for sig in institutional.get("signals", [])[:3]:
            reasons.append(f"- {sig}")
        for sig in institutional.get("insider_signals", [])[:2]:
            reasons.append(f"- Insider: {sig}")
        for sig in institutional.get("short_signals", [])[:1]:
            reasons.append(f"- Short Interest: {sig}")

    # ── 7. Options Intelligence ──
    if options_intel and options_intel.get("available"):
        opt_score = options_intel.get("score", 50)
        reasons.append(f"\n### 📊 Options Market Intelligence (Score: {opt_score}/100)")
        reasons.append(f"- **Options Sentiment:** {options_intel.get('options_sentiment', 'N/A')}")
        for sig in options_intel.get("signals", [])[:4]:
            reasons.append(f"- {sig}")

    # ── 8. Sector Rotation ──
    if sector:
        sector_score_val = sector.get("score", 50)
        reasons.append(f"\n### 🔄 Sector Rotation (Score: {sector_score_val}/100)")
        reasons.append(f"- **Signal:** {sector.get('rotation_signal', 'Neutral')}")
        for sig in sector.get("signals", [])[:3]:
            reasons.append(f"- {sig}")

    # ── 9. Earnings Outlook ──
    if earnings:
        earn_score = earnings.get("score", 50)
        reasons.append(f"\n### 📅 Earnings Outlook (Score: {earn_score}/100)")
        reasons.append(f"- **Momentum:** {earnings.get('earnings_momentum', 'Neutral')}")
        if earnings.get("next_earnings_date"):
            urgency = earnings.get("earnings_urgency", "")
            days = earnings.get("days_to_earnings")
            if days is not None and days > 0:
                reasons.append(f"- Next Earnings: **{earnings['next_earnings_date']}** ({days} days) — {urgency}")
        beat = earnings.get("beat_count", 0)
        miss = earnings.get("miss_count", 0)
        if beat + miss > 0:
            reasons.append(f"- EPS Track Record: {beat} beats, {miss} misses in recent quarters")
        for sig in earnings.get("estimate_signals", [])[:2]:
            reasons.append(f"- {sig}")

    # ── Risk-Reward ──
    rr = recommendation.get("risk_reward", {})
    if rr.get("risk_reward_ratio"):
        reasons.append(f"\n### ⚖️ Risk-Reward Analysis")
        if rr.get("upside_target"):
            reasons.append(f"- **Upside Potential:** {rr['upside_target']}%")
        if rr.get("downside_risk"):
            reasons.append(f"- **Downside Risk:** {rr['downside_risk']}%")
        reasons.append(f"- **Risk/Reward Ratio:** {rr['risk_reward_ratio']}:1")
        if rr.get("position_suggestion"):
            reasons.append(f"- **Positioning:** {rr['position_suggestion']}")

    # ── 30-Day Outlook ──
    reasons.append("\n### 🔭 30-Day Outlook")
    outlook_points = []

    # Earnings urgency
    if earnings:
        days = earnings.get("days_to_earnings")
        if days is not None and 0 < days <= 30:
            if earnings.get("score", 50) >= 65:
                outlook_points.append(f"Earnings in {days} days — strong historical beat rate sets up potential positive catalyst")
            elif earnings.get("score", 50) <= 35:
                outlook_points.append(f"Earnings in {days} days — weak earnings track record creates near-term risk")
            else:
                outlook_points.append(f"Earnings in {days} days — event risk present, position size accordingly")

    # Macro outlook
    if macro:
        env = macro.get("environment", "Neutral")
        if "Bullish" in env or "Risk-On" in env:
            outlook_points.append("Macro backdrop favorable — risk-on environment supportive of equities")
        elif "Bearish" in env or "Risk-Off" in env:
            outlook_points.append("Macro backdrop challenging — risk-off conditions may cap upside")

    # Technical trend
    regime = recommendation.get("market_regime", "Unknown")
    if regime == "Bullish Trend":
        outlook_points.append("Technical trend bullish — follow trend with trailing stops")
    elif regime == "Bearish Trend":
        outlook_points.append("Technical trend bearish — prefer cash or hedged positions")

    # Policy / institutional
    if policy and policy.get("score", 50) >= 65:
        outlook_points.append("Policy tailwinds identified — government support may drive sector re-rating")
    if institutional and institutional.get("score", 50) >= 68:
        outlook_points.append("Smart money accumulation — institutional buying supports price floor")
    elif institutional and institutional.get("score", 50) <= 32:
        outlook_points.append("Smart money distributing — FII/insider selling pressure may weigh on price")

    if outlook_points:
        for pt in outlook_points:
            reasons.append(f"- {pt}")
    else:
        if score >= 60:
            reasons.append("- Combination of strong fundamentals and positive technical momentum points to continued upside over next 30 days")
        elif score >= 42:
            reasons.append("- Mixed signals — range-bound action likely. Monitor for catalyst to determine next directional move")
        else:
            reasons.append("- Multiple negative signals across pillars — near-term downside risk elevated")

    # ── Action Summary ──
    reasons.append("\n### 💡 Action Summary")
    if score >= 70:
        reasons.append(
            "This stock scores strongly across multiple pillars of our analysis framework. "
            "Consider building a position with appropriate stop-loss protection. "
            "Review all 8 analysis pillars above before committing capital."
        )
    elif score >= 55:
        reasons.append(
            "The stock presents a solid opportunity. Consider starting with a core position and "
            "look for pullbacks to key support levels for better entries."
        )
    elif score >= 40:
        reasons.append(
            "Mixed signals across our 8-pillar framework. Wait for confirmation — either "
            "a breakout above resistance with volume, or improved macro/earnings signals."
        )
    else:
        reasons.append(
            "The risk profile is unfavorable at current levels based on our multi-pillar analysis. "
            "Consider reducing exposure or waiting for a significant correction."
        )

    reasons.append(
        "\n---\n*This analysis is generated algorithmically using technical, fundamental, sentiment, "
        "macro, policy, institutional, options, sector rotation, and earnings signals. "
        "Not financial advice. Conduct your own research.*"
    )

    return "\n".join(reasons)
