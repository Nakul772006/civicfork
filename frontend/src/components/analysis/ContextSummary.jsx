import React from 'react';
import { 
  Building, 
  Trees, 
  Store, 
  Factory, 
  Bus, 
  Milestone, 
  Users, 
  MapPin, 
  Info,
  CheckCircle2,
  Waves
} from 'lucide-react';
import { formatDistance } from '../../utils/formatters';

export function ContextSummary({ contextSummary, plot }) {
  if (!contextSummary) return null;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 mb-5 gap-2">
        <div>
          <div className="flex items-center space-x-2 text-blue-600">
            <MapPin className="w-4 h-4" />
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800">
              Urban Context &amp; Spatial Baseline
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Surrounding infrastructure and environmental indicators within {plot?.radius_m || 2000}m radius.
          </p>
        </div>

        <div className="flex items-center flex-wrap gap-2">
          <span className="text-[11px] font-mono bg-emerald-50 text-emerald-800 border border-emerald-300 px-2 py-0.5 rounded-full flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            <span>[observed] OSM Features</span>
          </span>
          <span className="text-[11px] font-mono bg-blue-50 text-blue-800 border border-blue-300 px-2 py-0.5 rounded-full flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
            <span>[calculated] Distances</span>
          </span>
          <span className="text-[11px] font-mono bg-purple-50 text-purple-800 border border-purple-300 px-2 py-0.5 rounded-full flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-500"></span>
            <span>[modelled] Densities</span>
          </span>
        </div>
      </div>

      {/* Ward Administrative Context */}
      {contextSummary.ward ? (
        <div className="mb-5 p-3 bg-blue-50/70 border border-blue-200 rounded-lg flex flex-col sm:flex-row sm:items-center justify-between text-xs text-blue-900 gap-2">
          <div className="flex items-center space-x-2">
            <span className="font-semibold px-2 py-0.5 bg-blue-600 text-white rounded text-[11px] font-mono">
              MCC Ward {contextSummary.ward.ward_id}
            </span>
            <span className="font-bold text-slate-800 text-sm">
              {contextSummary.ward.ward_name}
            </span>
          </div>
          <div className="flex items-center flex-wrap gap-3 text-slate-600 text-[11px]">
            {contextSummary.ward.area_sq_km != null && (
              <span>Area: <strong>{contextSummary.ward.area_sq_km} km²</strong></span>
            )}
            {contextSummary.ward.population != null && (
              <span>
                Census {contextSummary.ward.population_year || 2011} Pop: <strong>{contextSummary.ward.population.toLocaleString()}</strong>
                {contextSummary.ward.population_density_per_sq_km != null && (
                  <span className="text-slate-400 ml-1">({Math.round(contextSummary.ward.population_density_per_sq_km).toLocaleString()} / km²)</span>
                )}
              </span>
            )}
            <span className="font-mono text-[10px] text-blue-700 bg-blue-100/80 px-1.5 py-0.5 rounded">
              [supplied] Ward Context
            </span>
          </div>
        </div>
      ) : (
        <div className="mb-5 p-2.5 bg-slate-50 border border-dashed border-slate-200 rounded-lg flex items-center justify-between text-xs text-slate-500">
          <span>Location outside covered MCC 65-ward corporation boundary dataset</span>
          <span className="font-mono text-[10px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
            [contextual]
          </span>
        </div>
      )}

      {/* Environmental / Water-body Proximity Context */}
      {contextSummary.nearest_water_body_name && (
        <div className="mb-5 p-3 bg-cyan-50/70 border border-cyan-200 rounded-lg flex flex-col sm:flex-row sm:items-center justify-between text-xs text-cyan-950 gap-2">
          <div className="flex items-center space-x-2">
            <span className="font-semibold px-2 py-0.5 bg-cyan-700 text-white rounded text-[11px] font-mono flex items-center space-x-1">
              <Waves className="w-3 h-3 inline mr-1" />
              <span>Water-body Proximity Context</span>
            </span>
            <span className="font-bold text-slate-800 text-sm">
              {contextSummary.nearest_water_body_name}
            </span>
          </div>
          <div className="flex items-center flex-wrap gap-3 text-slate-600 text-[11px]">
            {contextSummary.nearest_water_body_m != null && (
              <span>
                Distance: <strong>{formatDistance(contextSummary.nearest_water_body_m)}</strong>
              </span>
            )}
            <span>
              Within {plot?.radius_m || 2000}m: <strong>{contextSummary.water_body_count}</strong> mapped
            </span>
            {contextSummary.water_body_area_within_radius_sqm > 0 && (
              <span>
                Overlap Area: <strong>{Math.round(contextSummary.water_body_area_within_radius_sqm).toLocaleString()} m²</strong>
              </span>
            )}
            <span className="font-mono text-[10px] text-cyan-800 bg-cyan-100/80 px-1.5 py-0.5 rounded">
              [supplied] OSM Natural Water
            </span>
          </div>
        </div>
      )}

      {/* Primary Context Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        {/* Total POIs */}
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <div className="flex items-center justify-between text-slate-500 mb-1">
            <span className="text-[11px] font-semibold uppercase">Total POIs</span>
            <Building className="w-3.5 h-3.5 text-blue-600" />
          </div>
          <div className="text-xl font-bold text-slate-900">{contextSummary.total_pois}</div>
          <span className="text-[10px] text-emerald-700 font-mono">[observed]</span>
        </div>

        {/* Dominant Land Use */}
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <div className="flex items-center justify-between text-slate-500 mb-1">
            <span className="text-[11px] font-semibold uppercase">Dominant Zone</span>
            <Store className="w-3.5 h-3.5 text-indigo-600" />
          </div>
          <div className="text-sm font-bold text-slate-900 truncate capitalize">
            {contextSummary.dominant_landuse || 'Mixed'}
          </div>
          <span className="text-[10px] text-emerald-700 font-mono">[observed]</span>
        </div>

        {/* Transit Stops */}
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <div className="flex items-center justify-between text-slate-500 mb-1">
            <span className="text-[11px] font-semibold uppercase">Transit Stops</span>
            <Bus className="w-3.5 h-3.5 text-cyan-600" />
          </div>
          <div className="text-xl font-bold text-slate-900">{contextSummary.transit_stop_count}</div>
          <span className="text-[10px] text-slate-500">
            {contextSummary.nearest_transit_m != null ? `Nearest ${formatDistance(contextSummary.nearest_transit_m)}` : 'None in radius'}
          </span>
        </div>

        {/* Road Network */}
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <div className="flex items-center justify-between text-slate-500 mb-1">
            <span className="text-[11px] font-semibold uppercase">Major Roads</span>
            <Milestone className="w-3.5 h-3.5 text-amber-600" />
          </div>
          <div className="text-xl font-bold text-slate-900">{contextSummary.major_road_count}</div>
          <span className="text-[10px] text-slate-500">
            {contextSummary.nearest_major_road_m != null ? `Nearest ${formatDistance(contextSummary.nearest_major_road_m)}` : 'Local only'}
          </span>
        </div>

        {/* Modelled Population Density */}
        <div className="bg-purple-50/50 border border-purple-200 rounded-lg p-3">
          <div className="flex items-center justify-between text-purple-700 mb-1">
            <span className="text-[11px] font-semibold uppercase">Est. Pop Density</span>
            <Users className="w-3.5 h-3.5 text-purple-600" />
          </div>
          <div className="text-xl font-bold text-purple-900">
            {Math.round(contextSummary.population_density_estimate).toLocaleString()}
          </div>
          <span className="text-[10px] text-purple-700 font-mono">[modelled estimate] / km²</span>
        </div>

        {/* Modelled Building Density */}
        <div className="bg-purple-50/50 border border-purple-200 rounded-lg p-3">
          <div className="flex items-center justify-between text-purple-700 mb-1">
            <span className="text-[11px] font-semibold uppercase">Est. Buildings</span>
            <Building className="w-3.5 h-3.5 text-purple-600" />
          </div>
          <div className="text-xl font-bold text-purple-900">
            {Math.round(contextSummary.building_density_estimate).toLocaleString()}
          </div>
          <span className="text-[10px] text-purple-700 font-mono">[modelled estimate] / km²</span>
        </div>
      </div>

      {/* Provenance Disclosure Note */}
      <div className="mb-6 p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-[11px] text-slate-500 flex items-center justify-between flex-wrap gap-2">
        <span className="flex items-center space-x-1.5">
          <Info className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
          <span><strong>Provenance:</strong> <code className="text-emerald-700 bg-emerald-50 px-1 py-0.5 rounded font-mono">[observed]</code> direct from OpenStreetMap; <code className="text-blue-700 bg-blue-50 px-1 py-0.5 rounded font-mono">[calculated]</code> GIS network lengths; <code className="text-purple-700 bg-purple-50 px-1 py-0.5 rounded font-mono">[modelled]</code> spatial regression approximations.</span>
        </span>
      </div>

      {/* Land Use & Street Composition Bar */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-50 p-4 rounded-lg border border-slate-200">
        <div>
          <span className="text-xs font-semibold text-slate-700 block mb-2">
            Land-Use Composition Breakdown
          </span>
          <div className="space-y-2">
            <div>
              <div className="flex justify-between text-xs text-slate-600 mb-1">
                <span className="flex items-center space-x-1.5">
                  <Trees className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Green &amp; Open Space</span>
                </span>
                <span className="font-semibold">{contextSummary.green_space_pct.toFixed(1)}%</span>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-emerald-500 h-1.5 rounded-full"
                  style={{ width: `${Math.min(100, Math.max(0, contextSummary.green_space_pct))}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs text-slate-600 mb-1">
                <span className="flex items-center space-x-1.5">
                  <Store className="w-3.5 h-3.5 text-purple-600" />
                  <span>Commercial Zoning</span>
                </span>
                <span className="font-semibold">{contextSummary.commercial_pct.toFixed(1)}%</span>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-purple-500 h-1.5 rounded-full"
                  style={{ width: `${Math.min(100, Math.max(0, contextSummary.commercial_pct))}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs text-slate-600 mb-1">
                <span className="flex items-center space-x-1.5">
                  <Factory className="w-3.5 h-3.5 text-amber-600" />
                  <span>Industrial / Utility</span>
                </span>
                <span className="font-semibold">{contextSummary.industrial_pct.toFixed(1)}%</span>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-amber-500 h-1.5 rounded-full"
                  style={{ width: `${Math.min(100, Math.max(0, contextSummary.industrial_pct))}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        <div>
          <span className="text-xs font-semibold text-slate-700 block mb-2">
            Street Network Connectivity
          </span>
          <div className="space-y-2 text-xs text-slate-600">
            <div className="flex justify-between py-1 border-b border-slate-200">
              <span>Total Road Network Length:</span>
              <span className="font-semibold text-slate-900">
                {formatDistance(contextSummary.road_network_length_m)}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-200">
              <span>Road Density:</span>
              <span className="font-semibold text-slate-900">
                {Math.round(contextSummary.road_density_m_per_sqkm).toLocaleString()} m / km²
              </span>
            </div>
            <div className="flex justify-between py-1">
              <span>Nearest Transit Distance:</span>
              <span className="font-semibold text-slate-900">
                {contextSummary.nearest_transit_m != null
                  ? formatDistance(contextSummary.nearest_transit_m)
                  : 'N/A'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ContextSummary;
