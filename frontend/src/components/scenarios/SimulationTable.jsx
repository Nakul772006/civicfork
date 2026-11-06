import React from 'react';
import { 
  BarChart3, 
  HelpCircle, 
  ArrowRight, 
  TrendingUp,
  Layers,
  Trees,
  Hospital,
  GraduationCap,
  Car,
  Store,
  Users,
  Bus
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

const DIMENSIONS = [
  { id: 'traffic', label: 'Traffic', tip: 'Higher = lower traffic congestion' },
  { id: 'cost', label: 'Cost', tip: 'Higher = lower fiscal / operational burden' },
  { id: 'environmental', label: 'Environmental', tip: 'Higher = higher green cover & permeability' },
  { id: 'accessibility', label: 'Accessibility', tip: 'Higher = better transit & road proximity' },
  { id: 'gap_improvement', label: 'Gap Closure', tip: 'Higher = closes more acute infrastructure gaps' },
  { id: 'social_utility', label: 'Social Utility', tip: 'Higher = more jobs & civic visitor benefit' },
];

export function SimulationTable({
  scoreMatrix,
  scenarios = [],
  onProceedToRank,
}) {
  if (!scoreMatrix) return null;

  const scenarioScores = scoreMatrix.scenario_scores || [];

  return (
    <div className="bg-white rounded-xl shadow-xs border border-slate-200 p-6 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 mb-5 gap-3">
        <div>
          <div className="flex items-center space-x-2 text-blue-600">
            <BarChart3 className="w-4 h-4" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900">
              Stage 3: Impact Simulation Matrix (6 Dimensions × 7 Scenarios)
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Normalized 0–100 scale across all performance dimensions (higher is always better).
          </p>
        </div>

        {onProceedToRank && (
          <button
            type="button"
            onClick={onProceedToRank}
            className="px-4 py-2 rounded-lg text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 active:scale-98 transition-all shadow-xs flex items-center space-x-2 cursor-pointer self-start sm:self-auto"
          >
            <span>Proceed to Priority Ranking</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Responsive Score Table */}
      <div className="overflow-x-auto rounded-lg border border-slate-200 shadow-2xs">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-slate-700 font-bold">
              <th className="py-3 px-3 min-w-[200px]">Policy Alternative</th>
              {DIMENSIONS.map((d) => (
                <th key={d.id} className="py-3 px-2 text-center font-semibold" title={d.tip}>
                  <div className="flex items-center justify-center space-x-1">
                    <span>{d.label}</span>
                  </div>
                </th>
              ))}
              <th className="py-3 px-3 text-center bg-slate-100 text-slate-900 font-bold border-l border-slate-200" title="Arithmetic mean (unweighted baseline)">
                Unweighted Mean
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {scenarioScores.map((row) => {
              const sid = row.scenario_id;
              const Icon = SCENARIO_ICONS[sid] || Layers;
              const name = SCENARIO_NAMES[sid] || sid;

              // Map dimension scores by dimension key
              const scoreMap = {};
              if (row.scores) {
                row.scores.forEach((ds) => {
                  scoreMap[ds.dimension] = ds.score;
                });
              }

              return (
                <tr key={sid} className="hover:bg-slate-50/70 transition-colors">
                  <td className="py-2.5 px-3">
                    <div className="flex items-center space-x-2.5">
                      <div className="p-1.5 rounded-md bg-slate-100 text-slate-700 border border-slate-200/60 flex-shrink-0">
                        <Icon className="w-3.5 h-3.5" />
                      </div>
                      <span className="font-semibold text-slate-900">{name}</span>
                    </div>
                  </td>

                  {DIMENSIONS.map((dim) => {
                    const score = scoreMap[dim.id];
                    return (
                      <td key={dim.id} className="py-2.5 px-2 text-center">
                        <span
                          className={`inline-block min-w-[46px] px-2 py-0.5 rounded text-xs font-mono font-semibold border ${getScoreColor(
                            score
                          )}`}
                        >
                          {formatScore(score)}
                        </span>
                      </td>
                    );
                  })}

                  <td className="py-2.5 px-3 text-center bg-slate-50/50 font-mono font-bold text-slate-900 border-l border-slate-200">
                    {formatScore(row.unweighted_composite)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Explanatory Footnote */}
      <div className="mt-4 text-[11px] text-slate-500 bg-slate-50 p-3 rounded-lg border border-slate-200 flex items-start space-x-2">
        <HelpCircle className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
        <span>
          <strong>Methodology Note:</strong> Unweighted Mean is purely descriptive. Official decision-support ranking occurs at the next stage using municipal priority sliders. All dimension calculations are completely deterministic without stochastic variance.
        </span>
      </div>
    </div>
  );
}

export default SimulationTable;
