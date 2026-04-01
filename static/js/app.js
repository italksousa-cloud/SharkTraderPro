// Shark Trader Pro Frontend UI Logic

const apiBase = 'http://127.0.0.1:5000/api';

// Elements
const dot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const btnToggle = document.getElementById('toggle-bot');
const maxSymbols = document.getElementById('max-symbols');

const elBalance = document.getElementById('current-balance');
const elPnlPct = document.getElementById('pnl-pct');
const elWinRate = document.getElementById('win-rate');
const elTotalTrades = document.getElementById('total-trades');
const elDrawdown = document.getElementById('max-drawdown');
const elBestTrade = document.getElementById('best-trade');
const elWorstTrade = document.getElementById('worst-trade');

const openTradesContainer = document.getElementById('open-trades-container');
const historyTbody = document.getElementById('history-tbody');

// Plotly layout template
const chartLayout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#94a3b8', family: 'Inter' },
    margin: { t: 10, r: 10, b: 40, l: 40 },
    xaxis: { showgrid: false, zeroline: false },
    yaxis: { gridcolor: 'rgba(255,255,255,0.05)', zerolinecolor: 'rgba(255,255,255,0.1)' }
};

let chartInitialized = false;

// Functions
async function fetchStatus() {
    try {
        const res = await fetch(`${apiBase}/status`);
        const data = await res.json();
        
        maxSymbols.innerText = data.max_symbols;
        
        if (data.running && !data.paused) {
            dot.className = 'dot';
            statusText.innerText = 'Ativo (Escaneando)';
            btnToggle.innerHTML = '<i class="fa-solid fa-pause"></i> Pausar Simulação';
            btnToggle.style.background = 'linear-gradient(135deg, #ef4444, #b91c1c)';
        } else if (data.running && data.paused) {
            dot.className = 'dot offline';
            dot.style.backgroundColor = '#f59e0b';
            dot.style.boxShadow = '0 0 10px #f59e0b';
            statusText.innerText = 'Pausado (Limite Risco)';
            btnToggle.innerHTML = '<i class="fa-solid fa-play"></i> Retomar';
            btnToggle.style.background = 'linear-gradient(135deg, #10b981, #059669)';
        } else {
            dot.className = 'dot offline';
            statusText.innerText = 'Desligado';
            btnToggle.innerHTML = '<i class="fa-solid fa-power-off"></i> Iniciar Servidor';
            btnToggle.style.background = 'linear-gradient(135deg, #3b82f6, #8b5cf6)';
        }
    } catch(e) {
        dot.className = 'dot offline';
        statusText.innerText = 'Desconectado da API';
    }
}

async function fetchWallet() {
    try {
        const res = await fetch(`${apiBase}/wallet`);
        const data = await res.json();
        
        elBalance.innerText = `$ ${data.current.toFixed(2)}`;
        elPnlPct.innerText = `${data.pnl_pct >= 0 ? '+' : ''}${data.pnl_pct.toFixed(2)}%`;
        elPnlPct.className = `metric-trend ${data.pnl_pct >= 0 ? 'success' : 'danger'}`;
        
        elWinRate.innerText = `${data.win_rate.toFixed(0)}%`;
        elTotalTrades.innerText = `${data.total_trades} trades`;
        elDrawdown.innerText = `${data.drawdown.toFixed(2)}%`;
        
        elBestTrade.innerText = `$ ${data.best_trade.toFixed(2)}`;
        elWorstTrade.innerText = `Pior: $ ${data.worst_trade.toFixed(2)}`;
        
    } catch(e) {}
}

async function fetchOpenTrades() {
    try {
        const res = await fetch(`${apiBase}/trades/open`);
        const data = await res.json();
        
        if (data.length === 0) {
            openTradesContainer.innerHTML = '<div class="empty-state">Nenhuma operação aberta no momento...</div>';
            return;
        }
        
        let html = '';
        data.forEach(t => {
            html += `
            <div class="trade-item ${t.side}">
                <div class="trade-header">
                    <span>${t.symbol}</span>
                    <span style="text-transform:uppercase">${t.side}</span>
                </div>
                <div class="trade-details">
                    <span>Entrada: $${t.entry_price.toFixed(4)}</span>
                    <span>Qtd: ${t.quantity.toFixed(4)}</span>
                </div>
            </div>`;
        });
        openTradesContainer.innerHTML = html;
        
    } catch(e) {}
}

async function fetchHistory() {
    try {
        const res = await fetch(`${apiBase}/trades/history`);
        const data = await res.json();
        
        let html = '';
        data.reverse().forEach(t => {
            const pnl = t.net_profit;
            html += `
            <tr>
                <td><strong>${t.symbol}</strong></td>
                <td><span class="badge ${t.side}">${t.side}</span></td>
                <td>$${t.entry_price.toFixed(4)}</td>
                <td>$${t.exit_price.toFixed(4)}</td>
                <td class="badge ${pnl >= 0 ? 'profit' : 'loss'}">${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}</td>
                <td style="color:var(--text-secondary);font-size:12px">${t.exit_time.replace('T', ' ').substring(0, 16)}</td>
            </tr>`;
        });
        historyTbody.innerHTML = html;
        
    } catch(e) {}
}

async function updateChart() {
    try {
        const res = await fetch(`${apiBase}/chart`);
        const data = await res.json();
        
        const x = data.map(d => d.time);
        const y = data.map(d => d.balance);
        
        const trace = {
            x: x,
            y: y,
            type: 'scatter',
            mode: 'lines',
            line: {
                color: '#8b5cf6',
                width: 3,
                shape: 'spline'
            },
            fill: 'tozeroy',
            fillcolor: 'rgba(139,92,246,0.1)'
        };

        if(!chartInitialized) {
            Plotly.newPlot('plotly-chart', [trace], chartLayout, {responsive: true, displayModeBar: false});
            chartInitialized = true;
        } else {
            // Update existing
            Plotly.react('plotly-chart', [trace], chartLayout);
        }
    } catch(e) {}
}

// Polling interval
function refreshAll() {
    fetchStatus();
    fetchWallet();
    fetchOpenTrades();
    fetchHistory();
    updateChart();
}

// Events
btnToggle.addEventListener('click', async () => {
    try {
        await fetch(`${apiBase}/toggle`);
        refreshAll();
    } catch(e) {}
});

// Initialization
refreshAll();
setInterval(refreshAll, 3000); // 3-second real-time polling
