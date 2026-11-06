/**
 * CivicFork display and formatting utilities.
 */

export function formatScore(score) {
  if (score === null || score === undefined || isNaN(score)) return '—';
  return Number(score).toFixed(1);
}

export function formatDistance(meters) {
  if (meters === null || meters === undefined || isNaN(meters)) return '—';
  if (meters >= 1000) {
    return `${(meters / 1000).toFixed(2)} km`;
  }
  return `${Math.round(meters)} m`;
}

export function formatArea(sqm) {
  if (sqm === null || sqm === undefined || isNaN(sqm)) return '—';
  return `${Number(sqm).toLocaleString()} m²`;
}

export function formatINR(amount) {
  if (amount === null || amount === undefined || isNaN(amount)) return '—';
  if (amount >= 10000000) {
    return `₹${(amount / 10000000).toFixed(2)} Cr`;
  }
  if (amount >= 100000) {
    return `₹${(amount / 100000).toFixed(2)} L`;
  }
  return `₹${Number(amount).toLocaleString('en-IN')}`;
}

export function getScoreColor(score) {
  if (score === null || score === undefined || isNaN(score)) return 'text-slate-400 bg-slate-100';
  if (score >= 75) return 'text-emerald-700 bg-emerald-50 border-emerald-200';
  if (score >= 50) return 'text-blue-700 bg-blue-50 border-blue-200';
  if (score >= 35) return 'text-amber-700 bg-amber-50 border-amber-200';
  return 'text-rose-700 bg-rose-50 border-rose-200';
}
