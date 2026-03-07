"""
Stock Investment Analyzer — Flask Application
Main entry point wiring all 8 analysis pillars and serving the frontend.
"""

import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import yfinance as yf
import traceback

from analysis.technical import run_technical_analysis
from analysis.fundamental import run_fundamental_analysis
from analysis.sentiment import run_sentiment_analysis
from analysis.recommendation import compute_recommendation, generate_reasoning
from analysis.scanner import scan_top_picks
from analysis.macro import run_macro_analysis
from analysis.policy import run_policy_analysis
from analysis.institutional import run_institutional_analysis
from analysis.options_intel import run_options_analysis
from analysis.sector_rotation import run_sector_rotation_analysis
from analysis.earnings_outlook import run_earnings_outlook

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "stock-analyzer-secret-key-2026")

# ─── Access Code Configuration ───
ACCESS_CODE = os.environ.get("STOCK_APP_ACCESS_CODE", "StockReferCode5282")


@app.before_request
def require_access_code():
    """Gate every request behind access-code authentication."""
    allowed_endpoints = ("login", "static")
    if request.endpoint in allowed_endpoints:
        return None
    if not session.get("authenticated"):
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page — validates the unique access code."""
    error = None
    if request.method == "POST":
        code = request.form.get("access_code", "").strip()
        if code == ACCESS_CODE:
            session["authenticated"] = True
            return redirect(url_for("index"))
        else:
            error = "Invalid access code. Please try again."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    """Clear session and redirect to login."""
    session.clear()
    return redirect(url_for("login"))


EXCHANGE_SUFFIXES = [
    "",
    ".NS",
    ".BO",
    ".L",
    ".TO",
    ".AX",
    ".HK",
    ".DE",
    ".PA",
]


def resolve_ticker(ticker_symbol):
    """
    Try to resolve a ticker by testing multiple exchange suffixes.
    Returns (yf.Ticker, resolved_symbol, history_df).
    """
    if "." in ticker_symbol:
        t = yf.Ticker(ticker_symbol)
        hist = t.history(period="1y")
        if not hist.empty:
            return t, ticker_symbol, hist
        return None, ticker_symbol, None

    for suffix in EXCHANGE_SUFFIXES:
        try_symbol = ticker_symbol + suffix
        try:
            t = yf.Ticker(try_symbol)
            hist = t.history(period="1y")
            if not hist.empty and len(hist) > 5:
                return t, try_symbol, hist
        except Exception:
            continue

    return None, ticker_symbol, None


def _is_india_ticker(ticker_symbol):
    """Detect if a ticker is listed on Indian exchanges."""
    return ".NS" in ticker_symbol or ".BO" in ticker_symbol


@app.route("/api/search", methods=["GET"])
def search_ticker():
    """Search for stock tickers by name or partial symbol."""
    query = request.args.get("q", "").strip()
    if not query or len(query) < 2:
        return jsonify([])

    try:
        results = []
        search = yf.Search(query)
        if hasattr(search, 'quotes') and search.quotes:
            for q in search.quotes[:8]:
                results.append({
                    "symbol": q.get("symbol", ""),
                    "name": q.get("longname") or q.get("shortname", ""),
                    "exchange": q.get("exchange", ""),
                    "type": q.get("quoteType", ""),
                })
        return jsonify(results)
    except Exception:
        return jsonify([])


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/top-picks")
def top_picks_page():
    return render_template("top_picks.html")


@app.route("/api/top-picks", methods=["GET"])
def top_picks_api():
    try:
        market = request.args.get("market", "all").lower()
        results = scan_top_picks(market=market, top_n=5)
        return jsonify({"picks": results, "market": market, "count": len(results)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Scan failed: {str(e)}", "picks": []}), 500


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    Full 8-pillar stock analysis endpoint.
    Expects JSON: { "ticker": "AAPL" }
    """
    try:
        data = request.get_json()
        if not data or "ticker" not in data:
            return jsonify({"error": "Please provide a ticker symbol"}), 400

        ticker_symbol = data["ticker"].strip().upper()
        if not ticker_symbol:
            return jsonify({"error": "Ticker symbol cannot be empty"}), 400

        # Resolve ticker
        ticker, ticker_symbol, hist = resolve_ticker(ticker_symbol)

        if hist is None or hist.empty:
            return jsonify({
                "error": f"No data found for ticker '{data['ticker'].strip().upper()}'. Please check the symbol."
            }), 404

        # Info
        try:
            info = ticker.info
        except Exception:
            info = {}

        company_name = info.get("longName") or info.get("shortName") or ticker_symbol
        sector = info.get("sector", "")
        is_india = _is_india_ticker(ticker_symbol)

        current_price = round(hist["Close"].iloc[-1], 2) if not hist.empty else None
        prev_close = None
        daily_change = None
        daily_change_pct = None
        if len(hist) >= 2:
            prev_close = round(hist["Close"].iloc[-2], 2)
            daily_change = round(current_price - prev_close, 2)
            daily_change_pct = round((daily_change / prev_close) * 100, 2)

        # ─── Run all 8 analysis pillars ───

        # 1. Technical
        technical = run_technical_analysis(hist.copy())

        # 2. Fundamental (with Piotroski)
        fundamental = run_fundamental_analysis(info)

        # 3. Sentiment (enhanced)
        sentiment = run_sentiment_analysis(ticker_symbol, company_name)

        # 4. Macro
        try:
            macro = run_macro_analysis(ticker_symbol, is_india=is_india)
        except Exception:
            macro = {"score": 50, "environment": "Neutral", "signals": [], "error": "Macro fetch failed"}

        # 5. Policy
        try:
            policy = run_policy_analysis(ticker_symbol, company_name, sector, is_india=is_india)
        except Exception:
            policy = {"score": 50, "policy_stance": "Neutral", "tailwinds": [], "headwinds": [], "error": "Policy fetch failed"}

        # 6. Institutional
        try:
            institutional = run_institutional_analysis(ticker, info)
        except Exception:
            institutional = {"score": 50, "institutional_stance": "Neutral", "signals": [], "error": "Institutional fetch failed"}

        # 7. Options Intelligence (US only)
        try:
            options_intel = run_options_analysis(ticker, ticker_symbol, hist.copy(), current_price)
        except Exception:
            options_intel = {"available": False, "score": 50, "signals": ["Options data unavailable"]}

        # 8. Sector Rotation
        try:
            sector_rotation = run_sector_rotation_analysis(ticker_symbol, sector, hist.copy(), is_india=is_india)
        except Exception:
            sector_rotation = {"score": 50, "rotation_signal": "Neutral", "signals": []}

        # 9. Earnings Outlook
        try:
            earnings = run_earnings_outlook(ticker, info)
        except Exception:
            earnings = {"score": 50, "earnings_momentum": "Neutral", "signals": []}

        # ─── Recommendation (all 8 pillars) ───
        market_regime = technical.get("market_regime", "Unknown")
        recommendation = compute_recommendation(
            technical["score"],
            fundamental["score"],
            sentiment["score"],
            market_regime=market_regime,
            fundamental_data=fundamental,
            macro_score=macro.get("score"),
            policy_score=policy.get("score"),
            institutional_score=institutional.get("score"),
            options_score=options_intel.get("score") if options_intel.get("available") else None,
            sector_score=sector_rotation.get("score"),
            earnings_score=earnings.get("score"),
        )

        reasoning = generate_reasoning(
            technical, fundamental, sentiment, recommendation,
            macro=macro,
            policy=policy,
            institutional=institutional,
            options_intel=options_intel if options_intel.get("available") else None,
            sector=sector_rotation,
            earnings=earnings,
        )

        # ─── Build response ───
        response = {
            "ticker": ticker_symbol,
            "companyName": company_name,
            "currentPrice": current_price,
            "previousClose": prev_close,
            "dailyChange": daily_change,
            "dailyChangePct": daily_change_pct,
            "currency": info.get("currency", "USD"),
            "exchange": info.get("exchange", "N/A"),
            "sector": sector,
            "isIndia": is_india,

            # 8 Pillars
            "technical": technical,
            "fundamental": fundamental,
            "sentiment": sentiment,
            "macro": macro,
            "policy": policy,
            "institutional": institutional,
            "options_intel": options_intel,
            "sector_rotation": sector_rotation,
            "earnings": earnings,

            # Recommendation
            "recommendation": recommendation,
            "reasoning": reasoning,
        }

        return jsonify(response)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500


if __name__ == "__main__":
    print("\n>>> Stock Investment Analyzer (8-Pillar) running at http://localhost:5000\n")
    app.run(debug=True, port=5000)
