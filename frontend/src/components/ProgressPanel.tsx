import React from 'react';
import {
  Loader2,
  CheckCircle2,
  AlertCircle,
  Clock,
  Layers,
  HelpCircle,
  Search,
  Globe,
  Scale,
  ShieldAlert,
  GitMerge,
  Sparkles,
  Activity,
  Radio,
} from 'lucide-react';
import { StreamProgressEvent } from '../types/falsify';

interface Props {
  stages: StreamProgressEvent[];
  latestMessage: string;
  isStreaming: boolean;
  errorMessage?: string | null;
  onCancelStream?: () => void;
}

interface StageStyle {
  label: string;
  badge: string;
  border: string;
  iconBg: string;
  glow: string;
  icon: React.ComponentType<{ className?: string }>;
}

const STAGE_CONFIG: Record<string, StageStyle> = {
  normalization: {
    label: 'Normalization',
    badge: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30',
    border: 'border-indigo-500/30',
    iconBg: 'bg-indigo-950/80 text-indigo-400 border-indigo-500/40',
    glow: 'rgba(99, 102, 241, 0.25)',
    icon: Layers,
  },
  hypotheses: {
    label: 'Hypotheses',
    badge: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    border: 'border-amber-500/30',
    iconBg: 'bg-amber-950/80 text-amber-400 border-amber-500/40',
    glow: 'rgba(245, 158, 11, 0.25)',
    icon: HelpCircle,
  },
  query_generation: {
    label: 'Query Gen',
    badge: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
    border: 'border-sky-500/30',
    iconBg: 'bg-sky-950/80 text-sky-400 border-sky-500/40',
    glow: 'rgba(14, 165, 233, 0.25)',
    icon: Search,
  },
  retrieval: {
    label: 'Retrieval',
    badge: 'bg-teal-500/15 text-teal-300 border-teal-500/30',
    border: 'border-teal-500/30',
    iconBg: 'bg-teal-950/80 text-teal-400 border-teal-500/40',
    glow: 'rgba(20, 184, 166, 0.25)',
    icon: Globe,
  },
  assessment: {
    label: 'Assessment',
    badge: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
    border: 'border-purple-500/30',
    iconBg: 'bg-purple-950/80 text-purple-400 border-purple-500/40',
    glow: 'rgba(168, 85, 247, 0.25)',
    icon: Scale,
  },
  contradiction_detection: {
    label: 'Contradiction',
    badge: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    border: 'border-rose-500/30',
    iconBg: 'bg-rose-950/80 text-rose-400 border-rose-500/40',
    glow: 'rgba(244, 63, 94, 0.25)',
    icon: ShieldAlert,
  },
  fusion: {
    label: 'Fusion',
    badge: 'bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30',
    border: 'border-fuchsia-500/30',
    iconBg: 'bg-fuchsia-950/80 text-fuchsia-400 border-fuchsia-500/40',
    glow: 'rgba(217, 70, 239, 0.25)',
    icon: GitMerge,
  },
  verdict: {
    label: 'Verdict',
    badge: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    border: 'border-emerald-500/30',
    iconBg: 'bg-emerald-950/80 text-emerald-400 border-emerald-500/40',
    glow: 'rgba(16, 185, 129, 0.25)',
    icon: CheckCircle2,
  },
  confidence: {
    label: 'Confidence',
    badge: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
    border: 'border-cyan-500/30',
    iconBg: 'bg-cyan-950/80 text-cyan-400 border-cyan-500/40',
    glow: 'rgba(6, 182, 212, 0.25)',
    icon: Activity,
  },
  synthesis: {
    label: 'Synthesis',
    badge: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
    border: 'border-violet-500/30',
    iconBg: 'bg-violet-950/80 text-violet-400 border-violet-500/40',
    glow: 'rgba(139, 92, 246, 0.25)',
    icon: Sparkles,
  },
};

const DEFAULT_STAGE_STYLE: StageStyle = {
  label: 'Pipeline',
  badge: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
  border: 'border-cyan-500/30',
  iconBg: 'bg-cyan-950/80 text-cyan-400 border-cyan-500/40',
  glow: 'rgba(6, 182, 212, 0.25)',
  icon: Activity,
};

export const ProgressPanel: React.FC<Props> = ({
  stages,
  latestMessage,
  isStreaming,
  errorMessage,
  onCancelStream,
}) => {
  // Compute overall completion fraction if provided by latest event
  const latestProgress = stages.length > 0 ? stages[stages.length - 1].progress : 0.05;
  const progressPercent = Math.min(Math.round(latestProgress * 100), 100);

  return (
    <div className="glass-panel-glow rounded-2xl p-5 mb-6 transition-all duration-300 relative overflow-hidden font-sans">
      {/* Ambient background glow orb */}
      <div
        className="absolute -top-24 -right-24 w-64 h-64 rounded-full pointer-events-none blur-3xl opacity-20"
        style={{
          background: errorMessage
            ? 'radial-gradient(circle, #f43f5e 0%, transparent 70%)'
            : isStreaming
            ? 'radial-gradient(circle, #06b6d4 0%, transparent 70%)'
            : 'radial-gradient(circle, #10b981 0%, transparent 70%)',
        }}
      />

      {/* Header bar */}
      <div className="flex items-center justify-between pb-3.5 border-b border-white/[0.08] relative z-10">
        <div className="flex items-center gap-3.5">
          <div
            className={`w-9 h-9 rounded-xl flex items-center justify-center transition-all shadow-lg ${
              errorMessage
                ? 'bg-rose-950/80 border border-rose-500/40 text-rose-400 shadow-[0_0_12px_rgba(244,63,94,0.3)]'
                : isStreaming
                ? 'bg-cyan-950/80 border border-cyan-500/40 text-cyan-300 animate-ring-pulse shadow-[0_0_15px_rgba(6,182,212,0.4)]'
                : 'bg-emerald-950/80 border border-emerald-500/40 text-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.3)]'
            }`}
          >
            {errorMessage ? (
              <AlertCircle className="w-4 h-4 text-rose-400" />
            ) : isStreaming ? (
              <Loader2 className="w-4 h-4 animate-spin text-cyan-300" />
            ) : (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            )}
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-display text-sm font-bold tracking-tight text-white">
                {errorMessage
                  ? 'Verification Halted'
                  : isStreaming
                  ? 'Adversarial Pipeline In Progress'
                  : 'Verification Completed'}
              </h3>
              {isStreaming && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-cyan-950/70 border border-cyan-500/30 text-cyan-300 animate-pulse">
                  <Radio className="w-2.5 h-2.5 text-cyan-400 animate-spin" />
                  LIVE STREAM
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-0.5 font-sans">
              {isStreaming
                ? 'Hunting for counterevidence across authoritative primary sources (~3-10s)...'
                : 'All adversarial stages completed and verified.'}
            </p>
          </div>
        </div>

        {isStreaming && onCancelStream && (
          <button
            type="button"
            onClick={onCancelStream}
            className="text-xs font-medium text-slate-400 hover:text-rose-300 px-3 py-1.5 rounded-lg border border-white/10 hover:border-rose-500/40 bg-white/[0.03] hover:bg-rose-950/30 transition-all duration-200 active:scale-95"
          >
            Disconnect Stream
          </button>
        )}
      </div>

      {/* Progress Bar & Status */}
      <div className="my-4 relative z-10">
        <div className="flex justify-between items-center text-xs mb-1.5">
          <div className="flex items-center gap-2 max-w-[80%]">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
            <span className="font-medium text-cyan-200 truncate font-sans">
              {latestMessage || 'Initializing pipeline...'}
            </span>
          </div>
          <span className="text-cyan-400 font-mono font-bold text-xs tracking-wider">
            {progressPercent}%
          </span>
        </div>

        {/* Multi-layered Glowing Progress Bar */}
        <div className="w-full bg-black/40 rounded-full h-2.5 p-0.5 border border-white/10 shadow-inner overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ease-out relative ${
              errorMessage
                ? 'bg-rose-500'
                : 'bg-gradient-to-r from-indigo-500 via-cyan-400 to-emerald-400 shadow-[0_0_12px_rgba(6,182,212,0.6)]'
            }`}
            style={{ width: `${progressPercent}%` }}
          >
            {isStreaming && (
              <div className="absolute inset-0 bg-white/25 animate-shimmer rounded-full" />
            )}
          </div>
        </div>
      </div>

      {/* Pipeline Stage Trace Timeline */}
      <div className="mt-3 relative z-10">
        <div className="flex items-center justify-between mb-2.5">
          <h4 className="text-[11px] font-display font-bold uppercase tracking-wider text-slate-400">
            Pipeline Stage Trace
          </h4>
          {stages.length > 0 && (
            <span className="text-[10px] font-mono text-slate-400">
              Stage {stages.length} of ~10
            </span>
          )}
        </div>

        <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
          {stages.length === 0 ? (
            <div className="flex items-center gap-2 text-xs text-slate-400 py-2.5 px-3 rounded-lg bg-black/20 border border-white/[0.04]">
              <Clock className="w-3.5 h-3.5 animate-pulse text-cyan-400" />
              <span>Awaiting initial stage updates from the engine...</span>
            </div>
          ) : (
            stages.map((stage, idx) => {
              const isLast = idx === stages.length - 1;
              const stageKey = stage.stage.toLowerCase();
              const config = STAGE_CONFIG[stageKey] || DEFAULT_STAGE_STYLE;
              const StageIcon = config.icon;

              return (
                <div
                  key={idx}
                  className={`flex items-start gap-3 p-2.5 rounded-xl text-xs transition-all duration-200 animate-stage-in relative overflow-hidden ${
                    isLast && isStreaming
                      ? 'bg-gradient-to-r from-cyan-950/50 via-slate-900/60 to-slate-900/40 border border-cyan-500/40 text-cyan-100 shadow-[0_0_16px_rgba(6,182,212,0.15)]'
                      : 'bg-slate-900/40 hover:bg-slate-900/70 text-slate-300 border border-white/[0.06]'
                  }`}
                >
                  {/* Subtle active background shimmer */}
                  {isLast && isStreaming && (
                    <div className="absolute inset-0 pointer-events-none animate-shimmer opacity-40" />
                  )}

                  {/* Left Stage Icon / State Node */}
                  <div className="mt-0.5 shrink-0 relative z-10">
                    {isLast && isStreaming ? (
                      <div className="w-4 h-4 rounded-md bg-cyan-950 border border-cyan-400 flex items-center justify-center animate-spin">
                        <Loader2 className="w-3 h-3 text-cyan-300" />
                      </div>
                    ) : (
                      <div className="w-4 h-4 rounded-md bg-emerald-950/70 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
                        <CheckCircle2 className="w-3 h-3" />
                      </div>
                    )}
                  </div>

                  {/* Stage Label Badge & Informative Message */}
                  <div className="flex-1 min-w-0 relative z-10">
                    <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
                      <span
                        className={`font-display font-semibold text-[10px] px-2 py-0.5 rounded-md border tracking-wider uppercase inline-flex items-center gap-1 ${config.badge}`}
                      >
                        <StageIcon className="w-2.5 h-2.5" />
                        {stage.stage}
                      </span>
                      <span className="truncate text-slate-200 font-sans font-medium text-[13px]">
                        {stage.message}
                      </span>
                    </div>
                  </div>

                  {/* Right Percentage Badge */}
                  <div className="shrink-0 flex items-center gap-1 relative z-10">
                    <span className="font-mono text-[11px] font-bold text-cyan-400 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-500/30">
                      {Math.round(stage.progress * 100)}%
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
