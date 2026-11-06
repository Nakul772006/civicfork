"""AI-powered Narrative Synthesis Service for CivicFork.

Architectural Rule:
    "Python calculates. AI explains."

The Narrative layer receives only a compact structured summary of already-computed CivicFork results.
It must never calculate, modify, rank, normalize, reinterpret, or override CivicFork's numerical results.
Supports multiple providers:
    - groq: Fast Llama-3.3 inference via OpenAI-compatible endpoint
    - gemini: Google Gemini multi-model generation with automatic failover
    - auto: Resilient provider hierarchy (Groq -> Gemini -> Deterministic fallback)
    - deterministic: Pure offline evidence-based template generation (zero network calls)
If all external providers are unavailable or fail, the service returns a graceful deterministic fallback explanation.
"""

import json
import logging
import time
from typing import Any, Dict, List, Literal, Optional, Tuple
import httpx

from app.models.domain import (
    DecisionRationale,
    NarrativeRequest,
    NarrativeResponse,
    NarrativeType,
)
from app.settings import settings

logger = logging.getLogger("civicfork.narrative")

SUPPORTED_PROVIDERS = {"groq", "gemini", "auto", "deterministic"}
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"

CLEAN_FALLBACK_STATUS = (
    "AI narrative temporarily unavailable. CivicFork is using its deterministic evidence-based "
    "explanation engine. All numerical scores, rankings, feasibility results and recommendations remain operational."
)

CLEAN_DETERMINISTIC_STATUS = (
    "CivicFork is operating in deterministic mode. Explanations are generated directly from "
    "evidence-based municipal calculation templates."
)

CLEAN_NO_KEY_STATUS = (
    "AI narrative provider key not configured. CivicFork is using its deterministic "
    "evidence-based explanation engine. All numerical scores, rankings, feasibility results and recommendations remain operational."
)

EXPECTED_SECTIONS_BY_TYPE: Dict[str, List[str]] = {
    "context_summary": ["overview", "urban_context", "infrastructure_gaps"],
    "score_explanation": [
        "decision_rationale",
        "overview",
        "recommended_scenario",
        "trade_offs",
        "feasibility",
    ],
    "counterfactual_explanation": [
        "overview",
        "comparison_analysis",
        "trade_offs",
        "recommendation_context",
    ],
    "full_report": [
        "decision_rationale",
        "overview",
        "urban_context",
        "infrastructure_gaps",
        "recommended_scenario",
        "trade_offs",
        "feasibility",
    ],
}


class NarrativeService:
    """Service synthesizing human-readable policy explanations via Groq, Gemini, or deterministic fallback."""

    def __init__(
        self,
        provider: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        groq_model: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        gemini_model: Optional[str] = None,
        http_client: Optional[httpx.Client] = None,
        # Backward compatibility for existing callers and tests
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        raw_provider = provider if provider is not None else settings.ai_provider
        self._provider = raw_provider.strip().lower() if raw_provider else "auto"
        if self._provider not in SUPPORTED_PROVIDERS:
            logger.warning(
                "Unrecognized AI_PROVIDER '%s'. Defaulting to 'auto'. Supported: %s",
                self._provider,
                SUPPORTED_PROVIDERS,
            )
            self._provider = "auto"

        # Groq credentials & client
        self._groq_api_key = groq_api_key if groq_api_key is not None else settings.groq_api_key
        self._groq_model = groq_model or settings.groq_model or DEFAULT_GROQ_MODEL
        self._http_client = http_client or httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0))

        # Gemini credentials & client (supports legacy api_key/model_name args)
        self._gemini_api_key = (
            api_key if api_key is not None else (gemini_api_key if gemini_api_key is not None else settings.gemini_api_key)
        )
        self._gemini_model = model_name or gemini_model or settings.gemini_model or DEFAULT_GEMINI_MODEL
        self._gemini_client = None

        if self._gemini_api_key:
            try:
                from google import genai
                from google.genai import types
                self._gemini_client = genai.Client(
                    api_key=self._gemini_api_key,
                    http_options=types.HttpOptions(timeout=10000),
                )
                logger.info("Gemini client initialized with model '%s'", self._gemini_model)
            except Exception as exc:
                logger.warning("Could not initialize Gemini client: %s", exc)
                self._gemini_client = None
        else:
            logger.debug("No Gemini API key configured.")

    @property
    def provider(self) -> str:
        """Active narrative provider setting."""
        return self._provider

    @property
    def _client(self):
        """Backward compatibility property for Gemini client."""
        return self._gemini_client

    @_client.setter
    def _client(self, value):
        self._gemini_client = value

    @property
    def _api_key(self) -> str:
        """Backward compatibility property for Gemini API key."""
        return self._gemini_api_key

    @property
    def _model_name(self) -> str:
        """Backward compatibility property for Gemini model."""
        return self._gemini_model

    @property
    def is_ai_available(self) -> bool:
        """Check whether live AI synthesis is available under the active provider configuration."""
        if self._provider == "deterministic":
            return False
        if self._provider == "groq":
            return bool(self._groq_api_key)
        if self._provider == "gemini":
            return self._gemini_client is not None
        # auto mode
        return bool(self._groq_api_key) or (self._gemini_client is not None)

    def build_compact_summary(self, request: NarrativeRequest) -> Dict[str, Any]:
        """Construct the strictly bounded compact summary of pre-computed results.

        Boundary Guarantee:
        - NEVER contains raw OSM POI lists, road geometries, or GeoJSON features.
        - NEVER contains credentials, secrets, or internal engine state.
        - Contains only pre-computed aggregates, scores, rankings, and deltas.
        """
        plot = request.plot
        ctx = request.context_summary

        plot_data = {
            "label": plot.label or "Selected Mysuru Parcel",
            "lat": plot.lat,
            "lng": plot.lng,
            "radius_m": plot.radius_m,
            "area_sqm": plot.area_sqm,
        }

        context_data = {
            "observed_poi_count": ctx.total_pois,
            "road_network_length_m": round(ctx.road_network_length_m, 1),
            "dominant_landuse": ctx.dominant_landuse,
            "landuse_distribution_pct": {
                "residential": round(ctx.residential_pct, 1),
                "commercial": round(ctx.commercial_pct, 1),
                "green_space": round(ctx.green_space_pct, 1),
                "industrial": round(ctx.industrial_pct, 1),
            },
            "transit_stops_in_radius": ctx.transit_stop_count,
            "nearest_transit_stop_m": round(ctx.nearest_transit_m, 1) if ctx.nearest_transit_m is not None else None,
            "modeled_population_density_per_sqkm": round(ctx.population_density_estimate, 1),
            "modeled_building_coverage_ratio": round(ctx.building_density_estimate, 3),
        }

        if getattr(ctx, "ward", None):
            ward = ctx.ward
            context_data["ward"] = {
                "ward_id": ward.ward_id,
                "ward_name": ward.ward_name,
                "population_2011": ward.population,
            }

        if getattr(ctx, "nearest_water_body_name", None):
            context_data["water_body_proximity"] = {
                "nearest_water_body_name": ctx.nearest_water_body_name,
                "distance_m": round(ctx.nearest_water_body_m, 1) if getattr(ctx, "nearest_water_body_m", None) is not None else None,
            }

        gaps_data = [
            {
                "category": g.category,
                "gap_type": g.gap_type,
                "gap_severity_0_to_1": round(g.gap_severity, 2),
                "facilities_observed": g.facilities_in_radius,
                "facilities_expected": g.expected_facilities,
                "nearest_facility_distance_m": round(g.nearest_facility_distance_m, 1) if g.nearest_facility_distance_m else None,
                "coverage_threshold_m": g.coverage_threshold_m,
                "description": g.description,
            }
            for g in request.gaps
        ]

        scenarios_data = [
            {
                "id": s.id,
                "name": s.name,
                "estimated_cost_inr": s.estimated_cost_inr,
                "proposed_area_sqm": s.proposed_area_sqm,
                "description": s.description,
            }
            for s in request.scenarios
        ]

        summary: Dict[str, Any] = {
            "narrative_type": request.narrative_type,
            "plot": plot_data,
            "urban_context": context_data,
            "infrastructure_gaps": gaps_data,
            "scenarios": scenarios_data,
        }

        if request.score_matrix:
            sm = request.score_matrix
            scores_data = {}
            scenario_scores = getattr(sm, "scenario_scores", None) or (sm.get("scenario_scores") if isinstance(sm, dict) else [])
            for sc in scenario_scores:
                sc_id = getattr(sc, "scenario_id", None) or (sc.get("scenario_id") if isinstance(sc, dict) else None)
                dim_list = getattr(sc, "scores", None) or (sc.get("scores") if isinstance(sc, dict) else [])
                sc_dict = {}
                for ds in dim_list:
                    dim_name = getattr(ds, "dimension", None) or (ds.get("dimension") if isinstance(ds, dict) else None)
                    dim_score = getattr(ds, "score", None) or (ds.get("score") if isinstance(ds, dict) else 0.0)
                    if dim_score is None:
                        dim_score = 0.0
                    if dim_name:
                        sc_dict[dim_name] = round(dim_score, 1)
                if sc_id:
                    scores_data[sc_id] = sc_dict
            summary["scores_matrix"] = scores_data

        if request.ranking:
            summary["ranking"] = [
                {
                    "rank": r.rank,
                    "scenario_id": r.scenario_id,
                    "weighted_score": round(r.weighted_score, 1),
                    "score_delta_from_top": round(r.score_delta_from_top, 1),
                    "dimension_contributions": {
                        k: round(v, 2) for k, v in r.dimension_contributions.items()
                    },
                }
                for r in request.ranking
            ]

        if request.feasibility:
            summary["feasibility"] = [
                {
                    "scenario_id": f.scenario_id,
                    "feasible": f.feasible,
                    "blocker_count": f.blocker_count,
                    "warning_count": f.warning_count,
                    "blockers": f.blockers,
                    "warnings": f.warnings,
                }
                for f in request.feasibility
            ]

        if request.counterfactual:
            cf = request.counterfactual
            summary["counterfactual"] = {
                "scenario_a_id": cf.scenario_a_id,
                "scenario_a_name": cf.scenario_a_name,
                "scenario_b_id": cf.scenario_b_id,
                "scenario_b_name": cf.scenario_b_name,
                "net_advantage": cf.net_advantage,
                "net_delta": round(cf.net_delta, 1),
                "verdict": cf.verdict,
                "headline": cf.headline,
                "dimension_deltas": [
                    {
                        "dimension": d.dimension,
                        "score_a": round(d.score_a, 1),
                        "score_b": round(d.score_b, 1),
                        "delta": round(d.delta, 1),
                        "direction": d.direction,
                        "magnitude": d.magnitude,
                    }
                    for d in cf.deltas
                ],
            }

        # Structured Municipal Decision Highlights (pre-calculated context for narrative synthesis)
        if request.ranking and len(request.ranking) > 0:
            top_rank = request.ranking[0]
            top_id = top_rank.scenario_id
            top_scenario_obj = next((s for s in request.scenarios if s.id == top_id), None)
            runner_up_rank = request.ranking[1] if len(request.ranking) > 1 else None
            runner_up_obj = (
                next((s for s in request.scenarios if s.id == runner_up_rank.scenario_id), None)
                if runner_up_rank
                else None
            )

            # Strongest and weakest dimension contributions for top scenario
            contribs = top_rank.dimension_contributions or {}
            sorted_contribs = sorted(contribs.items(), key=lambda x: x[1], reverse=True)
            strongest_dims = [
                {"dimension": k, "contribution_pts": round(v, 2)}
                for k, v in sorted_contribs[:2]
            ]
            weakest_dims = [
                {"dimension": k, "contribution_pts": round(v, 2)}
                for k, v in sorted_contribs[-2:]
            ]

            # Infrastructure gaps addressed by this scenario
            scenario_gap_map = {
                "park": ["green_space"],
                "healthcare": ["healthcare"],
                "education": ["education"],
                "transit_hub": ["transit"],
                "affordable_housing": ["residential", "housing"],
                "mixed_use": ["commercial", "residential"],
                "commercial": ["commercial"],
            }
            target_gaps = scenario_gap_map.get(top_id, [])
            addressed_gaps = [
                {
                    "category": g.category,
                    "gap_type": g.gap_type,
                    "severity": round(g.gap_severity, 2),
                    "description": g.description,
                }
                for g in request.gaps
                if g.category in target_gaps or any(tg in g.description.lower() for tg in target_gaps)
            ]

            # Feasibility for top scenario
            top_feas = (
                next((f for f in (request.feasibility or []) if f.scenario_id == top_id), None)
            )

            summary["decision_context"] = {
                "top_scenario": {
                    "id": top_id,
                    "name": top_scenario_obj.name if top_scenario_obj else top_id,
                    "rank": 1,
                    "weighted_score": round(top_rank.weighted_score, 1),
                    "estimated_cost_inr": top_scenario_obj.estimated_cost_inr if top_scenario_obj else None,
                    "strongest_dimensions": strongest_dims,
                    "weakest_trade_off_dimensions": weakest_dims,
                    "addressed_infrastructure_gaps": addressed_gaps,
                    "feasibility": {
                        "feasible": top_feas.feasible if top_feas else True,
                        "blocker_count": top_feas.blocker_count if top_feas else 0,
                        "warning_count": top_feas.warning_count if top_feas else 0,
                        "blockers": top_feas.blockers if top_feas else [],
                        "warnings": top_feas.warnings if top_feas else [],
                    } if top_feas else None,
                },
                "comparison_against_runner_up": {
                    "has_runner_up": runner_up_rank is not None,
                    "runner_up_id": runner_up_rank.scenario_id if runner_up_rank else None,
                    "runner_up_name": runner_up_obj.name if runner_up_obj else (runner_up_rank.scenario_id if runner_up_rank else None),
                    "runner_up_score": round(runner_up_rank.weighted_score, 1) if runner_up_rank else None,
                    "score_margin_pts": round(runner_up_rank.score_delta_from_top, 1) if runner_up_rank else None,
                } if runner_up_rank else {"has_runner_up": False},
            }

        summary["data_provenance_definitions"] = {
            "observed": "OpenStreetMap documented features (POIs, road network length, transit stops). Open catalog entries, not complete field surveys.",
            "calculated": "Deterministic 0-100 scores, priority-weighted ranking, and dimension contributions produced by mathematical engines.",
            "modelled": "Algorithmic heuristic baselines (estimated population density, building coverage ratio). Not official census figures.",
            "configured": "Planner-selected simulation inputs (priority weights, spatial analysis radius buffer). Contextual land use is not legal zoning.",
            "derived": "Pairwise counterfactual delta comparisons and regulatory feasibility constraint checks.",
        }

        return summary

    def _generate_with_groq(
        self,
        compact_summary: Dict[str, Any],
        expected_sections: List[str],
        request: NarrativeRequest,
    ) -> NarrativeResponse:
        """Generate structured narrative using Groq OpenAI-compatible API."""
        if not self._groq_api_key:
            raise ValueError("Groq API key is not configured")

        logger.info("Groq narrative request started (model=%s)", self._groq_model)
        prompt = self._construct_prompt(compact_summary, expected_sections)
        headers = {
            "Authorization": f"Bearer {self._groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._groq_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert urban planning and municipal policy analyst. "
                        "You explain pre-calculated decision metrics without modifying or recalculating them. "
                        "Return only valid JSON matching the requested section keys."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        resp = self._http_client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        # One-shot retry on transient 429/503 with short backoff
        if resp.status_code in (429, 503):
            retry_after = min(float(resp.headers.get("retry-after", "3")), 10.0)
            logger.warning("Groq returned HTTP %s; retrying after %.1fs", resp.status_code, retry_after)
            time.sleep(retry_after)
            resp = self._http_client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
            )
        resp.raise_for_status()
        logger.info("Groq narrative request succeeded (HTTP %s)", resp.status_code)
        data = resp.json()
        raw_text = data["choices"][0]["message"]["content"]
        sections, decision_rationale = self._parse_and_validate_sections(
            raw_text, expected_sections, request, compact_summary
        )

        return NarrativeResponse(
            narrative_type=request.narrative_type,
            sections=sections,
            decision_rationale=decision_rationale,
            generated_by="groq",
            fallback_reason=None,
        )

    def _generate_with_gemini(
        self,
        compact_summary: Dict[str, Any],
        expected_sections: List[str],
        request: NarrativeRequest,
    ) -> NarrativeResponse:
        """Generate structured narrative using Google Gemini client with failover."""
        if not self._gemini_client:
            raise ValueError("Gemini client is not initialized")

        from google.genai import types

        prompt = self._construct_prompt(compact_summary, expected_sections)
        models_to_try = [self._gemini_model]
        if "lite" not in self._gemini_model:
            models_to_try.append("gemini-3.5-flash-lite")
        else:
            models_to_try.append("gemini-3.5-flash")

        last_exc: Optional[Exception] = None
        response = None
        for model_id in models_to_try:
            try:
                response = self._gemini_client.models.generate_content(
                    model=model_id,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                    ),
                )
                if response and response.text:
                    break
            except Exception as exc:
                last_exc = exc
                logger.warning("Gemini generation on model '%s' failed: %s", model_id, exc)

        if response is None or not response.text:
            raise last_exc or RuntimeError("Empty response received from Gemini API")

        sections, decision_rationale = self._parse_and_validate_sections(
            response.text, expected_sections, request, compact_summary
        )

        return NarrativeResponse(
            narrative_type=request.narrative_type,
            sections=sections,
            decision_rationale=decision_rationale,
            generated_by="gemini",
            fallback_reason=None,
        )

    def _build_decision_rationale_object(
        self,
        parsed_data: Dict[str, Any],
        sections_dict: Dict[str, str],
        summary: Dict[str, Any],
    ) -> Optional[DecisionRationale]:
        """Construct structured DecisionRationale from parsed JSON or formatted markdown."""
        decision_context = summary.get("decision_context", {})
        top_sc = decision_context.get("top_scenario", {})
        ranking = summary.get("ranking", [])
        if not top_sc and not ranking:
            return None

        top_id = top_sc.get("id") or (ranking[0].get("scenario_id") if ranking else "Recommended Option")
        top_name = top_sc.get("name") or top_id
        score = top_sc.get("weighted_score") if top_sc else (ranking[0].get("weighted_score") if ranking else 0.0)

        # 1. If parsed_data had a structured dict for decision_rationale
        val = parsed_data.get("decision_rationale")
        if isinstance(val, dict):
            headline = val.get("headline") or f"Decision Rationale: {top_name} Recommended as Rank #1 Allocation"
            rationale = val.get("rationale") or f"Under current municipal priorities, {top_name} achieved Rank #1 with a composite score of {score:.1f}/100."
            strengths = val.get("strengths") or [
                f"{d['dimension'].replace('_', ' ').title()}: +{d['contribution_pts']:.1f} pts contribution"
                for d in top_sc.get("strongest_dimensions", [])
            ]
            trade_offs = val.get("trade_offs") or [
                f"{d['dimension'].replace('_', ' ').title()}: +{d['contribution_pts']:.1f} pts contribution"
                for d in top_sc.get("weakest_trade_off_dimensions", [])
            ]
            context = val.get("recommendation_context") or ""
            return DecisionRationale(
                headline=headline,
                rationale=rationale,
                strengths=strengths,
                trade_offs=trade_offs,
                recommendation_context=context,
            )

        # 2. Extract from markdown string if present
        raw_md = sections_dict.get("decision_rationale", "")
        headline = f"Decision Rationale: {top_name} Recommended as Rank #1 Allocation"
        rationale_parts = []
        strengths = []
        trade_offs = []
        context_parts = []

        if raw_md:
            lines = raw_md.split("\n")
            current_section = "rationale"
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("#"):
                    headline = stripped.lstrip("#").strip()
                    continue
                lower = stripped.lower()
                if "strength" in lower or "gaps alleviated" in lower or "impact dimension" in lower:
                    current_section = "strengths"
                    continue
                elif "trade-off" in lower or "weaker" in lower or "weakness" in lower:
                    current_section = "trade_offs"
                    continue
                elif "context" in lower or "feasibility" in lower or "planning sanction" in lower:
                    current_section = "context"
                    continue

                if current_section == "rationale":
                    if not stripped.startswith("-") and not stripped.startswith("*"):
                        rationale_parts.append(stripped)
                elif current_section == "strengths":
                    item = stripped.lstrip("-*• ").strip()
                    if item:
                        strengths.append(item)
                elif current_section == "trade_offs":
                    item = stripped.lstrip("-*• ").strip()
                    if item:
                        trade_offs.append(item)
                elif current_section == "context":
                    context_parts.append(stripped.lstrip("-*• ").strip())

        rationale = " ".join(rationale_parts).strip()
        context = " ".join(context_parts).strip()

        # Fill any missing parts from precalculated decision context
        if not rationale:
            rationale = f"Under active municipal weighting, {top_name} ranks #1 with a weighted score of {score:.1f}/100."
        if not strengths and top_sc.get("strongest_dimensions"):
            strengths = [
                f"{d['dimension'].replace('_', ' ').title()}: +{d['contribution_pts']:.1f} pts contribution"
                for d in top_sc.get("strongest_dimensions", [])
            ]
            if top_sc.get("addressed_infrastructure_gaps"):
                strengths.append(f"Directly addresses: {', '.join(g['category'].title() for g in top_sc['addressed_infrastructure_gaps'])}")
        if not trade_offs and top_sc.get("weakest_trade_off_dimensions"):
            trade_offs = [
                f"{d['dimension'].replace('_', ' ').title()}: +{d['contribution_pts']:.1f} pts contribution"
                for d in top_sc.get("weakest_trade_off_dimensions", [])
            ]
        if not context:
            runner_up_info = decision_context.get("comparison_against_runner_up", {})
            if runner_up_info.get("has_runner_up"):
                context = f"Outperforms {runner_up_info.get('runner_up_name')} by +{runner_up_info.get('score_margin_pts', 0.0):.1f} pts margin."
            else:
                context = "Evaluated against municipal feasibility thresholds."

        return DecisionRationale(
            headline=headline,
            rationale=rationale,
            strengths=strengths,
            trade_offs=trade_offs,
            recommendation_context=context,
        )

    def _parse_and_validate_sections(
        self,
        raw_text: str,
        expected_sections: List[str],
        request: NarrativeRequest,
        summary: Dict[str, Any],
    ) -> Tuple[Dict[str, str], Optional[DecisionRationale]]:
        """Clean markdown formatting, parse JSON, and ensure all expected sections are populated."""
        cleaned_text = (raw_text or "").strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]
        cleaned_text = cleaned_text.strip()

        try:
            parsed_data = json.loads(cleaned_text)
        except json.JSONDecodeError as exc:
            logger.warning("Narrative JSON parse failed (%s): returning deterministic fallback for sections.", exc)
            fallback_res = self._generate_fallback(request, summary, expected_sections)
            return fallback_res.sections, fallback_res.decision_rationale

        result_sections: Dict[str, str] = {}
        fallback_res = None
        for sec in expected_sections:
            val = parsed_data.get(sec)
            if isinstance(val, dict) and sec == "decision_rationale":
                headline = val.get("headline", "")
                rationale = val.get("rationale", "")
                strengths = val.get("strengths", [])
                trade_offs = val.get("trade_offs", [])
                context = val.get("recommendation_context", "")
                md_parts = []
                if headline:
                    md_parts.append(f"### {headline}")
                if rationale:
                    md_parts.append(rationale)
                if strengths:
                    md_parts.append("**Strongest Impact Dimensions & Gaps Alleviated:**\n" + "\n".join(f"- {s}" for s in strengths))
                if trade_offs:
                    md_parts.append("**Trade-offs & Weaker Dimensions:**\n" + "\n".join(f"- {t}" for t in trade_offs))
                if context:
                    md_parts.append(f"**Recommendation Context & Feasibility:**\n- {context}")
                result_sections[sec] = "\n\n".join(md_parts)
            elif isinstance(val, str) and val.strip():
                result_sections[sec] = val.strip()
            else:
                if fallback_res is None:
                    fallback_res = self._generate_fallback(request, summary, expected_sections)
                result_sections[sec] = fallback_res.sections.get(sec, "")

        decision_rationale = None
        if "decision_rationale" in expected_sections:
            decision_rationale = self._build_decision_rationale_object(parsed_data, result_sections, summary)

        return result_sections, decision_rationale

    def generate_narrative(self, request: NarrativeRequest) -> NarrativeResponse:
        """Generate structured narrative according to active provider strategy with graceful fallback."""
        expected_sections = EXPECTED_SECTIONS_BY_TYPE.get(
            request.narrative_type, EXPECTED_SECTIONS_BY_TYPE["full_report"]
        )
        compact_summary = self.build_compact_summary(request)
        logger.info("NarrativeService provider='%s' groq_key_set=%s gemini_client_set=%s",
                    self._provider, bool(self._groq_api_key), self._gemini_client is not None)

        # 1. Deterministic mode: strictly local, no external calls
        if self._provider == "deterministic":
            return self._generate_fallback(
                request=request,
                summary=compact_summary,
                sections=expected_sections,
                reason=CLEAN_DETERMINISTIC_STATUS,
                generated_by="deterministic",
            )

        # 2. Explicit Groq mode
        if self._provider == "groq":
            if not self._groq_api_key:
                return self._generate_fallback(
                    request=request,
                    summary=compact_summary,
                    sections=expected_sections,
                    reason=CLEAN_NO_KEY_STATUS,
                    generated_by="fallback",
                )
            try:
                return self._generate_with_groq(compact_summary, expected_sections, request)
            except Exception as exc:
                logger.warning("Groq narrative generation failed: %s (%s). Falling back.", type(exc).__name__, exc)
                return self._generate_fallback(
                    request=request,
                    summary=compact_summary,
                    sections=expected_sections,
                    reason=CLEAN_FALLBACK_STATUS,
                    generated_by="fallback",
                )

        # 3. Explicit Gemini mode
        if self._provider == "gemini":
            if not self._gemini_client:
                return self._generate_fallback(
                    request=request,
                    summary=compact_summary,
                    sections=expected_sections,
                    reason=CLEAN_NO_KEY_STATUS,
                    generated_by="fallback",
                )
            try:
                return self._generate_with_gemini(compact_summary, expected_sections, request)
            except Exception as exc:
                logger.warning("Gemini narrative generation failed: %s (%s). Falling back.", type(exc).__name__, exc)
                return self._generate_fallback(
                    request=request,
                    summary=compact_summary,
                    sections=expected_sections,
                    reason=CLEAN_FALLBACK_STATUS,
                    generated_by="fallback",
                )

        # 4. Auto mode: Groq -> Gemini -> Fallback
        # 4a. Attempt Groq first if key present
        if self._groq_api_key:
            try:
                return self._generate_with_groq(compact_summary, expected_sections, request)
            except Exception as exc:
                logger.warning(
                    "Auto provider Groq attempt failed: %s (%s). Attempting Gemini fallback.",
                    type(exc).__name__,
                    exc,
                )

        # 4b. Attempt Gemini if client initialized
        if self._gemini_client:
            try:
                return self._generate_with_gemini(compact_summary, expected_sections, request)
            except Exception as exc:
                logger.warning(
                    "Auto provider Gemini attempt failed: %s (%s). Falling back to deterministic engine.",
                    type(exc).__name__,
                    exc,
                )

        # 4c. All providers unavailable / unconfigured
        has_any_key = bool(self._groq_api_key or self._gemini_api_key)
        reason = CLEAN_FALLBACK_STATUS if has_any_key else CLEAN_NO_KEY_STATUS
        return self._generate_fallback(
            request=request,
            summary=compact_summary,
            sections=expected_sections,
            reason=reason,
            generated_by="fallback",
        )

    def _construct_prompt(self, summary: Dict[str, Any], sections: List[str]) -> str:
        """Construct the prompt enforcing strict numerical integrity, municipal policy tone, and cautious language."""
        json_data = json.dumps(summary, indent=2)
        required_keys = ", ".join(f'"{s}"' for s in sections)

        decision_rationale_guide = ""
        if "decision_rationale" in sections:
            decision_rationale_guide = """
MUNICIPAL DECISION RATIONALE SECTION REQUIREMENTS:
- Headline: Authoritative executive recommendation title naming the top-ranked scenario (e.g. '### Decision Rationale: <Scenario Name> Recommended as Rank #1 Allocation').
- Rationale: Context-aware paragraph explaining why this scenario ranks #1 given the active municipal weights, observed deficits, and urban context.
- Strongest Impact Dimensions & Gaps Alleviated: Bullet points identifying its 2 highest-contributing dimensions and specific gaps addressed.
- Trade-offs & Weaker Dimensions: Bullet points identifying its lowest-scoring dimensions or cost considerations that municipal decision-makers must evaluate.
- Recommendation Context & Feasibility: Planning feasibility status (noting non-blocking advisory warnings vs critical blockers) and comparison against the runner-up scenario (score margin).
"""

        return f"""You are an expert urban planning and municipal policy analyst generating an executive narrative explanation for a policy assessment in Mysuru, Karnataka, India.

CRITICAL ARCHITECTURAL CONSTRAINTS:
1. Python calculates. AI explains. All scores, rankings, dimensions, and feasibility checks have already been deterministically calculated by the CivicFork engine.
2. DO NOT invent, alter, recalculate, or re-rank any scores. You must cite the provided figures exactly.
3. STRICT DATA BOUNDARY & TERMINOLOGY DISTINCTIONS:
   - OBSERVED: Features documented in OpenStreetMap (POI count, mapped road network length, transit stops). Never claim open data proves absolute real-world absence; say 'open geospatial data indicates an absence or sparse coverage'.
   - CALCULATED: Deterministic scores (0-100), rankings, and dimension contributions calculated from the mathematical model.
   - MODELLED: Algorithmic heuristic estimates (population density, building coverage ratio). Never claim modelled population is a measured census count.
   - CONFIGURED: Municipal priority weights and spatial buffer radii set by planners. Never claim contextual landuse is legal master plan zoning.
   - DERIVED: Feasibility verdicts (blockers vs warnings) and counterfactual trade-off deltas.
4. MUNICIPAL POLICY TONE: Write as an authoritative decision-support system for the Mysuru City Corporation (MCC). Be concise, clear, and objective.
{decision_rationale_guide}
5. Return your response as a valid JSON object matching the requested schema with the specified section keys: [{required_keys}].

COMPUTED CIVICFORK RESULTS (INPUT DATA):
{json_data}

REQUIRED JSON OUTPUT FORMAT:
{{
  {', '.join(f'"{s}": "<comprehensive markdown narrative for {s}>"' for s in sections)}
}}
"""

    def _generate_fallback(
        self,
        request: NarrativeRequest,
        summary: Dict[str, Any],
        sections: List[str],
        reason: Optional[str] = None,
        generated_by: str = "fallback",
    ) -> NarrativeResponse:
        """Generate high-quality deterministic narrative text from computed results."""
        plot = summary.get("plot", {})
        ctx = summary.get("urban_context", {})
        gaps = summary.get("infrastructure_gaps", [])
        ranking = summary.get("ranking", [])
        feasibility = summary.get("feasibility", [])
        counterfactual = summary.get("counterfactual", {})

        top_scenario = ranking[0] if ranking else None
        top_name = (
            next((s["name"] for s in summary.get("scenarios", []) if s["id"] == top_scenario["scenario_id"]), top_scenario["scenario_id"])
            if top_scenario
            else "Recommended Option"
        )

        built_sections: Dict[str, str] = {}
        decision_rationale_obj: Optional[DecisionRationale] = None

        if "decision_rationale" in sections:
            if top_scenario:
                top_id = top_scenario.get("scenario_id")
                weighted_score = top_scenario.get("weighted_score", 0.0)
                contribs = top_scenario.get("dimension_contributions", {})
                sorted_contribs = sorted(contribs.items(), key=lambda x: x[1], reverse=True)
                strongest = sorted_contribs[:2] if sorted_contribs else []
                weakest = sorted_contribs[-2:] if len(sorted_contribs) >= 4 else []

                runner_up = ranking[1] if len(ranking) > 1 else None
                runner_up_name = (
                    next((s["name"] for s in summary.get("scenarios", []) if s["id"] == runner_up["scenario_id"]), runner_up["scenario_id"])
                    if runner_up
                    else None
                )
                margin_text = (
                    f"outperforming the runner-up **{runner_up_name}** (Rank #2, score {runner_up['weighted_score']:.1f}) by a margin of {runner_up['score_delta_from_top']:.1f} points"
                    if runner_up
                    else "as the single evaluated candidate in the current scenario run"
                )

                top_gaps = [
                    g for g in gaps
                    if top_id in g.get("category", "") or g.get("gap_severity_0_to_1", 0) >= 0.5
                ]
                gaps_text = (
                    f"It directly mitigates identified municipal deficits in **{', '.join(g['category'].title() for g in top_gaps[:2])}**"
                    if top_gaps
                    else "It aligns with baseline municipal infrastructure targets for the buffer area"
                )

                top_feas = next((f for f in feasibility if f.get("scenario_id") == top_id), None)
                feas_status = "FEASIBLE" if (top_feas and top_feas.get("feasible")) else "REVIEW REQUIRED"
                feas_notes = []
                if top_feas and top_feas.get("warnings"):
                    feas_notes.append(f"{len(top_feas['warnings'])} advisory notice(s)")
                if top_feas and top_feas.get("blockers"):
                    feas_notes.append(f"{len(top_feas['blockers'])} regulatory blocker(s)")
                feas_str = f"Status: `{feas_status}`" + (f" with {', '.join(feas_notes)}" if feas_notes else " (0 blockers, 0 warnings)")

                headline_text = f"Decision Rationale: {top_name} Recommended as Rank #1 Allocation"
                rationale_text = (
                    f"Under the active municipal weighting scheme, **{top_name}** achieved Rank #1 with a calculated composite score "
                    f"of **{weighted_score:.1f}/100**, {margin_text}. In the context of {plot.get('label', 'the parcel')} "
                    f"(observed {ctx.get('observed_poi_count', 0)} OSM POIs, {ctx.get('road_network_length_m', 0):,.0f} m mapped road network, "
                    f"predominantly `{ctx.get('dominant_landuse', 'residential')}` land use), {gaps_text}."
                )

                strength_list = [
                    f"{k.replace('_', ' ').title()}: Strong positive contribution (+{v:.1f} pts) aligning with prioritized community objectives."
                    for k, v in strongest
                ]
                if top_gaps:
                    strength_list.append(
                        f"Directly addresses {len(top_gaps)} identified infrastructure deficit(s): {', '.join(g['category'].title() for g in top_gaps[:2])}."
                    )

                tradeoff_list = [
                    f"{k.replace('_', ' ').title()}: Lower relative score contribution (+{v:.1f} pts); represents an operational trade-off to consider during budget allocation."
                    for k, v in weakest
                ] if weakest else ["Balanced performance profile across remaining evaluated dimensions."]

                context_text = (
                    f"Planning Sanction: {feas_str}. "
                    + (f"Comparative evaluation confirms {top_name} outperforms {runner_up_name} by +{runner_up['score_delta_from_top']:.1f} pts composite utility." if runner_up else "Scenario assessed against municipal threshold standards.")
                )

                built_sections["decision_rationale"] = (
                    f"### {headline_text}\n\n"
                    f"{rationale_text}\n\n"
                    f"**Strongest Impact Dimensions & Gaps Alleviated:**\n"
                    + "\n".join(f"- **{s.split(':')[0]}:**{s.split(':', 1)[1] if ':' in s else s}" for s in strength_list)
                    + "\n\n**Trade-offs & Weaker Dimensions:**\n"
                    + "\n".join(f"- **{t.split(':')[0]}:**{t.split(':', 1)[1] if ':' in t else t}" for t in tradeoff_list)
                    + f"\n\n**Recommendation Context & Feasibility:**\n- {context_text}"
                )

                decision_rationale_obj = DecisionRationale(
                    headline=headline_text,
                    rationale=rationale_text,
                    strengths=strength_list,
                    trade_offs=tradeoff_list,
                    recommendation_context=context_text,
                )
            else:
                built_sections["decision_rationale"] = "### Decision Rationale\n\nScenario ranking has not yet been computed for this session."

        if "overview" in sections:
            built_sections["overview"] = (
                f"### Executive Assessment Overview\n\n"
                f"Evaluation of the selected parcel **{plot.get('label', 'Mysuru Parcel')}** "
                f"located at `({plot.get('lat', 12.31) or 12.31:.4f}, {plot.get('lng', 76.65) or 76.65:.4f})` with an area of "
                f"{plot.get('area_sqm') or 3500:,.0f} m² and a spatial analysis buffer of {plot.get('radius_m') or 2000:,} m. "
                f"The CivicFork engine simulated 7 canonical urban policy scenarios across 6 normalized impact dimensions. "
                + (f"Under current municipal priorities, **{top_name}** ranks #1 with a weighted score of **{top_scenario['weighted_score']:.1f}/100**." if top_scenario else "")
            )

        if "urban_context" in sections:
            dist = ctx.get("landuse_distribution_pct", {}) or {}
            built_sections["urban_context"] = (
                f"### Observed Urban Context & Density Estimates\n\n"
                f"- **Observed Geospatial Features:** OpenStreetMap data documents {ctx.get('observed_poi_count') or 0} points of interest, "
                f"{ctx.get('road_network_length_m') or 0:,.0f} m of mapped road network, and {ctx.get('transit_stops_in_radius') or 0} public transit stops "
                f"(nearest stop located {ctx.get('nearest_transit_stop_m') or 0:,.0f} m away).\n"
                f"- **Land-Use Composition:** Dominant land use is `{ctx.get('dominant_landuse') or 'residential'}` "
                f"(Residential: {dist.get('residential') or 0}%, Commercial: {dist.get('commercial') or 0}%, "
                f"Green Space: {dist.get('green_space') or 0}%, Industrial: {dist.get('industrial') or 0}%).\n"
                f"- **Modelled Baseline Estimates:** Contextual heuristics estimate a population density of "
                f"{ctx.get('modeled_population_density_per_sqkm') or 0:,.0f} people/km² and an average building coverage ratio of "
                f"{ctx.get('modeled_building_coverage_ratio') or 0:.2f}. *(Note: Modeled density figures represent algorithmic baseline estimations, while POIs and road geometries reflect documented open map data.)*"
            )

        if "infrastructure_gaps" in sections:
            critical_gaps = [g for g in gaps if g.get("gap_severity_0_to_1", 0) >= 0.7]
            gap_bullets = [
                f"- **{g.get('category', '').title()}** (Severity: `{g.get('gap_severity_0_to_1', 0):.2f}` — {g.get('gap_type', '').upper()}): "
                f"{g.get('description', '')}. Documented facilities in buffer: {g.get('facilities_observed', 0)} (expected: {g.get('facilities_expected', 0)})."
                for g in gaps
            ]
            built_sections["infrastructure_gaps"] = (
                f"### Infrastructure Gap Assessment\n\n"
                f"Algorithmic evaluation identified {len(critical_gaps)} critical gap(s) with severity $\\ge 0.70$:\n\n"
                + "\n".join(gap_bullets)
                + "\n\n*> [!NOTE] Cautious Geospatial Interpretation:* Lack of documented amenities in OpenStreetMap signifies "
                "potential infrastructure deficiencies in the available geospatial catalog; municipal field surveys are advised to verify on-ground service delivery."
            )

        if "recommended_scenario" in sections:
            if top_scenario:
                contribs = top_scenario.get("dimension_contributions", {})
                contrib_text = ", ".join(f"**{k.replace('_', ' ').title()}** (+{v:.1f} pts)" for k, v in contribs.items())
                built_sections["recommended_scenario"] = (
                    f"### Recommended Scenario: {top_name}\n\n"
                    f"Under the active municipal weighting scheme, **{top_name}** achieved Rank #1 with a weighted composite score of **{top_scenario['weighted_score']:.1f}/100**.\n\n"
                    f"- **Score Contribution Breakdown:** {contrib_text}.\n"
                    f"- **Score Margin:** It outperforms the lowest-ranked alternative by {ranking[-1]['score_delta_from_top']:.1f} points."
                )
            else:
                built_sections["recommended_scenario"] = "### Recommended Scenario\n\nScenario ranking has not yet been computed for this session."

        if "trade_offs" in sections:
            if counterfactual and counterfactual.get("scenario_a_id"):
                deltas = counterfactual.get("dimension_deltas", [])
                delta_bullets = [
                    f"- **{d['dimension'].replace('_', ' ').title()}:** {d['direction'].replace('_', ' ').title()} "
                    f"(Baseline: {d['score_a']:.1f} vs Alternative: {d['score_b']:.1f}, $\\Delta = {d['delta']:+.1f}$, {d['magnitude']} impact)."
                    for d in deltas
                ]
                built_sections["trade_offs"] = (
                    f"### Key Policy Trade-offs & Counterfactual Analysis\n\n"
                    f"**Comparison:** {counterfactual.get('scenario_a_name')} (Baseline A) vs {counterfactual.get('scenario_b_name')} (Alternative B)\n\n"
                    f"**Verdict:** `{counterfactual.get('verdict', '').upper()}` — *{counterfactual.get('headline', '')}*\n\n"
                    + "\n".join(delta_bullets)
                )
            elif ranking and len(ranking) >= 2:
                runner_up = ranking[1]
                runner_up_name = next((s["name"] for s in summary.get("scenarios", []) if s["id"] == runner_up["scenario_id"]), runner_up["scenario_id"])
                built_sections["trade_offs"] = (
                    f"### Key Policy Trade-offs\n\n"
                    f"Choosing **{top_name}** (Rank #1, score {top_scenario['weighted_score']:.1f}) over the runner-up **{runner_up_name}** "
                    f"(Rank #2, score {runner_up['weighted_score']:.1f}) offers a net advantage of {runner_up['score_delta_from_top']:.1f} points. "
                    f"Decision makers should weigh capital costs against localized service enhancements when finalizing allocation."
                )
            else:
                built_sections["trade_offs"] = "### Key Policy Trade-offs\n\nTrade-off simulation matrix is available to explore pairwise counterfactual trade-offs."

        if "feasibility" in sections:
            if feasibility:
                feas_bullets = []
                for f in feasibility:
                    sc_name = next((s["name"] for s in summary.get("scenarios", []) if s["id"] == f["scenario_id"]), f["scenario_id"])
                    status_text = "✓ FEASIBLE" if f.get("feasible") else "✗ INFEASIBLE"
                    issues = []
                    if f.get("blockers"):
                        issues.append(f"{len(f['blockers'])} blocker(s): " + "; ".join(f["blockers"]))
                    if f.get("warnings"):
                        issues.append(f"{len(f['warnings'])} warning(s): " + "; ".join(f["warnings"]))
                    issue_str = f" ({', '.join(issues)})" if issues else ""
                    feas_bullets.append(f"- **{sc_name}:** `{status_text}`{issue_str}")

                built_sections["feasibility"] = (
                    f"### Planning & Regulatory Feasibility Checks\n\n"
                    f"Deterministic feasibility checks evaluated minimum parcel area, proximity conflicts, service saturation, and zoning compatibility:\n\n"
                    + "\n".join(feas_bullets)
                    + "\n\n*> [!IMPORTANT] Regulatory Distinction:* Warnings represent non-blocking advisory notices for municipal planners. "
                    "Only blockers mandate structural parcel adjustments or zoning variances prior to sanction."
                )
            else:
                built_sections["feasibility"] = "### Planning & Regulatory Feasibility Checks\n\nFeasibility checks have not been evaluated for this session."

        if "comparison_analysis" in sections and "comparison_analysis" not in built_sections:
            built_sections["comparison_analysis"] = built_sections.get("trade_offs", "Pairwise dimension analysis available.")

        if "recommendation_context" in sections and "recommendation_context" not in built_sections:
            built_sections["recommendation_context"] = built_sections.get("recommended_scenario", "Recommendation policy context.")

        return NarrativeResponse(
            narrative_type=request.narrative_type,
            sections=built_sections,
            decision_rationale=decision_rationale_obj,
            generated_by=generated_by,
            fallback_reason=reason,
        )


_narrative_service: Optional[NarrativeService] = None


def get_narrative_service() -> NarrativeService:
    """Retrieve or initialize the singleton NarrativeService."""
    global _narrative_service
    if _narrative_service is None:
        _narrative_service = NarrativeService()
    return _narrative_service
