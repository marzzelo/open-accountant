/* ── charts.js — Statistics view with Chart.js ── */

'use strict';

let _charts = {};

function destroyCharts() {
  Object.values(_charts).forEach(c => { try { c.destroy(); } catch {} });
  _charts = {};
}

const Charts = {

  async stats() {
    const q    = State.apiDateParams;
    const data = await API.get('/reports/stats' + q);
    const main = document.getElementById('main');

    destroyCharts();

    main.innerHTML = `
      <div class="overflow-y-auto flex-1">
      <div class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-5 xl:px-4 py-6">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-5" id="stats-grid">
        <div class="lg:col-span-2 bg-dark-800 border border-dark-600 rounded-xl p-4">
          <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.monthly_cashflow')}</h3>
          <canvas id="ch-cashflow" height="80"></canvas>
        </div>
        <div class="bg-dark-800 border border-dark-600 rounded-xl p-4">
          <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.expense_by_type')}</h3>
          <canvas id="ch-exp-pie" height="200"></canvas>
        </div>
        <div class="bg-dark-800 border border-dark-600 rounded-xl p-4">
          <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.asset_composition')}</h3>
          <canvas id="ch-asset-pie" height="200"></canvas>
        </div>
        <div class="lg:col-span-2 bg-dark-800 border border-dark-600 rounded-xl p-4">
          <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.asset_evolution')}</h3>
          <canvas id="ch-evolution" height="200"></canvas>
        </div>
      </div></div></div>`;

    const defaults = {
      color: '#c9d1d9',
      borderColor: '#30363d',
      plugins: {
        legend: { labels: { color: '#8b949e', font: { size: 11 } } },
        tooltip: {
          backgroundColor: '#21262d',
          borderColor: '#30363d',
          borderWidth: 1,
          titleColor: '#e6edf3',
          bodyColor: '#c9d1d9',
          callbacks: {
            label: (ctx) => ` ${fmt(ctx.parsed.y ?? ctx.parsed)}`
          }
        }
      },
      scales: {
        x: { ticks: { color: '#8b949e', font: { size: 10 } }, grid: { color: '#30363d33' } },
        y: { ticks: { color: '#8b949e', font: { size: 10 },
                       callback: v => '$ ' + v.toLocaleString('en-US') },
             grid: { color: '#30363d66' } },
      },
    };

    /* ── 1. Monthly Cashflow ── */
    if (data.monthly_cashflow.length > 0) {
      const labels = data.monthly_cashflow.map(r => r.month);
      _charts.cashflow = new Chart(document.getElementById('ch-cashflow'), {
        type: 'bar',
        data: {
          labels,
          datasets: [
            {
              label: t('chart.income'),
              data: data.monthly_cashflow.map(r => r.ingresos),
              backgroundColor: '#66bb6a88',
              borderColor: '#66bb6a',
              borderWidth: 1,
            },
            {
              label: t('chart.expense'),
              data: data.monthly_cashflow.map(r => r.gastos),
              backgroundColor: '#ef535088',
              borderColor: '#ef5350',
              borderWidth: 1,
            },
            {
              label: t('chart.net'),
              data: data.monthly_cashflow.map(r => r.neto),
              type: 'line',
              borderColor: '#ffd54f',
              backgroundColor: '#ffd54f22',
              borderWidth: 2,
              tension: 0.4,
              pointRadius: 3,
              fill: true,
              yAxisID: 'y',
            },
          ],
        },
        options: { ...defaults, responsive: true },
      });
    } else {
      document.getElementById('ch-cashflow').parentElement.innerHTML +=
        `<div class="empty">${t('report.no_data')}</div>`;
    }

    /* ── 2. Expenses by Subtype (donut) ── */
    if (data.expenses_by_subtype.length > 0) {
      const pieColors = ['#ffd54f','#ffb74d','#ff8a65','#ef5350','#e040fb',
                         '#7c4dff','#448aff','#40c4ff','#64ffda','#69f0ae'];
      _charts.expPie = new Chart(document.getElementById('ch-exp-pie'), {
        type: 'doughnut',
        data: {
          labels: data.expenses_by_subtype.map(r => r.subtype),
          datasets: [{
            data: data.expenses_by_subtype.map(r => r.amount),
            backgroundColor: pieColors,
            borderColor: '#161b22',
            borderWidth: 2,
          }],
        },
        options: {
          responsive: true,
          plugins: {
            legend: { position: 'right', labels: { color: '#8b949e', font: { size: 10 }, boxWidth: 12 } },
            tooltip: {
              callbacks: { label: ctx => ` ${ctx.label}: ${fmt(ctx.raw)}` }
            }
          },
        },
      });
    } else {
      document.getElementById('ch-exp-pie').parentElement.innerHTML +=
        `<div class="empty">${t('report.no_data')}</div>`;
    }

    /* ── 3. Asset composition (donut) ── */
    if (data.asset_composition.length > 0) {
      const assetColors = ['#4fc3f7','#80deea','#66bb6a','#ffd54f','#ff8a65',
                           '#ce93d8','#9575cd','#7986cb','#4db6ac','#90caf9'];
      _charts.assetPie = new Chart(document.getElementById('ch-asset-pie'), {
        type: 'doughnut',
        data: {
          labels: data.asset_composition.map(r => r.account),
          datasets: [{
            data: data.asset_composition.map(r => r.balance),
            backgroundColor: assetColors,
            borderColor: '#161b22',
            borderWidth: 2,
          }],
        },
        options: {
          responsive: true,
          plugins: {
            legend: { position: 'right', labels: { color: '#8b949e', font: { size: 10 }, boxWidth: 12 } },
            tooltip: {
              callbacks: { label: ctx => ` ${ctx.label}: ${fmt(ctx.raw)}` }
            }
          },
        },
      });
    } else {
      document.getElementById('ch-asset-pie').parentElement.innerHTML +=
        `<div class="empty">${t('report.no_data')}</div>`;
    }

    /* ── 4. Balance evolution (line) ── */
    if (data.balance_evolution.length > 0) {
      // Group by account
      const byAccount = {};
      data.balance_evolution.forEach(r => {
        if (!byAccount[r.account_name]) byAccount[r.account_name] = {};
        byAccount[r.account_name][r.month] = r.balance;
      });

      const months = [...new Set(data.balance_evolution.map(r => r.month))].sort();
      const evColors = ['#4fc3f7','#66bb6a','#ce93d8','#ffd54f','#ef5350'];
      const datasets = Object.entries(byAccount).map(([name, mdata], i) => ({
        label: name,
        data: months.map(m => mdata[m] ?? null),
        borderColor: evColors[i % evColors.length],
        backgroundColor: evColors[i % evColors.length] + '22',
        borderWidth: 2,
        tension: 0.4,
        fill: false,
        spanGaps: true,
        pointRadius: 3,
      }));

      _charts.evolution = new Chart(document.getElementById('ch-evolution'), {
        type: 'line',
        data: { labels: months, datasets },
        options: {
          responsive: true,
          plugins: {
            legend: { labels: { color: '#8b949e', font: { size: 10 }, boxWidth: 12 } },
            tooltip: { callbacks: { label: ctx => ` ${ctx.dataset.label}: ${fmt(ctx.raw)}` } }
          },
          scales: {
            x: { ticks: { color: '#8b949e', font: { size: 9 } }, grid: { color: '#30363d33' } },
            y: { ticks: { color: '#8b949e', font: { size: 9 },
                           callback: v => '$ ' + (v/1000).toFixed(0) + 'k' },
                 grid: { color: '#30363d44' } },
          },
        },
      });
    }
  },
};
