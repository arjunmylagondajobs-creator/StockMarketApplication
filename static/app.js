/**
 * Stock Investment Analyzer — Frontend Application Logic
 * Handles API calls, chart rendering, score animation, and UI updates.
 */

// Chart instances (for cleanup on re-analyze)
let priceChart = null;
let rsiChart = null;
let macdChart = null;

// Search autocomplete
let searchTimeout = null;
let dropdownVisible = false;

// --- Core Functions ---

function quickAnalyze(ticker) {
    document.getElementById('tickerInput').value = ticker;
    hideDropdown();
    analyzeStock();
}

async function analyzeStock() {
    const input = document.getElementById('tickerInput');
    const ticker = input.value.trim();
    if (!ticker) {
        input.focus();
        return;
    }

    hideDropdown();
    showLoading(ticker);
    hideError();
    hideResults();

    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker: ticker })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Analysis failed');
        }

        renderResults(data);
    } catch (err) {
        showError(err.message);
    } finally {
        hideLoading();
    }
}

// --- Search Autocomplete ---

async function searchTickers(query) {
    if (!query || query.length < 2) {
        hideDropdown();
        return;
    }

    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const results = await response.json();

        if (results.length > 0) {
            showDropdown(results);
        } else {
            hideDropdown();
        }
    } catch (err) {
        hideDropdown();
    }
}

function showDropdown(results) {
    let dropdown = document.getElementById('searchDropdown');
    if (!dropdown) {
        dropdown = document.createElement('div');
        dropdown.id = 'searchDropdown';
        dropdown.className = 'search-dropdown';
        document.querySelector('.search-box').parentElement.appendChild(dropdown);
    }

    dropdown.innerHTML = results.map(r => `
        <div class="dropdown-item" onclick="selectTicker('${escapeHtml(r.symbol)}')">
            <span class="dropdown-symbol">${escapeHtml(r.symbol)}</span>
            <span class="dropdown-name">${escapeHtml(r.name)}</span>
            <span class="dropdown-exchange">${escapeHtml(r.exchange)}</span>
        </div>
    `).join('');

    dropdown.classList.remove('hidden');
    dropdownVisible = true;
}

function hideDropdown() {
    const dropdown = document.getElementById('searchDropdown');
    if (dropdown) {
        dropdown.classList.add('hidden');
    }
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
    if (e.key === 'Enter') {
        hideDropdown();
        analyzeStock();
    }
    if (e.key === 'Escape') {
        hideDropdown();
    }
});

tickerInput.addEventListener('input', (e) => {
    const query = e.target.value.trim();
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => searchTickers(query), 300);
});

// Close dropdown on outside click
document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-container')) {
        hideDropdown();
    }
});

// --- UI Helpers ---

function showLoading(ticker) {
    document.getElementById('loadingTicker').textContent = ticker.toUpperCase();
    document.getElementById('loadingOverlay').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
}

function showError(msg) {
    document.getElementById('errorMessage').textContent = msg;
    document.getElementById('errorContainer').classList.remove('hidden');
}

function hideError() {
    document.getElementById('errorContainer').classList.add('hidden');
}

function showResults() {
    document.getElementById('resultsSection').classList.remove('hidden');
}

function hideResults() {
    document.getElementById('resultsSection').classList.add('hidden');
}

// --- Main Render ---

function renderResults(data) {
    renderStockHeader(data);
    renderRecommendation(data.recommendation);
    renderScoreCards(data);
    renderCharts(data.technical.chart_data);
    renderMetrics(data.fundamental.metrics);
    renderNews(data.sentiment);
    renderReasoning(data.reasoning);
    showResults();
}

// --- Stock Header ---

function renderStockHeader(data) {
    document.getElementById('companyName').textContent = data.companyName;
    document.getElementById('tickerBadge').textContent = data.ticker;
    document.getElementById('exchangeBadge').textContent = data.exchange;

    const currency = data.currency === 'INR' ? '₹' : '$';
    document.getElementById('currentPrice').textContent = `${currency}${data.currentPrice}`;

    const changeEl = document.getElementById('dailyChange');
    if (data.dailyChange !== null) {
        const sign = data.dailyChange >= 0 ? '+' : '';
        changeEl.textContent = `${sign}${data.dailyChange} (${sign}${data.dailyChangePct}%)`;
        changeEl.className = 'daily-change ' + (data.dailyChange >= 0 ? 'positive' : 'negative');
    } else {
        changeEl.textContent = '';
    }
}

// --- Recommendation Banner ---

function renderRecommendation(rec) {
    const banner = document.getElementById('recommendationBanner');
    const color = rec.color;

    banner.style.background = `linear-gradient(135deg, ${hexToRgba(color, 0.08)}, ${hexToRgba(color, 0.03)})`;
    banner.style.borderColor = hexToRgba(color, 0.3);

    const verdictEl = document.getElementById('verdictText');
    verdictEl.textContent = rec.verdict;
    verdictEl.style.color = color;

    const scoreEl = document.getElementById('finalScore');
    scoreEl.textContent = rec.final_score;
    scoreEl.style.color = color;

    document.getElementById('confidenceText').textContent = rec.confidence;
}

// --- Score Cards with Animated Gauges ---

function renderScoreCards(data) {
    animateGauge('technicalGauge', 'technicalScore', data.technical.score);
    animateGauge('fundamentalGauge', 'fundamentalScore', data.fundamental.score);
    animateGauge('sentimentGauge', 'sentimentScore', data.sentiment.score);

    // Technical signals
    const techSignals = document.getElementById('technicalSignals');
    techSignals.innerHTML = '';
    const techItems = [
        data.technical.rsi.signal,
        data.technical.macd.trend,
        data.technical.bollinger_bands.signal,
        data.technical.volume.signal
    ].filter(s => s && s !== 'N/A');
    techItems.slice(0, 3).forEach(s => {
        techSignals.innerHTML += `<div class="signal">${s}</div>`;
    });

    // Fundamental signals
    const fundSignals = document.getElementById('fundamentalSignals');
    fundSignals.innerHTML = '';
    (data.fundamental.signals || []).slice(0, 3).forEach(s => {
        fundSignals.innerHTML += `<div class="signal">${s}</div>`;
    });

    // Sentiment signals
    const sentSignals = document.getElementById('sentimentSignals');
    sentSignals.innerHTML = '';
    sentSignals.innerHTML = `
        <div class="signal">Overall: ${data.sentiment.overall_sentiment}</div>
        <div class="signal">📗 ${data.sentiment.positive_count} positive · 📕 ${data.sentiment.negative_count} negative</div>
    `;
}

function animateGauge(gaugeId, valueId, score) {
    const gauge = document.getElementById(gaugeId);
    const valueEl = document.getElementById(valueId);

    // The arc length of the half-circle is ~157
    const maxDash = 157;
    const targetDash = (score / 100) * maxDash;

    // Color based on score
    let color;
    if (score >= 65) color = '#00e676';
    else if (score >= 45) color = '#ff9800';
    else color = '#f44336';

    gauge.style.stroke = color;
    valueEl.style.color = color;

    // Animate
    let current = 0;
    const step = score / 40; // 40 frames
    const animate = () => {
        current = Math.min(current + step, score);
        const dash = (current / 100) * maxDash;
        gauge.setAttribute('stroke-dasharray', `${dash} ${maxDash}`);
        valueEl.textContent = Math.round(current);
        if (current < score) requestAnimationFrame(animate);
    };
    requestAnimationFrame(animate);
}

// --- Charts ---

function renderCharts(chartData) {
    if (!chartData || !chartData.dates) return;

    // Destroy existing charts
    if (priceChart) priceChart.destroy();
    if (rsiChart) rsiChart.destroy();
    if (macdChart) macdChart.destroy();

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: {
                    color: '#8b949e',
                    font: { family: 'Inter', size: 11 },
                    usePointStyle: true,
                    pointStyle: 'line'
                }
            }
        },
        scales: {
            x: {
                ticks: { color: '#6e7681', font: { size: 10 }, maxTicksLimit: 10 },
                grid: { color: 'rgba(48,54,61,0.5)' }
            },
            y: {
                ticks: { color: '#6e7681', font: { size: 10 } },
                grid: { color: 'rgba(48,54,61,0.5)' }
            }
        },
        interaction: { intersect: false, mode: 'index' },
        elements: { point: { radius: 0 }, line: { tension: 0.1 } }
    };

    // Price Chart
    const priceCtx = document.getElementById('priceChart').getContext('2d');
    priceChart = new Chart(priceCtx, {
        type: 'line',
        data: {
            labels: chartData.dates,
            datasets: [
                {
                    label: 'Price',
                    data: chartData.close,
                    borderColor: '#58a6ff',
                    borderWidth: 2,
                    fill: { target: 'origin', above: 'rgba(88,166,255,0.05)' }
                },
                {
                    label: 'SMA 20',
                    data: chartData.sma_20,
                    borderColor: '#ff9800',
                    borderWidth: 1.5,
                    borderDash: [4, 2]
                },
                {
                    label: 'SMA 50',
                    data: chartData.sma_50,
                    borderColor: '#bb86fc',
                    borderWidth: 1.5,
                    borderDash: [4, 2]
                },
                {
                    label: 'BB Upper',
                    data: chartData.bb_upper,
                    borderColor: 'rgba(0,230,118,0.3)',
                    borderWidth: 1,
                    borderDash: [2, 2]
                },
                {
                    label: 'BB Lower',
                    data: chartData.bb_lower,
                    borderColor: 'rgba(244,67,54,0.3)',
                    borderWidth: 1,
                    borderDash: [2, 2],
                    fill: { target: '-1', above: 'rgba(139,148,158,0.03)' }
                }
            ]
        },
        options: { ...chartOptions }
    });

    // RSI Chart
    const rsiCtx = document.getElementById('rsiChart').getContext('2d');
    rsiChart = new Chart(rsiCtx, {
        type: 'line',
        data: {
            labels: chartData.dates,
            datasets: [
                {
                    label: 'RSI',
                    data: chartData.rsi,
                    borderColor: '#bb86fc',
                    borderWidth: 2,
                    fill: false
                }
            ]
        },
        options: {
            ...chartOptions,
            scales: {
                ...chartOptions.scales,
                y: {
                    ...chartOptions.scales.y,
                    min: 0,
                    max: 100
                }
            },
            plugins: {
                ...chartOptions.plugins,
                annotation: {
                    annotations: {
                        overbought: {
                            type: 'line',
                            yMin: 70, yMax: 70,
                            borderColor: 'rgba(244,67,54,0.5)',
                            borderWidth: 1,
                            borderDash: [5, 3]
                        },
                        oversold: {
                            type: 'line',
                            yMin: 30, yMax: 30,
                            borderColor: 'rgba(0,230,118,0.5)',
                            borderWidth: 1,
                            borderDash: [5, 3]
                        }
                    }
                }
            }
        }
    });

    // MACD Chart
    const macdCtx = document.getElementById('macdChart').getContext('2d');
    const histColors = chartData.macd_hist.map(v => v !== null && v >= 0 ? 'rgba(0,230,118,0.6)' : 'rgba(244,67,54,0.6)');
    macdChart = new Chart(macdCtx, {
        type: 'bar',
        data: {
            labels: chartData.dates,
            datasets: [
                {
                    label: 'Histogram',
                    data: chartData.macd_hist,
                    backgroundColor: histColors,
                    borderWidth: 0,
                    order: 2
                },
                {
                    type: 'line',
                    label: 'MACD',
                    data: chartData.macd,
                    borderColor: '#58a6ff',
                    borderWidth: 1.5,
                    fill: false,
                    order: 1
                },
                {
                    type: 'line',
                    label: 'Signal',
                    data: chartData.macd_signal,
                    borderColor: '#ff9800',
                    borderWidth: 1.5,
                    fill: false,
                    order: 1
                }
            ]
        },
        options: chartOptions
    });
}

// --- Metrics Table ---

function renderMetrics(metrics) {
    const grid = document.getElementById('metricsGrid');
    grid.innerHTML = '';

    const items = [
        { label: 'Market Cap', value: metrics.marketCapFormatted || 'N/A' },
        { label: 'P/E Ratio', value: fmtNum(metrics.peRatio) },
        { label: 'Forward P/E', value: fmtNum(metrics.forwardPE) },
        { label: 'PEG Ratio', value: fmtNum(metrics.pegRatio) },
        { label: 'Revenue Growth', value: fmtPct(metrics.revenueGrowth) },
        { label: 'Earnings Growth', value: fmtPct(metrics.earningsGrowth) },
        { label: 'Profit Margin', value: fmtPct(metrics.profitMargin) },
        { label: 'Return on Equity', value: fmtPct(metrics.returnOnEquity) },
        { label: 'Debt/Equity', value: metrics.debtToEquity ? `${metrics.debtToEquity.toFixed(1)}%` : 'N/A' },
        { label: 'Dividend Yield', value: fmtPct(metrics.dividendYield) },
        { label: '52W High', value: metrics.fiftyTwoWeekHigh ? `$${metrics.fiftyTwoWeekHigh}` : 'N/A' },
        { label: '52W Low', value: metrics.fiftyTwoWeekLow ? `$${metrics.fiftyTwoWeekLow}` : 'N/A' },
        { label: 'Analyst Target', value: metrics.targetMeanPrice ? `$${metrics.targetMeanPrice}` : 'N/A' },
        { label: 'Analyst Upside', value: metrics.analystUpside != null ? `${metrics.analystUpside}%` : 'N/A' },
        { label: 'Sector', value: metrics.sector || 'N/A' },
        { label: 'Industry', value: metrics.industry || 'N/A' }
    ];

    items.forEach(item => {
        const div = document.createElement('div');
        div.className = 'metric-item';
        div.innerHTML = `
            <div class="metric-label">${item.label}</div>
            <div class="metric-value">${item.value}</div>
        `;
        grid.appendChild(div);
    });
}

// --- News Feed ---

function renderNews(sentiment) {
    // Summary badges
    const summary = document.getElementById('newsSummary');
    summary.innerHTML = `
        <span class="news-stat positive">👍 ${sentiment.positive_count} Positive</span>
        <span class="news-stat negative">👎 ${sentiment.negative_count} Negative</span>
        <span class="news-stat neutral">➖ ${sentiment.neutral_count} Neutral</span>
    `;

    // Headlines
    const list = document.getElementById('newsList');
    list.innerHTML = '';

    if (sentiment.headlines && sentiment.headlines.length > 0) {
        sentiment.headlines.forEach(h => {
            const sentClass = h.sentiment_label.includes('Positive') ? 'positive' :
                h.sentiment_label.includes('Negative') ? 'negative' : 'neutral';
            const div = document.createElement('div');
            div.className = 'news-item';
            div.innerHTML = `
                <span class="news-sentiment-dot ${sentClass}"></span>
                <span class="news-title">${escapeHtml(h.title)}</span>
                <span class="news-source">${escapeHtml(h.source)}</span>
                <span class="news-sentiment-label ${sentClass}">${h.sentiment_label}</span>
            `;
            list.appendChild(div);
        });
    } else {
        list.innerHTML = '<div class="news-item"><span class="news-title" style="color: var(--text-muted);">No recent news found.</span></div>';
    }
}

// --- Reasoning ---

function renderReasoning(reasoning) {
    const el = document.getElementById('reasoningText');
    // Convert markdown-like bold to HTML
    let html = reasoning
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n\n/g, '<br><br>')
        .replace(/  •/g, '&nbsp;&nbsp;•');
    el.innerHTML = html;
}

// --- Utilities ---

function fmtNum(val) {
    if (val == null || val === undefined) return 'N/A';
    return val.toFixed(2);
}

function fmtPct(val) {
    if (val == null || val === undefined) return 'N/A';
    return (val * 100).toFixed(2) + '%';
}

function hexToRgba(hex, alpha) {
    // Handle named or hex colors
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 1;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = hex;
    ctx.fillRect(0, 0, 1, 1);
    const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
