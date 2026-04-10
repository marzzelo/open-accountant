/* ── projections.js — Financial Projections view ── */

'use strict';

let _projCharts = {};

let _projState = {
  horizon: 12,
  historyMonths: 12,
  series: [],
  projData: null,
  trendPanelOpen: false,
  trendSettings: {
    income:   { mode: 'linear', minVal: '', maxVal: '', inflationBase: '', inflationRate: '' },
    expenses: { mode: 'linear', minVal: '', maxVal: '', inflationBase: '', inflationRate: '' },
  },
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

function _fmtProjRatio(value) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  return `${Number(value).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}x`;
}

function _fmtProjMonths(value) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  return `${Number(value).toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}m`;
}

function _healthCard(label, value, note = '', valueClass = 'text-dark-100', infoKey = null) {
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

function _getLastKnownValue(metric, projData) {
  if (!projData) return null;
  const pts = projData.historical[metric] || [];
  return pts.length > 0 ? pts[pts.length - 1].value : null;
}

function _trendSettingPrecision(field) {
  return field === 'inflationRate' ? 4 : 2;
}

function _parseTrendSettingNumber(value, field) {
  const parsed = parseMoneyInput(value, { maxFractionDigits: _trendSettingPrecision(field) });
  return parsed.isValid ? parsed.value : null;
}

function _normalizeTrendSettingValue(field, value) {
  const parsed = parseMoneyInput(value, { maxFractionDigits: _trendSettingPrecision(field) });
  if (parsed.isEmpty) return { isEmpty: true, isValid: true, normalized: '', value: null };
  if (!parsed.isValid || !Number.isFinite(parsed.value) || parsed.value < 0) {
    return { isEmpty: false, isValid: false, normalized: '', value: Number.NaN };
  }
  return {
    isEmpty: false,
    isValid: true,
    normalized: parsed.normalized,
    value: parsed.value,
  };
}

// ── Trend computation ─────────────────────────────────────────────────────────

function _olsFromPoints(pts) {
  // OLS on [{idx, value}] using actual indices (not re-indexed 0..n-1).
  // This ensures the result is consistent with the index space of allLabels.
  const n = pts.length;
  if (n === 0) return { slope: 0, intercept: 0 };
  if (n === 1) return { slope: 0, intercept: pts[0].value };
  const xm = pts.reduce((s, p) => s + p.idx, 0) / n;
  const ym = pts.reduce((s, p) => s + p.value, 0) / n;
  const num = pts.reduce((s, p) => s + (p.idx - xm) * (p.value - ym), 0);
  const den = pts.reduce((s, p) => s + (p.idx - xm) ** 2, 0);
  const slope = den ? num / den : 0;
  return { slope, intercept: ym - slope * xm };
}

function _computeTrendDatasets(allLabels, histMonths, histMap, color, settings) {
  // Returns { trendDataset, outlierDataset } — either may be null.
  // idx of each known point = its position in allLabels (== position in histMonths).
  const allPts = histMonths
    .map((m, i) => histMap[m] != null ? { idx: i, month: m, value: histMap[m] } : null)
    .filter(Boolean);

  // ── Inflation mode ──────────────────────────────────────────────────────────
  if (settings.mode === 'inflation') {
    if (allPts.length === 0) return { trendDataset: null, outlierDataset: null };

    const lastPt  = allPts[allPts.length - 1];
    const rawBase = settings.inflationBase;
    const base    = (rawBase !== '' && rawBase !== null) ? _parseTrendSettingNumber(rawBase, 'inflationBase') : lastPt.value;
    const rawRate = settings.inflationRate;
    const parsedRate = (rawRate !== '' && rawRate !== null) ? _parseTrendSettingNumber(rawRate, 'inflationRate') : null;
    const rate = parsedRate != null ? parsedRate / 100 : 0;

    if (isNaN(base)) return { trendDataset: null, outlierDataset: null };

    // Trend starts at lastPt.idx (last known month) and extends into the future.
    // Historical months before that point are left null (no backward extrapolation).
    const trendData = allLabels.map((_, i) => {
      if (i < lastPt.idx) return null;
      return Math.max(0, Math.round(base * Math.pow(1 + rate, i - lastPt.idx) * 100) / 100);
    });

    return {
      trendDataset: {
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
        spanGaps: false,
      },
      outlierDataset: null,
    };
  }

  // ── Linear regression mode (with optional outlier filtering) ────────────────
  const minVal = settings.minVal !== '' ? _parseTrendSettingNumber(settings.minVal, 'minVal') : null;
  const maxVal = settings.maxVal !== '' ? _parseTrendSettingNumber(settings.maxVal, 'maxVal') : null;
  const hasMin = minVal !== null && !isNaN(minVal);
  const hasMax = maxVal !== null && !isNaN(maxVal);

  const inliers  = allPts.filter(p => (!hasMin || p.value >= minVal) && (!hasMax || p.value <= maxVal));
  const outliers = allPts.filter(p => (hasMin && p.value < minVal) || (hasMax && p.value > maxVal));
  const outlierDataset = outliers.length > 0 ? {
    label: t('proj.chart.outliers'),
    type: 'scatter',
    data: outliers.map(p => ({ x: p.month, y: p.value })),
    parsing: false,
    pointStyle: 'crossRot',
    pointRadius: 7,
    pointBorderWidth: 2.5,
    pointBackgroundColor: 'transparent',
    pointBorderColor: '#ef4444',
    showLine: false,
    order: 0,
  } : null;

  if (inliers.length === 0) return { trendDataset: null, outlierDataset };

  const { slope, intercept } = _olsFromPoints(inliers);
  const trendData = allLabels.map((_, i) =>
    Math.max(0, Math.round((intercept + slope * i) * 100) / 100)
  );

  const trendDataset = {
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
  };

  return { trendDataset, outlierDataset };
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

function _renderHealthSummary() {
  const container = document.getElementById('proj-health-summary');
  if (!container) return;

  const health = _projState.projData?.health;
  if (!health) {
    container.innerHTML = '';
    return;
  }

  const current = health.current || {};
  const baseline = health.baseline_end || {};
  const scenario = health.scenario_end || {};
  const delta = health.delta_end || {};
  const deltaNetWorth = Number(delta.net_worth || 0);
  const deltaRunway = delta.runway_months == null ? null : Number(delta.runway_months);

  KpiInfo.set('net_worth', {
    name: t('kpi.info.net_worth.name'),
    def: t('kpi.info.net_worth.def'),
    formula: t('kpi.info.net_worth.formula'),
    vars: [
      { label: t('report.total_assets'), value: fmt(current.assets ?? 0) },
      { label: t('report.total_liab'),   value: fmt(current.liabilities ?? 0) },
    ],
  });
  KpiInfo.set('current_ratio', {
    name: t('kpi.info.current_ratio.name'),
    def: t('kpi.info.current_ratio.def'),
    formula: t('kpi.info.current_ratio.formula'),
    vars: [
      { label: t('stats.kpi.current_assets'),      value: fmt(current.current_assets ?? 0) },
      { label: t('stats.kpi.current_liabilities'), value: fmt(current.current_liabilities ?? 0) },
    ],
  });
  KpiInfo.set('quick_ratio', {
    name: t('kpi.info.quick_ratio.name'),
    def: t('kpi.info.quick_ratio.def'),
    formula: t('kpi.info.quick_ratio.formula'),
    vars: [
      { label: t('stats.kpi.quick_assets'),        value: fmt(current.quick_assets ?? 0) },
      { label: t('stats.kpi.current_liabilities'), value: fmt(current.current_liabilities ?? 0) },
    ],
  });
  KpiInfo.set('runway_months', {
    name: t('kpi.info.runway_months.name'),
    def: t('kpi.info.runway_months.def'),
    formula: t('kpi.info.runway_months.formula'),
    vars: [
      { label: t('stats.kpi.quick_assets'),      value: fmt(current.quick_assets ?? 0) },
      { label: t('stats.kpi.essential_expense'), value: fmt(current.monthly_essential_expense ?? 0) },
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
      { label: t('proj.health.scenario_end_runway'), value: _fmtProjMonths(scenario.runway_months) },
      { label: t('proj.health.baseline_end_runway'), value: _fmtProjMonths(baseline.runway_months) },
    ],
  });

  container.innerHTML = `
    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
      ${_healthCard(t('proj.health.current_net_worth'), fmt(current.net_worth), current.month || '', 'text-activo', 'net_worth')}
      ${_healthCard(t('stats.kpi.current_ratio'), _fmtProjRatio(current.current_ratio), `${t('stats.kpi.current_liabilities')}: ${fmt(current.current_liabilities)}`, 'text-dark-100', 'current_ratio')}
      ${_healthCard(t('stats.kpi.quick_ratio'), _fmtProjRatio(current.quick_ratio), `${t('stats.kpi.quick_assets')}: ${fmt(current.quick_assets)}`, 'text-dark-100', 'quick_ratio')}
      ${_healthCard(t('stats.kpi.runway_months'), _fmtProjMonths(current.runway_months), `${t('stats.kpi.essential_expense')}: ${fmt(current.monthly_essential_expense)}`, 'text-dark-100', 'runway_months')}
      ${_healthCard(t('proj.health.baseline_end_net_worth'), fmt(baseline.net_worth), baseline.month || '', 'text-activo', 'net_worth')}
      ${_healthCard(t('proj.health.baseline_end_runway'), _fmtProjMonths(baseline.runway_months), `${t('stats.kpi.current_ratio')}: ${_fmtProjRatio(baseline.current_ratio)}`, 'text-dark-100', 'runway_months')}
      ${_healthCard(t('proj.health.scenario_end_net_worth'), fmt(scenario.net_worth), scenario.month || '', 'text-activo', 'net_worth')}
      ${_healthCard(t('proj.health.scenario_end_runway'), _fmtProjMonths(scenario.runway_months), `${t('stats.kpi.current_ratio')}: ${_fmtProjRatio(scenario.current_ratio)}`, 'text-dark-100', 'runway_months')}
      ${_healthCard(t('proj.health.delta_net_worth'), fmtSigned(delta.net_worth), delta.month || '', deltaNetWorth >= 0 ? 'text-ingreso' : 'text-pasivo', 'delta_net_worth')}
      ${_healthCard(
        t('proj.health.delta_runway'),
        deltaRunway == null ? '—' : `${deltaRunway >= 0 ? '+' : ''}${_fmtProjMonths(deltaRunway)}`,
        '',
        deltaRunway == null || deltaRunway >= 0 ? 'text-ingreso' : 'text-pasivo',
        'delta_runway'
      )}
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

function _buildProjectionDatasets(metric, histMonths, projMonths, projData, color, showTrend = true, trendSettings = null) {
  const allLabels = [...histMonths, ...projMonths];
  const n_hist = histMonths.length;

  // 1. Build histMap from real data points
  const histMap = {};
  (projData.historical[metric] || []).forEach(p => { histMap[p.month] = p.value; });

  // 2. Compute trend datasets
  let trendDataset = null;
  let outlierDataset = null;

  if (showTrend) {
    if (trendSettings) {
      // Frontend computation (income / expenses):
      // supports outlier filtering and inflation mode.
      ({ trendDataset, outlierDataset } = _computeTrendDatasets(
        allLabels, histMonths, histMap, color, trendSettings
      ));
    } else {
      // Backend regression (savings): use pre-computed slope/intercept.
      // Assets/liabilities have showTrend=false and never reach this branch.
      const reg = projData.regression[metric];
      if (reg) {
        const trendData = allLabels.map((_, i) =>
          Math.max(0, Math.round((reg.intercept + reg.slope * i) * 100) / 100)
        );
        trendDataset = {
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
        };
      }
    }
  }

  // 3. Historical scatter — inlier points only (outliers get their own dataset)
  const outlierMonths = new Set((outlierDataset?.data || []).map(p => p.x));
  const scatterPoints = histMonths
    .filter(m => histMap[m] != null && !outlierMonths.has(m))
    .map(m => ({ x: m, y: histMap[m] }));

  // 4. Projection (future only) = trend baseline + series adjustment
  //    When trendSettings is provided (income/expenses), we read the already-computed
  //    trend line values so that the projection curve always follows the chosen mode
  //    (linear regression or inflation). Otherwise (savings) we fall back to the
  //    backend-computed baseline.
  const adjArr = projData.series_adjustment[metric] || [];
  let projFull;
  if (trendSettings && trendDataset) {
    // trendDataset.data is indexed over allLabels; projected months start at n_hist.
    projFull = Array(n_hist).fill(null).concat(
      projMonths.map((_, projIdx) => {
        const trendVal = trendDataset.data[n_hist + projIdx] ?? 0;
        return Math.max(0, Math.round((trendVal + (adjArr[projIdx] || 0)) * 100) / 100);
      })
    );
  } else {
    const baseline = projData.baseline_projection[metric] || [];
    projFull = Array(n_hist).fill(null).concat(
      baseline.map((b, i) => Math.max(0, Math.round((b + (adjArr[i] || 0)) * 100) / 100))
    );
  }

  // Expose raw numerical arrays so derived metrics (savings = income - expenses)
  // can subtract them without re-parsing the chart dataset objects.
  const rawTrendData = trendDataset?.data ?? null;

  return {
    labels: allLabels,
    datasets: [
      {
        label: t('proj.chart.historical'),
        type: 'scatter',
        data: scatterPoints,
        parsing: false,
        pointRadius: 5,
        pointBackgroundColor: color,
        pointBorderColor: color,
        showLine: false,
        order: 1,
      },
      ...(trendDataset   ? [trendDataset]   : []),
      ...(outlierDataset ? [outlierDataset] : []),
      {
        label: t('proj.chart.projection'),
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
    ],
    _raw: { trendData: rawTrendData, projFull },
  };
}

// ── Trend settings panel ──────────────────────────────────────────────────────

function _buildTrendSection(metricKey, sectionLabel, color) {
  const s = _projState.trendSettings[metricKey];

  const modeBtn = (val, fallback) => {
    const active = s.mode === val;
    return `<button onclick="Projections._onTrendMode('${metricKey}', '${val}')"
               class="tbtn text-xs px-2.5 py-1${active ? ' !bg-blue-600/20 !border-blue-500/40 !text-blue-300' : ''}">
              ${t('proj.trend.mode_' + val) || fallback}
            </button>`;
  };

  const inputCls = 'w-full bg-dark-700 border border-dark-600 rounded-lg text-dark-200 text-xs px-2 py-1.5 focus:outline-none focus:border-blue-500';
  const labelCls = 'text-[11px] text-dark-400 w-16 shrink-0';

  const linearBlock = `
    <div class="space-y-2${s.mode === 'linear' ? '' : ' hidden'}" id="trend-linear-${metricKey}">
      <div class="flex items-center gap-2">
        <label class="${labelCls}">${t('proj.trend.min') || 'Mín'}</label>
        <input type="text" value="${s.minVal}" inputmode="decimal"
               placeholder="${t('proj.trend.no_limit') || 'sin límite'}"
               onchange="Projections._onTrendSetting('${metricKey}', 'minVal', this.value)"
               class="${inputCls}">
      </div>
      <div class="flex items-center gap-2">
        <label class="${labelCls}">${t('proj.trend.max') || 'Máx'}</label>
        <input type="text" value="${s.maxVal}" inputmode="decimal"
               placeholder="${t('proj.trend.no_limit') || 'sin límite'}"
               onchange="Projections._onTrendSetting('${metricKey}', 'maxVal', this.value)"
               class="${inputCls}">
      </div>
      <p class="text-[10px] text-dark-500 leading-snug">${t('proj.trend.linear_hint') || 'Valores fuera del rango se excluyen del cálculo y se marcan con ✕ en el gráfico.'}</p>
    </div>`;

  const inflationBlock = `
    <div class="space-y-2${s.mode === 'inflation' ? '' : ' hidden'}" id="trend-inflation-${metricKey}">
      <div class="flex items-center gap-2">
        <label class="${labelCls}">${t('proj.trend.base') || 'Base'}</label>
        <input type="text" value="${s.inflationBase}" inputmode="decimal"
               placeholder="${t('proj.trend.last_value') || 'último valor'}"
               onchange="Projections._onTrendSetting('${metricKey}', 'inflationBase', this.value)"
               class="${inputCls}">
      </div>
      <div class="flex items-center gap-2">
        <label class="${labelCls}">${t('proj.trend.rate') || '% / mes'}</label>
        <input type="text" step="0.01" value="${s.inflationRate}" inputmode="decimal"
               placeholder="0.00"
               onchange="Projections._onTrendSetting('${metricKey}', 'inflationRate', this.value)"
               class="${inputCls}">
      </div>
      <p class="text-[10px] text-dark-500 leading-snug">${t('proj.trend.inflation_hint') || 'La tendencia parte del último valor registrado y crece por interés compuesto mensual.'}</p>
    </div>`;

  return `
    <div class="flex-1 min-w-[230px] space-y-3">
      <div class="flex items-center gap-2">
        <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background:${color}"></span>
        <span class="text-xs font-semibold text-dark-200 uppercase tracking-wide">${sectionLabel}</span>
      </div>
      <div class="flex gap-1">
        ${modeBtn('linear',    'Regresión lineal')}
        ${modeBtn('inflation', 'Inflación')}
      </div>
      ${linearBlock}
      ${inflationBlock}
    </div>`;
}

function _buildTrendPanel() {
  const open  = _projState.trendPanelOpen;
  const arrow = open ? '▲' : '▼';
  const title = t('proj.trend.panel_title') || 'Línea de tendencia';

  const header = `
    <button onclick="Projections._toggleTrendPanel()"
            class="w-full flex items-center justify-between px-4 py-3 text-xs text-dark-400 hover:text-dark-200 transition-colors">
      <span class="font-medium uppercase tracking-wide">${title}</span>
      <span class="text-dark-500">${arrow}</span>
    </button>`;

  if (!open) {
    return `<div class="bg-dark-800 border border-dark-600 rounded-xl">${header}</div>`;
  }

  const body = `
    <div class="border-t border-dark-600 px-4 py-4 flex flex-wrap gap-8">
      ${_buildTrendSection('income',   t('proj.trend.section_income')   || 'Ingresos', PROJ_COLORS.income)}
      ${_buildTrendSection('expenses', t('proj.trend.section_expenses') || 'Gastos',   PROJ_COLORS.expenses)}
    </div>`;

  return `<div class="bg-dark-800 border border-dark-600 rounded-xl">${header}${body}</div>`;
}

function _renderTrendPanel() {
  const el = document.getElementById('proj-trend-panel');
  if (el) el.innerHTML = _buildTrendPanel();
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

      <!-- Trend settings panel (income & expenses only) -->
      <div id="proj-trend-panel"></div>

      <!-- Health summary -->
      <div id="proj-health-summary"></div>

      <!-- Series table -->
      <div class="bg-dark-800 border border-dark-600 rounded-xl p-4">
        <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('proj.series.table_title')}</h3>
        <div id="proj-series-table"><div class="spinner">⏳</div></div>
      </div>

      <!-- Charts grid -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-5" id="proj-charts-grid">
        <div class="bg-dark-800 border border-dark-600 rounded-xl p-4 lg:col-span-2">
          <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('proj.chart.combined')}</h3>
          <canvas id="ch-proj-combined" height="220"></canvas>
        </div>
      </div>

    </div></div>`;
}

// ── Preferences persistence ───────────────────────────────────────────────────

function _saveProjPrefs(patch) {
  API.put('/settings/preferences', patch).catch(() => {});
}

async function _loadProjPrefs() {
  try {
    const prefs = await API.get('/settings/preferences');
    if (typeof prefs.proj_horizon === 'number') _projState.horizon = prefs.proj_horizon;
    if (typeof prefs.proj_history_months === 'number') _projState.historyMonths = prefs.proj_history_months;
    if (prefs.proj_trend_income   && typeof prefs.proj_trend_income   === 'object')
      Object.assign(_projState.trendSettings.income,   prefs.proj_trend_income);
    if (prefs.proj_trend_expenses && typeof prefs.proj_trend_expenses === 'object')
      Object.assign(_projState.trendSettings.expenses, prefs.proj_trend_expenses);
  } catch {}
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
    _renderHealthSummary();
    _renderSeriesTable();
    _renderCharts();
  } catch (e) {
    const tbl = document.getElementById('proj-series-table');
    if (tbl) tbl.innerHTML = `<div class="empty text-pasivo text-xs">Error: ${escapeHtml(e.message)}</div>`;
  }
}

// ── Chart rendering ───────────────────────────────────────────────────────────

function _makeChartOptions() {
  return {
    ..._projDefaults,
    responsive: true,
    plugins: { ..._projDefaults.plugins, legend: { ..._projDefaults.plugins.legend } },
    scales: {
      x: { ..._projDefaults.scales.x, ticks: { ..._projDefaults.scales.x.ticks, maxTicksLimit: 24, maxRotation: 45 } },
      y: _projDefaults.scales.y,
    },
  };
}

function _renderCharts() {
  _destroyProjCharts();
  const { projData } = _projState;
  if (!projData) return;

  const histMonths = projData.historical_months || [];
  const projMonths = projData.projected_months  || [];
  const allLabels  = [...histMonths, ...projMonths];

  // ── Income & Expenses (user-configurable trend mode) ──────────────────────
  const incomeResult   = _buildProjectionDatasets('income',   histMonths, projMonths, projData, PROJ_COLORS.income,   true, _projState.trendSettings.income);
  const expensesResult = _buildProjectionDatasets('expenses', histMonths, projMonths, projData, PROJ_COLORS.expenses, true, _projState.trendSettings.expenses);

  const incProj  = incomeResult._raw.projFull;
  const expProj  = expensesResult._raw.projFull;
  const incTrend = incomeResult._raw.trendData;
  const expTrend = expensesResult._raw.trendData;

  const incHistMap = {}, expHistMap = {}, assetsHistMap = {};
  (projData.historical.income   || []).forEach(p => { incHistMap[p.month]    = p.value; });
  (projData.historical.expenses || []).forEach(p => { expHistMap[p.month]    = p.value; });
  (projData.historical.assets   || []).forEach(p => { assetsHistMap[p.month] = p.value; });

  // Savings (monthly)
  const savingsTrendData = (incTrend && expTrend)
    ? allLabels.map((_, i) => {
        const inc = incTrend[i], exp = expTrend[i];
        return (inc != null && exp != null) ? Math.round((inc - exp) * 100) / 100 : null;
      })
    : null;

  const savingsProjFull = allLabels.map((_, i) => {
    const inc = incProj[i], exp = expProj[i];
    return (inc != null && exp != null) ? Math.round((inc - exp) * 100) / 100 : null;
  });

  // Assets = current balance + cumulative projected savings
  const currentAssets = projData.current_balances?.total_assets ?? 0;
  let cumSavings = 0;
  const assetsProjFull = allLabels.map((_, i) => {
    const s = savingsProjFull[i];
    if (s == null) return null;
    cumSavings += s;
    return Math.round((currentAssets + cumSavings) * 100) / 100;
  });

  // ── Combined chart: income/expenses/savings (left) + assets (right) ───────
  const combinedCanvas = document.getElementById('ch-proj-combined');
  if (combinedCanvas) {
    // _h: true marks a dataset as hidden from the legend
    const pickScatterData = (result, pointStyle = null) => (
      result.datasets.find(ds => ds.type === 'scatter' && (ds.pointStyle || null) === pointStyle)?.data || []
    );

    const scatter = (color, data, yId) => ({
      _h: true,
      type: 'scatter',
      data,
      parsing: false,
      pointRadius: 3,
      pointBackgroundColor: color,
      pointBorderColor: color,
      showLine: false,
      order: 4,
      yAxisID: yId,
    });

    const outlierMarks = (label, data, yId) => ({
      _h: true,
      label: `${label} (${t('proj.chart.outliers')})`,
      type: 'scatter',
      data,
      parsing: false,
      pointStyle: 'crossRot',
      pointRadius: 7,
      pointHoverRadius: 7,
      pointBorderWidth: 2.5,
      pointBackgroundColor: 'transparent',
      pointBorderColor: '#ef4444',
      showLine: false,
      order: 5,
      yAxisID: yId,
    });

    const trendLine = (color, data, yId) => ({
      _h: true,
      type: 'line',
      data,
      borderColor: color + '55',
      backgroundColor: 'transparent',
      borderWidth: 1.5,
      borderDash: [6, 4],
      pointRadius: 0,
      fill: false,
      tension: 0,
      order: 3,
      spanGaps: false,
      yAxisID: yId,
    });

    const projLine = (label, color, data, yId) => ({
      label,
      type: 'line',
      data,
      borderColor: color,
      backgroundColor: color + '14',
      borderWidth: 2,
      pointRadius: 2,
      fill: 'origin',
      tension: 0.3,
      order: yId === 'y2' ? 0 : 1,
      spanGaps: false,
      yAxisID: yId,
    });

    const incScatter  = pickScatterData(incomeResult);
    const incOutliers = pickScatterData(incomeResult, 'crossRot');
    const expScatter  = pickScatterData(expensesResult);
    const expOutliers = pickScatterData(expensesResult, 'crossRot');
    const savScatter  = histMonths.filter(m => incHistMap[m]  != null && expHistMap[m] != null)
                                  .map(m => ({ x: m, y: Math.round((incHistMap[m] - expHistMap[m]) * 100) / 100 }));
    const assetScatter = histMonths.filter(m => assetsHistMap[m] != null).map(m => ({ x: m, y: assetsHistMap[m] }));

    const datasets = [
      scatter(PROJ_COLORS.income,   incScatter,   'y'),
      ...(incOutliers.length ? [outlierMarks(t('proj.chart.income'), incOutliers, 'y')] : []),
      ...(incTrend ? [trendLine(PROJ_COLORS.income,   incTrend,         'y')] : []),
      projLine(t('proj.chart.income'),   PROJ_COLORS.income,   incProj,         'y'),

      scatter(PROJ_COLORS.expenses, expScatter,   'y'),
      ...(expOutliers.length ? [outlierMarks(t('proj.chart.expenses'), expOutliers, 'y')] : []),
      ...(expTrend ? [trendLine(PROJ_COLORS.expenses, expTrend,         'y')] : []),
      projLine(t('proj.chart.expenses'), PROJ_COLORS.expenses, expProj,         'y'),

      scatter(PROJ_COLORS.savings,  savScatter,   'y'),
      ...(savingsTrendData ? [trendLine(PROJ_COLORS.savings, savingsTrendData, 'y')] : []),
      projLine(t('proj.chart.savings'),  PROJ_COLORS.savings,  savingsProjFull, 'y'),

      scatter(PROJ_COLORS.assets,   assetScatter, 'y2'),
      projLine(t('proj.chart.assets'),   PROJ_COLORS.assets,   assetsProjFull,  'y2'),
    ];

    _projCharts['ch-proj-combined'] = new Chart(combinedCanvas, {
      type: 'line',
      data: { labels: allLabels, datasets },
      options: {
        ..._projDefaults,
        responsive: true,
        plugins: {
          ..._projDefaults.plugins,
          legend: {
            display: true,
            labels: {
              color: '#8b949e',
              font: { size: 11 },
              filter: (item, data) => !data.datasets[item.datasetIndex]._h,
            },
          },
        },
        scales: {
          x: {
            ..._projDefaults.scales.x,
            ticks: { ..._projDefaults.scales.x.ticks, maxTicksLimit: 24, maxRotation: 45 },
          },
          y: {
            ..._projDefaults.scales.y,
            type: 'linear',
            position: 'left',
            title: {
              display: true,
              text: t('proj.chart.y_monthly'),
              color: '#8b949e',
              font: { size: 10 },
            },
          },
          y2: {
            type: 'linear',
            position: 'right',
            grid: { drawOnChartArea: false },
            ticks: {
              color: PROJ_COLORS.assets,
              font: { size: 9 },
              callback: v => '$ ' + (Math.abs(v) >= 1000 ? (v / 1000).toFixed(0) + 'k' : v.toFixed(0)),
            },
            title: {
              display: true,
              text: t('proj.chart.y_cumulative'),
              color: PROJ_COLORS.assets,
              font: { size: 10 },
            },
          },
        },
      },
    });
  }

}

// ── Public API ────────────────────────────────────────────────────────────────

const Projections = {

  async render() {
    _destroyProjCharts();
    await _loadProjPrefs();
    const main = document.getElementById('main');
    main.innerHTML = _buildPageShell();
    _renderTrendPanel();
    _setActiveBtn('proj-horizon-btns', _projState.horizon);
    _setActiveBtn('proj-history-btns', _projState.historyMonths);
    await _loadData();
  },

  _onHorizonChange(months) {
    _projState.horizon = months;
    _setActiveBtn('proj-horizon-btns', months);
    _saveProjPrefs({ proj_horizon: months });
    _loadData();
  },

  _onHistoryChange(months) {
    _projState.historyMonths = months;
    _setActiveBtn('proj-history-btns', months);
    _saveProjPrefs({ proj_history_months: months });
    _loadData();
  },

  // ── Trend panel handlers ────────────────────────────────────────────────────

  _toggleTrendPanel() {
    _projState.trendPanelOpen = !_projState.trendPanelOpen;
    _renderTrendPanel();
  },

  _onTrendMode(metricKey, mode) {
    _projState.trendSettings[metricKey].mode = mode;
    // When switching to inflation, pre-fill base with the last known value
    // so the user sees the correct default without having to type it.
    if (mode === 'inflation' && _projState.trendSettings[metricKey].inflationBase === '') {
      const lastVal = _getLastKnownValue(metricKey, _projState.projData);
      if (lastVal !== null) {
        _projState.trendSettings[metricKey].inflationBase = String(Math.round(lastVal * 100) / 100);
      }
    }
    _saveProjPrefs({ [`proj_trend_${metricKey}`]: _projState.trendSettings[metricKey] });
    _renderTrendPanel();
    _renderCharts();
  },

  _onTrendSetting(metricKey, field, value) {
    const normalized = _normalizeTrendSettingValue(field, value);
    if (!normalized.isValid) {
      Toast.show(t('msg.invalid_money_input'), 'err');
      _renderTrendPanel();
      return;
    }

    _projState.trendSettings[metricKey][field] = normalized.normalized;
    _saveProjPrefs({ [`proj_trend_${metricKey}`]: _projState.trendSettings[metricKey] });
    _renderTrendPanel();
    _renderCharts();
  },

  // ── Series dialog ───────────────────────────────────────────────────────────

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
            T.input('ps-amount', { type: 'text', val: existing?.monthly_amount ?? '', ph: '0.00', inputmode: 'decimal' }))
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
        const amountState = parseMoneyInput(document.getElementById('ps-amount').value);
        const amount = amountState.isValid ? amountState.value : Number.NaN;

        if (!name) { Toast.show(t('msg.invalid_value'), 'err'); return false; }
        if (!start) { Toast.show(t('msg.invalid_value'), 'err'); return false; }
        if (isNaN(months) || months < 1) { Toast.show(t('msg.invalid_value'), 'err'); return false; }
        if (amountState.isEmpty || !amountState.isValid || amount <= 0) { Toast.show(t('msg.invalid_money_input'), 'err'); return false; }

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
