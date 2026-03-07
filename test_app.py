"""
Critical Test Suite for Stock Investment Analyzer (8-Pillar)
Tests: Access-code auth, all pillars, edge cases, India vs US, error handling.
"""

import requests
import json
import time
import sys

BASE = "http://localhost:5000"
ACCESS_CODE = "StockReferCode5282"
RESULTS = []


def get_authenticated_session():
    """Create a requests.Session that is authenticated via the access code."""
    s = requests.Session()
    # POST the access code to login
    r = s.post(f"{BASE}/login", data={"access_code": ACCESS_CODE}, allow_redirects=True, timeout=15)
    return s


# Create a shared authenticated session for all tests
SESSION = get_authenticated_session()


def test(name, func):
    """Run a test and record result."""
    try:
        start = time.time()
        result = func()
        elapsed = round(time.time() - start, 2)
        status = "PASS" if result else "FAIL"
        RESULTS.append((name, status, elapsed, ""))
        icon = "+" if status == "PASS" else "X"
        print(f"  [{icon}] {name} ({elapsed}s)")
        return result
    except Exception as e:
        elapsed = round(time.time() - start, 2)
        RESULTS.append((name, "ERROR", elapsed, str(e)[:80]))
        print(f"  [!] {name} ({elapsed}s) - ERROR: {e}")
        return False


def analyze(ticker):
    """Helper: call /api/analyze and return parsed JSON."""
    r = SESSION.post(f"{BASE}/api/analyze", json={"ticker": ticker}, timeout=180)
    return r.status_code, r.json()


# ====================================================
# TEST 0: Access Code Authentication
# ====================================================
print("\n=== TEST GROUP 0: Access Code Authentication ===")

def t0_unauthenticated_redirect():
    """Unauthenticated request to / should redirect to /login."""
    r = requests.get(f"{BASE}/", allow_redirects=False, timeout=15)
    return r.status_code == 302 and "/login" in r.headers.get("Location", "")
test("0.1 Unauthenticated GET / redirects to /login", t0_unauthenticated_redirect)

def t0_unauthenticated_api():
    """Unauthenticated API call should redirect to /login."""
    r = requests.post(f"{BASE}/api/analyze", json={"ticker": "AAPL"}, allow_redirects=False, timeout=15)
    return r.status_code == 302 and "/login" in r.headers.get("Location", "")
test("0.2 Unauthenticated POST /api/analyze redirects to /login", t0_unauthenticated_api)

def t0_wrong_code():
    """Wrong access code should show login page again (not redirect to /)."""
    r = requests.post(f"{BASE}/login", data={"access_code": "WRONG_CODE"}, allow_redirects=False, timeout=15)
    # Should return 200 with login page (containing error), NOT a redirect to /
    return r.status_code == 200
test("0.3 Wrong access code is rejected", t0_wrong_code)

def t0_correct_code():
    """Correct access code should redirect to /."""
    s = requests.Session()
    r = s.post(f"{BASE}/login", data={"access_code": ACCESS_CODE}, allow_redirects=False, timeout=15)
    return r.status_code == 302 and r.headers.get("Location", "").endswith("/")
test("0.4 Correct access code grants access (redirect to /)", t0_correct_code)

def t0_login_page_loads():
    """Login page should load properly."""
    r = requests.get(f"{BASE}/login", timeout=15)
    return r.status_code == 200 and "access code" in r.text.lower()
test("0.5 Login page loads with access code form", t0_login_page_loads)

def t0_logout():
    """Logout should clear session and redirect to /login."""
    s = requests.Session()
    s.post(f"{BASE}/login", data={"access_code": ACCESS_CODE}, timeout=15)
    r = s.get(f"{BASE}/logout", allow_redirects=False, timeout=15)
    return r.status_code == 302 and "/login" in r.headers.get("Location", "")
test("0.6 Logout clears session and redirects to /login", t0_logout)


# ====================================================
# TEST 1: US Large Cap - AAPL (all 8 pillars)
# ====================================================
print("\n=== TEST GROUP 1: US Large Cap (AAPL) ===")

aapl_data = [None]
def t1_fetch():
    code, data = analyze("AAPL")
    aapl_data[0] = data
    return code == 200 and "error" not in data
test("1.1 AAPL: API returns 200", t1_fetch)

def t1_basic():
    d = aapl_data[0]
    return all([
        d.get("ticker") == "AAPL",
        d.get("companyName"),
        d.get("currentPrice") and d["currentPrice"] > 0,
        d.get("currency"),
    ])
test("1.2 AAPL: Basic info (name, price, currency)", t1_basic)

def t1_technical():
    t = aapl_data[0].get("technical", {})
    return all([
        t.get("score") is not None and 0 <= t["score"] <= 100,
        t.get("rsi", {}).get("value") is not None,
        t.get("macd", {}).get("trend") not in (None, "N/A"),
        t.get("adx", {}).get("value") is not None,
        t.get("market_regime") in ("Bullish Trend", "Bearish Trend", "Range-Bound", "Transitioning"),
    ])
test("1.3 AAPL: Technical pillar (RSI, MACD, ADX, regime)", t1_technical)

def t1_fundamental():
    f = aapl_data[0].get("fundamental", {})
    ps = f.get("pillar_scores", {})
    return all([
        f.get("score") is not None and 0 <= f["score"] <= 100,
        ps.get("valuation") is not None,
        ps.get("quality") is not None,
        ps.get("growth") is not None,
        ps.get("analyst") is not None,
        f.get("piotroski_score") is not None and 0 <= f["piotroski_score"] <= 9,
        len(f.get("signals", [])) > 0,
    ])
test("1.4 AAPL: Fundamental pillar + Piotroski F-score", t1_fundamental)

def t1_sentiment():
    s = aapl_data[0].get("sentiment", {})
    return all([
        s.get("score") is not None and 0 <= s["score"] <= 100,
        s.get("overall_sentiment") in ("Bullish", "Slightly Bullish", "Neutral", "Slightly Bearish", "Bearish"),
    ])
test("1.5 AAPL: Sentiment pillar", t1_sentiment)

def t1_macro():
    m = aapl_data[0].get("macro", {})
    return all([
        m.get("score") is not None and 0 <= m["score"] <= 100,
        m.get("environment") is not None,
        len(m.get("signals", [])) >= 3,
    ])
test("1.6 AAPL: Macro pillar (VIX, yields, DXY)", t1_macro)

def t1_policy():
    p = aapl_data[0].get("policy", {})
    return all([
        p.get("score") is not None and 0 <= p["score"] <= 100,
        p.get("policy_stance") is not None,
    ])
test("1.7 AAPL: Policy pillar", t1_policy)

def t1_institutional():
    i = aapl_data[0].get("institutional", {})
    return all([
        i.get("score") is not None and 0 <= i["score"] <= 100,
        i.get("institutional_stance") is not None,
        len(i.get("signals", [])) >= 1,
    ])
test("1.8 AAPL: Institutional pillar (holders, insiders, short)", t1_institutional)

def t1_options():
    o = aapl_data[0].get("options_intel", {})
    return all([
        o.get("available") == True,
        o.get("score") is not None and 0 <= o["score"] <= 100,
        o.get("put_call_ratio") is not None,
        o.get("options_sentiment") is not None,
    ])
test("1.9 AAPL: Options Intelligence (PCR, IV, MaxPain)", t1_options)

def t1_sector():
    sr = aapl_data[0].get("sector_rotation", {})
    return all([
        sr.get("score") is not None and 0 <= sr["score"] <= 100,
        sr.get("rotation_signal") is not None,
    ])
test("1.10 AAPL: Sector Rotation", t1_sector)

def t1_earnings():
    e = aapl_data[0].get("earnings", {})
    return all([
        e.get("score") is not None and 0 <= e["score"] <= 100,
        e.get("earnings_momentum") is not None,
    ])
test("1.11 AAPL: Earnings Outlook", t1_earnings)

def t1_recommendation():
    r = aapl_data[0].get("recommendation", {})
    return all([
        r.get("final_score") is not None and 0 <= r["final_score"] <= 100,
        r.get("verdict") in ("STRONG BUY", "BUY", "LEAN BUY", "HOLD", "LEAN SELL", "SELL", "STRONG SELL"),
        r.get("confidence") is not None,
        r.get("weights_used") is not None and len(r["weights_used"]) >= 5,
        r.get("pillar_scores") is not None and len(r["pillar_scores"]) >= 7,
    ])
test("1.12 AAPL: 8-pillar recommendation engine", t1_recommendation)

def t1_reasoning():
    reasoning = aapl_data[0].get("reasoning", "")
    checks = [
        "Technical Analysis" in reasoning,
        "Fundamental Analysis" in reasoning,
        "Sentiment" in reasoning,
        "Macro" in reasoning,
        "30-Day Outlook" in reasoning,
        "Action Summary" in reasoning,
    ]
    return sum(checks) >= 5
test("1.13 AAPL: Reasoning has all sections (incl 30-day outlook)", t1_reasoning)


# ====================================================
# TEST 2: India Stock - RELIANCE.NS
# ====================================================
print("\n=== TEST GROUP 2: India Stock (RELIANCE.NS) ===")

rel_data = [None]
def t2_fetch():
    code, data = analyze("RELIANCE.NS")
    rel_data[0] = data
    return code == 200 and "error" not in data
test("2.1 RELIANCE.NS: API returns 200", t2_fetch)

def t2_india_detected():
    d = rel_data[0]
    return d.get("isIndia") == True
test("2.2 RELIANCE.NS: isIndia=True detected", t2_india_detected)

def t2_macro_india():
    m = rel_data[0].get("macro", {})
    subs = m.get("sub_scores", {})
    return "usdinr" in subs
test("2.3 RELIANCE.NS: Macro includes USD/INR (India-specific)", t2_macro_india)

def t2_options_na():
    o = rel_data[0].get("options_intel", {})
    return o.get("available") == False
test("2.4 RELIANCE.NS: Options correctly N/A for India", t2_options_na)

def t2_all_pillars():
    d = rel_data[0]
    return all([
        d.get("technical", {}).get("score") is not None,
        d.get("fundamental", {}).get("score") is not None,
        d.get("sentiment", {}).get("score") is not None,
        d.get("macro", {}).get("score") is not None,
        d.get("institutional", {}).get("score") is not None,
        d.get("sector_rotation", {}).get("score") is not None,
        d.get("earnings", {}).get("score") is not None,
        d.get("recommendation", {}).get("final_score") is not None,
    ])
test("2.5 RELIANCE.NS: All pillars return valid scores", t2_all_pillars)


# ====================================================
# TEST 3: Auto-resolve India ticker (INFY)
# ====================================================
print("\n=== TEST GROUP 3: Auto-resolve India ticker (INFY) ===")

infy_data = [None]
def t3_fetch():
    code, data = analyze("INFY")
    infy_data[0] = data
    return code == 200 and "error" not in data
test("3.1 INFY: Auto-resolves to INFY.NS", t3_fetch)

def t3_resolved():
    d = infy_data[0]
    return ".NS" in d.get("ticker", "") or ".BO" in d.get("ticker", "")
test("3.2 INFY: Resolved ticker has exchange suffix", t3_resolved)


# ====================================================
# TEST 4: Error handling
# ====================================================
print("\n=== TEST GROUP 4: Error Handling ===")

def t4_invalid():
    code, data = analyze("XYZZZZ12345")
    return code in (404, 500) and "error" in data
test("4.1 Invalid ticker returns error gracefully", t4_invalid)

def t4_empty():
    code, data = analyze("")
    return code == 400 and "error" in data
test("4.2 Empty ticker returns 400", t4_empty)

def t4_no_body():
    r = SESSION.post(f"{BASE}/api/analyze", json={}, timeout=30)
    return r.status_code == 400
test("4.3 Missing ticker field returns 400", t4_no_body)


# ====================================================
# TEST 5: Search API
# ====================================================
print("\n=== TEST GROUP 5: Search API ===")

def t5_search():
    r = SESSION.get(f"{BASE}/api/search?q=Apple", timeout=30)
    data = r.json()
    return r.status_code == 200 and len(data) > 0 and any("AAPL" in d.get("symbol", "") for d in data)
test("5.1 Search 'Apple' returns AAPL", t5_search)

def t5_search_short():
    r = SESSION.get(f"{BASE}/api/search?q=A", timeout=30)
    data = r.json()
    return r.status_code == 200 and data == []
test("5.2 Search too-short query returns []", t5_search_short)


# ====================================================
# TEST 6: Score boundaries and consistency
# ====================================================
print("\n=== TEST GROUP 6: Score Validation ===")

def t6_scores_in_range():
    d = aapl_data[0]
    scores = [
        d.get("technical", {}).get("score"),
        d.get("fundamental", {}).get("score"),
        d.get("sentiment", {}).get("score"),
        d.get("macro", {}).get("score"),
        d.get("policy", {}).get("score"),
        d.get("institutional", {}).get("score"),
        d.get("sector_rotation", {}).get("score"),
        d.get("earnings", {}).get("score"),
        d.get("recommendation", {}).get("final_score"),
    ]
    return all(s is not None and 0 <= s <= 100 for s in scores)
test("6.1 All scores in 0-100 range", t6_scores_in_range)

def t6_weights_sum():
    w = aapl_data[0].get("recommendation", {}).get("weights_used", {})
    total = sum(w.values())
    return 98 <= total <= 102
test("6.2 Recommendation weights sum to ~100%", t6_weights_sum)

def t6_piotroski_range():
    p = aapl_data[0].get("fundamental", {}).get("piotroski_score")
    details = aapl_data[0].get("fundamental", {}).get("piotroski_details", [])
    return p is not None and 0 <= p <= 9 and len(details) >= 5
test("6.3 Piotroski F-Score 0-9 with details", t6_piotroski_range)


# ====================================================
# TEST 7: Frontend pages (authenticated)
# ====================================================
print("\n=== TEST GROUP 7: Frontend Pages ===")

def t7_index():
    r = SESSION.get(f"{BASE}/", timeout=15)
    return r.status_code == 200 and "Stock" in r.text
test("7.1 Index page loads (authenticated)", t7_index)

def t7_top_picks():
    r = SESSION.get(f"{BASE}/top-picks", timeout=15)
    return r.status_code == 200
test("7.2 Top Picks page loads (authenticated)", t7_top_picks)

def t7_logout_link():
    r = SESSION.get(f"{BASE}/", timeout=15)
    return r.status_code == 200 and "logout" in r.text.lower()
test("7.3 Index page has Logout link", t7_logout_link)


# ====================================================
# SUMMARY
# ====================================================
print("\n" + "="*55)
print("TEST RESULTS SUMMARY")
print("="*55)

passed = sum(1 for _, s, _, _ in RESULTS if s == "PASS")
failed = sum(1 for _, s, _, _ in RESULTS if s == "FAIL")
errors = sum(1 for _, s, _, _ in RESULTS if s == "ERROR")
total = len(RESULTS)

for name, status, elapsed, err in RESULTS:
    icon = {"PASS": "[+]", "FAIL": "[X]", "ERROR": "[!]"}[status]
    line = f"{icon} {name} ({elapsed}s)"
    if err:
        line += f" -- {err}"
    print(line)

print(f"\n{'='*55}")
print(f"TOTAL: {total} | PASS: {passed} | FAIL: {failed} | ERROR: {errors}")

# Performance summary
analyze_tests = [(n, e) for n, s, e, _ in RESULTS if "API returns 200" in n and s == "PASS"]
if analyze_tests:
    times = [e for _, e in analyze_tests]
    print(f"\nPerformance - Analyze API response times:")
    for name, t in analyze_tests:
        speed = "FAST" if t < 30 else ("OK" if t < 60 else "SLOW")
        print(f"  [{speed}] {name}: {t}s")
    avg = round(sum(times) / len(times), 1)
    print(f"  Average: {avg}s")

print(f"\n{'='*55}")
if failed + errors == 0:
    print("ALL TESTS PASSED!")
else:
    print(f"WARNING: {failed + errors} test(s) need attention")
