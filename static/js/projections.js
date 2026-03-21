/* ── projections.js — Financial Projections view ── */

'use strict';

let _projCharts = {};

let _projState = {
  horizon: 12,
  historyMonths: 12,
  series: [],
  projData: null,
};

function _destroyProjCharts() {
  Object.values(_projCharts).forEach(c => { try { c.destroy(); } catch {} });
  _projCharts = {};
}

const PROJ_COLORS = {
  income:      '#66bb6a',
  expenses:    '#ef5350',
  savings:     '#ffd54f',
  assets:      '#4fc3f7',
  liabilities: '#ce93d8',
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function _parseMonth(m) {
  return { y: parseInt(m.slice(0, 4)), mo: parseInt(m.slice(5, 7)) };
}

function _monthActive(series, monthStr) {
  // Returns true if monthStr (YYYY-MM) falls within the series date range
  const start = series.start_date.slice(0, 7); // YYYY-MM
  const { y: sy, mo: sm } = _parseMonth(start);
  const { y: my, mo: mm } = _parseMonth(monthStr);
  const idx = (my - sy) * 12 + (mm - sm);
  return idx >= 0 && idx < series.months;
}

// ── Series table ──────────────────────────────────────────────────────────────

function _renderSeriesTable() {
  const container = document.getElementById('proj-series-table');
  if (!container) return;

  const { series, projData } = _projState;
  const projMonths = projData?.projected_months ?? [];

  if (series.length === 0) {
    container.innerHTML = `<div class="empty text-sm py-4">${t('proj.no_series')}</div>`;
    return;
  }

  // Header row
  const thMonths = projMonths.map(m =>
    `<th class="px-2 py-1.5 text-right text-[10px] text-dark-400 font-normal whitespace-nowrap">${m}</th>`
  ).join('');

  // Income and expense totals per projected month
  const incomeTotals = new Array(projMonths.length).fill(0);
  const expenseTotals = new Array(projMonths.length).fill(0);

  const rows = series.map(s => {
    const typeBadge = s.type === 'income'
      ? `<span class="text-[10px] px-1.5 py-0.5 rounded bg-ingreso/20 text-ingreso">${t('proj.series.type_income')}</span>`
      : `<span class="text-[10px] px-1.5 py-0.5 rounded bg-gasto/20 text-gasto">${t('proj.series.type_expense')}</span>`;

    const cells = projMonths.map((m, i) => {
      const active = _monthActive(s, m);
      if (active) {
        if (s.type === 'income') incomeTotals[i] += s.monthly_amount;
        else expenseTotals[i] += s.monthly_amount;
        return `<td class="px-2 py-1 text-right text-xs text-dark-200 whitespace-nowrap">${fmt(s.monthly_amount)}</td>`;
      }
      return `<td class="px-2 py-1 text-right text-xs text-dark-600">—</td>`;
    }).join('');

    return `<tr class="border-t border-dark-700 hover:bg-dark-700/30">
      <td class="sticky left-0 z-10 bg-dark-800 px-3 py-2 min-w-[180px]">
        <div class="flex items-center gap-2">
          <span class="text-sm text-dark-200 truncate max-w-[120px]" title="${escapeHtml(s.name)}">${escapeHtml(s.name)}</span>
          ${typeBadge}
        </div>
      </td>
      <td class="px-2 py-1 text-right">
        <div class="flex items-center justify-end gap-1">
          <button onclick="Projections.openSeriesDialog(${s.id})"
                  class="text-dark-400 hover:text-dark-200 text-xs px-1.5 py-0.5 rounded hover:bg-dark-600">✏️</button>
          <button onclick="Projections.deleteSeries(${s.id})"
                  class="text-dark-400 hover:text-pasivo text-xs px-1.5 py-0.5 rounded hover:bg-dark-600">🗑</button>
        </div>
      </td>
      ${cells}
    </tr>`;
  }).join('');

  // Totals rows
  const incomeTotalCells = incomeTotals.map(v =>
    `<td class="px-2 py-1.5 text-right text-xs font-medium text-ingreso whitespace-nowrap">${v > 0 ? fmt(v) : '—'}</td>`
  ).join('');
  const expenseTotalCells = expenseTotals.map(v =>
    `<td class="px-2 py-1.5 text-right text-xs font-medium text-gasto whitespace-nowrap">${v > 0 ? fmt(v) : '—'}</td>`
  ).join('');

  container.innerHTML = `
    <div class="overflow-x-auto rounded-xl border border-dark-600">
      <table class="w-full text-sm border-collapse min-w-max">
        <thead>
          <tr class="bg-dark-700/50">
            <th class="sticky left-0 z-10 bg-dark-700/50 px-3 py-1.5 text-left text-xs text-dark-400 font-medium min-w-[180px]">${t('proj.series.col.name')}</th>
            <th class="px-2 py-1.5 text-left text-xs text-dark-400 font-medium whitespace-nowrap">${t('proj.series.col.type')}</th>
            ${thMonths}
          </tr>
        </thead>
        <tbody>
          ${rows}
          <tr class="border-t-2 border-dark-500 bg-dark-700/30">
            <td class="sticky left-0 z-10 bg-dark-700 px-3 py-1.5 text-xs font-semibold text-ingreso">${t('proj.series.col.income_total')}</td>
            <td></td>
            ${incomeTotalCells}
          </tr>
          <tr class="border-t border-dark-600 bg-dark-700/20">
            <td class="sticky left-0 z-10 bg-dark-700/50 px-3 py-1.5 text-xs font-semibold text-gasto">${t('proj.series.col.expense_total')}</td>
            <td></td>
            ${expenseTotalCells}
          </tr>
        </tbody>
      </table>
    </div>`;
}

// ── Charts ────────────────────────────────────────────────────────────────────

const _projDefaults = {
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
        label: (ctx) => {
          const val = ctx.parsed?.y ?? ctx.parsed;
          return val != null ? ` ${fmt(val)}` : '';
        }
      }
    }
  },
  scales: {
    x: { ticks: { color: '#8b949e', font: { size: 9 } }, grid: { color: '#30363d33' } },
    y: { ticks: { color: '#8b949e', font: { size: 9 },
                  callback: v => '$ ' + (Math.abs(v) >= 1000 ? (v / 1000).toFixed(0) + 'k' : v.toFixed(0)) },
         grid: { color: '#30363d44' } },
  },
};

function _buildProjectionDatasets(metric, histMonths, projMonths, projData, color) {
  const allLabels = [...histMonths, ...projMonths];
  const n_hist = histMonths.length;
  const n_proj = projMonths.length;
  const n_all = allLabels.length;

  // 1. Historical scatter
  const histMap = {};
  (projData.historical[metric] || []).forEach(p => { histMap[p.month] = p.value; });
  const scatterData = histMonths.map(m => histMap[m] != null ? histMap[m] : null);

  // 2. Regression trend line across all months
  const reg = projData.regression[metric];
  const trendData = allLabels.map((_, i) => {
    const val = reg.intercept + reg.slope * i;
    return Math.max(0, Math.round(val * 100) / 100);
  });

  // 3. Final projection (future only) = baseline + series adjustment
  const baseline = projData.baseline_projection[metric] || [];
  const adjArr   = projData.series_adjustment[metric]   || [];
  const projFull = Array(n_hist).fill(null).concat(
    baseline.map((b, i) => Math.max(0, Math.round((b + (adjArr[i] || 0)) * 100) / 100))
  );

  return {
    labels: allLabels,
    datasets: [
      {
        label: t('proj.chart.historical'),
        type: 'scatter',
        data: scatterData.map((v, i) => v != null ? { x: histMonths[i], y: v } : null).filter(Boolean),
        parsing: false,
        pointRadius: 5,
        pointBackgroundColor: color,
        pointBorderColor: color,
        showLine: false,
        order: 1,
      },
      {
        label: t('proj.chart.trend'),
        type: 'line',
        data: trendData,
        borderColor: color + '88',
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        borderDash: [6, 3],
        pointRadius: 0,
        fill: false,
        tension: 0,
        order: 2,
      },
      {
        label: t('proj.chart.with_series'),
        type: 'line',
        data: projFull,
        borderColor: color,
        backgroundColor: color + '18',
        borderWidth: 2,
        pointRadius: 2,
        fill: 'origin',
        tension: 0.3,
        order: 0,
      },
    ]
  };
}

function _renderCharts() {
  _destroyProjCharts();
  const { projData } = _projState;
  if (!projData) return;

  const histMonths = projData.historical_months || [];
  const projMonths = projData.projected_months || [];

  const metrics = [
    { key: 'income',      labelKey: 'proj.chart.income',      id: 'ch-proj-income' },
    { key: 'expenses',    labelKey: 'proj.chart.expenses',    id: 'ch-proj-expenses' },
    { key: 'savings',     labelKey: 'proj.chart.savings',     id: 'ch-proj-savings' },
    { key: 'assets',      labelKey: 'proj.chart.assets',      id: 'ch-proj-assets' },
    { key: 'liabilities', labelKey: 'proj.chart.liabilities', id: 'ch-proj-liabilities' },
  ];

  for (const m of metrics) {
    const canvas = document.getElementById(m.id);
    if (!canvas) continue;
    const hasHist = (projData.historical[m.key] || []).length > 0;
    if (!hasHist && projMonths.length === 0) {
      canvas.parentElement.innerHTML +=
        `<div class="empty text-xs py-2">${t('proj.no_history')}</div>`;
      continue;
    }

    const { labels, datasets } = _buildProjectionDatasets(
      m.key, histMonths, projMonths, projData, PROJ_COLORS[m.key]
    );

    _projCharts[m.id] = new Chart(canvas, {
      type: 'line',
      data: { labels, datasets },
      options: {
        ..._projDefaults,
        responsive: true,
        plugins: {
          ..._projDefaults.plugins,
          legend: { ..._projDefaults.plugins.legend },
        },
        scales: {
          x: {
            ..._projDefaults.scales.x,
            ticks: {
              ..._projDefaults.scales.x.ticks,
              maxTicksLimit: 24,
              maxRotation: 45,
            },
          },
          y: _projDefaults.scales.y,
        },
      },
    });
  }
}

// ── Controls ──────────────────────────────────────────────────────────────────

function _setActiveBtn(groupId, value) {
  document.querySelectorAll(`#${groupId} button`).forEach(btn => {
    const active = String(btn.dataset.val) === String(value);
    btn.classList.toggle('!bg-blue-600/20', active);
    btn.classList.toggle('!border-blue-500/40', active);
    btn.classList.toggle('!text-blue-300', active);
  });
}

function _buildPageShell() {
  const horizonBtns = [
    { months: 12,  label: t('proj.horizon.1y') },
    { months: 24,  label: t('proj.horizon.2y') },
    { months: 60,  label: t('proj.horizon.5y') },
    { months: 120, label: t('proj.horizon.10y') },
  ].map(b =>
    `<button class="tbtn text-xs px-2.5 py-1" data-val="${b.months}"
             onclick="Projections._onHorizonChange(${b.months})">${b.label}</button>`
  ).join('');

  const histBtns = [
    { months: 3,  label: t('proj.history.3m') },
    { months: 6,  label: t('proj.history.6m') },
    { months: 12, label: t('proj.history.12m') },
    { months: 24, label: t('proj.history.24m') },
  ].map(b =>
    `<button class="tbtn text-xs px-2.5 py-1" data-val="${b.months}"
             onclick="Projections._onHistoryChange(${b.months})">${b.label}</button>`
  ).join('');

  const chartSection = (id, labelKey) => `
    <div class="bg-dark-800 border border-dark-600 rounded-xl p-4 lg:col-span-2">
      <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t(labelKey)}</h3>
      <canvas id="${id}" height="200"></canvas>
    </div>`;

  return `
    <div class="overflow-y-auto flex-1">
    <div class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-5 xl:px-4 py-6 space-y-5">

      <!-- Controls bar -->
      <div class="flex flex-wrap items-center gap-3 bg-dark-800 border border-dark-600 rounded-xl px-4 py-3">
        <span class="text-xs text-dark-400 shrink-0">${t('proj.controls.horizon')}:</span>
        <div class="flex gap-1" id="proj-horizon-btns">${horizonBtns}</div>
        <div class="w-px h-4 bg-dark-600 mx-1 shrink-0 hidden sm:block"></div>
        <span class="text-xs text-dark-400 shrink-0">${t('proj.controls.history')}:</span>
        <div class="flex gap-1" id="proj-history-btns">${histBtns}</div>
        <div class="flex-1"></div>
        <button class="tbtn text-xs px-3 py-1.5 !bg-blue-600/20 !border-blue-500/50 !text-blue-300"
                onclick="Projections.openSeriesDialog()">${t('proj.controls.add_series')}</button>
      </div>

      <!-- Series table -->
      <div class="bg-dark-800 border border-dark-600 rounded-xl p-4">
        <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('proj.series.table_title')}</h3>
        <div id="proj-series-table"><div class="spinner">⏳</div></div>
      </div>

      <!-- Charts grid -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-5" id="proj-charts-grid">
        ${chartSection('ch-proj-income',      'proj.chart.income')}
        ${chartSection('ch-proj-expenses',    'proj.chart.expenses')}
        ${chartSection('ch-proj-savings',     'proj.chart.savings')}
        ${chartSection('ch-proj-assets',      'proj.chart.assets')}
        ${chartSection('ch-proj-liabilities', 'proj.chart.liabilities')}
      </div>

    </div></div>`;
}

// ── Data loading ──────────────────────────────────────────────────────────────

async function _loadData() {
  try {
    const [series, projData] = await Promise.all([
      API.get('/projections/series'),
      API.get(`/reports/projections?horizon=${_projState.horizon}&history_months=${_projState.historyMonths}`),
    ]);
    _projState.series = series;
    _projState.projData = projData;
    _renderSeriesTable();
    _renderCharts();
  } catch (e) {
    const tbl = document.getElementById('proj-series-table');
    if (tbl) tbl.innerHTML = `<div class="empty text-pasivo text-xs">Error: ${escapeHtml(e.message)}</div>`;
  }
}

// ── Public API ────────────────────────────────────────────────────────────────

const Projections = {

  async render() {
    _destroyProjCharts();
    const main = document.getElementById('main');
    main.innerHTML = _buildPageShell();
    _setActiveBtn('proj-horizon-btns', _projState.horizon);
    _setActiveBtn('proj-history-btns', _projState.historyMonths);
    await _loadData();
  },

  _onHorizonChange(months) {
    _projState.horizon = months;
    _setActiveBtn('proj-horizon-btns', months);
    _loadData();
  },

  _onHistoryChange(months) {
    _projState.historyMonths = months;
    _setActiveBtn('proj-history-btns', months);
    _loadData();
  },

  openSeriesDialog(id = null) {
    const existing = id != null ? _projState.series.find(s => s.id === id) : null;
    const title = existing ? t('proj.series.edit_title') : t('proj.series.add_title');

    // Default start month = current month
    const today = new Date();
    const defaultMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;
    const startVal = existing ? existing.start_date.slice(0, 7) : defaultMonth;

    const html = `<div class="p-5 space-y-4">
      ${T.group(t('proj.series.name'),
          T.input('ps-name', { val: existing?.name ?? '', ph: t('proj.series.name_ph'), auto: true }))}
      ${T.row2(
          T.group(t('proj.series.type'),
              `<select id="ps-type"
                 class="w-full bg-dark-700 border border-dark-600 rounded-lg text-dark-200 text-sm px-3 py-2 focus:outline-none focus:border-blue-500">
                <option value="income" ${existing?.type === 'income' ? 'selected' : ''}>${t('proj.series.type_income')}</option>
                <option value="expense" ${existing?.type === 'expense' ? 'selected' : ''}>${t('proj.series.type_expense')}</option>
              </select>`),
          T.group(t('proj.series.start_date'),
              `<input type="month" id="ps-start" value="${startVal}"
                 class="w-full bg-dark-700 border border-dark-600 rounded-lg text-dark-200 text-sm px-3 py-2 focus:outline-none focus:border-blue-500">`)
      )}
      ${T.row2(
          T.group(t('proj.series.months'),
              T.input('ps-months', { type: 'number', val: existing?.months ?? 1, ph: '1' })),
          T.group(t('proj.series.amount'),
              T.input('ps-amount', { type: 'number', val: existing?.monthly_amount ?? '', ph: '0.00' }))
      )}
    </div>`;

    Modal.open(html, {
      title,
      submitLabel: existing ? t('btn.save') : t('btn.create'),
      onSubmit: async () => {
        const name   = document.getElementById('ps-name').value.trim();
        const type   = document.getElementById('ps-type').value;
        const start  = document.getElementById('ps-start').value;  // YYYY-MM
        const months = parseInt(document.getElementById('ps-months').value, 10);
        const amount = parseFloat(document.getElementById('ps-amount').value);

        if (!name) { Toast.show(t('msg.invalid_value'), 'err'); return false; }
        if (!start) { Toast.show(t('msg.invalid_value'), 'err'); return false; }
        if (isNaN(months) || months < 1) { Toast.show(t('msg.invalid_value'), 'err'); return false; }
        if (isNaN(amount) || amount <= 0) { Toast.show(t('msg.invalid_value'), 'err'); return false; }

        const payload = { name, type, start_date: start + '-01', months, monthly_amount: amount };
        try {
          if (existing) {
            await API.put(`/projections/series/${id}`, payload);
            Toast.show(t('proj.series.updated'));
          } else {
            await API.post('/projections/series', payload);
            Toast.show(t('proj.series.created'));
          }
          await _loadData();
        } catch (e) {
          Toast.show(e.message, 'err');
          return false;
        }
      },
    });
  },

  async deleteSeries(id) {
    const s = _projState.series.find(x => x.id === id);
    const confirmed = await Dialog.confirm({
      title: t('proj.series.delete_title'),
      message: s ? `"${escapeHtml(s.name)}"` : '',
      confirmLabel: t('btn.delete'),
      submitTone: 'danger',
    });
    if (!confirmed) return;
    try {
      await API.del(`/projections/series/${id}`);
      Toast.show(t('proj.series.deleted'));
      await _loadData();
    } catch (e) {
      Toast.show(e.message, 'err');
    }
  },
};
