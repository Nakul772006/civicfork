/**
 * CivicFork API Client.
 * Connects frontend to the FastAPI backend endpoints.
 */

import axios from 'axios';

const getBaseUrl = () => {
  if (typeof process !== 'undefined' && process.env?.VITE_API_URL) {
    return process.env.VITE_API_URL;
  }
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  return '';
};

const api = axios.create({
  baseURL: getBaseUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Response interceptor to unwrap { success, data, error }
api.interceptors.response.use(
  (response) => {
    // If response is a blob (e.g. PDF), return directly
    if (response.config.responseType === 'blob') {
      return response.data;
    }
    const { data } = response;
    if (data && data.success === false) {
      return Promise.reject(data.error || { message: 'Request failed' });
    }
    return data && data.data !== undefined ? data.data : data;
  },
  async (error) => {
    if (error.response && error.response.data) {
      let errorData = error.response.data;
      if (typeof errorData === 'string') {
        try {
          errorData = JSON.parse(errorData);
        } catch {
          // keep as string
        }
      } else if (typeof Blob !== 'undefined' && errorData instanceof Blob) {
        try {
          const text = await errorData.text();
          errorData = JSON.parse(text);
        } catch {
          // keep as blob
        }
      } else if (typeof Buffer !== 'undefined' && Buffer.isBuffer(errorData)) {
        try {
          errorData = JSON.parse(errorData.toString('utf-8'));
        } catch {
          // keep as buffer
        }
      }

      if (errorData && errorData.error) {
        return Promise.reject(errorData.error);
      }
    }
    return Promise.reject({
      code: 'NETWORK_ERROR',
      message: error.message || 'Unable to connect to CivicFork backend',
    });
  }
);

export const apiClient = {
  // System Health
  checkHealth: () => api.get('/api/health'),

  // 1. Analyze Plot Location
  analyzePlot: (payload) => api.post('/api/analyze', payload),

  // 2. Simulate 7 Scenarios
  simulateScenarios: (sessionId) => api.post('/api/simulate', { session_id: sessionId }),

  // 3. Apply Priority Weights & Rank
  rankScenarios: (sessionId, weights) => api.post('/api/rank', { session_id: sessionId, weights }),

  // 4. Feasibility Check
  checkFeasibility: (sessionId, scenarioId = null) => {
    const payload = { session_id: sessionId };
    if (scenarioId) {
      payload.scenario_id = scenarioId;
    }
    return api.post('/api/feasibility', payload);
  },

  // 5. Counterfactual Comparison (A vs B)
  compareCounterfactual: (sessionId, scenarioAId, scenarioBId) =>
    api.post('/api/counterfactual', {
      session_id: sessionId,
      scenario_a_id: scenarioAId,
      scenario_b_id: scenarioBId,
    }),
  compareScenarios: (sessionId, scenarioAId, scenarioBId) =>
    api.post('/api/counterfactual', {
      session_id: sessionId,
      scenario_a_id: scenarioAId,
      scenario_b_id: scenarioBId,
    }),

  // 5b. Decision Stability / Sensitivity Analysis
  getStability: (sessionId) =>
    api.post('/api/stability', {
      session_id: sessionId,
    }),
  checkStability: (sessionId) =>
    api.post('/api/stability', {
      session_id: sessionId,
    }),

  // 6. Generate AI Narrative Explanation
  generateExplanation: (sessionId, narrativeType = 'full_report') =>
    api.post('/api/explain', {
      session_id: sessionId,
      narrative_type: narrativeType,
    }),
  explain: (sessionId, narrativeType = 'full_report') =>
    api.post('/api/explain', {
      session_id: sessionId,
      narrative_type: narrativeType,
    }),

  // 7. Download PDF Report
  downloadReport: (sessionId, includeNarrative = true) =>
    api.post(
      '/api/report',
      { session_id: sessionId, include_narrative: includeNarrative },
      { responseType: 'blob' }
    ),
};

export default apiClient;
