/**
 * Automated Phase 3.0 frontend client workflow verification.
 * Tests the real frontend apiClient against running FastAPI backend.
 */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { apiClient } from './src/api/client.js';

const MYSURU_PLOT = {
  lat: 12.3100,
  lng: 76.6500,
  radius_m: 2000,
  area_sqm: 3500.0,
  label: 'Frontend Test Parcel',
};

test('1. System Health Verification', async () => {
  const health = await apiClient.checkHealth();
  assert.equal(health.status, 'healthy');
  assert.equal(health.osm_data_loaded, true);
  assert.equal(health.config_loaded, true);
  assert.equal(health.demo_area, 'mysuru');
});

test('2. Stage 1: Plot Analysis & Session Creation', async () => {
  const data = await apiClient.analyzePlot(MYSURU_PLOT);
  assert.ok(data.session_id, 'session_id should be returned');
  assert.equal(data.plot.lat, 12.3100);
  assert.equal(data.plot.lng, 76.6500);

  // Context summary validation
  assert.ok(data.context_summary.total_pois > 0, 'POIs should be observed');
  assert.ok(data.context_summary.road_network_length_m > 0);
  assert.ok(data.context_summary.population_density_estimate > 0);
  assert.ok(data.context_summary.ward != null, 'Ward context should be resolved for Saraswathipuram');
  assert.equal(data.context_summary.ward.ward_id, '41');
  assert.equal(data.context_summary.nearest_water_body_name, 'Kukkarahalli Lake');
  assert.ok(data.context_summary.nearest_water_body_m > 0);
  assert.ok(data.context_summary.water_body_count >= 1);

  // 7 Infrastructure gaps
  assert.equal(data.gaps.length, 7);

  // 7 Scenarios
  assert.equal(data.scenarios.length, 7);
  for (const s of data.scenarios) {
    assert.ok(s.id);
    assert.ok(s.name);
    assert.ok(s.estimated_cost_inr > 0);
  }

  // GeoJSON layers
  assert.equal(data.poi_geojson.type, 'FeatureCollection');
  assert.equal(data.landuse_geojson.type, 'FeatureCollection');
  assert.equal(data.transport_geojson.type, 'FeatureCollection');
});

test('3. Stage 2 & 3: Simulation and Ranking Sequence with Same session_id', async () => {
  // 3a. Analyze
  const analyzeData = await apiClient.analyzePlot(MYSURU_PLOT);
  const sessionId = analyzeData.session_id;

  // 3b. Simulate using captured session_id
  const simData = await apiClient.simulateScenarios(sessionId);
  assert.equal(simData.scenarios.length, 7);
  assert.equal(simData.score_matrix.scenarios_evaluated, 7);
  assert.equal(simData.score_matrix.dimensions_evaluated, 6);
  assert.equal(simData.default_ranking.length, 7);
  assert.equal(simData.default_ranking[0].rank, 1);
  assert.equal(simData.default_ranking[0].score_delta_from_top, 0.0);

  // 3c. Rank with balanced weights
  const balancedWeights = {
    traffic: 1.0,
    cost: 1.0,
    environmental: 1.0,
    accessibility: 1.0,
    gap_improvement: 1.0,
    social_utility: 1.0,
  };
  const rankData1 = await apiClient.rankScenarios(sessionId, balancedWeights);
  assert.equal(rankData1.ranking.length, 7);
  assert.equal(rankData1.ranking[0].rank, 1);

  // Verify dimension contributions
  for (const r of rankData1.ranking) {
    assert.ok(r.dimension_contributions);
    const contribSum = Object.values(r.dimension_contributions).reduce((a, b) => a + b, 0);
    assert.ok(Math.abs(r.weighted_score - contribSum) <= 0.1, 'Contributions must sum to weighted score');
  }

  // 3d. Rank with environmental-heavy priority weights
  const envWeights = {
    traffic: 0.5,
    cost: 0.5,
    environmental: 5.0,
    accessibility: 1.0,
    gap_improvement: 2.0,
    social_utility: 1.0,
  };
  const rankData2 = await apiClient.rankScenarios(sessionId, envWeights);
  assert.equal(rankData2.ranking.length, 7);
  assert.equal(rankData2.ranking[0].rank, 1);

  // Verify weights altered scores
  assert.notEqual(rankData1.ranking[0].weighted_score, rankData2.ranking[0].weighted_score);
});

test('4. Error Handling: Out-of-Bounds Plot & Invalid Session', async () => {
  // 4a. Out of bounds
  await assert.rejects(
    async () => {
      await apiClient.analyzePlot({ ...MYSURU_PLOT, lat: 15.0000 });
    },
    (err) => {
      assert.equal(err.code, 'VALIDATION_ERROR');
      return true;
    }
  );

  // 4b. Invalid session ID
  await assert.rejects(
    async () => {
      await apiClient.simulateScenarios('00000000-0000-0000-0000-000000000000');
    },
    (err) => {
      assert.equal(err.code, 'SESSION_NOT_FOUND');
      return true;
    }
  );
});

test('5. Stage 4: Pairwise Counterfactual Comparison (A vs B)', async () => {
  const analyzeData = await apiClient.analyzePlot(MYSURU_PLOT);
  const sessionId = analyzeData.session_id;
  await apiClient.simulateScenarios(sessionId);

  // Compare Park (A) vs Healthcare (B)
  const cfData = await apiClient.compareScenarios(sessionId, 'park', 'healthcare');
  assert.ok(cfData.result, 'result should be returned');
  const res = cfData.result;

  assert.equal(res.scenario_a_id, 'park');
  assert.equal(res.scenario_b_id, 'healthcare');
  assert.equal(res.deltas.length, 6);

  // Check delta calculation: Alternative (B) - Baseline (A)
  for (const d of res.deltas) {
    const expectedDelta = Math.round((d.score_b - d.score_a) * 10) / 10;
    assert.equal(d.delta, expectedDelta);
    assert.equal(d.abs_delta, Math.round(Math.abs(expectedDelta) * 10) / 10);
    assert.ok(['a_better', 'b_better', 'neutral'].includes(d.direction));
    assert.ok(['negligible', 'minor', 'moderate', 'significant', 'major'].includes(d.magnitude));
  }

  // Check verdict & headline
  assert.ok(['meaningfully_better', 'meaningfully_worse', 'practically_equivalent'].includes(res.verdict));
  assert.ok(res.headline && res.headline.length > 0);

  // Test symmetry / swap
  const swappedData = await apiClient.compareScenarios(sessionId, 'healthcare', 'park');
  assert.ok(Math.abs(res.net_delta + swappedData.result.net_delta) <= 0.2);
});

test('6. Counterfactual Validation & Prerequisites', async () => {
  const analyzeData = await apiClient.analyzePlot(MYSURU_PLOT);
  const sessionId = analyzeData.session_id;

  // 6a. Calling counterfactual before simulation should fail with MISSING_PREREQUISITE
  await assert.rejects(
    async () => {
      await apiClient.compareScenarios(sessionId, 'park', 'healthcare');
    },
    (err) => {
      assert.equal(err.code, 'MISSING_PREREQUISITE');
      return true;
    }
  );

  // Simulate now
  await apiClient.simulateScenarios(sessionId);

  // 6b. Same scenario on both sides rejected with VALIDATION_ERROR
  await assert.rejects(
    async () => {
      await apiClient.compareScenarios(sessionId, 'park', 'park');
    },
    (err) => {
      assert.equal(err.code, 'VALIDATION_ERROR');
      return true;
    }
  );
});

test('7. Stage 5: Scenario Feasibility Constraints Check', async () => {
  const analyzeData = await apiClient.analyzePlot(MYSURU_PLOT);
  const sessionId = analyzeData.session_id;
  await apiClient.simulateScenarios(sessionId);

  // 7a. Check feasibility for all 7 scenarios
  const feasDataAll = await apiClient.checkFeasibility(sessionId);
  assert.ok(feasDataAll.verdicts, 'verdicts array should be returned');
  assert.equal(feasDataAll.verdicts.length, 7);

  const scenarioIds = feasDataAll.verdicts.map((v) => v.scenario_id);
  assert.ok(scenarioIds.includes('park'));
  assert.ok(scenarioIds.includes('healthcare'));
  assert.ok(scenarioIds.includes('education'));

  for (const v of feasDataAll.verdicts) {
    assert.ok(v.scenario_id);
    assert.equal(typeof v.feasible, 'boolean');
    assert.equal(typeof v.blocker_count, 'number');
    assert.equal(typeof v.warning_count, 'number');
    assert.equal(v.blockers.length, v.blocker_count);
    assert.equal(v.warnings.length, v.warning_count);
    assert.equal(v.feasible, v.blocker_count === 0);
    assert.equal(v.checks.length, 4);

    for (const c of v.checks) {
      assert.ok(['minimum_area', 'proximity_conflict', 'service_saturation', 'zoning_compatibility'].includes(c.check_name));
      assert.equal(typeof c.passed, 'boolean');
      assert.ok(['warning', 'blocker'].includes(c.severity));
      assert.ok(typeof c.message === 'string' && c.message.length > 0);
      assert.ok(typeof c.details === 'object');
    }
  }

  // 7b. Check single scenario feasibility (e.g. healthcare)
  const feasDataSingle = await apiClient.checkFeasibility(sessionId, 'healthcare');
  assert.ok(feasDataSingle.verdicts);
  assert.equal(feasDataSingle.verdicts.length, 1);
  assert.equal(feasDataSingle.verdicts[0].scenario_id, 'healthcare');

  // 7c. Small plot test (200 sqm) - should trigger blocker for healthcare (requires 2000 sqm)
  const smallPlot = { ...MYSURU_PLOT, area_sqm: 200.0, label: 'Tiny Parcel' };
  const smallPlotData = await apiClient.analyzePlot(smallPlot);
  const smallSessionId = smallPlotData.session_id;
  await apiClient.simulateScenarios(smallSessionId);

  const smallFeas = await apiClient.checkFeasibility(smallSessionId, 'healthcare');
  const hcVerdict = smallFeas.verdicts[0];
  assert.equal(hcVerdict.feasible, false, 'Healthcare should be infeasible on 200 sqm plot');
  assert.ok(hcVerdict.blocker_count >= 1);
  assert.ok(hcVerdict.blockers.some((b) => b.includes('Plot area') || b.includes('below minimum')));
});

test('8. Feasibility Validation & Prerequisite Handling', async () => {
  // 8a. Feasibility on non-existent session
  await assert.rejects(
    async () => {
      await apiClient.checkFeasibility('00000000-0000-0000-0000-000000000000');
    },
    (err) => {
      assert.equal(err.code, 'SESSION_NOT_FOUND');
      return true;
    }
  );

  // 8b. Invalid scenario ID
  const analyzeData = await apiClient.analyzePlot(MYSURU_PLOT);
  const sessionId = analyzeData.session_id;

  await assert.rejects(
    async () => {
      await apiClient.checkFeasibility(sessionId, 'invalid_scenario_xyz');
    },
    (err) => {
      assert.equal(err.code, 'VALIDATION_ERROR');
      return true;
    }
  );
});

test('9. Stage 6: AI Narrative Synthesis & Deterministic Fallback Verification', async () => {
  // Complete full pipeline first
  const analyzeData = await apiClient.analyzePlot(MYSURU_PLOT);
  const sessionId = analyzeData.session_id;
  await apiClient.simulateScenarios(sessionId);
  await apiClient.rankScenarios(sessionId, {
    traffic: 1.0,
    cost: 1.0,
    environmental: 1.0,
    accessibility: 1.0,
    gap_improvement: 2.0,
    social_utility: 2.0,
  });
  await apiClient.checkFeasibility(sessionId);
  await apiClient.compareScenarios(sessionId, 'park', 'healthcare');

  // 9a. Request full_report explanation
  const explainData = await apiClient.generateExplanation(sessionId, 'full_report');
  assert.ok(explainData.narrative, 'narrative should be returned');
  const n = explainData.narrative;

  assert.equal(n.narrative_type, 'full_report');
  assert.ok(['gemini', 'groq', 'fallback', 'deterministic'].includes(n.generated_by));

  // If running in fallback mode, verify fallback_reason is populated
  if (n.generated_by === 'fallback' || n.generated_by === 'deterministic') {
    assert.ok(typeof n.fallback_reason === 'string' && n.fallback_reason.length > 0);
  }

  // Verify all 6 mandatory sections are present
  const requiredSections = [
    'overview',
    'urban_context',
    'infrastructure_gaps',
    'recommended_scenario',
    'trade_offs',
    'feasibility',
  ];
  for (const sec of requiredSections) {
    assert.ok(n.sections[sec], `Section '${sec}' must be present`);
    assert.ok(typeof n.sections[sec] === 'string' && n.sections[sec].length > 20);
  }

  // Verify numerical integrity cited in fallback (plot coordinates and parcel label)
  if (n.generated_by === 'fallback' || n.generated_by === 'deterministic') {
    assert.ok(n.sections.overview.includes('12.31') || n.sections.overview.includes('Frontend Test Parcel'));
  } else {
    assert.ok(n.sections.overview.length > 20);
  }

  // 9b. Request targeted narrative using alias explain(...)
  const scoreExplainData = await apiClient.explain(sessionId, 'score_explanation');
  assert.ok(scoreExplainData.narrative);
  assert.equal(scoreExplainData.narrative.narrative_type, 'score_explanation');
  assert.ok(scoreExplainData.narrative.sections.overview);
  assert.ok(scoreExplainData.narrative.sections.recommended_scenario);
});

test('10. Narrative Validation & Prerequisite Handling', async () => {
  // 10a. Non-existent session
  await assert.rejects(
    async () => {
      await apiClient.explain('00000000-0000-0000-0000-000000000000', 'full_report');
    },
    (err) => {
      assert.equal(err.code, 'SESSION_NOT_FOUND');
      return true;
    }
  );

  // 10b. Invalid narrative type
  const analyzeData = await apiClient.analyzePlot(MYSURU_PLOT);
  const sessionId = analyzeData.session_id;

  await assert.rejects(
    async () => {
      await apiClient.explain(sessionId, 'invalid_narrative_type');
    },
    (err) => {
      assert.equal(err.code, 'VALIDATION_ERROR');
      return true;
    }
  );

  // 10c. Calling score_explanation before simulate should be rejected with MISSING_PREREQUISITE
  await assert.rejects(
    async () => {
      await apiClient.explain(sessionId, 'score_explanation');
    },
    (err) => {
      assert.equal(err.code, 'MISSING_PREREQUISITE');
      return true;
    }
  );

  // 10d. Context summary narrative is valid immediately after analyze
  const ctxSummaryData = await apiClient.explain(sessionId, 'context_summary');
  assert.ok(ctxSummaryData.narrative);
  assert.equal(ctxSummaryData.narrative.narrative_type, 'context_summary');
  assert.ok(ctxSummaryData.narrative.sections.overview);
  assert.ok(ctxSummaryData.narrative.sections.urban_context);
});

test('11. Phase 4.3: Executive Decision Snapshot Data Model Verification', async () => {
  const analyzeData = await apiClient.analyzePlot(MYSURU_PLOT);
  const sessionId = analyzeData.session_id;

  // Simulate & rank
  const simData = await apiClient.simulateScenarios(sessionId);
  const feasData = await apiClient.checkFeasibility(sessionId);
  const rankData = await apiClient.rankScenarios(sessionId, {
    traffic: 1.0,
    cost: 1.0,
    environmental: 2.0,
    accessibility: 1.0,
    gap_improvement: 2.0,
    social_utility: 1.5,
  });

  const ranking = rankData.ranking;
  assert.ok(ranking.length >= 2, 'Ranking must have at least 2 scenarios');
  const topScenario = ranking[0];
  assert.equal(topScenario.rank, 1, 'Top scenario must be rank 1');

  // Verify Snapshot presentation values
  // 1. Location and Radius
  const wardName = analyzeData.context_summary?.ward?.ward_name;
  assert.equal(wardName, 'Devarajamohalla');
  const radiusLabel = `${(MYSURU_PLOT.radius_m / 1000).toFixed(0)} km analysis radius`;
  assert.equal(radiusLabel, '2 km analysis radius');

  // 2. Recommended policy
  assert.ok(topScenario.scenario_name);
  assert.ok(topScenario.scenario_id);

  // 3. Decision score
  const scoreStr = topScenario.weighted_score.toFixed(1);
  assert.ok(parseFloat(scoreStr) > 0 && parseFloat(scoreStr) <= 100);

  // 4. Feasibility for Rank #1
  const topVerdict = feasData.verdicts.find((v) => v.scenario_id === topScenario.scenario_id);
  assert.ok(topVerdict, 'Verdict must exist for top scenario');
  assert.equal(typeof topVerdict.feasible, 'boolean');

  // 5. Supporting insights derivation:
  // Key Opportunity from gaps
  assert.equal(analyzeData.gaps.length, 7);
  const targetCategory = topScenario.scenario_id === 'park' ? 'parks' : topScenario.scenario_id;
  const matchedGap = analyzeData.gaps.find((g) => g.category === targetCategory);
  assert.ok(matchedGap, `Gap category ${targetCategory} should exist in gaps`);

  // Key Advantage from contributions
  assert.ok(topScenario.dimension_contributions);
  const entries = Object.entries(topScenario.dimension_contributions);
  entries.sort((a, b) => b[1] - a[1]);
  assert.ok(entries.length === 6);
  const [topDim, topPts] = entries[0];
  assert.ok(topPts > 0, 'Top contribution points should be positive');

  // Primary Trade-off from raw dimension scores in score_matrix.scenario_scores
  const scMatch = simData.score_matrix.scenario_scores.find((s) => s.scenario_id === topScenario.scenario_id);
  assert.ok(scMatch, 'Score matrix scenario_scores should contain top scenario');
  assert.equal(scMatch.scores.length, 6);
  const rawDimScores = {};
  scMatch.scores.forEach((ds) => {
    rawDimScores[ds.dimension] = ds.score;
  });
  const dimScoreEntries = Object.entries(rawDimScores);
  dimScoreEntries.sort((a, b) => a[1] - b[1]);
  assert.equal(dimScoreEntries.length, 6);
  const [lowestDim, lowestScore] = dimScoreEntries[0];
  assert.ok(lowestScore >= 0 && lowestScore <= 100);

  // 6. Dynamic update when weights change
  const altWeights = {
    traffic: 10.0,
    cost: 0.1,
    environmental: 0.1,
    accessibility: 0.1,
    gap_improvement: 0.1,
    social_utility: 0.1,
  };
  const reRankData = await apiClient.rankScenarios(sessionId, altWeights);
  const reTop = reRankData.ranking[0];
  assert.ok(reTop);
  // Decision score should dynamically reflect new weights
  assert.notEqual(reTop.weighted_score, topScenario.weighted_score);
});

test('12. Phase 4.4: Recharts Decision-Support Visualizations Data Contracts', async () => {
  const analyzeData = await apiClient.analyzePlot(MYSURU_PLOT);
  const sessionId = analyzeData.session_id;

  const simData = await apiClient.simulateScenarios(sessionId);

  // Scenario Decision Ranking Chart contract verification
  // 1. Initial Balanced Weights Ranking
  const balancedWeights = {
    traffic: 1.0,
    cost: 1.0,
    environmental: 1.0,
    accessibility: 1.0,
    gap_improvement: 1.0,
    social_utility: 1.0,
  };
  const rankData = await apiClient.rankScenarios(sessionId, balancedWeights);
  const ranking = rankData.ranking;

  // Chart 1 verification:
  // - Exactly 7 scenarios rendered
  assert.equal(ranking.length, 7, 'Ranking chart must contain all 7 scenarios');
  // - Order strictly matches backend ranking
  for (let i = 0; i < ranking.length; i++) {
    assert.equal(ranking[i].rank, i + 1, `Rank should match position ${i + 1}`);
    assert.ok(ranking[i].scenario_name, 'Scenario name must be present');
    assert.ok(ranking[i].weighted_score >= 0 && ranking[i].weighted_score <= 100);
  }
  // - Rank #1 is distinct
  assert.equal(ranking[0].rank, 1);
  assert.equal(ranking[0].score_delta_from_top, 0.0);

  // Chart 2 (Why the Recommendation Wins) verification:
  // - Top two scenarios dynamically selected
  const recommended = ranking[0];
  const runnerUp = ranking[1];
  assert.notEqual(recommended.scenario_id, runnerUp.scenario_id);
  assert.equal(recommended.rank, 1);
  assert.equal(runnerUp.rank, 2);

  // - 6 dimensions extracted from score_matrix.scenario_scores
  const expectedDimensions = [
    'traffic',
    'cost',
    'environmental',
    'accessibility',
    'gap_improvement',
    'social_utility',
  ];

  const recScoreObj = simData.score_matrix.scenario_scores.find(
    (s) => s.scenario_id === recommended.scenario_id
  );
  const runScoreObj = simData.score_matrix.scenario_scores.find(
    (s) => s.scenario_id === runnerUp.scenario_id
  );

  assert.ok(recScoreObj, 'Recommended scenario must exist in simulation scores');
  assert.ok(runScoreObj, 'Runner-up scenario must exist in simulation scores');

  const recMap = {};
  recScoreObj.scores.forEach((ds) => {
    recMap[ds.dimension] = ds.score;
  });
  const runMap = {};
  runScoreObj.scores.forEach((ds) => {
    runMap[ds.dimension] = ds.score;
  });

  for (const dim of expectedDimensions) {
    assert.ok(dim in recMap, `Dimension ${dim} must exist for recommended`);
    assert.ok(dim in runMap, `Dimension ${dim} must exist for runner-up`);
    assert.ok(recMap[dim] >= 0 && recMap[dim] <= 100, `Dimension ${dim} must be 0-100`);
    assert.ok(runMap[dim] >= 0 && runMap[dim] <= 100, `Dimension ${dim} must be 0-100`);
  }

  // Dynamic ranking update test:
  // Weight change alters ranking order and dynamic chart selection
  const fiscalWeights = {
    traffic: 0.1,
    cost: 10.0,
    environmental: 0.1,
    accessibility: 0.1,
    gap_improvement: 0.1,
    social_utility: 0.1,
  };
  const fiscalRankData = await apiClient.rankScenarios(sessionId, fiscalWeights);
  const fiscalRanking = fiscalRankData.ranking;
  assert.equal(fiscalRanking.length, 7);
  // Verify order changed or scores changed
  assert.notEqual(
    fiscalRanking[0].weighted_score,
    ranking[0].weighted_score,
    'Weighted score must dynamically recalculate with new weights'
  );
  // Top 2 scenarios for Chart 2 dynamically adjust to new ranking
  const newRec = fiscalRanking[0];
  const newRun = fiscalRanking[1];
  assert.equal(newRec.rank, 1);
  assert.equal(newRun.rank, 2);
});

test('13. Phase 4.5: Municipal Decision PDF Report Generation (/api/report)', async () => {
  const analyzeData = await apiClient.analyzePlot(MYSURU_PLOT);
  const sessionId = analyzeData.session_id;

  // 1. Missing simulation prerequisite should reject with 400 (MISSING_PREREQUISITE)
  await assert.rejects(
    async () => {
      await apiClient.downloadReport(sessionId, false);
    },
    (err) => {
      return (
        err.code === 'MISSING_PREREQUISITE' ||
        (err.message && err.message.toLowerCase().includes('simulation'))
      );
    }
  );

  // 2. Simulate scenarios
  await apiClient.simulateScenarios(sessionId);

  // 3. Download report in pure deterministic mode (include_narrative = false)
  const reportDeterministic = await apiClient.downloadReport(sessionId, false);
  assert.ok(reportDeterministic, 'Deterministic report payload must be returned');

  let detBytes = 0;
  let detHeader = '';
  if (typeof reportDeterministic === 'string') {
    detBytes = reportDeterministic.length;
    detHeader = reportDeterministic.slice(0, 4);
  } else if (typeof reportDeterministic.arrayBuffer === 'function') {
    const ab = await reportDeterministic.arrayBuffer();
    detBytes = ab.byteLength;
    detHeader = Buffer.from(ab).slice(0, 4).toString('utf-8');
  } else if (Buffer.isBuffer(reportDeterministic)) {
    detBytes = reportDeterministic.length;
    detHeader = reportDeterministic.slice(0, 4).toString('utf-8');
  }

  assert.ok(detBytes > 10000, `PDF byte length (${detBytes}) must exceed 10KB`);
  assert.equal(detHeader, '%PDF', 'PDF stream must start with %PDF file signature');

  // 4. Download report with AI narrative (or automatic fallback if provider is unavailable)
  const reportWithNarrative = await apiClient.downloadReport(sessionId, true);
  assert.ok(reportWithNarrative, 'Report with narrative payload must be returned');

  let narBytes = 0;
  let narHeader = '';
  if (typeof reportWithNarrative === 'string') {
    narBytes = reportWithNarrative.length;
    narHeader = reportWithNarrative.slice(0, 4);
  } else if (typeof reportWithNarrative.arrayBuffer === 'function') {
    const ab = await reportWithNarrative.arrayBuffer();
    narBytes = ab.byteLength;
    narHeader = Buffer.from(ab).slice(0, 4).toString('utf-8');
  } else if (Buffer.isBuffer(reportWithNarrative)) {
    narBytes = reportWithNarrative.length;
    narHeader = reportWithNarrative.slice(0, 4).toString('utf-8');
  }

  assert.ok(narBytes > 10000, `PDF with narrative byte length (${narBytes}) must exceed 10KB`);
  assert.equal(narHeader, '%PDF', 'PDF with narrative must start with %PDF signature');
});



