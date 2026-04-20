/* ── projections/common.js — Shared stateful helpers for projections ── */
'use strict';

window.ProjectionsCommon = (() => {
  let getState = () => null;
  let savePrefs = () => {};
  let loadData = () => {};

  const PROJ_COLORS = {
    income: '#66bb6a',
    expenses: '#ef5350',
    savings: '#ffd54f',
    assets: '#4fc3f7',
    liabilities: '#ce93d8',
    investments: '#ff9800',
    nonInvestedAssets: '#26a69a',
  };

  function registerRuntime({ stateGetter, savePrefsFn, loadDataFn } = {}) {
    if (typeof stateGetter === 'function') getState = stateGetter;
    if (typeof savePrefsFn === 'function') savePrefs = savePrefsFn;
    if (typeof loadDataFn === 'function') loadData = loadDataFn;
  }

  function fmtProjRatio(value) {
    if (value == null || Number.isNaN(Number(value))) return '-';
    return `${Number(value).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}x`;
  }

  function fmtProjMonths(value) {
    if (value == null || Number.isNaN(Number(value))) return '-';
    return `${Number(value).toLocaleString('en-US', {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })}m`;
  }

  function healthCard(label, value, note = '', valueClass = 'text-dark-100', infoKey = null) {
    const infoBtn = infoKey
      ? `<button class="kpi-info-btn" onclick="KpiInfo.show('${infoKey}')"
               title="${escapeHtml(t('kpi.info.btn'))}" aria-label="${escapeHtml(t('kpi.info.btn'))}">i</button>`
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

  function parseMonth(value) {
    return { y: parseInt(value.slice(0, 4), 10), mo: parseInt(value.slice(5, 7), 10) };
  }

  function monthActive(series, monthStr) {
    if (series.enabled === false) return false;
    const start = series.start_date.slice(0, 7);
    const { y: sy, mo: sm } = parseMonth(start);
    const { y: my, mo: mm } = parseMonth(monthStr);
    const idx = (my - sy) * 12 + (mm - sm);
    const durationMonths = Math.max(1, Number(series.months) || 1);
    const periodMonths = Math.max(1, Number(series.period_months) || 1);
    return idx >= 0 && idx < durationMonths && idx % periodMonths === 0;
  }

  function hasActiveSeries() {
    const state = getState();
    return Array.isArray(state?.series) && state.series.some(
      series => series.enabled !== false && series.confirmed !== true
    );
  }

  function getLastKnownValue(metric, projData) {
    if (!projData) return null;
    const pts = projData.historical[metric] || [];
    return pts.length > 0 ? pts[pts.length - 1].value : null;
  }

  function trendSettingPrecision(field) {
    return field === 'inflationRate' ? 4 : 2;
  }

  function parseTrendSettingNumber(value, field) {
    const parsed = parseMoneyInput(value, { maxFractionDigits: trendSettingPrecision(field) });
    return parsed.isValid ? parsed.value : null;
  }

  function normalizeTrendSettingValue(field, value) {
    const parsed = parseMoneyInput(value, { maxFractionDigits: trendSettingPrecision(field) });
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

  function investmentFieldPrecision(field) {
    return field === 'interestPct' ? 6 : 2;
  }

  function investmentInputStep(field) {
    return field === 'interestPct' ? 0.000001 : 0.01;
  }

  function roundSliderValue(value, field = null) {
    const digits = investmentFieldPrecision(field);
    const factor = 10 ** digits;
    return Math.round(Number(value) * factor) / factor;
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function fmtSliderPct(value, field = null) {
    if (value == null || Number.isNaN(Number(value))) return '-';
    const digits = investmentFieldPrecision(field);
    return `${Number(value).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: digits,
    })}%`;
  }

  function updateInvestmentSliderValue(field, value) {
    const valueEl = document.getElementById(`proj-slider-${field}-value`);
    if (valueEl) valueEl.textContent = fmtSliderPct(value, field);

    const sliderEl = document.getElementById(`proj-slider-${field}`);
    if (sliderEl) sliderEl.value = value;

    const inputEl = document.getElementById(`proj-slider-${field}-input`);
    if (inputEl) inputEl.value = roundSliderValue(value, field);
  }

  function getInvestmentSliderMeta(field) {
    const state = getState();
    const model = state?.projData?.investment_model;
    const isInterestField = field === 'interestPct';
    const defaultValue = isInterestField
      ? (model?.default_interest_percent ?? 0)
      : (model?.default_contribution_percent ?? 0);
    const overrideValue = state?.investmentOverrides?.[field];

    return {
      slider: isInterestField
        ? (model?.interest_slider || { min: 0, max: 1, step: 0.01 })
        : (model?.contribution_slider || { min: 0, max: 1, step: 0.01 }),
      defaultValue,
      currentValue: overrideValue ?? defaultValue,
      hasOverride: overrideValue != null,
    };
  }

  function normalizeInvestmentOverride(value) {
    if (value == null || value === '') return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function investmentOverridePrefs() {
    const state = getState();
    return {
      proj_investment_interest_pct_override: state?.investmentOverrides?.interestPct ?? null,
      proj_investment_contribution_pct_override: state?.investmentOverrides?.contributionPct ?? null,
    };
  }

  function clearInvestmentRecalcSchedule() {
    const state = getState();
    const debounceId = state?.investmentOverrides?.debounceId;
    if (debounceId) {
      window.clearTimeout(debounceId);
      state.investmentOverrides.debounceId = null;
    }
  }

  function scheduleInvestmentRecalc() {
    const state = getState();
    if (!state?.investmentOverrides) return;
    clearInvestmentRecalcSchedule();
    state.investmentOverrides.debounceId = window.setTimeout(() => {
      state.investmentOverrides.debounceId = null;
      savePrefs(investmentOverridePrefs());
      loadData();
    }, 180);
  }

  return {
    registerRuntime,
    PROJ_COLORS,
    fmtProjRatio,
    fmtProjMonths,
    healthCard,
    parseMonth,
    monthActive,
    hasActiveSeries,
    getLastKnownValue,
    trendSettingPrecision,
    parseTrendSettingNumber,
    normalizeTrendSettingValue,
    investmentFieldPrecision,
    investmentInputStep,
    roundSliderValue,
    clamp,
    fmtSliderPct,
    updateInvestmentSliderValue,
    getInvestmentSliderMeta,
    normalizeInvestmentOverride,
    investmentOverridePrefs,
    clearInvestmentRecalcSchedule,
    scheduleInvestmentRecalc,
  };
})();