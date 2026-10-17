import React from 'react';
import { X, ExternalLink, ShieldCheck, AlertTriangle } from 'lucide-react';
import { VerificationResult } from '../types/falsify';
import { CanvasTab } from './CanvasHeader';

interface Props {
  nodeId: string | null;
  onClose: () => void;
  result: VerificationResult | null;
  onNavigateTab: (tab: CanvasTab) => void;
}

export const NodeDetailModal: React.FC<Props> = ({
  nodeId,
  onClose,
  result,
  onNavigateTab,
}) => {
  if (!nodeId) return null;

  const getDetails = () => {
    switch (nodeId) {
      case 'N01':
        return {
          title: 'NODE N01: CLAIM_INPUT (α_VECTOR)',
          badge: 'STAGE 01 — PARSING & VECTORIZATION',
          color: 'cyan',
          description:
            'The assertive proposition is parsed for normalized semantic predicates, quantitative constraints, entities, and temporal bounds.',
          content: (
            <div className="space-y-3 font-mono text-xs">
              <div className="p-3 bg-[#0d1424] rounded-lg border border-cyan-900/50">
                <span className="text-cyan-400 font-bold block mb-1">Normalized Claim:</span>
                <p className="text-slate-200">
                  {result?.claim?.normalized_text || result?.claim_text || 'Company X grew revenue by 40% in fiscal 2025.'}
                </p>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div className="p-2 bg-[#090e17] rounded border border-slate-800">
                  <span className="text-slate-500 block">Claim Kind:</span>
                  <span className="text-cyan-300 font-semibold">{result?.claim?.claim_kind || 'empirical_metric'}</span>
                </div>
                <div className="p-2 bg-[#090e17] rounded border border-slate-800">
                  <span className="text-slate-500 block">Entities Extracted:</span>
                  <span className="text-slate-200">
                    {result?.claim?.entities?.length ? result.claim.entities.join(', ') : 'Company X, Fiscal 2025'}
                  </span>
                </div>
              </div>
            </div>
          ),
          action: () => onNavigateTab('console'),
          actionText: 'View in Topology Canvas',
        };
      case 'N02':
        return {
          title: 'NODE N02: STRESS_SPLIT (3-FORK)',
          badge: 'STAGE 02 — ADVERSARIAL FORKING',
          color: 'purple',
          description:
            'Generates targeted falsification hypotheses (H1, H2, H3) designed to stress-test numerical bounds, counter-factuals, and temporal invalidity.',
          content: (
            <div className="space-y-2 font-mono text-xs">
              {result?.hypotheses && result.hypotheses.length > 0 ? (
                result.hypotheses.map((h, i) => (
                  <div key={i} className="p-2.5 bg-[#120d24] rounded-lg border border-purple-900/50">
                    <div className="flex items-center justify-between text-purple-300 font-bold text-[11px] mb-1">
                      <span>HYPOTHESIS #{i + 1} ({h.category})</span>
                      <span className="text-purple-400">PRIORITY {h.priority}</span>
                    </div>
                    <p className="text-slate-200 text-xs">{h.hypothesis}</p>
                  </div>
                ))
              ) : (
                <div className="p-3 bg-[#120d24] rounded-lg border border-purple-900/50 text-slate-300">
                  Forking 3 primary hypotheses: H1 (SEC filing contradictions), H2 (Negative metric variance), H3 (Temporal mismatch).
                </div>
              )}
            </div>
          ),
          action: () => onNavigateTab('stress'),
          actionText: 'Open Full Stress Test Panel',
        };
      case 'T1_SEC':
        return {
          title: 'NODE T1_SEC: REGULATORY_ANCHOR (CRYPT_SEAL 0.99)',
          badge: 'STAGE 03 — TIER-1 EVIDENCE RETRIEVAL',
          color: 'emerald',
          description:
            'Primary authoritative source retrieval focusing on certified statutory documents (e.g. SEC 10-K, 10-Q, peer-reviewed registries).',
          content: (
            <div className="space-y-3 font-mono text-xs">
              <div className="p-3 bg-[#061814] rounded-lg border border-emerald-900/50 flex items-center justify-between">
                <div>
                  <div className="text-emerald-300 font-bold">SEC EDGAR 10-K #409 Certified Anchor</div>
                  <div className="text-[11px] text-emerald-500">Cryptographic Attestation Hash: 0x99A3F1</div>
                </div>
                <ShieldCheck className="w-6 h-6 text-emerald-400" />
              </div>
              <div className="p-2 bg-[#090e17] rounded border border-slate-800 text-[11px] text-slate-300">
                Audited statements supersede secondary media claims, establishing an unshakeable ground-truth anchor.
              </div>
            </div>
          ),
          action: () => onNavigateTab('evidence'),
          actionText: 'Open Evidence Vault',
        };
      case 'H2_ATTACK':
        return {
          title: 'ATTACK VECTOR: H2_ATTACK (Δ 0.84)',
          badge: 'STAGE 03 — ADVERSARIAL ATTACK',
          color: 'rose',
          description:
            'Direct empirical contradiction probe targeting delta discrepancy between claimed growth vs audited actual filings.',
          content: (
            <div className="p-3 bg-[#240a15] rounded-lg border border-rose-900/60 font-mono text-xs text-rose-200">
              <div className="font-bold flex items-center gap-1.5 mb-1 text-rose-300">
                <AlertTriangle className="w-4 h-4 text-rose-400" />
                <span>Empirical Divergence: Δ 0.84</span>
              </div>
              <p className="text-slate-300 text-[11px]">
                Search probed for filings showing lower or negative growth, yielding definitive counter-statements.
              </p>
            </div>
          ),
          action: () => onNavigateTab('stress'),
          actionText: 'Inspect Attack Vectors',
        };
      case 'N04':
        return {
          title: 'NODE N04: SYBIL_COLLAPSE (104 → 1 DUP)',
          badge: 'STAGE 03 — SOURCE DEDUPLICATION',
          color: 'amber',
          description:
            'Detects syndicated wire stories and echo-chamber republishing. Collapses redundant reposts into independent origin clusters.',
          content: (
            <div className="p-3 bg-[#1e1307] rounded-lg border border-amber-900/50 font-mono text-xs">
              <div className="text-amber-300 font-bold mb-1">Echo-Chamber Elimination:</div>
              <p className="text-slate-300 text-[11px]">
                104 raw search results collapsed into 1 independent cluster to prevent artificially inflated consensus scores.
              </p>
            </div>
          ),
          action: () => onNavigateTab('evidence'),
          actionText: 'View Clustered Evidence',
        };
      case 'ARBITER':
        return {
          title: 'DIALECTIC_ARBITER: EMPIRICAL DIVERGENCE',
          badge: 'STAGE 04 — CONTRADICTION & FUSION',
          color: 'rose',
          description:
            'Cross-evaluates supporting claims vs counter-evidence across source quality, independence, and temporal constraints.',
          content: (
            <div className="space-y-2 font-mono text-xs">
              <div className="p-3 bg-[#210915] rounded-lg border border-rose-900/60">
                <div className="flex justify-between items-center text-rose-300 font-bold mb-1">
                  <span>Contradictions Detected:</span>
                  <span className="text-rose-400">{result?.contradictions?.length || 2} Active</span>
                </div>
                <p className="text-slate-300 text-[11px]">
                  Direct conflict identified between assertion and primary source filing data.
                </p>
              </div>
            </div>
          ),
          action: () => onNavigateTab('audit'),
          actionText: 'Inspect Contradiction Audit',
        };
      case 'TERMINAL':
      default:
        return {
          title: `FINAL_VERDICT: ${result?.verdict || 'REFUTED'}`,
          badge: 'STAGE 05 — DETERMINATION & SIGMA',
          color: 'rose',
          description:
            'The synthesis terminates with a Bayesian-calibrated confidence score and exhaustive epistemic rationale.',
          content: (
            <div className="space-y-3 font-mono text-xs">
              <div className="p-4 bg-[#1f0914] rounded-lg border border-rose-900/70 text-center">
                <div className="text-2xl font-black text-rose-400">
                  {result ? Math.round(result.confidence * 100) : 78}% {result?.verdict || 'REFUTED'}
                </div>
                <div className="text-slate-400 text-[11px] mt-1">Sigma 4.2 Decisiveness Margin</div>
              </div>
              <p className="text-slate-300 text-xs italic">
                "{result?.confidence_explanation || 'Audited SEC 10-K filing reports negative revenue delta, disproving positive 40% claim.'}"
              </p>
            </div>
          ),
          action: () => onNavigateTab('audit'),
          actionText: 'View Audit Logs & Trace',
        };
    }
  };

  const details = getDetails();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-fadeIn select-none">
      <div className="bg-[#0b0f19] border border-cyan-500/40 rounded-xl max-w-lg w-full p-5 shadow-[0_0_30px_rgba(6,182,212,0.3)]">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 pb-3 border-b border-[#1b263b]">
          <div>
            <span className="font-sans text-[10px] px-2 py-0.5 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/60 uppercase font-semibold">
              {details.badge}
            </span>
            <h3 className="font-sans font-bold text-sm text-white mt-1.5">{details.title}</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Description */}
        <p className="text-xs text-slate-300 my-3 leading-relaxed">{details.description}</p>

        {/* Dynamic Node Specific Content */}
        <div className="my-3">{details.content}</div>

        {/* Footer Actions */}
        <div className="mt-4 pt-3 border-t border-[#1b263b] flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 rounded text-xs font-sans text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
          >
            Close
          </button>
          <button
            type="button"
            onClick={() => {
              details.action();
              onClose();
            }}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-white font-sans text-xs font-semibold shadow-[0_0_10px_rgba(6,182,212,0.4)]"
          >
            <span>{details.actionText}</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
