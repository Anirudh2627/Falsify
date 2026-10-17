import React, { useState } from 'react';
import { MoreVertical, Flame } from 'lucide-react';
import { VerificationResult } from '../types/falsify';

export type CanvasTab = 'console' | 'stress' | 'evidence' | 'audit' | 'history' | 'about';

interface CanvasHeaderProps {
  activeTab: CanvasTab;
  onSelectTab: (tab: CanvasTab) => void;
  onDeployRedTeam: () => void;
  isStreaming: boolean;
  result?: VerificationResult | null;
  hasContradictions?: boolean;
}

export const CanvasHeader: React.FC<CanvasHeaderProps> = ({
  activeTab,
  onSelectTab,
  onDeployRedTeam,
  isStreaming,
  result,
}) => {
  const [selectedModel, setSelectedModel] = useState<'nemotron-ultra' | 'nemotron-nano' | 'deepseek-pro'>('deepseek-pro');
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  // Derive status pill display
  const statusLabel = isStreaming
    ? 'RUNNING'
    : result
    ? 'COMPLETED'
    : 'READY';

  const statusColorClass = isStreaming
    ? 'bg-indigo-950/80 text-indigo-300 border-indigo-500/40 shadow-sm'
    : result?.verdict === 'VERIFIED'
    ? 'bg-emerald-950/80 text-emerald-300 border-emerald-500/40'
    : result?.verdict === 'REFUTED'
    ? 'bg-rose-950/80 text-rose-300 border-rose-500/40'
    : result?.verdict === 'CONFLICTED'
    ? 'bg-amber-950/80 text-amber-300 border-amber-500/40'
    : 'bg-slate-900/80 text-slate-300 border-slate-700/60';

  const prHash = result?.id
    ? `PR #0x${result.id.toString(16).toUpperCase()}`
    : result?.claim_id
    ? `PR #${result.claim_id.slice(-6).toUpperCase()}`
    : 'PR #51';

  const claimSlug = result?.claim_text
    ? result.claim_text.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 28)
    : 'adversarial-falsification';

  return (
    <div className="w-full flex flex-col z-30 select-none">
      {/* 1. Top Minimal Navigation Bar */}
      <header className="bg-[#090d16] border-b border-slate-800/80 px-4 sm:px-8 py-2.5 flex items-center justify-between gap-4 text-xs font-sans">
        {/* Left Tabs */}
        <div className="flex items-center gap-1 sm:gap-6">
          <div className="flex items-center gap-2 mr-2 shrink-0">
            <div className="w-2.5 h-2.5 rounded-full bg-indigo-500 shadow-sm" />
            <span className="font-semibold text-sm tracking-tight text-white">Falsify</span>
            <span className="text-[11px] text-slate-400 font-sans tracking-normal hidden sm:inline">Research Engine</span>
          </div>

          <nav className="flex items-center gap-1 sm:gap-4" aria-label="Canvas Workspace Navigation">
            {/* Live Run Tab (maps to console / verification) */}
            <button
              type="button"
              role="button"
              aria-label="Verification"
              onClick={() => onSelectTab('console')}
              className={`relative py-1 px-2.5 sm:px-3 text-xs tracking-normal transition-all ${
                activeTab === 'console'
                  ? 'text-white font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <span>Live Run</span>
              {activeTab === 'console' && (
                <span className="absolute -bottom-2.5 left-0 right-0 h-[2px] bg-indigo-500 shadow-sm" />
              )}
            </button>

            {/* Run History Tab */}
            <button
              type="button"
              role="button"
              aria-label="History"
              onClick={() => onSelectTab('history')}
              className={`relative py-1 px-2.5 sm:px-3 text-xs tracking-normal transition-all ${
                activeTab === 'history'
                  ? 'text-white font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <span>Run History</span>
              {activeTab === 'history' && (
                <span className="absolute -bottom-2.5 left-0 right-0 h-[2px] bg-indigo-500 shadow-sm" />
              )}
            </button>

            {/* About Tab */}
            <button
              type="button"
              role="button"
              aria-label="About"
              onClick={() => onSelectTab('audit')}
              className={`relative py-1 px-2.5 sm:px-3 text-xs tracking-normal transition-all ${
                activeTab === 'audit'
                  ? 'text-white font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <span>About</span>
              {activeTab === 'audit' && (
                <span className="absolute -bottom-2.5 left-0 right-0 h-[2px] bg-indigo-500 shadow-sm" />
              )}
            </button>
          </nav>
        </div>

        {/* Right Actions: Deploy & Menu */}
        <div className="flex items-center gap-2 relative">
          <button
            type="button"
            onClick={onDeployRedTeam}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs tracking-normal transition-all shadow-sm active:scale-95"
            title="Deploy Red Team Stress Test"
          >
            <Flame className={`w-3.5 h-3.5 ${isStreaming ? 'animate-spin text-amber-300' : 'text-indigo-200'}`} />
            <span>Deploy</span>
          </button>

          <button
            type="button"
            onClick={() => setIsMenuOpen((prev) => !prev)}
            className="p-1.5 text-slate-400 hover:text-slate-200 transition-colors rounded hover:bg-slate-800/60"
            title="More Options"
            aria-label="More Options"
          >
            <MoreVertical className="w-4 h-4" />
          </button>

          {/* Quick Menu Dropdown */}
          {isMenuOpen && (
            <div className="absolute right-0 top-10 w-48 bg-[#0c1322] border border-slate-800 rounded-lg shadow-xl py-1.5 z-50 text-xs font-sans">
              <button
                type="button"
                onClick={() => {
                  onSelectTab('stress');
                  setIsMenuOpen(false);
                }}
                className="w-full text-left px-3.5 py-1.5 text-slate-300 hover:bg-slate-800/60 hover:text-white transition-colors"
              >
                Hypotheses Matrix
              </button>
              <button
                type="button"
                onClick={() => {
                  onSelectTab('evidence');
                  setIsMenuOpen(false);
                }}
                className="w-full text-left px-3.5 py-1.5 text-slate-300 hover:bg-slate-800/60 hover:text-white transition-colors"
              >
                Evidence Vault
              </button>
              <div className="h-px bg-slate-800 my-1" />
              <button
                type="button"
                onClick={() => {
                  onDeployRedTeam();
                  setIsMenuOpen(false);
                }}
                className="w-full text-left px-3.5 py-1.5 text-indigo-400 hover:bg-slate-800/60 transition-colors"
              >
                Run Red Team Test
              </button>
            </div>
          )}
        </div>
      </header>

      {/* 2. Sub-Ribbon Context Bar */}
      <div className="bg-[#0b0f19] border-b border-slate-800/80 px-4 sm:px-8 py-2 flex flex-wrap items-center justify-between gap-3 text-xs font-sans">
        {/* Left Status & Breadcrumb */}
        <div className="flex items-center gap-3 min-w-0">
          <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold tracking-wider uppercase border ${statusColorClass}`}>
            {statusLabel}
          </span>

          <div className="text-slate-400 text-[11px] truncate max-w-[260px] sm:max-w-md lg:max-w-xl">
            <span className="text-slate-300 font-medium">falsify-engine</span>
            <span className="mx-1.5 text-slate-600">·</span>
            <span>claim/{claimSlug}</span>
            <span className="mx-1.5 text-slate-600">·</span>
            <span className="text-slate-400 font-sans">{prHash}</span>
          </div>
        </div>

        {/* Right Model Pills (Nemotron Ultra, Nemotron Nano, DeepSeek Pro) */}
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            type="button"
            onClick={() => setSelectedModel('nemotron-ultra')}
            className={`text-[10px] sm:text-[11px] px-2.5 py-0.5 rounded-full border transition-all ${
              selectedModel === 'nemotron-ultra'
                ? 'bg-slate-800 text-white border-slate-600 font-medium'
                : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:border-slate-700'
            }`}
          >
            Nemotron Ultra
          </button>

          <button
            type="button"
            onClick={() => setSelectedModel('nemotron-nano')}
            className={`text-[10px] sm:text-[11px] px-2.5 py-0.5 rounded-full border transition-all ${
              selectedModel === 'nemotron-nano'
                ? 'bg-slate-800 text-white border-slate-600 font-medium'
                : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:border-slate-700'
            }`}
          >
            Nemotron Nano
          </button>

          <button
            type="button"
            onClick={() => setSelectedModel('deepseek-pro')}
            className={`text-[10px] sm:text-[11px] px-2.5 py-0.5 rounded-full border transition-all ${
              selectedModel === 'deepseek-pro'
                ? 'bg-slate-800 text-white border-slate-600 font-medium'
                : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:border-slate-700'
            }`}
          >
            DeepSeek Pro
          </button>
        </div>
      </div>
    </div>
  );
};
