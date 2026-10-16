import React from 'react';
import { AlertOctagon, GitMerge } from 'lucide-react';
import { Contradiction, FusionSummary, ContradictionTraceEntry, Severity } from '../types/falsify';

interface Props {
  contradictions: Contradiction[] | ContradictionTraceEntry[];
  fusion?: FusionSummary | null;
}

export const ContradictionsPanel: React.FC<Props> = ({ contradictions, fusion }) => {
  const getSeverityBadge = (severity?: Severity | string) => {
    switch (severity?.toLowerCase()) {
      case 'critical':
        return (
          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-rose-950/80 text-rose-300 border border-rose-600 shadow-[0_0_8px_rgba(244,63,94,0.3)]">
            CRITICAL SEVERITY
          </span>
        );
      case 'high':
        return (
          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-rose-950/70 text-rose-300 border border-rose-700">
            HIGH SEVERITY
          </span>
        );
      case 'medium':
        return (
          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-950/70 text-amber-300 border border-amber-600">
            MEDIUM SEVERITY
          </span>
        );
      default:
        return (
          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-900 text-slate-400 border border-slate-700">
            LOW SEVERITY
          </span>
        );
    }
  };

  return (
    <div className="bg-[#0a0e17] rounded-xl border border-[#1b2538] shadow-[0_0_25px_rgba(0,0,0,0.7)] p-6 mb-8 font-mono">
      {/* Contradictions Section */}
      <div className="pb-6 border-b border-[#162033]">
        <div className="flex items-center gap-2 mb-3">
          <AlertOctagon className="w-5 h-5 text-rose-400 animate-pulse" />
          <h3 className="text-sm sm:text-base font-bold text-white tracking-wide">
            Detected Factual Contradictions ({contradictions.length})
          </h3>
        </div>

        {contradictions.length === 0 ? (
          <div className="p-3.5 rounded-lg bg-emerald-950/40 border border-emerald-800/60 text-xs text-emerald-300 flex items-center gap-2">
            <span>No factual contradictions or numeric discrepancies were detected between the claim and the evidence.</span>
          </div>
        ) : (
          <div className="space-y-3">
            {contradictions.map((c, idx) => {
              const type = 'contradiction_type' in c ? c.contradiction_type : c.type;
              const evidenceUrls = 'evidence_urls' in c ? c.evidence_urls : [];

              return (
                <div
                  key={c.contradiction_id || idx}
                  className="p-4 rounded-xl bg-[#190912] border border-rose-900/60 space-y-2 shadow-[0_0_12px_rgba(244,63,94,0.15)]"
                >
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] font-bold px-2 py-0.5 rounded bg-[#2b0c1b] text-rose-300 border border-rose-700 uppercase">
                        {type}
                      </span>
                      {getSeverityBadge(c.severity)}
                    </div>
                  </div>

                  <p className="text-xs text-slate-200 font-semibold leading-relaxed">
                    {('explanation' in c ? c.explanation : '') || (c as any).description || ''}
                  </p>

                  {evidenceUrls.length > 0 && (
                    <div className="pt-2 border-t border-rose-950">
                      <div className="text-[10px] font-bold text-slate-400 mb-1">
                        Contradictory Source URLs:
                      </div>
                      <div className="space-y-1">
                        {evidenceUrls.map((url, uidx) => (
                          <div key={uidx} className="text-[11px] text-cyan-400 truncate">
                            <a href={url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                              {url}
                            </a>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Fusion & Independence Summary */}
      {fusion && (
        <div className="pt-6">
          <div className="flex items-center gap-2 mb-3">
            <GitMerge className="w-4 h-4 text-cyan-400" />
            <h4 className="text-xs sm:text-sm font-bold text-white tracking-wide">
              Evidence Fusion & Source Independence
            </h4>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 rounded-xl bg-[#080d16] border border-[#162033]">
              <span className="text-[10px] text-slate-500 block uppercase font-bold">Supporting Clusters</span>
              <span className="text-sm sm:text-base font-bold text-emerald-400">
                {fusion.independent_supporting_clusters} independent
              </span>
              <span className="text-[10px] text-slate-500 block mt-0.5">
                ({fusion.supporting_evidence} total sources)
              </span>
            </div>

            <div className="p-3 rounded-xl bg-[#080d16] border border-[#162033]">
              <span className="text-[10px] text-slate-500 block uppercase font-bold">Contradicting Clusters</span>
              <span className="text-sm sm:text-base font-bold text-rose-400">
                {fusion.independent_contradicting_clusters} independent
              </span>
              <span className="text-[10px] text-slate-500 block mt-0.5">
                ({fusion.contradicting_evidence} total sources)
              </span>
            </div>

            <div className="p-3 rounded-xl bg-[#080d16] border border-[#162033]">
              <span className="text-[10px] text-slate-500 block uppercase font-bold">Support Quality</span>
              <span className="text-sm sm:text-base font-bold text-cyan-300">
                {Math.round(fusion.max_support_quality * 100)}% peak
              </span>
              <span className="text-[10px] text-slate-500 block mt-0.5">
                Strength: {fusion.support_strength.toFixed(2)}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-[#080d16] border border-[#162033]">
              <span className="text-[10px] text-slate-500 block uppercase font-bold">Echo Suppression</span>
              <span className="text-sm sm:text-base font-bold text-amber-400">
                {fusion.duplicated_evidence_detected} duplicates
              </span>
              <span className="text-[10px] text-slate-500 block mt-0.5">
                {Math.round(fusion.coverage * 100)}% coverage
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
