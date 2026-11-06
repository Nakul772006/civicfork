"""Deterministic counterfactual comparison engine for CivicFork.

Computes pairwise dimension-by-dimension deltas between two scenarios:
Δ = Alternative Scenario (B) score - Baseline Scenario (A) score

Preserves approved neutrality thresholds:
- Δ > +2.0  -> Alternative is meaningfully better ('b_better')
- Δ < -2.0  -> Alternative is meaningfully worse / Baseline is better ('a_better')
- -2.0 <= Δ <= +2.0 -> Practically equivalent ('neutral')
"""

from typing import Dict, List, Optional
from app.models.domain import (
    DIMENSION_NAMES,
    CounterfactualResult,
    DeltaDirection,
    DeltaMagnitude,
    DimensionDelta,
    DimensionName,
    Scenario,
    ScenarioId,
    ScoreMatrix,
)

DEFAULT_SCENARIO_NAMES: Dict[str, str] = {
    "park": "Parks / Recreational Space",
    "healthcare": "Healthcare Facility",
    "education": "Educational Facility",
    "parking": "Public Parking",
    "commercial": "Commercial Development",
    "community_centre": "Community Centre",
    "public_transport": "Public Transport Facility",
}


def compute_magnitude(abs_delta: float) -> DeltaMagnitude:
    """Classify the magnitude of a score delta."""
    if abs_delta < 5.0:
        return "negligible"
    if abs_delta < 15.0:
        return "minor"
    if abs_delta < 30.0:
        return "moderate"
    if abs_delta < 50.0:
        return "significant"
    return "major"


class CounterfactualEngine:
    """Deterministic pairwise counterfactual comparison service."""

    def compare(
        self,
        scenario_a_id: ScenarioId,
        scenario_b_id: ScenarioId,
        score_matrix: ScoreMatrix,
        scenarios: Optional[List[Scenario]] = None,
    ) -> CounterfactualResult:
        """Compare Scenario B (Alternative) against Scenario A (Baseline).

        Args:
            scenario_a_id: Baseline/current scenario ID.
            scenario_b_id: Alternative scenario ID to compare against baseline.
            score_matrix: Authoritative 7x6 score matrix from simulation.
            scenarios: Optional list of generated Scenario domain objects for metadata.

        Returns:
            CounterfactualResult with dimension deltas, win counts, and verdict.
        """
        # Build scenario name map
        name_map = dict(DEFAULT_SCENARIO_NAMES)
        if scenarios:
            for s in scenarios:
                name_map[s.id] = s.name

        name_a = name_map.get(scenario_a_id, str(scenario_a_id))
        name_b = name_map.get(scenario_b_id, str(scenario_b_id))

        # Extract ScenarioScores
        scores_by_id = {sc.scenario_id: sc for sc in score_matrix.scenario_scores}
        if scenario_a_id not in scores_by_id:
            raise ValueError(f"Scenario '{scenario_a_id}' not found in simulation score matrix")
        if scenario_b_id not in scores_by_id:
            raise ValueError(f"Scenario '{scenario_b_id}' not found in simulation score matrix")

        sc_a = scores_by_id[scenario_a_id]
        sc_b = scores_by_id[scenario_b_id]

        dim_scores_a = {ds.dimension: ds for ds in sc_a.scores}
        dim_scores_b = {ds.dimension: ds for ds in sc_b.scores}

        deltas: List[DimensionDelta] = []
        a_wins: List[str] = []
        b_wins: List[str] = []
        neutral: List[str] = []

        # Evaluate all 6 dimensions deterministically
        for dim in DIMENSION_NAMES:
            ds_a = dim_scores_a.get(dim)
            ds_b = dim_scores_b.get(dim)

            score_a = round(ds_a.score if ds_a else 0.0, 1)
            score_b = round(ds_b.score if ds_b else 0.0, 1)

            # Delta = Alternative (B) - Baseline (A)
            # Positive delta means B/Alternative is better
            # Negative delta means A/Baseline is better
            delta = round(score_b - score_a, 1)
            abs_delta = round(abs(delta), 1)

            if delta > 2.0:
                direction: DeltaDirection = "b_better"
                b_wins.append(dim)
            elif delta < -2.0:
                direction: DeltaDirection = "a_better"
                a_wins.append(dim)
            else:
                direction: DeltaDirection = "neutral"
                neutral.append(dim)

            magnitude = compute_magnitude(abs_delta)

            expl_a = (ds_a.direction_note if ds_a and ds_a.direction_note else f"{name_a} {dim}: {score_a}")
            expl_b = (ds_b.direction_note if ds_b and ds_b.direction_note else f"{name_b} {dim}: {score_b}")

            deltas.append(
                DimensionDelta(
                    dimension=dim,
                    score_a=score_a,
                    score_b=score_b,
                    delta=delta,
                    abs_delta=abs_delta,
                    direction=direction,
                    magnitude=magnitude,
                    explanation_a_summary=expl_a,
                    explanation_b_summary=expl_b,
                )
            )

        net_delta = round(sum(d.delta for d in deltas), 1)

        # Verdict logic
        if net_delta > 2.0:
            verdict = "meaningfully_better"
            net_advantage = scenario_b_id
            headline = f"{name_b} outperforms {name_a} on {len(b_wins)} of 6 dimensions (net delta +{net_delta:.1f} pts)"
        elif net_delta < -2.0:
            verdict = "meaningfully_worse"
            net_advantage = scenario_a_id
            headline = f"{name_a} outperforms {name_b} on {len(a_wins)} of 6 dimensions (net delta {net_delta:.1f} pts)"
        else:
            verdict = "practically_equivalent"
            net_advantage = "balanced"
            headline = f"{name_b} and {name_a} demonstrate practically equivalent performance across the 6 dimensions"

        return CounterfactualResult(
            scenario_a_id=scenario_a_id,
            scenario_a_name=name_a,
            scenario_b_id=scenario_b_id,
            scenario_b_name=name_b,
            deltas=deltas,
            a_wins_dimensions=a_wins,
            b_wins_dimensions=b_wins,
            neutral_dimensions=neutral,
            net_advantage=net_advantage,
            net_delta=net_delta,
            headline=headline,
            verdict=verdict,
        )


_counterfactual_engine: Optional[CounterfactualEngine] = None


def get_counterfactual_engine() -> CounterfactualEngine:
    """Singleton getter for CounterfactualEngine."""
    global _counterfactual_engine
    if _counterfactual_engine is None:
        _counterfactual_engine = CounterfactualEngine()
    return _counterfactual_engine
