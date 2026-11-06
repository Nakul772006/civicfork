import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  LabelList,
} from 'recharts';
import { Scale, Info, Award, CheckCircle2, AlertCircle } from 'lucide-react';

const DIMENSIONS = [
  { key: 'traffic', label: 'Traffic' },
  { key: 'cost', label: 'Cost' },
  { key: 'environmental', label: 'Environmental' },
  { key: 'accessibility', label: 'Accessibility' },
  { key: 'gap_improvement', label: 'Gap Improvement' },
  { key: 'social_utility', label: 'Social Utility' },
];

/**
 * Custom tooltip for top-two impact profile comparison.
 */
function ImpactComparisonTooltip({ active, payload, recName, runName }) {
  if (!active || !payload || payload.length === 0) return null;
  const item = payload[0].payload;

  return (
    <div className="bg-slate-900 text-white text-xs rounded-xl p-3.5 shadow-xl border border-slate-800 z-50">
      <div className="font-bold text-slate-100 flex items-center justify-between gap-4 mb-2 pb-1.5 border-b border-slate-800">
        <span className="text-sm font-semibold">{item.dimension}</span>
        <span className="text-[10px] font-mono text-slate-400">0–100 scale</span>
      </div>

      <div className="space-y-1.5 text-slate-300">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded bg-emerald-500 inline-block"></span>
            <span className="font-medium text-emerald-300">{recName} (Rec):</span>
          </div>
          <span className="font-mono font-bold text-white">{item.recommendedFormatted}</span>
        </div>

        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded bg-blue-500 inline-block"></span>
            <span className="font-medium text-blue-300">{runName} (Runner-up):</span>
          </div>
          <span className="font-mono font-bold text-white">{item.runnerUpFormatted}</span>
        </div>

        <div className="pt-1.5 border-t border-slate-800 flex items-center justify-between text-[11px]">
          <span className="text-slate-400">Advantage:</span>
          <span
            className={`font-mono font-bold ${
              item.diff > 0
                ? 'text-emerald-400'
                : item.diff < 0
                ? 'text-blue-400'
                : 'text-slate-300'
            }`}
          >
            {item.diff > 0
              ? `+${item.diff.toFixed(1)} pts (${recName})`
              : item.diff < 0
              ? `+${Math.abs(item.diff).toFixed(1)} pts (${runName})`
              : 'Tie (0.0)'}
          </span>
        </div>
      </div>
    </div>
  );
}

/**
 * ImpactComparisonChart
 * 
 * Grouped horizontal bar chart comparing the Current Rank #1 Recommended Scenario
 * vs Current Rank #2 Runner-up Scenario across all 6 normalized impact dimensions.
 * 
 * Strict boundary: Read-only presentation of pre-calculated backend score matrix.
 */
export function ImpactComparisonChart({
  ranking = [],
  scoreMatrix = null,
  loading = false,
}) {
  // Empty state handling: No ranking at all
  if (!ranking || ranking.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
        <div className="flex items-center space-x-2 text-slate-400 mb-2">
          <Scale className="w-5 h-5" />
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">
            Why the Recommendation Wins
          </h2>
        </div>
        <div className="p-8 text-center bg-slate-50 border border-slate-200 border-dashed rounded-lg">
          <Info className="w-6 h-6 text-slate-400 mx-auto mb-2" />
          <p className="text-xs text-slate-500 font-medium">
            Impact profile comparison unavailable. Run scenario simulation and ranking to compare top alternatives.
          </p>
        </div>
      </div>
    );
  }

  // Edge state: Only 1 scenario available
  if (ranking.length === 1) {
    const singleScenario = ranking[0];
    return (
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
        <div className="flex items-center space-x-2 text-blue-600 mb-2">
          <Scale className="w-5 h-5 text-blue-600" />
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800">
            Why the Recommendation Wins
          </h2>
        </div>
        <div className="p-6 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-600 space-y-2">
          <p className="font-semibold text-slate-800">
            Only one policy alternative is currently available: {singleScenario.scenario_name} (#{singleScenario.rank}).
          </p>
          <p className="text-slate-500">
            A runner-up comparison chart requires at least two ranked policy scenarios. Please ensure multiple scenarios are evaluated.
          </p>
        </div>
      </div>
    );
  }

  // Top two scenarios from current dynamic ranking
  const recommended = ranking[0];
  const runnerUp = ranking[1];

  // Resolve raw dimension scores for each scenario from scoreMatrix.scenario_scores
  const recScoreMap = {};
  const runScoreMap = {};

  if (scoreMatrix?.scenario_scores) {
    const recScores = scoreMatrix.scenario_scores.find((s) => s.scenario_id === recommended.scenario_id);
    if (recScores?.scores) {
      recScores.scores.forEach((ds) => {
        recScoreMap[ds.dimension] = ds.score;
      });
    }
    const runScores = scoreMatrix.scenario_scores.find((s) => s.scenario_id === runnerUp.scenario_id);
    if (runScores?.scores) {
      runScores.scores.forEach((ds) => {
        runScoreMap[ds.dimension] = ds.score;
      });
    }
  }

  // Prepare grouped horizontal bar chart data
  const chartData = DIMENSIONS.map(({ key, label }) => {
    const recVal = Number(recScoreMap[key] ?? 0);
    const runVal = Number(runScoreMap[key] ?? 0);
    const diff = Number((recVal - runVal).toFixed(1));

    return {
      dimension: label,
      dimensionKey: key,
      recommended: recVal,
      runnerUp: runVal,
      recommendedFormatted: recVal.toFixed(1),
      runnerUpFormatted: runVal.toFixed(1),
      diff,
      winner: diff > 0 ? 'recommended' : diff < 0 ? 'runnerUp' : 'tie',
    };
  });

  // Calculate dimension win counts for executive takeaway
  const recWins = chartData.filter((d) => d.winner === 'recommended');
  const runWins = chartData.filter((d) => d.winner === 'runnerUp');
  const ties = chartData.filter((d) => d.winner === 'tie');

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 mb-5 gap-2">
        <div>
          <div className="flex items-center space-x-2 text-blue-600">
            <Scale className="w-4 h-4 text-emerald-600" />
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800">
              Why the Recommendation Wins
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Impact profile of the top two policy alternatives
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono text-slate-500 bg-slate-50 border border-slate-200 px-3 py-1 rounded-lg self-start sm:self-auto">
          <span>Rank #1 vs Rank #2</span>
        </div>
      </div>

      {/* Accessible Dynamic Legend (Non-color reliant with rank badges and status) */}
      <div className="flex flex-wrap items-center gap-3 p-3 bg-slate-50/80 border border-slate-200 rounded-lg mb-5 text-xs">
        <div className="flex items-center space-x-2">
          <span className="w-4 h-4 rounded bg-emerald-600 inline-flex items-center justify-center text-white text-[10px] font-bold font-mono">
            1
          </span>
          <span className="font-bold text-slate-800">{recommended.scenario_name}</span>
          <span className="bg-emerald-100 text-emerald-800 text-[10px] font-bold px-2 py-0.5 rounded-full border border-emerald-300 uppercase tracking-wider">
            Recommended
          </span>
        </div>

        <div className="flex items-center space-x-2">
          <span className="w-4 h-4 rounded bg-blue-600 inline-flex items-center justify-center text-white text-[10px] font-bold font-mono">
            2
          </span>
          <span className="font-bold text-slate-800">{runnerUp.scenario_name}</span>
          <span className="bg-blue-100 text-blue-800 text-[10px] font-bold px-2 py-0.5 rounded-full border border-blue-300 uppercase tracking-wider">
            Runner-up
          </span>
        </div>

        <span className="text-slate-400 font-mono text-[11px] ml-auto hidden md:inline">
          6 Evaluated Dimensions (0–100, Higher = Better)
        </span>
      </div>

      {/* Recharts Grouped Horizontal Bar Chart */}
      <div className="w-full h-[340px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            layout="vertical"
            data={chartData}
            margin={{ top: 8, right: 38, left: 10, bottom: 8 }}
            barGap={3}
            barCategoryGap={12}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              horizontal={false}
              stroke="#e2e8f0"
            />
            <XAxis
              type="number"
              domain={[0, 100]}
              tickCount={6}
              tick={{ fontSize: 11, fill: '#64748b' }}
              axisLine={{ stroke: '#cbd5e1' }}
            />
            <YAxis
              type="category"
              dataKey="dimension"
              width={120}
              tick={{ fontSize: 12, fill: '#1e293b', fontWeight: 500 }}
              axisLine={{ stroke: '#cbd5e1' }}
            />
            <Tooltip
              content={
                <ImpactComparisonTooltip
                  recName={recommended.scenario_name}
                  runName={runnerUp.scenario_name}
                />
              }
              cursor={{ fill: '#f1f5f9' }}
            />
            <Bar
              dataKey="recommended"
              name={`${recommended.scenario_name} (Recommended)`}
              fill="#059669"
              radius={[0, 4, 4, 0]}
              barSize={14}
              animationDuration={500}
            >
              <LabelList
                dataKey="recommendedFormatted"
                position="right"
                style={{
                  fontSize: 10,
                  fill: '#065f46',
                  fontWeight: 'bold',
                  fontFamily: 'monospace',
                }}
              />
            </Bar>
            <Bar
              dataKey="runnerUp"
              name={`${runnerUp.scenario_name} (Runner-up)`}
              fill="#3b82f6"
              radius={[0, 4, 4, 0]}
              barSize={14}
              animationDuration={500}
            >
              <LabelList
                dataKey="runnerUpFormatted"
                position="right"
                style={{
                  fontSize: 10,
                  fill: '#1e40af',
                  fontWeight: 'bold',
                  fontFamily: 'monospace',
                }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Executive Dimension Summary Callout */}
      <div className="mt-4 p-3.5 bg-slate-50 rounded-xl border border-slate-200 text-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span className="text-slate-800">
              <strong>{recommended.scenario_name}</strong> outperforms runner-up on{' '}
              <strong className="text-emerald-700">{recWins.length} of 6</strong> dimensions
              {recWins.length > 0 && ` (${recWins.map((w) => w.dimension).join(', ')})`}.
            </span>
          </div>

          {runWins.length > 0 && (
            <div className="flex items-center space-x-1.5 text-slate-600">
              <span className="text-[11px] font-mono bg-blue-100 text-blue-800 border border-blue-200 px-2 py-0.5 rounded">
                Trade-off: #{runnerUp.rank} wins on {runWins.map((w) => w.dimension).join(', ')}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ImpactComparisonChart;
