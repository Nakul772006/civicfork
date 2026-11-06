"""Tests for Multi-Provider AI Narrative Synthesis Service (Groq, Gemini, Deterministic) and /api/explain."""

import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import httpx

from app.main import app
from app.models.domain import (
    ContextSummary,
    CounterfactualResult,
    DimensionDelta,
    FeasibilityCheck,
    FeasibilityVerdict,
    InfrastructureGap,
    NarrativeRequest,
    PlotLocation,
    RankedScenario,
    Scenario,
    ScoreMatrix,
)
from app.services.context_analyzer import get_context_analyzer
from app.services.gap_analyzer import get_gap_analyzer
from app.services.scenario_generator import get_scenario_generator
from app.services.impact_simulator import get_impact_simulator
from app.services.ranking_engine import get_ranking_engine
from app.services.feasibility_checker import get_feasibility_checker
from app.services.counterfactual_engine import get_counterfactual_engine
from app.services.narrative_service import (
    CLEAN_DETERMINISTIC_STATUS,
    CLEAN_FALLBACK_STATUS,
    CLEAN_NO_KEY_STATUS,
    NarrativeService,
    get_narrative_service,
)


@pytest.fixture
def sample_narrative_request():
    plot = PlotLocation(lat=12.3100, lng=76.6500, radius_m=2000, area_sqm=3500.0, label="Test Parcel")
    ctx = get_context_analyzer().analyze(plot)
    gaps = get_gap_analyzer().analyze(plot, ctx)
    scenarios = get_scenario_generator().generate(plot, ctx, gaps)
    score_matrix = get_impact_simulator().simulate(scenarios, ctx, gaps)
    ranking = get_ranking_engine().rank(score_matrix, scenarios=scenarios)
    feasibility = get_feasibility_checker().evaluate_all(scenarios, plot, ctx, gaps)
    counterfactual = get_counterfactual_engine().compare("park", "healthcare", score_matrix, scenarios)

    return NarrativeRequest(
        narrative_type="full_report",
        plot=plot,
        context_summary=ctx.summary,
        gaps=gaps,
        scenarios=scenarios,
        score_matrix=score_matrix,
        ranking=ranking,
        feasibility=feasibility,
        counterfactual=counterfactual,
    )


def test_ai_input_boundary_guarantee(sample_narrative_request):
    """Verify that summary excludes raw GeoJSON, raw POI nodes, and credentials."""
    service = NarrativeService(provider="deterministic")
    summary = service.build_compact_summary(sample_narrative_request)

    # Allowed keys
    assert "plot" in summary
    assert "urban_context" in summary
    assert "infrastructure_gaps" in summary
    assert "scenarios" in summary
    assert "ranking" in summary
    assert "feasibility" in summary
    assert "counterfactual" in summary

    # Strict prohibitions
    summary_str = str(summary)
    assert "FeatureCollection" not in summary_str
    assert "geometry" not in summary_str
    assert "coordinates" not in summary["urban_context"]
    assert "api_key" not in summary_str
    assert "session_store" not in summary_str


def test_deterministic_fallback_when_no_api_key(sample_narrative_request):
    """Verify clean deterministic fallback narrative when no API key is configured."""
    service = NarrativeService(provider="gemini", api_key="", groq_api_key="")
    assert not service.is_ai_available

    res = service.generate_narrative(sample_narrative_request)
    assert res.narrative_type == "full_report"
    assert res.generated_by == "fallback"
    assert res.fallback_reason is not None
    assert "deterministic" in res.fallback_reason.lower()
    # Ensure raw API key name or env variable is sanitized
    assert "503" not in res.fallback_reason

    # Verify all 6 full_report sections are populated
    for sec in ["overview", "urban_context", "infrastructure_gaps", "recommended_scenario", "trade_offs", "feasibility"]:
        assert sec in res.sections
        assert len(res.sections[sec]) > 20

    # Verify authoritative numbers are cited in fallback text
    assert "12.3100" in res.sections["overview"]
    assert "3,500" in res.sections["overview"]
    assert str(sample_narrative_request.context_summary.total_pois) in res.sections["urban_context"]
    assert sample_narrative_request.context_summary.dominant_landuse in res.sections["urban_context"]
    assert "FEASIBLE" in res.sections["feasibility"]


def test_deterministic_fallback_when_gemini_raises(sample_narrative_request):
    """Verify graceful fallback if Gemini client throws an exception (quota, network, etc.)."""
    service = NarrativeService(provider="gemini", gemini_api_key="fake-gemini-key")
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("503 UNAVAILABLE: Model overloaded")
    service._client = mock_client

    res = service.generate_narrative(sample_narrative_request)
    assert res.generated_by == "fallback"
    # Ensure error is sanitized - NO raw 503 or traceback in user-facing fallback reason
    assert "503" not in res.fallback_reason
    assert "overloaded" not in res.fallback_reason
    assert "deterministic" in res.fallback_reason.lower()
    assert "overview" in res.sections


def test_mocked_gemini_successful_synthesis(sample_narrative_request):
    """Verify successful Gemini synthesis parsing when API returns valid structured JSON."""
    service = NarrativeService(provider="gemini", gemini_api_key="fake-key")
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = """{
      "overview": "Synthesized AI overview for Mysuru parcel via Gemini.",
      "urban_context": "Detailed AI contextual narrative.",
      "infrastructure_gaps": "AI explanation of service gaps.",
      "recommended_scenario": "Healthcare recommended with 78.5 score.",
      "trade_offs": "Trade-offs between park and clinic.",
      "feasibility": "All 4 constraint checks passed."
    }"""
    mock_client.models.generate_content.return_value = mock_response
    service._client = mock_client

    res = service.generate_narrative(sample_narrative_request)
    assert res.generated_by == "gemini"
    assert res.fallback_reason is None
    assert "Gemini" in res.sections["overview"]
    assert res.sections["recommended_scenario"] == "Healthcare recommended with 78.5 score."


def test_groq_successful_synthesis(sample_narrative_request):
    """Verify successful Groq OpenAI-compatible synthesis when API returns valid structured JSON."""
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "overview": "Synthesized AI overview for Mysuru parcel via Groq Llama-3.3.",
                        "urban_context": "Groq-generated urban context narrative.",
                        "infrastructure_gaps": "Identified service deficit explanation.",
                        "recommended_scenario": "Parks / Recreational Space recommended.",
                        "trade_offs": "Trade-off analysis between alternatives.",
                        "feasibility": "All physical constraints verified.",
                    })
                }
            }
        ]
    }
    mock_http.post.return_value = mock_resp

    service = NarrativeService(
        provider="groq",
        groq_api_key="gsk_test_mock_key",
        groq_model="llama-3.3-70b-versatile",
        http_client=mock_http,
    )
    assert service.is_ai_available

    res = service.generate_narrative(sample_narrative_request)
    assert res.generated_by == "groq"
    assert res.fallback_reason is None
    assert "Groq Llama-3.3" in res.sections["overview"]
    assert "Parks" in res.sections["recommended_scenario"]

    # Verify Groq request structure
    mock_http.post.assert_called_once()
    call_kwargs = mock_http.post.call_args[1]
    assert "https://api.groq.com/openai/v1/chat/completions" in mock_http.post.call_args[0]
    assert call_kwargs["headers"]["Authorization"] == "Bearer gsk_test_mock_key"
    assert call_kwargs["json"]["model"] == "llama-3.3-70b-versatile"
    assert call_kwargs["json"]["response_format"] == {"type": "json_object"}


def test_groq_failure_fallback(sample_narrative_request):
    """Verify that Groq failure falls back to deterministic template without exposing raw 503 or error JSON."""
    mock_http = MagicMock()
    mock_http.post.side_effect = httpx.HTTPStatusError(
        message="503 Service Unavailable",
        request=MagicMock(),
        response=MagicMock(status_code=503, text='{"error": {"code": 503, "message": "High demand"}}'),
    )

    service = NarrativeService(
        provider="groq",
        groq_api_key="gsk_test_key",
        http_client=mock_http,
    )

    res = service.generate_narrative(sample_narrative_request)
    assert res.generated_by == "fallback"
    assert res.fallback_reason is not None

    # Error sanitization assertions
    assert "503" not in res.fallback_reason
    assert "High demand" not in res.fallback_reason
    assert "gsk_" not in res.fallback_reason
    assert "error" not in res.fallback_reason.lower() or "explanation engine" in res.fallback_reason.lower()
    assert "deterministic" in res.fallback_reason.lower()

    # All sections populated
    assert "overview" in res.sections
    assert "feasibility" in res.sections


def test_auto_provider_hierarchy_groq_first(sample_narrative_request):
    """Verify that 'auto' provider attempts Groq first and succeeds without invoking Gemini."""
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "overview": "Synthesized via Groq in auto mode.",
                        "urban_context": "Context text.",
                        "infrastructure_gaps": "Gaps text.",
                        "recommended_scenario": "Scenario text.",
                        "trade_offs": "Trade-offs text.",
                        "feasibility": "Feasibility text.",
                    })
                }
            }
        ]
    }
    mock_http.post.return_value = mock_resp

    mock_gemini = MagicMock()

    service = NarrativeService(
        provider="auto",
        groq_api_key="gsk_test_key",
        gemini_api_key="fake-gemini-key",
        http_client=mock_http,
    )
    service._client = mock_gemini

    res = service.generate_narrative(sample_narrative_request)
    assert res.generated_by == "groq"
    assert res.fallback_reason is None

    # Gemini was not called
    mock_gemini.models.generate_content.assert_not_called()


def test_auto_provider_groq_fails_gemini_succeeds(sample_narrative_request):
    """Verify that 'auto' provider falls back to Gemini when Groq fails."""
    mock_http = MagicMock()
    mock_http.post.side_effect = httpx.ConnectError("Connection refused")

    mock_gemini = MagicMock()
    mock_gemini_resp = MagicMock()
    mock_gemini_resp.text = """{
      "overview": "Synthesized via Gemini fallback in auto mode.",
      "urban_context": "Context text.",
      "infrastructure_gaps": "Gaps text.",
      "recommended_scenario": "Scenario text.",
      "trade_offs": "Trade-offs text.",
      "feasibility": "Feasibility text."
    }"""
    mock_gemini.models.generate_content.return_value = mock_gemini_resp

    service = NarrativeService(
        provider="auto",
        groq_api_key="gsk_test_key",
        gemini_api_key="fake-gemini-key",
        http_client=mock_http,
    )
    service._client = mock_gemini

    res = service.generate_narrative(sample_narrative_request)
    assert res.generated_by == "gemini"
    assert res.fallback_reason is None
    assert "Gemini fallback" in res.sections["overview"]


def test_auto_provider_both_fail_fallback(sample_narrative_request):
    """Verify that 'auto' provider falls back to deterministic template if both Groq and Gemini fail."""
    mock_http = MagicMock()
    mock_http.post.side_effect = httpx.ConnectError("Groq offline")

    mock_gemini = MagicMock()
    mock_gemini.models.generate_content.side_effect = RuntimeError("Gemini 503 UNAVAILABLE")

    service = NarrativeService(
        provider="auto",
        groq_api_key="gsk_test_key",
        gemini_api_key="fake-gemini-key",
        http_client=mock_http,
    )
    service._client = mock_gemini

    res = service.generate_narrative(sample_narrative_request)
    assert res.generated_by == "fallback"
    assert "deterministic" in res.fallback_reason.lower()
    # Zero exposure of 503 or stack trace
    assert "503" not in res.fallback_reason
    assert "Traceback" not in res.fallback_reason
    assert "gsk_" not in res.fallback_reason


def test_deterministic_provider_no_external_calls(sample_narrative_request):
    """Verify that 'deterministic' mode never makes network calls even if keys are provided."""
    mock_http = MagicMock()
    mock_gemini = MagicMock()

    service = NarrativeService(
        provider="deterministic",
        groq_api_key="gsk_real_looking_key",
        gemini_api_key="gemini_real_looking_key",
        http_client=mock_http,
    )
    service._client = mock_gemini

    assert not service.is_ai_available

    res = service.generate_narrative(sample_narrative_request)
    assert res.generated_by == "deterministic"
    assert "deterministic" in res.fallback_reason.lower()

    # Verify zero external network calls
    mock_http.post.assert_not_called()
    mock_gemini.models.generate_content.assert_not_called()


def test_numerical_isolation_across_providers(sample_narrative_request):
    """Verify that changing AI provider has zero impact on scores, ranking, feasibility, or counterfactuals."""
    providers_to_test = ["deterministic", "gemini", "groq", "auto"]

    # Baseline calculations from sample request
    expected_ranking = [r.scenario_id for r in sample_narrative_request.ranking]
    expected_scores = {
        s.scenario_id: [round(ds.score, 1) for ds in s.scores]
        for s in sample_narrative_request.score_matrix.scenario_scores
    }
    expected_cf_delta = sample_narrative_request.counterfactual.net_delta
    expected_feas_verdicts = [f.feasible for f in sample_narrative_request.feasibility]

    for prov in providers_to_test:
        svc = NarrativeService(provider=prov, groq_api_key="", gemini_api_key="")
        res = svc.generate_narrative(sample_narrative_request)

        # Output is text narrative only
        assert isinstance(res.sections, dict)

        # Engine domain models remain strictly unmodified
        actual_ranking = [r.scenario_id for r in sample_narrative_request.ranking]
        actual_scores = {
            s.scenario_id: [round(ds.score, 1) for ds in s.scores]
            for s in sample_narrative_request.score_matrix.scenario_scores
        }
        assert actual_ranking == expected_ranking
        assert actual_scores == expected_scores
        assert sample_narrative_request.counterfactual.net_delta == expected_cf_delta
        assert [f.feasible for f in sample_narrative_request.feasibility] == expected_feas_verdicts


def test_error_sanitization_guarantee(sample_narrative_request):
    """Verify that sensitive tokens, 503 errors, stack traces, and JSON payloads never reach fallback_reason."""
    raw_sensitive_cases = [
        RuntimeError("ServerError: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'High demand'}}"),
        ValueError("Invalid API key: TEST_API_KEY_REDACTED"),
        Exception("Traceback (most recent call last):\n  File 'app/services/narrative_service.py', line 240, in generate"),
    ]

    for raw_err in raw_sensitive_cases:
        service = NarrativeService(provider="gemini", gemini_api_key="mock_key")
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = raw_err
        service._client = mock_client

        res = service.generate_narrative(sample_narrative_request)
        reason = res.fallback_reason

        assert "503" not in reason
        assert "UNAVAILABLE" not in reason
        assert "Traceback" not in reason
        assert "TEST_API_KEY_REDACTED" not in reason
        assert "{" not in reason
        assert "}" not in reason
        assert "CivicFork is using its deterministic evidence-based explanation engine" in reason


def test_explain_api_endpoint_prerequisites_and_validation():
    """Verify HTTP validation and prerequisite enforcement for POST /api/explain."""
    client = TestClient(app)

    # 1. Non-existent session
    res = client.post("/api/explain", json={"session_id": "00000000-0000-0000-0000-000000000000", "narrative_type": "full_report"})
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "SESSION_NOT_FOUND"

    # 2. Invalid narrative type
    res = client.post("/api/explain", json={"session_id": "00000000-0000-0000-0000-000000000000", "narrative_type": "invalid_type"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"

    # 3. Analyze plot first
    analyze_payload = {
        "lat": 12.3100,
        "lng": 76.6500,
        "radius_m": 2000,
        "area_sqm": 3500.0,
        "label": "API Test Parcel",
    }
    ana_res = client.post("/api/analyze", json=analyze_payload)
    session_id = ana_res.json()["data"]["session_id"]

    # 4. context_summary narrative is valid immediately after analyze
    ctx_res = client.post("/api/explain", json={"session_id": session_id, "narrative_type": "context_summary"})
    assert ctx_res.status_code == 200
    ctx_data = ctx_res.json()["data"]["narrative"]
    assert ctx_data["narrative_type"] == "context_summary"
    assert "overview" in ctx_data["sections"]
    assert "urban_context" in ctx_data["sections"]
    assert "infrastructure_gaps" in ctx_data["sections"]

    # 5. Calling score_explanation before simulate should fail with MISSING_PREREQUISITE
    score_res = client.post("/api/explain", json={"session_id": session_id, "narrative_type": "score_explanation"})
    assert score_res.status_code == 400
    assert score_res.json()["error"]["code"] == "MISSING_PREREQUISITE"


def test_explain_api_endpoint_end_to_end_workflow():
    """Verify end-to-end full_report explanation synthesis across the complete workflow."""
    client = TestClient(app)

    # 1. Analyze
    analyze_payload = {
        "lat": 12.3100,
        "lng": 76.6500,
        "radius_m": 2000,
        "area_sqm": 3500.0,
        "label": "Full Workflow Parcel",
    }
    ana_res = client.post("/api/analyze", json=analyze_payload)
    session_id = ana_res.json()["data"]["session_id"]

    # 2. Simulate
    client.post("/api/simulate", json={"session_id": session_id})

    # 3. Rank
    client.post("/api/rank", json={"session_id": session_id, "weights": {"traffic": 1.0, "cost": 1.0, "environmental": 1.0, "accessibility": 1.0, "gap_improvement": 2.0, "social_utility": 2.0}})

    # 4. Feasibility
    client.post("/api/feasibility", json={"session_id": session_id})

    # 5. Counterfactual
    client.post("/api/counterfactual", json={"session_id": session_id, "scenario_a_id": "park", "scenario_b_id": "healthcare"})

    # 6. Explain full_report
    exp_res = client.post("/api/explain", json={"session_id": session_id, "narrative_type": "full_report"})
    assert exp_res.status_code == 200
    data = exp_res.json()
    assert data["success"] is True
    assert data["error"] is None

    narrative = data["data"]["narrative"]
    assert narrative["narrative_type"] == "full_report"
    assert narrative["generated_by"] in ("gemini", "groq", "fallback", "deterministic")

    sections = narrative["sections"]
    assert "decision_rationale" in sections
    assert "overview" in sections
    assert "urban_context" in sections
    assert "infrastructure_gaps" in sections
    assert "recommended_scenario" in sections
    assert "trade_offs" in sections
    assert "feasibility" in sections


def test_phase41_successful_ai_explanation(sample_narrative_request):
    """Verify that successful AI generation parses Decision Rationale covering all 7 municipal points."""
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "decision_rationale": {
                            "headline": "Decision Rationale: Parks / Recreational Space Recommended as Rank #1 Allocation",
                            "rationale": "Under the active municipal weighting scheme, Parks / Recreational Space achieved Rank #1 with a composite score of 89.0/100, addressing green space deficits in Agrahara Ward.",
                            "strengths": [
                                "Environmental: +10.0 pts contribution",
                                "Directly alleviates open-space deficits documented in OSM data"
                            ],
                            "trade_offs": [
                                "Cost: Lower economic tax generation compared to commercial alternatives"
                            ],
                            "recommendation_context": "Planning status: FEASIBLE with 0 blockers. Outperforms Healthcare Facility by +4.8 pts margin."
                        },
                        "overview": "Overview text.",
                        "urban_context": "Context text.",
                        "infrastructure_gaps": "Gaps text.",
                        "recommended_scenario": "Recommended scenario text.",
                        "trade_offs": "Trade-offs text.",
                        "feasibility": "Feasibility text."
                    })
                }
            }
        ]
    }
    mock_http.post.return_value = mock_resp

    service = NarrativeService(
        provider="groq",
        groq_api_key="gsk_mock_test_key",
        http_client=mock_http,
    )
    res = service.generate_narrative(sample_narrative_request)

    assert res.generated_by == "groq"
    assert res.fallback_reason is None
    assert "decision_rationale" in res.sections
    assert res.decision_rationale is not None

    dr = res.decision_rationale
    assert "Parks" in dr.headline
    assert "89.0" in dr.rationale
    assert len(dr.strengths) >= 2
    assert len(dr.trade_offs) >= 1
    assert "FEASIBLE" in dr.recommendation_context


def test_phase41_deterministic_fallback_decision_rationale(sample_narrative_request):
    """Verify deterministic fallback produces a context-aware decision explanation without network calls."""
    service = NarrativeService(provider="deterministic")
    res = service.generate_narrative(sample_narrative_request)

    assert res.generated_by == "deterministic"
    assert "decision_rationale" in res.sections
    assert res.decision_rationale is not None

    dr = res.decision_rationale
    assert len(dr.headline) > 10
    assert "Rank #1" in dr.headline
    assert len(dr.rationale) > 50
    assert len(dr.strengths) >= 1
    assert len(dr.trade_offs) >= 1
    assert "FEASIBLE" in dr.recommendation_context

    # Verify authoritative values are accurately cited in deterministic text
    top_sc = sample_narrative_request.ranking[0]
    assert f"{top_sc.weighted_score:.1f}" in dr.rationale
    assert "decision_rationale" in res.sections
    assert dr.headline in res.sections["decision_rationale"]


def test_phase41_missing_optional_comparison_data(sample_narrative_request):
    """Verify that decision rationale handles missing optional comparison data gracefully."""
    # Create request with only 1 scenario in ranking (no runner-up) and no counterfactual
    top_scenario = sample_narrative_request.ranking[0]
    single_ranking_request = NarrativeRequest(
        narrative_type="full_report",
        plot=sample_narrative_request.plot,
        context_summary=sample_narrative_request.context_summary,
        gaps=[],
        scenarios=sample_narrative_request.scenarios[:1],
        score_matrix=sample_narrative_request.score_matrix,
        ranking=[top_scenario],
        feasibility=sample_narrative_request.feasibility[:1],
        counterfactual=None,  # No counterfactual
    )

    service = NarrativeService(provider="deterministic")
    res = service.generate_narrative(single_ranking_request)

    assert res.generated_by == "deterministic"
    assert "decision_rationale" in res.sections
    dr = res.decision_rationale
    assert dr is not None
    # Graceful fallback phrasing when runner-up is absent
    assert "single evaluated candidate" in dr.rationale or "threshold" in dr.recommendation_context
    assert len(dr.strengths) >= 1
    assert len(dr.trade_offs) >= 1


def test_phase41_no_numerical_mutation(sample_narrative_request):
    """Verify strict Python calculations boundary: narrative synthesis NEVER mutates numerical data."""
    # Capture snapshot of numerical engine outputs before narrative synthesis
    orig_ranking_scores = [r.weighted_score for r in sample_narrative_request.ranking]
    orig_ranking_order = [r.scenario_id for r in sample_narrative_request.ranking]
    orig_contributions = [dict(r.dimension_contributions) for r in sample_narrative_request.ranking]
    orig_matrix_scores = [
        [ds.score for ds in sc.scores]
        for sc in sample_narrative_request.score_matrix.scenario_scores
    ]
    orig_cf_delta = sample_narrative_request.counterfactual.net_delta
    orig_feas_verdicts = [f.feasible for f in sample_narrative_request.feasibility]

    service = NarrativeService(provider="deterministic")
    res = service.generate_narrative(sample_narrative_request)

    # Post-synthesis verification: zero modification
    assert [r.weighted_score for r in sample_narrative_request.ranking] == orig_ranking_scores
    assert [r.scenario_id for r in sample_narrative_request.ranking] == orig_ranking_order
    assert [dict(r.dimension_contributions) for r in sample_narrative_request.ranking] == orig_contributions
    assert [
        [ds.score for ds in sc.scores]
        for sc in sample_narrative_request.score_matrix.scenario_scores
    ] == orig_matrix_scores
    assert sample_narrative_request.counterfactual.net_delta == orig_cf_delta
    assert [f.feasible for f in sample_narrative_request.feasibility] == orig_feas_verdicts


def test_phase41_no_fabricated_values(sample_narrative_request):
    """Verify narrative cites precomputed figures exactly and does not fabricate numbers."""
    service = NarrativeService(provider="deterministic")
    res = service.generate_narrative(sample_narrative_request)

    top_scenario = sample_narrative_request.ranking[0]
    expected_score_str = f"{top_scenario.weighted_score:.1f}"
    expected_poi_str = str(sample_narrative_request.context_summary.total_pois)
    expected_lat_str = f"{sample_narrative_request.plot.lat:.4f}"

    # Verify calculated figures appear verbatim in the explanation
    rationale_text = res.decision_rationale.rationale
    assert expected_score_str in rationale_text
    assert expected_poi_str in rationale_text
    assert expected_lat_str in res.sections["overview"]

    # Verify no fabricated rankings
    assert "Rank #1" in res.decision_rationale.headline
