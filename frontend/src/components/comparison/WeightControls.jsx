import React, { useState } from 'react';
import { Sliders, RotateCcw, Sparkles, CheckCircle2, Loader2 } from 'lucide-react';

const DIMENSIONS = [
  { id: 'traffic', label: 'Traffic Congestion Mitigation', desc: 'Prioritize lower trip generation and minimal road strain' },
  { id: 'cost', label: 'Fiscal & Capital Prudence', desc: 'Prioritize lower municipal capital investment and annual operating costs' },
  { id: 'environmental', label: 'Environmental Quality & Greenery', desc: 'Prioritize net green space gains and higher permeable surface area' },
  { id: 'accessibility', label: 'Transit & Street Accessibility', desc: 'Prioritize sites near major road networks and bus stops' },
  { id: 'gap_improvement', label: 'Infrastructure Gap Resolution', desc: 'Prioritize amenities addressing the most severe local voids' },
  { id: 'social_utility', label: 'Civic Utility & Employment', desc: 'Prioritize direct local job creation and active community use' },
];

const PRESETS = [
  {
    name: 'Equal / Balanced',
    weights: { traffic: 1, cost: 1, environmental: 1, accessibility: 1, gap_improvement: 1, social_utility: 1 },
  },
  {
    name: 'Green & Health Focus',
    weights: { traffic: 1, cost: 1, environmental: 4, accessibility: 2, gap_improvement: 4, social_utility: 3 },
  },
  {
    name: 'Traffic & Infrastructure',
    weights: { traffic: 4, cost: 1, environmental: 2, accessibility: 4, gap_improvement: 4, social_utility: 2 },
  },
  {
    name: 'Fiscal Prudence',
    weights: { traffic: 2, cost: 5, environmental: 1, accessibility: 1, gap_improvement: 2, social_utility: 1 },
  },
];

export function WeightControls({
  weights,
  onWeightChange,
  onRank,
  ranking = false,
}) {
  const [internalWeights, setInternalWeights] = useState(
    weights || {
      traffic: 1.0,
      cost: 1.0,
      environmental: 1.0,
      accessibility: 1.0,
      gap_improvement: 1.0,
      social_utility: 1.0,
    }
  );

  const totalWeight = Object.values(internalWeights).reduce((sum, v) => sum + (Number(v) || 0), 0);

  const handleSliderChange = (dimId, val) => {
    const next = { ...internalWeights, [dimId]: parseFloat(val) || 0 };
    setInternalWeights(next);
    if (onWeightChange) onWeightChange(next);
  };

  const handleApplyPreset = (presetWeights) => {
    setInternalWeights(presetWeights);
    if (onWeightChange) onWeightChange(presetWeights);
  };

  const handleResetEqual = () => {
    const equal = { traffic: 1.0, cost: 1.0, environmental: 1.0, accessibility: 1.0, gap_improvement: 1.0, social_utility: 1.0 };
    setInternalWeights(equal);
    if (onWeightChange) onWeightChange(equal);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (totalWeight <= 0 || ranking) return;
    onRank(internalWeights);
  };

  return (
    <div className="bg-white rounded-xl shadow-xs border border-slate-200 p-6 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 mb-5 gap-3">
        <div>
          <div className="flex items-center space-x-2 text-blue-600">
            <Sliders className="w-4 h-4" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900">
              Stage 4: Municipal Priority Weighting
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Adjust slider weights according to municipal policy goals. The backend normalizes weights to 100%.
          </p>
        </div>

        {/* Preset Selector */}
        <div className="flex items-center flex-wrap gap-1.5">
          <span className="text-xs text-slate-500 font-medium mr-1">Presets:</span>
          {PRESETS.map((p) => (
            <button
              key={p.name}
              type="button"
              onClick={() => handleApplyPreset(p.weights)}
              className="text-xs px-2.5 py-1 rounded-md border border-slate-200 bg-slate-50 text-slate-700 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-200 font-medium transition-all cursor-pointer"
            >
              {p.name}
            </button>
          ))}
          <button
            type="button"
            onClick={handleResetEqual}
            title="Reset all priority weights to 1.0"
            className="p-1 rounded-md border border-slate-200 bg-slate-50 text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-all cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          {DIMENSIONS.map((dim) => {
            const val = internalWeights[dim.id] ?? 1.0;
            const pct = totalWeight > 0 ? ((val / totalWeight) * 100).toFixed(1) : '0.0';

            return (
              <div
                key={dim.id}
                className="border border-slate-200 rounded-lg p-3.5 bg-slate-50/50 hover:border-slate-300 transition-colors shadow-2xs"
              >
                <div className="flex items-center justify-between mb-1">
                  <label htmlFor={`slider-${dim.id}`} className="text-xs font-bold text-slate-900">
                    {dim.label}
                  </label>
                  <span className="text-xs font-mono font-bold text-blue-800 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                    {val.toFixed(1)} <span className="text-[10px] text-slate-500 font-normal">({pct}%)</span>
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 mb-2 leading-tight">
                  {dim.desc}
                </p>

                <div className="flex items-center space-x-2 pt-1">
                  <span className="text-[10px] font-mono text-slate-400">0</span>
                  <input
                    id={`slider-${dim.id}`}
                    type="range"
                    min="0"
                    max="5"
                    step="0.5"
                    value={val}
                    onChange={(e) => handleSliderChange(dim.id, e.target.value)}
                    className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                    aria-label={`${dim.label} priority weight`}
                  />
                  <span className="text-[10px] font-mono text-slate-400">5</span>
                </div>
              </div>
            );
          })}
        </div>

        {totalWeight <= 0 && (
          <p className="text-xs text-rose-600 mb-3 text-center font-medium">
            At least one priority weight must be greater than zero.
          </p>
        )}

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-4 border-t border-slate-100">
          <span className="text-xs text-slate-500 font-mono">
            Total Raw Weight: <strong className="text-slate-800">{totalWeight.toFixed(1)}</strong> (Relative ratios normalized by backend)
          </span>

          <button
            type="submit"
            disabled={ranking || totalWeight <= 0}
            className={`px-5 py-2.5 rounded-lg text-xs font-bold text-white shadow-xs flex items-center justify-center space-x-2 transition-all cursor-pointer ${
              ranking || totalWeight <= 0
                ? 'bg-slate-400 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-700 active:scale-98'
            }`}
          >
            {ranking ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Calculating Weighted Ranks...</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4" />
                <span>Calculate Scenario Leaderboard</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

export default WeightControls;
