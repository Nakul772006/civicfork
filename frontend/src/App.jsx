import React, { useState } from 'react';
import { Layout } from './components/common/Layout';
import { useSession } from './hooks/useSession';
import { ErrorBanner } from './components/common/ErrorBanner';
import { LoadingSpinner } from './components/common/LoadingSpinner';
import { PlotMap } from './components/map/PlotMap';
import { ContextSummary } from './components/analysis/ContextSummary';
import { GapList } from './components/analysis/GapList';
import { ScenarioList } from './components/analysis/ScenarioList';
import { SimulationTable } from './components/scenarios/SimulationTable';
import { WeightControls } from './components/comparison/WeightControls';
import { DecisionSnapshot } from './components/comparison/DecisionSnapshot';
import { ScenarioRankingChart } from './components/analysis/ScenarioRankingChart';
import { DecisionStability } from './components/analysis/DecisionStability';
import { ImpactComparisonChart } from './components/analysis/ImpactComparisonChart';
import { RankingTable } from './components/comparison/RankingTable';
import { CounterfactualComparison } from './components/comparison/CounterfactualComparison';
import { FeasibilityPanel } from './components/feasibility/FeasibilityPanel';
import { AIExplanation } from './components/analysis/AIExplanation';
import { apiClient } from './api/client';
import { 
  Compass, 
  MapPin, 
  Layers, 
  BarChart3, 
  Sliders, 
  Trophy, 
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  ArrowRight
} from 'lucide-react';

export function App() {
  const {
    session,
    loading,
    error,
    activeStep,
    setLoading,
    setError,
    setActiveStep,
    updateSession,
    resetSession,
  } = useSession();

  const [selectedPlot, setSelectedPlot] = useState({
    lat: 12.3100,
    lng: 76.6500,
    radius_m: 2000,
    area_sqm: 3500.0,
    label: 'Mysuru City Center Parcel',
  });

  const [weights, setWeights] = useState({
    traffic: 1.0,
    cost: 1.0,
    environmental: 1.0,
    accessibility: 1.0,
    gap_improvement: 1.0,
    social_utility: 1.0,
  });

  const [counterfactualLoading, setCounterfactualLoading] = useState(false);
  const [feasibilityLoading, setFeasibilityLoading] = useState(false);
  const [explanation, setExplanation] = useState(null);
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [explanationError, setExplanationError] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);

  // Stage 1: Analyze Plot
  const handleAnalyze = async (plotPayload) => {
    setSelectedPlot(plotPayload);
    setLoading(true);
    setError(null);
    setExplanation(null);
    setExplanationError(null);

    try {
      const data = await apiClient.analyzePlot(plotPayload);
      updateSession({
        sessionId: data.session_id,
        plot: data.plot,
        contextSummary: data.context_summary,
        gaps: data.gaps,
        scenarios: data.scenarios || [],
        scoreMatrix: null,
        ranking: [],
        weightsApplied: null,
        counterfactual: null,
        verdicts: [],
        stability: null,
        geojson: {
          pois: data.poi_geojson,
          landuse: data.landuse_geojson,
          transport: data.transport_geojson,
        },
      });
      setActiveStep(2);
    } catch (err) {
      const msg = err.message || 'Analysis failed. Please verify the selected location and try again.';
      setError({
        code: err.code || 'ANALYSIS_ERROR',
        message: msg,
      });
    } finally {
      setLoading(false);
    }
  };

  // Stage 2: Simulate Scenarios
  const handleSimulate = async () => {
    if (!session.sessionId) {
      setError({
        code: 'MISSING_SESSION',
        message: 'No active session found. Please analyze a plot location first.',
      });
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await apiClient.simulateScenarios(session.sessionId);
      let verdicts = [];
      try {
        const feasData = await apiClient.checkFeasibility(session.sessionId);
        verdicts = feasData.verdicts || [];
      } catch {
        // Non-blocking if feasibility fetch encounters an issue during simulate
      }
      let stability = null;
      try {
        const stabData = await apiClient.checkStability(session.sessionId);
        stability = stabData.result || null;
      } catch {
        // Non-blocking if stability fetch encounters an issue during simulate
      }
      updateSession({
        scenarios: data.scenarios,
        scoreMatrix: data.score_matrix,
        ranking: data.default_ranking,
        weightsApplied: data.default_weights,
        verdicts,
        stability,
      });
      setActiveStep(3);
    } catch (err) {
      const msg = err.message || 'Simulation scoring failed. Please try again.';
      setError({
        code: err.code || 'SIMULATION_ERROR',
        message: msg,
      });
    } finally {
      setLoading(false);
    }
  };

  // Stage 3: Rank Scenarios by Municipal Priorities
  const handleRank = async (submittedWeights) => {
    if (!session.sessionId) {
      setError({
        code: 'MISSING_SESSION',
        message: 'No active session found. Please analyze and simulate first.',
      });
      return;
    }

    const currentWeights = submittedWeights || weights;
    setWeights(currentWeights);
    setLoading(true);
    setError(null);

    try {
      const data = await apiClient.rankScenarios(session.sessionId, currentWeights);
      updateSession({
        ranking: data.ranking,
        weightsApplied: data.weights_applied,
        stability: data.stability || null,
      });
      setActiveStep(4);
      if (!session.verdicts || session.verdicts.length === 0) {
        handleCheckFeasibility();
      }
    } catch (err) {
      const msg = err.message || 'Ranking calculation failed. Please check weight values and try again.';
      setError({
        code: err.code || 'RANKING_ERROR',
        message: msg,
      });
    } finally {
      setLoading(false);
    }
  };

  // Stage 4: Pairwise Counterfactual Comparison
  const handleCompareCounterfactual = async (scenarioAId, scenarioBId) => {
    if (!session.sessionId) {
      setError({
        code: 'MISSING_SESSION',
        message: 'No active session found. Please analyze and simulate first.',
      });
      return;
    }
    if (!session.scoreMatrix) {
      setError({
        code: 'MISSING_PREREQUISITE',
        message: 'Simulation must be completed before running counterfactual comparison.',
      });
      return;
    }
    if (scenarioAId === scenarioBId) {
      setError({
        code: 'VALIDATION_ERROR',
        message: 'Please select two different scenarios to compare.',
      });
      return;
    }

    setCounterfactualLoading(true);
    setError(null);

    try {
      const data = await apiClient.compareScenarios(session.sessionId, scenarioAId, scenarioBId);
      updateSession({
        counterfactual: data.result,
      });
    } catch (err) {
      const msg = err.message || 'Counterfactual comparison failed. Please try again.';
      setError({
        code: err.code || 'COUNTERFACTUAL_ERROR',
        message: msg,
      });
    } finally {
      setCounterfactualLoading(false);
    }
  };

  // Stage 5: Scenario Feasibility & Constraints Check
  const handleCheckFeasibility = async (scenarioId = null) => {
    if (!session.sessionId) {
      setError({
        code: 'MISSING_SESSION',
        message: 'No active session found. Please analyze a plot first.',
      });
      return;
    }

    setFeasibilityLoading(true);
    try {
      const data = await apiClient.checkFeasibility(session.sessionId, scenarioId);
      const incoming = data.verdicts || [];
      if (!scenarioId || !session.verdicts || session.verdicts.length === 0) {
        updateSession({ verdicts: incoming });
      } else {
        const existingMap = new Map((session.verdicts || []).map((v) => [v.scenario_id, v]));
        incoming.forEach((v) => existingMap.set(v.scenario_id, v));
        updateSession({ verdicts: Array.from(existingMap.values()) });
      }
    } catch (err) {
      const msg = err.message || 'Feasibility check failed. Please try again.';
      setError({
        code: err.code || 'FEASIBILITY_ERROR',
        message: msg,
      });
    } finally {
      setFeasibilityLoading(false);
    }
  };

  // Stage 6: AI Narrative Explanation via Gemini
  const handleGenerateExplanation = async (narrativeType = 'full_report') => {
    if (!session.sessionId) {
      setError({
        code: 'MISSING_SESSION',
        message: 'No active session found. Please analyze a plot first.',
      });
      return;
    }

    setExplanationLoading(true);
    setExplanationError(null);

    try {
      const data = await apiClient.generateExplanation(session.sessionId, narrativeType);
      const narrative = data.narrative;
      setExplanation(narrative);
      updateSession({
        narratives: {
          ...(session.narratives || {}),
          [narrativeType]: narrative,
        },
      });
    } catch (err) {
      const msg = err.message || 'Failed to synthesize narrative briefing.';
      setExplanationError({
        code: err.code || 'EXPLAIN_ERROR',
        message: msg,
      });
    } finally {
      setExplanationLoading(false);
    }
  };

  // Stage 7 / Phase 4.5: Download Municipal Decision PDF Report
  const handleDownloadReport = async (includeNarrative = true) => {
    if (!session.sessionId) {
      setError({
        code: 'MISSING_SESSION',
        message: 'No active session found. Please analyze a parcel first.',
      });
      return;
    }

    setReportLoading(true);
    setError(null);

    try {
      const blob = await apiClient.downloadReport(session.sessionId, includeNarrative);
      const url = window.URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      const scenarioSlug = session.ranking?.[0]?.scenario_id || 'decision';
      a.download = `CivicFork_Decision_Report_${scenarioSlug}_${session.sessionId.substring(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.parentNode.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      let msg = err.message || 'Failed to download municipal report PDF.';
      if (err.response?.data instanceof Blob) {
        try {
          const text = await err.response.data.text();
          const parsed = JSON.parse(text);
          if (parsed.error?.message) {
            msg = parsed.error.message;
          }
        } catch {
          // ignore
        }
      }
      setError({
        code: err.code || 'REPORT_ERROR',
        message: msg,
      });
    } finally {
      setReportLoading(false);
    }
  };

  const handleReset = () => {
    resetSession();
    setExplanation(null);
    setExplanationError(null);
    setSelectedPlot({
      lat: 12.3100,
      lng: 76.6500,
      radius_m: 2000,
      area_sqm: 3500.0,
      label: 'Mysuru City Center Parcel',
    });
  };

  return (
    <Layout activeStep={activeStep} onStepChange={setActiveStep}>
      {/* Session Hero Banner */}
      <div className="bg-white rounded-xl shadow-xs border border-slate-200 p-5 mb-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2 text-blue-600 mb-1">
              <Compass className="w-4 h-4" />
              <span className="text-[11px] font-bold uppercase tracking-wider">
                Municipal Decision-Support Platform · Mysuru Study Area
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
              Urban Policy &amp; Infrastructure Decision Dashboard
            </h1>
            <p className="text-xs sm:text-sm text-slate-600 mt-1 max-w-3xl leading-relaxed">
              Deterministic geospatial impact simulation: select an urban parcel, analyze surrounding infrastructure gaps, evaluate six normalized performance dimensions across seven scenarios, and compare policy alternatives with counterfactual rigor.
            </p>
          </div>

          <div className="flex items-center space-x-3 bg-slate-50 border border-slate-200 rounded-xl p-3 self-start md:self-auto flex-shrink-0">
            <div>
              <span className="text-[10px] text-slate-500 uppercase tracking-wider block font-semibold">
                Analytical Session
              </span>
              <span className="text-xs font-mono font-bold text-slate-800">
                {session.sessionId ? `${session.sessionId.substring(0, 8)}...` : 'Ready to Start'}
              </span>
            </div>
            {session.sessionId && (
              <button
                type="button"
                onClick={handleReset}
                title="Reset simulation session"
                className="p-1.5 rounded-lg hover:bg-slate-200 text-slate-600 transition-colors cursor-pointer"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Global Error Banner */}
      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

      {/* Global Loading Spinner */}
      {loading && (
        <div className="my-6 bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <LoadingSpinner
            message={
              activeStep === 1
                ? 'Extracting OSM features & computing infrastructure gaps...'
                : activeStep === 2
                ? 'Simulating 6 impact dimensions across all 7 alternatives...'
                : 'Applying municipal priority weights & ordering leaderboard...'
            }
          />
        </div>
      )}

      {/* Step 1: Map Plot Selection */}
      <section className={activeStep === 1 ? 'block' : 'hidden'}>
        <PlotMap
          selectedPlot={selectedPlot}
          onPlotChange={setSelectedPlot}
          onAnalyze={handleAnalyze}
          loading={loading}
        />
      </section>

      {/* Step 2: Analysis Results (Context + Gaps + Scenarios) */}
      <section className={activeStep === 2 ? 'block' : 'hidden'}>
        <div className="mb-4 flex items-center justify-between">
          <button
            type="button"
            onClick={() => setActiveStep(1)}
            className="text-xs text-blue-600 hover:text-blue-800 font-semibold flex items-center space-x-1"
          >
            <span>&larr; Back to Plot Selection</span>
          </button>
          <span className="text-xs text-slate-500 font-mono">
            Plot: ({selectedPlot.lat.toFixed(4)}, {selectedPlot.lng.toFixed(4)}) · Radius: {selectedPlot.radius_m}m
          </span>
        </div>

        <ContextSummary contextSummary={session.contextSummary} plot={session.plot || selectedPlot} />
        <GapList gaps={session.gaps} />
        <ScenarioList
          scenarios={session.scenarios}
          onRunSimulation={handleSimulate}
          simulating={loading}
        />
      </section>

      {/* Step 3: Simulation Results (6 Dimensions x 7 Scenarios Table) */}
      <section className={activeStep === 3 ? 'block' : 'hidden'}>
        <div className="mb-4 flex items-center justify-between">
          <button
            type="button"
            onClick={() => setActiveStep(2)}
            className="text-xs text-blue-600 hover:text-blue-800 font-semibold flex items-center space-x-1"
          >
            <span>&larr; Back to Urban Context &amp; Gaps</span>
          </button>
          <span className="text-xs text-slate-500 font-mono">
            Evaluated: 7 Scenarios × 6 Normalized Dimensions
          </span>
        </div>

        <SimulationTable
          scoreMatrix={session.scoreMatrix}
          scenarios={session.scenarios}
          onProceedToRank={() => setActiveStep(4)}
        />
      </section>

      {/* Step 4: Weighting & Ranking Results */}
      <section className={activeStep === 4 ? 'block' : 'hidden'}>
        <div className="mb-4 flex items-center justify-between">
          <button
            type="button"
            onClick={() => setActiveStep(3)}
            className="text-xs text-blue-600 hover:text-blue-800 font-semibold flex items-center space-x-1"
          >
            <span>&larr; Back to Simulation Matrix</span>
          </button>
          <span className="text-xs text-slate-500 font-mono">
            Municipal Weighting &amp; Leaderboard
          </span>
        </div>

        <WeightControls
          weights={weights}
          onWeightChange={setWeights}
          onRank={handleRank}
          ranking={loading}
        />

        <DecisionSnapshot
          ranking={session.ranking}
          scoreMatrix={session.scoreMatrix}
          scenarios={session.scenarios}
          verdicts={session.verdicts || []}
          gaps={session.gaps || []}
          plot={session.plot || selectedPlot}
          contextSummary={session.contextSummary}
          onDownloadReport={handleDownloadReport}
          reportLoading={reportLoading}
        />

        <ScenarioRankingChart
          ranking={session.ranking}
          loading={loading}
        />

        <DecisionStability
          stabilityResult={session.stability}
          loading={loading}
        />

        <ImpactComparisonChart
          ranking={session.ranking}
          scoreMatrix={session.scoreMatrix}
          loading={loading}
        />

        <CounterfactualComparison
          scenarios={session.scenarios}
          ranking={session.ranking}
          counterfactualResult={session.counterfactual}
          onCompare={handleCompareCounterfactual}
          loading={counterfactualLoading}
          narrative={explanation}
        />

        <FeasibilityPanel
          scenarios={session.scenarios}
          ranking={session.ranking}
          verdicts={session.verdicts || []}
          onCheckFeasibility={handleCheckFeasibility}
          loading={feasibilityLoading}
        />

        <AIExplanation
          narrative={explanation}
          loading={explanationLoading}
          error={explanationError}
          onGenerate={handleGenerateExplanation}
          disabled={!session.sessionId}
          onDownloadReport={handleDownloadReport}
          downloadingReport={reportLoading}
        />

        <RankingTable
          ranking={session.ranking}
          weightsApplied={session.weightsApplied}
        />
      </section>
    </Layout>
  );
}

export default App;
