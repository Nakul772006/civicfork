import React from 'react';
import { 
  Trees, 
  Hospital, 
  GraduationCap, 
  Car, 
  Store, 
  Users, 
  Bus, 
  Layers, 
  ArrowRight,
  TrendingUp,
  DollarSign,
  Activity,
  Play,
  Loader2
} from 'lucide-react';
import { formatArea, formatINR } from '../../utils/formatters';

const SCENARIO_ICONS = {
  park: Trees,
  healthcare: Hospital,
  education: GraduationCap,
  parking: Car,
  commercial: Store,
  community_centre: Users,
  public_transport: Bus,
};

const SCENARIO_THEMES = {
  park: 'text-emerald-700 bg-emerald-50 border-emerald-200',
  healthcare: 'text-rose-700 bg-rose-50 border-rose-200',
  education: 'text-indigo-700 bg-indigo-50 border-indigo-200',
  parking: 'text-amber-700 bg-amber-50 border-amber-200',
  commercial: 'text-purple-700 bg-purple-50 border-purple-200',
  community_centre: 'text-cyan-700 bg-cyan-50 border-cyan-200',
  public_transport: 'text-blue-700 bg-blue-50 border-blue-200',
};

const SCENARIO_PURPOSES = {
  park: 'Recreational Green & Permeable Space',
  healthcare: 'Primary Health & Diagnostic Care',
  education: 'Public Learning & Vocational Training',
  parking: 'Off-Street Multi-Level Vehicle Facility',
  commercial: 'Mixed Commercial Retail & Services',
  community_centre: 'Civic Assembly & Cultural Facilities',
  public_transport: 'Public Transit Terminal & Feeder Depot',
};

export function ScenarioList({ scenarios = [], onRunSimulation, simulating = false }) {
  if (!scenarios || scenarios.length === 0) return null;

  return (
    <div className="bg-white rounded-xl shadow-xs border border-slate-200 p-6 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 mb-5 gap-3">
        <div>
          <div className="flex items-center space-x-2 text-blue-600">
            <Layers className="w-4 h-4" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900">
              Stage 2: Seven Policy Alternatives Generated
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Deterministic candidate development options tailored to plot dimensions and detected local gaps.
          </p>
        </div>

        {onRunSimulation && (
          <button
            type="button"
            onClick={onRunSimulation}
            disabled={simulating}
            className={`px-4 py-2 rounded-lg text-xs font-bold text-white shadow-xs flex items-center space-x-2 transition-all cursor-pointer ${
              simulating
                ? 'bg-slate-400 cursor-not-allowed'
                : 'bg-emerald-600 hover:bg-emerald-700 active:scale-98'
            }`}
          >
            {simulating ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Simulating 6 Dimensions...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Run Simulation on All 7</span>
              </>
            )}
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3.5">
        {scenarios.map((sc) => {
          const Icon = SCENARIO_ICONS[sc.id] || Layers;
          const theme = SCENARIO_THEMES[sc.id] || 'text-slate-700 bg-slate-50 border-slate-200';
          const purpose = SCENARIO_PURPOSES[sc.id] || 'Municipal Development Option';

          return (
            <div
              key={sc.id}
              className="border border-slate-200 rounded-lg p-4 bg-white flex flex-col justify-between hover:border-slate-300 hover:shadow-2xs transition-all shadow-2xs"
            >
              <div>
                <div className="flex items-start space-x-3 mb-3">
                  <div className={`p-2 rounded-lg border ${theme} flex-shrink-0`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-xs font-bold text-slate-900 leading-snug">
                      {sc.name}
                    </h3>
                    <p className="text-[11px] text-slate-500 leading-tight mt-0.5">
                      {purpose}
                    </p>
                  </div>
                </div>

                <div className="space-y-1.5 text-xs text-slate-600 mb-3 bg-slate-50/80 p-2.5 rounded-md border border-slate-100">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Proposed Area:</span>
                    <span className="font-semibold text-slate-800 font-mono">
                      {formatArea(sc.proposed_area_sqm)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Est. Capital Cost:</span>
                    <span className="font-semibold text-slate-800 font-mono">
                      {formatINR(sc.estimated_cost_inr)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Annual O&amp;M:</span>
                    <span className="font-semibold text-slate-800 font-mono">
                      {formatINR(sc.estimated_annual_operating_cost_inr)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Daily Visitors:</span>
                    <span className="font-semibold text-slate-800 font-mono">
                      {sc.estimated_daily_visitors.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Direct Jobs:</span>
                    <span className="font-semibold text-slate-800 font-mono">
                      {sc.estimated_jobs_created}
                    </span>
                  </div>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-100 text-[11px] flex items-center justify-between">
                <span className="text-slate-500">Traffic Strain:</span>
                <span
                  className={`font-semibold font-mono ${
                    sc.estimated_traffic_change_pct > 0
                      ? 'text-amber-700 bg-amber-50 px-1.5 py-0.2 rounded border border-amber-200'
                      : sc.estimated_traffic_change_pct < 0
                      ? 'text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-200'
                      : 'text-slate-700 bg-slate-50 px-1.5 py-0.2 rounded border border-slate-200'
                  }`}
                >
                  {sc.estimated_traffic_change_pct > 0 ? `+${sc.estimated_traffic_change_pct}%` : `${sc.estimated_traffic_change_pct}%`}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default ScenarioList;
