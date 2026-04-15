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

function _fmtSignedMonths(value) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  const amount = Number(value);
  return `${amount >= 0 ? '+' : '-'}${Math.abs(amount).toLocaleString('en-US', {
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

        function _buildProjectionQueryFromPrefs(prefs = {}) {
          const horizon = typeof prefs.proj_horizon === 'number' ? prefs.proj_horizon : 12;
          const historyMonths = typeof prefs.proj_history_months === 'number' ? prefs.proj_history_months : 12;
          const income = prefs.proj_trend_income && typeof prefs.proj_trend_income === 'object'
            ? prefs.proj_trend_income
            : {};
          const investments = prefs.proj_trend_investments && typeof prefs.proj_trend_investments === 'object'
            ? prefs.proj_trend_investments
            : {};
          let projUrl = `/reports/projections?horizon=${horizon}&history_months=${historyMonths}`;
          projUrl += `&income_trend_mode=${encodeURIComponent(income.mode || 'linear')}`;

          const incomeMin = income.minVal !== '' && Number.isFinite(Number(income.minVal))
            ? Number(income.minVal)
            : null;
          const incomeMax = income.maxVal !== '' && Number.isFinite(Number(income.maxVal))
            ? Number(income.maxVal)
            : null;
          const incomeInflationBase = income.inflationBase !== '' && Number.isFinite(Number(income.inflationBase))
            ? Number(income.inflationBase)
            : null;
          const incomeInflationRate = income.inflationRate !== '' && Number.isFinite(Number(income.inflationRate))
            ? Number(income.inflationRate)
            : null;

          if (incomeMin != null) projUrl += `&income_trend_min=${encodeURIComponent(incomeMin)}`;
          if (incomeMax != null) projUrl += `&income_trend_max=${encodeURIComponent(incomeMax)}`;
          if (incomeInflationBase != null) projUrl += `&income_inflation_base=${encodeURIComponent(incomeInflationBase)}`;
          if (incomeInflationRate != null) projUrl += `&income_inflation_rate=${encodeURIComponent(incomeInflationRate)}`;

          if (typeof investments.lookbackMonths === 'number') {
            projUrl += `&investment_lookback_months=${investments.lookbackMonths}`;
          }
          projUrl += `&investment_include_current_month=${investments.includeCurrentMonth === true}`;
          projUrl += `&investment_exclude_outliers=${investments.excludeOutliers !== false}`;
          projUrl += `&investment_outlier_k=${Number(investments.outlierK) || 1.5}`;

          return projUrl;
        }

        function _registerSharedKpiInfo(summary, health = {}) {
          const current = health.current || {};
          const baseline = health.baseline_end || {};
          const scenario = health.scenario_end || {};

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
              { label: t('report.total_assets'), value: fmt(summary.total_assets ?? current.assets ?? 0) },
              { label: t('report.total_liab'),   value: fmt(summary.total_liabilities ?? current.liabilities ?? 0) },
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
              { label: t('stats.kpi.current_assets'),      value: fmt(summary.current_assets ?? current.current_assets ?? 0) },
              { label: t('stats.kpi.current_liabilities'), value: fmt(summary.current_liabilities ?? current.current_liabilities ?? 0) },
            ],
          });
          KpiInfo.set('quick_ratio', {
            name: t('kpi.info.quick_ratio.name'),
            def: t('kpi.info.quick_ratio.def'),
            formula: t('kpi.info.quick_ratio.formula'),
            vars: [
              { label: t('stats.kpi.quick_assets'),        value: fmt(summary.quick_assets ?? current.quick_assets ?? 0) },
              { label: t('stats.kpi.current_liabilities'), value: fmt(summary.current_liabilities ?? current.current_liabilities ?? 0) },
            ],
          });
          KpiInfo.set('runway_months', {
            name: t('kpi.info.runway_months.name'),
            def: t('kpi.info.runway_months.def'),
            formula: t('kpi.info.runway_months.formula'),
            vars: [
              { label: t('stats.kpi.quick_assets'),      value: fmt(summary.quick_assets ?? current.quick_assets ?? 0) },
              { label: t('stats.kpi.essential_expense'), value: fmt(summary.monthly_essential_expense ?? current.monthly_essential_expense ?? 0) },
            ],
          });
          KpiInfo.set('total_runway', {
            name: t('kpi.info.total_runway.name'),
            def: t('kpi.info.total_runway.def'),
            formula: t('kpi.info.total_runway.formula'),
            vars: [
              { label: t('report.total_assets'), value: fmt(summary.total_assets) },
              { label: t('stats.kpi.avg_monthly_expense_recent'), value: fmt(summary.avg_monthly_expense_recent) },
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
          KpiInfo.set('delta_net_worth', {
            name: t('kpi.info.delta_net_worth.name'),
            def: t('kpi.info.delta_net_worth.def'),
            formula: t('kpi.info.delta_net_worth.formula'),
            vars: [
              { label: t('proj.health.scenario_end_net_worth'), value: fmt(scenario.net_worth ?? 0) },
              { label: t('proj.health.baseline_end_net_worth'), value: fmt(baseline.net_worth ?? 0) },
            ],
          });
          KpiInfo.set('delta_runway', {
            name: t('kpi.info.delta_runway.name'),
            def: t('kpi.info.delta_runway.def'),
            formula: t('kpi.info.delta_runway.formula'),
            vars: [
              { label: t('proj.health.scenario_end_runway'), value: _fmtMonths(scenario.runway_months) },
              { label: t('proj.health.baseline_end_runway'), value: _fmtMonths(baseline.runway_months) },
            ],
          });
        }

        function _statsChartsMarkup() {
          return `
              <div class="overflow-y-auto flex-1">
              <div class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-5 xl:px-4 py-6">
              ${typeof Reports !== 'undefined' ? Reports._tagFilterBar() : ''}
              <div class="grid grid-cols-1 xl:grid-cols-2 gap-5" id="stats-grid">
                <div class="xl:col-span-2 bg-dark-800 border border-dark-600 rounded-xl p-4">
                  <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.monthly_cashflow')}</h3>
                  <canvas id="ch-cashflow" height="200"></canvas>
                </div>
                <div class="bg-dark-800 border border-dark-600 rounded-xl p-4">
                  <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.expense_by_type')}</h3>
                  <canvas id="ch-expense-breakdown" height="200"></canvas>
                </div>
                <div class="bg-dark-800 border border-dark-600 rounded-xl p-4">
                  <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.income_by_type')}</h3>
                  <canvas id="ch-income-breakdown" height="200"></canvas>
                </div>
                <div class="bg-dark-800 border border-dark-600 rounded-xl p-4">
                  <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.asset_composition')}</h3>
                  <canvas id="ch-asset-pie" height="200"></canvas>
                </div>
                <div class="bg-dark-800 border border-dark-600 rounded-xl p-4">
                  <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.top_accounts')}</h3>
                  <canvas id="ch-top-accounts" height="200"></canvas>
                </div>
                <div class="xl:col-span-2 bg-dark-800 border border-dark-600 rounded-xl p-4">
                  <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.net_worth_evolution')}</h3>
                  <canvas id="ch-net-worth" height="200"></canvas>
                </div>
              </div></div></div>`;
        }

        function _renderStatsCharts(data) {
          const summary = data.summary || {};
          const monthlyCashflow = data.monthly_cashflow || [];
          const expenseBreakdown = _topBreakdown(data.expenses_by_subtype || [], 'subtype', 'amount');
          const incomeBreakdown = _topBreakdown(data.income_by_subtype || [], 'subtype', 'amount');
          const assetComposition = data.asset_composition || [];
          const topAccounts = (data.top_accounts || []).filter(item => String(item.account || '').trim().toUpperCase() !== 'CAPITAL');
          const netWorthEvolution = data.net_worth_evolution || [];

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

          if (expenseBreakdown.length > 0) {
            _buildDoughnutChart(
              'ch-expense-breakdown',
              expenseBreakdown,
              'subtype',
              'amount',
              item => `${item.subtype}: ${fmt(item.amount)}`,
              ['#ef5350', '#ff8a65', '#ffb74d', '#ffd54f', '#e57373', '#f06292', '#a1887f', '#ffcc80']
            );
          } else {
            _replaceWithEmpty('ch-expense-breakdown');
          }

          if (incomeBreakdown.length > 0) {
            _buildDoughnutChart(
              'ch-income-breakdown',
              incomeBreakdown,
              'subtype',
              'amount',
              item => `${item.subtype}: ${fmt(item.amount)}`,
              ['#66bb6a', '#81c784', '#4db6ac', '#4fc3f7', '#aed581', '#dce775', '#26a69a', '#80cbc4']
            );
          } else {
            _replaceWithEmpty('ch-income-breakdown');
          }

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

          if (topAccounts.length > 0) {
            _buildDoughnutChart(
              'ch-top-accounts',
              topAccounts,
              'account',
              'volume',
              item => `${item.account}: ${fmt(item.volume)} • ${item.tx_count} ${t('stats.tx_count')}`,
              ['#4fc3f7', '#90caf9', '#7986cb', '#4db6ac', '#80cbc4', '#66bb6a', '#ffd54f', '#ff8a65']
            );
          } else {
            _replaceWithEmpty('ch-top-accounts');
          }

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
                    yAxisID: 'y',
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
                    yAxisID: 'y1',
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
                    yAxisID: 'y',
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
                  y1: {
                    position: 'right',
                    ticks: {
                      color: '#ef9a9a',
                      font: { size: 9 },
                      callback: v => '$ ' + (v / 1000).toFixed(0) + 'k',
                    },
                    grid: { drawOnChartArea: false },
                  },
                },
              },
            });
          } else {
            _replaceWithEmpty('ch-net-worth');
          }
        }
              <span class="font-mono text-dark-200 shrink-0">${escapeHtml(String(v.value))}</span>
            </div>`).join('')}

          async panel() {
            const q = State.buildReportQuery();
            const [statsData, prefs] = await Promise.all([
              API.get('/reports/stats' + q),
              API.get('/settings/preferences').catch(() => ({})),
            ]);
            const projData = await API.get(_buildProjectionQueryFromPrefs(prefs)).catch(() => null);
            const main = document.getElementById('main');
            const summary = statsData.summary || {};
            const health = projData?.health || {};
            const current = health.current || {};
            const baseline = health.baseline_end || {};
            const scenario = health.scenario_end || {};
            const delta = health.delta_end || {};
            const investmentModel = projData?.investment_model || {};
            const netResultClass = _num(summary.net_result) >= 0 ? 'text-ingreso' : 'text-pasivo';
            const savingsRateClass = _num(summary.savings_rate) >= 0 ? 'text-ingreso' : 'text-pasivo';
            const deltaNetWorthClass = _num(delta.net_worth) >= 0 ? 'text-ingreso' : 'text-pasivo';
            const deltaRunwayClass = delta.runway_months == null || _num(delta.runway_months) >= 0 ? 'text-ingreso' : 'text-pasivo';
            const recentMonthsNote = t('stats.note.recent_months', { count: summary.recent_months_count ?? 0 });
            const yieldSamples = Number(investmentModel.sample_count || 0);
            const contributionSamples = Number(investmentModel.contrib_sample_count || 0);

            destroyCharts();
            _registerSharedKpiInfo(summary, health);

            main.innerHTML = `
              <div class="overflow-y-auto flex-1">
              <div class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-5 xl:px-4 py-6">
              ${typeof Reports !== 'undefined' ? Reports._tagFilterBar() : ''}
              <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-5">
                ${_kpiCard({
                  label: t('proj.health.current_net_worth'),
                  value: fmt(summary.net_worth),
                  valueClass: 'text-activo',
                  note: `${t('report.total_assets')}: ${fmt(summary.total_assets)} · ${t('report.total_liab')}: ${fmt(summary.total_liabilities)}`,
                  infoKey: 'net_worth',
                })}
                ${_kpiCard({
                  label: t('proj.health.baseline_end_net_worth'),
                  value: baseline.net_worth == null ? '—' : fmt(baseline.net_worth),
                  valueClass: 'text-activo',
                  note: baseline.month || t('report.no_data'),
                  infoKey: 'net_worth',
                })}
                ${_kpiCard({
                  label: t('proj.health.scenario_end_net_worth'),
                  value: scenario.net_worth == null ? '—' : fmt(scenario.net_worth),
                  valueClass: 'text-activo',
                  note: scenario.month || t('report.no_data'),
                  infoKey: 'net_worth',
                })}
                ${_kpiCard({
                  label: t('proj.health.delta_net_worth'),
                  value: delta.net_worth == null ? '—' : fmtSigned(delta.net_worth),
                  valueClass: deltaNetWorthClass,
                  note: delta.month || '',
                  infoKey: 'delta_net_worth',
                })}
                ${_kpiCard({
                  label: t('stats.kpi.runway_months'),
                  value: _fmtMonths(summary.runway_months),
                  valueClass: _num(summary.runway_months) < 3 ? 'text-pasivo' : 'text-dark-100',
                  note: `${t('stats.kpi.essential_expense')}: ${fmt(summary.monthly_essential_expense)} · ${t(`stats.runway_basis.${summary.runway_basis || 'essential'}`)}`,
                  infoKey: 'runway_months',
                })}
                ${_kpiCard({
                  label: t('stats.kpi.total_runway'),
                  value: _fmtMonths(summary.total_runway_months),
                  valueClass: _num(summary.total_runway_months) < 6 ? 'text-pasivo' : 'text-dark-100',
                  note: t('stats.note.total_runway_basis', { count: summary.recent_months_count ?? 0, amount: fmt(summary.avg_monthly_expense_recent) }),
                  infoKey: 'total_runway',
                })}
                ${_kpiCard({
                  label: t('proj.health.baseline_end_runway'),
                  value: _fmtMonths(baseline.runway_months),
                  valueClass: 'text-dark-100',
                  note: baseline.month || t('report.no_data'),
                  infoKey: 'runway_months',
                })}
                ${_kpiCard({
                  label: t('proj.health.scenario_end_runway'),
                  value: _fmtMonths(scenario.runway_months),
                  valueClass: 'text-dark-100',
                  note: scenario.month || t('report.no_data'),
                  infoKey: 'runway_months',
                })}
                ${_kpiCard({
                  label: t('proj.health.delta_runway'),
                  value: _fmtSignedMonths(delta.runway_months),
                  valueClass: deltaRunwayClass,
                  note: delta.month || '',
                  infoKey: 'delta_runway',
                })}
                ${_kpiCard({
                  label: t('stats.kpi.avg_monthly_income_recent'),
                  value: summary.avg_monthly_income_recent == null ? '—' : fmt(summary.avg_monthly_income_recent),
                  valueClass: 'text-ingreso',
                  note: recentMonthsNote,
                })}
                ${_kpiCard({
                  label: t('stats.kpi.avg_monthly_expense_recent'),
                  value: summary.avg_monthly_expense_recent == null ? '—' : fmt(summary.avg_monthly_expense_recent),
                  valueClass: 'text-pasivo',
                  note: recentMonthsNote,
                })}
                ${_kpiCard({
                  label: t('stats.kpi.avg_investment_yield'),
                  value: yieldSamples > 0 ? _fmtPct(investmentModel.yield_rate) : '—',
                  valueClass: 'text-activo',
                  note: t('stats.note.yield_samples', { count: yieldSamples }),
                })}
                ${_kpiCard({
                  label: t('stats.kpi.avg_investment_contribution_rate'),
                  value: contributionSamples > 0 ? _fmtPct(investmentModel.contribution_rate) : '—',
                  valueClass: 'text-dark-100',
                  note: t('stats.note.contribution_samples', { count: contributionSamples }),
                })}
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
              </div></div>`;
          },
        </div>
      </div>` : '';

    const body = `
      <div class="p-5 space-y-1">
  },
};
            main.innerHTML = _statsChartsMarkup();
            _renderStatsCharts(data);
          },
        },
      });
    } else {
      _replaceWithEmpty('ch-asset-pie');
    }

    /* ── 5. Top Accounts ── */
    if (topAccounts.length > 0) {
      _buildDoughnutChart(
        'ch-top-accounts',
        topAccounts,
        'account',
        'volume',
        item => `${item.account}: ${fmt(item.volume)} • ${item.tx_count} ${t('stats.tx_count')}`,
        ['#4fc3f7', '#90caf9', '#7986cb', '#4db6ac', '#80cbc4', '#66bb6a', '#ffd54f', '#ff8a65']
      );
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
              yAxisID: 'y',
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
              yAxisID: 'y1',
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
              yAxisID: 'y',
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
            y1: {
              position: 'right',
              ticks: {
                color: '#ef9a9a',
                font: { size: 9 },
                callback: v => '$ ' + (v / 1000).toFixed(0) + 'k',
              },
              grid: { drawOnChartArea: false },
            },
          },
        },
      });
    } else {
      _replaceWithEmpty('ch-net-worth');
    }
  },
};
