import React, { useState, useEffect } from 'react';
import { 
  ShieldCheck, 
  ShieldAlert, 
  ShieldX, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  Info, 
  Layers,
  Trees, 
  Hospital, 
  GraduationCap, 
  Car, 
  Store, 
  Users, 
  Bus,
  Maximize2,
  MapPin,
  Building,
  RefreshCw
} from 'lucide-react';
import { formatArea, formatDistance } from '../../utils/formatters';

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

const CHECK_LABELS = {
  minimum_area: {
    title: 'Plot Area Adequacy',
    description: 'Proposed plot area meets or exceeds minimum required spatial footprint',
  },
  proximity_conflict: {
    title: 'Proximity Buffer & Conflict Radius',
    description: 'No existing facility of the same type within the municipal conflict radius',
  },
  service_saturation: {
    title: 'Service Saturation Limit',
    description: 'Density of existing facilities in radius does not exceed saturation limit',
  },
  zoning_compatibility: {
    title: 'Zoning & Land-Use Compatibility',
    description: 'Dominant land-use zone does not conflict with the proposed scenario',
  },
};

export function FeasibilityPanel({
  scenarios = [],
  ranking = [],
  verdicts = [],
  onCheckFeasibility,
  loading = false,
}) {
  // Default to Rank #1 scenario, or first available scenario
  const defaultScenarioId = ranking[0]?.scenario_id || scenarios[0]?.id || 'park';
  const [selectedScenarioId, setSelectedScenarioId] = useState(defaultScenarioId);

  // Auto-sync when ranking becomes available if not yet set
  useEffect(() => {
    if (ranking.length > 0 && !verdicts.some((v) => v.scenario_id === selectedScenarioId)) {
      setSelectedScenarioId(ranking[0].scenario_id);
    }
  }, [ranking]);

  const handleScenarioChange = (e) => {
    const nextId = e.target.value;
    setSelectedScenarioId(nextId);
    if (onCheckFeasibility) {
      onCheckFeasibility(nextId);
    }
  };

  // Find verdict for currently selected scenario
  const currentVerdict = verdicts.find((v) => v.scenario_id === selectedScenarioId);
  const currentScenario = scenarios.find((s) => s.id === selectedScenarioId);
  const currentRankItem = ranking.find((r) => r.scenario_id === selectedScenarioId);
  const Icon = SCENARIO_ICONS[selectedScenarioId] || Layers;
  const scenarioName = SCENARIO_NAMES[selectedScenarioId] || currentScenario?.name || selectedScenarioId;

  const scenarioOptions = scenarios.length > 0 
    ? scenarios 
    : Object.entries(SCENARIO_NAMES).map(([id, name]) => ({ id, name }));

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 mb-5 gap-2">
        <div>
          <div className="flex items-center space-x-2 text-teal-600">
            <ShieldCheck className="w-5 h-5" />
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800">
              Feasibility &amp; Regulatory Constraints Check
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Evaluates deterministic physical, spatial, and zoning constraints from municipal guidelines (<code className="text-[11px] bg-slate-100 px-1 py-0.5 rounded font-mono">feasibility.yaml</code>).
          </p>
        </div>

        <span className="text-[11px] font-mono bg-teal-50 text-teal-700 border border-teal-200 px-2.5 py-1 rounded-full self-start sm:self-auto">
          Pass / Warning / Blocker Check
        </span>
      </div>

      {/* Conceptual Distinction Banner */}
      <div className="mb-5 p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-600 flex items-start space-x-2.5">
        <Info className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 w-full text-[11px]">
          <div>
            <strong className="text-slate-800">Ranking answers:</strong>{' '}
            <span>&ldquo;Which scenario performs best according to selected municipal priorities?&rdquo;</span>
          </div>
          <div>
            <strong className="text-slate-800">Feasibility answers:</strong>{' '}
            <span>&ldquo;Can the selected scenario satisfy the configured implementation constraints?&rdquo;</span>
          </div>
        </div>
      </div>

      {/* Scenario Selector & Status Bar */}
      <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 mb-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3 w-full sm:w-auto">
            <div className="p-2.5 rounded-lg bg-white border border-slate-200 text-teal-700 shadow-xs">
              <Icon className="w-5 h-5" />
            </div>
            <div className="flex-1 sm:flex-initial">
              <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1">
                Select Scenario to Evaluate
              </label>
              <select
                value={selectedScenarioId}
                onChange={handleScenarioChange}
                className="w-full sm:w-72 pl-3 pr-8 py-2 bg-white text-xs font-semibold text-slate-900 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-teal-500 shadow-xs"
              >
                {scenarioOptions.map((s) => {
                  const rankItem = ranking.find((r) => r.scenario_id === s.id);
                  const isTopRank = rankItem?.rank === 1;
                  return (
                    <option key={s.id} value={s.id}>
                      {s.name} {rankItem ? `(Rank #${rankItem.rank}${isTopRank ? ' - Recommended' : ''})` : ''}
                    </option>
                  );
                })}
              </select>
            </div>
          </div>

          <div className="flex items-center space-x-2 self-start sm:self-center">
            {currentRankItem && (
              <span className="text-xs font-mono font-bold bg-white border border-slate-200 px-2.5 py-1 rounded-lg text-slate-700">
                Current Rank: #{currentRankItem.rank}
              </span>
            )}
            {onCheckFeasibility && (
              <button
                type="button"
                onClick={() => onCheckFeasibility(selectedScenarioId)}
                disabled={loading}
                className="px-3 py-1.5 bg-white border border-slate-300 hover:border-teal-400 text-slate-700 hover:text-teal-700 text-xs font-medium rounded-lg flex items-center space-x-1.5 transition-all shadow-xs"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                <span>Re-check</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Feasibility Verdict Card */}
      {currentVerdict ? (
        <div className="space-y-5 animate-in fade-in duration-300">
          <div
            className={`p-5 rounded-xl border flex flex-col md:flex-row md:items-center justify-between gap-4 ${
              currentVerdict.feasible
                ? 'bg-emerald-50 border-emerald-300 text-emerald-950'
                : 'bg-rose-50 border-rose-300 text-rose-950'
            }`}
          >
            <div className="flex items-start space-x-3.5">
              <div
                className={`p-2.5 rounded-xl text-white shadow-xs ${
                  currentVerdict.feasible ? 'bg-emerald-600' : 'bg-rose-600'
                }`}
              >
                {currentVerdict.feasible ? (
                  <ShieldCheck className="w-6 h-6" />
                ) : (
                  <ShieldX className="w-6 h-6" />
                )}
              </div>

              <div>
                <div className="flex items-center space-x-2 mb-1">
                  <span
                    className={`text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full ${
                      currentVerdict.feasible
                        ? 'bg-emerald-200 text-emerald-900'
                        : 'bg-rose-200 text-rose-900'
                    }`}
                  >
                    {currentVerdict.feasible ? 'OVERALL: FEASIBLE' : 'OVERALL: INFEASIBLE'}
                  </span>
                  {currentVerdict.warning_count > 0 && (
                    <span className="text-[11px] font-semibold bg-amber-100 text-amber-800 border border-amber-200 px-2 py-0.5 rounded-full flex items-center space-x-1">
                      <AlertTriangle className="w-3 h-3 text-amber-600" />
                      <span>{currentVerdict.warning_count} Warning{currentVerdict.warning_count > 1 ? 's' : ''}</span>
                    </span>
                  )}
                </div>
                <h3 className="text-base font-bold leading-tight">
                  {currentVerdict.feasible
                    ? `${scenarioName} satisfies all configured feasibility constraints.`
                    : `${scenarioName} fails ${currentVerdict.blocker_count} critical implementation constraint${currentVerdict.blocker_count > 1 ? 's' : ''}.`}
                </h3>
                <p className="text-xs opacity-80 mt-0.5">
                  {currentVerdict.feasible
                    ? 'Plot area meets mandatory minimum footprint. No blocking regulatory conflicts identified.'
                    : 'Mandatory spatial or legal requirements are not satisfied. Policy revision required before implementation.'}
                </p>
              </div>
            </div>

            {/* Blockers / Warnings Summary Pill */}
            <div className="bg-white/90 backdrop-blur-xs border border-inherit rounded-lg p-3 text-right self-start md:self-auto flex-shrink-0">
              <span className="text-[10px] text-slate-500 uppercase block font-semibold">
                Constraint Issues
              </span>
              <span className="text-sm font-mono font-bold">
                <span className={currentVerdict.blocker_count > 0 ? 'text-rose-600' : 'text-emerald-600'}>
                  {currentVerdict.blocker_count} Blockers
                </span>
                <span className="text-slate-300 mx-1.5">|</span>
                <span className={currentVerdict.warning_count > 0 ? 'text-amber-600' : 'text-slate-500'}>
                  {currentVerdict.warning_count} Warnings
                </span>
              </span>
            </div>
          </div>

          {/* Individual Feasibility Checks (4 rules) */}
          <div className="border border-slate-200 rounded-xl overflow-hidden">
            <div className="p-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between text-xs font-semibold text-slate-700">
              <span>Individual Constraint Rule Evaluations</span>
              <span className="text-[11px] text-slate-400 font-mono">4 Deterministic Checks</span>
            </div>

            <div className="divide-y divide-slate-100">
              {currentVerdict.checks.map((check) => {
                const meta = CHECK_LABELS[check.check_name] || {
                  title: check.check_name,
                  description: 'Municipal planning rule check',
                };
                const isBlocker = check.severity === 'blocker';
                const isPassed = check.passed;

                return (
                  <div key={check.check_name} className="p-4 hover:bg-slate-50/60 transition-colors">
                    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 mb-2">
                      <div className="flex items-start space-x-3">
                        <div className="mt-0.5">
                          {isPassed ? (
                            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                          ) : isBlocker ? (
                            <XCircle className="w-4 h-4 text-rose-600" />
                          ) : (
                            <AlertTriangle className="w-4 h-4 text-amber-500" />
                          )}
                        </div>

                        <div>
                          <div className="flex items-center space-x-2">
                            <h4 className="text-xs font-bold text-slate-900">{meta.title}</h4>
                            <span
                              className={`text-[10px] font-mono px-1.5 py-0.2 rounded font-semibold uppercase ${
                                isBlocker
                                  ? 'bg-rose-50 text-rose-700 border border-rose-200'
                                  : 'bg-amber-50 text-amber-700 border border-amber-200'
                              }`}
                            >
                              {check.severity}
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-500 mt-0.5">{meta.description}</p>
                        </div>
                      </div>

                      {/* Status Badge */}
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold font-mono border self-start ${
                          isPassed
                            ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                            : isBlocker
                            ? 'bg-rose-100 text-rose-900 border-rose-400 shadow-2xs'
                            : 'bg-amber-50 text-amber-900 border-amber-300'
                        }`}
                      >
                        {isPassed ? '✓ PASS' : isBlocker ? '✗ CRITICAL BLOCKER' : '⚠ ADVISORY'}
                      </span>
                    </div>

                    {/* Backend Rationale Message & Numerical Details */}
                    <div className="ml-7 bg-slate-50 border border-slate-150 rounded-lg p-2.5 text-xs text-slate-700 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <span className="font-medium">{check.message}</span>

                      {/* Numerical details rendered directly from backend */}
                      {check.details && (
                        <div className="flex items-center flex-wrap gap-2 text-[11px] font-mono text-slate-500 flex-shrink-0">
                          {check.details.required_min_sqm != null && (
                            <span className="bg-white px-2 py-0.5 rounded border border-slate-200">
                              Min Required: <strong>{formatArea(check.details.required_min_sqm)}</strong>
                            </span>
                          )}
                          {check.details.available_sqm != null && (
                            <span className="bg-white px-2 py-0.5 rounded border border-slate-200">
                              Available: <strong>{formatArea(check.details.available_sqm)}</strong>
                            </span>
                          )}
                          {check.details.conflict_buffer_m != null && (
                            <span className="bg-white px-2 py-0.5 rounded border border-slate-200">
                              Buffer: <strong>{formatDistance(check.details.conflict_buffer_m)}</strong>
                            </span>
                          )}
                          {check.details.nearest_facility_distance_m != null && (
                            <span className="bg-white px-2 py-0.5 rounded border border-slate-200">
                              Nearest: <strong>{formatDistance(check.details.nearest_facility_distance_m)}</strong>
                            </span>
                          )}
                          {check.details.saturation_limit != null && (
                            <span className="bg-white px-2 py-0.5 rounded border border-slate-200">
                              Limit: <strong>{check.details.saturation_limit}</strong> (Actual: {check.details.existing_facilities_count})
                            </span>
                          )}
                          {check.details.dominant_landuse && (
                            <span className="bg-white px-2 py-0.5 rounded border border-slate-200">
                              Zone: <strong className="capitalize">{check.details.dominant_landuse}</strong>
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center py-8 text-xs text-slate-500 bg-slate-50 rounded-xl border border-dashed border-slate-200">
          <ShieldCheck className="w-8 h-8 mx-auto text-slate-400 mb-2 opacity-70" />
          <p className="font-medium text-slate-700">Click below to evaluate feasibility constraints for {scenarioName}.</p>
          <button
            type="button"
            onClick={() => onCheckFeasibility && onCheckFeasibility(selectedScenarioId)}
            disabled={loading}
            className="mt-3 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white font-bold rounded-lg transition-all shadow-xs"
          >
            {loading ? 'Evaluating...' : `Check Feasibility for ${scenarioName}`}
          </button>
        </div>
      )}
    </div>
  );
}

export default FeasibilityPanel;
