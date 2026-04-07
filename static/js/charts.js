/* ── charts.js — Statistics view with Chart.js ── */

'use strict';

let _charts = {};

function destroyCharts() {
  Object.values(_charts).forEach(c => { try { c.destroy(); } catch {} });
  _charts = {};
}

function _num(value) {
  return Number(value) || 0;
}

function _fmtPct(value, digits = 1) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  return `${(Number(value) * 100).toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}%`;
}

function _fmtRatio(value) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  return `${Number(value).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}x`;
}

function _fmtMonths(value) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  return `${Number(value).toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}m`;
}

function _compactMoney(value) {
  const amount = _num(value);
  const abs = Math.abs(amount);
  if (abs >= 1000000) return `$ ${(amount / 1000000).toFixed(1)}M`;
  if (abs >= 1000) return `$ ${(amount / 1000).toFixed(0)}k`;
  return `$ ${amount.toLocaleString('en-US')}`;
}

function _rollingAverage(values, windowSize = 3) {
  return values.map((_, idx) => {
    const slice = values.slice(Math.max(0, idx - windowSize + 1), idx + 1);
    return slice.length ? slice.reduce((sum, value) => sum + _num(value), 0) / slice.length : 0;
  });
}

function _topBreakdown(items, labelKey, valueKey, limit = 6) {
  if (!Array.isArray(items) || items.length <= limit) return items || [];

  const head = items.slice(0, limit);
  const otherTotal = items.slice(limit).reduce((sum, item) => sum + _num(item[valueKey]), 0);
  if (otherTotal > 0) {
    head.push({ [labelKey]: t('stats.other'), [valueKey]: otherTotal });
  }
  return head;
}

const KpiInfo = {
  _registry: {},

  set(key, data) {
    this._registry[key] = data;
  },

  show(key) {
    const info = this._registry[key];
    if (!info) return;

    const formulaHtml = info.formula ? `
      <div class="mt-3 rounded-lg bg-dark-700/60 border border-dark-600 px-3 py-2">
        <div class="text-[10px] uppercase tracking-wide text-dark-500 mb-1">${t('kpi.info.formula')}</div>
        <div class="font-mono text-xs text-blue-300">${escapeHtml(info.formula)}</div>
      </div>` : '';

    const varsHtml = info.vars && info.vars.length ? `
      <div class="mt-3">
        <div class="text-[10px] uppercase tracking-wide text-dark-500 mb-2">${t('kpi.info.variables')}</div>
        <div class="space-y-1.5">
          ${info.vars.map(v => `
            <div class="flex justify-between items-baseline gap-4 text-sm">
              <span class="text-dark-400">${escapeHtml(v.label)}</span>
              <span class="font-mono text-dark-200 shrink-0">${escapeHtml(String(v.value))}</span>
            </div>`).join('')}
        </div>
      </div>` : '';

    const body = `
      <div class="p-5 space-y-1">
        <p class="text-sm text-dark-300 leading-relaxed">${escapeHtml(info.def)}</p>
        ${formulaHtml}
        ${varsHtml}
        <div class="flex justify-end pt-4 border-t border-dark-600 !mt-5">
          <button type="button" data-modal-close class="tbtn px-4 py-2 text-sm">${t('btn.close')}</button>
        </div>
      </div>`;

    Modal.open(body, { title: escapeHtml(info.name) });
  },
};

function _kpiCard({ label, value, note = '', valueClass = 'text-dark-100', infoKey = null }) {
  const infoBtn = infoKey
    ? `<button class="kpi-info-btn" onclick="KpiInfo.show('${infoKey}')"
               title="${escapeHtml(t('kpi.info.btn'))}" aria-label="${escapeHtml(t('kpi.info.btn'))}">ⓘ</button>`
    : '';
  return `
    <div class="bg-dark-800 border border-dark-600 rounded-xl p-4">
      <div class="flex items-start justify-between gap-1 mb-2">
        <div class="text-[11px] text-dark-400 uppercase tracking-wide">${escapeHtml(label)}</div>
        ${infoBtn}
      </div>
      <div class="text-2xl font-semibold ${valueClass}">${escapeHtml(value)}</div>
      <div class="text-xs text-dark-400 mt-2 min-h-[18px]">${escapeHtml(note)}</div>
    </div>`;
}

function _replaceWithEmpty(canvasId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  canvas.outerHTML = `<div class="empty h-full flex items-center justify-center">${escapeHtml(t('report.no_data'))}</div>`;
}

function _buildHorizontalBar(canvasId, items, labelKey, valueKey, color, tooltipLabel) {
  const total = items.reduce((sum, item) => sum + _num(item[valueKey]), 0);
  _charts[canvasId] = new Chart(document.getElementById(canvasId), {
    type: 'bar',
    data: {
      labels: items.map(item => item[labelKey]),
      datasets: [{
        data: items.map(item => item[valueKey]),
        backgroundColor: color + 'bb',
        borderColor: color,
        borderWidth: 1,
        borderRadius: 8,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#21262d',
          borderColor: '#30363d',
          borderWidth: 1,
          titleColor: '#e6edf3',
          bodyColor: '#c9d1d9',
          callbacks: {
            label: ctx => ` ${tooltipLabel(ctx)} • ${_fmtPct(total ? ctx.raw / total : null)}`,
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: '#8b949e',
            font: { size: 10 },
            callback: value => _compactMoney(value),
          },
          grid: { color: '#30363d33' },
        },
        y: {
          ticks: { color: '#8b949e', font: { size: 10 } },
          grid: { display: false },
        },
      },
    },
  });
}

const Charts = {

  async stats() {
    const q = State.buildReportQuery();
    const data = await API.get('/reports/stats' + q);
    const main = document.getElementById('main');
    const summary = data.summary || {};
    const monthlyCashflow = data.monthly_cashflow || [];
    const expenseBreakdown = _topBreakdown(data.expenses_by_subtype || [], 'subtype', 'amount');
    const incomeBreakdown = _topBreakdown(data.income_by_subtype || [], 'subtype', 'amount');
    const assetComposition = data.asset_composition || [];
    const topAccounts = data.top_accounts || [];
    const netWorthEvolution = data.net_worth_evolution || [];
    const netResultClass = _num(summary.net_result) >= 0 ? 'text-ingreso' : 'text-pasivo';
    const savingsRateClass = _num(summary.savings_rate) >= 0 ? 'text-ingreso' : 'text-pasivo';

    destroyCharts();

    KpiInfo.set('savings_rate', {
      name: t('kpi.info.savings_rate.name'),
      def: t('kpi.info.savings_rate.def'),
      formula: t('kpi.info.savings_rate.formula'),
      vars: [
        { label: t('report.total_income'),  value: fmt(summary.total_income) },
        { label: t('report.total_expense'), value: fmt(summary.total_expense) },
      ],
    });
    KpiInfo.set('net_worth', {
      name: t('kpi.info.net_worth.name'),
      def: t('kpi.info.net_worth.def'),
      formula: t('kpi.info.net_worth.formula'),
      vars: [
        { label: t('report.total_assets'), value: fmt(summary.total_assets) },
        { label: t('report.total_liab'),   value: fmt(summary.total_liabilities) },
      ],
    });
    KpiInfo.set('debt_ratio', {
      name: t('kpi.info.debt_ratio.name'),
      def: t('kpi.info.debt_ratio.def'),
      formula: t('kpi.info.debt_ratio.formula'),
      vars: [
        { label: t('report.total_liab'),   value: fmt(summary.total_liabilities) },
        { label: t('report.total_assets'), value: fmt(summary.total_assets) },
      ],
    });
    KpiInfo.set('current_ratio', {
      name: t('kpi.info.current_ratio.name'),
      def: t('kpi.info.current_ratio.def'),
      formula: t('kpi.info.current_ratio.formula'),
      vars: [
        { label: t('stats.kpi.current_assets'),      value: fmt(summary.current_assets) },
        { label: t('stats.kpi.current_liabilities'), value: fmt(summary.current_liabilities) },
      ],
    });
    KpiInfo.set('quick_ratio', {
      name: t('kpi.info.quick_ratio.name'),
      def: t('kpi.info.quick_ratio.def'),
      formula: t('kpi.info.quick_ratio.formula'),
      vars: [
        { label: t('stats.kpi.quick_assets'),        value: fmt(summary.quick_assets) },
        { label: t('stats.kpi.current_liabilities'), value: fmt(summary.current_liabilities) },
      ],
    });
    KpiInfo.set('runway_months', {
      name: t('kpi.info.runway_months.name'),
      def: t('kpi.info.runway_months.def'),
      formula: t('kpi.info.runway_months.formula'),
      vars: [
        { label: t('stats.kpi.quick_assets'),      value: fmt(summary.quick_assets) },
        { label: t('stats.kpi.essential_expense'), value: fmt(summary.monthly_essential_expense) },
      ],
    });
    KpiInfo.set('top_asset', {
      name: t('kpi.info.top_asset.name'),
      def: t('kpi.info.top_asset.def'),
      formula: t('kpi.info.top_asset.formula'),
      vars: [
        { label: t('report.total_assets'), value: fmt(summary.total_assets) },
        { label: summary.top_asset_name || '—', value: _fmtPct(summary.top_asset_share) },
      ],
    });
    KpiInfo.set('top_expense', {
      name: t('kpi.info.top_expense.name'),
      def: t('kpi.info.top_expense.def'),
      formula: t('kpi.info.top_expense.formula'),
      vars: [
        { label: t('report.total_expense'), value: fmt(summary.total_expense) },
        { label: summary.top_expense_name || '—', value: _fmtPct(summary.top_expense_share) },
      ],
    });

    main.innerHTML = `
      <div class="overflow-y-auto flex-1">
      <div class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-5 xl:px-4 py-6">
      ${typeof Reports !== 'undefined' ? Reports._tagFilterBar() : ''}
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-5">
        ${_kpiCard({
          label: t('report.total_income'),
          value: fmt(summary.total_income),
          valueClass: 'text-ingreso',
        })}
        ${_kpiCard({
          label: t('report.total_expense'),
          value: fmt(summary.total_expense),
          valueClass: 'text-pasivo',
          note: `${t('stats.kpi.negative_months')}: ${summary.negative_months ?? 0}`,
        })}
        ${_kpiCard({
          label: t('report.result'),
          value: fmt(summary.net_result),
          valueClass: netResultClass,
          note: `${t('stats.kpi.avg_monthly_net')}: ${fmt(summary.avg_monthly_net)}`,
        })}
        ${_kpiCard({
          label: t('stats.kpi.savings_rate'),
          value: _fmtPct(summary.savings_rate),
          valueClass: savingsRateClass,
          note: `${t('stats.kpi.monthly_volatility')}: ${fmt(summary.monthly_volatility)}`,
          infoKey: 'savings_rate',
        })}
        ${_kpiCard({
          label: t('stats.kpi.net_worth'),
          value: fmt(summary.net_worth),
          valueClass: 'text-activo',
          note: `${t('report.total_assets')}: ${fmt(summary.total_assets)} · ${t('report.total_liab')}: ${fmt(summary.total_liabilities)}`,
          infoKey: 'net_worth',
        })}
        ${_kpiCard({
          label: t('stats.kpi.debt_ratio'),
          value: _fmtPct(summary.debt_ratio),
          valueClass: _num(summary.debt_ratio) > 0.5 ? 'text-pasivo' : 'text-dark-100',
          infoKey: 'debt_ratio',
        })}
        ${_kpiCard({
          label: t('stats.kpi.current_ratio'),
          value: _fmtRatio(summary.current_ratio),
          valueClass: _num(summary.current_ratio) < 1 ? 'text-pasivo' : 'text-dark-100',
          note: `${t('stats.kpi.current_assets')}: ${fmt(summary.current_assets)} · ${t('stats.kpi.current_liabilities')}: ${fmt(summary.current_liabilities)}`,
          infoKey: 'current_ratio',
        })}
        ${_kpiCard({
          label: t('stats.kpi.quick_ratio'),
          value: _fmtRatio(summary.quick_ratio),
          valueClass: _num(summary.quick_ratio) < 1 ? 'text-pasivo' : 'text-dark-100',
          note: `${t('stats.kpi.quick_assets')}: ${fmt(summary.quick_assets)}`,
          infoKey: 'quick_ratio',
        })}
        ${_kpiCard({
          label: t('stats.kpi.runway_months'),
          value: _fmtMonths(summary.runway_months),
          valueClass: _num(summary.runway_months) < 3 ? 'text-pasivo' : 'text-dark-100',
          note: `${t('stats.kpi.essential_expense')}: ${fmt(summary.monthly_essential_expense)} · ${t(`stats.runway_basis.${summary.runway_basis || 'essential'}`)}`,
          infoKey: 'runway_months',
        })}
        ${_kpiCard({
          label: t('stats.kpi.top_asset_concentration'),
          value: _fmtPct(summary.top_asset_share),
          valueClass: 'text-activo',
          note: summary.top_asset_name || t('report.no_data'),
          infoKey: 'top_asset',
        })}
        ${_kpiCard({
          label: t('stats.kpi.top_expense_concentration'),
          value: _fmtPct(summary.top_expense_share),
          valueClass: 'text-pasivo',
          note: summary.top_expense_name || t('report.no_data'),
          infoKey: 'top_expense',
        })}
      </div>
      <div class="grid grid-cols-1 xl:grid-cols-2 gap-5" id="stats-grid">
        <div class="xl:col-span-2 bg-dark-800 border border-dark-600 rounded-xl p-4">
          <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.monthly_cashflow')}</h3>
          <canvas id="ch-cashflow" height="200"></canvas>
        </div>
        <div class="bg-dark-800 border border-dark-600 rounded-xl p-4">
          <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.expense_by_type')}</h3>
          <div class="h-[320px]"><canvas id="ch-expense-breakdown"></canvas></div>
        </div>
        <div class="bg-dark-800 border border-dark-600 rounded-xl p-4">
          <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.income_by_type')}</h3>
          <div class="h-[320px]"><canvas id="ch-income-breakdown"></canvas></div>
        </div>
        <div class="bg-dark-800 border border-dark-600 rounded-xl p-4">
          <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.asset_composition')}</h3>
          <canvas id="ch-asset-pie" height="200"></canvas>
        </div>
        <div class="bg-dark-800 border border-dark-600 rounded-xl p-4">
          <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.top_accounts')}</h3>
          <div class="h-[320px]"><canvas id="ch-top-accounts"></canvas></div>
        </div>
        <div class="xl:col-span-2 bg-dark-800 border border-dark-600 rounded-xl p-4">
          <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.net_worth_evolution')}</h3>
          <canvas id="ch-net-worth" height="200"></canvas>
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
    if (monthlyCashflow.length > 0) {
      const labels = monthlyCashflow.map(r => r.month);
      const netValues = monthlyCashflow.map(r => _num(r.neto));
      const movingAverage = _rollingAverage(netValues, 3);
      _charts.cashflow = new Chart(document.getElementById('ch-cashflow'), {
        type: 'bar',
        data: {
          labels,
          datasets: [
            {
              label: t('chart.income'),
              data: monthlyCashflow.map(r => r.ingresos),
              backgroundColor: '#66bb6a88',
              borderColor: '#66bb6a',
              borderWidth: 1,
              borderRadius: 8,
            },
            {
              label: t('chart.expense'),
              data: monthlyCashflow.map(r => r.gastos),
              backgroundColor: '#ef535088',
              borderColor: '#ef5350',
              borderWidth: 1,
              borderRadius: 8,
            },
            {
              label: t('chart.net'),
              data: netValues,
              type: 'line',
              borderColor: '#ffd54f',
              backgroundColor: 'transparent',
              borderWidth: 2,
              tension: 0.4,
              pointRadius: 4,
              pointBackgroundColor: netValues.map(value => value < 0 ? '#ef5350' : '#ffd54f'),
              pointBorderColor: netValues.map(value => value < 0 ? '#ef5350' : '#ffd54f'),
              fill: false,
              yAxisID: 'y',
            },
            {
              label: t('stats.moving_average'),
              data: movingAverage,
              type: 'line',
              borderColor: '#4fc3f7',
              backgroundColor: 'transparent',
              borderWidth: 2,
              borderDash: [6, 4],
              tension: 0.25,
              pointRadius: 0,
              fill: false,
              yAxisID: 'y',
            },
          ],
        },
        options: { ...defaults, responsive: true },
      });
    } else {
      _replaceWithEmpty('ch-cashflow');
    }

    /* ── 2. Expenses by Subtype ── */
    if (expenseBreakdown.length > 0) {
      _buildHorizontalBar(
        'ch-expense-breakdown',
        expenseBreakdown,
        'subtype',
        'amount',
        '#ef5350',
        ctx => `${ctx.label}: ${fmt(ctx.raw)}`
      );
    } else {
      _replaceWithEmpty('ch-expense-breakdown');
    }

    /* ── 3. Income by Subtype ── */
    if (incomeBreakdown.length > 0) {
      _buildHorizontalBar(
        'ch-income-breakdown',
        incomeBreakdown,
        'subtype',
        'amount',
        '#66bb6a',
        ctx => `${ctx.label}: ${fmt(ctx.raw)}`
      );
    } else {
      _replaceWithEmpty('ch-income-breakdown');
    }

    /* ── 4. Asset composition (donut) ── */
    if (assetComposition.length > 0) {
      const assetColors = ['#4fc3f7','#80deea','#66bb6a','#ffd54f','#ff8a65',
                           '#ce93d8','#9575cd','#7986cb','#4db6ac','#90caf9'];
      _charts.assetPie = new Chart(document.getElementById('ch-asset-pie'), {
        type: 'doughnut',
        data: {
          labels: assetComposition.map(r => r.account),
          datasets: [{
            data: assetComposition.map(r => r.balance),
            backgroundColor: assetColors,
            borderColor: '#161b22',
            borderWidth: 2,
          }],
        },
        options: {
          responsive: true,
          cutout: '58%',
          plugins: {
            legend: { position: 'bottom', labels: { color: '#8b949e', font: { size: 10 }, boxWidth: 12 } },
            tooltip: {
              callbacks: {
                label: ctx => ` ${ctx.label}: ${fmt(ctx.raw)} • ${_fmtPct(summary.total_assets ? ctx.raw / summary.total_assets : null)}`,
              }
            }
          },
        },
      });
    } else {
      _replaceWithEmpty('ch-asset-pie');
    }

    /* ── 5. Top Accounts ── */
    if (topAccounts.length > 0) {
      _charts.topAccounts = new Chart(document.getElementById('ch-top-accounts'), {
        type: 'bar',
        data: {
          labels: topAccounts.map(item => item.account),
          datasets: [{
            label: t('chart.volume'),
            data: topAccounts.map(item => item.volume),
            backgroundColor: '#4fc3f7bb',
            borderColor: '#4fc3f7',
            borderWidth: 1,
            borderRadius: 8,
          }],
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: '#21262d',
              borderColor: '#30363d',
              borderWidth: 1,
              titleColor: '#e6edf3',
              bodyColor: '#c9d1d9',
              callbacks: {
                label: ctx => {
                  const account = topAccounts[ctx.dataIndex];
                  return ` ${account.account}: ${fmt(ctx.raw)} • ${account.tx_count} ${t('stats.tx_count')}`;
                },
              },
            },
          },
          scales: {
            x: {
              ticks: {
                color: '#8b949e',
                font: { size: 10 },
                callback: value => _compactMoney(value),
              },
              grid: { color: '#30363d33' },
            },
            y: {
              ticks: { color: '#8b949e', font: { size: 10 } },
              grid: { display: false },
            },
          },
        },
      });
    } else {
      _replaceWithEmpty('ch-top-accounts');
    }

    /* ── 6. Net Worth Evolution ── */
    if (netWorthEvolution.length > 0) {
      _charts.netWorth = new Chart(document.getElementById('ch-net-worth'), {
        type: 'line',
        data: {
          labels: netWorthEvolution.map(row => row.month),
          datasets: [
            {
              label: t('report.total_assets'),
              data: netWorthEvolution.map(row => row.assets),
              borderColor: '#4fc3f7',
              backgroundColor: '#4fc3f722',
              borderWidth: 2,
              tension: 0.35,
              fill: false,
              pointRadius: 2,
            },
            {
              label: t('report.total_liab'),
              data: netWorthEvolution.map(row => row.liabilities),
              borderColor: '#ef5350',
              backgroundColor: '#ef535022',
              borderWidth: 2,
              tension: 0.35,
              fill: false,
              pointRadius: 2,
            },
            {
              label: t('stats.kpi.net_worth'),
              data: netWorthEvolution.map(row => row.net_worth),
              borderColor: '#ffd54f',
              backgroundColor: '#ffd54f22',
              borderWidth: 2,
              tension: 0.35,
              fill: false,
              pointRadius: 3,
            },
          ],
        },
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
    } else {
      _replaceWithEmpty('ch-net-worth');
    }
  },
};
