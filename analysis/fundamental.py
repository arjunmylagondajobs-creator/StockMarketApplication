"""
Fundamental Analysis Module — Institutional Grade
Multi-pillar scoring: Valuation (35%), Quality (30%), Growth (20%), Analyst Consensus (15%).
Includes FCF yield, ROIC, earnings quality, sector-relative P/E, DCF-lite, analyst integration.
"""


# Sector-average P/E ratios (approximate medians from institutional data)
SECTOR_PE_BENCHMARKS = {
    "Technology": 28,
    "Communication Services": 22,
    "Consumer Cyclical": 20,
    "Consumer Defensive": 22,
    "Healthcare": 24,
    "Financial Services": 14,
    "Industrials": 20,
    "Energy": 12,
    "Utilities": 18,
    "Real Estate": 35,
    "Basic Materials": 15,
}

DEFAULT_SECTOR_PE = 20


def safe_get(info, key, default=None):
    """Safely get a value from the info dict."""
    val = info.get(key, default)
    if val is None:
        return default
    return val


# ═══════════════════════════════════════════════════════════
# VALUATION PILLAR (35% of total)
# ═══════════════════════════════════════════════════════════

def _score_pe_valuation(info, sector):
    """Score P/E ratio relative to sector benchmark."""
    score = 50
    signals = []

    pe = safe_get(info, "trailingPE")
    forward_pe = safe_get(info, "forwardPE")
    sector_pe = SECTOR_PE_BENCHMARKS.get(sector, DEFAULT_SECTOR_PE)

    if pe and pe > 0:
        # Score relative to sector average
        pe_ratio_to_sector = pe / sector_pe
        if pe_ratio_to_sector < 0.6:
            score = 90
            signals.append(f"P/E ({pe:.1f}) deeply below sector avg ({sector_pe}) — significantly undervalued")
        elif pe_ratio_to_sector < 0.85:
            score = 75
            signals.append(f"P/E ({pe:.1f}) below sector avg ({sector_pe}) — attractively valued")
        elif pe_ratio_to_sector < 1.15:
            score = 55
            signals.append(f"P/E ({pe:.1f}) near sector avg ({sector_pe}) — fairly valued")
        elif pe_ratio_to_sector < 1.5:
            score = 35
            signals.append(f"P/E ({pe:.1f}) above sector avg ({sector_pe}) — premium valuation")
        else:
            score = 15
            signals.append(f"P/E ({pe:.1f}) far above sector avg ({sector_pe}) — expensive")
    elif pe and pe < 0:
        score = 15
        signals.append("Negative P/E — company is unprofitable")
    else:
        signals.append("P/E data unavailable")

    # Forward P/E improvement bonus
    if forward_pe and pe and forward_pe > 0 and pe > 0:
        improvement = (pe - forward_pe) / pe * 100
        if improvement > 15:
            score = min(100, score + 10)
            signals.append(f"Forward P/E ({forward_pe:.1f}) shows {improvement:.0f}% earnings growth expected")
        elif improvement > 5:
            score = min(100, score + 5)
        elif improvement < -10:
            score = max(0, score - 5)
            signals.append(f"Forward P/E ({forward_pe:.1f}) higher — earnings decline expected")

    return score, signals


def _score_peg(info):
    """Score PEG ratio — the gold standard valuation-to-growth metric."""
    peg = safe_get(info, "pegRatio")
    if not peg or peg <= 0:
        return 50, []

    if peg < 0.75:
        return 90, [f"PEG ({peg:.2f}) < 0.75 — significantly undervalued vs growth"]
    elif peg < 1.0:
        return 75, [f"PEG ({peg:.2f}) < 1.0 — undervalued relative to growth"]
    elif peg < 1.5:
        return 55, [f"PEG ({peg:.2f}) — fairly priced for growth"]
    elif peg < 2.5:
        return 35, [f"PEG ({peg:.2f}) — growth already priced in"]
    else:
        return 15, [f"PEG ({peg:.2f}) > 2.5 — overpriced relative to growth"]


def _score_fcf_yield(info):
    """
    Free Cash Flow Yield = FCF / Market Cap.
    Institutional investors consider this the #1 valuation metric.
    """
    fcf = safe_get(info, "freeCashflow")
    market_cap = safe_get(info, "marketCap")

    if not fcf or not market_cap or market_cap <= 0:
        return 50, []

    fcf_yield = (fcf / market_cap) * 100

    if fcf_yield > 8:
        return 90, [f"FCF yield {fcf_yield:.1f}% — excellent cash generation"]
    elif fcf_yield > 5:
        return 75, [f"FCF yield {fcf_yield:.1f}% — strong free cash flow"]
    elif fcf_yield > 3:
        return 60, [f"FCF yield {fcf_yield:.1f}% — decent cash flow"]
    elif fcf_yield > 0:
        return 40, [f"FCF yield {fcf_yield:.1f}% — low but positive"]
    else:
        return 15, [f"Negative FCF yield ({fcf_yield:.1f}%) — burning cash"]


def _estimate_intrinsic_value(info):
    """
    Simplified DCF-lite intrinsic value estimate.
    Uses current FCF, projected growth, and terminal multiple.
    """
    fcf = safe_get(info, "freeCashflow")
    shares = safe_get(info, "sharesOutstanding")
    growth = safe_get(info, "revenueGrowth")
    current_price = safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice")

    if not fcf or not shares or shares <= 0 or not current_price or fcf <= 0:
        return None, None, []

    # Cap growth rate at reasonable bounds
    if growth is None:
        growth = 0.05  # assume 5% if unknown
    growth = max(-0.10, min(growth, 0.30))  # cap between -10% and 30%

    # Decay growth toward 3% terminal rate over 5 years
    terminal_growth = 0.03
    discount_rate = 0.10  # 10% required return (institutional standard)

    projected_fcf = []
    current_fcf = fcf
    for year in range(1, 6):
        year_growth = growth + (terminal_growth - growth) * (year / 5)
        current_fcf = current_fcf * (1 + year_growth)
        projected_fcf.append(current_fcf / (1 + discount_rate) ** year)

    # Terminal value (year 5 FCF * terminal multiple)
    terminal_multiple = 15  # Conservative
    terminal_value = (projected_fcf[-1] * (1 + discount_rate) ** 5 * terminal_multiple) / (1 + discount_rate) ** 5

    intrinsic_total = sum(projected_fcf) + terminal_value
    intrinsic_per_share = round(intrinsic_total / shares, 2)

    margin_of_safety = round(((intrinsic_per_share - current_price) / current_price) * 100, 1)

    signals = []
    if margin_of_safety > 30:
        signals.append(f"DCF estimate: {_format_currency(intrinsic_per_share)} ({margin_of_safety}% upside) — significant margin of safety")
    elif margin_of_safety > 10:
        signals.append(f"DCF estimate: {_format_currency(intrinsic_per_share)} ({margin_of_safety}% upside) — moderate upside")
    elif margin_of_safety > -10:
        signals.append(f"DCF estimate: {_format_currency(intrinsic_per_share)} — roughly fair value")
    else:
        signals.append(f"DCF estimate: {_format_currency(intrinsic_per_share)} ({margin_of_safety}% downside) — overvalued")

    return intrinsic_per_share, margin_of_safety, signals


def _compute_valuation_score(info, sector):
    """Combine all valuation metrics into a single 0-100 score."""
    pe_score, pe_signals = _score_pe_valuation(info, sector)
    peg_score, peg_signals = _score_peg(info)
    fcf_score, fcf_signals = _score_fcf_yield(info)

    # Weight: P/E relative (40%), PEG (30%), FCF yield (30%)
    has_peg = safe_get(info, "pegRatio") is not None
    has_fcf = safe_get(info, "freeCashflow") is not None

    if has_peg and has_fcf:
        score = pe_score * 0.35 + peg_score * 0.30 + fcf_score * 0.35
    elif has_peg:
        score = pe_score * 0.45 + peg_score * 0.55
    elif has_fcf:
        score = pe_score * 0.45 + fcf_score * 0.55
    else:
        score = pe_score

    return round(score), pe_signals + peg_signals + fcf_signals


# ═══════════════════════════════════════════════════════════
# QUALITY PILLAR (30% of total)
# ═══════════════════════════════════════════════════════════

def _score_profitability(info):
    """Score profit margins and ROE."""
    score = 50
    signals = []

    pm = safe_get(info, "profitMargins")
    if pm is not None:
        pm_pct = pm * 100
        if pm > 0.25:
            score = 85
            signals.append(f"Excellent profit margin ({pm_pct:.1f}%) — strong pricing power")
        elif pm > 0.15:
            score = 70
            signals.append(f"Good profit margin ({pm_pct:.1f}%)")
        elif pm > 0.08:
            score = 55
            signals.append(f"Moderate profit margin ({pm_pct:.1f}%)")
        elif pm > 0:
            score = 35
            signals.append(f"Thin profit margin ({pm_pct:.1f}%)")
        else:
            score = 10
            signals.append(f"Negative margin ({pm_pct:.1f}%) — losing money")

    return score, signals


def _score_roic(info):
    """
    Return on Invested Capital — better than ROE for cross-sector comparison.
    Approximated from yfinance data.
    """
    roe = safe_get(info, "returnOnEquity")
    roa = safe_get(info, "returnOnAssets")

    # Use ROE as primary, ROA as secondary
    metric = roe if roe is not None else roa
    label = "ROE" if roe is not None else "ROA"

    if metric is None:
        return 50, []

    pct = metric * 100
    if metric > 0.25:
        return 90, [f"Exceptional {label} ({pct:.1f}%) — outstanding capital efficiency"]
    elif metric > 0.15:
        return 72, [f"Strong {label} ({pct:.1f}%) — efficient use of capital"]
    elif metric > 0.08:
        return 55, [f"Decent {label} ({pct:.1f}%)"]
    elif metric > 0:
        return 35, [f"Low {label} ({pct:.1f}%) — weak capital efficiency"]
    else:
        return 10, [f"Negative {label} ({pct:.1f}%)"]


def _score_earnings_quality(info):
    """
    Earnings quality: Operating Cash Flow vs Net Income ratio.
    Ratio > 1 means earnings are backed by real cash. < 1 = accounting profits only.
    """
    ocf = safe_get(info, "operatingCashflow")
    net_income = safe_get(info, "netIncomeToCommon")

    if not ocf or not net_income or net_income == 0:
        return 50, []

    ratio = ocf / net_income

    if ratio > 1.3:
        return 85, [f"High earnings quality (OCF/NI: {ratio:.2f}) — cash exceeds reported profits"]
    elif ratio > 1.0:
        return 70, [f"Good earnings quality (OCF/NI: {ratio:.2f}) — earnings backed by cash"]
    elif ratio > 0.7:
        return 45, [f"Moderate earnings quality (OCF/NI: {ratio:.2f})"]
    elif ratio > 0:
        return 25, [f"Low earnings quality (OCF/NI: {ratio:.2f}) — aggressive accounting?"]
    else:
        return 10, [f"Negative cash flow relative to earnings — red flag"]


def _score_balance_sheet(info):
    """Score debt levels and balance sheet strength."""
    score = 50
    signals = []

    dte = safe_get(info, "debtToEquity")
    current_ratio = safe_get(info, "currentRatio")

    if dte is not None:
        if dte < 20:
            score = 85
            signals.append(f"Very low debt-to-equity ({dte:.0f}%) — fortress balance sheet")
        elif dte < 50:
            score = 70
            signals.append(f"Conservative leverage ({dte:.0f}% D/E)")
        elif dte < 100:
            score = 50
            signals.append(f"Moderate leverage ({dte:.0f}% D/E)")
        elif dte < 200:
            score = 30
            signals.append(f"High leverage ({dte:.0f}% D/E) — elevated risk")
        else:
            score = 10
            signals.append(f"Very high leverage ({dte:.0f}% D/E) — dangerous debt level")

    if current_ratio is not None:
        if current_ratio > 2.0:
            score = min(100, score + 10)
            signals.append(f"Strong liquidity (current ratio: {current_ratio:.1f})")
        elif current_ratio < 1.0:
            score = max(0, score - 10)
            signals.append(f"Liquidity concern (current ratio: {current_ratio:.1f} < 1)")

    return score, signals


def _compute_quality_score(info):
    """Combine quality metrics: profitability, ROIC, earnings quality, balance sheet."""
    prof_score, prof_signals = _score_profitability(info)
    roic_score, roic_signals = _score_roic(info)
    eq_score, eq_signals = _score_earnings_quality(info)
    bs_score, bs_signals = _score_balance_sheet(info)

    score = (prof_score * 0.30 + roic_score * 0.30 + eq_score * 0.20 + bs_score * 0.20)
    return round(score), prof_signals + roic_signals + eq_signals + bs_signals


# ═══════════════════════════════════════════════════════════
# GROWTH PILLAR (20% of total)
# ═══════════════════════════════════════════════════════════

def _compute_growth_score(info):
    """Score revenue and earnings growth trajectory."""
    score = 50
    signals = []
    sub_scores = []

    rev_growth = safe_get(info, "revenueGrowth")
    earn_growth = safe_get(info, "earningsGrowth")

    if rev_growth is not None:
        rg_pct = rev_growth * 100
        if rev_growth > 0.25:
            s = 90
            signals.append(f"Exceptional revenue growth ({rg_pct:.1f}%) — rapidly scaling")
        elif rev_growth > 0.10:
            s = 72
            signals.append(f"Strong revenue growth ({rg_pct:.1f}%)")
        elif rev_growth > 0.03:
            s = 55
            signals.append(f"Moderate revenue growth ({rg_pct:.1f}%)")
        elif rev_growth > 0:
            s = 40
            signals.append(f"Slow revenue growth ({rg_pct:.1f}%)")
        else:
            s = 15
            signals.append(f"Revenue declining ({rg_pct:.1f}%)")
        sub_scores.append(s)

    if earn_growth is not None:
        eg_pct = earn_growth * 100
        if earn_growth > 0.30:
            s = 90
            signals.append(f"Exceptional earnings growth ({eg_pct:.1f}%)")
        elif earn_growth > 0.10:
            s = 72
            signals.append(f"Strong earnings growth ({eg_pct:.1f}%)")
        elif earn_growth > 0.03:
            s = 55
            signals.append(f"Moderate earnings growth ({eg_pct:.1f}%)")
        elif earn_growth > 0:
            s = 40
            signals.append(f"Slow earnings growth ({eg_pct:.1f}%)")
        else:
            s = 15
            signals.append(f"Earnings declining ({eg_pct:.1f}%)")
        sub_scores.append(s)

    if sub_scores:
        score = round(sum(sub_scores) / len(sub_scores))
    return score, signals


# ═══════════════════════════════════════════════════════════
# ANALYST CONSENSUS PILLAR (15% of total)
# ═══════════════════════════════════════════════════════════

def _compute_analyst_score(info):
    """
    Integrate analyst consensus from yfinance:
    - recommendationMean: 1=Strong Buy, 2=Buy, 3=Hold, 4=Sell, 5=Strong Sell
    - targetMeanPrice: consensus price target
    - numberOfAnalystOpinions: coverage depth
    """
    score = 50
    signals = []

    rec_mean = safe_get(info, "recommendationMean")
    rec_key = safe_get(info, "recommendationKey")
    target = safe_get(info, "targetMeanPrice")
    target_high = safe_get(info, "targetHighPrice")
    target_low = safe_get(info, "targetLowPrice")
    current = safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice")
    num_analysts = safe_get(info, "numberOfAnalystOpinions")

    # Recommendation score (1-5 scale → 0-100)
    if rec_mean is not None:
        if rec_mean <= 1.5:
            score = 90
            signals.append(f"Analyst consensus: STRONG BUY ({rec_mean:.1f}/5 from {num_analysts or '?'} analysts)")
        elif rec_mean <= 2.2:
            score = 75
            signals.append(f"Analyst consensus: BUY ({rec_mean:.1f}/5 from {num_analysts or '?'} analysts)")
        elif rec_mean <= 2.8:
            score = 60
            signals.append(f"Analyst consensus: OUTPERFORM ({rec_mean:.1f}/5 from {num_analysts or '?'} analysts)")
        elif rec_mean <= 3.5:
            score = 40
            signals.append(f"Analyst consensus: HOLD ({rec_mean:.1f}/5 from {num_analysts or '?'} analysts)")
        elif rec_mean <= 4.2:
            score = 20
            signals.append(f"Analyst consensus: SELL ({rec_mean:.1f}/5 from {num_analysts or '?'} analysts)")
        else:
            score = 10
            signals.append(f"Analyst consensus: STRONG SELL ({rec_mean:.1f}/5)")
    elif rec_key:
        key_map = {"strong_buy": 85, "buy": 72, "outperform": 65,
                    "hold": 45, "underperform": 25, "sell": 15, "strong_sell": 5}
        score = key_map.get(rec_key.lower(), 50)
        signals.append(f"Analyst recommendation: {rec_key.upper()}")

    # Price target upside/downside
    upside = None
    if target and current and current > 0:
        upside = ((target - current) / current) * 100
        if upside > 30:
            score = min(100, score + 10)
            signals.append(f"Target price {_format_currency(target)} ({upside:.1f}% upside) — significant potential")
        elif upside > 10:
            score = min(100, score + 5)
            signals.append(f"Target price {_format_currency(target)} ({upside:.1f}% upside)")
        elif upside < -15:
            score = max(0, score - 10)
            signals.append(f"Target price {_format_currency(target)} ({upside:.1f}% downside) — overvalued per analysts")
        elif upside < 0:
            score = max(0, score - 3)
            signals.append(f"Target price {_format_currency(target)} ({upside:.1f}%) — near consensus value")

    # Target spread (conviction indicator)
    if target_high and target_low and target_high > target_low:
        spread = ((target_high - target_low) / target_low) * 100
        if spread < 30:
            signals.append(f"Tight analyst range ({_format_currency(target_low)}-{_format_currency(target_high)}) — high conviction")
        elif spread > 80:
            signals.append(f"Wide analyst range ({_format_currency(target_low)}-{_format_currency(target_high)}) — high uncertainty")

    # Analyst coverage depth
    if num_analysts and num_analysts > 20:
        score = min(100, score + 3)  # Well-covered stock
    elif num_analysts and num_analysts < 3:
        score = max(0, score - 5)  # Low coverage = less reliable

    return score, signals, upside


# ═══════════════════════════════════════════════════════════
# PIOTROSKI F-SCORE (9-point financial health)
# ═══════════════════════════════════════════════════════════

def _compute_piotroski_score(info):
    """
    Piotroski F-Score: 9 binary criteria (1 point each).
    Score 7-9 = Strong, 4-6 = Moderate, 1-3 = Weak.
    Criteria:
    Profitability (4): ROA > 0, Operating CF > 0, Change in ROA > 0, Accruals < 0
    Leverage (3): Change in D/E (lower=better), Current Ratio > 1, No share dilution
    Efficiency (2): Change in Gross Margin > 0, Change in Asset Turnover > 0
    """
    score = 0
    details = []

    roa = safe_get(info, "returnOnAssets")
    ocf = safe_get(info, "operatingCashflow")
    net_income = safe_get(info, "netIncomeToCommon")
    dte = safe_get(info, "debtToEquity")
    current_ratio = safe_get(info, "currentRatio")
    shares = safe_get(info, "sharesOutstanding")
    rev_growth = safe_get(info, "revenueGrowth")
    gross_margin = safe_get(info, "grossMargins")
    earn_growth = safe_get(info, "earningsGrowth")
    total_assets = safe_get(info, "totalAssets")

    # 1. ROA > 0 (profitability)
    if roa is not None and roa > 0:
        score += 1
        details.append("✓ Profitable (ROA > 0)")
    else:
        details.append("✗ Not profitable (ROA ≤ 0)")

    # 2. Operating Cash Flow > 0
    if ocf is not None and ocf > 0:
        score += 1
        details.append("✓ Positive operating cash flow")
    else:
        details.append("✗ Negative operating cash flow")

    # 3. Accruals < 0 (OCF/Assets > ROA — cash-backed earnings)
    if ocf and net_income and total_assets and total_assets > 0:
        ocf_to_assets = ocf / total_assets
        if ocf_to_assets > (roa or 0):
            score += 1
            details.append("✓ Cash earnings exceed reported earnings (low accruals)")
        else:
            details.append("✗ Accrual-heavy earnings (accounting risk)")

    # 4. ROA improvement proxy — earnings growth
    if earn_growth is not None and earn_growth > 0:
        score += 1
        details.append("✓ Earnings improving YoY")
    else:
        details.append("✗ Earnings not improving")

    # 5. Leverage — debt-to-equity reasonable
    if dte is not None and dte < 100:
        score += 1
        details.append(f"✓ Manageable leverage (D/E: {dte:.0f}%)")
    else:
        details.append(f"✗ High leverage (D/E: {dte:.0f}%)" if dte else "✗ Leverage data unavailable")

    # 6. Current Ratio > 1
    if current_ratio is not None and current_ratio > 1:
        score += 1
        details.append(f"✓ Good liquidity (current ratio: {current_ratio:.1f})")
    else:
        details.append(f"✗ Liquidity concern (current ratio: {current_ratio:.1f})" if current_ratio else "✗ Liquidity data unavailable")

    # 7. No share dilution proxy — positive revenue growth suggests healthy expansion
    if rev_growth is not None and rev_growth > 0:
        score += 1
        details.append("✓ Revenue growing (expansion signal)")
    else:
        details.append("✗ Revenue not growing")

    # 8. Gross margin positive
    if gross_margin is not None and gross_margin > 0.20:
        score += 1
        details.append(f"✓ Solid gross margin ({gross_margin*100:.1f}%)")
    else:
        details.append(f"✗ Low gross margin ({(gross_margin or 0)*100:.1f}%)")

    # 9. Asset efficiency — revenue growth > 0 (proxy for asset turnover improvement)
    if rev_growth is not None and earn_growth is not None and rev_growth > 0 and earn_growth > rev_growth:
        score += 1
        details.append("✓ Earnings growing faster than revenue — margin expansion")
    elif earn_growth is not None and earn_growth > 0:
        # Partial credit
        score += 0
        details.append("~ Earnings growing but below revenue growth")
    else:
        details.append("✗ No margin expansion signal")

    return score, details


# ═══════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════

def _format_currency(value):
    """Format a price value."""
    if value is None:
        return "N/A"
    if value >= 10000:
        return f"${value:,.0f}"
    return f"${value:,.2f}"


def _format_market_cap(mc):
    """Format market cap for display."""
    if not mc:
        return "N/A"
    if mc >= 1e12:
        return f"${mc/1e12:.2f}T"
    elif mc >= 1e9:
        return f"${mc/1e9:.2f}B"
    elif mc >= 1e6:
        return f"${mc/1e6:.2f}M"
    return f"${mc:,.0f}"


# ═══════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════

def run_fundamental_analysis(ticker_info):
    """
    Run institutional-grade fundamental analysis.
    Returns dict with metrics, signals, pillar scores, and composite score.
    """
    result = {
        "metrics": {},
        "signals": [],
        "score": 50,
        "pillar_scores": {},
        "intrinsic_value": None,
        "margin_of_safety": None,
        "analyst_upside": None,
        "error": None
    }

    if not ticker_info:
        result["error"] = "No fundamental data available"
        return result

    info = ticker_info
    sector = safe_get(info, "sector", "Unknown")

    # ── Extract metrics ──
    metrics = {
        "marketCap": safe_get(info, "marketCap"),
        "marketCapFormatted": _format_market_cap(safe_get(info, "marketCap")),
        "peRatio": safe_get(info, "trailingPE"),
        "forwardPE": safe_get(info, "forwardPE"),
        "pegRatio": safe_get(info, "pegRatio"),
        "revenueGrowth": safe_get(info, "revenueGrowth"),
        "earningsGrowth": safe_get(info, "earningsGrowth"),
        "profitMargin": safe_get(info, "profitMargins"),
        "grossMargin": safe_get(info, "grossMargins"),
        "ebitdaMargin": safe_get(info, "ebitdaMargins"),
        "returnOnEquity": safe_get(info, "returnOnEquity"),
        "returnOnAssets": safe_get(info, "returnOnAssets"),
        "debtToEquity": safe_get(info, "debtToEquity"),
        "currentRatio": safe_get(info, "currentRatio"),
        "freeCashflow": safe_get(info, "freeCashflow"),
        "operatingCashflow": safe_get(info, "operatingCashflow"),
        "dividendYield": safe_get(info, "dividendYield"),
        "currentPrice": safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice"),
        "targetMeanPrice": safe_get(info, "targetMeanPrice"),
        "targetHighPrice": safe_get(info, "targetHighPrice"),
        "targetLowPrice": safe_get(info, "targetLowPrice"),
        "recommendationMean": safe_get(info, "recommendationMean"),
        "recommendationKey": safe_get(info, "recommendationKey"),
        "numberOfAnalysts": safe_get(info, "numberOfAnalystOpinions"),
        "sector": sector,
        "industry": safe_get(info, "industry", "N/A"),
        "companyName": safe_get(info, "longName") or safe_get(info, "shortName", "Unknown"),
        "fiftyTwoWeekHigh": safe_get(info, "fiftyTwoWeekHigh"),
        "fiftyTwoWeekLow": safe_get(info, "fiftyTwoWeekLow"),
    }
    result["metrics"] = metrics

    # ── Compute pillar scores ──
    all_signals = []

    # Pillar 1: Valuation (35%)
    val_score, val_signals = _compute_valuation_score(info, sector)
    all_signals.extend(val_signals)

    # Pillar 2: Quality (30%)
    qual_score, qual_signals = _compute_quality_score(info)
    all_signals.extend(qual_signals)

    # Pillar 3: Growth (20%)
    growth_score, growth_signals = _compute_growth_score(info)
    all_signals.extend(growth_signals)

    # Pillar 4: Analyst Consensus (15%)
    analyst_score, analyst_signals, analyst_upside = _compute_analyst_score(info)
    all_signals.extend(analyst_signals)
    result["analyst_upside"] = analyst_upside

    # DCF intrinsic value
    iv, mos, dcf_signals = _estimate_intrinsic_value(info)
    if iv is not None:
        result["intrinsic_value"] = iv
        result["margin_of_safety"] = mos
        all_signals.extend(dcf_signals)

    # Dividend bonus
    div_yield = safe_get(info, "dividendYield")
    if div_yield and div_yield > 0:
        dy_pct = div_yield * 100
        if div_yield > 0.04:
            all_signals.append(f"High dividend yield ({dy_pct:.2f}%) — good income stock")
        elif div_yield > 0.02:
            all_signals.append(f"Moderate dividend yield ({dy_pct:.2f}%)")

    # ── Piotroski F-Score ──
    piotroski_score, piotroski_details = _compute_piotroski_score(info)
    result["piotroski_score"] = piotroski_score
    result["piotroski_details"] = piotroski_details

    # ── Weighted composite ──
    pillar_scores = {
        "valuation": val_score,
        "quality": qual_score,
        "growth": growth_score,
        "analyst": analyst_score,
        "piotroski": piotroski_score,
    }
    result["pillar_scores"] = pillar_scores

    # Piotroski bonus/penalty (normalized: 9-point → subtle adjustment)
    piotroski_adjustment = (piotroski_score - 5) * 1.5  # -7.5 to +6 range

    composite = (
        val_score * 0.33 +
        qual_score * 0.28 +
        growth_score * 0.19 +
        analyst_score * 0.14 +
        piotroski_adjustment * 0.06
    )

    result["signals"] = all_signals
    result["score"] = max(0, min(100, round(composite)))

    return result
