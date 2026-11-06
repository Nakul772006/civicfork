import React, { useState } from 'react';
import {
  Sparkles,
  Bot,
  FileText,
  Scale,
  ShieldCheck,
  AlertCircle,
  RefreshCw,
  Info,
  Trophy,
  MapPin,
  Layers,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  Award,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  FileDown,
} from 'lucide-react';

const SECTION_METADATA = {
  decision_rationale: {
    title: 'Municipal Decision Rationale',
    icon: Award,
    accent: 'purple',
  },
  overview: {
    title: 'Executive Assessment Overview',
    icon: FileText,
    accent: 'blue',
  },
  urban_context: {
    title: 'Observed Urban Context & Density Estimates',
    icon: MapPin,
    accent: 'emerald',
  },
  infrastructure_gaps: {
    title: 'Infrastructure Gap Assessment',
    icon: AlertCircle,
    accent: 'amber',
  },
  recommended_scenario: {
    title: 'Recommended Scenario & Priority Alignment',
    icon: Trophy,
    accent: 'indigo',
  },
  trade_offs: {
    title: 'Key Policy Trade-offs & Alternatives',
    icon: Scale,
    accent: 'purple',
  },
  feasibility: {
    title: 'Planning & Regulatory Feasibility Constraints',
    icon: ShieldCheck,
    accent: 'teal',
  },
  comparison_analysis: {
    title: 'Pairwise Counterfactual Comparison',
    icon: Scale,
    accent: 'purple',
  },
  recommendation_context: {
    title: 'Municipal Policy Context',
    icon: Sparkles,
    accent: 'indigo',
  },
};

const NARRATIVE_TYPES = [
  { id: 'full_report', label: 'Full Assessment Report', description: 'Complete municipal briefing with Decision Rationale' },
  { id: 'score_explanation', label: 'Score & Ranking Analysis', description: 'Impact dimensions, weights, & rationale' },
  { id: 'counterfactual_explanation', label: 'Trade-off Analysis', description: 'Pairwise counterfactual delta' },
  { id: 'context_summary', label: 'Context & Gaps', description: 'Spatial analysis baseline' },
];

export function AIExplanation({
  narrative,
  loading = false,
  error = null,
  onGenerate,
  disabled = false,
  onDownloadReport = null,
  downloadingReport = false,
}) {
  const [selectedType, setSelectedType] = useState('full_report');
  const [showDetailedSections, setShowDetailedSections] = useState(true);

  const handleTypeSelect = (typeId) => {
    setSelectedType(typeId);
    if (onGenerate) {
      onGenerate(typeId);
    }
  };

  const handleManualGenerate = () => {
    if (onGenerate) {
      onGenerate(selectedType);
    }
  };

  // Helper to extract structured decision rationale
  const getDecisionRationale = () => {
    if (narrative?.decision_rationale) {
      return narrative.decision_rationale;
    }
    if (narrative?.sections?.decision_rationale) {
      const raw = narrative.sections.decision_rationale;
      const lines = raw.split('\n').map((l) => l.trim()).filter(Boolean);
      let headline = 'Municipal Decision Rationale';
      let rationale = '';
      const strengths = [];
      const trade_offs = [];
      let recommendation_context = '';

      let currentSec = 'rationale';
      for (const line of lines) {
        if (line.startsWith('#')) {
          headline = line.replace(/^[#\s]+/, '').trim();
          continue;
        }
        const lower = line.toLowerCase();
        if (lower.includes('strength') || lower.includes('gaps alleviated') || lower.includes('impact dimension')) {
          currentSec = 'strengths';
          continue;
        } else if (lower.includes('trade-off') || lower.includes('weaker') || lower.includes('weakness')) {
          currentSec = 'trade_offs';
          continue;
        } else if (lower.includes('context') || lower.includes('feasibility') || lower.includes('planning sanction')) {
          currentSec = 'context';
          continue;
        }

        if (currentSec === 'rationale') {
          if (!line.startsWith('-') && !line.startsWith('*')) {
            rationale += (rationale ? ' ' : '') + line;
          }
        } else if (currentSec === 'strengths') {
          if (line.startsWith('-') || line.startsWith('*')) {
            strengths.push(line.replace(/^[-*\s]+/, '').trim());
          }
        } else if (currentSec === 'trade_offs') {
          if (line.startsWith('-') || line.startsWith('*')) {
            trade_offs.push(line.replace(/^[-*\s]+/, '').trim());
          }
        } else if (currentSec === 'context') {
          recommendation_context += (recommendation_context ? ' ' : '') + line.replace(/^[-*\s]+/, '').trim();
        }
      }

      return {
        headline,
        rationale: rationale || raw.slice(0, 220),
        strengths: strengths.length ? strengths : ['Calculated positive priority-weighted score contribution'],
        trade_offs: trade_offs.length ? trade_offs : ['Balanced operational trade-off profile across dimensions'],
        recommendation_context: recommendation_context || 'Assessed against municipal feasibility standards.',
      };
    }
    return null;
  };

  const decisionRationale = getDecisionRationale();

  // Helper to render markdown text with basic formatting (paragraphs, bold, bullet points)
  const renderFormattedText = (text) => {
    if (!text) return null;

    const lines = text.split('\n');
    const elements = [];
    let listItems = [];

    const flushList = (key) => {
      if (listItems.length > 0) {
        elements.push(
          <ul key={`ul-${key}`} className="space-y-1 my-2 list-disc list-inside text-xs text-slate-700">
            {listItems.map((item, idx) => (
              <li key={idx} dangerouslySetInnerHTML={{ __html: formatInlineMarkdown(item) }} />
            ))}
          </ul>
        );
        listItems = [];
      }
    };

    lines.forEach((line, index) => {
      const trimmed = line.trim();

      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        listItems.push(trimmed.substring(2));
      } else {
        flushList(index);
        if (trimmed.startsWith('### ')) {
          elements.push(
            <h4 key={index} className="text-xs font-bold text-slate-900 uppercase tracking-wider mt-3 mb-1">
              {trimmed.substring(4)}
            </h4>
          );
        } else if (trimmed.startsWith('*> [!')) {
          elements.push(
            <div key={index} className="my-2 p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-[11px] text-amber-900 italic">
              {trimmed.replace(/^\*>\s*\[!.*?\]\s*/, '')}
            </div>
          );
        } else if (trimmed.length > 0) {
          elements.push(
            <p
              key={index}
              className="text-xs text-slate-700 leading-relaxed my-1.5"
              dangerouslySetInnerHTML={{ __html: formatInlineMarkdown(trimmed) }}
            />
          );
        }
      }
    });

    flushList(lines.length);
    return elements;
  };

  const formatInlineMarkdown = (str) => {
    return str
      .replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-slate-900">$1</strong>')
      .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 rounded bg-slate-100 font-mono text-[11px] text-slate-800">$1</code>')
      .replace(/\*(.*?)\*/g, '<em class="italic">$1</em>');
  };

  const isGemini = narrative?.generated_by === 'gemini';
  const isGroq = narrative?.generated_by === 'groq';
  const isFallback = narrative?.generated_by === 'fallback' || narrative?.generated_by === 'deterministic';

  // Filter out decision_rationale from detailed sections list to avoid redundancy with the featured card
  const otherSections = Object.entries(narrative?.sections || {}).filter(
    ([secKey]) => secKey !== 'decision_rationale'
  );

  return (
    <div className="bg-white rounded-xl shadow-xs border border-slate-200 p-6 mb-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 mb-5 gap-3">
        <div className="flex items-start space-x-3">
          <div className="p-2.5 rounded-xl bg-purple-50 text-purple-600 border border-purple-200 shadow-2xs mt-0.5">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2 flex-wrap gap-1">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900">
                Municipal Decision Support &amp; AI Narrative Briefing
              </h2>
              {isGemini && (
                <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-purple-100 text-purple-800 border border-purple-200">
                  <Sparkles className="w-3 h-3 text-purple-600" />
                  <span>Synthesized with Gemini AI</span>
                </span>
              )}
              {isGroq && (
                <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
                  <Sparkles className="w-3 h-3 text-emerald-600" />
                  <span>Synthesized with Groq AI</span>
                </span>
              )}
              {isFallback && (
                <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-700 border border-slate-300">
                  <ShieldCheck className="w-3 h-3 text-slate-500" />
                  <span>Deterministic Mode</span>
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Translates precomputed municipal scores, spatial context, infrastructure gaps, and feasibility constraints into context-aware decision explanations.
            </p>
          </div>
        </div>

        {/* Action Buttons: Download PDF & Generate Briefing */}
        <div className="flex flex-wrap items-center gap-2 self-start sm:self-auto flex-shrink-0">
          {onDownloadReport && (
            <button
              type="button"
              onClick={() => onDownloadReport(true)}
              disabled={downloadingReport || disabled}
              title="Download official 6-page Municipal Decision Report PDF"
              className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 disabled:bg-slate-100 disabled:text-slate-400 text-xs font-semibold rounded-lg flex items-center justify-center space-x-1.5 transition-all border border-slate-300 shadow-2xs cursor-pointer disabled:cursor-not-allowed"
            >
              <FileDown className={`w-3.5 h-3.5 ${downloadingReport ? 'animate-bounce' : ''}`} />
              <span>{downloadingReport ? 'Compiling PDF...' : 'Download Decision PDF'}</span>
            </button>
          )}

          <button
            type="button"
            onClick={handleManualGenerate}
            disabled={loading || disabled}
            className="px-3.5 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-300 text-white text-xs font-semibold rounded-lg flex items-center justify-center space-x-1.5 transition-all shadow-xs cursor-pointer disabled:cursor-not-allowed"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>{narrative ? 'Re-synthesize Decision Briefing' : 'Synthesize Decision Briefing'}</span>
          </button>
        </div>
      </div>

      {/* Narrative Type Selector Tabs */}
      <div className="flex items-center flex-wrap gap-2 mb-5 pb-3 border-b border-slate-150">
        <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mr-1">
          Briefing Scope:
        </span>
        {NARRATIVE_TYPES.map((type) => {
          const isActive = selectedType === type.id;
          return (
            <button
              key={type.id}
              type="button"
              onClick={() => handleTypeSelect(type.id)}
              disabled={loading || disabled}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? 'bg-purple-50 text-purple-700 font-semibold border border-purple-200 shadow-xs'
                  : 'bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200'
              }`}
            >
              <span>{type.label}</span>
            </button>
          );
        })}
      </div>

      {/* Error Banner */}
      {error && (
        <div className="mb-5 p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start space-x-2">
          <AlertCircle className="w-4 h-4 text-rose-600 mt-0.5 flex-shrink-0" />
          <div>
            <strong>Synthesis Error:</strong> {error.message || 'Unable to generate narrative explanation.'}
          </div>
        </div>
      )}

      {/* Fallback Notice when offline */}
      {isFallback && narrative?.fallback_reason && (
        <div className="mb-5 p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-600 flex items-start space-x-2">
          <Info className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
          <div className="text-[11px]">
            <strong className="text-slate-800">Deterministic Mode:</strong> {narrative.fallback_reason}
          </div>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && (
        <div className="p-6 rounded-xl border border-purple-100 bg-purple-50/40 space-y-4 animate-pulse">
          <div className="flex items-center space-x-2 text-purple-700">
            <Sparkles className="w-4 h-4 animate-spin" />
            <span className="text-xs font-semibold">Synthesizing context-aware municipal decision rationale...</span>
          </div>
          <div className="h-4 bg-purple-100 rounded w-3/4" />
          <div className="h-3 bg-purple-100/70 rounded w-full" />
          <div className="h-3 bg-purple-100/70 rounded w-5/6" />
        </div>
      )}

      {/* Empty State before first generation */}
      {!narrative && !loading && !error && (
        <div className="p-8 rounded-xl border border-dashed border-slate-200 bg-slate-50 text-center">
          <Bot className="w-8 h-8 text-slate-400 mx-auto mb-2" />
          <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
            No Decision Briefing Generated Yet
          </h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto mb-4">
            Click &ldquo;Synthesize Decision Briefing&rdquo; to generate a context-aware municipal decision rationale, detailing ranking drivers, gap mitigation, strengths, trade-offs, and comparative advantage.
          </p>
          <button
            type="button"
            onClick={handleManualGenerate}
            disabled={disabled}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-xs font-semibold rounded-lg inline-flex items-center space-x-1.5 transition-all shadow-xs"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Generate Decision Briefing Now</span>
          </button>
        </div>
      )}

      {/* Render Narrative */}
      {narrative && !loading && (
        <div className="space-y-5 animate-in fade-in duration-300">
          {/* FEATURED: Phase 4.1 Municipal Decision Rationale Section */}
          {decisionRationale && (
            <div className="p-5 sm:p-6 rounded-xl border-2 border-purple-200 bg-gradient-to-br from-purple-50/40 via-white to-indigo-50/30 shadow-xs">
              {/* Badge & Title */}
              <div className="flex items-center justify-between pb-3 border-b border-purple-100 mb-4 gap-2">
                <div className="flex items-center space-x-2">
                  <div className="p-2 rounded-lg bg-purple-600 text-white shadow-xs">
                    <Award className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="text-[10px] font-bold tracking-wider text-purple-700 uppercase">
                      Municipal Decision-Support
                    </span>
                    <h3 className="text-sm sm:text-base font-bold text-slate-900 leading-snug">
                      {decisionRationale.headline || 'Decision Rationale'}
                    </h3>
                  </div>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-purple-100 text-purple-800 border border-purple-200 self-start sm:self-auto flex-shrink-0">
                  {isFallback ? 'Deterministic Rationale' : 'Context-Aware Explanation'}
                </span>
              </div>

              {/* Rationale Paragraph */}
              <div className="bg-white/80 backdrop-blur-xs p-4 rounded-xl border border-purple-100/80 mb-4 text-xs sm:text-sm text-slate-800 leading-relaxed shadow-2xs">
                <div dangerouslySetInnerHTML={{ __html: formatInlineMarkdown(decisionRationale.rationale) }} />
              </div>

              {/* Strengths & Trade-offs 2-Column Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 mb-3.5">
                {/* Strengths */}
                <div className="p-4 rounded-xl bg-emerald-50/70 border border-emerald-200/80">
                  <div className="flex items-center space-x-1.5 mb-2.5 pb-1.5 border-b border-emerald-200/60">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-950">
                      Strongest Impact Dimensions &amp; Gaps Addressed
                    </h4>
                  </div>
                  <ul className="space-y-2 text-xs text-slate-700">
                    {(decisionRationale.strengths || []).map((str, idx) => (
                      <li key={idx} className="flex items-start space-x-2">
                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1.5 flex-shrink-0" />
                        <span dangerouslySetInnerHTML={{ __html: formatInlineMarkdown(str) }} />
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Trade-offs & Weaknesses */}
                <div className="p-4 rounded-xl bg-amber-50/70 border border-amber-200/80">
                  <div className="flex items-center space-x-1.5 mb-2.5 pb-1.5 border-b border-amber-200/60">
                    <Scale className="w-4 h-4 text-amber-600 flex-shrink-0" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-amber-950">
                      Trade-offs &amp; Weaker Dimensions
                    </h4>
                  </div>
                  <ul className="space-y-2 text-xs text-slate-700">
                    {(decisionRationale.trade_offs || []).map((tf, idx) => (
                      <li key={idx} className="flex items-start space-x-2">
                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500 mt-1.5 flex-shrink-0" />
                        <span dangerouslySetInnerHTML={{ __html: formatInlineMarkdown(tf) }} />
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Recommendation Context & Feasibility */}
              {decisionRationale.recommendation_context && (
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/90 flex items-start space-x-2.5 text-xs text-slate-700">
                  <ShieldCheck className="w-4 h-4 text-indigo-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <strong className="text-slate-900 block mb-0.5">
                      Planning Sanction &amp; Comparative Margin:
                    </strong>
                    <div dangerouslySetInnerHTML={{ __html: formatInlineMarkdown(decisionRationale.recommendation_context) }} />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Collapsible Header for Detailed Assessment Sections */}
          {otherSections.length > 0 && (
            <div className="pt-2">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  Detailed Municipal Analysis Sections ({otherSections.length})
                </span>
                <button
                  type="button"
                  onClick={() => setShowDetailedSections(!showDetailedSections)}
                  className="text-xs text-purple-700 hover:text-purple-800 font-medium inline-flex items-center space-x-1"
                >
                  <span>{showDetailedSections ? 'Hide Detailed Sections' : 'Show Detailed Sections'}</span>
                  {showDetailedSections ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                </button>
              </div>

              {/* Detailed Sections List */}
              {showDetailedSections && (
                <div className="space-y-4">
                  {otherSections.map(([secKey, secContent]) => {
                    const meta = SECTION_METADATA[secKey] || {
                      title: secKey.replace(/_/g, ' ').toUpperCase(),
                      icon: FileText,
                      accent: 'slate',
                    };
                    const Icon = meta.icon;

                    return (
                      <div
                        key={secKey}
                        className="p-5 rounded-xl border border-slate-200 bg-slate-50/50 hover:bg-slate-50 transition-colors"
                      >
                        <div className="flex items-center space-x-2.5 mb-2.5 pb-2 border-b border-slate-200/80">
                          <div className="p-1.5 rounded-lg bg-white border border-slate-200 text-purple-700 shadow-2xs">
                            <Icon className="w-4 h-4" />
                          </div>
                          <h3 className="text-xs font-bold text-slate-900 tracking-wide uppercase">
                            {meta.title}
                          </h3>
                        </div>

                        <div className="text-xs text-slate-700 space-y-1">
                          {renderFormattedText(secContent)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Strict Architectural Boundary Disclaimer */}
      <div className="mt-5 pt-4 border-t border-slate-200 flex items-start space-x-2.5 text-[11px] text-slate-500">
        <Info className="w-4 h-4 text-purple-500 mt-0.5 flex-shrink-0" />
        <p>
          <strong className="text-slate-700">CivicFork Architectural Constraint:</strong>{' '}
          <em>&ldquo;Python calculates. AI explains.&rdquo;</em> All underlying scores, rankings, dimension deltas,
          and feasibility checks are calculated deterministically by CivicFork. AI narrative synthesis provides decision-support
          and does not calculate, modify, or override numerical results.
        </p>
      </div>
    </div>
  );
}

export default AIExplanation;
