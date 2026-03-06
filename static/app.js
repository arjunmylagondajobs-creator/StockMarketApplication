/**
 * Stock Investment Analyzer PRO — Frontend (8-Pillar)
 * Renders: pillar cards, radar chart, weight allocation, Piotroski,
 * score ring, price/RSI/MACD charts, metrics, news, reasoning.
 */

let priceChart = null;
let rsiChart = null;
let macdChart = null;
let radarChart = null;
let searchTimeout = null;
let dropdownVisible = false;

// ── Core Functions ──
function quickAnalyze(ticker) {
    document.getElementById('tickerInput').value = ticker;
    analyzeStock();
}

function analyzeStock() {
    const ticker = document.getElementById('tickerInput').value.trim();
    if (!ticker) return;

    hideError();
    hideResults();
    showLoading(ticker);

    fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker })
    })
        .then(r => r.json().then(data => ({ status: r.status, data })))
        .then(({ status, data }) => {
            hideLoading();
            if (data.error) {
                showError(data.error);
            } else {
                renderResults(data);
                showResults();
            }
        })
        .catch(err => {
            hideLoading();
            showError('Network error — is the server running?');
        });
}

// ── Search Autocomplete ──
function searchTickers(query) {
    fetch(`/api/search?q=${encodeURIComponent(query)}`)
        .then(r => r.json())
        .then(results => {
            if (results.length > 0) showDropdown(results);
            else hideDropdown();
        })
        .catch(() => hideDropdown());
}

function showDropdown(results) {
    hideDropdown();
    const container = document.querySelector('.search-container');
    const dd = document.createElement('div');
    dd.className = 'search-dropdown';
    dd.id = 'searchDropdown';
    results.forEach(r => {
        const item = document.createElement('div');
        item.className = 'dropdown-item';
        item.innerHTML = `
            <span class="dropdown-symbol">${escapeHtml(r.symbol)}</span>
            <span class="dropdown-name">${escapeHtml(r.name)}</span>
            <span class="dropdown-exchange">${escapeHtml(r.exchange || '')}</span>`;
        item.onclick = () => selectTicker(r.symbol);
        dd.appendChild(item);
    });
    container.appendChild(dd);
    dropdownVisible = true;
}

function hideDropdown() {
    const dd = document.getElementById('searchDropdown');
    if (dd) dd.remove();
    dropdownVisible = false;
}
function selectTicker(symbol) {
    document.getElementById('tickerInput').value = symbol;
    hideDropdown();
    analyzeStock();
}

// Input events
const tickerInput = document.getElementById('tickerInput');
tickerInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { hideDropdown(); analyzeStock(); }
    if (e.key === 'Escape') hideDropdown();
});
tickerInput.addEventListener('input', (e) => {
    const q = e.target.value.trim();
    clearTimeout(searchTimeout);
    if (q.length >= 2) {
        searchTimeout = setTimeout(() => searchTickers(q), 300);
    } else {
        hideDropdown();
    }
});
document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-container')) hideDropdown();
});

// ── UI Helpers ──
function showLoading(ticker) {
    document.getElementById('loadingTicker').textContent = ticker;
    document.getElementById('loadingOverlay').classList.remove('hidden');
}
function hideLoading() { document.getElementById('loadingOverlay').classList.add('hidden'); }
function showError(msg) {
    document.getElementById('errorMessage').textContent = msg;
    document.getElementById('errorContainer').classList.remove('hidden');
}
function hideError() { document.getElementById('errorContainer').classList.add('hidden'); }
function showResults() { document.getElementById('resultsSection').classList.remove('hidden'); }
function hideResults() { document.getElementById('resultsSection').classList.add('hidden'); }

// ── Main Render ──
function renderResults(data) {
    renderStockHeader(data);
    renderRecommendation(data.recommendation);
    renderPillarCards(data);
    renderRadarChart(data);
    renderWeightBars(data.recommendation);
    renderCharts(data.technical);
    renderMetrics(data.fundamental?.metrics || {});
    renderPiotroski(data.fundamental);
    renderNews(data.sentiment);
    renderReasoning(data.reasoning);
}

// ── Stock Header ──
function renderStockHeader(data) {
    document.getElementById('companyName').textContent = data.companyName || data.ticker;
    document.getElementById('tickerBadge').textContent = data.ticker;
    document.getElementById('exchangeBadge').textContent = data.exchange || '';

    const sectorBadge = document.getElementById('sectorBadge');
    if (data.sector) {
        sectorBadge.textContent = data.sector;
        sectorBadge.style.display = 'inline-block';
    } else {
        sectorBadge.style.display = 'none';
    }

    const currency = data.currency || 'USD';
    const sym = currency === 'INR' ? '₹' : '$';
    document.getElementById('currentPrice').textContent = data.currentPrice ? `${sym}${data.currentPrice.toLocaleString()}` : '—';

    const changeEl = document.getElementById('dailyChange');
    if (data.dailyChange != null) {
        const sign = data.dailyChange >= 0 ? '+' : '';
        changeEl.textContent = `${sign}${data.dailyChange.toFixed(2)} (${sign}${data.dailyChangePct}%)`;
        changeEl.className = `daily-change ${data.dailyChange >= 0 ? 'positive' : 'negative'}`;
    } else {
        changeEl.textContent = '—';
    }
}

// ── Recommendation Banner ──
function renderRecommendation(rec) {
    if (!rec) return;
    const banner = document.getElementById('recommendationBanner');
    const color = rec.color || '#ff9800';
    banner.style.borderColor = color;
    banner.querySelector('::before')?.style && (banner.style.background = `linear-gradient(135deg, ${hexToRgba(color, 0.06)}, transparent)`);

    const verdictEl = document.getElementById('verdictText');
    verdictEl.textContent = rec.verdict;
    verdictEl.style.color = color;

    // Score ring animation
    const score = rec.final_score || 0;
    const scoreEl = document.getElementById('finalScore');
    const circumference = 2 * Math.PI * 42; // ~264
    const ringCircle = document.getElementById('scoreRingCircle');
    const ringColor = getScoreColor(score);
    setTimeout(() => {
        const dash = (score / 100) * circumference;
        ringCircle.setAttribute('stroke-dasharray', `${dash} ${circumference}`);
        ringCircle.setAttribute('stroke', ringColor);
    }, 100);
    animateNumber(scoreEl, score);

    document.getElementById('confidenceText').textContent = `${rec.confidence || '—'} (${rec.confidence_pct || 0}%)`;

    const regimeEl = document.getElementById('marketRegime');
    regimeEl.textContent = rec.market_regime || 'Unknown';
    const regime = rec.market_regime || '';
    if (regime.includes('Bullish')) { regimeEl.style.background = 'var(--accent-green-dim)'; regimeEl.style.color = 'var(--accent-green)'; }
    else if (regime.includes('Bearish')) { regimeEl.style.background = 'var(--accent-red-dim)'; regimeEl.style.color = 'var(--accent-red)'; }
}

// ── 8-Pillar Cards ──
function renderPillarCards(data) {
    const pillars = [
        { key: 'technical', scoreId: 'techPillarScore', barId: 'techBar', sigId: 'technicalSignals', dataKey: 'technical' },
        { key: 'fundamental', scoreId: 'fundPillarScore', barId: 'fundBar', sigId: 'fundamentalSignals', dataKey: 'fundamental' },
        { key: 'sentiment', scoreId: 'sentPillarScore', barId: 'sentBar', sigId: 'sentimentSignals', dataKey: 'sentiment' },
        { key: 'macro', scoreId: 'macroPillarScore', barId: 'macroBar', sigId: 'macroSignals', dataKey: 'macro' },
        { key: 'policy', scoreId: 'policyPillarScore', barId: 'policyBar', sigId: 'policySignals', dataKey: 'policy' },
        { key: 'institutional', scoreId: 'instPillarScore', barId: 'instBar', sigId: 'institutionalSignals', dataKey: 'institutional' },
        { key: 'options_intel', scoreId: 'optPillarScore', barId: 'optBar', sigId: 'optionsSignals', dataKey: 'options_intel' },
        { key: 'sector_rotation', scoreId: 'secPillarScore', barId: 'secBar', sigId: 'sectorSignals', dataKey: 'sector_rotation' },
        { key: 'earnings', scoreId: 'earnPillarScore', barId: 'earnBar', sigId: 'earningsSignals', dataKey: 'earnings' },
    ];

    pillars.forEach(p => {
        const d = data[p.dataKey] || {};
        const score = d.score ?? 50;
        const color = getScoreColor(score);

        // Score number
        const scoreEl = document.getElementById(p.scoreId);
        scoreEl.style.color = color;
        animateNumber(scoreEl, score);

        // Bar
        const barEl = document.getElementById(p.barId);
        setTimeout(() => {
            barEl.style.width = `${score}%`;
            barEl.style.background = score >= 60 ? 'var(--gradient-bullish)' : score >= 40 ? 'var(--gradient-neutral)' : 'var(--gradient-bearish)';
        }, 100);

        // Signals
        const sigEl = document.getElementById(p.sigId);
        const signals = d.signals || d.insider_signals || d.short_signals || [];
        const allSigs = [...(d.signals || []), ...(d.insider_signals || []), ...(d.short_signals || []), ...(d.estimate_signals || [])];
        const limitedSigs = allSigs.filter((v, i, a) => a.indexOf(v) === i).slice(0, 4);

        let sigHtml = '';
        // Add stance/environment if available
        if (d.environment) sigHtml += `<div class="signal"><strong>Environment:</strong> ${escapeHtml(d.environment)}</div>`;
        if (d.policy_stance) sigHtml += `<div class="signal"><strong>Stance:</strong> ${escapeHtml(d.policy_stance)}</div>`;
        if (d.institutional_stance) sigHtml += `<div class="signal"><strong>Smart Money:</strong> ${escapeHtml(d.institutional_stance)}</div>`;
        if (d.options_sentiment) sigHtml += `<div class="signal"><strong>Sentiment:</strong> ${escapeHtml(d.options_sentiment)}</div>`;
        if (d.rotation_signal) sigHtml += `<div class="signal"><strong>Signal:</strong> ${escapeHtml(d.rotation_signal)}</div>`;
        if (d.earnings_momentum) sigHtml += `<div class="signal"><strong>Momentum:</strong> ${escapeHtml(d.earnings_momentum)}</div>`;
        if (d.overall_sentiment) sigHtml += `<div class="signal"><strong>Overall:</strong> ${escapeHtml(d.overall_sentiment)}</div>`;

        limitedSigs.forEach(s => sigHtml += `<div class="signal">${escapeHtml(s)}</div>`);

        // Tailwinds/Headwinds
        (d.tailwinds || []).slice(0, 2).forEach(t => sigHtml += `<div class="signal" style="color:var(--accent-green)">✅ ${escapeHtml(t.slice(0, 80))}</div>`);
        (d.headwinds || []).slice(0, 2).forEach(h => sigHtml += `<div class="signal" style="color:var(--accent-red)">⚠️ ${escapeHtml(h.slice(0, 80))}</div>`);

        sigEl.innerHTML = sigHtml || '<div class="signal" style="opacity:0.5">No specific signals</div>';

        // Options card: grey out if not available
        if (p.key === 'options_intel' && !d.available) {
            const card = document.getElementById('optionsCard');
            card.style.opacity = '0.5';
            sigEl.innerHTML = '<div class="signal">Options data not available for this stock</div>';
        }
    });
}

// ── Radar Chart ──
function renderRadarChart(data) {
    const ctx = document.getElementById('radarChart').getContext('2d');
    if (radarChart) radarChart.destroy();

    const labels = ['Technical', 'Fundamental', 'Sentiment', 'Macro', 'Policy', 'Institutional', 'Options', 'Sector', 'Earnings'];
    const scores = [
        data.technical?.score ?? 0,
        data.fundamental?.score ?? 0,
        data.sentiment?.score ?? 0,
        data.macro?.score ?? 0,
        data.policy?.score ?? 0,
        data.institutional?.score ?? 0,
        data.options_intel?.score ?? 0,
        data.sector_rotation?.score ?? 0,
        data.earnings?.score ?? 0,
    ];

    radarChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels,
            datasets: [{
                label: 'Score',
                data: scores,
                backgroundColor: 'rgba(0, 230, 118, 0.12)',
                borderColor: '#00e676',
                borderWidth: 2,
                pointBackgroundColor: scores.map(s => getScoreColor(s)),
                pointBorderColor: '#0d1117',
                pointBorderWidth: 2,
                pointRadius: 5,
                pointHoverRadius: 7,
            }]
        },
        options: {
            responsive: true,
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        stepSize: 25,
                        font: { size: 10, family: 'Inter' },
                        color: 'rgba(255,255,255,0.2)',
                        backdropColor: 'transparent',
                    },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    angleLines: { color: 'rgba(255,255,255,0.05)' },
                    pointLabels: {
                        font: { size: 11, weight: '600', family: 'Inter' },
                        color: '#8b949e',
                    }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#1c2333',
                    titleFont: { family: 'Inter', weight: '700' },
                    bodyFont: { family: 'Inter' },
                    callbacks: {
                        label: (ctx) => `${ctx.label}: ${ctx.raw}/100`
                    }
                }
            },
            animation: { duration: 1200 }
        }
    });
}

// ── Weight Bars ──
function renderWeightBars(rec) {
    const weights = rec?.weights_used || {};
    const container = document.getElementById('weightBars');
    const colorMap = {
        technical: '#00e676', fundamental: '#58a6ff', sentiment: '#ff9800',
        macro: '#22d3ee', policy: '#bb86fc', institutional: '#f472b6',
        options: '#ffc107', sector: '#00bfa5', earnings: '#ef4444'
    };
    let html = '';
    const sorted = Object.entries(weights).sort((a, b) => b[1] - a[1]);
    sorted.forEach(([key, pct]) => {
        const color = colorMap[key] || '#8b949e';
        html += `
            <div class="weight-row">
                <span class="weight-label">${key.charAt(0).toUpperCase() + key.slice(1)}</span>
                <div class="weight-bar-track">
                    <div class="weight-bar-fill" style="width:${pct}%;background:${color}"></div>
                </div>
                <span class="weight-pct">${pct}%</span>
            </div>`;
    });
    container.innerHTML = html;
}

// ── Charts ──
function renderCharts(tech) {
    if (!tech || !tech.chart_data) return;
    const cd = tech.chart_data;
    const chartFont = { family: 'Inter', size: 11 };

    // Destroy old charts
    if (priceChart) priceChart.destroy();
    if (rsiChart) rsiChart.destroy();
    if (macdChart) macdChart.destroy();

    const last90 = Math.max(0, (cd.dates || []).length - 90);
    const dates = (cd.dates || []).slice(last90);
    const closes = (cd.closes || []).slice(last90);
    const sma20 = (cd.sma20 || []).slice(last90);
    const sma50 = (cd.sma50 || []).slice(last90);
    const sma200 = (cd.sma200 || []).slice(last90);
    const upper = (cd.bb_upper || []).slice(last90);
    const lower = (cd.bb_lower || []).slice(last90);
    const rsi = (cd.rsi || []).slice(last90);
    const macd_line = (cd.macd_line || []).slice(last90);
    const signal_line = (cd.signal_line || []).slice(last90);
    const histogram = (cd.histogram || []).slice(last90);

    const baseOpts = {
        responsive: true,
        interaction: { intersect: false, mode: 'index' },
        plugins: {
            legend: {
                labels: { font: chartFont, color: '#8b949e', boxWidth: 10, padding: 12 }
            },
            tooltip: {
                backgroundColor: '#1c2333', titleFont: { ...chartFont, weight: '700' },
                bodyFont: chartFont, borderColor: '#30363d', borderWidth: 1
            }
        },
        scales: {
            x: {
                ticks: { font: { ...chartFont, size: 10 }, color: '#6e7681', maxTicksLimit: 10, maxRotation: 0 },
                grid: { color: 'rgba(255,255,255,0.03)' }
            },
            y: {
                ticks: { font: chartFont, color: '#6e7681' },
                grid: { color: 'rgba(255,255,255,0.04)' }
            }
        }
    };

    // Price Chart
    priceChart = new Chart(document.getElementById('priceChart').getContext('2d'), {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                { label: 'Price', data: closes, borderColor: '#e6edf3', borderWidth: 2, pointRadius: 0, fill: false },
                { label: 'SMA 20', data: sma20, borderColor: '#00e676', borderWidth: 1.2, borderDash: [4, 3], pointRadius: 0, fill: false },
                { label: 'SMA 50', data: sma50, borderColor: '#ff9800', borderWidth: 1.2, borderDash: [4, 3], pointRadius: 0, fill: false },
                { label: 'SMA 200', data: sma200, borderColor: '#f44336', borderWidth: 1.2, borderDash: [6, 3], pointRadius: 0, fill: false },
                { label: 'BB Upper', data: upper, borderColor: 'rgba(88,166,255,0.3)', borderWidth: 1, pointRadius: 0, fill: false },
                {
                    label: 'BB Lower', data: lower, borderColor: 'rgba(88,166,255,0.3)', borderWidth: 1, pointRadius: 0, fill: '-1',
                    backgroundColor: 'rgba(88,166,255,0.04)'
                },
            ]
        },
        options: baseOpts
    });

    // RSI
    rsiChart = new Chart(document.getElementById('rsiChart').getContext('2d'), {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                { label: 'RSI', data: rsi, borderColor: '#bb86fc', borderWidth: 2, pointRadius: 0, fill: false },
                { label: 'Overbought', data: Array(dates.length).fill(70), borderColor: 'rgba(244,67,54,0.3)', borderWidth: 1, borderDash: [5, 5], pointRadius: 0, fill: false },
                { label: 'Oversold', data: Array(dates.length).fill(30), borderColor: 'rgba(0,230,118,0.3)', borderWidth: 1, borderDash: [5, 5], pointRadius: 0, fill: false },
            ]
        },
        options: { ...baseOpts, scales: { ...baseOpts.scales, y: { ...baseOpts.scales.y, min: 0, max: 100 } } }
    });

    // MACD
    macdChart = new Chart(document.getElementById('macdChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: dates,
            datasets: [
                { type: 'line', label: 'MACD', data: macd_line, borderColor: '#58a6ff', borderWidth: 1.5, pointRadius: 0, fill: false, order: 1 },
                { type: 'line', label: 'Signal', data: signal_line, borderColor: '#ff9800', borderWidth: 1.5, pointRadius: 0, fill: false, order: 2 },
                { label: 'Histogram', data: histogram, backgroundColor: histogram.map(v => v >= 0 ? 'rgba(0,230,118,0.5)' : 'rgba(244,67,54,0.5)'), borderWidth: 0, order: 3 },
            ]
        },
        options: baseOpts
    });
}

// ── Metrics ──
function renderMetrics(metrics) {
    const grid = document.getElementById('metricsGrid');
    const items = [
        { label: 'Market Cap', value: metrics.marketCapFormatted || '—' },
        { label: 'P/E Ratio', value: fmtNum(metrics.peRatio) },
        { label: 'Forward P/E', value: fmtNum(metrics.forwardPE) },
        { label: 'PEG Ratio', value: fmtNum(metrics.pegRatio) },
        { label: 'Revenue Growth', value: fmtPct(metrics.revenueGrowth) },
        { label: 'Earnings Growth', value: fmtPct(metrics.earningsGrowth) },
        { label: 'Profit Margin', value: fmtPct(metrics.profitMargin) },
        { label: 'Gross Margin', value: fmtPct(metrics.grossMargin) },
        { label: 'EBITDA Margin', value: fmtPct(metrics.ebitdaMargin) },
        { label: 'ROE', value: fmtPct(metrics.returnOnEquity) },
        { label: 'ROA', value: fmtPct(metrics.returnOnAssets) },
        { label: 'Debt/Equity', value: fmtNum(metrics.debtToEquity) },
        { label: 'Current Ratio', value: fmtNum(metrics.currentRatio) },
        { label: 'Dividend Yield', value: fmtPct(metrics.dividendYield) },
        { label: '52W High', value: metrics.fiftyTwoWeekHigh ? `$${fmtNum(metrics.fiftyTwoWeekHigh)}` : '—' },
        { label: '52W Low', value: metrics.fiftyTwoWeekLow ? `$${fmtNum(metrics.fiftyTwoWeekLow)}` : '—' },
        { label: 'Analysts', value: metrics.numberOfAnalysts || '—' },
        { label: 'Target Price', value: metrics.targetMeanPrice ? `$${fmtNum(metrics.targetMeanPrice)}` : '—' },
    ];

    grid.innerHTML = items.map(i =>
        `<div class="metric-item">
            <div class="metric-label">${i.label}</div>
            <div class="metric-value">${i.value}</div>
        </div>`
    ).join('');
}

// ── Piotroski ──
function renderPiotroski(fund) {
    const section = document.getElementById('piotroskiSection');
    if (!fund || fund.piotroski_score == null) {
        section.style.display = 'none';
        return;
    }
    section.style.display = 'block';
    const score = fund.piotroski_score;
    const valEl = document.getElementById('piotroskiValue');
    valEl.textContent = `${score}/9`;
    valEl.style.color = score >= 7 ? 'var(--accent-green)' : score >= 4 ? 'var(--accent-orange)' : 'var(--accent-red)';

    const details = fund.piotroski_details || [];
    const grid = document.getElementById('piotroskiDetails');
    grid.innerHTML = details.map(d => {
        let cls = 'partial';
        if (d.startsWith('✓')) cls = 'pass';
        else if (d.startsWith('✗')) cls = 'fail';
        return `<div class="piotroski-item ${cls}">${escapeHtml(d)}</div>`;
    }).join('');
}

// ── News ──
function renderNews(sentiment) {
    if (!sentiment) return;
    const summary = document.getElementById('newsSummary');
    summary.innerHTML = `
        <span class="news-stat positive">📈 ${sentiment.positive_count || 0} Positive</span>
        <span class="news-stat negative">📉 ${sentiment.negative_count || 0} Negative</span>
        <span class="news-stat neutral">➖ ${sentiment.neutral_count || 0} Neutral</span>
        <span class="news-stat" style="background:var(--accent-blue-dim);color:var(--accent-blue)">Overall: ${sentiment.overall_sentiment || 'N/A'}</span>`;

    const list = document.getElementById('newsList');
    const headlines = sentiment.headlines || [];
    if (!headlines.length) {
        list.innerHTML = '<p style="color:var(--text-muted);font-size:13px">No news headlines found.</p>';
        return;
    }
    list.innerHTML = headlines.slice(0, 10).map(h => {
        const label = h.sentiment_label || 'Neutral';
        const cls = label.includes('Positive') ? 'positive' : label.includes('Negative') ? 'negative' : 'neutral';
        const cat = h.category ? `<span style="font-size:10px;color:var(--text-muted);margin-left:6px">[${h.category}]</span>` : '';
        return `<div class="news-item">
            <span class="news-sentiment-dot ${cls}"></span>
            <span class="news-title">${escapeHtml(h.title)}${cat}</span>
            <span class="news-source">${escapeHtml(h.source || '')}</span>
            <span class="news-sentiment-label ${cls}">${label}</span>
        </div>`;
    }).join('');
}

// ── Reasoning ──
function renderReasoning(reasoning) {
    if (!reasoning) return;
    const el = document.getElementById('reasoningText');
    // Convert markdown-ish formatting
    let html = escapeHtml(reasoning)
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/^### (.*)/gm, '<h3>$1</h3>')
        .replace(/^- (.*)/gm, '<div style="padding-left:16px;margin:3px 0">• $1</div>')
        .replace(/\n{2,}/g, '<br><br>')
        .replace(/\n/g, '<br>');
    el.innerHTML = html;
}

// ── Utilities ──
function getScoreColor(score) {
    if (score >= 70) return '#00e676';
    if (score >= 55) return '#8bc34a';
    if (score >= 45) return '#ff9800';
    if (score >= 30) return '#ff5722';
    return '#f44336';
}

function animateNumber(el, target) {
    let current = 0;
    const step = Math.max(1, Math.floor(target / 30));
    const timer = setInterval(() => {
        current += step;
        if (current >= target) { current = target; clearInterval(timer); }
        el.textContent = Math.round(current);
    }, 25);
}

function fmtNum(val) {
    if (val == null || val === 'N/A') return '—';
    return typeof val === 'number' ? val.toFixed(2) : val;
}
function fmtPct(val) {
    if (val == null) return '—';
    return (val * 100).toFixed(2) + '%';
}
function hexToRgba(hex, alpha) {
    if (!hex || hex[0] !== '#') return `rgba(255,255,255,${alpha})`;
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
}
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
