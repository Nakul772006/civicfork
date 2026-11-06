import React from 'react';
import { Loader2 } from 'lucide-react';

export function LoadingSpinner({ message = 'Computing deterministic simulation...', size = 'md' }) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
  };

  return (
    <div className="flex flex-col items-center justify-center p-6 text-slate-600 space-y-2.5" role="status" aria-live="polite">
      <Loader2 className={`${sizeClasses[size] || sizeClasses.md} animate-spin text-blue-600`} />
      {message && <p className="text-xs font-semibold text-slate-700 font-mono tracking-tight">{message}</p>}
    </div>
  );
}

export default LoadingSpinner;
