import React from 'react';
import { AlertCircle, X } from 'lucide-react';

export function ErrorBanner({ error, onDismiss }) {
  if (!error) return null;

  const message = typeof error === 'string' ? error : error.message || 'An unexpected error occurred';
  const code = typeof error === 'object' ? error.code : null;

  return (
    <div className="bg-rose-50 border border-rose-300 text-rose-900 px-4 py-3 rounded-xl flex items-start justify-between shadow-xs my-4" role="alert">
      <div className="flex items-start space-x-3">
        <AlertCircle className="w-5 h-5 text-rose-600 mt-0.5 flex-shrink-0" />
        <div>
          <div className="flex items-center space-x-2">
            <span className="font-bold text-xs uppercase tracking-wider text-rose-950">System Notice</span>
            {code && (
              <span className="text-[11px] bg-rose-200/80 text-rose-900 font-mono px-1.5 py-0.2 rounded font-semibold border border-rose-300">
                {code}
              </span>
            )}
          </div>
          <p className="text-xs text-rose-800 mt-1 leading-relaxed">{message}</p>
        </div>
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="text-rose-500 hover:text-rose-800 transition-colors p-1 rounded-md hover:bg-rose-100 cursor-pointer"
          aria-label="Dismiss error notice"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}

export default ErrorBanner;
