import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  LabelList,
} from 'recharts';
import { BarChart3, Trophy, Info } from 'lucide-react';

/**
 * Custom tooltip for Scenario Decision Ranking chart.
 */
function RankingTooltip({ active, payload }) {
  if (!active || !payload || payload.length === 0) return null;
  const item = payload[0].payload;

  return (
    <div className="bg-slate-900 text-white text-xs rounded-xl p-3.5 shadow-xl border border-slate-800 z-50">
      <div className="font-bold text-slate-100 flex items-center gap-2 mb-2 pb-1.5 border-b border-slate-800">
        {item.isRecommended && (
          <span className="bg-emerald-500/20 text-emerald-300 text-[10px] font-mono px-2 py-0.5 rounded border border-emerald-400/40">
            ★ RECOMMENDED
          </span>
        )}
        <span className="text-sm font-semibold">{item.name}</span>
      </div>
      <div className="space-y-1 text-slate-300">
        <div className="flex items-center justify-between gap-4">
          <span className="text-slate-400">Leaderboard Rank:</span>
          <span className="font-mono font-bold text-white">#{item.rank}</span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span className="text-slate-400">Weighted Decision Score:</span>
          <span className="font-mono font-bold text-emerald-400">{item.scoreFormatted} / 100</span>
        </div>
        {item.scoreDeltaFromTop != null && item.rank > 1 && (
          <div className="flex items-center justify-between gap-4 text-[11px] pt-1 border-t border-slate-800 text-slate-400">
            <span>Delta from #1:</span>
            <span className="font-mono text-amber-400">-{Number(item.scoreDeltaFromTop).toFixed(1)} pts</span>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * ScenarioRankingChart
 * 
 * Horizontal bar chart displaying all seven ranked scenarios from the current
 * municipal weighting results. Rank #1 is prominently highlighted.
 * 
 * Strict boundary: Read-only presentation of pre-calculated backend ranking.
 */
export function ScenarioRankingChart({ ranking = [], loading = false }) {
  // Empty state handling
  if (!ranking || ranking.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
        <div className="flex items-center space-x-2 text-slate-400 mb-2">
          <BarChart3 className="w-5 h-5" />
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">
            Scenario Decision Ranking
          </h2>
        </div>
        <div className="p-8 text-center bg-slate-50 border border-slate-200 border-dashed rounded-lg">
          <Info className="w-6 h-6 text-slate-400 mx-auto mb-2" />
          <p className="text-xs text-slate-500 font-medium">
            Scenario decision ranking unavailable. Apply municipal priorities to calculate the scenario leaderboard.
          </p>
        </div>
      </div>
    );
  }

  // Format data strictly from backend ranking response
  const chartData = ranking.map((item) => {
    const scoreVal = Number(item.weighted_score);
    const isRecommended = item.rank === 1;
    return {
      scenarioId: item.scenario_id,
      name: item.scenario_name || item.scenario_id,
      score: scoreVal,
      scoreFormatted: scoreVal.toFixed(1),
      rank: item.rank,
      isRecommended,
      scoreDeltaFromTop: item.score_delta_from_top,
      displayLabel: `#${item.rank} · ${item.scenario_name}${isRecommended ? ' (Rec)' : ''}`,
    };
  });

  const topScenario = ranking[0];

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 mb-5 gap-2">
        <div>
          <div className="flex items-center space-x-2 text-blue-600">
            <Trophy className="w-4 h-4 text-amber-500" />
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800">
              Scenario Decision Ranking
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Weighted decision score under current municipal priorities
          </p>
        </div>

        {/* Total alternatives and dynamic top indicator */}
        <div className="flex items-center space-x-2 text-xs self-start sm:self-auto">
          <span className="font-mono bg-emerald-50 text-emerald-800 border border-emerald-300 px-2.5 py-1 rounded-lg flex items-center space-x-1.5 font-bold">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span>#1: {topScenario?.scenario_name} ({topScenario?.weighted_score?.toFixed(1)})</span>
          </span>
        </div>
      </div>

      {/* Accessible Legend / Guide */}
      <div className="flex flex-wrap items-center gap-3 mb-4 text-xs">
        <div className="flex items-center space-x-1.5">
          <span className="w-3 h-3 rounded bg-emerald-600 inline-block"></span>
          <span className="font-semibold text-slate-700">Rank #1 Recommended Policy</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-3 h-3 rounded bg-slate-500 inline-block"></span>
          <span className="text-slate-600">Rank #2–#7 Alternative Policies</span>
        </div>
        <span className="text-slate-400 text-[11px] font-mono ml-auto hidden md:inline">
          Scale: 0.0 – 100.0 (Higher is Better)
        </span>
      </div>

      {/* Recharts Horizontal Bar Chart */}
      <div className="w-full h-[360px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            layout="vertical"
            data={chartData}
            margin={{ top: 8, right: 48, left: 20, bottom: 8 }}
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
              dataKey="displayLabel"
              width={195}
              tick={{ fontSize: 12, fill: '#1e293b', fontWeight: 500 }}
              axisLine={{ stroke: '#cbd5e1' }}
            />
            <Tooltip content={<RankingTooltip />} cursor={{ fill: '#f1f5f9' }} />
            <Bar
              dataKey="score"
              radius={[0, 6, 6, 0]}
              barSize={24}
              animationDuration={500}
            >
              {chartData.map((entry) => (
                <Cell
                  key={`cell-${entry.scenarioId}`}
                  fill={entry.isRecommended ? '#059669' : '#64748b'}
                  stroke={entry.isRecommended ? '#047857' : '#475569'}
                  strokeWidth={1}
                />
              ))}
              <LabelList
                dataKey="scoreFormatted"
                position="right"
                style={{
                  fontSize: 11,
                  fontWeight: 'bold',
                  fill: '#1e293b',
                  fontFamily: 'monospace',
                }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Dynamic Note */}
      <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500 font-mono">
        <span>Dynamic Leaderboard: Recalculates immediately when priority weights are altered.</span>
        <span className="font-semibold text-emerald-700">Authoritative deterministic ranking</span>
      </div>
    </div>
  );
}

export default ScenarioRankingChart;
