import React from 'react';
import { VerdictBadge } from './VerdictBadge';
import { VerificationResult } from '../types/falsify';
import { Info, Gauge, Calendar, Hash, ShieldCheck } from 'lucide-react';

interface Props {
  result: VerificationResult;
}

export const VerdictCard: React.FC<Props> = ({ result }) => {
  const confidencePercent = Math.round(result.confidence * 100);
  const bd = result.confidence_breakdown;

  // Breakdown factor bars
  const factors = [
    { label: 'Retrieval Coverage', value: bd?.retrieval_coverage ?? 0 },
    { label: 'Evidence Quality', value: bd?.evidence_quality ?? 0 },
    { label: 'Evidence Relevance', value: bd?.evidence_relevance ?? 0 },
    { label: 'Source Independence', value: bd?.source_independence ?? 0 },
    { label: 'Cross-Source Agreement', value: bd?.cross_source_agreement ?? 0 },
    { label: 'Contradiction Strength', value: bd?.contradiction_strength ?? 0 },
    { label: 'Temporal Validity', value: bd?.temporal_validity ?? 0 },
  ];

  return (
    <div className="glass-panel rounded-2xl p-6 sm:p-7 mb-8 shadow-2xl relative overflow-hidden font-sans transition-all duration-300">
      {/* Top Banner: Verdict & Metrics */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-white/[0.08]">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="text-[11px] font-display font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
              Verification Determination
            </span>
            {result.id && (
              <span className="inline-flex items-center gap-1 text-[11px] text-cyan-300 bg-cyan-950/70 border border-cyan-500/30 px-2 py-0.5 rounded-full font-mono font-bold">
                <Hash className="w-3 h-3 text-cyan-400" />
                <span>#{result.id}</span>
              </span>
            )}
          </div>
          <div className="mt-3 flex items-center gap-3 flex-wrap">
            <VerdictBadge verdict={result.verdict} size="lg" />
            <div className="flex items-center gap-2.5 px-3.5 py-1.5 bg-slate-900/80 border border-white/10 rounded-xl text-cyan-300 text-sm shadow-md backdrop-blur-md">
              <Gauge className="w-4 h-4 text-cyan-400" />
              <span className="font-mono font-bold text-white text-base">{confidencePercent}%</span>
              <span className="text-xs text-slate-400 font-sans">Decisive Confidence</span>
            </div>
          </div>
        </div>

        {/* Timestamp & Metadata */}
        <div className="text-right sm:text-right text-xs text-slate-400 flex sm:flex-col items-center sm:items-end justify-between sm:justify-center gap-1.5">
          {result.created_at && (
            <div className="flex items-center gap-1.5 text-slate-300 font-mono text-[11px]">
              <Calendar className="w-3.5 h-3.5 text-cyan-400" />
              <span>{new Date(result.created_at).toLocaleString()}</span>
            </div>
          )}
          <div className="text-[11px] font-mono text-slate-500">
            Engine v{result.engine_version || '1.0.0'} • {result.retrieval_provider || 'in_memory'}
          </div>
        </div>
      </div>

      {/* Verified Claim Quote */}
      <div className="py-4 border-b border-white/[0.08]">
        <div className="text-[10px] font-display font-bold text-slate-400 uppercase tracking-widest mb-1.5">
          Submitted Claim Statement
        </div>
        <p className="text-base sm:text-lg font-sans font-medium text-slate-100 leading-relaxed italic">
          "{result.claim_text || result.claim?.original_text}"
        </p>
        {result.claim?.normalized_text && result.claim.normalized_text !== result.claim_text && (
          <p className="text-xs text-slate-400 mt-2 font-sans">
            <span className="font-semibold text-cyan-400">Normalized Assertion:</span>{' '}
            <span className="text-slate-300">{result.claim.normalized_text}</span>
          </p>
        )}
      </div>

      {/* Synthesis & Explanation */}
      <div className="py-4 border-b border-white/[0.08]">
        <div className="flex items-center gap-1.5 text-[11px] font-display font-bold text-slate-400 uppercase tracking-widest mb-2.5">
          <Info className="w-3.5 h-3.5 text-cyan-400" />
          <span>Synthesis & Determination Rationale</span>
        </div>
        <p className="text-xs sm:text-sm text-slate-200 leading-relaxed whitespace-pre-line font-sans font-normal">
          {result.reasoning_trace?.reasoning || result.confidence_explanation || 'No reasoning trace provided.'}
        </p>
        {result.confidence_explanation && result.confidence_explanation !== result.reasoning_trace?.reasoning && (
          <div className="mt-3.5 p-3.5 rounded-xl bg-cyan-950/30 border border-cyan-500/30 text-xs text-cyan-200 font-sans leading-relaxed">
            <span className="font-bold text-cyan-400">Confidence Factor Detail:</span> {result.confidence_explanation}
          </div>
        )}
      </div>

      {/* Confidence Factor Breakdown */}
      {bd && (
        <div className="pt-4">
          <div className="text-[11px] font-display font-bold text-slate-400 uppercase tracking-widest mb-3.5">
            Multi-Factor Confidence Weights
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {factors.map((f, i) => {
              const valPct = Math.round(f.value * 100);
              return (
                <div key={i} className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] hover:border-cyan-500/30 transition-colors">
                  <div className="flex justify-between items-center text-xs text-slate-300 mb-2">
                    <span className="truncate pr-1 font-sans text-xs">{f.label}</span>
                    <span className="font-mono font-bold text-cyan-300 text-xs">{valPct}%</span>
                  </div>
                  <div className="w-full bg-black/40 rounded-full h-1.5 overflow-hidden border border-white/5">
                    <div
                      className="bg-gradient-to-r from-cyan-500 to-emerald-400 h-full rounded-full transition-all duration-300"
                      style={{ width: `${Math.max(valPct, 4)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
