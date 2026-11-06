"""Ranking and Weighting Engine for CivicFork.

Deterministically synthesises multi-dimensional scenario scores with municipal priority
weights into weighted composite scores, producing an explainable descending ranking
of the seven development alternatives.

Ranking methodology:
1. Weight Normalization:
   w_hat_d = w_d / sum(w_d')  (defaults to equal 1/6 if weights sum to 0)
2. Weighted Composite Score:
   composite(s) = sum(w_hat_d * score(s, d))
3. Dimension Contributions:
   contribution(s, d) = round(w_hat_d * score(s, d), 2)
4. Descending Sort & Tie-Breaking:
   - Primary: weighted_score descending (higher is better)
   - Secondary (tie-breaker): gap_improvement score descending
   - Tertiary (tie-breaker): scenario_id ascending (alphabetical)
5. Delta from Top:
   delta_from_top(s) = round(top_scenario.weighted_score - s.weighted_score, 1)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from app.config_loader import AppConfig, get_app_config
from app.models.domain import (
    DIMENSION_NAMES,
    RankedScenario,
    Scenario,
    ScenarioId,
    ScenarioScore,
    ScoreMatrix,
    SessionData,
    WeightConfig,
)

logger = logging.getLogger("civicfork.ranking_engine")


class RankingEngine:
    """Service responsible for municipal priority weighting and scenario ranking."""

    def __init__(self, config: Optional[AppConfig] = None):
        self._config = config
        self._last_trace: Dict[str, Any] = {}

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            self._config = get_app_config()
        return self._config

    @property
    def last_trace(self) -> Dict[str, Any]:
        """Return a copy of the ranking and provenance trace from the latest execution."""
        return dict(self._last_trace)

    def rank(
        self,
        scores_or_matrix_or_session: Union[ScoreMatrix, List[ScenarioScore], SessionData],
        weights: Optional[Union[WeightConfig, Dict[str, float]]] = None,
        scenarios: Optional[List[Scenario]] = None,
        config: Optional[AppConfig] = None,
    ) -> List[RankedScenario]:
        """Calculate weighted composite scores and produce a ranked scenario list.

        Args:
            scores_or_matrix_or_session: ScoreMatrix, list of ScenarioScore, or SessionData.
            weights: Optional municipal priority weights; defaults to equal weights (1/6 each).
            scenarios: Optional list of Scenario domain models to resolve display names.
            config: Optional AppConfig override.

        Returns:
            List of RankedScenario models ordered from rank 1 (best) to rank 7 (worst).
        """
        active_config = config or self._config or self.config

        # 1. Resolve inputs and normalize weights
        scenario_scores, resolved_scenarios, session = self._resolve_inputs(
            scores_or_matrix_or_session=scores_or_matrix_or_session,
            scenarios=scenarios,
        )

        normalised_weights, raw_weights_dict = self._normalize_weights(weights)

        # Map scenario names for display
        names_by_id = self._build_name_map(resolved_scenarios, active_config)

        logger.info(
            "Ranking %d scenarios with priority weights: %s",
            len(scenario_scores),
            normalised_weights.model_dump(),
        )

        # 2. Compute weighted composite score and dimension contributions for each scenario
        candidate_items: List[Dict[str, Any]] = []

        for sc in scenario_scores:
            sid = sc.scenario_id
            dim_scores = {ds.dimension: ds.score for ds in sc.scores}

            # Dot product of dimension scores and normalized weights
            weighted_val = (
                dim_scores.get("traffic", 0.0) * normalised_weights.traffic
                + dim_scores.get("cost", 0.0) * normalised_weights.cost
                + dim_scores.get("environmental", 0.0) * normalised_weights.environmental
                + dim_scores.get("accessibility", 0.0) * normalised_weights.accessibility
                + dim_scores.get("gap_improvement", 0.0) * normalised_weights.gap_improvement
                + dim_scores.get("social_utility", 0.0) * normalised_weights.social_utility
            )

            # Clamped to [0.0, 100.0] and rounded to 1 decimal place
            clamped_weighted_score = round(min(100.0, max(0.0, weighted_val)), 1)

            # Dimension contributions: contribution(s, d) = round(weight_d * score_d, 2)
            contributions = {
                "traffic": round(dim_scores.get("traffic", 0.0) * normalised_weights.traffic, 2),
                "cost": round(dim_scores.get("cost", 0.0) * normalised_weights.cost, 2),
                "environmental": round(
                    dim_scores.get("environmental", 0.0) * normalised_weights.environmental, 2
                ),
                "accessibility": round(
                    dim_scores.get("accessibility", 0.0) * normalised_weights.accessibility, 2
                ),
                "gap_improvement": round(
                    dim_scores.get("gap_improvement", 0.0) * normalised_weights.gap_improvement, 2
                ),
                "social_utility": round(
                    dim_scores.get("social_utility", 0.0) * normalised_weights.social_utility, 2
                ),
            }

            candidate_items.append({
                "scenario_id": sid,
                "scenario_name": names_by_id.get(sid, sid.replace("_", " ").title()),
                "raw_weighted": round(weighted_val, 4),
                "clamped_weighted": clamped_weighted_score,
                "gap_score": dim_scores.get("gap_improvement", 0.0),
                "dim_scores": dim_scores,
                "contributions": contributions,
                "unweighted_composite": sc.unweighted_composite,
            })

        # 3. Sort by:
        #    - weighted score descending (higher is better)
        #    - secondary: gap_improvement score descending
        #    - tertiary: scenario_id ascending (alphabetical)
        candidate_items.sort(
            key=lambda x: (-x["raw_weighted"], -x["gap_score"], x["scenario_id"])
        )

        top_score = candidate_items[0]["clamped_weighted"] if candidate_items else 0.0

        # 4. Construct RankedScenario instances and record trace
        ranked_results: List[RankedScenario] = []
        scenario_traces: Dict[str, Dict[str, Any]] = {}

        for idx, item in enumerate(candidate_items, start=1):
            sid = item["scenario_id"]
            delta_from_top = round(max(0.0, top_score - item["clamped_weighted"]), 1)

            ranked_obj = RankedScenario(
                rank=idx,
                scenario_id=sid,
                scenario_name=item["scenario_name"],
                weighted_score=item["clamped_weighted"],
                dimension_contributions=item["contributions"],
                score_delta_from_top=delta_from_top,
            )
            ranked_results.append(ranked_obj)

            scenario_traces[sid] = {
                "rank": idx,
                "scenario_id": sid,
                "scenario_name": item["scenario_name"],
                "weighted_score": item["clamped_weighted"],
                "raw_weighted_score": item["raw_weighted"],
                "unweighted_composite": item["unweighted_composite"],
                "score_delta_from_top": delta_from_top,
                "dimension_scores": item["dim_scores"],
                "dimension_contributions": item["contributions"],
                "weights_applied": normalised_weights.model_dump(),
                "formula": "weighted_score = sum(normalized_weight[d] * score[d])",
            }

        # 5. Save structured trace
        self._last_trace = {
            "weights_supplied": raw_weights_dict,
            "weights_normalized": normalised_weights.model_dump(),
            "ranking_order": [r.scenario_id for r in ranked_results],
            "scenarios": scenario_traces,
            "ranking_rules": {
                "score_range": "0-100 (higher is better)",
                "sorting": "Descending by weighted composite score",
                "tie_breaking": "1st tie-breaker: Gap Improvement score descending; 2nd tie-breaker: Alphabetical scenario ID",
            },
        }

        # 6. If operating on SessionData, update session state
        if session is not None:
            session.ranking = ranked_results
            session.weights_used = normalised_weights

        return ranked_results

    def get_calculation_trace(self, scenario_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve explainability and calculation trace for the ranking.

        Args:
            scenario_id: Optional scenario ID. If provided, returns the trace for that scenario;
                         otherwise returns the complete ranking trace.
        """
        if not self._last_trace:
            raise KeyError("No ranking calculation trace available. Run rank() first.")

        if scenario_id is not None:
            sid = str(scenario_id)
            if sid in self._last_trace.get("scenarios", {}):
                return dict(self._last_trace["scenarios"][sid])
            raise KeyError(f"No calculation trace available for scenario '{sid}'.")

        return dict(self._last_trace)

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------

    def _resolve_inputs(
        self,
        scores_or_matrix_or_session: Union[ScoreMatrix, List[ScenarioScore], SessionData],
        scenarios: Optional[List[Scenario]],
    ) -> Tuple[List[ScenarioScore], Optional[List[Scenario]], Optional[SessionData]]:
        """Normalize varied input types into a list of ScenarioScore models."""
        session: Optional[SessionData] = None
        resolved_scenarios = scenarios

        if isinstance(scores_or_matrix_or_session, SessionData):
            session = scores_or_matrix_or_session
            matrix = session.score_matrix
            if matrix is None:
                raise ValueError("SessionData does not contain a score_matrix. Run ImpactSimulator first.")
            if isinstance(matrix, ScoreMatrix):
                scenario_scores = matrix.scenario_scores
            elif isinstance(matrix, dict):
                scenario_scores = [ScenarioScore(**s) for s in matrix.get("scenario_scores", [])]
            else:
                raise TypeError(f"Unsupported score_matrix type in SessionData: {type(matrix)}")

            if resolved_scenarios is None and session.scenarios:
                resolved_scenarios = (
                    session.scenarios
                    if isinstance(session.scenarios[0], Scenario)
                    else [Scenario(**s) for s in session.scenarios]
                )

        elif isinstance(scores_or_matrix_or_session, ScoreMatrix):
            scenario_scores = scores_or_matrix_or_session.scenario_scores

        elif isinstance(scores_or_matrix_or_session, list):
            scenario_scores = scores_or_matrix_or_session

        else:
            raise TypeError("Expected ScoreMatrix, List[ScenarioScore], or SessionData.")

        if not scenario_scores:
            raise ValueError("No scenario scores provided to rank.")

        return scenario_scores, resolved_scenarios, session

    def _normalize_weights(
        self, weights: Optional[Union[WeightConfig, Dict[str, float]]]
    ) -> Tuple[WeightConfig, Dict[str, float]]:
        """Normalize weights to sum to 1.0."""
        if weights is None:
            raw_weights = WeightConfig()
            raw_dict = raw_weights.model_dump()
            return raw_weights.normalised(), raw_dict

        if isinstance(weights, dict):
            raw_dict = dict(weights)
            env_w = raw_dict.get("environmental", raw_dict.get("environment", 1.0))
            raw_weights = WeightConfig(
                traffic=raw_dict.get("traffic", 1.0),
                cost=raw_dict.get("cost", 1.0),
                environmental=env_w,
                accessibility=raw_dict.get("accessibility", 1.0),
                gap_improvement=raw_dict.get("gap_improvement", 1.0),
                social_utility=raw_dict.get("social_utility", 1.0),
            )
            return raw_weights.normalised(), raw_dict

        if isinstance(weights, WeightConfig):
            return weights.normalised(), weights.model_dump()

        raise TypeError(f"Unsupported weights type: {type(weights)}")

    def _build_name_map(
        self,
        scenarios: Optional[List[Scenario]],
        config: AppConfig,
    ) -> Dict[str, str]:
        """Build scenario ID to display name mapping."""
        name_map: Dict[str, str] = {}
        if scenarios:
            for s in scenarios:
                name_map[s.id] = s.name

        # Fill any missing names from config
        for sid, t in config.scenarios.scenarios.items():
            if sid not in name_map:
                name_map[sid] = t.name

        return name_map


_ranking_engine_instance: Optional[RankingEngine] = None


def get_ranking_engine(
    config: Optional[AppConfig] = None, force_reload: bool = False
) -> RankingEngine:
    """Return the singleton RankingEngine instance."""
    global _ranking_engine_instance
    if _ranking_engine_instance is None or force_reload or config is not None:
        _ranking_engine_instance = RankingEngine(config=config)
    return _ranking_engine_instance
