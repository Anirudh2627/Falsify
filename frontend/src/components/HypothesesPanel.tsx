import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Search, CheckCircle, XCircle, AlertCircle, HelpCircle, Flame } from 'lucide-react';
import { FalsificationHypothesis, SearchQuery, HypothesisTraceEntry, QueryTraceEntry } from '../types/falsify';

interface Props {
  hypotheses: FalsificationHypothesis[] | HypothesisTraceEntry[];
  queries: SearchQuery[] | QueryTraceEntry[];
}

export const HypothesesPanel: React.FC<Props> = ({ hypotheses, queries }) => {
  const [isExpanded, setIsExpanded] = useState(true);

  const getOutcomeBadge = (outcome?: string) => {
    switch (outcome?.toLowerCase()) {
      case 'falsified':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-wider bg-rose-950/70 text-rose-300 border border-rose-600/70 shadow-[0_0_8px_rgba(244,63,94,0.3)]">
            <XCircle className="w-3 h-3 text-rose-400" />
            FALSIFIED
          </span>
        );
      case 'challenged':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-wider bg-amber-950/70 text-amber-300 border border-amber-600/70">
            <AlertCircle className="w-3 h-3 text-amber-400" />
            Challenged
          </span>
        );
      case 'survived':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-wider bg-emerald-950/70 text-emerald-300 border border-emerald-600/70 shadow-[0_0_8px_rgba(16,185,129,0.3)]">
            <CheckCircle className="w-3 h-3 text-emerald-400" />
            Survived
          </span>
        );
      case 'no_evidence':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-wider bg-slate-900 text-slate-400 border border-slate-700">
            <HelpCircle className="w-3 h-3 text-slate-500" />
            No Evidence
          </span>
        );
      default:
        return (
          <span className="text-[10px] px-2 py-0.5 rounded font-bold uppercase bg-slate-900 text-slate-400 border border-slate-700">
            {outcome || 'Evaluated'}
          </span>
        );
    }
  };

  return (
    <div className="bg-[#0a0e17] rounded-xl border border-[#1b2538] shadow-[0_0_25px_rgba(0,0,0,0.7)] p-6 mb-8 font-mono">
      <div
        className="flex items-center justify-between cursor-pointer select-none"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-purple-950/80 border border-purple-500/40 text-purple-400 flex items-center justify-center shadow-[0_0_10px_rgba(168,85,247,0.3)]">
            <Flame className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm sm:text-base font-bold text-white tracking-wide">
              Falsification Hypotheses & Adversarial Queries ({hypotheses.length})
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Specific falsification angles formulated to challenge the claim.
            </p>
          </div>
        </div>
        <button type="button" className="text-slate-400 hover:text-white p-1">
          {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
        </button>
      </div>

      {isExpanded && (
        <div className="mt-5 space-y-4">
          {/* Hypotheses List */}
          <div className="space-y-3">
            {hypotheses.map((h: any, idx: number) => {
              const category = h.category || 'General Falsification';
              const priority = h.priority !== undefined ? h.priority : idx + 1;
              const outcome = h.outcome;

              return (
                <div
                  key={h.hypothesis_id || idx}
                  className="p-4 rounded-xl border border-[#1b2538] bg-[#070b13] hover:border-purple-500/40 transition-all shadow-sm"
                >
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] px-2 py-0.5 rounded bg-purple-950/80 text-purple-300 border border-purple-800/60 font-bold uppercase tracking-wider">
                        {category}
                      </span>
                      <span className="text-[10px] text-slate-500 font-bold">Priority #{priority}</span>
                    </div>
                    {outcome && getOutcomeBadge(outcome)}
                  </div>

                  <p className="text-xs sm:text-sm font-semibold text-slate-200">
                    "{h.hypothesis}"
                  </p>

                  {h.rationale && (
                    <p className="mt-1.5 text-xs text-slate-400">
                      <span className="font-bold text-slate-500">Rationale:</span> {h.rationale}
                    </p>
                  )}

                  {h.falsification_target && (
                    <p className="mt-1 text-xs text-cyan-400">
                      <span className="font-bold text-slate-500">Target:</span> {h.falsification_target}
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          {/* Generated Queries List */}
          {queries && queries.length > 0 && (
            <div className="mt-5 pt-4 border-t border-[#162033]">
              <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-1.5">
                <Search className="w-3.5 h-3.5 text-cyan-400" />
                <span>Search Queries Dispatched to Providers</span>
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {queries.map((q: any, idx: number) => (
                  <div
                    key={q.query_id || idx}
                    className="p-2.5 rounded-lg border border-[#162033] bg-[#0c121e] text-xs font-mono"
                  >
                    <div className="text-cyan-300 font-semibold truncate">"{q.query}"</div>
                    <div className="text-[10px] text-slate-500 mt-1 flex items-center justify-between">
                      <span className="uppercase text-purple-400">{q.query_type || 'adversarial'}</span>
                      {q.results_found !== undefined && (
                        <span>{q.results_found} results</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
