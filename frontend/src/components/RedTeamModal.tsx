import React, { useState } from 'react';
import { X, Flame } from 'lucide-react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onDeploy: (claim: string) => void;
  isStreaming: boolean;
}

const RED_TEAM_PRESETS = [
  {
    title: 'SEC 10-K Audited Disproof',
    claim: 'Company X reported 40% revenue growth in fiscal 2025.',
    vector: 'Temporal & Numerical Filing Verification',
  },
  {
    title: 'Atmospheric Concentration Boundary',
    claim: 'Global atmospheric CO2 concentration exceeded 420 ppm.',
    vector: 'Primary Sensor Registry Disproof',
  },
  {
    title: 'Medical Trial Efficacy Counter-Search',
    claim: 'Drug Compound B demonstrated zero adverse cardiac events in Phase 3 trials.',
    vector: 'FDA ClinicalTrials.gov Falsification',
  },
];

export const RedTeamModal: React.FC<Props> = ({
  isOpen,
  onClose,
  onDeploy,
  isStreaming,
}) => {
  const [claim, setClaim] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!claim.trim() || isStreaming) return;
    onDeploy(claim.trim());
    onClose();
  };

  const handleSelectPreset = (presetClaim: string) => {
    setClaim(presetClaim);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-fadeIn select-none">
      <div className="bg-[#0b0f19] border border-[#ff0055]/50 rounded-xl max-w-xl w-full p-6 shadow-[0_0_35px_rgba(255,0,85,0.35)] relative">
        {/* Top Header */}
        <div className="flex items-start justify-between pb-3 border-b border-[#210e19]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#2b0816] border border-[#ff0055]/60 flex items-center justify-center text-[#ff0055] shadow-[0_0_12px_rgba(255,0,85,0.4)]">
              <Flame className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-mono font-bold text-base text-white tracking-wider">
                  DEPLOY RED TEAM
                </h3>
                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#ff0055]/20 text-[#ff0055] border border-[#ff0055]/50 font-bold">
                  ACTIVE FALSIFICATION
                </span>
              </div>
              <p className="text-xs font-mono text-slate-400 mt-0.5">
                Stress-test assertions with synthetic adversarial forking & counter-evidence probes.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label htmlFor="redteam-claim-input" className="block text-xs font-mono font-semibold text-slate-300 mb-1.5">
              TARGET PROPOSITION / ASSERTION:
            </label>
            <textarea
              id="redteam-claim-input"
              rows={3}
              value={claim}
              onChange={(e) => setClaim(e.target.value)}
              placeholder="Paste empirical assertion to subject to strict falsification..."
              className="w-full rounded-lg border border-[#231526] bg-[#070b13] p-3 text-xs font-mono text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-[#ff0055] focus:shadow-[0_0_15px_rgba(255,0,85,0.3)]"
            />
          </div>

          {/* Quick Attack Vector Presets */}
          <div>
            <span className="text-[11px] font-mono text-slate-400 block mb-2">
              OR SELECT BENCHMARK ATTACK TARGET:
            </span>
            <div className="space-y-2">
              {RED_TEAM_PRESETS.map((p, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSelectPreset(p.claim)}
                  className="w-full text-left p-2.5 rounded-lg border border-[#1b2538] hover:border-[#ff0055]/60 bg-[#080d16] hover:bg-[#150a14] transition-all group"
                >
                  <div className="flex items-center justify-between text-[11px] font-mono font-bold text-slate-300 group-hover:text-rose-300">
                    <span>{p.title}</span>
                    <span className="text-[10px] text-[#ff0055] font-semibold">{p.vector}</span>
                  </div>
                  <div className="text-[11px] font-mono text-slate-500 mt-1 line-clamp-1 italic">
                    "{p.claim}"
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Modal Action Controls */}
          <div className="pt-3 border-t border-[#1b2538] flex items-center justify-between">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-2 rounded text-xs font-mono text-slate-400 hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!claim.trim() || isStreaming}
              className="inline-flex items-center gap-2 px-5 py-2 rounded bg-[#ff0055] hover:bg-[#e6004c] text-white font-mono font-bold text-xs uppercase tracking-wider transition-all shadow-[0_0_18px_rgba(255,0,85,0.5)] disabled:opacity-50 active:scale-95"
            >
              <Flame className="w-4 h-4 animate-pulse" />
              <span>Initiate Verification</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
