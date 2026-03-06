"""
Government Policy & Regulatory Analysis Module
Detects tailwinds and headwinds from government policies, regulations,
and sector-specific initiatives via news scraping.
"""

import requests
from bs4 import BeautifulSoup
import re


# ── Sector → policy search terms ──
SECTOR_POLICY_TERMS = {
    "Technology": [
        "PLI scheme electronics", "semiconductor India policy", "IT sector tax",
        "digital India", "data protection bill", "AI regulation India",
        "tech tariff", "software export benefit"
    ],
    "Financial Services": [
        "RBI regulation bank", "SEBI new rules", "banking sector reform",
        "NPA regulation", "credit policy RBI", "bank license SEBI",
        "fintech regulation India"
    ],
    "Healthcare": [
        "pharma PLI scheme", "drug price control NPPA", "medical device policy",
        "healthcare FDI", "pharma export benefit", "drug recall FDA",
        "biosimilar approval"
    ],
    "Energy": [
        "renewable energy policy India", "solar PLI", "green hydrogen mission",
        "coal auction policy", "oil subsidy India", "energy tariff CERC",
        "net zero India policy"
    ],
    "Consumer Cyclical": [
        "GST rate consumer", "consumer goods PLI", "auto EV policy",
        "FAME scheme EV", "luxury tax", "consumption boost budget"
    ],
    "Consumer Defensive": [
        "FMCG GST", "food subsidy policy", "MSP agriculture",
        "food inflation government", "essential goods regulation"
    ],
    "Industrials": [
        "infrastructure budget India", "capex government scheme",
        "defence PLI scheme", "Make in India manufacturing",
        "import duty steel", "infrastructure push government"
    ],
    "Basic Materials": [
        "steel import duty", "mining regulation India", "commodity export ban",
        "minerals policy", "cement industry policy"
    ],
    "Real Estate": [
        "affordable housing scheme", "RERA regulation", "home loan subsidy",
        "stamp duty real estate", "REIT regulation SEBI"
    ],
    "Communication Services": [
        "telecom spectrum auction", "5G policy India", "OTT regulation",
        "TRAI regulation", "media FDI policy"
    ],
    "Utilities": [
        "power tariff regulation", "electricity act amendment",
        "discoms reform", "power sector privatization"
    ],
}

# Generic cross-sector policy terms always checked
GENERIC_POLICY_TERMS = [
    "budget 2025 sector", "FDI policy India", "divestment government",
    "corporate tax cut", "import duty hike", "export incentive",
    "RBI repo rate", "federal reserve rate hike", "rate cut Fed",
    "tariff war trade", "sanctions impact"
]

# Positive policy keywords (tailwinds)
POLICY_POSITIVE = {
    "scheme", "pli", "boost", "benefit", "incentive", "subsidy", "cut",
    "support", "approval", "invest", "promote", "ease", "reform",
    "liberalize", "relaxed", "waiver", "exempt", "rebate", "concession",
    "budget allocation", "capex", "stimulus", "green light", "approved",
    "launch", "initiative", "mission", "fund", "package"
}

# Negative policy keywords (headwinds)
POLICY_NEGATIVE = {
    "ban", "restrict", "levy", "hike", "penalty", "fine", "probe",
    "investigation", "regulation tighten", "crackdown", "cap", "ceiling",
    "sanction", "import duty increase", "windfall tax", "price control",
    "cess", "surcharge", "recall", "prohibit", "rejected", "cancelled",
    "delayed", "suspended", "compliance burden"
}


def _fetch_policy_news(queries, max_headlines=10):
    """Fetch news headlines for given policy queries from Google News RSS."""
    headlines = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    seen = set()

    for query in queries[:4]:  # limit to 4 queries for speed
        try:
            url = f"https://news.google.com/rss/search?q={query}&hl=en&gl=IN&ceid=IN:en"
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.content, "html.parser")
            for item in soup.find_all("item")[:6]:
                title_tag = item.find("title")
                if title_tag:
                    title = title_tag.text.strip()
                    if title not in seen:
                        seen.add(title)
                        headlines.append(title)
                        if len(headlines) >= max_headlines:
                            return headlines
        except Exception:
            continue
    return headlines


def _score_policy_headline(headline):
    """Score a single policy headline for tailwind/headwind sentiment."""
    words = set(re.findall(r'\b\w+\b', headline.lower()))
    pos = len(words & POLICY_POSITIVE)
    neg = len(words & POLICY_NEGATIVE)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total


def run_policy_analysis(ticker_symbol, company_name="", sector="", is_india=False):
    """
    Analyze government policy and regulatory environment for a stock.
    Returns structured dict with policy score (0-100) and key signals.
    """
    result = {
        "score": 50,
        "policy_stance": "Neutral",
        "tailwinds": [],
        "headwinds": [],
        "headlines": [],
        "error": None
    }

    # Build relevant search queries
    queries = list(GENERIC_POLICY_TERMS[:4])  # generic always included

    # Add sector-specific queries
    if sector and sector in SECTOR_POLICY_TERMS:
        queries = SECTOR_POLICY_TERMS[sector][:3] + queries

    # Add company/ticker specific
    base_ticker = ticker_symbol.split(".")[0] if "." in ticker_symbol else ticker_symbol
    if company_name and len(company_name) > 3:
        clean_name = company_name.split()[0] if company_name else base_ticker
        queries.insert(0, f'"{clean_name}" government policy')

    headlines = _fetch_policy_news(queries, max_headlines=12)

    if not headlines:
        result["error"] = "Could not fetch policy news. Using neutral score."
        return result

    # Score headlines
    scores = []
    tailwinds = []
    headwinds = []
    scored_headlines = []

    for h in headlines:
        s = _score_policy_headline(h)
        scores.append(s)
        scored_headlines.append({"title": h, "score": round(s, 2)})
        if s > 0.1:
            tailwinds.append(h[:120])
        elif s < -0.1:
            headwinds.append(h[:120])

    result["headlines"] = scored_headlines[:8]
    result["tailwinds"] = tailwinds[:3]
    result["headwinds"] = headwinds[:3]

    if scores:
        avg = sum(scores) / len(scores)
        policy_score = max(0, min(100, int(50 + avg * 60)))
    else:
        policy_score = 50

    result["score"] = policy_score

    if policy_score >= 68:
        result["policy_stance"] = "Strong Policy Tailwind"
    elif policy_score >= 57:
        result["policy_stance"] = "Mild Policy Tailwind"
    elif policy_score >= 43:
        result["policy_stance"] = "Neutral / Mixed Policy"
    elif policy_score >= 32:
        result["policy_stance"] = "Mild Policy Headwind"
    else:
        result["policy_stance"] = "Significant Policy Risk"

    return result
