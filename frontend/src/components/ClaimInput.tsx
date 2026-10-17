import React, { useState } from 'react';
import { Search, Loader2, XCircle, Sparkles, AlertCircle } from 'lucide-react';

interface Props {
  onVerify: (claim: string) => void;
  onCancelStream?: () => void;
  isStreaming: boolean;
  errorMessage?: string | null;
}

const SAMPLE_PRESETS = [
  {
    label: 'Corporate Revenue Claim',
    claim: 'Company X grew revenue by 40% in 2025.',
    note: 'Tests numerical and temporal constraints against SEC filings & news.',
  },
  {
    label: 'Comparative Landmark Claim',
    claim: 'The Eiffel Tower is taller than the Statue of Liberty.',
    note: 'Tests comparative dimensional facts.',
  },
  {
    label: 'Global EV Market Claim',
    claim: 'Global electric vehicle sales exceeded 14 million units in 2023.',
    note: 'Tests statistical metrics and global automotive aggregations.',
  },
];

export const ClaimInput: React.FC<Props> = ({
  onVerify,
  onCancelStream,
  isStreaming,
  errorMessage,
}) => {
  const [claimText, setClaimText] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);

  const charCount = claimText.length;
  const isTooLong = charCount > 4000;

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (isStreaming) return;

    const trimmed = claimText.trim();
    if (!trimmed) {
      setValidationError('Claim cannot be empty or whitespace only.');
      return;
    }
    if (isTooLong) {
      setValidationError(`Claim exceeds the 4,000-character limit (${charCount} chars).`);
      return;
    }

    setValidationError(null);
    onVerify(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSelectPreset = (presetClaim: string) => {
    if (isStreaming) return;
    setClaimText(presetClaim);
    setValidationError(null);
  };

  return (
    <div className="surface-card rounded-2xl p-5 sm:p-6 mb-6 relative overflow-hidden transition-all duration-300 font-sans">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-base sm:text-lg font-semibold text-white tracking-tight flex items-center gap-2 font-sans">
              <span className="w-2 h-2 rounded-full bg-indigo-500" />
              Adversarial Claim Verification
            </h2>
            <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-indigo-950/60 text-indigo-300 border border-indigo-500/30 font-medium tracking-normal font-sans">
              POPPERIAN ENGINE
            </span>
          </div>
          <p className="text-xs text-slate-300 mt-1.5 leading-relaxed font-sans">
            Formulates rigorous falsification hypotheses, executes targeted adversarial queries across authoritative sources,
            detects numerical & semantic contradictions, and calculates a decisive confidence breakdown.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} noValidate>
        <div className="relative">
          <label htmlFor="claim-input" className="sr-only">
            Claim statement to verify
          </label>
          <textarea
            id="claim-input"
            rows={3}
            value={claimText}
            onChange={(e) => {
              setClaimText(e.target.value);
              if (validationError) setValidationError(null);
            }}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
            placeholder="Enter an assertive claim to verify (e.g. 'Company X reported 40% revenue growth in fiscal 2025')..."
            className={`w-full rounded-xl border p-4 text-sm font-sans text-slate-100 placeholder:text-slate-500 bg-slate-950/70 focus:outline-none transition-all duration-200 leading-relaxed ${
              isTooLong || validationError
                ? 'border-rose-500 focus:ring-1 focus:ring-rose-500 bg-rose-950/20'
                : 'border-slate-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 shadow-inner'
            } ${isStreaming ? 'opacity-70 cursor-not-allowed' : ''}`}
          />

          {/* Character Counter & Validation */}
          <div className="flex justify-between items-center mt-2 px-1">
            <div>
              {validationError && (
                <span className="text-xs text-rose-400 font-sans font-medium flex items-center gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  {validationError}
                </span>
              )}
            </div>
            <span
              className={`text-[11px] font-mono ${
                isTooLong ? 'text-rose-400 font-bold' : 'text-slate-400'
              }`}
            >
              {charCount.toLocaleString()} / 4,000 characters
            </span>
          </div>
        </div>

        {/* Action Controls */}
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <button
              type="submit"
              disabled={isStreaming || isTooLong}
              className={`inline-flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-semibold tracking-normal transition-all duration-200 shadow-sm ${
                isStreaming || isTooLong
                  ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-white/5'
                  : 'bg-indigo-600 hover:bg-indigo-500 text-white active:scale-95'
              }`}
            >
              {isStreaming ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-white" />
                  <span>Verifying Claim...</span>
                </>
              ) : (
                <>
                  <Search className="w-4 h-4 text-white" />
                  <span>Verify Claim</span>
                </>
              )}
            </button>

            {isStreaming && onCancelStream && (
              <button
                type="button"
                onClick={onCancelStream}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-sans font-medium text-slate-400 hover:text-rose-300 hover:bg-rose-950/40 border border-slate-800 hover:border-rose-500/30 transition-all duration-200"
                title="Disconnects from the live stream. Backend verification continues in background."
              >
                <XCircle className="w-4 h-4 text-rose-400" />
                <span>Cancel Stream</span>
              </button>
            )}
          </div>

          <div className="text-[11px] font-sans text-slate-400 hidden sm:flex items-center gap-1.5">
            <span>Press</span>
            <kbd className="px-1.5 py-0.5 rounded bg-slate-800/80 border border-slate-700 text-slate-300 font-mono text-[10px]">
              Ctrl + Enter
            </kbd>
            <span>to execute</span>
          </div>
        </div>
      </form>

      {/* Backend / Global Error Banner */}
      {errorMessage && (
        <div className="mt-4 p-3.5 rounded-xl bg-rose-950/40 border border-rose-500/40 text-rose-300 text-xs font-sans flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0 text-rose-400" />
          <div>
            <p className="font-semibold text-rose-400 text-xs">
              Verification Error
            </p>
            <p className="mt-0.5 text-rose-200">{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Preset Demonstrations */}
      <div className="mt-5 pt-4 border-t border-slate-800/80">
        <div className="flex items-center gap-2 text-xs font-medium text-slate-400 mb-2.5">
          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
          <span>Curated Benchmarks for Demonstration:</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
          {SAMPLE_PRESETS.map((p, idx) => (
            <button
              key={idx}
              type="button"
              disabled={isStreaming}
              onClick={() => handleSelectPreset(p.claim)}
              className="text-left p-3 rounded-xl border border-slate-800 hover:border-indigo-500/40 bg-slate-900/40 hover:bg-slate-900/80 transition-all duration-200 group disabled:opacity-50"
            >
              <div className="text-xs font-sans font-semibold text-slate-200 group-hover:text-indigo-200 transition-colors">
                {p.label}
              </div>
              <div className="text-[11px] font-sans text-slate-400 mt-1 line-clamp-1 italic group-hover:text-slate-300">
                "{p.claim}"
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
