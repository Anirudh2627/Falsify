import React, { useState } from 'react';
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
  Workflow,
  List,
} from 'lucide-react';
import { StreamProgressEvent } from '../types/falsify';
import { PipelineStageDiagram } from './PipelineStageDiagram';

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
    badge: 'bg-slate-800 text-slate-300 border-slate-700/60',
    border: 'border-slate-800',
    iconBg: 'bg-slate-800 text-slate-300 border-slate-700/60',
    glow: 'none',
    icon: Layers,
  },
  hypotheses: {
    label: 'Hypotheses',
    badge: 'bg-slate-800 text-slate-300 border-slate-700/60',
    border: 'border-slate-800',
    iconBg: 'bg-slate-800 text-slate-300 border-slate-700/60',
    glow: 'none',
    icon: HelpCircle,
  },
  query_generation: {
    label: 'Query Gen',
    badge: 'bg-slate-800 text-slate-300 border-slate-700/60',
    border: 'border-slate-800',
    iconBg: 'bg-slate-800 text-slate-300 border-slate-700/60',
    glow: 'none',
    icon: Search,
  },
  retrieval: {
    label: 'Retrieval',
    badge: 'bg-slate-800 text-slate-300 border-slate-700/60',
    border: 'border-slate-800',
    iconBg: 'bg-slate-800 text-slate-300 border-slate-700/60',
    glow: 'none',
    icon: Globe,
  },
  assessment: {
    label: 'Assessment',
    badge: 'bg-slate-800 text-slate-300 border-slate-700/60',
    border: 'border-slate-800',
    iconBg: 'bg-slate-800 text-slate-300 border-slate-700/60',
    glow: 'none',
    icon: Scale,
  },
  contradiction_detection: {
    label: 'Contradiction',
    badge: 'bg-slate-800 text-slate-300 border-slate-700/60',
    border: 'border-slate-800',
    iconBg: 'bg-slate-800 text-slate-300 border-slate-700/60',
    glow: 'none',
    icon: ShieldAlert,
  },
  fusion: {
    label: 'Fusion',
    badge: 'bg-slate-800 text-slate-300 border-slate-700/60',
    border: 'border-slate-800',
    iconBg: 'bg-slate-800 text-slate-300 border-slate-700/60',
    glow: 'none',
    icon: GitMerge,
  },
  verdict: {
    label: 'Verdict',
    badge: 'bg-slate-800 text-slate-300 border-slate-700/60',
    border: 'border-slate-800',
    iconBg: 'bg-slate-800 text-slate-300 border-slate-700/60',
    glow: 'none',
    icon: CheckCircle2,
  },
  confidence: {
    label: 'Confidence',
    badge: 'bg-slate-800 text-slate-300 border-slate-700/60',
    border: 'border-slate-800',
    iconBg: 'bg-slate-800 text-slate-300 border-slate-700/60',
    glow: 'none',
    icon: Activity,
  },
  synthesis: {
    label: 'Synthesis',
    badge: 'bg-slate-800 text-slate-300 border-slate-700/60',
    border: 'border-slate-800',
    iconBg: 'bg-slate-800 text-slate-300 border-slate-700/60',
    glow: 'none',
    icon: Sparkles,
  },
};

const DEFAULT_STAGE_STYLE: StageStyle = {
  label: 'Pipeline',
  badge: 'bg-slate-800 text-slate-300 border-slate-700/60',
  border: 'border-slate-800',
  iconBg: 'bg-slate-800 text-slate-300 border-slate-700/60',
  glow: 'none',
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

  const [viewMode, setViewMode] = useState<'diagram' | 'trace'>('diagram');

  return (
    <div className="surface-card rounded-2xl p-5 mb-6 transition-all duration-300 relative font-sans">
      {/* Header bar */}
      <div className="flex items-center justify-between pb-3.5 border-b border-white/[0.08] relative z-10">
        <div className="flex items-center gap-3.5">
          <div
            className={`w-9 h-9 rounded-xl flex items-center justify-center transition-all shadow-sm ${
              errorMessage
                ? 'bg-rose-950/80 border border-rose-500/40 text-rose-400'
                : isStreaming
                ? 'bg-indigo-950/80 border border-indigo-500/40 text-indigo-300'
                : 'bg-emerald-950/80 border border-emerald-500/40 text-emerald-400'
            }`}
          >
            {errorMessage ? (
              <AlertCircle className="w-4 h-4 text-rose-400" />
            ) : isStreaming ? (
              <Loader2 className="w-4 h-4 animate-spin text-indigo-300" />
            ) : (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            )}
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-sm tracking-tight text-white font-sans">
                {errorMessage
                  ? 'Verification Halted'
                  : isStreaming
                  ? 'Adversarial Pipeline In Progress'
                  : 'Verification Completed'}
              </h3>
              {isStreaming && (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-sans font-medium bg-indigo-950/70 border border-indigo-500/30 text-indigo-300">
                  <Radio className="w-2.5 h-2.5 text-indigo-400" />
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
            className="text-xs font-medium text-slate-400 hover:text-rose-300 px-3 py-1.5 rounded-lg border border-white/10 hover:border-rose-500/40 bg-white/[0.03] hover:bg-rose-950/30 transition-all duration-200 active:scale-95 font-sans"
          >
            Disconnect Stream
          </button>
        )}
      </div>

      {/* Progress Bar & Status */}
      <div className="my-4 relative z-10">
        <div className="flex justify-between items-center text-xs mb-1.5">
          <div className="flex items-center gap-2 max-w-[80%]">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
            <span className="font-medium text-slate-300 truncate font-sans">
              {latestMessage || 'Initializing pipeline...'}
            </span>
          </div>
          <span className="text-indigo-300 font-sans font-semibold text-xs tracking-wider">
            {progressPercent}%
          </span>
        </div>

        {/* Multi-layered Glowing Progress Bar */}
        <div className="w-full bg-slate-950/80 rounded-full h-2 p-0.5 border border-white/10 shadow-inner overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ease-out relative ${
              errorMessage
                ? 'bg-rose-500'
                : 'bg-gradient-to-r from-indigo-500 via-blue-500 to-emerald-400 shadow-sm'
            }`}
            style={{ width: `${progressPercent}%` }}
          >
            {isStreaming && (
              <div className="absolute inset-0 bg-white/20 animate-shimmer rounded-full" />
            )}
          </div>
        </div>
      </div>

      {/* Pipeline Stage Trace & Architecture Diagram */}
      <div className="mt-4 relative z-10">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2.5">
            <h4 className="text-[11px] font-sans font-semibold uppercase tracking-wider text-slate-400">
              Pipeline Stage Trace
            </h4>
            {stages.length > 0 && (
              <span className="text-[11px] text-slate-300 bg-slate-800/80 border border-slate-700/60 px-2 py-0.5 rounded-md font-medium">
                {stages.length} event{stages.length !== 1 ? 's' : ''} logged
              </span>
            )}
          </div>

          {/* View Mode Toggle: Diagram vs Trace Log */}
          <div className="flex items-center gap-1 bg-slate-950/70 p-1 rounded-lg border border-slate-800">
            <button
              type="button"
              onClick={() => setViewMode('diagram')}
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-sans font-medium transition-all ${
                viewMode === 'diagram'
                  ? 'bg-slate-800 text-white border border-slate-700 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Workflow className="w-3.5 h-3.5 text-slate-300" />
              <span>Diagram View</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode('trace')}
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-sans font-medium transition-all ${
                viewMode === 'trace'
                  ? 'bg-slate-800 text-white border border-slate-700 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <List className="w-3.5 h-3.5 text-slate-300" />
              <span>Trace Log ({stages.length})</span>
            </button>
          </div>
        </div>

        {viewMode === 'diagram' ? (
          /* Visual Pipeline Flow Diagram */
          <PipelineStageDiagram
            stages={stages}
            isStreaming={isStreaming}
            errorMessage={errorMessage}
          />
        ) : (
          /* Linear Chronological Trace Log */
          <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
            {stages.length === 0 ? (
              <div className="flex items-center gap-2 text-xs text-slate-400 py-3 px-3.5 rounded-xl bg-slate-900/40 border border-slate-800">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
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
                    className={`flex items-start gap-3 p-2.5 rounded-xl text-xs transition-all duration-150 relative overflow-hidden ${
                      isLast && isStreaming
                        ? 'bg-slate-900 border border-slate-700 text-slate-100 shadow-sm'
                        : 'bg-slate-900/40 hover:bg-slate-900/70 text-slate-300 border border-slate-800'
                    }`}
                  >
                    {/* Left Stage Icon / State Node */}
                    <div className="mt-0.5 shrink-0 relative z-10">
                      {isLast && isStreaming ? (
                        <div className="w-4 h-4 rounded-md bg-blue-950/60 border border-blue-500/50 flex items-center justify-center animate-spin">
                          <Loader2 className="w-3 h-3 text-blue-300" />
                        </div>
                      ) : (
                        <div className="w-4 h-4 rounded-md bg-emerald-950/50 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
                          <CheckCircle2 className="w-3 h-3" />
                        </div>
                      )}
                    </div>

                    {/* Stage Label Badge & Informative Message */}
                    <div className="flex-1 min-w-0 relative z-10">
                      <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
                        <span
                          className={`font-semibold text-[10px] px-2 py-0.5 rounded-md border tracking-normal inline-flex items-center gap-1 ${config.badge}`}
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
                      <span className="text-[11px] font-medium text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700/60">
                        {Math.round(stage.progress * 100)}%
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>
    </div>
  );
};
