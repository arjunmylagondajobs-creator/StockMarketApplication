"""
Sentiment Analysis Module — Enhanced
Fetches recent news headlines and applies weighted sentiment scoring.
Improvements over basic version:
- Source tier weighting (Bloomberg, Reuters = 2x; unknown = 0.5x)
- Recency weighting (last 24h = 3x, last week = 1.5x, older = 1x)
- Headline category tagging (earnings, policy, macro, legal, management, general)
- Stronger phrase matching (multi-word financial phrases)
"""

import requests
from bs4 import BeautifulSoup
import re


# ── Positive and negative single-word/phrase signals ──
POSITIVE_WORDS = {
    "surge", "surges", "surging", "rally", "rallies", "rallying", "gain", "gains",
    "rise", "rises", "rising", "jump", "jumps", "soar", "soars", "soaring",
    "bull", "bullish", "upgrade", "upgrades", "upgraded", "beat", "beats",
    "outperform", "outperforms", "record", "high", "highs", "profit", "profits",
    "growth", "growing", "strong", "strength", "boost", "boosts", "boosted",
    "positive", "optimistic", "buy", "breakout", "breakthrough", "innovation",
    "expand", "expands", "expansion", "upbeat", "recover", "recovery",
    "dividend", "revenue", "earnings", "exceed", "exceeds", "exceeded",
    "impressive", "robust", "momentum", "opportunity", "successful", "success",
    "approve", "approved", "approval", "partnership", "deal", "acquisition",
    "win", "winning", "accelerate", "launch", "contract", "order"
}

NEGATIVE_WORDS = {
    "crash", "crashes", "crashing", "fall", "falls", "falling", "drop", "drops",
    "decline", "declines", "declining", "plunge", "plunges", "plunging",
    "bear", "bearish", "downgrade", "downgrades", "downgraded", "miss", "misses",
    "underperform", "underperforms", "loss", "losses", "losing", "weak",
    "weakness", "cut", "cuts", "negative", "pessimistic", "sell", "selloff",
    "concern", "concerns", "worried", "worry", "risk", "risks", "risky",
    "debt", "lawsuit", "lawsuits", "sue", "sued", "fine", "fined", "penalty",
    "layoff", "layoffs", "fired", "restructuring", "bankrupt", "bankruptcy",
    "fraud", "scandal", "investigation", "probe", "warning", "warns",
    "recession", "slowdown", "slowing", "stagnant", "volatile", "volatility",
    "disappoint", "disappointing", "disappointed", "fails", "fail", "failure",
    "recall", "ban", "sanction", "tariff", "headwind"
}

# ── High-signal financial phrases (weighted 2x) ──
STRONG_POSITIVE_PHRASES = [
    "beats estimates", "beats expectations", "raises guidance", "raises outlook",
    "price target raised", "target raised", "upgraded to buy", "initiated buy",
    "record revenue", "record earnings", "record profit", "margin expansion",
    "strong quarterly", "earnings beat", "revenue beat", "strong demand",
    "new all-time high", "strategic acquisition", "major contract", "dividends raised"
]

STRONG_NEGATIVE_PHRASES = [
    "misses estimates", "misses expectations", "cuts guidance", "lowers outlook",
    "price target cut", "target lowered", "downgraded to sell", "earnings miss",
    "revenue miss", "margin compression", "profit warning", "layoffs announced",
    "class action", "sec investigation", "accounting irregularities",
    "dividend cut", "dividend suspended", "debt downgrade"
]

# ── Source tiers (multipliers for scoring) ──
TIER1_SOURCES = {
    "reuters", "bloomberg", "financial times", "wall street journal", "wsj",
    "economic times", "the hindu businessline", "mint", "moneycontrol",
    "cnbc", "ft.com", "barrons", "marketwatch"
}
TIER2_SOURCES = {
    "business standard", "livemint", "the motley fool", "seeking alpha",
    "investopedia", "yahoo finance", "bse india", "nse india", "msn money"
}

# ── Headline category keywords ──
CATEGORY_TAGS = {
    "earnings":   ["earnings", "quarterly", "revenue", "profit", "eps", "results", "guidance", "q1", "q2", "q3", "q4"],
    "policy":     ["rbi", "fed", "sebi", "government", "policy", "regulation", "budget", "gst", "rate", "tariff"],
    "macro":      ["inflation", "gdp", "economy", "recession", "rate cut", "rate hike", "unemployment", "cpi"],
    "legal":      ["lawsuit", "sue", "fraud", "investigation", "probe", "fine", "penalty", "class action"],
    "management": ["ceo", "cfo", "management", "leadership", "board", "resignation", "appointed", "founder"],
}


def _categorize_headline(headline_lower):
    """Tag a headline with its primary category."""
    for category, keywords in CATEGORY_TAGS.items():
        if any(kw in headline_lower for kw in keywords):
            return category
    return "general"


def _get_source_multiplier(source):
    """Return scoring multiplier based on source tier."""
    s = source.lower() if source else ""
    for t1 in TIER1_SOURCES:
        if t1 in s:
            return 2.0
    for t2 in TIER2_SOURCES:
        if t2 in s:
            return 1.3
    return 0.8


def fetch_news_headlines(ticker, company_name=""):
    """
    Fetch recent news headlines from Google News RSS.
    Returns list of {title, link, source} dicts.
    """
    headlines = []
    base_ticker = ticker.split(".")[0] if "." in ticker else ticker

    queries = [f'"{base_ticker}" stock']
    if company_name and company_name != "Unknown" and len(company_name) > 2:
        clean_company = company_name
        for suf in ["Limited", "Ltd", "Inc.", "Inc", "Corporation", "Corp.", "Corp",
                    "Incorporated", "Holdings", "Group", "PLC", "plc", "N.V.", "S.A."]:
            clean_company = clean_company.replace(suf, "").strip()
        if clean_company and len(clean_company) > 2:
            queries.append(f'"{clean_company}" stock')

    relevance_keywords = _build_relevance_keywords(base_ticker, company_name)

    for query in queries:
        try:
            url = f"https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "html.parser")
                for item in soup.find_all("item")[:15]:
                    title_tag = item.find("title")
                    link_tag = item.find("link")
                    source_tag = item.find("source")
                    pub_date_tag = item.find("pubDate")

                    if title_tag:
                        title_text = title_tag.text.strip()
                        if not _is_headline_relevant(title_text, relevance_keywords):
                            continue
                        headline = {
                            "title": title_text,
                            "link": link_tag.next_sibling.strip() if link_tag and link_tag.next_sibling else "",
                            "source": source_tag.text.strip() if source_tag else "Unknown",
                            "pub_date": pub_date_tag.text.strip() if pub_date_tag else ""
                        }
                        if headline["title"] not in [h["title"] for h in headlines]:
                            headlines.append(headline)
        except Exception:
            continue

    return headlines[:14]


def _build_relevance_keywords(base_ticker, company_name):
    """Build keyword set for relevance filtering."""
    keywords = set()
    keywords.add(base_ticker.lower())
    keywords.add(f"{base_ticker.lower()}.ns")
    keywords.add(f"{base_ticker.lower()}.bo")

    if company_name and company_name != "Unknown":
        keywords.add(company_name.lower())
        skip_words = {
            "limited", "ltd", "inc", "corp", "corporation", "company", "co",
            "technologies", "technology", "tech", "services", "solutions",
            "industries", "industrial", "group", "holdings", "international",
            "global", "the", "and", "of", "for", "new", "india", "pvt",
            "private", "public", "enterprise", "enterprises", "systems"
        }
        for part in company_name.split():
            clean_part = re.sub(r'[^a-zA-Z]', '', part).lower()
            if len(clean_part) >= 4 and clean_part not in skip_words:
                keywords.add(clean_part)
    return keywords


def _is_headline_relevant(headline, relevance_keywords):
    """Check if headline is about the specific stock."""
    headline_lower = headline.lower()
    return any(kw in headline_lower for kw in relevance_keywords)


def score_headline(headline_text, source="", pub_date=""):
    """
    Score a single headline using enhanced weighting.
    Returns a value between -2 and 2 (stronger than before due to phrase matching).
    """
    headline_lower = headline_text.lower()
    words = set(re.findall(r'\b\w+\b', headline_lower))

    pos_count = len(words & POSITIVE_WORDS)
    neg_count = len(words & NEGATIVE_WORDS)

    # Phrase bonuses
    phrase_bonus = 0
    for phrase in STRONG_POSITIVE_PHRASES:
        if phrase in headline_lower:
            phrase_bonus += 1.5
    for phrase in STRONG_NEGATIVE_PHRASES:
        if phrase in headline_lower:
            phrase_bonus -= 1.5

    total = pos_count + neg_count
    raw_score = (pos_count - neg_count) / max(total, 1) if total > 0 else 0
    combined = raw_score + (phrase_bonus * 0.3)

    # Source multiplier (0.8 – 2.0)
    source_mult = _get_source_multiplier(source)
    combined *= source_mult

    # Recency multiplier (simple: newer articles in pub_date string are first)
    # We can't parse exact times reliably across feeds, so use list position weighting
    # (handled in run_sentiment_analysis with enumerate)

    return max(-2.0, min(2.0, combined))


def classify_sentiment(score):
    """Classify a -2 to 2 score into a label."""
    if score > 0.5:
        return "Positive"
    elif score > 0.15:
        return "Slightly Positive"
    elif score < -0.5:
        return "Negative"
    elif score < -0.15:
        return "Slightly Negative"
    else:
        return "Neutral"


def run_sentiment_analysis(ticker, company_name=""):
    """
    Enhanced sentiment analysis with source weighting, recency weighting,
    phrase detection, and headline categorization.
    """
    result = {
        "headlines": [],
        "overall_sentiment": "Neutral",
        "score": 50,
        "positive_count": 0,
        "negative_count": 0,
        "neutral_count": 0,
        "category_breakdown": {},
        "error": None
    }

    headlines = fetch_news_headlines(ticker, company_name)

    if not headlines:
        result["error"] = "Could not fetch news headlines. Sentiment score defaulted to neutral."
        return result

    scored_headlines = []
    sentiment_scores = []
    category_scores = {}
    n = len(headlines)

    for i, h in enumerate(headlines):
        # Recency multiplier: earlier in list = more recent (RSS is newest-first)
        recency_mult = 3.0 if i < 2 else (1.5 if i < int(n * 0.4) else 1.0)

        raw_sent_score = score_headline(h["title"], h.get("source", ""), h.get("pub_date", ""))
        weighted_score = raw_sent_score * recency_mult

        # Normalize to -1..1 range for aggregation
        normalized = max(-1.0, min(1.0, weighted_score / 2.0))
        sentiment_scores.append(normalized)

        # Categorize
        category = _categorize_headline(h["title"].lower())
        if category not in category_scores:
            category_scores[category] = []
        category_scores[category].append(normalized)

        label = classify_sentiment(raw_sent_score)
        scored_headlines.append({
            "title": h["title"],
            "link": h.get("link", ""),
            "source": h.get("source", ""),
            "sentiment_score": round(raw_sent_score, 2),
            "sentiment_label": label,
            "category": category,
        })

        if label in ("Positive", "Slightly Positive"):
            result["positive_count"] += 1
        elif label in ("Negative", "Slightly Negative"):
            result["negative_count"] += 1
        else:
            result["neutral_count"] += 1

    result["headlines"] = scored_headlines

    # Category breakdown
    result["category_breakdown"] = {
        cat: round(sum(scores) / len(scores), 2)
        for cat, scores in category_scores.items() if scores
    }

    # Composite score (0–100)
    if sentiment_scores:
        # Weighted average (earlier headlines already have recency-baked)
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
        result["score"] = max(0, min(100, int(50 + avg_sentiment * 50)))

    # Label
    s = result["score"]
    if s > 68:
        result["overall_sentiment"] = "Bullish"
    elif s > 57:
        result["overall_sentiment"] = "Slightly Bullish"
    elif s < 32:
        result["overall_sentiment"] = "Bearish"
    elif s < 43:
        result["overall_sentiment"] = "Slightly Bearish"
    else:
        result["overall_sentiment"] = "Neutral"

    return result
