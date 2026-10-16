import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Code, Clock, Terminal } from 'lucide-react';
import { ReasoningTrace, VerificationResult } from '../types/falsify';

interface Props {
  trace?: ReasoningTrace;
  fullResult: VerificationResult;
}

export const ReasoningTraceView: React.FC<Props> = ({ trace, fullResult }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [showRawJson, setShowRawJson] = useState(false);

  const timings = trace?.stage_timings_ms || {};

  return (
    <div className="bg-[#0a0e17] rounded-xl border border-[#1b2538] shadow-[0_0_25px_rgba(0,0,0,0.7)] p-6 mb-8 font-mono">
      <div
        className="flex items-center justify-between cursor-pointer select-none"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-amber-950/80 border border-amber-500/40 text-amber-400 flex items-center justify-center shadow-[0_0_10px_rgba(245,158,11,0.3)]">
            <Terminal className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm sm:text-base font-bold text-white tracking-wide">
              Audit & Reasoning Trace
            </h3>
            <p className="text-xs text-slate-400">
              Detailed stage execution latency and full structured JSON data contract.
            </p>
          </div>
        </div>

        <button
          type="button"
          aria-expanded={isOpen}
          className="text-slate-400 hover:text-white p-1"
        >
          {isOpen ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
        </button>
      </div>

      {isOpen && (
        <div className="mt-5 space-y-5 pt-4 border-t border-[#162033]">
          {/* Stage Timings */}
          {Object.keys(timings).length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">
                <Clock className="w-3.5 h-3.5 text-cyan-400" />
                <span>Pipeline Stage Latency (ms)</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(timings).map(([stage, ms]) => (
                  <div
                    key={stage}
                    className="px-2.5 py-1.5 rounded-lg bg-[#080d16] border border-[#162033] text-xs flex items-center gap-2"
                  >
                    <span className="font-mono text-cyan-400 capitalize">{stage}</span>
                    <span className="font-mono font-bold text-slate-200">{ms}ms</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Raw JSON Toggle */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-1.5">
                <Code className="w-3.5 h-3.5 text-cyan-400" />
                <span>Structured Output JSON</span>
              </span>
              <button
                type="button"
                onClick={() => setShowRawJson(!showRawJson)}
                className="text-xs text-cyan-400 hover:text-cyan-300 font-bold"
              >
                {showRawJson ? 'Hide Full JSON Output' : 'Show Full JSON Output'}
              </button>
            </div>

            {showRawJson && (
              <pre className="p-4 rounded-xl bg-[#060910] border border-[#1b2538] text-[11px] font-mono text-cyan-200/90 overflow-x-auto max-h-96 selection:bg-cyan-500/30">
                {JSON.stringify(fullResult, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
