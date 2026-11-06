import React from 'react';
import { 
  Trophy, 
  MapPin, 
  Trees, 
  Hospital, 
  GraduationCap, 
  Car, 
  Store, 
  Users, 
  Bus, 
  Layers, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  Target, 
  TrendingUp, 
  Scale, 
  Sparkles,
  FileDown
} from 'lucide-react';
import { formatINR } from '../../utils/formatters';

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

const SCENARIO_TO_GAP_CATEGORY = {
  park: 'parks',
  healthcare: 'healthcare',
  education: 'education',
  parking: 'parking',
  commercial: 'commercial',
  community_centre: 'community',
  public_transport: 'transport',
};

const GAP_CATEGORY_NAMES = {
  parks: 'Parks & Recreational Space',
  healthcare: 'Healthcare Facilities',
  education: 'Educational Institutions',
  parking: 'Public Parking Capacity',
  commercial: 'Commercial Amenities',
  community: 'Community & Civic Hubs',
  transport: 'Public Transit Connectivity',
};

const DIMENSION_DISPLAY = {
  traffic: 'Traffic Impact',
  cost: 'Fiscal / Cost Burden',
  environmental: 'Environmental Quality',
  accessibility: 'Citizen Accessibility',
  gap_improvement: 'Infrastructure Gap Closure',
  social_utility: 'Social Utility & Reach',
};

/**
 * DecisionSnapshot
 * 
 * Compact executive "Decision Snapshot" card for municipal judges and planners.
 * Provides instant 5-second clarity on the recommended policy, decision score,
 * feasibility status, and primary supporting insights (opportunity, advantage, trade-off).
 * 
 * Strict boundary: Read-only presentation of pre-calculated backend session data.
 */
export function DecisionSnapshot({
  ranking = [],
  scoreMatrix = null,
  scenarios = [],
  verdicts = [],
  gaps = [],
  plot = null,
  contextSummary = null,
  onDownloadReport = null,
  reportLoading = false,
}) {
  // Only render when ranking results are available
  if (!ranking || ranking.length === 0) {
    return null;
  }

  // Rank #1 scenario is the primary focus of the snapshot
  const topScenario = ranking[0];
  const scenarioId = topScenario.scenario_id;
  const scenarioName = topScenario.scenario_name || SCENARIO_NAMES[scenarioId] || scenarioId;
  const Icon = SCENARIO_ICONS[scenarioId] || Layers;

  // Resolve raw dimension scores from scoreMatrix scenario_scores or scenario trace
  const rawDimensionScores = {};
  if (scoreMatrix?.scenario_scores) {
    const scMatch = scoreMatrix.scenario_scores.find((s) => s.scenario_id === scenarioId);
    if (scMatch?.scores) {
      scMatch.scores.forEach((ds) => {
        rawDimensionScores[ds.dimension] = ds.score;
      });
    }
  } else if (topScenario.dimension_scores) {
    Object.assign(rawDimensionScores, topScenario.dimension_scores);
  }
  const hasRawScores = Object.keys(rawDimensionScores).length > 0;

  // Decision Score: Formatted to 1 decimal place
  const weightedScore = topScenario.weighted_score != null 
    ? Number(topScenario.weighted_score).toFixed(1) 
    : '—';

  // Location & Radius formatting
  const locationLabel = contextSummary?.ward?.ward_name || plot?.label || 'Mysuru Study Parcel';
  const radiusMeters = plot?.radius_m || 2000;
  const radiusLabel = radiusMeters >= 1000
    ? `${(radiusMeters / 1000).toFixed(radiusMeters % 1000 === 0 ? 0 : 1)} km analysis radius`
    : `${radiusMeters} m analysis radius`;

  // Feasibility status lookup for Rank #1
  const topVerdict = (verdicts || []).find((v) => v.scenario_id === scenarioId);
  let feasibilityState = null;
  if (topVerdict) {
    if (!topVerdict.feasible || (topVerdict.blocker_count && topVerdict.blocker_count > 0)) {
      feasibilityState = {
        label: '✕ Not feasible',
        badgeClass: 'bg-rose-50 text-rose-700 border-rose-300',
        icon: XCircle,
      };
    } else if (topVerdict.warning_count && topVerdict.warning_count > 0) {
      feasibilityState = {
        label: '⚠ Feasible with advisories',
        badgeClass: 'bg-amber-50 text-amber-800 border-amber-300',
        icon: AlertTriangle,
      };
    } else {
      feasibilityState = {
        label: '✓ Feasible',
        badgeClass: 'bg-emerald-50 text-emerald-800 border-emerald-300',
        icon: CheckCircle2,
      };
    }
  }

  // Supporting Insight 1: Key Opportunity (highest-severity gap addressed)
  const targetCategory = SCENARIO_TO_GAP_CATEGORY[scenarioId];
  const matchedGap = (gaps || []).find((g) => g.category === targetCategory);
  const highestGap = (gaps || []).length > 0 
    ? [...gaps].sort((a, b) => (b.gap_severity || 0) - (a.gap_severity || 0))[0]
    : null;
  const relevantGap = (matchedGap && (matchedGap.gap_severity || 0) > 0) ? matchedGap : highestGap;

  let keyOpportunity = null;
  if (relevantGap && relevantGap.gap_severity > 0) {
    const catName = GAP_CATEGORY_NAMES[relevantGap.category] || relevantGap.category;
    const sevPct = Math.round(relevantGap.gap_severity * 100);
    const classification = relevantGap.classification ? relevantGap.classification.toUpperCase() : 'DEFICIT';
    const isDirect = relevantGap.category === targetCategory;

    keyOpportunity = {
      title: isDirect ? 'Direct Gap Resolution' : 'Priority Local Need',
      headline: `${catName} (${sevPct}% deficit · ${classification})`,
      explanation: isDirect
        ? `Directly targets the municipality's measured ${relevantGap.category} deficit.`
        : `Addresses community infrastructure priorities within the ${radiusLabel}.`,
    };
  }

  // Supporting Insight 2: Key Advantage (strongest impact dimension contribution)
  let keyAdvantage = null;
  if (topScenario.dimension_contributions && Object.keys(topScenario.dimension_contributions).length > 0) {
    const entries = Object.entries(topScenario.dimension_contributions);
    entries.sort((a, b) => b[1] - a[1]);
    const [topDim, topContrib] = entries[0];
    const rawScore = hasRawScores ? rawDimensionScores[topDim] : null;

    keyAdvantage = {
      dimension: DIMENSION_DISPLAY[topDim] || topDim,
      contribution: Number(topContrib).toFixed(1),
      score: rawScore != null ? Number(rawScore).toFixed(1) : null,
      explanation: `Strongest value driver adding +${Number(topContrib).toFixed(1)} pts to decision score${rawScore != null ? ` (${Number(rawScore).toFixed(1)}/100 raw)` : ''}.`,
    };
  } else if (hasRawScores) {
    const entries = Object.entries(rawDimensionScores);
    entries.sort((a, b) => b[1] - a[1]);
    const [topDim, topScore] = entries[0];

    keyAdvantage = {
      dimension: DIMENSION_DISPLAY[topDim] || topDim,
      score: Number(topScore).toFixed(1),
      explanation: `Highest-performing evaluated dimension at ${Number(topScore).toFixed(1)} / 100.`,
    };
  }

  // Supporting Insight 3: Primary Trade-off (lowest dimension / capital outlay / advisory)
  let primaryTradeoff = null;
  const tradeOffDimSource = hasRawScores ? rawDimensionScores : topScenario.dimension_contributions;
  if (tradeOffDimSource && Object.keys(tradeOffDimSource).length > 0) {
    const entries = Object.entries(tradeOffDimSource);
    entries.sort((a, b) => a[1] - b[1]);
    const [lowestDim, lowestVal] = entries[0];
    const rawLowestScore = hasRawScores ? rawDimensionScores[lowestDim] : null;

    const scenarioMeta = (scenarios || []).find((s) => s.id === scenarioId);
    const costStr = scenarioMeta?.estimated_cost_inr ? formatINR(scenarioMeta.estimated_cost_inr) : null;

    let explanation = `Lowest relative dimension performance is in ${DIMENSION_DISPLAY[lowestDim] || lowestDim}${rawLowestScore != null ? ` (${Number(rawLowestScore).toFixed(1)}/100)` : ''}.`;
    if (lowestDim === 'cost' && costStr) {
      explanation = `Requires capital outlay of ${costStr}, resulting in lower fiscal score${rawLowestScore != null ? ` (${Number(rawLowestScore).toFixed(1)}/100)` : ''}.`;
    } else if (lowestDim === 'traffic') {
      explanation = `Localized vehicular trip generation limits traffic performance${rawLowestScore != null ? ` to ${Number(rawLowestScore).toFixed(1)}/100` : ''}.`;
    }

    if (topVerdict?.warning_count > 0) {
      explanation += ` Subject to ${topVerdict.warning_count} municipal spatial advisory.`;
    }

    primaryTradeoff = {
      dimension: DIMENSION_DISPLAY[lowestDim] || lowestDim,
      score: rawLowestScore != null ? Number(rawLowestScore).toFixed(1) : Number(lowestVal).toFixed(1),
      explanation,
    };
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden mb-6">
      {/* Top Banner Header */}
      <div className="bg-slate-900 text-white px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800">
        <div>
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-amber-400" />
            <h2 className="text-xs sm:text-sm font-bold uppercase tracking-wider text-slate-100">
              CIVICFORK DECISION SNAPSHOT
            </h2>
          </div>
          <p className="text-xs text-slate-300 mt-0.5">
            Executive summary of the current urban policy analysis.
          </p>
        </div>

        {/* Location & Analysis Radius + PDF Export */}
        <div className="flex flex-wrap items-center gap-2.5 self-start sm:self-auto">
          <div className="flex items-center space-x-2 text-xs bg-slate-800/90 border border-slate-700/80 px-3 py-1.5 rounded-lg">
            <MapPin className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
            <div className="flex flex-col sm:flex-row sm:items-center sm:space-x-1.5 leading-tight">
              <span className="font-semibold text-slate-200">{locationLabel}</span>
              <span className="hidden sm:inline text-slate-500">·</span>
              <span className="text-slate-400 font-mono text-[11px]">{radiusLabel}</span>
            </div>
          </div>

          {onDownloadReport && (
            <button
              type="button"
              onClick={() => onDownloadReport(true)}
              disabled={reportLoading}
              title="Download official 6-page Municipal Decision Report PDF"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-500 active:bg-blue-700 disabled:bg-slate-700 text-white transition-all shadow-xs cursor-pointer disabled:cursor-not-allowed"
            >
              <FileDown className={`w-3.5 h-3.5 ${reportLoading ? 'animate-bounce' : ''}`} />
              <span>{reportLoading ? 'Generating PDF...' : 'Decision PDF'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Executive Summary Row */}
      <div className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-center pb-6 border-b border-slate-100">
          
          {/* Recommended Policy & Rank + Feasibility */}
          <div className="col-span-12 md:col-span-7 lg:col-span-8 flex items-start space-x-4">
            <div className="p-3.5 bg-gradient-to-br from-blue-600 to-indigo-700 text-white rounded-xl shadow-md shadow-blue-500/20 flex-shrink-0">
              <Icon className="w-7 h-7 sm:w-8 sm:h-8" />
            </div>

            <div className="space-y-2">
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 block">
                  RECOMMENDED POLICY
                </span>
                <h3 className="text-xl sm:text-2xl font-black text-slate-900 leading-tight">
                  {scenarioName}
                </h3>
              </div>

              {/* Rank + Feasibility Badges */}
              <div className="flex flex-wrap items-center gap-2 pt-0.5">
                {/* Rank Badge */}
                <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-900 border border-amber-300 font-mono shadow-xs">
                  <Trophy className="w-3.5 h-3.5 text-amber-600" />
                  <span>#1 Recommended</span>
                </span>

                {/* Feasibility Badge */}
                {feasibilityState && (
                  <span className={`inline-flex items-center space-x-1 px-3 py-1 rounded-full text-xs font-bold border font-mono shadow-xs ${feasibilityState.badgeClass}`}>
                    <span>{feasibilityState.label}</span>
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Large Weighted Decision Score */}
          <div className="col-span-12 md:col-span-5 lg:col-span-4 bg-slate-50 border border-slate-200 rounded-xl p-4 flex flex-col items-start sm:items-end justify-center">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Weighted Decision Score
            </span>
            <div className="flex items-baseline">
              <span className="text-4xl sm:text-5xl font-black font-mono tracking-tight text-slate-900">
                {weightedScore}
              </span>
              <span className="text-base sm:text-lg font-bold font-mono text-slate-400 ml-1.5">
                / 100
              </span>
            </div>
            {ranking.length > 1 && (
              <span className="text-[11px] text-slate-500 mt-1 font-mono">
                +{(topScenario.weighted_score - ranking[1].weighted_score).toFixed(1)} pts over #{2} {ranking[1].scenario_name}
              </span>
            )}
          </div>
        </div>

        {/* Supporting Insights Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-6">
          
          {/* Key Opportunity */}
          {keyOpportunity ? (
            <div className="bg-slate-50/70 border border-slate-200/90 rounded-xl p-4 flex flex-col justify-between hover:border-slate-300 transition-colors">
              <div>
                <div className="flex items-center space-x-2 text-blue-600 mb-2">
                  <Target className="w-4 h-4 text-blue-600" />
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                    Key Opportunity
                  </span>
                </div>
                <h4 className="text-xs font-bold text-slate-900 mb-1">
                  {keyOpportunity.headline}
                </h4>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {keyOpportunity.explanation}
                </p>
              </div>
            </div>
          ) : null}

          {/* Key Advantage */}
          {keyAdvantage ? (
            <div className="bg-emerald-50/40 border border-emerald-200/80 rounded-xl p-4 flex flex-col justify-between hover:border-emerald-300 transition-colors">
              <div>
                <div className="flex items-center space-x-2 text-emerald-700 mb-2">
                  <TrendingUp className="w-4 h-4 text-emerald-600" />
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                    Key Advantage
                  </span>
                </div>
                <h4 className="text-xs font-bold text-slate-900 mb-1">
                  {keyAdvantage.dimension}
                </h4>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {keyAdvantage.explanation}
                </p>
              </div>
            </div>
          ) : null}

          {/* Primary Trade-off */}
          {primaryTradeoff ? (
            <div className="bg-amber-50/40 border border-amber-200/80 rounded-xl p-4 flex flex-col justify-between hover:border-amber-300 transition-colors">
              <div>
                <div className="flex items-center space-x-2 text-amber-700 mb-2">
                  <Scale className="w-4 h-4 text-amber-600" />
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                    Primary Trade-off
                  </span>
                </div>
                <h4 className="text-xs font-bold text-slate-900 mb-1">
                  {primaryTradeoff.dimension}
                </h4>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {primaryTradeoff.explanation}
                </p>
              </div>
            </div>
          ) : null}

        </div>
      </div>
    </div>
  );
}

export default DecisionSnapshot;
