/* ── charts.js — Statistics view with Chart.js ── */

'use strict';

let _charts = {};

function destroyCharts() {
  Object.values(_charts).forEach(c => { try { c.destroy(); } catch {} });
  _charts = {};
}

function _statsYAxisStartsAtZero() {
  return State?.userPreferences?.stats_y_axis_from_zero !== false;
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

function _parseColor(value) {
  const color = String(value || '').trim();
  if (!color) return null;

  if (color.startsWith('#')) {
    let hex = color.slice(1);
    if (hex.length === 3 || hex.length === 4) {
      hex = hex.split('').map(char => char + char).join('');
    }
    if (hex.length !== 6 && hex.length !== 8) return null;
    return {
      r: Number.parseInt(hex.slice(0, 2), 16),
      g: Number.parseInt(hex.slice(2, 4), 16),
      b: Number.parseInt(hex.slice(4, 6), 16),
    };
  }

  const rgbMatch = color.match(/rgba?\(([^)]+)\)/i);
  if (!rgbMatch) return null;
  const [r, g, b] = rgbMatch[1].split(',').slice(0, 3).map(part => Number.parseFloat(part.trim()));
  if ([r, g, b].some(channel => Number.isNaN(channel))) return null;
  return { r, g, b };
}

function _colorLuminance(value) {
  const rgb = _parseColor(value);
  if (!rgb) return 0.5;
  const channels = [rgb.r, rgb.g, rgb.b].map(channel => {
    const normalized = channel / 255;
    return normalized <= 0.03928
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4;
  });
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}

function _labelTextColor(backgroundColor) {
  return _colorLuminance(backgroundColor) > 0.35 ? '#0d1117' : '#f8fafc';
}

function _labelOutlineColor(textColor) {
  return textColor === '#0d1117' ? 'rgba(255,255,255,0.35)' : 'rgba(13,17,23,0.45)';
}

function _truncateTextToWidth(ctx, text, maxWidth) {
  const raw = String(text || '').trim();
  if (!raw || maxWidth <= 0) return '';
  if (ctx.measureText(raw).width <= maxWidth) return raw;

  const ellipsis = '...';
  let end = raw.length;
  while (end > 0) {
    const candidate = `${raw.slice(0, end).trim()}${ellipsis}`;
    if (ctx.measureText(candidate).width <= maxWidth) return candidate;
    end -= 1;
  }
  return '';
}

function _fitLabelLines(ctx, text, maxWidth, maxLines = 1) {
  const raw = String(text || '').trim();
  if (!raw || maxWidth <= 16) return [];
  if (maxLines <= 1) {
    const line = _truncateTextToWidth(ctx, raw, maxWidth);
    return line ? [line] : [];
  }

  const words = raw.split(/\s+/);
  const lines = [];

  while (words.length && lines.length < maxLines) {
    let line = words.shift();
    while (words.length && ctx.measureText(`${line} ${words[0]}`).width <= maxWidth) {
      line = `${line} ${words.shift()}`;
    }
    if (lines.length === maxLines - 1 && words.length) {
      line = _truncateTextToWidth(ctx, `${line} ${words.join(' ')}`.trim(), maxWidth);
      words.length = 0;
    }
    if (!line) break;
    lines.push(line);
  }

  return lines;
}

function _drawCenteredLabel(ctx, lines, x, y, {
  font = '600 11px "Segoe UI", sans-serif',
  color = '#f8fafc',
  outlineColor = 'rgba(13,17,23,0.45)',
  lineHeight = 12,
  maxWidth = 140,
} = {}) {
  if (!lines.length) return;

  ctx.save();
  ctx.font = font;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.lineJoin = 'round';
  ctx.lineWidth = 4;

  const offset = ((lines.length - 1) * lineHeight) / 2;
  lines.forEach((line, index) => {
    const lineY = y - offset + (index * lineHeight);
    ctx.strokeStyle = outlineColor;
    ctx.strokeText(line, x, lineY, maxWidth);
    ctx.fillStyle = color;
    ctx.fillText(line, x, lineY, maxWidth);
  });

  ctx.restore();
}

function _stackSlotWidth(meta, index, chartArea) {
  const point = meta.data[index];
  if (!point) return 0;
  if (meta.data.length === 1) return (chartArea.right - chartArea.left) * 0.75;

  const previous = meta.data[index - 1];
  const next = meta.data[index + 1];
  if (previous && next) return Math.abs(next.x - previous.x) * 0.55;
  if (next) return Math.abs(next.x - point.x) * 0.8;
  if (previous) return Math.abs(point.x - previous.x) * 0.8;
  return 0;
}

function _stackRangeAt(chart, datasetIndex, valueIndex) {
  const dataset = chart.data.datasets[datasetIndex];
  const currentValue = _num(dataset?.data?.[valueIndex]);
  if (Math.abs(currentValue) < 0.005) return null;

  const sign = currentValue >= 0 ? 1 : -1;
  let baseValue = 0;

  for (let index = 0; index < datasetIndex; index += 1) {
    const candidate = chart.data.datasets[index];
    if (!candidate || candidate.stack !== dataset.stack || candidate.fill !== true || !chart.isDatasetVisible(index)) {
      continue;
    }
    const candidateValue = _num(candidate.data?.[valueIndex]);
    if (Math.abs(candidateValue) < 0.005) continue;
    if ((candidateValue >= 0 ? 1 : -1) === sign) {
      baseValue += candidateValue;
    }
  }

  return { start: baseValue, end: baseValue + currentValue };
}

function _drawStackedAreaLabels(chart, options = {}) {
  const yScale = chart.scales?.y;
  const chartArea = chart.chartArea;
  if (!yScale || !chartArea) return;

  const minHeight = options.minHeight || 18;
  const minWidth = options.minWidth || 56;
  const maxWidth = options.maxWidth || 144;

  chart.data.datasets.forEach((dataset, datasetIndex) => {
    if (!dataset || dataset.fill !== true || !dataset.stack || !chart.isDatasetVisible(datasetIndex)) return;

    const meta = chart.getDatasetMeta(datasetIndex);
    let bestSlot = null;

    for (let valueIndex = 0; valueIndex < meta.data.length; valueIndex += 1) {
      const point = meta.data[valueIndex];
      const range = _stackRangeAt(chart, datasetIndex, valueIndex);
      if (!point || !range) continue;

      const startY = yScale.getPixelForValue(range.start);
      const endY = yScale.getPixelForValue(range.end);
      const height = Math.abs(endY - startY);
      const width = _stackSlotWidth(meta, valueIndex, chartArea);
      if (height < minHeight || width < minWidth) continue;

      const candidate = {
        x: point.x,
        y: (startY + endY) / 2,
        height,
        width,
        score: height * width,
      };
      if (!bestSlot || candidate.score > bestSlot.score) {
        bestSlot = candidate;
      }
    }

    if (!bestSlot) return;

    chart.ctx.save();
    chart.ctx.font = options.font || '600 11px "Segoe UI", sans-serif';
    const availableWidth = Math.max(24, Math.min(bestSlot.width, maxWidth) - 10);
    const lines = _fitLabelLines(chart.ctx, dataset.label, availableWidth, 1);
    if (!lines.length) {
      chart.ctx.restore();
      return;
    }

    const widestLine = Math.max(...lines.map(line => chart.ctx.measureText(line).width));
    chart.ctx.restore();
    if (widestLine > availableWidth) return;

    const textX = Math.min(
      chartArea.right - (availableWidth / 2) - 6,
      Math.max(chartArea.left + (availableWidth / 2) + 6, bestSlot.x)
    );
    const textY = Math.min(chartArea.bottom - 8, Math.max(chartArea.top + 8, bestSlot.y));
    const textColor = _labelTextColor(dataset.backgroundColor);

    _drawCenteredLabel(chart.ctx, lines, textX, textY, {
      font: options.font || '600 11px "Segoe UI", sans-serif',
      color: textColor,
      outlineColor: _labelOutlineColor(textColor),
      lineHeight: options.lineHeight || 12,
      maxWidth: availableWidth,
    });
  });
}

function _drawDoughnutLabels(chart, options = {}) {
  const meta = chart.getDatasetMeta(0);
  const dataset = chart.data.datasets?.[0];
  if (!meta || !dataset || !chart.isDatasetVisible(0)) return;

  const values = Array.isArray(dataset.data) ? dataset.data.map(value => Math.abs(_num(value))) : [];
  const total = values.reduce((sum, value) => sum + value, 0);
  if (!total) return;

  const minShare = options.minShare || 0.08;
  const maxWidth = options.maxWidth || 92;

  meta.data.forEach((arc, index) => {
    const value = values[index] || 0;
    if (!value) return;

    const share = value / total;
    const circumference = Math.abs(arc.circumference || (arc.endAngle - arc.startAngle));
    const ringThickness = arc.outerRadius - arc.innerRadius;
    const midAngle = (arc.startAngle + arc.endAngle) / 2;
    const radius = arc.innerRadius + (ringThickness * 0.52);
    const x = arc.x + Math.cos(midAngle) * radius;
    const y = arc.y + Math.sin(midAngle) * radius;
    const arcWidth = Math.min((radius * circumference) - 12, maxWidth);

    if (share < minShare || ringThickness < 22 || arcWidth < 30) return;

    chart.ctx.save();
    chart.ctx.font = options.font || '600 10px "Segoe UI", sans-serif';
    const lines = _fitLabelLines(chart.ctx, chart.data.labels?.[index], arcWidth, 2);
    chart.ctx.restore();
    if (!lines.length) return;

    const textColor = _labelTextColor(Array.isArray(dataset.backgroundColor) ? dataset.backgroundColor[index] : dataset.backgroundColor);
    _drawCenteredLabel(chart.ctx, lines, x, y, {
      font: options.font || '600 10px "Segoe UI", sans-serif',
      color: textColor,
      outlineColor: _labelOutlineColor(textColor),
      lineHeight: options.lineHeight || 11,
      maxWidth: arcWidth,
    });
  });
}

const _internalLabelsPlugin = {
  id: 'internalLabels',

  afterDatasetsDraw(chart, _args, pluginOptions) {
    if (!pluginOptions) return;
    if (chart.config.type === 'doughnut' && pluginOptions.doughnut?.enabled) {
      _drawDoughnutLabels(chart, pluginOptions.doughnut);
    }
    if (chart.config.type === 'line' && pluginOptions.stackedArea?.enabled) {
      _drawStackedAreaLabels(chart, pluginOptions.stackedArea);
    }
  },
};

if (typeof Chart !== 'undefined' && !Chart.registry.plugins.get('internalLabels')) {
  Chart.register(_internalLabelsPlugin);
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

function _fmtStatNumber(value) {
  return value == null || Number.isNaN(Number(value)) ? '—' : fmt(value);
}

function _positionInRange(value, minValue, maxValue) {
  if (value == null || minValue == null || maxValue == null || Number.isNaN(Number(value))) return null;
  const start = Number(minValue);
  const end = Number(maxValue);
  if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
  if (Math.abs(end - start) < 0.0000001) return 0.5;
  const raw = (Number(value) - start) / (end - start);
  return Math.min(1, Math.max(0, raw));
}

function _accountBoxplotSvg(row) {
  const box = row?.boxplot || {};
  const lowerBound = box.lower_bound;
  const upperBound = box.upper_bound;
  const whiskerMin = box.min;
  const q1 = box.q1;
  const median = box.median;
  const q3 = box.q3;
  const whiskerMax = box.max;
  const mean = box.mean;
  const current = box.current;

  if ([lowerBound, upperBound, whiskerMin, q1, median, q3, whiskerMax, mean].some(value => value == null)) {
    return `<div class="text-xs text-dark-500">${escapeHtml(t('report.no_data'))}</div>`;
  }

  const width = 240;
  const height = 28;
  const leftPad = 10;
  const rightPad = 10;
  const trackWidth = width - leftPad - rightPad;
  const midY = height / 2;
  const boxTop = 4;
  const boxHeight = 20;
  const whiskerCapHalf = 6;

  const xFor = value => leftPad + trackWidth * _positionInRange(value, lowerBound, upperBound);
  const whiskerMinX = xFor(whiskerMin);
  const q1X = xFor(q1);
  const medianX = xFor(median);
  const q3X = xFor(q3);
  const whiskerMaxX = xFor(whiskerMax);
  const meanX = xFor(mean);
  const currentRatio = _positionInRange(current, lowerBound, upperBound);
  const currentX = currentRatio == null ? null : leftPad + trackWidth * currentRatio;
  const currentIsClamped = current != null && currentRatio != null && (Number(current) < Number(lowerBound) || Number(current) > Number(upperBound));
  const currentMarkerColor = currentIsClamped ? '#ff3700' : '#00ff00';
  const currentTriangle = currentX == null
    ? ''
    : `${currentX - 2},0 ${currentX + 2},0 ${currentX},8`;

  return `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" class="w-full h-8 min-w-[220px] overflow-visible" role="img" aria-label="${escapeHtml(t('stats.account_table.boxplot_aria', { account: row.account_name }))}">
      <line x1="${leftPad}" y1="${midY}" x2="${width - rightPad}" y2="${midY}" stroke="#30363d" stroke-width="1" />
      <line x1="${whiskerMinX}" y1="${midY}" x2="${q1X}" y2="${midY}" stroke="#8b949e" stroke-width="0.5" />
      <line x1="${q3X}" y1="${midY}" x2="${whiskerMaxX}" y2="${midY}" stroke="#8b949e" stroke-width="0.5" />
      <line x1="${whiskerMinX}" y1="${midY - whiskerCapHalf}" x2="${whiskerMinX}" y2="${midY + whiskerCapHalf}" stroke="#8b949e" stroke-width="0.5" />
      <line x1="${whiskerMaxX}" y1="${midY - whiskerCapHalf}" x2="${whiskerMaxX}" y2="${midY + whiskerCapHalf}" stroke="#8b949e" stroke-width="0.5" />
      <rect x="${Math.min(q1X, q3X)}" y="${boxTop}" width="${Math.max(1, Math.abs(q3X - q1X))}" height="${boxHeight}" rx="0" fill="#1f2937" stroke="#27d7ff" stroke-width="0.5" />
      <line x1="${medianX}" y1="${boxTop}" x2="${medianX}" y2="${boxTop + boxHeight}" stroke="#ffffff" stroke-width="0.3" />
      <line x1="${meanX}" y1="${boxTop + 1}" x2="${meanX}" y2="${boxTop + boxHeight - 3}" stroke="#ffe100" stroke-width="0.5" stroke-dasharray="2 1" />
      ${currentX == null ? '' : `<g>
        <line x1="${currentX}" y1="4" x2="${currentX}" y2="${height - 4}" stroke="${currentMarkerColor}" stroke-width="0.5" />
        <polygon points="${currentTriangle}" fill="${currentMarkerColor}" stroke="#000000" stroke-width="0.2" /> 
      </g>`}
    </svg>`;
}

function _accountTypeLabel(typeId) {
  const keyMap = {
    1: 'asset',
    2: 'liability',
    3: 'income',
    4: 'expense',
  };
  const typeKey = keyMap[typeId];
  return typeKey ? t(`account.type.${typeKey}`) : '—';
}

function _accountTypeSectionTitle(typeId) {
  const keyMap = {
    1: 'asset',
    2: 'liability',
    3: 'income',
    4: 'expense',
  };
  const typeKey = keyMap[typeId];
  return typeKey ? t(`stats.account_table.section.${typeKey}`) : _accountTypeLabel(typeId);
}

function _accountNameCell(row) {
  const label = escapeHtml(row.account_name || '—');
  if (typeof Reports === 'undefined' || !row.account_id) {
    return `<span class="text-sm text-dark-100 whitespace-nowrap">${label}</span>`;
  }
  const title = escapeHtml(t('report.open_ledger_account', { account: row.account_name || '' }));
  return `<button type="button"
      class="text-sm text-blue-300 hover:text-blue-200 hover:underline whitespace-nowrap text-left"
      onclick="Reports.openLedger(${Number(row.account_id)})"
      title="${title}"
      aria-label="${title}">${label}</button>`;
}

function _accountStatsLegend() {
  const items = [
    { key: 'range', swatch: '<span class="inline-block w-8 h-[2px] rounded bg-dark-600"></span>' },
    { key: 'min', swatch: '<span class="relative inline-block w-4 h-3"><span class="absolute left-1/2 top-0 h-3 w-[2px] -translate-x-1/2 bg-dark-300"></span></span>' },
    { key: 'q1_q3', swatch: '<span class="inline-block w-8 h-3 rounded-sm border border-blue-400 bg-dark-700"></span>' },
    { key: 'median', swatch: '<span class="relative inline-block w-4 h-3"><span class="absolute left-1/2 top-0 h-3 w-[2px] -translate-x-1/2 bg-slate-50"></span></span>' },
    { key: 'mean', swatch: '<span class="relative inline-block w-4 h-3"><span class="absolute left-1/2 top-0 h-3 w-[2px] -translate-x-1/2 border-l-2 border-dashed border-amber-400"></span></span>' },
    { key: 'current', swatch: '<span class="relative inline-block w-4 h-3"><span class="absolute left-1/2 top-0 h-3 w-[2px] -translate-x-1/2 bg-green-500"></span><span class="absolute left-1/2 top-0 -translate-x-1/2 text-[8px] leading-none text-green-500">▼</span></span>' },
    { key: 'current_clamped', swatch: '<span class="relative inline-block w-4 h-3"><span class="absolute left-1/2 top-0 h-3 w-[2px] -translate-x-1/2 bg-orange-500"></span><span class="absolute left-1/2 top-0 -translate-x-1/2 text-[8px] leading-none text-orange-500">▼</span></span>' },
    { key: 'max', swatch: '<span class="relative inline-block w-4 h-3"><span class="absolute left-1/2 top-0 h-3 w-[2px] -translate-x-1/2 bg-dark-300"></span></span>' },
  ];

  return `
    <div class="mt-4 pt-4 border-t border-dark-700">
      <div class="text-[11px] font-medium uppercase tracking-wide text-dark-400 mb-3">${escapeHtml(t('stats.account_table.legend_title'))}</div>
      <div class="flex flex-wrap gap-x-5 gap-y-2 text-xs text-dark-300">
        ${items.map(item => `
          <div class="inline-flex items-center gap-2">
            ${item.swatch}
            <span>${escapeHtml(t(`stats.account_table.legend.${item.key}`))}</span>
          </div>`).join('')}
      </div>
    </div>`;
}

function _accountStatsSection(typeId, rows) {
  if (!rows.length) return '';

  const bodyRows = rows.map(row => `
    <tr class="border-t border-dark-700 hover:bg-dark-700/30">
      <td class="px-3 py-2">${_accountNameCell(row)}</td>
      <td class="px-3 py-2 text-sm text-right whitespace-nowrap ${_num(row.current) >= 0 ? 'text-dark-100' : 'text-pasivo'}">${escapeHtml(_fmtStatNumber(row.current))}</td>
      <td class="px-3 py-2 text-sm text-right whitespace-nowrap text-dark-200">${escapeHtml(_fmtStatNumber(row.mean))}</td>
      <td class="px-3 py-2 text-sm text-right whitespace-nowrap text-dark-200">${escapeHtml(_fmtStatNumber(row.median))}</td>
      <td class="px-3 py-2 text-sm text-right whitespace-nowrap text-dark-200">${escapeHtml(_fmtStatNumber(row.stddev))}</td>
      <td class="px-3 py-2 w-full min-w-[240px]">${_accountBoxplotSvg(row)}</td>
    </tr>`).join('');

  return `
    <div class="mb-5 last:mb-0">
      <div class="text-[11px] font-medium uppercase tracking-wide text-dark-500 mb-2">${escapeHtml(_accountTypeSectionTitle(typeId))}</div>
      <div class="overflow-x-auto">
        <table class="w-full min-w-[860px] table-auto">
          <thead>
            <tr class="border-b border-dark-600">
              <th class="px-3 py-2 text-left text-[11px] font-medium text-dark-400 uppercase tracking-wide">${escapeHtml(t('stats.account_table.name'))}</th>
              <th class="px-3 py-2 text-right text-[11px] font-medium text-dark-400 uppercase tracking-wide whitespace-nowrap">${escapeHtml(t('stats.account_table.current'))}</th>
              <th class="px-3 py-2 text-right text-[11px] font-medium text-dark-400 uppercase tracking-wide whitespace-nowrap">${escapeHtml(t('stats.account_table.mean'))}</th>
              <th class="px-3 py-2 text-right text-[11px] font-medium text-dark-400 uppercase tracking-wide whitespace-nowrap">${escapeHtml(t('stats.account_table.median'))}</th>
              <th class="px-3 py-2 text-right text-[11px] font-medium text-dark-400 uppercase tracking-wide whitespace-nowrap">${escapeHtml(t('stats.account_table.stddev'))}</th>
              <th class="px-3 py-2 text-left text-[11px] font-medium text-dark-400 uppercase tracking-wide w-full">${escapeHtml(t('stats.account_table.boxplot'))}</th>
            </tr>
          </thead>
          <tbody>${bodyRows}</tbody>
        </table>
      </div>
    </div>`;
}

function _accountStatsTable(rows = []) {
  if (!Array.isArray(rows) || rows.length === 0) {
    return `
      <div class="bg-dark-800 border border-dark-600 rounded-xl p-4 mb-5">
        <div class="text-xs text-dark-400 uppercase tracking-wide mb-3">${escapeHtml(t('stats.account_table.title'))}</div>
        <div class="empty py-6">${escapeHtml(t('report.no_data'))}</div>
      </div>`;
  }

  const orderedTypeIds = [1, 2, 3, 4];
  const groupedSections = orderedTypeIds.map(typeId => {
    const sectionRows = rows
      .filter(row => Number(row.type_id) === typeId)
      .sort((left, right) => String(left.account_name || '').localeCompare(String(right.account_name || ''), undefined, { sensitivity: 'base' }));
    return _accountStatsSection(typeId, sectionRows);
  }).join('');

  return `
    <div class="bg-dark-800 border border-dark-600 rounded-xl p-4 mb-5">
      <div class="flex items-center justify-between gap-3 mb-3">
        <div class="text-xs text-dark-400 uppercase tracking-wide">${escapeHtml(t('stats.account_table.title'))}</div>
        <div class="text-[11px] text-dark-500">${escapeHtml(t('stats.account_table.subtitle', { k: '1.5' }))}</div>
      </div>
      ${groupedSections}
      ${_accountStatsLegend()}
    </div>`;
}

function _replaceWithEmpty(canvasId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  canvas.outerHTML = `<div class="empty h-full flex items-center justify-center">${escapeHtml(t('report.no_data'))}</div>`;
}

function _buildDoughnutChart(canvasId, items, labelKey, valueKey, tooltipLabel, colors = null) {
  const filteredItems = (items || []).filter(item => _num(item[valueKey]) > 0);
  const total = filteredItems.reduce((sum, item) => sum + _num(item[valueKey]), 0);
  const palette = colors || ['#ef5350', '#ff8a65', '#ffd54f', '#66bb6a', '#4fc3f7', '#7986cb', '#ce93d8', '#4db6ac', '#90caf9', '#a5d6a7'];

  if (!filteredItems.length || !total) {
    _replaceWithEmpty(canvasId);
    return;
  }

  _charts[canvasId] = new Chart(document.getElementById(canvasId), {
    type: 'doughnut',
    data: {
      labels: filteredItems.map(item => item[labelKey]),
      datasets: [{
        data: filteredItems.map(item => item[valueKey]),
        backgroundColor: filteredItems.map((_, index) => palette[index % palette.length]),
        borderColor: '#161b22',
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      cutout: '58%',
      plugins: {
        internalLabels: {
          doughnut: {
            enabled: true,
          },
        },
        legend: {
          position: 'bottom',
          labels: { color: '#8b949e', font: { size: 10 }, boxWidth: 12 },
        },
        tooltip: {
          backgroundColor: '#21262d',
          borderColor: '#30363d',
          borderWidth: 1,
          titleColor: '#e6edf3',
          bodyColor: '#c9d1d9',
          callbacks: {
            label: ctx => {
              const item = filteredItems[ctx.dataIndex];
              const defaultLabel = `${ctx.label}: ${fmt(ctx.raw)}`;
              const baseLabel = tooltipLabel ? tooltipLabel(item, ctx) : defaultLabel;
              return ` ${baseLabel} • ${_fmtPct(total ? ctx.raw / total : null)}`;
            },
          },
        },
      },
    },
  });
}

function _buildAssetEvolutionBuckets(balanceEvolution = []) {
  return _buildSubtypeEvolutionBuckets(balanceEvolution, {
    bucketKey: 'subtype_name',
    valueKey: 'balance',
  });
}

function _buildSubtypeEvolutionBuckets(rows = [], {
  bucketKey = 'subtype',
  valueKey = 'amount',
  valueTransform = value => _num(value),
  maxBuckets = null,
  otherLabel = null,
} = {}) {
  const monthMap = new Map();
  const months = [];
  const bucketOrder = [];
  const bucketWeights = new Map();

  for (const row of rows) {
    const month = row.month;
    const bucket = String(row[bucketKey] || '').trim() || 'Sin subtipo';
    if (!bucket || !month) continue;

    if (!bucketOrder.includes(bucket)) {
      bucketOrder.push(bucket);
      monthMap.forEach(values => {
        values[bucket] = 0;
      });
    }

    if (!monthMap.has(month)) {
      monthMap.set(month, Object.fromEntries(bucketOrder.map(key => [key, 0])));
      months.push(month);
    }
    const value = valueTransform(row[valueKey]);
    if (Math.abs(value) < 0.005) continue;
    monthMap.get(month)[bucket] += value;
    bucketWeights.set(bucket, (bucketWeights.get(bucket) || 0) + Math.abs(value));
  }

  let sortedBucketOrder = [...bucketOrder].sort((left, right) => {
    const totalDiff = (bucketWeights.get(right) || 0) - (bucketWeights.get(left) || 0);
    if (totalDiff !== 0) return totalDiff;
    return left.localeCompare(right);
  });

  if (maxBuckets && sortedBucketOrder.length > maxBuckets) {
    const primaryBuckets = sortedBucketOrder.slice(0, maxBuckets);
    const overflowBuckets = sortedBucketOrder.slice(maxBuckets);
    const otherBucket = otherLabel || t('stats.other');

    for (const month of months) {
      const monthValues = monthMap.get(month);
      monthValues[otherBucket] = overflowBuckets.reduce((sum, bucket) => sum + _num(monthValues[bucket]), 0);
    }

    bucketWeights.set(
      otherBucket,
      overflowBuckets.reduce((sum, bucket) => sum + (bucketWeights.get(bucket) || 0), 0)
    );
    sortedBucketOrder = [...primaryBuckets, otherBucket];
  }

  return {
    months,
    bucketOrder: sortedBucketOrder,
    series: Object.fromEntries(
      sortedBucketOrder.map(bucket => [
        bucket,
        months.map(month => monthMap.get(month)?.[bucket] || 0),
      ])
    ),
  };
}

function _buildMonthlyTotals(months = [], rows = [], valueKey) {
  const totalsByMonth = new Map(rows.map(row => [row.month, _num(row[valueKey])]))
  return months.map(month => totalsByMonth.get(month) || 0);
}

function _renderStackedEvolutionChart({
  chartKey,
  canvasId,
  months,
  bucketOrder,
  series,
  totalSeries,
  totalLabel,
  totalColor = '#e6edf3',
  stackKey,
}) {
  if (!months.length || !bucketOrder.length) {
    _replaceWithEmpty(canvasId);
    return;
  }

  const startYAxisAtZero = _statsYAxisStartsAtZero();

  const totalDatasetIndex = bucketOrder.length;
  const compareStackedLabelOrder = (leftIndex, rightIndex) => {
    const leftIsTotal = leftIndex === totalDatasetIndex;
    const rightIsTotal = rightIndex === totalDatasetIndex;
    if (leftIsTotal || rightIsTotal) return leftIsTotal ? -1 : 1;
    return rightIndex - leftIndex;
  };

  const palette = [
    ['#ff9800', '#ff980044'],
    ['#4fc3f7', '#4fc3f744'],
    ['#66bb6a', '#66bb6a44'],
    ['#ce93d8', '#ce93d844'],
    ['#ffd54f', '#ffd54f44'],
    ['#ef5350', '#ef535044'],
    ['#7986cb', '#7986cb44'],
    ['#4db6ac', '#4db6ac44'],
    ['#90caf9', '#90caf944'],
    ['#a5d6a7', '#a5d6a744'],
  ];

  _charts[chartKey] = new Chart(document.getElementById(canvasId), {
    type: 'line',
    data: {
      labels: months,
      datasets: [
        ...bucketOrder.map((bucket, index) => {
          const [borderColor, backgroundColor] = palette[index % palette.length];
          return {
            label: bucket,
            data: series[bucket],
            borderColor,
            backgroundColor,
            borderWidth: 2,
            pointRadius: 0,
            tension: 0,
            fill: true,
            stack: stackKey,
            order: 2,
          };
        }),
        {
          label: totalLabel,
          data: totalSeries,
          borderColor: totalColor,
          backgroundColor: 'transparent',
          borderWidth: 2.5,
          pointRadius: 0,
          pointHoverRadius: 4,
          tension: 0,
          fill: false,
          order: 1,
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        internalLabels: {
          stackedArea: {
            enabled: true,
          },
        },
        legend: {
          labels: {
            color: '#8b949e',
            font: { size: 11 },
            sort: (left, right) => compareStackedLabelOrder(left.datasetIndex, right.datasetIndex),
          },
        },
        tooltip: {
          backgroundColor: '#21262d',
          borderColor: '#30363d',
          borderWidth: 1,
          titleColor: '#e6edf3',
          bodyColor: '#c9d1d9',
          itemSort: (left, right) => compareStackedLabelOrder(left.datasetIndex, right.datasetIndex),
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: ${fmt(ctx.raw)}`,
          },
        },
      },
      scales: {
        x: { ticks: { color: '#8b949e', font: { size: 10 } }, grid: { color: '#30363d33' } },
        y: {
          stacked: true,
          beginAtZero: startYAxisAtZero,
          ticks: { color: '#8b949e', font: { size: 10 }, callback: v => '$ ' + Number(v).toLocaleString('en-US') },
          grid: { color: '#30363d66' },
        },
      },
    },
  });
}

function _buildProjectionQueryFromPrefs(prefs = {}) {
  const horizon = typeof prefs.proj_horizon === 'number' ? prefs.proj_horizon : 12;
  const historyMonths = typeof prefs.proj_history_months === 'number' ? prefs.proj_history_months : 12;
  const income = prefs.proj_trend_income && typeof prefs.proj_trend_income === 'object' ? prefs.proj_trend_income : {};
  const investments = prefs.proj_trend_investments && typeof prefs.proj_trend_investments === 'object' ? prefs.proj_trend_investments : {};

  let projUrl = `/reports/projections?horizon=${horizon}&history_months=${historyMonths}`;
  projUrl += `&income_trend_mode=${encodeURIComponent(income.mode || 'linear')}`;

  const incomeMin = income.minVal !== '' && Number.isFinite(Number(income.minVal)) ? Number(income.minVal) : null;
  const incomeMax = income.maxVal !== '' && Number.isFinite(Number(income.maxVal)) ? Number(income.maxVal) : null;
  const incomeInflationBase = income.inflationBase !== '' && Number.isFinite(Number(income.inflationBase)) ? Number(income.inflationBase) : null;
  const incomeInflationRate = income.inflationRate !== '' && Number.isFinite(Number(income.inflationRate)) ? Number(income.inflationRate) : null;

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

function _registerSharedKpiInfo(summary, health = {}, monthlyCashflow = []) {
  const current = health.current || {};
  const baseline = health.baseline_end || {};
  const scenario = health.scenario_end || {};
  const observedMonths = Array.isArray(monthlyCashflow) ? monthlyCashflow.length : 0;
  const avgMonthlyExpense = observedMonths > 0
    ? _num(summary.total_expense) / observedMonths
    : null;
  const totalAssetBaseRunway = summary.monthly_essential_expense
    ? _num(summary.total_assets) / _num(summary.monthly_essential_expense)
    : null;

  KpiInfo.set('savings_rate', { name: t('kpi.info.savings_rate.name'), def: t('kpi.info.savings_rate.def'), formula: t('kpi.info.savings_rate.formula'), vars: [ { label: t('report.total_income'), value: fmt(summary.total_income) }, { label: t('report.total_expense'), value: fmt(summary.total_expense) } ] });
  KpiInfo.set('net_worth', { name: t('kpi.info.net_worth.name'), def: t('kpi.info.net_worth.def'), formula: t('kpi.info.net_worth.formula'), vars: [ { label: t('report.total_assets'), value: fmt(summary.total_assets ?? current.assets ?? 0) }, { label: t('report.total_liab'), value: fmt(summary.total_liabilities ?? current.liabilities ?? 0) } ] });
  KpiInfo.set('debt_ratio', { name: t('kpi.info.debt_ratio.name'), def: t('kpi.info.debt_ratio.def'), formula: t('kpi.info.debt_ratio.formula'), vars: [ { label: t('report.total_liab'), value: fmt(summary.total_liabilities) }, { label: t('report.total_assets'), value: fmt(summary.total_assets) } ] });
  KpiInfo.set('current_ratio', { name: t('kpi.info.current_ratio.name'), def: t('kpi.info.current_ratio.def'), formula: t('kpi.info.current_ratio.formula'), vars: [ { label: t('stats.kpi.current_assets'), value: fmt(summary.current_assets ?? current.current_assets ?? 0) }, { label: t('stats.kpi.current_liabilities'), value: fmt(summary.current_liabilities ?? current.current_liabilities ?? 0) } ] });
  KpiInfo.set('quick_ratio', { name: t('kpi.info.quick_ratio.name'), def: t('kpi.info.quick_ratio.def'), formula: t('kpi.info.quick_ratio.formula'), vars: [ { label: t('stats.kpi.quick_assets'), value: fmt(summary.quick_assets ?? current.quick_assets ?? 0) }, { label: t('stats.kpi.current_liabilities'), value: fmt(summary.current_liabilities ?? current.current_liabilities ?? 0) } ] });
  KpiInfo.set('runway_months', { name: t('kpi.info.runway_months.name'), def: t('kpi.info.runway_months.def'), formula: t('kpi.info.runway_months.formula'), vars: [ { label: t('stats.kpi.quick_assets'), value: fmt(summary.quick_assets ?? current.quick_assets ?? 0) }, { label: t('stats.kpi.essential_expense'), value: fmt(summary.monthly_essential_expense ?? current.monthly_essential_expense ?? 0) } ] });
  KpiInfo.set('total_runway', { name: t('kpi.info.total_runway.name'), def: t('kpi.info.total_runway.def'), formula: t('kpi.info.total_runway.formula'), vars: [ { label: t('report.total_assets'), value: fmt(summary.total_assets) }, { label: t('stats.kpi.avg_monthly_expense'), value: avgMonthlyExpense == null ? '—' : fmt(avgMonthlyExpense) } ] });
  KpiInfo.set('total_assets_basic_runway', { name: t('kpi.info.total_assets_basic_runway.name'), def: t('kpi.info.total_assets_basic_runway.def'), formula: t('kpi.info.total_assets_basic_runway.formula'), vars: [ { label: t('report.total_assets'), value: fmt(summary.total_assets) }, { label: t('stats.kpi.avg_monthly_essential_expense'), value: fmt(summary.monthly_essential_expense) }, { label: t('stats.kpi.total_assets_basic_runway'), value: _fmtMonths(totalAssetBaseRunway) } ] });
  KpiInfo.set('top_asset', { name: t('kpi.info.top_asset.name'), def: t('kpi.info.top_asset.def'), formula: t('kpi.info.top_asset.formula'), vars: [ { label: t('report.total_assets'), value: fmt(summary.total_assets) }, { label: summary.top_asset_name || '—', value: _fmtPct(summary.top_asset_share) } ] });
  KpiInfo.set('top_expense', { name: t('kpi.info.top_expense.name'), def: t('kpi.info.top_expense.def'), formula: t('kpi.info.top_expense.formula'), vars: [ { label: t('report.total_expense'), value: fmt(summary.total_expense) }, { label: summary.top_expense_name || '—', value: _fmtPct(summary.top_expense_share) } ] });
  KpiInfo.set('delta_net_worth', { name: t('kpi.info.delta_net_worth.name'), def: t('kpi.info.delta_net_worth.def'), formula: t('kpi.info.delta_net_worth.formula'), vars: [ { label: t('proj.health.scenario_end_net_worth'), value: fmt(scenario.net_worth ?? 0) }, { label: t('proj.health.baseline_end_net_worth'), value: fmt(baseline.net_worth ?? 0) } ] });
  KpiInfo.set('delta_runway', { name: t('kpi.info.delta_runway.name'), def: t('kpi.info.delta_runway.def'), formula: t('kpi.info.delta_runway.formula'), vars: [ { label: t('proj.health.scenario_end_runway'), value: _fmtMonths(scenario.runway_months) }, { label: t('proj.health.baseline_end_runway'), value: _fmtMonths(baseline.runway_months) } ] });
}

function _statsChartsGridMarkup() {
  return `
    <div class="grid grid-cols-1 xl:grid-cols-3 gap-5" id="stats-grid">
      <div class="xl:col-span-3 bg-dark-800 border border-dark-600 rounded-xl p-4"><h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.monthly_cashflow')}</h3><canvas id="ch-cashflow" height="140"></canvas></div>
      <div class="bg-dark-800 border border-dark-600 rounded-xl p-4"><h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.expense_by_type')}</h3><canvas id="ch-expense-breakdown" height="200"></canvas></div>
      <div class="bg-dark-800 border border-dark-600 rounded-xl p-4"><h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.income_by_type')}</h3><canvas id="ch-income-breakdown" height="200"></canvas></div>
      <div class="bg-dark-800 border border-dark-600 rounded-xl p-4"><h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.asset_composition')}</h3><canvas id="ch-asset-pie" height="200"></canvas></div>
      <div class="xl:col-span-3 bg-dark-800 border border-dark-600 rounded-xl p-4"><h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.asset_evolution')}</h3><canvas id="ch-asset-evolution" height="180"></canvas></div>
      <div class="xl:col-span-3 bg-dark-800 border border-dark-600 rounded-xl p-4"><h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.income_evolution')}</h3><canvas id="ch-income-evolution" height="180"></canvas></div>
      <div class="xl:col-span-3 bg-dark-800 border border-dark-600 rounded-xl p-4"><h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.expense_evolution')}</h3><canvas id="ch-expense-evolution" height="180"></canvas></div>
      <div class="xl:col-span-3 bg-dark-800 border border-dark-600 rounded-xl p-4"><h3 class="text-xs text-dark-400 uppercase tracking-wide mb-3">${t('stats.liability_evolution')}</h3><canvas id="ch-liability-evolution" height="180"></canvas></div>
    </div>`;
}

function _statsChartsMarkup() {
  return `
    <div class="overflow-y-auto flex-1">
    <div class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-5 xl:px-4 py-6">
    ${typeof Reports !== 'undefined' ? Reports._tagFilterBar() : ''}
    <div class="flex flex-wrap gap-4 mb-5">
      <label class="inline-flex items-center gap-2 text-xs text-dark-300 select-none cursor-pointer">
        <input type="checkbox"
               class="h-3.5 w-3.5 rounded border-dark-500 bg-dark-700 text-blue-500 focus:ring-blue-500/40"
               ${_statsYAxisStartsAtZero() ? 'checked' : ''}
               data-chart-change="toggle-stats-y-axis-zero">
        <span>${t('stats.y_axis_from_zero')}</span>
      </label>
    </div>
    ${_statsChartsGridMarkup()}
    </div></div>`;
}

function _renderStatsCharts(data) {
  const startYAxisAtZero = _statsYAxisStartsAtZero();
  const summary = data.summary || {};
  const monthlyCashflow = data.monthly_cashflow || [];
  const expenseBreakdown = _topBreakdown(data.expenses_by_subtype || [], 'subtype', 'amount');
  const incomeBreakdown = _topBreakdown(data.income_by_subtype || [], 'subtype', 'amount');
  const assetComposition = data.asset_composition || [];
  const balanceEvolution = data.balance_evolution || [];
  const incomeEvolution = data.income_evolution || [];
  const expenseEvolution = data.expense_evolution || [];
  const liabilityEvolution = data.liability_evolution || [];
  const netWorthEvolution = data.net_worth_evolution || [];
  const defaults = { color: '#c9d1d9', borderColor: '#30363d', plugins: { legend: { labels: { color: '#8b949e', font: { size: 11 } } }, tooltip: { backgroundColor: '#21262d', borderColor: '#30363d', borderWidth: 1, titleColor: '#e6edf3', bodyColor: '#c9d1d9', callbacks: { label: ctx => ` ${fmt(ctx.parsed.y ?? ctx.parsed)}` } } }, scales: { x: { ticks: { color: '#8b949e', font: { size: 10 } }, grid: { color: '#30363d33' } }, y: { beginAtZero: startYAxisAtZero, ticks: { color: '#8b949e', font: { size: 10 }, callback: v => '$ ' + v.toLocaleString('en-US') }, grid: { color: '#30363d66' } } } };

  if (monthlyCashflow.length > 0) {
    const labels = monthlyCashflow.map(row => row.month);
    const netValues = monthlyCashflow.map(row => _num(row.neto));
    const movingAverage = _rollingAverage(netValues, 3);
    _charts.cashflow = new Chart(document.getElementById('ch-cashflow'), {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: t('chart.income'),
            data: monthlyCashflow.map(row => row.ingresos),
            borderColor: '#66bb6a',
            backgroundColor: 'transparent',
            borderWidth: 2,
            tension: 0,
            pointRadius: 3,
            fill: false,
            yAxisID: 'y',
          },
          {
            label: t('chart.expense'),
            data: monthlyCashflow.map(row => row.gastos),
            borderColor: '#ef5350',
            backgroundColor: 'transparent',
            borderWidth: 2,
            tension: 0,
            pointRadius: 3,
            fill: false,
            yAxisID: 'y',
          },
          {
            label: t('chart.net'),
            data: netValues,
            borderColor: '#ffd54f',
            backgroundColor: 'transparent',
            borderWidth: 2,
            tension: 0,
            pointRadius: 4,
            pointBackgroundColor: netValues.map(value => value < 0 ? '#ef5350' : '#ffd54f'),
            pointBorderColor: netValues.map(value => value < 0 ? '#ef5350' : '#ffd54f'),
            fill: false,
            yAxisID: 'y',
          },
          {
            label: t('stats.moving_average'),
            data: movingAverage,
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
    _buildDoughnutChart('ch-expense-breakdown', expenseBreakdown, 'subtype', 'amount', item => `${item.subtype}: ${fmt(item.amount)}`, ['#ef5350', '#ff8a65', '#ffb74d', '#ffd54f', '#e57373', '#f06292', '#a1887f', '#ffcc80']);
  } else {
    _replaceWithEmpty('ch-expense-breakdown');
  }

  if (incomeBreakdown.length > 0) {
    _buildDoughnutChart('ch-income-breakdown', incomeBreakdown, 'subtype', 'amount', item => `${item.subtype}: ${fmt(item.amount)}`, ['#66bb6a', '#81c784', '#4db6ac', '#4fc3f7', '#aed581', '#dce775', '#26a69a', '#80cbc4']);
  } else {
    _replaceWithEmpty('ch-income-breakdown');
  }

  if (assetComposition.length > 0) {
    const assetColors = ['#4fc3f7', '#80deea', '#66bb6a', '#ffd54f', '#ff8a65', '#ce93d8', '#9575cd', '#7986cb', '#4db6ac', '#90caf9'];
    _charts.assetPie = new Chart(document.getElementById('ch-asset-pie'), { type: 'doughnut', data: { labels: assetComposition.map(row => row.account), datasets: [{ data: assetComposition.map(row => row.balance), backgroundColor: assetColors, borderColor: '#161b22', borderWidth: 2 }] }, options: { responsive: true, cutout: '58%', plugins: { internalLabels: { doughnut: { enabled: true } }, legend: { position: 'bottom', labels: { color: '#8b949e', font: { size: 10 }, boxWidth: 12 } }, tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${fmt(ctx.raw)} • ${_fmtPct(summary.total_assets ? ctx.raw / summary.total_assets : null)}` } } } } });
  } else {
    _replaceWithEmpty('ch-asset-pie');
  }

  const assetBuckets = _buildAssetEvolutionBuckets(balanceEvolution);
  if (assetBuckets.months.length > 0) {
    _renderStackedEvolutionChart({
      chartKey: 'assetEvolution',
      canvasId: 'ch-asset-evolution',
      months: assetBuckets.months,
      bucketOrder: assetBuckets.bucketOrder,
      series: assetBuckets.series,
      totalSeries: _buildMonthlyTotals(assetBuckets.months, netWorthEvolution, 'assets'),
      totalLabel: t('report.total_assets'),
      totalColor: '#e6edf3',
      stackKey: 'assets',
    });
  } else {
    _replaceWithEmpty('ch-asset-evolution');
  }

  const incomeBuckets = _buildSubtypeEvolutionBuckets(incomeEvolution, { bucketKey: 'subtype', valueKey: 'amount' });
  if (incomeBuckets.months.length > 0) {
    _renderStackedEvolutionChart({
      chartKey: 'incomeEvolution',
      canvasId: 'ch-income-evolution',
      months: incomeBuckets.months,
      bucketOrder: incomeBuckets.bucketOrder,
      series: incomeBuckets.series,
      totalSeries: _buildMonthlyTotals(incomeBuckets.months, monthlyCashflow, 'ingresos'),
      totalLabel: t('report.total_income'),
      totalColor: '#dce775',
      stackKey: 'income',
    });
  } else {
    _replaceWithEmpty('ch-income-evolution');
  }

  const expenseBuckets = _buildSubtypeEvolutionBuckets(expenseEvolution, { bucketKey: 'subtype', valueKey: 'amount', maxBuckets: 6, otherLabel: t('stats.other') });
  if (expenseBuckets.months.length > 0) {
    _renderStackedEvolutionChart({
      chartKey: 'expenseEvolution',
      canvasId: 'ch-expense-evolution',
      months: expenseBuckets.months,
      bucketOrder: expenseBuckets.bucketOrder,
      series: expenseBuckets.series,
      totalSeries: _buildMonthlyTotals(expenseBuckets.months, monthlyCashflow, 'gastos'),
      totalLabel: t('report.total_expense'),
      totalColor: '#ffcc80',
      stackKey: 'expense',
    });
  } else {
    _replaceWithEmpty('ch-expense-evolution');
  }

  const liabilityBuckets = _buildSubtypeEvolutionBuckets(liabilityEvolution, {
    bucketKey: 'subtype_name',
    valueKey: 'balance',
  });
  if (liabilityBuckets.months.length > 0) {
    _renderStackedEvolutionChart({
      chartKey: 'liabilityEvolution',
      canvasId: 'ch-liability-evolution',
      months: liabilityBuckets.months,
      bucketOrder: liabilityBuckets.bucketOrder,
      series: liabilityBuckets.series,
      totalSeries: _buildMonthlyTotals(liabilityBuckets.months, netWorthEvolution, 'liabilities'),
      totalLabel: t('report.total_liab'),
      totalColor: '#ffb4ab',
      stackKey: 'liabilities',
    });
  } else {
    _replaceWithEmpty('ch-liability-evolution');
  }
}

const Charts = {
  _statsData: null,

  _renderStatsView(data) {
    this._statsData = data;
    const main = document.getElementById('main');
    destroyCharts();
    main.innerHTML = _statsChartsMarkup();
    _renderStatsCharts(data);
  },

  _rerenderStatsCharts() {
    if (!this._statsData) return;

    const grid = document.getElementById('stats-grid');
    if (!grid) return;

    destroyCharts();
    grid.outerHTML = _statsChartsGridMarkup();
    _renderStatsCharts(this._statsData);
  },

  async panel() {
    const q = State.buildReportQuery();
    const [statsData, prefs] = await Promise.all([API.get('/reports/stats' + q), API.get('/settings/preferences').catch(() => ({}))]);
    const projData = await API.get(_buildProjectionQueryFromPrefs(prefs)).catch(() => null);
    const main = document.getElementById('main');
    const summary = statsData.summary || {};
    const accountStats = Array.isArray(statsData.account_stats) ? statsData.account_stats : [];
    const investmentModel = projData?.investment_model || {};
    const health = projData?.health || {};
    const monthlyCashflow = Array.isArray(statsData.monthly_cashflow) ? statsData.monthly_cashflow : [];
    const observedMonths = monthlyCashflow.length;
    const currentMonthCashflow = observedMonths > 0 ? monthlyCashflow[observedMonths - 1] : null;
    const avgMonthlyIncome = observedMonths > 0 ? _num(summary.total_income) / observedMonths : null;
    const avgMonthlyExpense = observedMonths > 0 ? _num(summary.total_expense) / observedMonths : null;
    const avgMonthlyBaseExpense = summary.monthly_essential_expense;
    const avgMonthlyResult = observedMonths > 0 ? _num(summary.net_result) / observedMonths : null;
    const avgMonthlySavings = avgMonthlyResult;
    const avgMonthlySavingsToTotalIncome = _num(summary.total_income) ? avgMonthlySavings / _num(summary.total_income) : null;
    const totalAssetsBasicRunway = avgMonthlyBaseExpense ? _num(summary.total_assets) / _num(avgMonthlyBaseExpense) : null;
    const totalAssetsRunway = avgMonthlyExpense ? _num(summary.total_assets) / _num(avgMonthlyExpense) : null;
    const currentMonthNote = currentMonthCashflow?.month || t('report.no_data');
    const avgMonthlyResultClass = _num(avgMonthlyResult) >= 0 ? 'text-ingreso' : 'text-pasivo';
    const avgMonthlySavingsClass = _num(avgMonthlySavings) >= 0 ? 'text-ingreso' : 'text-pasivo';
    const avgMonthlySavingsToTotalIncomeClass = _num(avgMonthlySavingsToTotalIncome) >= 0 ? 'text-ingreso' : 'text-pasivo';
    const baseExpenseBasisNote = `${t('stats.kpi.essential_expense')}: ${summary.runway_basis ? t(`stats.runway_basis.${summary.runway_basis}`) : '—'}`;
    const yieldSamples = Number(investmentModel.sample_count || 0);
    const contributionSamples = Number(investmentModel.contrib_sample_count || 0);

    destroyCharts();
    _registerSharedKpiInfo(summary, health, monthlyCashflow);

    main.innerHTML = `
      <div class="overflow-y-auto flex-1">
      <div class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-5 xl:px-4 py-6">
      ${typeof Reports !== 'undefined' ? Reports._tagFilterBar() : ''}
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-5">
        ${_kpiCard({ label: t('report.total_assets'), value: fmt(summary.total_assets), valueClass: 'text-activo' })}
        ${_kpiCard({ label: t('report.total_liab'), value: fmt(summary.total_liabilities), valueClass: 'text-pasivo' })}
        ${_kpiCard({ label: t('stats.kpi.current_month_income'), value: currentMonthCashflow ? fmt(currentMonthCashflow.ingresos) : '—', valueClass: 'text-ingreso', note: currentMonthNote })}
        ${_kpiCard({ label: t('stats.kpi.current_month_expense'), value: currentMonthCashflow ? fmt(currentMonthCashflow.gastos) : '—', valueClass: 'text-pasivo', note: currentMonthNote })}
        ${_kpiCard({ label: t('stats.kpi.avg_monthly_income'), value: avgMonthlyIncome == null ? '—' : fmt(avgMonthlyIncome), valueClass: 'text-ingreso' })}
        ${_kpiCard({ label: t('stats.kpi.avg_monthly_expense'), value: avgMonthlyExpense == null ? '—' : fmt(avgMonthlyExpense), valueClass: 'text-pasivo' })}
        ${_kpiCard({ label: t('stats.kpi.avg_monthly_essential_expense'), value: avgMonthlyBaseExpense == null ? '—' : fmt(avgMonthlyBaseExpense), valueClass: 'text-pasivo', note: baseExpenseBasisNote })}
        ${_kpiCard({ label: t('stats.kpi.avg_monthly_result'), value: avgMonthlyResult == null ? '—' : fmt(avgMonthlyResult), valueClass: avgMonthlyResultClass })}
        ${_kpiCard({ label: t('stats.kpi.avg_investment_contribution_amount'), value: contributionSamples > 0 ? fmt(investmentModel.contribution_amount) : '—', valueClass: 'text-orange-400', note: t('stats.note.contribution_samples', { count: contributionSamples }) })}
        ${_kpiCard({ label: t('stats.kpi.avg_investment_yield_amount'), value: yieldSamples > 0 ? fmt(investmentModel.interest_amount) : '—', valueClass: 'text-activo', note: t('stats.note.yield_samples', { count: yieldSamples }) })}
        ${_kpiCard({ label: t('stats.kpi.avg_investment_contribution_rate'), value: contributionSamples > 0 ? _fmtPct(investmentModel.contribution_rate) : '—', valueClass: 'text-orange-400', note: t('stats.note.contribution_samples', { count: contributionSamples }) })}
        ${_kpiCard({ label: t('stats.kpi.avg_investment_yield'), value: yieldSamples > 0 ? _fmtPct(investmentModel.yield_rate) : '—', valueClass: 'text-activo', note: t('stats.note.yield_samples', { count: yieldSamples }) })}
        ${_kpiCard({ label: t('stats.kpi.avg_monthly_savings'), value: avgMonthlySavings == null ? '—' : fmt(avgMonthlySavings), valueClass: avgMonthlySavingsClass, note: `${t('stats.kpi.avg_monthly_income')}: ${avgMonthlyIncome == null ? '—' : fmt(avgMonthlyIncome)} · ${t('stats.kpi.avg_monthly_expense')}: ${avgMonthlyExpense == null ? '—' : fmt(avgMonthlyExpense)}` })}
        ${_kpiCard({ label: t('stats.kpi.avg_monthly_savings_to_total_income'), value: _fmtPct(avgMonthlySavingsToTotalIncome), valueClass: avgMonthlySavingsToTotalIncomeClass, note: `${t('report.total_income')}: ${fmt(summary.total_income)}` })}
        ${_kpiCard({ label: t('stats.kpi.total_assets_basic_runway'), value: _fmtMonths(totalAssetsBasicRunway), valueClass: totalAssetsBasicRunway != null && _num(totalAssetsBasicRunway) < 6 ? 'text-pasivo' : 'text-dark-100', note: `${t('stats.kpi.avg_monthly_essential_expense')}: ${avgMonthlyBaseExpense == null ? '—' : fmt(avgMonthlyBaseExpense)}`, infoKey: 'total_assets_basic_runway' })}
        ${_kpiCard({ label: t('stats.kpi.total_assets_total_runway'), value: _fmtMonths(totalAssetsRunway), valueClass: totalAssetsRunway != null && _num(totalAssetsRunway) < 6 ? 'text-pasivo' : 'text-dark-100', note: `${t('stats.kpi.avg_monthly_expense')}: ${avgMonthlyExpense == null ? '—' : fmt(avgMonthlyExpense)}`, infoKey: 'total_runway' })}
      </div>
      ${_accountStatsTable(accountStats)}
      </div></div>`;
  },

  async stats() {
    const q = State.buildReportQuery();
    const data = await API.get('/reports/stats' + q);
    this._renderStatsView(data);
  },

  async toggleStatsYAxisZero(checked) {
    try {
      await Preferences.save({ stats_y_axis_from_zero: checked });
      this._rerenderStatsCharts();
    } catch (error) {
      const toggle = document.querySelector('[data-chart-change="toggle-stats-y-axis-zero"]');
      if (toggle) toggle.checked = _statsYAxisStartsAtZero();
      Toast.show(t('msg.error_generic', { msg: error.message }), 'error');
    }
  },
};

window.KpiInfo = KpiInfo;
window.Charts = Charts;

document.addEventListener('change', event => {
  const target = event.target.closest('[data-chart-change]');
  if (!target) return;

  const main = document.getElementById('main');
  if (main && !main.contains(target)) return;

  switch (target.dataset.chartChange) {
    case 'toggle-stats-y-axis-zero':
      Charts.toggleStatsYAxisZero(target.checked);
      break;
    default:
      break;
  }
});
