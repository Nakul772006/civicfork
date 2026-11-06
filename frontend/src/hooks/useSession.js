/**
 * Session state management hook for CivicFork.
 */

import { useState, useCallback } from 'react';

const INITIAL_STATE = {
  sessionId: null,
  plot: null,
  contextSummary: null,
  gaps: [],
  scenarios: [],
  scoreMatrix: null,
  ranking: [],
  weightsApplied: null,
  verdicts: [],
  counterfactual: null,
  stability: null,
  narratives: {},
  geojson: {
    pois: null,
    landuse: null,
    transport: null,
  },
};

export function useSession() {
  const [session, setSession] = useState(INITIAL_STATE);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeStep, setActiveStep] = useState(1);

  const resetSession = useCallback(() => {
    setSession(INITIAL_STATE);
    setError(null);
    setActiveStep(1);
  }, []);

  const updateSession = useCallback((updates) => {
    setSession((prev) => ({ ...prev, ...updates }));
  }, []);

  return {
    session,
    loading,
    error,
    activeStep,
    setLoading,
    setError,
    setActiveStep,
    updateSession,
    resetSession,
  };
}

export default useSession;
