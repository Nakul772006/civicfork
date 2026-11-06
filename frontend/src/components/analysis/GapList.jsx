import React from 'react';
import { 
  Trees, 
  Hospital, 
  GraduationCap, 
  Car, 
  Store, 
  Users, 
  Bus, 
  AlertTriangle, 
  CheckCircle2, 
  AlertCircle,
  XCircle,
  ShieldAlert,
  Info
} from 'lucide-react';
import { formatDistance } from '../../utils/formatters';

const CATEGORY_META = {
  parks: { name: 'Parks & Recreational Space', icon: Trees, color: 'text-emerald-700 bg-emerald-50 border-emerald-200' },
  healthcare: { name: 'Healthcare Facilities', icon: Hospital, color: 'text-rose-700 bg-rose-50 border-rose-200' },
  education: { name: 'Educational Institutions', icon: GraduationCap, color: 'text-indigo-700 bg-indigo-50 border-indigo-200' },
  parking: { name: 'Public Parking Capacity', icon: Car, color: 'text-amber-700 bg-amber-50 border-amber-200' },
  commercial: { name: 'Commercial Amenities', icon: Store, color: 'text-purple-700 bg-purple-50 border-purple-200' },
  community: { name: 'Community Centers & Civic Hubs', icon: Users, color: 'text-cyan-700 bg-cyan-50 border-cyan-200' },
  transport: { name: 'Public Transit Connectivity', icon: Bus, color: 'text-blue-700 bg-blue-50 border-blue-200' },
};

function getSeverityBadge(severity, classification, gapType) {
  let label = classification ? classification.toUpperCase() : 'MODERATE';
  let Icon = AlertTriangle;
  let bg = 'bg-amber-50 text-amber-900 border-amber-300';
  let bar = 'bg-amber-500';

  if (gapType === 'absent' || severity >= 0.75) {
    label = 'CRITICAL DEFICIT';
    Icon = XCircle;
    bg = 'bg-rose-50 text-rose-900 border-rose-300';
    bar = 'bg-rose-500';
  } else if (gapType === 'insufficient' || severity >= 0.50) {
    label = 'INSUFFICIENT';
    Icon = AlertTriangle;
    bg = 'bg-amber-50 text-amber-900 border-amber-300';
    bar = 'bg-amber-500';
  } else if (gapType === 'distant' || severity >= 0.25) {
    label = 'DISTANT BUFFER';
    Icon = AlertCircle;
    bg = 'bg-yellow-50 text-yellow-900 border-yellow-300';
    bar = 'bg-yellow-500';
  } else {
    label = 'ADEQUATE';
    Icon = CheckCircle2;
    bg = 'bg-emerald-50 text-emerald-900 border-emerald-300';
    bar = 'bg-emerald-500';
  }

  return { label, Icon, bg, bar };
}

export function GapList({ gaps = [] }) {
  if (!gaps || gaps.length === 0) return null;

  return (
    <div className="bg-white rounded-xl shadow-xs border border-slate-200 p-6 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 mb-4 gap-2">
        <div>
          <div className="flex items-center space-x-2 text-blue-600">
            <AlertTriangle className="w-4 h-4 text-amber-500" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900">
              Infrastructure Gap Analysis (7 Municipal Categories)
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Deterministic gap severity derived by comparing observed amenities with configured planning thresholds.
          </p>
        </div>
        <span className="text-xs text-slate-500 font-mono self-start sm:self-auto bg-slate-50 px-2.5 py-1 rounded-md border border-slate-200">
          Scale: 0.0 (Adequate) → 1.0 (Critical Deficit)
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 mb-4">
        {gaps.map((gap) => {
          const meta = CATEGORY_META[gap.category] || {
            name: gap.category,
            icon: ShieldAlert,
            color: 'text-slate-600 bg-slate-50 border-slate-200',
          };
          const Icon = meta.icon;
          const sevInfo = getSeverityBadge(gap.gap_severity, gap.classification, gap.gap_type);
          const StatusIcon = sevInfo.Icon;

          return (
            <div
              key={gap.category}
              className="border border-slate-200 rounded-lg p-3.5 hover:border-slate-300 transition-colors bg-white flex flex-col justify-between shadow-2xs"
            >
              <div>
                <div className="flex items-start justify-between mb-2 gap-2">
                  <div className="flex items-center space-x-2.5">
                    <div className={`p-1.5 rounded-lg border ${meta.color} flex-shrink-0`}>
                      <Icon className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="text-xs font-bold text-slate-900 leading-tight">
                        {meta.name}
                      </h3>
                      <span className="text-[11px] text-slate-500 capitalize">
                        {gap.gap_type !== 'none' ? `${gap.gap_type} coverage` : 'Adequate municipal coverage'}
                      </span>
                    </div>
                  </div>

                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full border font-mono flex items-center space-x-1 flex-shrink-0 ${sevInfo.bg}`}
                  >
                    <StatusIcon className="w-3 h-3 flex-shrink-0" />
                    <span>{sevInfo.label}</span>
                    <span className="opacity-75">({(gap.gap_severity * 100).toFixed(0)}%)</span>
                  </span>
                </div>

                {/* Progress Severity Bar */}
                <div className="w-full bg-slate-100 rounded-full h-2 mb-2 overflow-hidden border border-slate-200/50">
                  <div
                    className={`h-2 rounded-full ${sevInfo.bar} transition-all duration-500`}
                    style={{ width: `${Math.min(100, Math.max(5, gap.gap_severity * 100))}%` }}
                    aria-label={`Severity ${(gap.gap_severity * 100).toFixed(0)} percent`}
                  />
                </div>
              </div>

              {/* Gap Metrics Footer */}
              <div className="text-[11px] text-slate-600 pt-2 border-t border-slate-100 flex items-center justify-between">
                <span>
                  Observed: <strong>{gap.facilities_in_radius}</strong> / {gap.expected_facilities} target
                </span>
                <span>
                  Nearest: <strong>{gap.nearest_facility_distance_m != null ? formatDistance(gap.nearest_facility_distance_m) : 'None in radius'}</strong>
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Dataset Coverage Limitation Note */}
      <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-[11px] text-slate-500 flex items-start space-x-2">
        <Info className="w-3.5 h-3.5 text-slate-400 mt-0.5 flex-shrink-0" />
        <span>
          <strong>Data Coverage Notice:</strong> &ldquo;0 observed&rdquo; denotes that no facilities were detected in the analyzed OpenStreetMap dataset within the scoping radius. This indicates an identified municipal service deficit or dataset coverage boundary, not necessarily physical impossibility.
        </span>
      </div>
    </div>
  );
}

export default GapList;
