/* ── projections/trends.js — Trend dataset builders ── */
'use strict';

window.ProjectionsTrends = (() => {
  function olsFromPoints(points) {
    const n = points.length;
    if (n === 0) return { slope: 0, intercept: 0 };
    if (n === 1) return { slope: 0, intercept: points[0].value };
    const xm = points.reduce((sum, point) => sum + point.idx, 0) / n;
    const ym = points.reduce((sum, point) => sum + point.value, 0) / n;
    const num = points.reduce((sum, point) => sum + (point.idx - xm) * (point.value - ym), 0);
    const den = points.reduce((sum, point) => sum + (point.idx - xm) ** 2, 0);
    const slope = den ? num / den : 0;
    return { slope, intercept: ym - slope * xm };
  }

  function computeTrendDatasets(allLabels, histMonths, histMap, color, settings) {
    const parseTrendSettingNumber = window.ProjectionsCommon.parseTrendSettingNumber;
    const allPts = histMonths
      .map((month, index) => histMap[month] != null ? { idx: index, month, value: histMap[month] } : null)
      .filter(Boolean);

    if (settings.mode === 'inflation') {
      if (allPts.length === 0) return { trendDataset: null, outlierDataset: null };

      const lastPt = allPts[allPts.length - 1];
      const rawBase = settings.inflationBase;
      const base = (rawBase !== '' && rawBase !== null)
        ? parseTrendSettingNumber(rawBase, 'inflationBase')
        : lastPt.value;
      const rawRate = settings.inflationRate;
      const parsedRate = (rawRate !== '' && rawRate !== null)
        ? parseTrendSettingNumber(rawRate, 'inflationRate')
        : null;
      const rate = parsedRate != null ? parsedRate / 100 : 0;

      if (isNaN(base)) return { trendDataset: null, outlierDataset: null };

      const trendData = allLabels.map((_, index) => {
        if (index < lastPt.idx) return null;
        return Math.max(0, Math.round(base * Math.pow(1 + rate, index - lastPt.idx) * 100) / 100);
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

    const minVal = settings.minVal !== '' ? parseTrendSettingNumber(settings.minVal, 'minVal') : null;
    const maxVal = settings.maxVal !== '' ? parseTrendSettingNumber(settings.maxVal, 'maxVal') : null;
    const hasMin = minVal !== null && !isNaN(minVal);
    const hasMax = maxVal !== null && !isNaN(maxVal);

    const inliers = allPts.filter(point => (!hasMin || point.value >= minVal) && (!hasMax || point.value <= maxVal));
    const outliers = allPts.filter(point => (hasMin && point.value < minVal) || (hasMax && point.value > maxVal));
    const outlierDataset = outliers.length > 0 ? {
      label: t('proj.chart.outliers'),
      type: 'scatter',
      data: outliers.map(point => ({ x: point.month, y: point.value })),
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

    const { slope, intercept } = olsFromPoints(inliers);
    const trendData = allLabels.map((_, index) =>
      Math.max(0, Math.round((intercept + slope * index) * 100) / 100)
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

  return {
    olsFromPoints,
    computeTrendDatasets,
  };
})();