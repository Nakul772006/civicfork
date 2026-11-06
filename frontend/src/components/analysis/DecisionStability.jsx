import React from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  AlertCircle,
  Activity,
  CheckCircle2,
  TrendingUp,
  Scale,
  Award,
  Trees,
  Hospital,
  GraduationCap,
  Car,
  Store,
  Users,
  Bus,
  Layers,
} from 'lucide-react';

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

/**
 * DecisionStability
 * 
 * Executive Decision Stability / Sensitivity Analysis Card.
 * Answers: "How robust is the recommendation when municipal priorities change?"
 * 
 * Evaluates the baseline recommended policy across 7 deterministic municipal
 * priority configurations using the existing CivicFork ranking engine.
 * 
 * Strict presentation boundary: All scores, win counts, and interpretations
 * originate directly from the backend StabilityResult.
 */
export function DecisionStability({ stabilityResult = null, loading = false }) {
  if (loading) {
    return (
      <div className="bg-white rounded-xl shadow-xs border border-slate-200 p-6 mb-6 animate-pulse">
        <div className="h-4 bg-slate-200 rounded w-1/3 mb-3"></div>
        <div className="h-3 bg-slate-100 rounded w-1/2 mb-6"></div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <div className="h-20 bg-slate-100 rounded-lg"></div>
          <div className="h-20 bg-slate-100 rounded-lg"></div>
          <div className="h-20 bg-slate-100 rounded-lg"></div>
          <div className="h-20 bg-slate-100 rounded-lg"></div>
        </div>
      </div>
    );
  }

  if (!stabilityResult) {
    return null;
  }

  const {
    baseline_scenario_id,
    baseline_scenario_name,
    baseline_wins = 0,
    total_configurations = 7,
    stability_score = 0.0,
    stability_level = 'MODERATE',
    strongest_challenger = null,
    interpretation = '',
    configuration_results = [],
    calculation_trace = {},
  } = stabilityResult;

  const BaselineIcon = SCENARIO_ICONS[baseline_scenario_id] || Layers;
  const isHigh = stability_level === 'HIGH';
  const isModerate = stability_level === 'MODERATE';
  const isLow = stability_level === 'LOW';

  return (
    <div className="bg-white rounded-xl shadow-xs border border-slate-200 p-6 mb-6">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 mb-5 gap-2">
        <div>
          <div className="flex items-center space-x-2 text-indigo-600">
            <Activity className="w-5 h-5 text-indigo-600" />
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800">
              Decision Stability
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            How robust is the recommendation when municipal priorities change?
          </p>
        </div>

        <span className="text-[11px] font-mono bg-indigo-50 text-indigo-700 border border-indigo-200 px-2.5 py-1 rounded-full self-start sm:self-auto flex items-center space-x-1.5">
          <Scale className="w-3.5 h-3.5" />
          <span>7 Deterministic Configurations Tested</span>
        </span>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 mb-5">
        {/* Recommended Policy */}
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 flex items-center space-x-3">
          <div className="p-2.5 rounded-lg bg-emerald-100 text-emerald-800 border border-emerald-200 flex-shrink-0">
            <BaselineIcon className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
              Recommended Policy
            </span>
            <span className="text-xs font-bold text-slate-900 truncate block">
              {baseline_scenario_name || SCENARIO_NAMES[baseline_scenario_id] || baseline_scenario_id}
            </span>
            <span className="text-[10px] text-emerald-700 font-semibold flex items-center space-x-1 mt-0.5">
              <Award className="w-3 h-3" />
              <span>Current Rank #1</span>
            </span>
          </div>
        </div>

        {/* Stability Score & Win Rate */}
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
            Stability Score
          </span>
          <div className="flex items-baseline space-x-1.5 mt-0.5">
            <span className="text-2xl font-black font-mono text-slate-900">
              {stability_score.toFixed(1)}%
            </span>
            <span className="text-xs text-slate-500 font-medium">robustness</span>
          </div>
          <span className="text-[11px] font-semibold text-indigo-700 block mt-0.5">
            Wins {baseline_wins} of {total_configurations} priority configurations
          </span>
        </div>

        {/* Stability Classification Badge */}
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 flex flex-col justify-between">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
            Stability Level
          </span>
          <div>
            <span
              className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-lg text-xs font-bold border ${
                isHigh
                  ? 'bg-emerald-100 text-emerald-900 border-emerald-300'
                  : isModerate
                  ? 'bg-amber-100 text-amber-900 border-amber-300'
                  : 'bg-rose-100 text-rose-900 border-rose-300'
              }`}
            >
              {isHigh ? (
                <ShieldCheck className="w-4 h-4 text-emerald-700" />
              ) : isModerate ? (
                <AlertTriangle className="w-4 h-4 text-amber-700" />
              ) : (
                <AlertCircle className="w-4 h-4 text-rose-700" />
              )}
              <span>{stability_level} STABILITY</span>
            </span>
          </div>
          <span className="text-[10px] text-slate-400 mt-1">
            Threshold: {isHigh ? '≥75%' : isModerate ? '50–74%' : '<50%'}
          </span>
        </div>

        {/* Strongest Challenger */}
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
            Strongest Challenger
          </span>
          <div className="mt-1">
            {strongest_challenger ? (
              <>
                <span className="text-xs font-bold text-slate-900 truncate block">
                  {strongest_challenger.scenario_name || SCENARIO_NAMES[strongest_challenger.scenario_id] || strongest_challenger.scenario_id}
                </span>
                <span className="text-[11px] font-mono font-semibold text-slate-600 block mt-0.5">
                  {strongest_challenger.wins > 0
                    ? `Won ${strongest_challenger.wins} alternative configuration${strongest_challenger.wins > 1 ? 's' : ''}`
                    : 'Closest competitor (0 wins)'}
                </span>
              </>
            ) : (
              <span className="text-xs font-semibold text-emerald-700">
                None (Clean sweep across all vectors)
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Deterministic Interpretation Box */}
      <div
        className={`p-3.5 rounded-xl border mb-5 flex items-start space-x-2.5 ${
          isHigh
            ? 'bg-emerald-50/80 border-emerald-200 text-emerald-950'
            : isModerate
            ? 'bg-amber-50/80 border-amber-200 text-amber-950'
            : 'bg-rose-50/80 border-rose-200 text-rose-950'
        }`}
      >
        {isHigh ? (
          <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 flex-shrink-0" />
        ) : isModerate ? (
          <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
        ) : (
          <AlertCircle className="w-4 h-4 text-rose-600 mt-0.5 flex-shrink-0" />
        )}
        <div className="text-xs leading-relaxed">
          <strong className="font-bold">Interpretation: </strong>
          <span>{interpretation}</span>
        </div>
      </div>

      {/* Compact Configuration Breakdown Table */}
      <div className="border border-slate-200 rounded-xl overflow-hidden mb-4">
        <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between text-xs font-semibold text-slate-700">
          <span className="uppercase tracking-wider text-[11px]">
            Municipal Priority Sensitivity Matrix
          </span>
          <span className="text-[11px] text-slate-500 font-mono">
            Evaluated via RankingEngine
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50/50 text-[10px] uppercase font-bold text-slate-500 border-b border-slate-200">
              <tr>
                <th className="py-2 px-3.5">Priority Configuration</th>
                <th className="py-2 px-3.5">Winner</th>
                <th className="py-2 px-3.5 text-center">Winning Score</th>
                <th className="py-2 px-3.5 text-center">Recommended Status</th>
                <th className="py-2 px-3.5 text-right">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {configuration_results.map((cfg) => {
                const isWon = cfg.baseline_won;
                const WinnerIcon = SCENARIO_ICONS[cfg.winning_scenario_id] || Layers;

                return (
                  <tr
                    key={cfg.configuration_id}
                    className={`hover:bg-slate-50/80 transition-colors ${
                      isWon ? '' : 'bg-amber-50/30'
                    }`}
                  >
                    {/* Configuration Name */}
                    <td className="py-2.5 px-3.5 font-medium text-slate-900">
                      {cfg.configuration_name}
                    </td>

                    {/* Winning Scenario */}
                    <td className="py-2.5 px-3.5">
                      <div className="flex items-center space-x-2">
                        <WinnerIcon className="w-3.5 h-3.5 text-slate-600 flex-shrink-0" />
                        <span className="font-semibold text-slate-800 truncate">
                          {cfg.winning_scenario_name || cfg.winning_scenario_id}
                        </span>
                      </div>
                    </td>

                    {/* Winning Score */}
                    <td className="py-2.5 px-3.5 text-center font-mono font-bold text-slate-800">
                      {cfg.winning_score.toFixed(1)}
                    </td>

                    {/* Baseline Status */}
                    <td className="py-2.5 px-3.5 text-center">
                      <span className="font-mono text-[11px] text-slate-600">
                        Rank #{cfg.baseline_rank} ({cfg.baseline_score.toFixed(1)})
                      </span>
                    </td>

                    {/* Outcome Tag */}
                    <td className="py-2.5 px-3.5 text-right">
                      <span
                        className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-bold ${
                          isWon
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {isWon ? (
                          <>
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Recommended Wins</span>
                          </>
                        ) : (
                          <>
                            <TrendingUp className="w-3 h-3" />
                            <span>Challenger Wins</span>
                          </>
                        )}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Provenance & Methodology Disclaimer */}
      <div className="text-[11px] text-slate-400 flex items-start space-x-1.5 pt-1">
        <span className="font-bold text-slate-500 uppercase tracking-wider text-[10px] flex-shrink-0">
          Provenance Note:
        </span>
        <span className="leading-tight">
          {calculation_trace?.disclaimer ||
            'Modelled sensitivity analysis for municipal decision support across 7 deterministic priority configurations; not an empirical forecast of real-world outcomes.'}
        </span>
      </div>
    </div>
  );
}

export default DecisionStability;
