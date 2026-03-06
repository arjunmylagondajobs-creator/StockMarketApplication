"""
Validation Script — Compares our app's verdicts against real analyst consensus.
Runs 10 stocks and outputs a comparison table.
"""
import requests
import json
import time

BASE = "http://localhost:5000"

STOCKS = [
    "AAPL",          # US Tech mega-cap
    "TSLA",          # US EV - volatile
    "JPM",           # US Financials
    "PFE",           # US Healthcare/Pharma
    "NVDA",          # US AI/Semiconductor
    "RELIANCE.NS",   # India conglomerate
    "TCS.NS",        # India IT
    "HDFCBANK.NS",   # India Banking
    "META",          # US Social/Tech
    "XOM",           # US Energy/Oil
]

results = []

for ticker in STOCKS:
    print(f"\n{'='*50}")
    print(f"Analyzing {ticker}...")
    start = time.time()
    try:
        r = requests.post(f"{BASE}/api/analyze", json={"ticker": ticker}, timeout=180)
        data = r.json()
        elapsed = round(time.time() - start, 1)

        if "error" in data:
            print(f"  ERROR: {data['error']}")
            results.append({
                "ticker": ticker,
                "error": data["error"]
            })
            continue

        rec = data.get("recommendation", {})
        fund = data.get("fundamental", {})
        tech = data.get("technical", {})
        sent = data.get("sentiment", {})
        macro = data.get("macro", {})
        inst = data.get("institutional", {})
        opts = data.get("options_intel", {})
        sect = data.get("sector_rotation", {})
        earn = data.get("earnings", {})
        policy = data.get("policy", {})

        metrics = fund.get("metrics", {})

        result = {
            "ticker": ticker,
            "company": data.get("companyName", ""),
            "price": data.get("currentPrice"),
            "our_verdict": rec.get("verdict"),
            "our_score": rec.get("final_score"),
            "confidence": rec.get("confidence"),
            "confidence_pct": rec.get("confidence_pct"),
            "market_regime": rec.get("market_regime"),

            # Pillar scores
            "tech_score": tech.get("score"),
            "fund_score": fund.get("score"),
            "sent_score": sent.get("score"),
            "macro_score": macro.get("score"),
            "policy_score": policy.get("score"),
            "inst_score": inst.get("score"),
            "opt_score": opts.get("score") if opts.get("available") else "N/A",
            "sect_score": sect.get("score"),
            "earn_score": earn.get("score"),

            # Key fundamental data for comparison
            "pe_ratio": metrics.get("peRatio"),
            "forward_pe": metrics.get("forwardPE"),
            "analyst_rec_key": metrics.get("recommendationKey"),
            "analyst_rec_mean": metrics.get("recommendationMean"),
            "target_price": metrics.get("targetMeanPrice"),
            "num_analysts": metrics.get("numberOfAnalysts"),
            "piotroski": fund.get("piotroski_score"),

            # Institutional stance
            "inst_stance": inst.get("institutional_stance"),
            "earnings_momentum": earn.get("earnings_momentum"),

            "elapsed": elapsed,
        }
        results.append(result)

        print(f"  Company: {result['company']}")
        print(f"  Price: ${result['price']}")
        print(f"  OUR VERDICT: {result['our_verdict']} (Score: {result['our_score']}/100)")
        print(f"  Analyst Consensus (yfinance): {result['analyst_rec_key']} ({result['analyst_rec_mean']})")
        print(f"  Target Price: ${result['target_price']} | Analysts: {result['num_analysts']}")
        print(f"  Piotroski: {result['piotroski']}/9")
        print(f"  Pillars: Tech={result['tech_score']} Fund={result['fund_score']} Sent={result['sent_score']} Macro={result['macro_score']} Policy={result['policy_score']} Inst={result['inst_score']} Opt={result['opt_score']} Sect={result['sect_score']} Earn={result['earn_score']}")
        print(f"  Time: {elapsed}s")

    except Exception as e:
        print(f"  FAILED: {e}")
        results.append({"ticker": ticker, "error": str(e)})

# ── Summary Table ──
print("\n\n" + "="*120)
print("VALIDATION SUMMARY: Our App vs. Analyst Consensus")
print("="*120)
print(f"{'Ticker':<14} {'Company':<22} {'Price':>8} {'Our Verdict':<12} {'Score':>5} {'Analyst Con.':>12} {'Target $':>9} {'#Analysts':>9} {'Piotroski':>9} {'Match?':>7}")
print("-"*120)

matches = 0
total_valid = 0

for r in results:
    if "error" in r:
        print(f"{r['ticker']:<14} ERROR: {r.get('error', 'Unknown')[:80]}")
        continue

    total_valid += 1

    # Determine if our verdict aligns with analyst consensus
    our = r["our_verdict"]
    analyst = (r["analyst_rec_key"] or "").lower()

    # Map analyst consensus to our categories
    analyst_bullish = analyst in ("strong_buy", "buy", "outperform")
    analyst_neutral = analyst in ("hold", "neutral")
    analyst_bearish = analyst in ("sell", "underperform", "strong_sell")

    our_bullish = our in ("STRONG BUY", "BUY", "LEAN BUY")
    our_neutral = our == "HOLD"
    our_bearish = our in ("LEAN SELL", "SELL", "STRONG SELL")

    # Match = both bullish, both neutral, or both bearish
    # Also "adjacent" match: e.g., our HOLD vs analyst hold, or our LEAN BUY vs analyst buy
    if (our_bullish and analyst_bullish) or (our_neutral and analyst_neutral) or (our_bearish and analyst_bearish):
        match = "YES"
        matches += 1
    elif (our_neutral and analyst_bullish) or (our_bullish and analyst_neutral):
        match = "~CLOSE"  # Adjacent — not perfect but not opposite
        matches += 0.5
    elif (our_neutral and analyst_bearish) or (our_bearish and analyst_neutral):
        match = "~CLOSE"
        matches += 0.5
    else:
        match = "NO"

    target = f"${r['target_price']:.0f}" if r['target_price'] else "—"
    print(f"{r['ticker']:<14} {r['company'][:21]:<22} ${r['price']:>7.2f} {our:<12} {r['our_score']:>5.1f} {analyst.upper():>12} {target:>9} {r['num_analysts'] or '—':>9} {r['piotroski'] or '—':>9} {match:>7}")

print("-"*120)
accuracy = (matches / total_valid * 100) if total_valid > 0 else 0
print(f"\nAlignment Rate: {matches}/{total_valid} = {accuracy:.0f}%")
print("(YES=exact match, ~CLOSE=adjacent category, NO=opposite direction)")
print("\nNote: 'Analyst Con.' is yfinance's aggregated analyst consensus from major brokerages.")
print("Our app adds sentiment, macro, policy, options, sector rotation, and earnings — so some divergence is expected and healthy.")
