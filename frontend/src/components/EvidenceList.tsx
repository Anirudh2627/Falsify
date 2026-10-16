import React, { useState } from 'react';
import { ExternalLink, CheckCircle2, XCircle, MinusCircle, ShieldAlert, Shield } from 'lucide-react';
import { Evidence, EvidenceAssessment, SourceTier } from '../types/falsify';

interface Props {
  evidenceList: Evidence[];
  assessments?: EvidenceAssessment[];
}

export const EvidenceList: React.FC<Props> = ({ evidenceList, assessments = [] }) => {
  const [filterStance, setFilterStance] = useState<string>('all');

  // Match assessments to evidence by evidence_id
  const assessmentMap = new Map<string, EvidenceAssessment>();
  for (const a of assessments) {
    assessmentMap.set(a.evidence_id, a);
  }

  const items = evidenceList.map((ev) => ({
    evidence: ev,
    assessment: assessmentMap.get(ev.evidence_id),
  }));

  const filteredItems = items.filter(({ assessment }) => {
    if (filterStance === 'all') return true;
    if (!assessment) return filterStance === 'neutral';
    return assessment.stance === filterStance;
  });

  const getTierLabel = (tier?: SourceTier) => {
    switch (tier) {
      case 1:
        return { label: 'Tier 1 Primary / Regulatory', color: 'bg-emerald-950/70 text-emerald-300 border-emerald-600/70 shadow-[0_0_8px_rgba(16,185,129,0.3)]' };
      case 2:
        return { label: 'Tier 2 Reputable Secondary', color: 'bg-blue-950/70 text-blue-300 border-blue-600/70' };
      case 3:
        return { label: 'Tier 3 Unverified / Blog', color: 'bg-slate-900/80 text-slate-400 border-slate-700' };
      default:
        return { label: 'Unclassified Tier', color: 'bg-slate-900/80 text-slate-400 border-slate-700' };
    }
  };

  const getStanceBadge = (stance?: string) => {
    switch (stance) {
      case 'supporting':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full font-bold bg-emerald-950/70 text-emerald-300 border border-emerald-600/70">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            Supports Claim
          </span>
        );
      case 'contradicting':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full font-bold bg-rose-950/70 text-rose-300 border border-rose-600/70">
            <XCircle className="w-3 h-3 text-rose-400" />
            Contradicts Claim
          </span>
        );
      case 'mixed':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full font-bold bg-amber-950/70 text-amber-300 border border-amber-600/70">
            <ShieldAlert className="w-3 h-3 text-amber-400" />
            Mixed Evidence
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full font-bold bg-slate-900 text-slate-400 border border-slate-700">
            <MinusCircle className="w-3 h-3 text-slate-500" />
            Neutral
          </span>
        );
    }
  };

  return (
    <div className="bg-[#0a0e17] rounded-xl border border-[#1b2538] shadow-[0_0_25px_rgba(0,0,0,0.7)] p-6 mb-8 font-mono">
      {/* Header and Filter Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#162033]">
        <div>
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm sm:text-base font-bold text-white tracking-wide">
              Retrieved Evidence Corroboration ({evidenceList.length})
            </h3>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Evaluated for source tiering, stance, relevance, and factual directness.
          </p>
        </div>

        {/* Filter buttons */}
        <div className="flex items-center gap-1 bg-[#0c121e] p-1 rounded-lg text-xs border border-[#1b2538] self-start sm:self-auto">
          {['all', 'supporting', 'contradicting', 'neutral'].map((stance) => (
            <button
              key={stance}
              type="button"
              onClick={() => setFilterStance(stance)}
              className={`px-2.5 py-1 rounded-md font-semibold capitalize transition-all ${
                filterStance === stance
                  ? 'bg-cyan-950/80 text-cyan-300 border border-cyan-700/60 shadow-[0_0_8px_rgba(6,182,212,0.3)]'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {stance}
            </button>
          ))}
        </div>
      </div>

      {/* Cards List */}
      <div className="mt-4 space-y-4">
        {filteredItems.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-500 italic">
            No evidence items matching the '{filterStance}' filter.
          </div>
        ) : (
          filteredItems.map(({ evidence, assessment }, idx) => {
            const tierInfo = getTierLabel(assessment?.source_tier);
            const passages = evidence.relevant_passages && evidence.relevant_passages.length > 0
              ? evidence.relevant_passages
              : evidence.retrieved_text
              ? [evidence.retrieved_text]
              : (evidence as any).snippet
              ? [(evidence as any).snippet]
              : [];

            const sourceUrl = evidence.source_url || (evidence as any).url || '#';
            const qual = assessment ? ((assessment as any).source_quality_score ?? (assessment as any).quality_score) : null;
            const rel = assessment ? assessment.relevance_score : null;

            return (
              <div
                key={evidence.evidence_id || idx}
                className="p-4 rounded-xl border border-[#1b2538] bg-[#070b13] hover:border-cyan-500/40 transition-all shadow-sm group"
              >
                {/* Source Metadata & Badges */}
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    {getStanceBadge(assessment?.stance)}
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded border font-bold uppercase tracking-wider ${tierInfo.color}`}
                    >
                      {tierInfo.label}
                    </span>
                    {assessment?.is_direct && (
                      <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-950/70 text-cyan-300 border border-cyan-800/60 font-bold uppercase tracking-wider">
                        Direct Evidence
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2 text-xs text-slate-400">
                    {assessment && (
                      <>
                        {rel !== null && rel !== undefined && (
                          <span>Rel: <strong className="text-cyan-300">{Math.round(rel * 100)}%</strong></span>
                        )}
                        {rel !== null && qual !== null && (
                          <span className="text-slate-600">•</span>
                        )}
                        {qual !== null && qual !== undefined && (
                          <span>Qual: <strong className="text-emerald-300">{Math.round(qual * 100)}%</strong></span>
                        )}
                      </>
                    )}
                  </div>
                </div>

                {/* Title & Link */}
                <h4 className="text-sm font-bold text-slate-100">
                  <a
                    href={sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:text-cyan-300 inline-flex items-center gap-1.5 transition-colors"
                  >
                    <span>{evidence.title || sourceUrl}</span>
                    <ExternalLink className="w-3.5 h-3.5 shrink-0 text-slate-500 group-hover:text-cyan-400" />
                  </a>
                </h4>

                <div className="text-xs text-slate-400 mt-1 flex items-center gap-2">
                  <span className="text-cyan-400/90">{evidence.publisher || evidence.domain}</span>
                  {evidence.publication_date && (
                    <>
                      <span className="text-slate-600">•</span>
                      <span>{evidence.publication_date}</span>
                    </>
                  )}
                </div>

                {/* Relevant Passages / Excerpts */}
                {passages.length > 0 && (
                  <div className="mt-3 p-3 rounded-lg bg-[#0c1322] border-l-2 border-l-cyan-400 border-r border-t border-b border-[#1b2538] text-xs text-slate-200 leading-relaxed italic">
                    "{passages[0]}"
                  </div>
                )}

                {/* Assessment Reasoning */}
                {assessment?.reasoning && (
                  <p className="mt-2 text-xs text-slate-400">
                    <span className="font-bold text-slate-300">Assessment:</span> {assessment.reasoning}
                  </p>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
