import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Circle, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { MapPin, Navigation, Compass, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

// Custom DOM Marker icon to eliminate asset loading issues in bundler
const customMarkerIcon = L.divIcon({
  className: 'custom-map-pin',
  html: `
    <div style="position: relative; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">
      <div style="position: absolute; width: 32px; height: 32px; border-radius: 50%; background-color: rgba(37, 99, 235, 0.25); animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>
      <div style="width: 20px; height: 20px; border-radius: 50%; background-color: #2563eb; border: 3px solid #ffffff; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3); display: flex; align-items: center; justify-content: center;">
        <div style="width: 6px; height: 6px; border-radius: 50%; background-color: #ffffff;"></div>
      </div>
    </div>
  `,
  iconSize: [32, 32],
  iconAnchor: [16, 16],
});

// Mysuru boundary constants matching backend models
const MYSURU_CENTER = [12.3100, 76.6500];
const MYSURU_BOUNDS = {
  latMin: 12.20,
  latMax: 12.42,
  lngMin: 76.55,
  lngMax: 76.75,
};

// Preset demo locations across Mysuru
const PRESETS = [
  { name: 'Palace / Central', lat: 12.3051, lng: 76.6551 },
  { name: 'Vijayanagar', lat: 12.3320, lng: 76.6150 },
  { name: 'Kuvempunagar', lat: 12.2850, lng: 76.6350 },
  { name: 'Hebbal / KRS Road', lat: 12.3550, lng: 76.6100 },
];

function MapClickHandler({ onSelect }) {
  useMapEvents({
    click(e) {
      const lat = Number(e.latlng.lat.toFixed(4));
      const lng = Number(e.latlng.lng.toFixed(4));
      onSelect(lat, lng);
    },
  });
  return null;
}

function PanToLocation({ center }) {
  const map = useMap();
  useEffect(() => {
    if (center && center[0] && center[1]) {
      map.setView(center, map.getZoom());
    }
  }, [center, map]);
  return null;
}

export function PlotMap({
  selectedPlot,
  onPlotChange,
  onAnalyze,
  loading = false,
}) {
  const [lat, setLat] = useState(selectedPlot?.lat || 12.3100);
  const [lng, setLng] = useState(selectedPlot?.lng || 76.6500);
  const [radiusM, setRadiusM] = useState(selectedPlot?.radius_m || 2000);
  const [areaSqm, setAreaSqm] = useState(selectedPlot?.area_sqm || 3500);
  const [label, setLabel] = useState(selectedPlot?.label || 'Mysuru Development Plot');

  // Sync internal state when parent selectedPlot changes
  useEffect(() => {
    if (selectedPlot) {
      if (selectedPlot.lat) setLat(selectedPlot.lat);
      if (selectedPlot.lng) setLng(selectedPlot.lng);
      if (selectedPlot.radius_m) setRadiusM(selectedPlot.radius_m);
      if (selectedPlot.area_sqm) setAreaSqm(selectedPlot.area_sqm);
      if (selectedPlot.label) setLabel(selectedPlot.label);
    }
  }, [selectedPlot]);

  const handleMapClick = (newLat, newLng) => {
    setLat(newLat);
    setLng(newLng);
    if (onPlotChange) {
      onPlotChange({
        lat: newLat,
        lng: newLng,
        radius_m: radiusM,
        area_sqm: areaSqm,
        label,
      });
    }
  };

  const handlePresetClick = (preset) => {
    setLat(preset.lat);
    setLng(preset.lng);
    if (onPlotChange) {
      onPlotChange({
        lat: preset.lat,
        lng: preset.lng,
        radius_m: radiusM,
        area_sqm: areaSqm,
        label: `${preset.name} Parcel`,
      });
    }
  };

  const isWithinBounds =
    lat >= MYSURU_BOUNDS.latMin &&
    lat <= MYSURU_BOUNDS.latMax &&
    lng >= MYSURU_BOUNDS.lngMin &&
    lng <= MYSURU_BOUNDS.lngMax;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!isWithinBounds || loading) return;
    onAnalyze({
      lat: Number(lat),
      lng: Number(lng),
      radius_m: Number(radiusM),
      area_sqm: Number(areaSqm),
      label,
    });
  };

  return (
    <div className="bg-white rounded-xl shadow-xs border border-slate-200 overflow-hidden mb-6">
      {/* Map Control Bar */}
      <div className="p-4 border-b border-slate-200 bg-slate-50/80 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2 text-blue-600">
            <Compass className="w-4 h-4" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900">
              Stage 1: Plot Selection &amp; Spatial Scoping
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Select an urban parcel within Mysuru study boundaries or choose a municipal landmark preset.
          </p>
        </div>

        {/* Quick Presets */}
        <div className="flex items-center flex-wrap gap-1.5">
          <span className="text-xs text-slate-500 mr-1 font-medium">Presets:</span>
          {PRESETS.map((p) => {
            const isActive = Math.abs(lat - p.lat) < 0.001 && Math.abs(lng - p.lng) < 0.001;
            return (
              <button
                key={p.name}
                type="button"
                onClick={() => handlePresetClick(p)}
                className={`text-xs px-2.5 py-1 rounded-md border font-medium transition-all cursor-pointer ${
                  isActive
                    ? 'bg-blue-600 text-white border-blue-600 shadow-xs'
                    : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-100'
                }`}
              >
                {p.name}
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-0">
        {/* Map Canvas (2 cols) */}
        <div className="lg:col-span-2 h-[480px] relative">
          <MapContainer
            center={[lat, lng]}
            zoom={13}
            scrollWheelZoom={true}
            className="w-full h-full z-0"
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <PanToLocation center={[lat, lng]} />
            <MapClickHandler onSelect={handleMapClick} />

            <Marker position={[lat, lng]} icon={customMarkerIcon} />
            <Circle
              center={[lat, lng]}
              radius={radiusM}
              pathOptions={{
                color: '#2563eb',
                fillColor: '#3b82f6',
                fillOpacity: 0.12,
                weight: 2,
                dashArray: '4, 4',
              }}
            />
          </MapContainer>

          {/* Data Lineage & Context Notice */}
          <div className="absolute top-3 right-3 z-[1000] bg-white/95 backdrop-blur-xs border border-slate-200 shadow-xs rounded-lg px-2.5 py-1.5 text-[11px] text-slate-600 flex items-center space-x-1.5 max-w-xs pointer-events-none">
            <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0"></span>
            <span>OSM base map tiles provide geographical reference; impact scoring runs against curated Mysuru GeoJSON.</span>
          </div>

          {/* Coordinates Overlay Pill */}
          <div className="absolute bottom-3 left-3 z-[1000] bg-slate-900/90 text-white backdrop-blur-xs border border-slate-800 shadow-md rounded-lg px-3 py-1.5 text-xs font-mono flex items-center space-x-2">
            <Navigation className="w-3.5 h-3.5 text-blue-400" />
            <span>
              Lat: <strong className="text-white">{lat.toFixed(4)}</strong>, Lng: <strong className="text-white">{lng.toFixed(4)}</strong>
            </span>
            <span className="text-slate-600">|</span>
            <span>Radius: <strong className="text-white">{radiusM}m</strong></span>
          </div>
        </div>

        {/* Plot Parameters & Analysis Trigger (1 col) */}
        <div className="p-5 flex flex-col justify-between border-t lg:border-t-0 lg:border-l border-slate-200 bg-white">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1">
                Plot Identification Label
              </label>
              <input
                type="text"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="e.g. Kuvempunagar Redevelopment"
                className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:border-blue-500 shadow-2xs"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Latitude
                </label>
                <input
                  type="number"
                  step="0.0001"
                  value={lat}
                  onChange={(e) => setLat(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 text-xs font-mono border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 shadow-2xs"
                />
              </div>
              <div>
                <label className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Longitude
                </label>
                <input
                  type="number"
                  step="0.0001"
                  value={lng}
                  onChange={(e) => setLng(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 text-xs font-mono border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 shadow-2xs"
                />
              </div>
            </div>

            {!isWithinBounds && (
              <div className="flex items-start space-x-2 text-rose-700 bg-rose-50 border border-rose-200 p-2.5 rounded-lg text-xs">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-rose-600" />
                <span>
                  Coordinates outside Mysuru bounding box ({MYSURU_BOUNDS.latMin}-{MYSURU_BOUNDS.latMax} N, {MYSURU_BOUNDS.lngMin}-{MYSURU_BOUNDS.lngMax} E).
                </span>
              </div>
            )}

            <div>
              <label className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1">
                Analysis Scoping Radius
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[1000, 2000, 5000].map((r) => {
                  const isActive = radiusM === r;
                  return (
                    <button
                      key={r}
                      type="button"
                      onClick={() => setRadiusM(r)}
                      className={`py-2 px-2 text-xs font-semibold rounded-lg border text-center transition-all cursor-pointer ${
                        isActive
                          ? 'bg-blue-600 text-white border-blue-600 shadow-xs'
                          : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
                      }`}
                    >
                      {r >= 1000 ? `${r / 1000} km` : `${r} m`}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1">
                Parcel Area (m²)
              </label>
              <input
                type="number"
                min="500"
                max="50000"
                step="100"
                value={areaSqm}
                onChange={(e) => setAreaSqm(parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-2 text-xs font-mono border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 shadow-2xs"
              />
              <span className="text-[11px] text-slate-500 mt-1 block">
                Standard municipal plot range: 500 – 50,000 m²
              </span>
            </div>

            <button
              type="submit"
              disabled={loading || !isWithinBounds}
              className={`w-full py-2.5 px-4 rounded-lg text-xs font-bold text-white shadow-xs flex items-center justify-center space-x-2 transition-all cursor-pointer ${
                loading || !isWithinBounds
                  ? 'bg-slate-400 cursor-not-allowed opacity-75'
                  : 'bg-blue-600 hover:bg-blue-700 active:scale-[0.99]'
              }`}
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Analyzing Urban Context...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Analyze Plot Location</span>
                </>
              )}
            </button>
          </form>

          <div className="text-[11px] text-slate-400 mt-4 border-t border-slate-100 pt-3 flex items-center justify-between font-mono">
            <span>OSM Dataset: 93 POIs, 38 Roads</span>
            <span className="text-emerald-700 font-semibold bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
              Active
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PlotMap;
