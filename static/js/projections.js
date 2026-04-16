/* ── projections.js — Financial Projections view ── */

'use strict';

let _projCharts = {};

let _projState = {
  horizon: 12,
  historyMonths: 12,
  series: [],
  projData: null,
  requestSeq: 0,
  trendPanelOpen: false,
  investmentOverrides: {
    interestPct: null,
    contributionPct: null,
    debounceId: null,
  },
  trendSettings: {
    income:   { mode: 'linear', minVal: '', maxVal: '', inflationBase: '', inflationRate: '' },
    expenses: { mode: 'linear', minVal: '', maxVal: '', inflationBase: '', inflationRate: '' },
    investments: { lookbackMonths: null, includeCurrentMonth: false, excludeOutliers: true, outlierK: 1.5 },
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
  investments: '#ff9800',
  nonInvestedAssets: '#26a69a',
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
  if (series.enabled === false) return false;
  const start = series.start_date.slice(0, 7); // YYYY-MM
  const { y: sy, mo: sm } = _parseMonth(start);
  const { y: my, mo: mm } = _parseMonth(monthStr);
  const idx = (my - sy) * 12 + (mm - sm);
  return idx >= 0 && idx < series.months;
}

function _hasActiveSeries() {
  return _projState.series.some(series => series.enabled !== false);
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

function _roundSliderValue(value) {
  return Math.round(Number(value) * 100) / 100;
}

function _clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function _fmtSliderPct(value) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  return `${Number(value).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`;
}

function _updateInvestmentSliderValue(field, value) {
  const valueEl = document.getElementById(`proj-slider-${field}-value`);
  if (valueEl) valueEl.textContent = _fmtSliderPct(value);

  const sliderEl = document.getElementById(`proj-slider-${field}`);
  if (sliderEl) sliderEl.value = value;

  const inputEl = document.getElementById(`proj-slider-${field}-input`);
  if (inputEl) inputEl.value = _roundSliderValue(value);
}

function _getInvestmentSliderMeta(field) {
  const model = _projState.projData?.investment_model;
  if (field === 'interestPct') {
    return {
      slider: model?.interest_slider || { min: 0, max: 1, step: 0.01 },
      fallback: _projState.investmentOverrides.interestPct ?? model?.default_interest_percent ?? 0,
    };
  }
  return {
    slider: model?.contribution_slider || { min: 0, max: 1, step: 0.01 },
    fallback: _projState.investmentOverrides.contributionPct ?? model?.default_contribution_percent ?? 0,
  };
}

function _scheduleInvestmentRecalc() {
  if (_projState.investmentOverrides.debounceId) {
    window.clearTimeout(_projState.investmentOverrides.debounceId);
  }
  _projState.investmentOverrides.debounceId = window.setTimeout(() => {
    _loadData();
  }, 180);
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
    const enabled = s.enabled !== false;
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

    return `<tr class="border-t border-dark-700 hover:bg-dark-700/30 ${enabled ? '' : 'opacity-60'}">
      <td class="sticky left-0 z-10 bg-dark-800 px-3 py-2 min-w-[180px]">
        <div class="flex items-center gap-2">
          <span class="text-sm text-dark-200 truncate max-w-[120px]" title="${escapeHtml(s.name)}">${escapeHtml(s.name)}</span>
          ${typeBadge}
        </div>
      </td>
      <td class="px-2 py-1 text-right">
        <div class="flex items-center justify-end gap-1">
          <label class="inline-flex items-center gap-1.5 text-[11px] text-dark-400 mr-1" title="${escapeHtml(t('proj.series.enabled'))}">
            <input type="checkbox"
                   class="h-3.5 w-3.5 rounded border-dark-500 bg-dark-700 text-blue-500 focus:ring-blue-500/40"
                   ${enabled ? 'checked' : ''}
                   onchange="Projections.toggleSeriesEnabled(${s.id}, this.checked)">
            <span>${t('proj.series.enabled_short')}</span>
          </label>
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

function _roundProjectionValue(value, digits = 4) {
  if (value == null || Number.isNaN(Number(value))) return 0;
  const factor = 10 ** digits;
  return Math.round(Number(value) * factor) / factor;
}

function _safeProjectionRatio(numerator, denominator) {
  const num = Number(numerator);
  const den = Number(denominator);
  if (!Number.isFinite(num) || !Number.isFinite(den) || Math.abs(den) < 0.0000001) {
    return null;
  }
  return num / den;
}

function _projectedValuesFromSeries(series, nHist, projMonths, fallback = []) {
  return projMonths.map((_, index) => {
    const value = Array.isArray(series) ? series[nHist + index] : undefined;
    const fallbackValue = Array.isArray(fallback) ? fallback[index] : 0;
    return _roundProjectionValue(value ?? fallbackValue);
  });
}

function _buildProjectedAssetSeries(
  currentAssets,
  projectedSavings,
  projectedReturns,
) {
  // NOTE: contributions are intentionally excluded here.
  // A periodic manual contribution is an internal transfer from
  // non-investment assets to investment assets.  It does NOT change
  // total assets — it only affects the split between the two buckets
  // and, indirectly, the interest earned on the larger investment base.
  let running = Number(currentAssets || 0);
  return projectedSavings.map((savings, index) => {
    running = _roundProjectionValue(
      running
      + Number(savings || 0)
      + Number(projectedReturns[index] || 0)
    );
    return running;
  });
}

function _buildProjectedInvestmentSeries(
  currentInvestments,
  projectedReturns,
  projectedContributions,
) {
  let running = Number(currentInvestments || 0);
  return projectedReturns.map((interest, index) => {
    running = _roundProjectionValue(
      running
      + Number(interest || 0)
      + Number(projectedContributions[index] || 0)
    );
    return running;
  });
}

function _deriveProjectionDisplayState() {
  const projData = _projState.projData;
  if (!projData) return null;

  const histMonths = projData.historical_months || [];
  const projMonths = projData.projected_months || [];
  const allLabels = [...histMonths, ...projMonths];
  const nHist = histMonths.length;

  const incomeResult = _buildProjectionDatasets(
    'income',
    histMonths,
    projMonths,
    projData,
    PROJ_COLORS.income,
    true,
    _projState.trendSettings.income
  );
  const expensesResult = _buildProjectionDatasets(
    'expenses',
    histMonths,
    projMonths,
    projData,
    PROJ_COLORS.expenses,
    true,
    _projState.trendSettings.expenses
  );

  const incProj = incomeResult._raw.projFull || [];
  const expProj = expensesResult._raw.projFull || [];
  const incTrend = incomeResult._raw.trendData || null;
  const expTrend = expensesResult._raw.trendData || null;

  const baselineIncomeProjected = _projectedValuesFromSeries(
    incTrend,
    nHist,
    projMonths,
    projData.baseline_projection?.income || []
  );
  const baselineExpenseProjected = _projectedValuesFromSeries(
    expTrend,
    nHist,
    projMonths,
    projData.baseline_projection?.expenses || []
  );
  const scenarioIncomeProjected = _projectedValuesFromSeries(
    incProj,
    nHist,
    projMonths,
    projData.baseline_projection?.income || []
  );
  const scenarioExpenseProjected = _projectedValuesFromSeries(
    expProj,
    nHist,
    projMonths,
    projData.baseline_projection?.expenses || []
  );

  const baselineSavingsProjected = projMonths.map((_, index) =>
    _roundProjectionValue(
      Number(baselineIncomeProjected[index] || 0)
      - Number(baselineExpenseProjected[index] || 0)
    )
  );
  const scenarioSavingsProjected = projMonths.map((_, index) =>
    _roundProjectionValue(
      Number(scenarioIncomeProjected[index] || 0)
      - Number(scenarioExpenseProjected[index] || 0)
    )
  );

  const projectedReturns = (projData.investment_detail || [])
    .filter(row => row.is_projected)
    .map(row => _roundProjectionValue(row.interest_total || 0));
  const projectedContributions = (projData.investment_detail || [])
    .filter(row => row.is_projected)
    .map(row => _roundProjectionValue(row.manual_contribution || 0));

  const currentAssets = Number(projData.current_balances?.total_assets || 0);
  const currentInvestments = Number(projData.current_balances?.total_investments || 0);
  const hasActiveSeries = _hasActiveSeries();

  const baselineAssetsProjected = _buildProjectedAssetSeries(
    currentAssets,
    baselineSavingsProjected,
    projectedReturns,
  );
  const scenarioAssetsProjected = _buildProjectedAssetSeries(
    currentAssets,
    scenarioSavingsProjected,
    projectedReturns,
  );
  const baselineInvestmentsProjected = (projData.baseline_projection?.investments || [])
    .map(value => _roundProjectionValue(value));
  const scenarioInvestmentsProjected = _buildProjectedInvestmentSeries(
    currentInvestments,
    projectedReturns,
    projectedContributions,
  );
  const baselineNonInvestedAssetsProjected = baselineAssetsProjected.map((value, index) =>
    _roundProjectionValue(Number(value || 0) - Number(baselineInvestmentsProjected[index] || 0))
  );
  const scenarioNonInvestedAssetsProjected = scenarioAssetsProjected.map((value, index) =>
    _roundProjectionValue(Number(value || 0) - Number(scenarioInvestmentsProjected[index] || 0))
  );

  return {
    projData,
    histMonths,
    projMonths,
    allLabels,
    nHist,
    incomeResult,
    expensesResult,
    incProj,
    expProj,
    incTrend,
    expTrend,
    baselineIncomeProjected,
    baselineExpenseProjected,
    scenarioIncomeProjected,
    scenarioExpenseProjected,
    baselineSavingsProjected,
    scenarioSavingsProjected,
    projectedReturns,
    projectedContributions,
    baselineAssetsProjected,
    scenarioAssetsProjected,
    baselineInvestmentsProjected,
    scenarioInvestmentsProjected,
    baselineNonInvestedAssetsProjected,
    scenarioNonInvestedAssetsProjected,
    hasActiveSeries,
  };
}

function _buildProjectedHealthPoint(
  month,
  assets,
  liabilities,
  currentAssets,
  quickAssets,
  currentLiabilities,
  essentialExpense
) {
  const currentRatio = _safeProjectionRatio(currentAssets, currentLiabilities);
  const quickRatio = _safeProjectionRatio(quickAssets, currentLiabilities);
  const runwayMonths = essentialExpense > 0
    ? _safeProjectionRatio(quickAssets, essentialExpense)
    : null;

  return {
    month,
    assets: _roundProjectionValue(assets),
    liabilities: _roundProjectionValue(liabilities),
    net_worth: _roundProjectionValue(Number(assets || 0) - Number(liabilities || 0)),
    current_assets: _roundProjectionValue(currentAssets),
    quick_assets: _roundProjectionValue(quickAssets),
    current_liabilities: _roundProjectionValue(currentLiabilities),
    current_ratio: currentRatio == null ? null : _roundProjectionValue(currentRatio),
    quick_ratio: quickRatio == null ? null : _roundProjectionValue(quickRatio),
    monthly_essential_expense: _roundProjectionValue(essentialExpense),
    runway_months: runwayMonths == null ? null : _roundProjectionValue(runwayMonths),
  };
}

function _deriveDisplayedHealthSummary(displayState) {
  const projData = _projState.projData;
  const backendHealth = projData?.health;
  if (!projData || !backendHealth) return null;

  const currentBackend = backendHealth.current || {};
  const assumptions = backendHealth.assumptions || {};
  const currentBalances = projData.current_balances || {};
  const currentAssetsTotal = Number(currentBalances.total_assets || 0);
  const currentLiabilitiesTotal = Number(currentBalances.total_liabilities || 0);
  const currentInvestments = Number(currentBalances.total_investments || 0);
  const currentNonInvestmentAssets = currentAssetsTotal - currentInvestments;
  const currentAssetsBucket = Number(currentBackend.current_assets || 0);
  const currentQuickAssets = Number(currentBackend.quick_assets || 0);
  const currentLiabilityShare = Number(assumptions.current_liability_share || 0);
  const essentialExpenseShare = Number(assumptions.essential_expense_share || 0);
  const projectedInvestments = projData.baseline_projection?.investments || [];
  const baselineLiabilities = projData.baseline_projection?.liabilities || [];
  const scenarioLiabilityAdjustments = projData.series_adjustment?.liabilities || [];
  const scenarioLiabilities = displayState.projMonths.map((_, index) =>
    _roundProjectionValue(
      Number(baselineLiabilities[index] || 0)
      + Number(scenarioLiabilityAdjustments[index] || 0)
    )
  );

  const current = {
    ...currentBackend,
    assets: _roundProjectionValue(currentAssetsTotal),
    liabilities: _roundProjectionValue(currentLiabilitiesTotal),
    net_worth: _roundProjectionValue(currentBackend.net_worth),
    current_assets: _roundProjectionValue(currentAssetsBucket),
    quick_assets: _roundProjectionValue(currentQuickAssets),
    current_liabilities: _roundProjectionValue(currentBackend.current_liabilities || 0),
    monthly_essential_expense: _roundProjectionValue(currentBackend.monthly_essential_expense || 0),
  };

  const buildEndPoint = (assetsSeries, expenseSeries, liabilitiesSeries) => {
    if (!displayState.projMonths.length) return current;

    const lastIndex = displayState.projMonths.length - 1;
    const totalAssets = Number(assetsSeries[lastIndex] || currentAssetsTotal);
    const totalLiabilities = Number(liabilitiesSeries[lastIndex] || 0);
    const projectedInvestmentsEnd = Number(projectedInvestments[lastIndex] || currentInvestments);
    const projectedNonInvestmentAssets = totalAssets - projectedInvestmentsEnd;
    const projectedNonInvestmentGrowth = Math.max(
      0,
      projectedNonInvestmentAssets - currentNonInvestmentAssets
    );
    const currentAssetsEnd = currentAssetsBucket + projectedNonInvestmentGrowth;
    const quickAssetsEnd = currentQuickAssets + projectedNonInvestmentGrowth;
    const currentLiabilitiesEnd = totalLiabilities * currentLiabilityShare;
    const essentialExpenseEnd = Math.max(
      0,
      Number(expenseSeries[lastIndex] || 0) * essentialExpenseShare
    );

    return _buildProjectedHealthPoint(
      displayState.projMonths[lastIndex],
      totalAssets,
      totalLiabilities,
      currentAssetsEnd,
      quickAssetsEnd,
      currentLiabilitiesEnd,
      essentialExpenseEnd
    );
  };

  const baseline = buildEndPoint(
    displayState.baselineAssetsProjected,
    displayState.baselineExpenseProjected,
    baselineLiabilities
  );
  const scenario = buildEndPoint(
    displayState.scenarioAssetsProjected,
    displayState.scenarioExpenseProjected,
    scenarioLiabilities
  );

  const deltaValue = (scenarioValue, baselineValue) => (
    scenarioValue == null || baselineValue == null
      ? null
      : _roundProjectionValue(Number(scenarioValue) - Number(baselineValue))
  );

  return {
    current,
    baseline_end: baseline,
    scenario_end: scenario,
    delta_end: {
      month: displayState.projMonths[displayState.projMonths.length - 1] || current.month,
      net_worth: deltaValue(scenario.net_worth, baseline.net_worth),
      runway_months: deltaValue(scenario.runway_months, baseline.runway_months),
      current_ratio: deltaValue(scenario.current_ratio, baseline.current_ratio),
      quick_ratio: deltaValue(scenario.quick_ratio, baseline.quick_ratio),
    },
    assumptions,
  };
}

function _renderHealthSummary() {
  const container = document.getElementById('proj-health-summary');
  if (!container) return;

  const displayState = _deriveProjectionDisplayState();
  const health = displayState
    ? _deriveDisplayedHealthSummary(displayState)
    : _projState.projData?.health;
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

function _buildInvestmentTrendSection() {
  const s = _projState.trendSettings.investments;
  const model = _projState.projData?.investment_model;
  const color = PROJ_COLORS.investments;
  const inputCls = 'w-full bg-dark-700 border border-dark-600 rounded-lg text-dark-200 text-xs px-2 py-1.5 focus:outline-none focus:border-blue-500';
  const labelCls = 'text-[11px] text-dark-400 w-24 shrink-0';

  // If no investment accounts detected, show a short message
  if (model && !model.enabled) {
    return `
      <div class="flex-1 min-w-[230px] space-y-3">
        <div class="flex items-center gap-2">
          <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background:${color}"></span>
          <span class="text-xs font-semibold text-dark-200 uppercase tracking-wide">${t('proj.trend.section_investments')}</span>
        </div>
        <p class="text-[10px] text-dark-500 leading-snug">${t('proj.trend.inv_no_data')}</p>
      </div>`;
  }

  const includeCurrentChecked = s.includeCurrentMonth === true ? 'checked' : '';
  const outlierChecked = s.excludeOutliers !== false ? 'checked' : '';

  // Model metadata
  let modelInfo = '';
  if (model) {
    const yieldPct = (model.yield_rate * 100).toFixed(4);
    const contribRatePct = (model.contribution_rate * 100).toFixed(4);
    const warnings = (model.warnings || []).map(w => {
      const key = `proj.trend.inv_warning_${w}`;
      return `<div class="text-[10px] text-yellow-500 mt-1">⚠ ${t(key)}</div>`;
    }).join('');
    modelInfo = `
      <div class="mt-3 space-y-1 text-[10px] text-dark-400 border-t border-dark-700 pt-2">
        <div>${t('proj.trend.inv_yield')}: <span class="text-dark-200">${yieldPct}%</span>
          <span class="text-dark-500">(${model.sample_count} ${t('proj.trend.inv_samples')}${model.yield_excluded > 0 ? `, ${model.yield_excluded} ${t('proj.trend.inv_excluded')}` : ''})</span></div>
        <div>${t('proj.trend.inv_contribution_rate')}: <span class="text-dark-200">${contribRatePct}%</span>
          <span class="text-dark-500">(${model.contrib_sample_count} ${t('proj.trend.inv_contrib_samples')}${model.contrib_excluded > 0 ? `, ${model.contrib_excluded} ${t('proj.trend.inv_excluded')}` : ''})</span></div>
        ${warnings}
      </div>`;
  }

  return `
    <div class="flex-1 min-w-[230px] space-y-3">
      <div class="flex items-center gap-2">
        <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background:${color}"></span>
        <span class="text-xs font-semibold text-dark-200 uppercase tracking-wide">${t('proj.trend.section_investments')}</span>
      </div>
      <div class="text-[10px] text-dark-500 uppercase tracking-wide">${t('proj.trend.mode_compound')}</div>
      <div class="space-y-2">
        <div class="flex items-center gap-2">
          <label class="${labelCls}">${t('proj.trend.lookback')}</label>
          <input type="number" min="3" max="60" value="${s.lookbackMonths || ''}" inputmode="numeric"
                 placeholder="${_projState.historyMonths}"
                 onchange="Projections._onInvSetting('lookbackMonths', this.value)"
                 class="${inputCls}">
        </div>
        <div class="flex items-center gap-2">
          <label class="${labelCls}">${t('proj.trend.include_current_month')}</label>
          <input type="checkbox" ${includeCurrentChecked}
                 onchange="Projections._onInvSetting('includeCurrentMonth', this.checked)"
                 class="accent-blue-500">
        </div>
        <div class="flex items-center gap-2">
          <label class="${labelCls}">${t('proj.trend.outlier_toggle')}</label>
          <input type="checkbox" ${outlierChecked}
                 onchange="Projections._onInvSetting('excludeOutliers', this.checked)"
                 class="accent-blue-500">
        </div>
        <div class="flex items-center gap-2${s.excludeOutliers !== false ? '' : ' opacity-50'}">
          <label class="${labelCls}">${t('proj.trend.outlier_k')}</label>
          <input type="number" min="0.5" max="5" step="0.1" value="${s.outlierK || 1.5}" inputmode="decimal"
                 ${s.excludeOutliers !== false ? '' : 'disabled'}
                 onchange="Projections._onInvSetting('outlierK', this.value)"
                 class="${inputCls}">
        </div>
        <p class="text-[10px] text-dark-500 leading-snug">${t('proj.trend.compound_hint')}</p>
      </div>
      ${modelInfo}
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
      ${_buildInvestmentTrendSection()}
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

      <!-- Trend settings panel (income, expenses & investments) -->
      <div id="proj-trend-panel"></div>

      <!-- Series table -->
      <div class="bg-dark-800 border border-dark-600 rounded-xl p-4">
        <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('proj.series.table_title')}</h3>
        <div id="proj-series-table"><div class="spinner">⏳</div></div>
      </div>

      <!-- Charts grid -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-5" id="proj-charts-grid">
        <div class="bg-dark-800 border border-dark-600 rounded-xl p-4 lg:col-span-2">
          <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3" id="proj-chart-combined-title">${t('proj.chart.combined')}</h3>
          <canvas id="ch-proj-combined" height="220"></canvas>
        </div>
      </div>

      <div id="proj-investment-sliders" class="bg-dark-800 border border-dark-600 rounded-xl p-4" style="display:none">
        <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('proj.slider.title')}</h3>
        <div id="proj-investment-sliders-body"></div>
      </div>

      <!-- Investment detail table -->
      <div id="proj-investment-detail" class="bg-dark-800 border border-dark-600 rounded-xl p-4" style="display:none">
        <h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('proj.detail.table_title')}</h3>
        <div id="proj-investment-detail-body"></div>
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
    if (prefs.proj_trend_investments && typeof prefs.proj_trend_investments === 'object')
      Object.assign(_projState.trendSettings.investments, prefs.proj_trend_investments);
    delete _projState.trendSettings.investments.statistic;
  } catch {}
}

// ── Data loading ──────────────────────────────────────────────────────────────

async function _loadData() {
  const requestSeq = ++_projState.requestSeq;
  try {
    const income = _projState.trendSettings.income;
    const inv = _projState.trendSettings.investments;
    const overrides = _projState.investmentOverrides;
    let projUrl = `/reports/projections?horizon=${_projState.horizon}&history_months=${_projState.historyMonths}`;
    projUrl += `&income_trend_mode=${encodeURIComponent(income.mode || 'linear')}`;
    const incomeMin = income.minVal !== '' ? _parseTrendSettingNumber(income.minVal, 'minVal') : null;
    const incomeMax = income.maxVal !== '' ? _parseTrendSettingNumber(income.maxVal, 'maxVal') : null;
    const incomeInflationBase = income.inflationBase !== '' ? _parseTrendSettingNumber(income.inflationBase, 'inflationBase') : null;
    const incomeInflationRate = income.inflationRate !== '' ? _parseTrendSettingNumber(income.inflationRate, 'inflationRate') : null;
    if (incomeMin != null) projUrl += `&income_trend_min=${encodeURIComponent(incomeMin)}`;
    if (incomeMax != null) projUrl += `&income_trend_max=${encodeURIComponent(incomeMax)}`;
    if (incomeInflationBase != null) projUrl += `&income_inflation_base=${encodeURIComponent(incomeInflationBase)}`;
    if (incomeInflationRate != null) projUrl += `&income_inflation_rate=${encodeURIComponent(incomeInflationRate)}`;
    const expenses = _projState.trendSettings.expenses;
    projUrl += `&expense_trend_mode=${encodeURIComponent(expenses.mode || 'linear')}`;
    const expenseMin = expenses.minVal !== '' ? _parseTrendSettingNumber(expenses.minVal, 'minVal') : null;
    const expenseMax = expenses.maxVal !== '' ? _parseTrendSettingNumber(expenses.maxVal, 'maxVal') : null;
    const expenseInflationBase = expenses.inflationBase !== '' ? _parseTrendSettingNumber(expenses.inflationBase, 'inflationBase') : null;
    const expenseInflationRate = expenses.inflationRate !== '' ? _parseTrendSettingNumber(expenses.inflationRate, 'inflationRate') : null;
    if (expenseMin != null) projUrl += `&expense_trend_min=${encodeURIComponent(expenseMin)}`;
    if (expenseMax != null) projUrl += `&expense_trend_max=${encodeURIComponent(expenseMax)}`;
    if (expenseInflationBase != null) projUrl += `&expense_inflation_base=${encodeURIComponent(expenseInflationBase)}`;
    if (expenseInflationRate != null) projUrl += `&expense_inflation_rate=${encodeURIComponent(expenseInflationRate)}`;
    if (inv.lookbackMonths != null) projUrl += `&investment_lookback_months=${inv.lookbackMonths}`;
    projUrl += `&investment_include_current_month=${inv.includeCurrentMonth === true}`;
    projUrl += `&investment_exclude_outliers=${inv.excludeOutliers !== false}`;
    projUrl += `&investment_outlier_k=${inv.outlierK || 1.5}`;
    if (overrides.interestPct != null) projUrl += `&investment_interest_pct_override=${encodeURIComponent(overrides.interestPct)}`;
    if (overrides.contributionPct != null) projUrl += `&investment_contribution_pct_override=${encodeURIComponent(overrides.contributionPct)}`;
    const [series, projData] = await Promise.all([
      API.get('/projections/series'),
      API.get(projUrl),
    ]);
    if (requestSeq !== _projState.requestSeq) return;
    _projState.series = series;
    _projState.projData = projData;
    _renderHealthSummary();
    _renderSeriesTable();
    _renderCharts();
    _renderInvestmentSliders();
    _renderInvestmentDetailTable();
  } catch (e) {
    if (requestSeq !== _projState.requestSeq) return;
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
  const displayState = _deriveProjectionDisplayState();
  const hasActiveSeries = Boolean(displayState?.hasActiveSeries);

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

  // Assets must stay aligned with the displayed savings line. Income/expense
  // trend settings can be adjusted in the frontend, so the charted asset curve
  // needs to evolve from the previous projected assets plus displayed savings
  // plus projected investment return for each future month.
  const currentAssets = projData.current_balances?.total_assets ?? 0;
  const n_hist = histMonths.length;
  const projectedReturns = (projData.investment_detail || [])
    .filter(row => row.is_projected)
    .map(row => Number(row.interest_total || 0));
  const projectedContributions = (projData.investment_detail || [])
    .filter(row => row.is_projected)
    .map(row => Number(row.manual_contribution || 0));
  let projectedAssetsRunning = currentAssets;
  const assetsProjFull = allLabels.map((_, i) => {
    const projIdx = i - n_hist;
    if (projIdx >= 0 && projIdx < projMonths.length) {
      const displayedSavings = savingsProjFull[i] ?? 0;
      const projectedReturn = projectedReturns[projIdx] ?? 0;
      projectedAssetsRunning += displayedSavings + projectedReturn;
      return Math.round(projectedAssetsRunning * 100) / 100;
    }
    return null;
  });

  // ── Combined chart: income/expenses/savings (left) + assets + investments (right) ───────
  const combinedCanvas = document.getElementById('ch-proj-combined');
  if (combinedCanvas) {
    // Update chart title based on whether investments are present
    const chartTitle = document.getElementById('proj-chart-combined-title');
    const invModel = projData.investment_model;
    if (chartTitle) {
      chartTitle.textContent = (invModel?.enabled) ? t('proj.chart.combined_with_inv') : t('proj.chart.combined');
    }
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

    const baselineLine = (label, color, data, yId) => ({
      label,
      type: 'line',
      data,
      borderColor: color + 'bb',
      backgroundColor: 'transparent',
      borderWidth: 2,
      borderDash: [10, 5],
      pointRadius: 0,
      fill: false,
      tension: 0.25,
      order: yId === 'y2' ? 1 : 2,
      spanGaps: false,
      yAxisID: yId,
    });

    const scenarioLabel = label => hasActiveSeries
      ? `${label} (${t('proj.chart.with_series')})`
      : label;
    const baselineLabel = label => `${label} (${t('proj.chart.without_series')})`;

    const baselineIncomeFull = displayState
      ? Array(histMonths.length).fill(null).concat(displayState.baselineIncomeProjected)
      : [];
    const baselineExpensesFull = displayState
      ? Array(histMonths.length).fill(null).concat(displayState.baselineExpenseProjected)
      : [];
    const baselineSavingsFull = displayState
      ? Array(histMonths.length).fill(null).concat(displayState.baselineSavingsProjected)
      : [];
    const baselineAssetsFull = displayState
      ? Array(histMonths.length).fill(null).concat(displayState.baselineAssetsProjected)
      : [];
    const baselineNonInvestedAssetsFull = displayState
      ? Array(histMonths.length).fill(null).concat(displayState.baselineNonInvestedAssetsProjected)
      : [];

    const incScatter  = pickScatterData(incomeResult);
    const incOutliers = pickScatterData(incomeResult, 'crossRot');
    const expScatter  = pickScatterData(expensesResult);
    const expOutliers = pickScatterData(expensesResult, 'crossRot');
    const savScatter  = histMonths.filter(m => incHistMap[m]  != null && expHistMap[m] != null)
                                  .map(m => ({ x: m, y: Math.round((incHistMap[m] - expHistMap[m]) * 100) / 100 }));
    const assetScatter = histMonths.filter(m => assetsHistMap[m] != null).map(m => ({ x: m, y: assetsHistMap[m] }));

    // ── Investment data for combined chart ──
    const invHistMap = {};
    (projData.historical.investments || []).forEach(p => { invHistMap[p.month] = p.value; });
    const invScatter = histMonths.filter(m => invHistMap[m] != null).map(m => ({ x: m, y: invHistMap[m] }));
    const invProjFull = Array(histMonths.length).fill(null).concat(
      (displayState?.scenarioInvestmentsProjected || []).map(v => Math.round(v * 100) / 100)
    );
    const nonInvestedAssetsProjFull = Array(histMonths.length).fill(null).concat(
      (displayState?.scenarioNonInvestedAssetsProjected || []).map(v => Math.round(v * 100) / 100)
    );
    const hasInvestments = projData.investment_model?.enabled === true;

    const datasets = [
      scatter(PROJ_COLORS.income,   incScatter,   'y'),
      ...(incOutliers.length ? [outlierMarks(t('proj.chart.income'), incOutliers, 'y')] : []),
      ...(incTrend ? [trendLine(PROJ_COLORS.income,   incTrend,         'y')] : []),
      ...(hasActiveSeries ? [baselineLine(baselineLabel(t('proj.chart.income')), PROJ_COLORS.income, baselineIncomeFull, 'y')] : []),
      projLine(scenarioLabel(t('proj.chart.income')),   PROJ_COLORS.income,   incProj,         'y'),

      scatter(PROJ_COLORS.expenses, expScatter,   'y'),
      ...(expOutliers.length ? [outlierMarks(t('proj.chart.expenses'), expOutliers, 'y')] : []),
      ...(expTrend ? [trendLine(PROJ_COLORS.expenses, expTrend,         'y')] : []),
      ...(hasActiveSeries ? [baselineLine(baselineLabel(t('proj.chart.expenses')), PROJ_COLORS.expenses, baselineExpensesFull, 'y')] : []),
      projLine(scenarioLabel(t('proj.chart.expenses')), PROJ_COLORS.expenses, expProj,         'y'),

      scatter(PROJ_COLORS.savings,  savScatter,   'y'),
      ...(savingsTrendData ? [trendLine(PROJ_COLORS.savings, savingsTrendData, 'y')] : []),
      ...(hasActiveSeries ? [baselineLine(baselineLabel(t('proj.chart.savings')), PROJ_COLORS.savings, baselineSavingsFull, 'y')] : []),
      projLine(scenarioLabel(t('proj.chart.savings')),  PROJ_COLORS.savings,  savingsProjFull, 'y'),

      scatter(PROJ_COLORS.assets,   assetScatter, 'y2'),
      ...(hasActiveSeries ? [baselineLine(baselineLabel(t('proj.chart.assets')), PROJ_COLORS.assets, baselineAssetsFull, 'y2')] : []),
      projLine(scenarioLabel(t('proj.chart.assets')),   PROJ_COLORS.assets,   assetsProjFull,  'y2'),

      ...(hasInvestments ? [
        ...(hasActiveSeries ? [baselineLine(baselineLabel(t('proj.chart.non_invested_assets')), PROJ_COLORS.nonInvestedAssets, baselineNonInvestedAssetsFull, 'y2')] : []),
        projLine(scenarioLabel(t('proj.chart.non_invested_assets')), PROJ_COLORS.nonInvestedAssets, nonInvestedAssetsProjFull, 'y2'),
        scatter(PROJ_COLORS.investments, invScatter, 'y2'),
        projLine(t('proj.chart.investments'), PROJ_COLORS.investments, invProjFull, 'y2'),
      ] : []),
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

// ── Investment sliders ───────────────────────────────────────────────────────

function _renderInvestmentSliders() {
  const container = document.getElementById('proj-investment-sliders');
  const body = document.getElementById('proj-investment-sliders-body');
  if (!container || !body) return;

  const model = _projState.projData?.investment_model;
  if (!model || !model.enabled) {
    container.style.display = 'none';
    return;
  }

  container.style.display = '';

  const interestSlider = model.interest_slider || { min: 0, max: 1, step: 0.01 };
  const contributionSlider = model.contribution_slider || { min: 0, max: 1, step: 0.01 };
  const hasInterestOverride = _projState.investmentOverrides.interestPct != null;
  const hasContributionOverride = _projState.investmentOverrides.contributionPct != null;
  const interestRaw = hasInterestOverride
    ? _projState.investmentOverrides.interestPct
    : (model.default_interest_percent ?? 0);
  const contributionRaw = hasContributionOverride
    ? _projState.investmentOverrides.contributionPct
    : (model.default_contribution_percent ?? 0);
  const interestValue = _clamp(interestRaw, interestSlider.min, interestSlider.max);
  const contributionValue = _clamp(contributionRaw, contributionSlider.min, contributionSlider.max);
  if (hasInterestOverride) _projState.investmentOverrides.interestPct = interestValue;
  if (hasContributionOverride) _projState.investmentOverrides.contributionPct = contributionValue;

  const sliderCard = ({ field, label, value, slider, defaultValue }) => `
    <div class="space-y-2">
      <div class="flex items-center justify-between gap-3">
        <div>
          <div class="text-sm text-dark-100 font-medium">${label}</div>
          <div class="text-[11px] text-dark-500">${t('proj.slider.default_value')}: <span class="text-dark-300">${_fmtSliderPct(defaultValue)}</span></div>
        </div>
        <div id="proj-slider-${field}-value" class="text-sm text-blue-300 font-medium whitespace-nowrap">${_fmtSliderPct(value)}</div>
      </div>
      <div class="flex items-center gap-3">
        <input type="range"
               id="proj-slider-${field}"
               min="${slider.min}"
               max="${slider.max}"
               step="${slider.step}"
               value="${value}"
               oninput="Projections._onInvestmentSliderInput('${field}', this.value)"
               class="flex-1 accent-blue-500">
        <label class="flex items-center gap-1 w-28 shrink-0">
          <input type="number"
                 id="proj-slider-${field}-input"
                 min="${slider.min}"
                 max="${slider.max}"
                 step="${slider.step}"
                 value="${_roundSliderValue(value)}"
                 inputmode="decimal"
                 onchange="Projections._onInvestmentSliderFieldChange('${field}', this.value)"
                 class="w-full bg-dark-700 border border-dark-600 rounded-lg text-dark-100 text-sm px-2 py-1.5 text-right focus:outline-none focus:border-blue-500">
          <span class="text-xs text-dark-400">%</span>
        </label>
      </div>
      <div class="flex items-center justify-between text-[10px] text-dark-500">
        <span>${_fmtSliderPct(slider.min)}</span>
        <span>${_fmtSliderPct(slider.max)}</span>
      </div>
    </div>`;

  body.innerHTML = `
    <div class="space-y-4">
      <div class="grid grid-cols-1 xl:grid-cols-2 gap-5">
        ${sliderCard({
          field: 'interestPct',
          label: t('proj.slider.interest'),
          value: interestValue,
          slider: interestSlider,
          defaultValue: model.default_interest_percent ?? 0,
        })}
        ${sliderCard({
          field: 'contributionPct',
          label: t('proj.slider.contribution'),
          value: contributionValue,
          slider: contributionSlider,
          defaultValue: model.default_contribution_percent ?? 0,
        })}
      </div>
      <p class="text-[11px] text-dark-500 leading-snug">${t('proj.slider.hint')}</p>
    </div>`;
}

// ── Investment detail table ──────────────────────────────────────────────────

function _renderInvestmentDetailTable() {
  const container = document.getElementById('proj-investment-detail');
  const body = document.getElementById('proj-investment-detail-body');
  if (!container || !body) return;

  const { projData } = _projState;
  const detail = projData?.investment_detail;
  if (!detail || detail.length === 0) {
    container.style.display = 'none';
    return;
  }

  container.style.display = '';

  const fmtMoney = (v) => {
    if (v == null) return '—';
    return fmt(v);
  };
  const fmtPct = (v) => {
    if (v == null) return '—';
    return Number(v).toFixed(2) + '%';
  };

  const rows = detail.map(row => {
    const cls = row.is_projected
      ? 'text-blue-300/80'
      : (row.is_current_partial ? 'text-amber-200' : 'text-dark-200');
    const bgCls = row.is_projected
      ? 'bg-blue-900/10'
      : (row.is_current_partial ? 'bg-amber-900/10' : '');
    const monthBadge = row.is_projected
      ? ' <span class="text-[9px] text-blue-400">▸</span>'
      : (row.is_current_partial ? ` <span class="text-[9px] text-amber-400 uppercase tracking-wide">${escapeHtml(t('proj.detail.partial_badge'))}</span>` : '');
    return `<tr class="${cls} ${bgCls} border-b border-dark-700 hover:bg-dark-700/40">
      <td class="px-3 py-1.5 whitespace-nowrap text-xs">${escapeHtml(row.month)}${monthBadge}</td>
      <td class="px-3 py-1.5 text-xs text-right">${fmtMoney(row.total_income)}</td>
      <td class="px-3 py-1.5 text-xs text-right">${fmtMoney(row.total_expense)}</td>
      <td class="px-3 py-1.5 text-xs text-right">${fmtMoney(row.net_result)}</td>
      <td class="px-3 py-1.5 text-xs text-right">${fmtPct(row.contribution_pct_result)}</td>
      <td class="px-3 py-1.5 text-xs text-right">${fmtMoney(row.manual_contribution)}</td>
      <td class="px-3 py-1.5 text-xs text-right">${fmtMoney(row.investment_balance)}</td>
      <td class="px-3 py-1.5 text-xs text-right">${fmtPct(row.interest_pct_investments)}</td>
      <td class="px-3 py-1.5 text-xs text-right">${fmtMoney(row.dividends)}</td>
    </tr>`;
  }).join('');

  body.innerHTML = `
    <div class="overflow-x-auto">
      <table class="w-full text-left">
        <thead>
          <tr class="text-[10px] text-dark-400 uppercase tracking-wide border-b border-dark-600">
            <th class="px-3 py-2">${t('proj.detail.col_month')}</th>
            <th class="px-3 py-2 text-right">${t('proj.detail.col_total_income')}</th>
            <th class="px-3 py-2 text-right">${t('proj.detail.col_total_expense')}</th>
            <th class="px-3 py-2 text-right">${t('proj.detail.col_net_result')}</th>
            <th class="px-3 py-2 text-right">${t('proj.detail.col_contribution_pct_result')}</th>
            <th class="px-3 py-2 text-right">${t('proj.detail.col_contribution')}</th>
            <th class="px-3 py-2 text-right">${t('proj.detail.col_investment_balance')}</th>
            <th class="px-3 py-2 text-right">${t('proj.detail.col_interest')}</th>
            <th class="px-3 py-2 text-right">${t('proj.detail.col_dividends')}</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
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
    if (metricKey === 'income' || metricKey === 'expenses') _loadData();
    else _renderCharts();
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
    if (metricKey === 'income' || metricKey === 'expenses') _loadData();
    else _renderCharts();
  },

  _onInvSetting(field, value) {
    const inv = _projState.trendSettings.investments;
    if (field === 'lookbackMonths') {
      const n = parseInt(value, 10);
      inv.lookbackMonths = (isNaN(n) || value === '') ? null : Math.max(3, Math.min(60, n));
    } else if (field === 'includeCurrentMonth') {
      inv.includeCurrentMonth = !!value;
    } else if (field === 'excludeOutliers') {
      inv.excludeOutliers = !!value;
    } else if (field === 'outlierK') {
      const k = parseFloat(value);
      inv.outlierK = isNaN(k) ? 1.5 : Math.max(0.5, Math.min(5.0, k));
    }
    delete inv.statistic;
    _saveProjPrefs({ proj_trend_investments: inv });
    _loadData();
  },

  _onInvestmentSliderInput(field, value) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return;
    const { slider } = _getInvestmentSliderMeta(field);
    const rounded = _roundSliderValue(_clamp(parsed, slider.min, slider.max));
    _projState.investmentOverrides[field] = rounded;
    _updateInvestmentSliderValue(field, rounded);
    _scheduleInvestmentRecalc();
  },

  _onInvestmentSliderFieldChange(field, value) {
    const { slider, fallback } = _getInvestmentSliderMeta(field);
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      _updateInvestmentSliderValue(field, fallback);
      return;
    }

    const rounded = _roundSliderValue(_clamp(parsed, slider.min, slider.max));
    _projState.investmentOverrides[field] = rounded;
    _updateInvestmentSliderValue(field, rounded);
    _scheduleInvestmentRecalc();
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

  async toggleSeriesEnabled(id, enabled) {
    const series = _projState.series.find(item => item.id === id);
    if (!series || series.enabled === enabled) return;

    try {
      await API.put(`/projections/series/${id}`, { enabled });
      Toast.show(enabled ? t('proj.series.enabled_on') : t('proj.series.enabled_off'));
      await _loadData();
    } catch (e) {
      Toast.show(e.message, 'err');
      await _loadData();
    }
  },
};
