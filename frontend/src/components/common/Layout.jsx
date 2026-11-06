import React, { useEffect, useState } from 'react';
import { Building2, MapPin, Activity, CheckCircle2, AlertTriangle, ShieldCheck, Check } from 'lucide-react';
import { apiClient } from '../../api/client';

export function Layout({
  children,
  activeStep = 1,
  onStepChange,
  steps = [
    { num: 1, title: 'Plot Selection' },
    { num: 2, title: 'Context & Gaps' },
    { num: 3, title: 'Impact Simulation' },
    { num: 4, title: 'Decision Center & Report' },
  ],
}) {
  const [healthStatus, setHealthStatus] = useState('checking'); // 'healthy', 'offline', 'checking'
  const [healthData, setHealthData] = useState(null);

  useEffect(() => {
    let mounted = true;
    apiClient
      .checkHealth()
      .then((data) => {
        if (mounted) {
          setHealthStatus('healthy');
          setHealthData(data);
        }
      })
      .catch(() => {
        if (mounted) {
          setHealthStatus('offline');
          setHealthData(null);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-slate-100 text-slate-800 antialiased selection:bg-blue-100 selection:text-blue-900">
      {/* Top Municipal Navigation Bar */}
      <header className="bg-slate-900 text-white border-b border-slate-800 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-blue-600 p-2 rounded-lg text-white shadow-xs flex items-center justify-center">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-lg font-bold tracking-tight text-white font-mono">CivicFork</span>
                <span className="text-[11px] bg-slate-800 border border-slate-700 text-slate-300 px-2 py-0.5 rounded-full font-medium">
                  Municipal Decision Support
                </span>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">
                Urban Policy Impact Simulation &amp; Decision Platform
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {/* Demo Location Badge */}
            <div className="hidden md:flex items-center space-x-1.5 bg-slate-800/90 border border-slate-700/80 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300">
              <MapPin className="w-3.5 h-3.5 text-emerald-400" />
              <span>Demo Study Area: <strong className="text-white">Mysuru, Karnataka</strong></span>
            </div>

            {/* Backend Health & Config Status Indicators */}
            <div className="flex items-center space-x-2">
              <div
                className="flex items-center space-x-1.5 bg-slate-800/90 border border-slate-700/80 px-2.5 py-1.5 rounded-lg text-xs"
                title={healthStatus === 'healthy' ? 'FastAPI decision engine is operational' : 'Backend unavailable'}
              >
                {healthStatus === 'healthy' && (
                  <>
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                    <span className="text-emerald-300 font-mono text-[11px]">Backend Ready</span>
                  </>
                )}
                {healthStatus === 'offline' && (
                  <>
                    <span className="w-2 h-2 rounded-full bg-amber-400" />
                    <span className="text-amber-300 font-mono text-[11px]">Backend Offline</span>
                  </>
                )}
                {healthStatus === 'checking' && (
                  <>
                    <span className="w-2 h-2 rounded-full bg-slate-400 animate-pulse" />
                    <span className="text-slate-400 font-mono text-[11px]">Connecting...</span>
                  </>
                )}
              </div>

              {healthData && (
                <div
                  className="hidden lg:flex items-center space-x-1.5 bg-slate-800/90 border border-slate-700/80 px-2.5 py-1.5 rounded-lg text-xs"
                  title={`OSM Data: ${healthData.osm_data_loaded ? 'Loaded' : 'Missing'} | Config: ${healthData.config_loaded ? 'Loaded' : 'Missing'}`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      healthData.osm_data_loaded ? 'bg-blue-400' : 'bg-rose-400'
                    }`}
                  />
                  <span className="text-slate-300 font-mono text-[11px]">
                    OSM Dataset Active
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Workflow Step Bar */}
      <nav aria-label="Analytical Workflow Steps" className="bg-white border-b border-slate-200 shadow-2xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2.5 overflow-x-auto">
          <div className="flex items-center justify-between min-w-[650px]">
            {steps.map((s, idx) => {
              const isCurrent = activeStep === s.num;
              const isCompleted = activeStep > s.num;
              const isClickable = s.num <= activeStep && onStepChange;

              return (
                <div key={s.num} className="flex items-center flex-1 last:flex-initial">
                  <button
                    type="button"
                    onClick={() => isClickable && onStepChange(s.num)}
                    disabled={!isClickable}
                    className={`flex items-center space-x-2 text-xs font-medium py-1.5 px-3 rounded-lg transition-all focus:outline-hidden focus:ring-2 focus:ring-blue-500/50 ${
                      isCurrent
                        ? 'bg-blue-50 text-blue-900 font-bold border border-blue-200 shadow-2xs'
                        : isCompleted
                        ? 'text-slate-700 hover:bg-slate-50 hover:text-slate-900 cursor-pointer'
                        : 'text-slate-400 cursor-not-allowed opacity-60'
                    }`}
                  >
                    <span
                      className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold transition-all ${
                        isCurrent
                          ? 'bg-blue-600 text-white shadow-xs'
                          : isCompleted
                          ? 'bg-emerald-600 text-white'
                          : 'bg-slate-200 text-slate-500'
                      }`}
                    >
                      {isCompleted ? <Check className="w-3 h-3 stroke-[3]" /> : s.num}
                    </span>
                    <span className="whitespace-nowrap">{s.title}</span>
                  </button>

                  {idx < steps.length - 1 && (
                    <div className="flex-1 mx-2 h-0.5 bg-slate-200 min-w-[20px]" />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {children}
      </main>

      {/* Municipal Footer */}
      <footer className="bg-white border-t border-slate-200 py-4 text-xs text-slate-500 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3 text-center sm:text-left">
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-blue-600 flex-shrink-0" />
            <span className="font-semibold text-slate-700">CivicFork — Municipality Urban Decision-Support Platform</span>
          </div>
          <div className="text-slate-500 text-[11px]">
            <span>Deterministic Python Simulation · AI Narrative Layer · Mysuru Study Area</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default Layout;
