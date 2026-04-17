/* ── projections/display.js — Derived display state builders ── */
'use strict';

window.ProjectionsDisplay = (() => {
  let getState = () => null;
  let buildProjectionDatasets = () => null;
  let hasActiveSeries = () => false;

  function registerRuntime({ stateGetter, buildProjectionDatasetsFn, hasActiveSeriesFn } = {}) {
    if (typeof stateGetter === 'function') getState = stateGetter;
    if (typeof buildProjectionDatasetsFn === 'function') buildProjectionDatasets = buildProjectionDatasetsFn;
    if (typeof hasActiveSeriesFn === 'function') hasActiveSeries = hasActiveSeriesFn;
  }

  function roundProjectionValue(value, digits = 4) {
    if (value == null || Number.isNaN(Number(value))) return 0;
    const factor = 10 ** digits;
    return Math.round(Number(value) * factor) / factor;
  }

  function safeProjectionRatio(numerator, denominator) {
    const num = Number(numerator);
    const den = Number(denominator);
    if (!Number.isFinite(num) || !Number.isFinite(den) || Math.abs(den) < 0.0000001) {
      return null;
    }
    return num / den;
  }

  function projectedValuesFromSeries(series, nHist, projMonths, fallback = []) {
    return projMonths.map((_, index) => {
      const value = Array.isArray(series) ? series[nHist + index] : undefined;
      const fallbackValue = Array.isArray(fallback) ? fallback[index] : 0;
      return roundProjectionValue(value ?? fallbackValue);
    });
  }

  function buildProjectedAssetSeries(currentAssets, projectedSavings, projectedReturns) {
    let running = Number(currentAssets || 0);
    return projectedSavings.map((savings, index) => {
      running = roundProjectionValue(
        running
        + Number(savings || 0)
        + Number(projectedReturns[index] || 0)
      );
      return running;
    });
  }

  function buildProjectedInvestmentSeries(currentInvestments, projectedReturns, projectedContributions) {
    let running = Number(currentInvestments || 0);
    return projectedReturns.map((interest, index) => {
      running = roundProjectionValue(
        running
        + Number(interest || 0)
        + Number(projectedContributions[index] || 0)
      );
      return running;
    });
  }

  function deriveProjectionDisplayState() {
    const projState = getState();
    const projData = projState?.projData;
    if (!projData) return null;

    const common = window.ProjectionsCommon;
    const histMonths = projData.historical_months || [];
    const projMonths = projData.projected_months || [];
    const allLabels = [...histMonths, ...projMonths];
    const nHist = histMonths.length;

    const incomeResult = buildProjectionDatasets(
      'income',
      histMonths,
      projMonths,
      projData,
      common.PROJ_COLORS.income,
      true,
      projState.trendSettings.income
    );
    const expensesResult = buildProjectionDatasets(
      'expenses',
      histMonths,
      projMonths,
      projData,
      common.PROJ_COLORS.expenses,
      true,
      projState.trendSettings.expenses
    );

    const incProj = incomeResult._raw.projFull || [];
    const expProj = expensesResult._raw.projFull || [];
    const incTrend = incomeResult._raw.trendData || null;
    const expTrend = expensesResult._raw.trendData || null;

    const baselineIncomeProjected = projectedValuesFromSeries(
      incTrend,
      nHist,
      projMonths,
      projData.baseline_projection?.income || []
    );
    const baselineExpenseProjected = projectedValuesFromSeries(
      expTrend,
      nHist,
      projMonths,
      projData.baseline_projection?.expenses || []
    );
    const scenarioIncomeProjected = projectedValuesFromSeries(
      incProj,
      nHist,
      projMonths,
      projData.baseline_projection?.income || []
    );
    const scenarioExpenseProjected = projectedValuesFromSeries(
      expProj,
      nHist,
      projMonths,
      projData.baseline_projection?.expenses || []
    );

    const baselineSavingsProjected = projMonths.map((_, index) =>
      roundProjectionValue(
        Number(baselineIncomeProjected[index] || 0)
        - Number(baselineExpenseProjected[index] || 0)
      )
    );
    const scenarioSavingsProjected = projMonths.map((_, index) =>
      roundProjectionValue(
        Number(scenarioIncomeProjected[index] || 0)
        - Number(scenarioExpenseProjected[index] || 0)
      )
    );

    const projectedReturns = (projData.investment_detail || [])
      .filter(row => row.is_projected)
      .map(row => roundProjectionValue(row.interest_total || 0));
    const projectedContributions = (projData.investment_detail || [])
      .filter(row => row.is_projected)
      .map(row => roundProjectionValue((row.manual_contribution || 0) + (row.series_transfer || 0)));

    const baselineReturns = (projData.baseline_projection?.returns || [])
      .map(value => roundProjectionValue(value));

    const currentAssets = Number(projData.current_balances?.total_assets || 0);
    const currentInvestments = Number(projData.current_balances?.total_investments || 0);
    const hasActiveSeriesValue = hasActiveSeries();

    const baselineAssetsProjected = buildProjectedAssetSeries(
      currentAssets,
      baselineSavingsProjected,
      baselineReturns
    );
    const scenarioAssetsProjected = buildProjectedAssetSeries(
      currentAssets,
      scenarioSavingsProjected,
      projectedReturns
    );
    const baselineInvestmentsProjected = (projData.baseline_projection?.investments || [])
      .map(value => roundProjectionValue(value));
    const scenarioInvestmentsProjected = [];
    const scenarioNonInvestedAssetsProjected = [];

    {
      let invRunning = currentInvestments;
      for (let index = 0; index < projMonths.length; index += 1) {
        let naiveInv = roundProjectionValue(
          invRunning + Number(projectedReturns[index] || 0) + Number(projectedContributions[index] || 0)
        );
        const totalAssets = Number(scenarioAssetsProjected[index] || 0);
        let nonInv = roundProjectionValue(totalAssets - naiveInv);
        let inv = naiveInv;

        if (nonInv < 0) {
          inv = roundProjectionValue(inv + nonInv);
          if (inv < 0) inv = 0;
          nonInv = roundProjectionValue(totalAssets - inv);
          if (nonInv < 0) nonInv = 0;
        }

        scenarioInvestmentsProjected.push(inv);
        scenarioNonInvestedAssetsProjected.push(nonInv);
        invRunning = inv;
      }
    }

    const baselineNonInvestedAssetsProjected = baselineAssetsProjected.map((value, index) =>
      roundProjectionValue(Number(value || 0) - Number(baselineInvestmentsProjected[index] || 0))
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
      hasActiveSeries: hasActiveSeriesValue,
    };
  }

  function buildProjectedHealthPoint(month, assets, liabilities, currentAssets, quickAssets, currentLiabilities, essentialExpense) {
    const currentRatio = safeProjectionRatio(currentAssets, currentLiabilities);
    const quickRatio = safeProjectionRatio(quickAssets, currentLiabilities);
    const runwayMonths = essentialExpense > 0
      ? safeProjectionRatio(quickAssets, essentialExpense)
      : null;

    return {
      month,
      assets: roundProjectionValue(assets),
      liabilities: roundProjectionValue(liabilities),
      net_worth: roundProjectionValue(Number(assets || 0) - Number(liabilities || 0)),
      current_assets: roundProjectionValue(currentAssets),
      quick_assets: roundProjectionValue(quickAssets),
      current_liabilities: roundProjectionValue(currentLiabilities),
      current_ratio: currentRatio == null ? null : roundProjectionValue(currentRatio),
      quick_ratio: quickRatio == null ? null : roundProjectionValue(quickRatio),
      monthly_essential_expense: roundProjectionValue(essentialExpense),
      runway_months: runwayMonths == null ? null : roundProjectionValue(runwayMonths),
    };
  }

  function deriveDisplayedHealthSummary(displayState) {
    const projData = getState()?.projData;
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
      roundProjectionValue(
        Number(baselineLiabilities[index] || 0)
        + Number(scenarioLiabilityAdjustments[index] || 0)
      )
    );

    const current = {
      ...currentBackend,
      assets: roundProjectionValue(currentAssetsTotal),
      liabilities: roundProjectionValue(currentLiabilitiesTotal),
      net_worth: roundProjectionValue(currentBackend.net_worth),
      current_assets: roundProjectionValue(currentAssetsBucket),
      quick_assets: roundProjectionValue(currentQuickAssets),
      current_liabilities: roundProjectionValue(currentBackend.current_liabilities || 0),
      monthly_essential_expense: roundProjectionValue(currentBackend.monthly_essential_expense || 0),
    };

    const buildEndPoint = (assetsSeries, expenseSeries, liabilitiesSeries) => {
      if (!displayState.projMonths.length) return current;

      const lastIndex = displayState.projMonths.length - 1;
      const totalAssets = Number(assetsSeries[lastIndex] || currentAssetsTotal);
      const totalLiabilities = Number(liabilitiesSeries[lastIndex] || 0);
      const projectedInvestmentsEnd = Number(projectedInvestments[lastIndex] || currentInvestments);
      const projectedNonInvestmentAssets = totalAssets - projectedInvestmentsEnd;
      const projectedNonInvestmentGrowth = Math.max(0, projectedNonInvestmentAssets - currentNonInvestmentAssets);
      const currentAssetsEnd = currentAssetsBucket + projectedNonInvestmentGrowth;
      const quickAssetsEnd = currentQuickAssets + projectedNonInvestmentGrowth;
      const currentLiabilitiesEnd = totalLiabilities * currentLiabilityShare;
      const essentialExpenseEnd = Math.max(0, Number(expenseSeries[lastIndex] || 0) * essentialExpenseShare);

      return buildProjectedHealthPoint(
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
        : roundProjectionValue(Number(scenarioValue) - Number(baselineValue))
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

  return {
    registerRuntime,
    roundProjectionValue,
    safeProjectionRatio,
    projectedValuesFromSeries,
    buildProjectedAssetSeries,
    buildProjectedInvestmentSeries,
    buildProjectedHealthPoint,
    deriveProjectionDisplayState,
    deriveDisplayedHealthSummary,
  };
})();