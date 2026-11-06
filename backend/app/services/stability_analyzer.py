"""Decision Stability / Sensitivity Analysis Service for CivicFork.

Deterministically synthesises multi-dimensional scenario scores across alternative
municipal priority-weight configurations to evaluate how robust the recommended
scenario is when municipal priorities change.

Calculation methodology:
1. Deterministic Sensitivity Configurations:
   Evaluates 7 distinct, mathematically unique priority configurations:
   - Balanced Priorities (equal 1.0 weights across all six dimensions)
   - Traffic Priority (traffic 5.0, others 0.5)
   - Environmental Priority (environmental 5.0, others 0.5)
   - Accessibility Priority (accessibility 5.0, others 0.5)
   - Cost / Fiscal Priority (cost 5.0, others 0.5)
   - Infrastructure Gap Priority (gap_improvement 5.0, others 0.5)
   - Social Utility Priority (social_utility 5.0, others 0.5)

2. Winner & Baseline Evaluation:
   Reuses the authoritative CivicFork RankingEngine to determine the winning
   scenario (#1) and baseline scenario rank/score for each configuration.

3. Stability Score & Categorization:
   stability_score = round(100.0 * baseline_wins / total_configurations, 1)
   - >= 75.0 -> HIGH
   - >= 50.0 and < 75.0 -> MODERATE
   - < 50.0 -> LOW

4. Strongest Challenger & Deterministic Tie-Breaking:
   Identifies the non-baseline scenario with the highest win count.
   Ties are broken deterministically by:
   - Primary: Win count descending
   - Secondary: Baseline ranking position ascending (higher rank / lower number wins)
   - Tertiary: Scenario ID alphabetical ascending
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from app.config_loader import AppConfig, get_app_config
from app.models.domain import (
    ChallengerInfo,
    ConfigurationResult,
    RankedScenario,
    Scenario,
    ScenarioScore,
    ScoreMatrix,
    StabilityResult,
    WeightConfig,
)
from app.services.ranking_engine import RankingEngine, get_ranking_engine

logger = logging.getLogger("civicfork.stability_analyzer")

# Exactly 7 mathematically unique configurations
STABILITY_CONFIGURATIONS: List[Dict[str, Any]] = [
    {
        "id": "balanced",
        "name": "Balanced Priorities",
        "description": "Equal priority across all six municipal dimensions (1.0 each)",
        "weights": WeightConfig(
            traffic=1.0,
            cost=1.0,
            environmental=1.0,
            accessibility=1.0,
            gap_improvement=1.0,
            social_utility=1.0,
        ),
    },
    {
        "id": "traffic_priority",
        "name": "Traffic Priority",
        "description": "Traffic decongestion heavily weighted (5.0 vs 0.5 others)",
        "weights": WeightConfig(
            traffic=5.0,
            cost=0.5,
            environmental=0.5,
            accessibility=0.5,
            gap_improvement=0.5,
            social_utility=0.5,
        ),
    },
    {
        "id": "environmental_priority",
        "name": "Environmental Priority",
        "description": "Urban ecology and green space heavily weighted (5.0 vs 0.5 others)",
        "weights": WeightConfig(
            traffic=0.5,
            cost=0.5,
            environmental=5.0,
            accessibility=0.5,
            gap_improvement=0.5,
            social_utility=0.5,
        ),
    },
    {
        "id": "accessibility_priority",
        "name": "Accessibility Priority",
        "description": "Citizen accessibility and transit reach heavily weighted (5.0 vs 0.5 others)",
        "weights": WeightConfig(
            traffic=0.5,
            cost=0.5,
            environmental=0.5,
            accessibility=5.0,
            gap_improvement=0.5,
            social_utility=0.5,
        ),
    },
    {
        "id": "cost_priority",
        "name": "Cost Priority",
        "description": "Municipal capital and operational savings heavily weighted (5.0 vs 0.5 others)",
        "weights": WeightConfig(
            traffic=0.5,
            cost=5.0,
            environmental=0.5,
            accessibility=0.5,
            gap_improvement=0.5,
            social_utility=0.5,
        ),
    },
    {
        "id": "gap_improvement_priority",
        "name": "Gap Improvement Priority",
        "description": "Alleviating verified local infrastructure deficits heavily weighted (5.0 vs 0.5 others)",
        "weights": WeightConfig(
            traffic=0.5,
            cost=0.5,
            environmental=0.5,
            accessibility=0.5,
            gap_improvement=5.0,
            social_utility=0.5,
        ),
    },
    {
        "id": "social_utility_priority",
        "name": "Social Utility Priority",
        "description": "Community benefit and public service reach heavily weighted (5.0 vs 0.5 others)",
        "weights": WeightConfig(
            traffic=0.5,
            cost=0.5,
            environmental=0.5,
            accessibility=0.5,
            gap_improvement=0.5,
            social_utility=5.0,
        ),
    },
]


class StabilityAnalyzer:
    """Service responsible for deterministic decision stability / sensitivity analysis."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        ranking_engine: Optional[RankingEngine] = None,
    ):
        self._config = config
        self._ranking_engine = ranking_engine or get_ranking_engine(config)

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            self._config = get_app_config()
        return self._config

    def analyze(
        self,
        score_matrix: Union[ScoreMatrix, List[ScenarioScore], Dict[str, Any]],
        baseline_ranking: List[RankedScenario],
        scenarios: Optional[List[Scenario]] = None,
    ) -> StabilityResult:
        """Evaluate stability of baseline recommendation under alternative priority weights.

        Args:
            score_matrix: Authoritative score matrix from ImpactSimulator.
            baseline_ranking: Current ranked scenario list from RankingEngine (rank #1 is baseline).
            scenarios: Optional scenario definitions for name resolution.

        Returns:
            StabilityResult with scores, levels, challenger, and per-configuration breakdown.
        """
        if not baseline_ranking:
            raise ValueError("baseline_ranking must contain at least one ranked scenario")

        # 1. Identify baseline recommended scenario (Rank #1)
        baseline_item = baseline_ranking[0]
        baseline_id = baseline_item.scenario_id
        baseline_name = baseline_item.scenario_name

        # Map baseline ranks and scenario names
        baseline_ranks: Dict[str, int] = {item.scenario_id: item.rank for item in baseline_ranking}
        scenario_names: Dict[str, str] = {item.scenario_id: item.scenario_name for item in baseline_ranking}

        if scenarios:
            for s in scenarios:
                if s.id not in scenario_names:
                    scenario_names[s.id] = s.name

        # Track win counts for all known scenarios
        scenario_win_counts: Dict[str, int] = {sid: 0 for sid in baseline_ranks.keys()}

        configuration_results: List[ConfigurationResult] = []
        configurations_tested: List[str] = []
        baseline_wins = 0

        # 2. Evaluate each deterministic configuration
        for cfg in STABILITY_CONFIGURATIONS:
            cfg_id = cfg["id"]
            cfg_name = cfg["name"]
            cfg_weights: WeightConfig = cfg["weights"]
            configurations_tested.append(cfg_name)

            # Deterministic ranking using existing RankingEngine
            ranked = self._ranking_engine.rank(
                scores_or_matrix_or_session=score_matrix,
                weights=cfg_weights,
                scenarios=scenarios,
            )

            winner = ranked[0]
            winning_id = winner.scenario_id
            winning_name = winner.scenario_name or scenario_names.get(winning_id, winning_id)
            winning_score = round(float(winner.weighted_score), 1)

            # Find baseline scenario performance in this configuration
            baseline_in_cfg = next((r for r in ranked if r.scenario_id == baseline_id), None)
            if baseline_in_cfg is not None:
                b_rank = baseline_in_cfg.rank
                b_score = round(float(baseline_in_cfg.weighted_score), 1)
            else:
                b_rank = len(ranked)
                b_score = 0.0

            baseline_won = (winning_id == baseline_id)
            if baseline_won:
                baseline_wins += 1

            if winning_id not in scenario_win_counts:
                scenario_win_counts[winning_id] = 0
            scenario_win_counts[winning_id] += 1

            configuration_results.append(
                ConfigurationResult(
                    configuration_id=cfg_id,
                    configuration_name=cfg_name,
                    weights=cfg_weights.model_dump(),
                    winning_scenario_id=winning_id,
                    winning_scenario_name=winning_name,
                    winning_score=winning_score,
                    baseline_rank=b_rank,
                    baseline_score=b_score,
                    baseline_won=baseline_won,
                )
            )

        total_configs = len(STABILITY_CONFIGURATIONS)
        stability_score = round(100.0 * baseline_wins / total_configs, 1)

        # 3. Categorize stability level deterministically
        if stability_score >= 75.0:
            stability_level = "HIGH"
            interpretation = (
                "The recommendation remains the top-ranked option across most tested priority configurations."
            )
        elif stability_score >= 50.0:
            stability_level = "MODERATE"
            interpretation = (
                "The recommendation is sensitive to changes in municipal priorities and has a meaningful alternative."
            )
        else:
            stability_level = "LOW"
            interpretation = (
                "The recommendation changes substantially when municipal priorities shift."
            )

        # 4. Identify strongest challenger with deterministic tie-breaking
        non_baseline_ids = [sid for sid in baseline_ranks.keys() if sid != baseline_id]

        strongest_challenger: Optional[ChallengerInfo] = None
        if non_baseline_ids:
            # Sort order:
            # 1. wins descending
            # 2. baseline rank ascending (lower rank number = better)
            # 3. scenario_id ascending
            sorted_challengers = sorted(
                non_baseline_ids,
                key=lambda sid: (
                    -scenario_win_counts.get(sid, 0),
                    baseline_ranks.get(sid, 999),
                    sid,
                ),
            )
            top_challenger_id = sorted_challengers[0]
            top_challenger_wins = scenario_win_counts.get(top_challenger_id, 0)
            strongest_challenger = ChallengerInfo(
                scenario_id=top_challenger_id,
                scenario_name=scenario_names.get(top_challenger_id, top_challenger_id),
                wins=top_challenger_wins,
            )

        # 5. Build calculation trace & provenance
        calculation_trace = {
            "provenance": {
                "score_matrix": "calculated",
                "baseline_ranking": "derived",
                "priority_configurations": "configured",
                "stability_score": "derived",
            },
            "methodology": (
                "Deterministic sensitivity evaluation across 7 orthogonal priority weight "
                "vectors using the CivicFork ranking engine."
            ),
            "disclaimer": (
                "Modelled sensitivity analysis for municipal decision support; not an "
                "empirical forecast of real-world outcomes."
            ),
        }

        return StabilityResult(
            baseline_scenario_id=baseline_id,
            baseline_scenario_name=baseline_name,
            configurations_tested=configurations_tested,
            baseline_wins=baseline_wins,
            total_configurations=total_configs,
            stability_score=stability_score,
            stability_level=stability_level,
            scenario_win_counts=scenario_win_counts,
            strongest_challenger=strongest_challenger,
            interpretation=interpretation,
            configuration_results=configuration_results,
            calculation_trace=calculation_trace,
        )


_default_stability_analyzer: Optional[StabilityAnalyzer] = None


def get_stability_analyzer(
    config: Optional[AppConfig] = None,
    ranking_engine: Optional[RankingEngine] = None,
) -> StabilityAnalyzer:
    """Dependency provider for StabilityAnalyzer singleton."""
    global _default_stability_analyzer
    if _default_stability_analyzer is None or config is not None or ranking_engine is not None:
        _default_stability_analyzer = StabilityAnalyzer(
            config=config,
            ranking_engine=ranking_engine,
        )
    return _default_stability_analyzer
