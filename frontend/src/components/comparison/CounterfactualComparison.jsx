import React, { useState, useEffect } from 'react';
import { 
  GitCompare, 
  ArrowRight, 
  ArrowLeftRight, 
  TrendingUp, 
  TrendingDown, 
  Minus, 
  HelpCircle, 
  CheckCircle2, 
  AlertCircle,
  Trees, 
  Hospital, 
  GraduationCap, 
  Car, 
  Store, 
  Users, 
  Bus, 
  Layers,
  Scale,
  Sparkles,
  Info,
  Check,
  Award
} from 'lucide-react';
import { formatScore, getScoreColor } from '../../utils/formatters';

const SCENARIO_ICONS = {
  park: Trees,
  healthcare: Hospital,
  education: GraduationCap,
  parking: Car,
  commercial: Store,
  community_centre: Users,
  public_transport: Bus,
};

const SCENARIO_NAMES = {
  park: 'Parks / Recreational Space',
  healthcare: 'Healthcare Facility',
  education: 'Educational Facility',
  parking: 'Public Parking',
  commercial: 'Commercial Development',
  community_centre: 'Community Centre',
  public_transport: 'Public Transport Facility',
};

const DIMENSION_LABELS = {
  traffic: 'Traffic Impact',
  cost: 'Fiscal / Cost Burden',
  environmental: 'Environmental Quality',
  accessibility: 'Accessibility & Connectivity',
  gap_improvement: 'Infrastructure Gap Closure',
  social_utility: 'Social / Public Utility',
};

export function CounterfactualComparison({
  scenarios = [],
  ranking = [],
  counterfactualResult,
  onCompare,
  loading = false,
  narrative = null,
}) {
  // Defaults: baseline is rank #1 (or first scenario), alternative is rank #2 (or second)
  const defaultBaseline = ranking[0]?.scenario_id || scenarios[0]?.id || 'park';
  const defaultAlternative = ranking[1]?.scenario_id || scenarios[1]?.id || 'healthcare';

  const [baselineId, setBaselineId] = useState(defaultBaseline);
  const [alternativeId, setAlternativeId] = useState(defaultAlternative);
  const [localError, setLocalError] = useState(null);

  // Update defaults when ranking changes if not user-altered
  useEffect(() => {
    if (ranking.length >= 2) {
      setBaselineId(ranking[0].scenario_id);
      setAlternativeId(ranking[1].scenario_id);
    }
  }, [ranking]);

  const handleSwap = () => {
    const temp = baselineId;
    setBaselineId(alternativeId);
    setAlternativeId(temp);
    setLocalError(null);
  };

  const handleBaselineChange = (e) => {
    const nextId = e.target.value;
    setBaselineId(nextId);
    setLocalError(nextId === alternativeId ? 'Please select two different scenarios to compare.' : null);
  };

  const handleAlternativeChange = (e) => {
    const nextId = e.target.value;
    setAlternativeId(nextId);
    setLocalError(nextId === baselineId ? 'Please select two different scenarios to compare.' : null);
  };

  const handleCompareClick = (e) => {
    e.preventDefault();
    if (baselineId === alternativeId) {
      setLocalError('Please select two different scenarios to compare.');
      return;
    }
    setLocalError(null);
    onCompare(baselineId, alternativeId);
  };

  // Available scenarios list
  const scenarioOptions = scenarios.length > 0 ? scenarios : Object.entries(SCENARIO_NAMES).map(([id, name]) => ({ id, name }));

  // Helper to find scenario rank metadata
  const getRankInfo = (scId) => ranking.find((r) => r.scenario_id === scId);

  // Resolution for scenario icons
  const activeBaselineId = counterfactualResult?.scenario_a_id || baselineId;
  const activeAlternativeId = counterfactualResult?.scenario_b_id || alternativeId;

  const BaselineIcon = SCENARIO_ICONS[activeBaselineId] || Layers;
  const AlternativeIcon = SCENARIO_ICONS[activeAlternativeId] || Layers;

  const baselineRank = getRankInfo(activeBaselineId);
  const alternativeRank = getRankInfo(activeAlternativeId);

  // Win counts from existing backend response
  const aWinsCount = counterfactualResult?.a_wins_dimensions?.length || 0;
  const bWinsCount = counterfactualResult?.b_wins_dimensions?.length || 0;
  const neutralCount = counterfactualResult?.neutral_dimensions?.length || 0;
  const totalDimensions = 6;

  // Format decision implication text using precomputed backend counterfactual results
  const getDecisionImplication = () => {
    if (!counterfactualResult) return null;

    const {
      scenario_a_name,
      scenario_b_name,
      a_wins_dimensions = [],
      b_wins_dimensions = [],
      net_delta,
      verdict,
    } = counterfactualResult;

    const formatDimList = (dims) =>
      dims.map((d) => DIMENSION_LABELS[d] || d.replace(/_/g, ' ')).join(', ');

    const aWinsFormatted = a_wins_dimensions.length > 0 ? formatDimList(a_wins_dimensions) : 'none';
    const bWinsFormatted = b_wins_dimensions.length > 0 ? formatDimList(b_wins_dimensions) : 'none';

    if (verdict === 'meaningfully_better') {
      return `${scenario_b_name} provides the stronger overall trade-off (+${net_delta.toFixed(1)} pts net delta) under current planning priorities, with clear advantages in ${bWinsFormatted}.${a_wins_dimensions.length > 0 ? ` ${scenario_a_name} maintains superior performance in ${aWinsFormatted}.` : ''}`;
    }

    if (verdict === 'meaningfully_worse') {
      return `${scenario_a_name} maintains the superior overall policy trade-off (${net_delta.toFixed(1)} pts net delta), outperforming ${scenario_b_name} in ${aWinsFormatted}.${b_wins_dimensions.length > 0 ? ` ${scenario_b_name} offers localized advantages in ${bWinsFormatted}.` : ''}`;
    }

    return `Both ${scenario_a_name} and ${scenario_b_name} demonstrate practically equivalent overall performance across the 6 dimensions (net delta ${net_delta >= 0 ? '+' : ''}${net_delta.toFixed(1)} pts). Municipal planners should weigh specific neighborhood priorities and budget phasing.`;
  };

  const decisionImplication = getDecisionImplication();

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 mb-5 gap-2">
        <div>
          <div className="flex items-center space-x-2 text-indigo-600">
            <GitCompare className="w-5 h-5" />
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800">
              Counterfactual Decision Center
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Evaluate side-by-side trade-offs: &ldquo;What happens if we choose the alternative policy instead?&rdquo;
          </p>
        </div>

        <span className="text-[11px] font-mono bg-indigo-50 text-indigo-700 border border-indigo-200 px-2.5 py-1 rounded-full self-start sm:self-auto">
          Δ = Alternative (B) − Baseline (A)
        </span>
      </div>

      {/* Scenario Pair Selectors Form */}
      <form onSubmit={handleCompareClick} className="bg-slate-50 border border-slate-200 rounded-xl p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-center">
          {/* Baseline Scenario Selector (2 cols) */}
          <div className="md:col-span-2">
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5 flex items-center space-x-1.5">
              <span className="w-2 h-2 rounded-full bg-blue-600"></span>
              <span>Baseline Choice (Current / Benchmark)</span>
            </label>
            <div className="relative">
              <select
                value={baselineId}
                onChange={handleBaselineChange}
                className="w-full pl-3 pr-10 py-2.5 bg-white text-xs font-semibold text-slate-900 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 shadow-xs"
              >
                {scenarioOptions.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} {ranking.find((r) => r.scenario_id === s.id) ? `(Rank #${ranking.find((r) => r.scenario_id === s.id).rank})` : ''}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Swap Button (1 col) */}
          <div className="flex justify-center md:pt-5">
            <button
              type="button"
              onClick={handleSwap}
              title="Swap baseline and alternative"
              className="p-2 rounded-lg bg-white border border-slate-300 text-slate-600 hover:text-indigo-600 hover:border-indigo-300 transition-colors shadow-xs"
            >
              <ArrowLeftRight className="w-4 h-4" />
            </button>
          </div>

          {/* Alternative Scenario Selector (2 cols) */}
          <div className="md:col-span-2">
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5 flex items-center space-x-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-600"></span>
              <span>Alternative Choice (&ldquo;What if instead...&rdquo;)</span>
            </label>
            <div className="relative">
              <select
                value={alternativeId}
                onChange={handleAlternativeChange}
                className="w-full pl-3 pr-10 py-2.5 bg-white text-xs font-semibold text-slate-900 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 shadow-xs"
              >
                {scenarioOptions.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} {ranking.find((r) => r.scenario_id === s.id) ? `(Rank #${ranking.find((r) => r.scenario_id === s.id).rank})` : ''}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Local Validation Error */}
        {localError && (
          <div className="mt-3 text-xs text-rose-600 flex items-center space-x-1.5">
            <AlertCircle className="w-4 h-4" />
            <span>{localError}</span>
          </div>
        )}

        {/* Submit Compare Button */}
        <div className="mt-4 pt-3 border-t border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <p className="text-[11px] text-slate-500">
            Compare competing municipal policies across all 6 impact dimensions using the approved &plusmn;2.0 pts neutrality threshold.
          </p>

          <button
            type="submit"
            disabled={loading || baselineId === alternativeId}
            className={`px-5 py-2.5 rounded-xl text-xs font-bold text-white shadow-sm flex items-center justify-center space-x-2 transition-all ${
              loading || baselineId === alternativeId
                ? 'bg-slate-400 cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-700 active:scale-95 shadow-indigo-500/20'
            }`}
          >
            <Scale className="w-4 h-4" />
            <span>{loading ? 'Evaluating Counterfactual...' : 'Compare Alternatives'}</span>
          </button>
        </div>
      </form>

      {/* Counterfactual Results Display */}
      {counterfactualResult && (
        <div className="space-y-6 animate-in fade-in duration-300">
          {/* 1. EXECUTIVE "WHAT IF?" HERO */}
          <div className="p-5 sm:p-6 rounded-2xl border border-indigo-100 bg-gradient-to-br from-indigo-50/60 via-slate-50/40 to-purple-50/30">
            {/* Hero Header */}
            <div className="text-center mb-5">
              <span className="text-[11px] font-extrabold tracking-widest uppercase text-indigo-700 block mb-1">
                EXECUTIVE DECISION INQUIRY
              </span>
              <h3 className="text-xl sm:text-2xl font-black tracking-tight text-slate-900">
                WHAT IF WE CHOOSE THIS POLICY INSTEAD?
              </h3>
              <p className="text-xs text-slate-500 mt-1 max-w-xl mx-auto">
                Compare two urban policy alternatives before implementation.
              </p>
            </div>

            {/* Two Scenario Comparison Cards + VS Pill */}
            <div className="grid grid-cols-1 md:grid-cols-11 gap-3 items-center">
              {/* BASELINE CARD (5 cols) */}
              <div className="md:col-span-5 bg-white border-2 border-blue-200/90 rounded-xl p-4 shadow-xs">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-bold tracking-wider px-2 py-0.5 rounded-md bg-blue-100 text-blue-800 uppercase">
                    BASELINE (A)
                  </span>
                  {baselineRank && (
                    <span className="text-[11px] font-bold text-blue-700">
                      Rank #{baselineRank.rank}
                    </span>
                  )}
                </div>
                <div className="flex items-start space-x-3 mt-1">
                  <div className="p-2 rounded-lg bg-blue-50 text-blue-600 border border-blue-200 flex-shrink-0 mt-0.5">
                    <BaselineIcon className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-sm sm:text-base font-bold text-slate-900 leading-snug">
                      {counterfactualResult.scenario_a_name}
                    </h4>
                    <p className="text-xs text-slate-500 mt-1">
                      Composite Score:{' '}
                      <strong className="text-slate-800 font-mono">
                        {baselineRank ? `${baselineRank.weighted_score.toFixed(1)} / 100` : 'Evaluated'}
                      </strong>
                    </p>
                  </div>
                </div>
              </div>

              {/* VERSUS PILL (1 col) */}
              <div className="md:col-span-1 flex justify-center py-1 md:py-0">
                <div className="w-10 h-10 rounded-full bg-slate-900 text-white font-extrabold text-xs flex items-center justify-center shadow-md border-2 border-white flex-shrink-0">
                  VS
                </div>
              </div>

              {/* ALTERNATIVE CARD (5 cols) */}
              <div className="md:col-span-5 bg-white border-2 border-emerald-200/90 rounded-xl p-4 shadow-xs">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-bold tracking-wider px-2 py-0.5 rounded-md bg-emerald-100 text-emerald-800 uppercase">
                    ALTERNATIVE (B)
                  </span>
                  {alternativeRank && (
                    <span className="text-[11px] font-bold text-emerald-700">
                      Rank #{alternativeRank.rank}
                    </span>
                  )}
                </div>
                <div className="flex items-start space-x-3 mt-1">
                  <div className="p-2 rounded-lg bg-emerald-50 text-emerald-600 border border-emerald-200 flex-shrink-0 mt-0.5">
                    <AlternativeIcon className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-sm sm:text-base font-bold text-slate-900 leading-snug">
                      {counterfactualResult.scenario_b_name}
                    </h4>
                    <p className="text-xs text-slate-500 mt-1">
                      Composite Score:{' '}
                      <strong className="text-slate-800 font-mono">
                        {alternativeRank ? `${alternativeRank.weighted_score.toFixed(1)} / 100` : 'Evaluated'}
                      </strong>
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 2. PROMINENT VERDICT BANNER */}
          <div
            className={`p-5 rounded-xl border-2 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xs ${
              counterfactualResult.verdict === 'meaningfully_better'
                ? 'bg-emerald-50/90 border-emerald-300 text-emerald-950'
                : counterfactualResult.verdict === 'meaningfully_worse'
                ? 'bg-rose-50/90 border-rose-300 text-rose-950'
                : 'bg-slate-50/90 border-slate-300 text-slate-900'
            }`}
          >
            <div className="flex items-start space-x-3.5">
              <div
                className={`p-2.5 rounded-xl text-white shadow-xs mt-0.5 ${
                  counterfactualResult.verdict === 'meaningfully_better'
                    ? 'bg-emerald-600'
                    : counterfactualResult.verdict === 'meaningfully_worse'
                    ? 'bg-rose-600'
                    : 'bg-slate-600'
                }`}
              >
                {counterfactualResult.verdict === 'meaningfully_better' ? (
                  <TrendingUp className="w-6 h-6" />
                ) : counterfactualResult.verdict === 'meaningfully_worse' ? (
                  <TrendingDown className="w-6 h-6" />
                ) : (
                  <Minus className="w-6 h-6" />
                )}
              </div>

              <div>
                <div className="flex items-center space-x-2 mb-1">
                  <span
                    className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${
                      counterfactualResult.verdict === 'meaningfully_better'
                        ? 'bg-emerald-200/80 text-emerald-900 border-emerald-300'
                        : counterfactualResult.verdict === 'meaningfully_worse'
                        ? 'bg-rose-200/80 text-rose-900 border-rose-300'
                        : 'bg-slate-200 text-slate-800 border-slate-300'
                    }`}
                  >
                    Verdict:{' '}
                    {counterfactualResult.verdict === 'meaningfully_better'
                      ? 'Meaningfully Better'
                      : counterfactualResult.verdict === 'meaningfully_worse'
                      ? 'Meaningfully Worse'
                      : 'Practically Equivalent'}
                  </span>
                </div>
                <h3 className="text-base sm:text-lg font-black leading-tight">
                  {counterfactualResult.verdict === 'meaningfully_better'
                    ? `${counterfactualResult.scenario_b_name.toUpperCase()} IS THE STRONGER ALTERNATIVE`
                    : counterfactualResult.verdict === 'meaningfully_worse'
                    ? `${counterfactualResult.scenario_a_name.toUpperCase()} REMAINS THE STRONGER OPTION`
                    : 'PRACTICALLY EQUIVALENT MULTI-CRITERIA PERFORMANCE'}
                </h3>
                <p className="text-xs opacity-90 mt-1 font-medium">
                  {counterfactualResult.headline}
                </p>
                <p className="text-[11px] opacity-75 mt-0.5">
                  {counterfactualResult.verdict === 'meaningfully_better'
                    ? `${bWinsCount} of 6 dimensions favor ${counterfactualResult.scenario_b_name}`
                    : counterfactualResult.verdict === 'meaningfully_worse'
                    ? `${aWinsCount} of 6 dimensions favor ${counterfactualResult.scenario_a_name}`
                    : 'Performance deltas remain within the approved ±2.0 pts neutrality threshold across all dimensions'}
                </p>
              </div>
            </div>

            {/* Net Trade-off Delta Pill */}
            <div className="bg-white/95 backdrop-blur-xs border border-inherit rounded-xl p-3.5 text-right self-start md:self-auto flex-shrink-0 shadow-2xs">
              <span className="text-[10px] text-slate-500 uppercase block font-bold tracking-wider">
                Unweighted Trade-off Delta
              </span>
              <span
                className={`text-2xl sm:text-3xl font-black font-mono block ${
                  counterfactualResult.net_delta > 2.0
                    ? 'text-emerald-700'
                    : counterfactualResult.net_delta < -2.0
                    ? 'text-rose-700'
                    : 'text-slate-700'
                }`}
              >
                {counterfactualResult.net_delta > 0
                  ? `+${counterfactualResult.net_delta.toFixed(1)}`
                  : counterfactualResult.net_delta.toFixed(1)}{' '}
                <span className="text-xs text-slate-500 font-semibold">pts</span>
              </span>
              <span className="text-[10px] text-slate-400 block mt-0.5">
                Sum of 6 dimension score deltas
              </span>
            </div>
          </div>

          {/* 3. WIN DISTRIBUTION BAR */}
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-2.5 gap-1">
              <span className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center space-x-1.5">
                <Scale className="w-3.5 h-3.5 text-indigo-600" />
                <span>Dimension Win Distribution</span>
              </span>
              <span className="text-[11px] text-slate-500">
                6 Total Evaluated Impact Dimensions
              </span>
            </div>

            {/* Segmented Horizontal Comparison Bar */}
            <div className="w-full h-3 rounded-full bg-slate-200 overflow-hidden flex shadow-inner mb-3">
              {aWinsCount > 0 && (
                <div
                  style={{ width: `${(aWinsCount / totalDimensions) * 100}%` }}
                  className="bg-blue-600 h-full transition-all"
                  title={`Baseline (${counterfactualResult.scenario_a_name}) wins ${aWinsCount} dimensions`}
                />
              )}
              {neutralCount > 0 && (
                <div
                  style={{ width: `${(neutralCount / totalDimensions) * 100}%` }}
                  className="bg-slate-400 h-full transition-all"
                  title={`Neutral on ${neutralCount} dimensions`}
                />
              )}
              {bWinsCount > 0 && (
                <div
                  style={{ width: `${(bWinsCount / totalDimensions) * 100}%` }}
                  className="bg-emerald-600 h-full transition-all"
                  title={`Alternative (${counterfactualResult.scenario_b_name}) wins ${bWinsCount} dimensions`}
                />
              )}
            </div>

            {/* Numeric Win Badges */}
            <div className="grid grid-cols-3 gap-2.5 text-center text-xs">
              <div className="bg-white border border-blue-200 rounded-lg p-2 shadow-2xs">
                <span className="text-blue-900 font-extrabold text-sm block">
                  {aWinsCount}
                </span>
                <span className="text-[11px] text-blue-700 font-medium truncate block">
                  {counterfactualResult.scenario_a_name}
                </span>
                <span className="text-[10px] text-blue-500">Baseline Wins</span>
              </div>

              <div className="bg-white border border-slate-200 rounded-lg p-2 shadow-2xs">
                <span className="text-slate-800 font-extrabold text-sm block">
                  {neutralCount}
                </span>
                <span className="text-[11px] text-slate-600 font-medium block">
                  Neutral (±2 pts)
                </span>
                <span className="text-[10px] text-slate-400">Equivalent</span>
              </div>

              <div className="bg-white border border-emerald-200 rounded-lg p-2 shadow-2xs">
                <span className="text-emerald-900 font-extrabold text-sm block">
                  {bWinsCount}
                </span>
                <span className="text-[11px] text-emerald-700 font-medium truncate block">
                  {counterfactualResult.scenario_b_name}
                </span>
                <span className="text-[10px] text-emerald-500">Alternative Wins</span>
              </div>
            </div>
          </div>

          {/* 4. DECISION IMPLICATION CALLOUT */}
          {decisionImplication && (
            <div className="p-4 rounded-xl border border-indigo-200 bg-indigo-50/40 text-xs text-slate-800 shadow-2xs">
              <div className="flex items-start space-x-2.5">
                <div className="p-1.5 rounded-lg bg-indigo-600 text-white mt-0.5 flex-shrink-0">
                  <Sparkles className="w-3.5 h-3.5" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-indigo-950 uppercase tracking-wider mb-1">
                    DECISION IMPLICATION
                  </h4>
                  <p className="text-xs text-slate-700 leading-relaxed font-normal">
                    &ldquo;{decisionImplication}&rdquo;
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* 5. DETAILED SIX-DIMENSION COMPARISON TABLE */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                Detailed Dimension-by-Dimension Evidence
              </h4>
              <span className="text-[11px] text-slate-400 font-mono">
                Neutrality Buffer: &plusmn;2.0 pts
              </span>
            </div>

            <div className="overflow-x-auto border border-slate-200 rounded-xl shadow-2xs">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-slate-700 font-bold">
                    <th className="py-3 px-3">Impact Dimension</th>
                    <th className="py-3 px-3 text-center">
                      Baseline: {counterfactualResult.scenario_a_name}
                    </th>
                    <th className="py-3 px-3 text-center">
                      Alternative: {counterfactualResult.scenario_b_name}
                    </th>
                    <th className="py-3 px-3 text-center">Delta (&Delta; = B − A)</th>
                    <th className="py-3 px-3">Impact Trade-Off Explanation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {counterfactualResult.deltas.map((d) => {
                    const isAlternativeBetter = d.direction === 'b_better';
                    const isBaselineBetter = d.direction === 'a_better';
                    const isNeutral = d.direction === 'neutral';

                    return (
                      <tr key={d.dimension} className="hover:bg-slate-50/80 transition-colors">
                        <td className="py-3 px-3 font-semibold text-slate-900">
                          {DIMENSION_LABELS[d.dimension] || d.dimension}
                        </td>

                        <td className="py-3 px-3 text-center font-mono font-medium">
                          <span
                            className={`inline-block px-2.5 py-0.5 rounded text-xs border ${getScoreColor(
                              d.score_a
                            )}`}
                          >
                            {formatScore(d.score_a)}
                          </span>
                        </td>

                        <td className="py-3 px-3 text-center font-mono font-medium">
                          <span
                            className={`inline-block px-2.5 py-0.5 rounded text-xs border ${getScoreColor(
                              d.score_b
                            )}`}
                          >
                            {formatScore(d.score_b)}
                          </span>
                        </td>

                        {/* Enhanced Delta Badge: Color + Icon + Explicit Text Label */}
                        <td className="py-3 px-3 text-center">
                          <span
                            className={`inline-flex items-center space-x-1.5 font-mono font-bold px-2.5 py-1 rounded-full text-xs border shadow-2xs ${
                              isAlternativeBetter
                                ? 'bg-emerald-100 text-emerald-900 border-emerald-300'
                                : isBaselineBetter
                                ? 'bg-rose-100 text-rose-900 border-rose-300'
                                : 'bg-slate-100 text-slate-700 border-slate-300'
                            }`}
                          >
                            {isAlternativeBetter && <TrendingUp className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />}
                            {isBaselineBetter && <TrendingDown className="w-3.5 h-3.5 text-rose-600 flex-shrink-0" />}
                            {isNeutral && <Minus className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />}
                            <span>
                              {d.delta > 0 ? `+${d.delta.toFixed(1)}` : d.delta.toFixed(1)}
                            </span>
                            <span className="text-[10px] font-sans font-semibold opacity-80">
                              {isAlternativeBetter
                                ? 'Alt advantage'
                                : isBaselineBetter
                                ? 'Base advantage'
                                : 'Neutral'}
                            </span>
                          </span>
                        </td>

                        {/* Enhanced Trade-off Explanation */}
                        <td className="py-3 px-3 text-slate-700 text-xs leading-relaxed">
                          {isAlternativeBetter && (
                            <span className="text-emerald-950 font-bold block text-xs">
                              Alternative gains +{d.abs_delta.toFixed(1)} pts ({d.magnitude} advantage)
                            </span>
                          )}
                          {isBaselineBetter && (
                            <span className="text-rose-950 font-bold block text-xs">
                              Baseline gains +{d.abs_delta.toFixed(1)} pts (Alternative loses {d.magnitude})
                            </span>
                          )}
                          {isNeutral && (
                            <span className="text-slate-600 font-semibold italic block text-xs">
                              Practically equivalent (&Delta; within &plusmn;2.0 pts threshold)
                            </span>
                          )}
                          <span className="text-slate-500 text-[11px] block mt-0.5 leading-normal">
                            {d.explanation_b_summary || d.explanation_a_summary}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* 6. "WHY THIS MATTERS" CALLOUT */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700">
            <div className="flex items-start space-x-2.5">
              <div className="p-1.5 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-700 mt-0.5 flex-shrink-0">
                <Info className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-0.5">
                  WHY THIS MATTERS
                </h4>
                <p className="text-xs text-slate-600 leading-relaxed">
                  CivicFork does not simply recommend what to build. It compares competing urban policy choices and shows the trade-offs of choosing one alternative over another.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default CounterfactualComparison;
