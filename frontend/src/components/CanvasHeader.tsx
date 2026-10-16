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
    ? 'bg-cyan-950/80 text-cyan-300 border-cyan-400 shadow-[0_0_10px_rgba(6,182,212,0.4)] animate-pulse'
    : result?.verdict === 'VERIFIED'
    ? 'bg-emerald-950/80 text-emerald-300 border-emerald-500'
    : result?.verdict === 'REFUTED'
    ? 'bg-rose-950/80 text-rose-300 border-rose-500'
    : result?.verdict === 'CONFLICTED'
    ? 'bg-amber-950/80 text-amber-300 border-amber-500'
    : 'bg-[#111c2e] text-blue-300 border-blue-700/60';

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
      <header className="bg-[#090d18] border-b border-[#141d2f] px-4 sm:px-8 py-2.5 flex items-center justify-between gap-4 text-xs font-mono">
        {/* Left Tabs */}
        <div className="flex items-center gap-1 sm:gap-6">
          <div className="flex items-center gap-2 mr-2 shrink-0">
            <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_#00f5d4]" />
            <span className="font-mono font-black text-sm tracking-wider text-white">Falsify</span>
          </div>

          <nav className="flex items-center gap-1 sm:gap-4" aria-label="Canvas Workspace Navigation">
            {/* Live Run Tab (maps to console / verification) */}
            <button
              type="button"
              role="button"
              aria-label="Verification"
              onClick={() => onSelectTab('console')}
              className={`relative py-1 px-2.5 sm:px-3 text-xs tracking-wide transition-all ${
                activeTab === 'console'
                  ? 'text-cyan-300 font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <span>Live Run</span>
              {activeTab === 'console' && (
                <span className="absolute -bottom-2.5 left-0 right-0 h-[2px] bg-cyan-400 shadow-[0_0_8px_#00f5d4]" />
              )}
            </button>

            {/* Run History Tab */}
            <button
              type="button"
              role="button"
              aria-label="History"
              onClick={() => onSelectTab('history')}
              className={`relative py-1 px-2.5 sm:px-3 text-xs tracking-wide transition-all ${
                activeTab === 'history'
                  ? 'text-cyan-300 font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <span>Run History</span>
              {activeTab === 'history' && (
                <span className="absolute -bottom-2.5 left-0 right-0 h-[2px] bg-cyan-400 shadow-[0_0_8px_#00f5d4]" />
              )}
            </button>

            {/* About Tab */}
            <button
              type="button"
              role="button"
              aria-label="About"
              onClick={() => onSelectTab('audit')}
              className={`relative py-1 px-2.5 sm:px-3 text-xs tracking-wide transition-all ${
                activeTab === 'audit'
                  ? 'text-cyan-300 font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <span>About</span>
              {activeTab === 'audit' && (
                <span className="absolute -bottom-2.5 left-0 right-0 h-[2px] bg-cyan-400 shadow-[0_0_8px_#00f5d4]" />
              )}
            </button>
          </nav>
        </div>

        {/* Right Actions: Deploy & Menu */}
        <div className="flex items-center gap-2 relative">
          <button
            type="button"
            onClick={onDeployRedTeam}
            className="inline-flex items-center gap-2 px-4 py-1.5 rounded-lg bg-cyan-950/70 hover:bg-cyan-900/90 text-cyan-300 border border-cyan-500/60 font-mono font-semibold text-xs tracking-wider transition-all shadow-[0_0_12px_rgba(6,182,212,0.25)] active:scale-95"
            title="Deploy Red Team Stress Test"
          >
            <Flame className={`w-3.5 h-3.5 ${isStreaming ? 'animate-spin text-amber-300' : 'text-cyan-400'}`} />
            <span>Deploy</span>
          </button>

          <button
            type="button"
            onClick={() => setIsMenuOpen((prev) => !prev)}
            className="p-1.5 text-slate-400 hover:text-slate-200 transition-colors rounded hover:bg-[#151f33]"
            title="More Options"
            aria-label="More Options"
          >
            <MoreVertical className="w-4 h-4" />
          </button>

          {/* Quick Menu Dropdown */}
          {isMenuOpen && (
            <div className="absolute right-0 top-10 w-48 bg-[#0c1322] border border-[#1d2a45] rounded-lg shadow-[0_10px_25px_rgba(0,0,0,0.8)] py-1.5 z-50 text-xs">
              <button
                type="button"
                onClick={() => {
                  onSelectTab('stress');
                  setIsMenuOpen(false);
                }}
                className="w-full text-left px-3.5 py-1.5 text-slate-300 hover:bg-[#16233b] hover:text-cyan-300 transition-colors"
              >
                Hypotheses Matrix
              </button>
              <button
                type="button"
                onClick={() => {
                  onSelectTab('evidence');
                  setIsMenuOpen(false);
                }}
                className="w-full text-left px-3.5 py-1.5 text-slate-300 hover:bg-[#16233b] hover:text-cyan-300 transition-colors"
              >
                Evidence Vault
              </button>
              <div className="h-px bg-[#182338] my-1" />
              <button
                type="button"
                onClick={() => {
                  onDeployRedTeam();
                  setIsMenuOpen(false);
                }}
                className="w-full text-left px-3.5 py-1.5 text-cyan-400 hover:bg-[#16233b] transition-colors"
              >
                Run Red Team Test
              </button>
            </div>
          )}
        </div>
      </header>

      {/* 2. Sub-Ribbon Context Bar */}
      <div className="bg-[#070b14] border-b border-[#121929] px-4 sm:px-8 py-2 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
        {/* Left Status & Breadcrumb */}
        <div className="flex items-center gap-3 min-w-0">
          <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase border ${statusColorClass}`}>
            {statusLabel}
          </span>

          <div className="text-slate-400 text-[11px] truncate max-w-[260px] sm:max-w-md lg:max-w-xl">
            <span className="text-slate-300 font-semibold">falsify-engine</span>
            <span className="mx-1.5 text-slate-600">·</span>
            <span>claim/{claimSlug}</span>
            <span className="mx-1.5 text-slate-600">·</span>
            <span className="text-cyan-400/90 font-mono">{prHash}</span>
          </div>
        </div>

        {/* Right Model Pills (Nemotron Ultra, Nemotron Nano, DeepSeek Pro) */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => setSelectedModel('nemotron-ultra')}
            className={`text-[10px] sm:text-[11px] px-2.5 py-0.5 rounded-full border transition-all ${
              selectedModel === 'nemotron-ultra'
                ? 'bg-[#21133d] text-purple-300 border-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.3)] font-semibold'
                : 'bg-[#150d26]/60 text-purple-400/70 border-purple-900/50 hover:border-purple-700'
            }`}
          >
            Nemotron Ultra
          </button>

          <button
            type="button"
            onClick={() => setSelectedModel('nemotron-nano')}
            className={`text-[10px] sm:text-[11px] px-2.5 py-0.5 rounded-full border transition-all ${
              selectedModel === 'nemotron-nano'
                ? 'bg-[#2d1b09] text-amber-300 border-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.3)] font-semibold'
                : 'bg-[#1f1306]/60 text-amber-400/70 border-amber-900/50 hover:border-amber-700'
            }`}
          >
            Nemotron Nano
          </button>

          <button
            type="button"
            onClick={() => setSelectedModel('deepseek-pro')}
            className={`text-[10px] sm:text-[11px] px-2.5 py-0.5 rounded-full border transition-all ${
              selectedModel === 'deepseek-pro'
                ? 'bg-[#08242b] text-emerald-300 border-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.3)] font-semibold'
                : 'bg-[#05181d]/60 text-emerald-400/70 border-emerald-900/50 hover:border-emerald-700'
            }`}
          >
            DeepSeek Pro
          </button>
        </div>
      </div>
    </div>
  );
};
