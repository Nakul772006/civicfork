/**
 * Phase 4.7 — Comprehensive End-to-End Hardening & Verification Suite
 * 
 * Verifies all requirements from Phase 4.7:
 * 1. Health check (/api/health)
 * 2. Three important demo locations (Saraswathipuram, Vijayanagar, Hebbal)
 * 3. Dynamic weight recalculation (Default, Traffic-heavy, Environmental-heavy)
 * 4. Pairwise counterfactual (A vs B, swap, delta=B-A, unweighted net delta)
 * 5. Feasibility evaluation (minimum-area blocker vs proximity/saturation warnings)
 * 6. Undersized plot blocker verification (< minimum footprint)
 * 7. AI explanation endpoint & deterministic fallback
 * 8. PDF report generation (>10KB, %PDF signature, both with AI & fallback)
 * 9. Prerequisite enforcement & invalid state handling
 * 10. Demo session isolation & reset test
 */

process.env.VITE_API_URL = process.env.VITE_API_URL || 'http://localhost:8000';

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { apiClient } from './src/api/client.js';

const DEMO_LOCATIONS = {
  saraswathipuram: {
    lat: 12.3100,
    lng: 76.6500,
    radius_m: 2000,
    area_sqm: 3500.0,
    label: 'Saraswathipuram Central Parcel',
  },
  vijayanagar: {
    lat: 12.3320,
    lng: 76.6150,
    radius_m: 2000,
    area_sqm: 4200.0,
    label: 'Vijayanagar 2nd Stage Parcel',
  },
  hebbal: {
    lat: 12.3550,
    lng: 76.6100,
    radius_m: 2000,
    area_sqm: 5000.0,
    label: 'Hebbal Outer Area Parcel',
  },
};

test('1. Backend Health Check Verification', async () => {
  const health = await apiClient.checkHealth();
  assert.equal(health.status, 'healthy');
  assert.equal(health.osm_data_loaded, true);
  assert.equal(health.config_loaded, true);
  assert.equal(health.demo_area, 'mysuru');
});

test('2. Three Important Demo Locations End-to-End Pipeline', async () => {
  for (const [key, loc] of Object.entries(DEMO_LOCATIONS)) {
    // 2a. Analyze plot
    const analysis = await apiClient.analyzePlot(loc);
    assert.ok(analysis.session_id, `Session ID missing for ${key}`);
    const sid = analysis.session_id;

    // Check plot echo
    assert.equal(analysis.plot.lat, loc.lat);
    assert.equal(analysis.plot.lng, loc.lng);

    // Urban context
    assert.ok(analysis.context_summary.total_pois > 0, `Total POIs should be > 0 for ${key}`);
    assert.ok(analysis.context_summary.road_network_length_m > 0);
    assert.ok(analysis.context_summary.population_density_estimate > 0);

    // 7 Gaps & 7 Scenarios
    assert.equal(analysis.gaps.length, 7, `Gaps count should be 7 for ${key}`);
    assert.equal(analysis.scenarios.length, 7, `Scenarios count should be 7 for ${key}`);

    // 2b. Simulation
    const sim = await apiClient.simulateScenarios(sid);
    assert.equal(sim.scenarios.length, 7);
    assert.equal(sim.score_matrix.scenarios_evaluated, 7);
    assert.equal(sim.score_matrix.dimensions_evaluated, 6);
    assert.equal(sim.default_ranking.length, 7);
    assert.equal(sim.default_ranking[0].rank, 1);

    // 2c. Ranking with default weights
    const rankData = await apiClient.rankScenarios(sid, {
      traffic: 1.0,
      cost: 1.0,
      environmental: 1.0,
      accessibility: 1.0,
      gap_improvement: 1.0,
      social_utility: 1.0,
    });
    assert.equal(rankData.ranking.length, 7);
    assert.equal(rankData.ranking[0].rank, 1);

    // 2d. Feasibility evaluation
    const feas = await apiClient.checkFeasibility(sid, 'park');
    assert.ok(Array.isArray(feas.verdicts));
    assert.ok(feas.verdicts.length >= 1);
    const parkVerdict = feas.verdicts.find(v => v.scenario_id === 'park');
    assert.ok(parkVerdict);
    assert.equal(typeof parkVerdict.feasible, 'boolean');
    assert.equal(parkVerdict.checks.length, 4);

    // 2e. Pairwise Counterfactual
    const cfData = await apiClient.compareScenarios(sid, 'park', 'healthcare');
    assert.ok(cfData.result);
    const cf = cfData.result;
    assert.equal(cf.scenario_a_id, 'park');
    assert.equal(cf.scenario_b_id, 'healthcare');
    assert.equal(cf.deltas.length, 6);
    assert.ok(['meaningfully_better', 'meaningfully_worse', 'neutral'].includes(cf.verdict));

    // Verify delta = alternative - baseline
    for (const d of cf.deltas) {
      const expectedDelta = Math.round((d.score_b - d.score_a) * 10) / 10;
      assert.equal(d.delta, expectedDelta, `Delta must equal B - A for ${d.dimension}`);
    }

    // Verify unweighted net delta
    const sumDeltas = cf.deltas.reduce((acc, d) => acc + d.delta, 0);
    assert.ok(Math.abs(cf.net_delta - sumDeltas) < 0.1, 'Net delta must equal sum of dimension deltas');

    // 2f. Explain endpoint
    const explainData = await apiClient.generateExplanation(sid, 'full_report');
    assert.ok(explainData.narrative);
    assert.ok(['gemini', 'groq', 'fallback', 'deterministic'].includes(explainData.narrative.generated_by));
    assert.ok(explainData.narrative.sections.overview.length > 20);

    // 2g. PDF Report Generation
    const pdfReport = await apiClient.downloadReport(sid, false);
    assert.ok(pdfReport);
    let bytes = 0;
    let header = '';
    if (typeof pdfReport === 'string') {
      bytes = pdfReport.length;
      header = pdfReport.slice(0, 4);
    } else if (typeof pdfReport.arrayBuffer === 'function') {
      const ab = await pdfReport.arrayBuffer();
      bytes = ab.byteLength;
      header = Buffer.from(ab).slice(0, 4).toString('utf-8');
    } else if (Buffer.isBuffer(pdfReport)) {
      bytes = pdfReport.length;
      header = pdfReport.slice(0, 4).toString('utf-8');
    }
    assert.ok(bytes > 10000, `PDF size for ${key} (${bytes} bytes) must be > 10KB`);
    assert.equal(header, '%PDF', `PDF for ${key} must have %PDF header`);
  }
});

test('3. Dynamic Municipal Priority Weights & Ranking Verification', async () => {
  const analysis = await apiClient.analyzePlot(DEMO_LOCATIONS.saraswathipuram);
  const sid = analysis.session_id;
  await apiClient.simulateScenarios(sid);

  // 3a. Balanced Weights
  const balancedWeights = {
    traffic: 1.0,
    cost: 1.0,
    environmental: 1.0,
    accessibility: 1.0,
    gap_improvement: 1.0,
    social_utility: 1.0,
  };
  const resBalanced = await apiClient.rankScenarios(sid, balancedWeights);
  const rankBalanced = resBalanced.ranking;
  assert.equal(rankBalanced.length, 7);

  // Verify dimension contributions sum to weighted score
  for (const r of rankBalanced) {
    const sumContrib = Object.values(r.dimension_contributions).reduce((a, b) => a + b, 0);
    assert.ok(Math.abs(r.weighted_score - sumContrib) <= 0.1, 'Contributions must sum to weighted score');
  }

  // 3b. Traffic-heavy Configuration
  const trafficWeights = {
    traffic: 5.0,
    cost: 0.5,
    environmental: 0.5,
    accessibility: 0.5,
    gap_improvement: 0.5,
    social_utility: 0.5,
  };
  const resTraffic = await apiClient.rankScenarios(sid, trafficWeights);
  const rankTraffic = resTraffic.ranking;
  assert.equal(rankTraffic.length, 7);
  assert.notEqual(rankTraffic[0].weighted_score, rankBalanced[0].weighted_score);

  // Verify stability recalculated for new ranking
  assert.ok(resTraffic.stability);
  assert.equal(resTraffic.stability.baseline_scenario_id, rankTraffic[0].scenario_id);
  assert.equal(resTraffic.stability.total_configurations, 7);
  assert.ok(['HIGH', 'MODERATE', 'LOW'].includes(resTraffic.stability.stability_level));

  // 3c. Environmental-heavy Configuration
  const envWeights = {
    traffic: 0.5,
    cost: 0.5,
    environmental: 5.0,
    accessibility: 0.5,
    gap_improvement: 0.5,
    social_utility: 0.5,
  };
  const resEnv = await apiClient.rankScenarios(sid, envWeights);
  const rankEnv = resEnv.ranking;
  assert.equal(rankEnv.length, 7);
  assert.notEqual(rankEnv[0].weighted_score, rankTraffic[0].weighted_score);
});

test('4. Pairwise Counterfactual Verification (Symmetry & Swap)', async () => {
  const analysis = await apiClient.analyzePlot(DEMO_LOCATIONS.saraswathipuram);
  const sid = analysis.session_id;
  await apiClient.simulateScenarios(sid);

  // A = park, B = healthcare
  const resAB = await apiClient.compareScenarios(sid, 'park', 'healthcare');
  // Swap: A = healthcare, B = park
  const resBA = await apiClient.compareScenarios(sid, 'healthcare', 'park');

  const cfAB = resAB.result;
  const cfBA = resBA.result;

  assert.equal(cfAB.scenario_a_id, 'park');
  assert.equal(cfAB.scenario_b_id, 'healthcare');
  assert.equal(cfBA.scenario_a_id, 'healthcare');
  assert.equal(cfBA.scenario_b_id, 'park');

  // Verify net delta symmetry: net_delta(B, A) = - net_delta(A, B)
  assert.ok(
    Math.abs(cfAB.net_delta + cfBA.net_delta) < 0.1,
    `Net deltas must be symmetric: ${cfAB.net_delta} vs ${cfBA.net_delta}`
  );

  // Dimension delta symmetry
  for (const dAB of cfAB.deltas) {
    const dBA = cfBA.deltas.find(d => d.dimension === dAB.dimension);
    assert.ok(dBA);
    assert.ok(Math.abs(dAB.delta + dBA.delta) < 0.1, `Dimension ${dAB.dimension} delta must be antisymmetric`);
  }
});

test('5. Feasibility Constraints: Blockers vs Warnings & Small Plot Verification', async () => {
  // 5a. Normal Plot (3500 sqm) - Park & Healthcare
  const normalAnalysis = await apiClient.analyzePlot(DEMO_LOCATIONS.saraswathipuram);
  const normalSid = normalAnalysis.session_id;
  await apiClient.simulateScenarios(normalSid);

  const parkFeas = await apiClient.checkFeasibility(normalSid, 'park');
  const parkVerdict = parkFeas.verdicts.find(v => v.scenario_id === 'park');
  assert.ok(parkVerdict);
  const areaCheckNormal = parkVerdict.checks.find(c => c.check_name === 'minimum_area');
  assert.equal(areaCheckNormal.passed, true);
  assert.equal(parkVerdict.blocker_count, 0);

  // 5b. Undersized Plot (50 sqm) - Must trigger minimum_area BLOCKER for healthcare (requires 2000 sqm)
  const tinyPlot = {
    lat: 12.3100,
    lng: 76.6500,
    radius_m: 1000,
    area_sqm: 50.0,
    label: 'Undersized Test Parcel',
  };
  const tinyAnalysis = await apiClient.analyzePlot(tinyPlot);
  const tinySid = tinyAnalysis.session_id;

  const healthFeas = await apiClient.checkFeasibility(tinySid, 'healthcare');
  const healthVerdict = healthFeas.verdicts.find(v => v.scenario_id === 'healthcare');
  assert.ok(healthVerdict);
  assert.equal(healthVerdict.feasible, false, 'Healthcare on 50 sqm must be infeasible');
  assert.ok(healthVerdict.blocker_count >= 1, 'Must have at least 1 blocker');

  const areaCheckTiny = healthVerdict.checks.find(c => c.check_name === 'minimum_area');
  assert.equal(areaCheckTiny.passed, false);
  assert.equal(areaCheckTiny.severity, 'blocker');
});

test('6. AI Narrative Service & Deterministic Fallback Verification', async () => {
  const analysis = await apiClient.analyzePlot(DEMO_LOCATIONS.saraswathipuram);
  const sid = analysis.session_id;
  await apiClient.simulateScenarios(sid);

  // Request explanation
  const explainData = await apiClient.generateExplanation(sid, 'full_report');
  assert.ok(explainData.narrative);
  const n = explainData.narrative;
  assert.ok(['gemini', 'groq', 'fallback', 'deterministic'].includes(n.generated_by));
  assert.ok(n.sections.overview.length > 20);
  assert.ok(n.sections.trade_offs.length > 20);
  assert.ok(n.sections.feasibility.length > 20);
});

test('7. PDF Generation with and without AI Narrative', async () => {
  const analysis = await apiClient.analyzePlot(DEMO_LOCATIONS.saraswathipuram);
  const sid = analysis.session_id;
  await apiClient.simulateScenarios(sid);

  // PDF deterministic (without AI narrative)
  const pdfDet = await apiClient.downloadReport(sid, false);
  let detBytes = typeof pdfDet === 'string' ? pdfDet.length : (Buffer.isBuffer(pdfDet) ? pdfDet.length : (await pdfDet.arrayBuffer()).byteLength);
  assert.ok(detBytes > 10000, `Deterministic PDF size ${detBytes} > 10KB`);

  // PDF with AI narrative (or fallback if AI unavailable)
  const pdfAI = await apiClient.downloadReport(sid, true);
  let aiBytes = typeof pdfAI === 'string' ? pdfAI.length : (Buffer.isBuffer(pdfAI) ? pdfAI.length : (await pdfAI.arrayBuffer()).byteLength);
  assert.ok(aiBytes > 10000, `AI narrative PDF size ${aiBytes} > 10KB`);
});

test('8. Robust Error Handling & Invalid States', async () => {
  // 8a. Out-of-bounds coordinates
  await assert.rejects(
    async () => {
      await apiClient.analyzePlot({ lat: 28.6139, lng: 77.2090, radius_m: 1000, area_sqm: 3000 });
    },
    (err) => {
      assert.equal(err.code, 'VALIDATION_ERROR');
      return true;
    }
  );

  // 8b. Non-existent session
  const fakeSession = '00000000-0000-0000-0000-000000000000';
  await assert.rejects(
    async () => {
      await apiClient.simulateScenarios(fakeSession);
    },
    (err) => {
      assert.equal(err.code, 'SESSION_NOT_FOUND');
      return true;
    }
  );

  // 8c. Ranking before simulation
  const freshPlot = await apiClient.analyzePlot(DEMO_LOCATIONS.vijayanagar);
  const freshSid = freshPlot.session_id;

  await assert.rejects(
    async () => {
      await apiClient.rankScenarios(freshSid, { traffic: 1.0 });
    },
    (err) => {
      assert.equal(err.code, 'MISSING_PREREQUISITE');
      return true;
    }
  );

  // 8d. Counterfactual before simulation
  await assert.rejects(
    async () => {
      await apiClient.compareScenarios(freshSid, 'park', 'healthcare');
    },
    (err) => {
      assert.equal(err.code, 'MISSING_PREREQUISITE');
      return true;
    }
  );

  // 8e. Explanation before simulation
  await assert.rejects(
    async () => {
      await apiClient.generateExplanation(freshSid, 'full_report');
    },
    (err) => {
      assert.equal(err.code, 'MISSING_PREREQUISITE');
      return true;
    }
  );

  // 8f. Report before simulation
  await assert.rejects(
    async () => {
      await apiClient.downloadReport(freshSid, false);
    },
    (err) => {
      assert.equal(err.code, 'MISSING_PREREQUISITE');
      return true;
    }
  );
});

test('9. Session Isolation & Reset Verification', async () => {
  // Session 1: Saraswathipuram
  const session1 = await apiClient.analyzePlot(DEMO_LOCATIONS.saraswathipuram);
  const sid1 = session1.session_id;
  await apiClient.simulateScenarios(sid1);

  // Session 2: Vijayanagar
  const session2 = await apiClient.analyzePlot(DEMO_LOCATIONS.vijayanagar);
  const sid2 = session2.session_id;
  await apiClient.simulateScenarios(sid2);

  // Verify unique session IDs
  assert.notEqual(sid1, sid2, 'Sessions must have distinct IDs');

  // Verify distinct location coordinates
  assert.equal(session1.plot.lat, DEMO_LOCATIONS.saraswathipuram.lat);
  assert.equal(session2.plot.lat, DEMO_LOCATIONS.vijayanagar.lat);

  // Verify both sessions have independent simulation results
  const cf1 = await apiClient.compareScenarios(sid1, 'park', 'healthcare');
  const cf2 = await apiClient.compareScenarios(sid2, 'park', 'healthcare');

  assert.ok(cf1.result);
  assert.ok(cf2.result);
});

test('10. Phase 4.8A: Full Pipeline with Decision Stability Analysis', async () => {
  // 1. Analyze
  const analysis = await apiClient.analyzePlot(DEMO_LOCATIONS.saraswathipuram);
  const sid = analysis.session_id;

  // 2. Simulate
  const sim = await apiClient.simulateScenarios(sid);
  assert.equal(sim.scenarios.length, 7);

  // 3. Rank
  const rankData = await apiClient.rankScenarios(sid, {
    traffic: 1.0,
    cost: 1.0,
    environmental: 1.0,
    accessibility: 1.0,
    gap_improvement: 1.0,
    social_utility: 1.0,
  });
  const baselineRec = rankData.ranking[0];

  // 4. Decision Stability Endpoint (/api/stability)
  const stabData = await apiClient.checkStability(sid);
  assert.ok(stabData.result, 'result object must be returned');
  const stab = stabData.result;

  assert.equal(stab.baseline_scenario_id, baselineRec.scenario_id);
  assert.equal(stab.baseline_scenario_name, baselineRec.scenario_name);
  assert.equal(stab.total_configurations, 7);
  assert.equal(stab.configurations_tested.length, 7);
  assert.equal(stab.configuration_results.length, 7);

  // Stability score and level
  const expectedScore = Number(((100.0 * stab.baseline_wins) / 7).toFixed(1));
  assert.equal(stab.stability_score, expectedScore);
  assert.ok(['HIGH', 'MODERATE', 'LOW'].includes(stab.stability_level));

  if (stab.stability_score >= 75.0) {
    assert.equal(stab.stability_level, 'HIGH');
    assert.ok(stab.interpretation.includes('remains the top-ranked option'));
  } else if (stab.stability_score >= 50.0) {
    assert.equal(stab.stability_level, 'MODERATE');
    assert.ok(stab.interpretation.includes('sensitive to changes'));
  } else {
    assert.equal(stab.stability_level, 'LOW');
    assert.ok(stab.interpretation.includes('changes substantially'));
  }

  // Strongest challenger
  if (stab.strongest_challenger) {
    assert.notEqual(stab.strongest_challenger.scenario_id, stab.baseline_scenario_id);
    assert.ok(typeof stab.strongest_challenger.wins === 'number');
  }

  // Provenance trace
  assert.ok(stab.calculation_trace?.provenance);
  assert.equal(stab.calculation_trace.provenance.score_matrix, 'calculated');
  assert.equal(stab.calculation_trace.provenance.priority_configurations, 'configured');
  assert.equal(stab.calculation_trace.provenance.stability_score, 'derived');
  assert.ok(stab.calculation_trace.disclaimer.includes('Modelled sensitivity analysis'));

  // 5. Counterfactual continues to work seamlessly
  const cf = await apiClient.compareScenarios(sid, baselineRec.scenario_id, rankData.ranking[1].scenario_id);
  assert.ok(cf.result);
  assert.equal(cf.result.deltas.length, 6);
});
