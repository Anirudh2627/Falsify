import React, { useState, useEffect } from 'react';
import {
  Layers,
  HelpCircle,
  Search,
  Globe,
  Scale,
  ShieldAlert,
  GitMerge,
  CheckCircle2,
  Activity,
  Sparkles,
  Clock,
  Loader2,
  AlertCircle,
  Check,
  ChevronRight,
  Info,
} from 'lucide-react';
import { StreamProgressEvent } from '../types/falsify';

export interface StageNodeDef {
  id: string;
  stepNumber: string;
  name: string;
  shortLabel: string;
  phase: string;
  description: string;
  expectedProgress: number;
  icon: React.ComponentType<{ className?: string }>;
}

export const PIPELINE_NODES: StageNodeDef[] = [
  {
    id: 'normalization',
    stepNumber: '01',
    name: 'Claim Normalization',
    shortLabel: 'Normalization',
    phase: 'Ingestion',
    description: 'Deconstruct claim syntax, extract temporal constraints, entities, and numeric parameters.',
    expectedProgress: 15,
    icon: Layers,
  },
  {
    id: 'hypotheses',
    stepNumber: '02',
    name: 'Hypotheses Generation',
    shortLabel: 'Hypotheses',
    phase: 'Adversarial',
    description: 'Synthesize Popperian falsification hypotheses designed to stress-test the assertion.',
    expectedProgress: 25,
    icon: HelpCircle,
  },
  {
    id: 'query_generation',
    stepNumber: '03',
    name: 'Adversarial Query Gen',
    shortLabel: 'Query Gen',
    phase: 'Adversarial',
    description: 'Generate targeted counter-evidence queries across academic and primary web registries.',
    expectedProgress: 35,
    icon: Search,
  },
  {
    id: 'retrieval',
    stepNumber: '04',
    name: 'Evidence Retrieval',
    shortLabel: 'Retrieval',
    phase: 'Evidence',
    description: 'Crawl multi-source tier-1 databases, governmental archives, and peer-reviewed journals.',
    expectedProgress: 50,
    icon: Globe,
  },
  {
    id: 'assessment',
    stepNumber: '05',
    name: 'Credibility Assessment',
    shortLabel: 'Assessment',
    phase: 'Evidence',
    description: 'Evaluate evidence relevance, source tier credibility, stance, and temporal validity.',
    expectedProgress: 65,
    icon: Scale,
  },
  {
    id: 'contradiction_detection',
    stepNumber: '06',
    name: 'Contradiction Audit',
    shortLabel: 'Contradiction',
    phase: 'Epistemic Audit',
    description: 'Run adversarial contradiction matrix to discover direct empirical disproofs.',
    expectedProgress: 75,
    icon: ShieldAlert,
  },
  {
    id: 'fusion',
    stepNumber: '07',
    name: 'Dialectic Fusion',
    shortLabel: 'Fusion',
    phase: 'Epistemic Audit',
    description: 'Cluster independent sources, collapse duplicate claims, and measure consensus vs dissent.',
    expectedProgress: 85,
    icon: GitMerge,
  },
  {
    id: 'verdict',
    stepNumber: '08',
    name: 'Verdict Determination',
    shortLabel: 'Verdict',
    phase: 'Epistemic Arbiter',
    description: 'Formulate final verdict (Verified, Qualified, Conflicted, Refuted, or Unverifiable).',
    expectedProgress: 92,
    icon: CheckCircle2,
  },
  {
    id: 'confidence',
    stepNumber: '09',
    name: 'Confidence Scoring',
    shortLabel: 'Confidence',
    phase: 'Epistemic Arbiter',
    description: 'Compute 8-factor epistemic confidence breakdown and decisiveness margins.',
    expectedProgress: 95,
    icon: Activity,
  },
  {
    id: 'synthesis',
    stepNumber: '10',
    name: 'Reasoning Synthesis',
    shortLabel: 'Synthesis',
    phase: 'Epistemic Arbiter',
    description: 'Synthesize comprehensive dialectic rationale and assemble serialized trace.',
    expectedProgress: 98,
    icon: Sparkles,
  },
];

export interface PhaseTheme {
  name: string;
  badgeBg: string;
  badgeText: string;
  badgeBorder: string;
  nodeBorder: string;
  nodeBorderHover: string;
  nodeBg: string;
  nodeBgSelected: string;
  nodeRing: string;
  iconBg: string;
  iconText: string;
  iconBorder: string;
  progressText: string;
  progressBg: string;
  progressBorder: string;
  activeGlow: string;
  connectorColor: string;
  dotColor: string;
}

export const PHASE_THEMES: Record<string, PhaseTheme> = {
  Ingestion: {
    name: 'Ingestion',
    badgeBg: 'bg-indigo-950/70',
    badgeText: 'text-indigo-300',
    badgeBorder: 'border-indigo-500/40',
    nodeBorder: 'border-indigo-900/60',
    nodeBorderHover: 'hover:border-indigo-500/50',
    nodeBg: 'bg-[#0c102b]/90',
    nodeBgSelected: 'bg-[#141b47]',
    nodeRing: 'ring-indigo-500/60 shadow-[0_0_15px_rgba(99,102,241,0.3)]',
    iconBg: 'bg-indigo-950/80',
    iconText: 'text-indigo-300',
    iconBorder: 'border-indigo-600/40',
    progressText: 'text-indigo-300',
    progressBg: 'bg-indigo-950/80',
    progressBorder: 'border-indigo-600/40',
    activeGlow: 'border-indigo-500 ring-2 ring-indigo-500/50 shadow-[0_0_16px_rgba(99,102,241,0.4)]',
    connectorColor: 'bg-indigo-500/70',
    dotColor: 'bg-indigo-400',
  },
  Adversarial: {
    name: 'Adversarial',
    badgeBg: 'bg-amber-950/70',
    badgeText: 'text-amber-300',
    badgeBorder: 'border-amber-500/40',
    nodeBorder: 'border-amber-900/60',
    nodeBorderHover: 'hover:border-amber-500/50',
    nodeBg: 'bg-[#1f1406]/90',
    nodeBgSelected: 'bg-[#311f07]',
    nodeRing: 'ring-amber-500/60 shadow-[0_0_15px_rgba(245,158,11,0.3)]',
    iconBg: 'bg-amber-950/80',
    iconText: 'text-amber-300',
    iconBorder: 'border-amber-600/40',
    progressText: 'text-amber-300',
    progressBg: 'bg-amber-950/80',
    progressBorder: 'border-amber-600/40',
    activeGlow: 'border-amber-500 ring-2 ring-amber-500/50 shadow-[0_0_16px_rgba(245,158,11,0.4)]',
    connectorColor: 'bg-amber-500/70',
    dotColor: 'bg-amber-400',
  },
  Evidence: {
    name: 'Evidence Grounding',
    badgeBg: 'bg-cyan-950/70',
    badgeText: 'text-cyan-300',
    badgeBorder: 'border-cyan-500/40',
    nodeBorder: 'border-cyan-900/60',
    nodeBorderHover: 'hover:border-cyan-500/50',
    nodeBg: 'bg-[#061521]/90',
    nodeBgSelected: 'bg-[#09253b]',
    nodeRing: 'ring-cyan-500/60 shadow-[0_0_15px_rgba(6,182,212,0.3)]',
    iconBg: 'bg-cyan-950/80',
    iconText: 'text-cyan-300',
    iconBorder: 'border-cyan-600/40',
    progressText: 'text-cyan-300',
    progressBg: 'bg-cyan-950/80',
    progressBorder: 'border-cyan-600/40',
    activeGlow: 'border-cyan-500 ring-2 ring-cyan-500/50 shadow-[0_0_16px_rgba(6,182,212,0.4)]',
    connectorColor: 'bg-cyan-500/70',
    dotColor: 'bg-cyan-400',
  },
  'Epistemic Audit': {
    name: 'Epistemic Audit',
    badgeBg: 'bg-rose-950/70',
    badgeText: 'text-rose-300',
    badgeBorder: 'border-rose-500/40',
    nodeBorder: 'border-rose-900/60',
    nodeBorderHover: 'hover:border-rose-500/50',
    nodeBg: 'bg-[#1d0b16]/90',
    nodeBgSelected: 'bg-[#2f0e22]',
    nodeRing: 'ring-rose-500/60 shadow-[0_0_15px_rgba(244,63,94,0.3)]',
    iconBg: 'bg-rose-950/80',
    iconText: 'text-rose-300',
    iconBorder: 'border-rose-600/40',
    progressText: 'text-rose-300',
    progressBg: 'bg-rose-950/80',
    progressBorder: 'border-rose-600/40',
    activeGlow: 'border-rose-500 ring-2 ring-rose-500/50 shadow-[0_0_16px_rgba(244,63,94,0.4)]',
    connectorColor: 'bg-rose-500/70',
    dotColor: 'bg-rose-400',
  },
  'Epistemic Arbiter': {
    name: 'Epistemic Arbiter',
    badgeBg: 'bg-emerald-950/70',
    badgeText: 'text-emerald-300',
    badgeBorder: 'border-emerald-500/40',
    nodeBorder: 'border-emerald-900/60',
    nodeBorderHover: 'hover:border-emerald-500/50',
    nodeBg: 'bg-[#081a14]/90',
    nodeBgSelected: 'bg-[#0e2c21]',
    nodeRing: 'ring-emerald-500/60 shadow-[0_0_15px_rgba(16,185,129,0.3)]',
    iconBg: 'bg-emerald-950/80',
    iconText: 'text-emerald-300',
    iconBorder: 'border-emerald-600/40',
    progressText: 'text-emerald-300',
    progressBg: 'bg-emerald-950/80',
    progressBorder: 'border-emerald-600/40',
    activeGlow: 'border-emerald-500 ring-2 ring-emerald-500/50 shadow-[0_0_16px_rgba(16,185,129,0.4)]',
    connectorColor: 'bg-emerald-500/70',
    dotColor: 'bg-emerald-400',
  },
};

export type NodeStatus = 'completed' | 'running' | 'pending' | 'failed';

interface Props {
  stages: StreamProgressEvent[];
  isStreaming: boolean;
  errorMessage?: string | null;
}

export const PipelineStageDiagram: React.FC<Props> = ({
  stages,
  isStreaming,
  errorMessage,
}) => {
  // Map stage occurrences and latest events
  const stageEventsMap = React.useMemo(() => {
    const map = new Map<string, StreamProgressEvent[]>();
    for (const evt of stages) {
      const key = evt.stage.toLowerCase();
      if (!map.has(key)) {
        map.set(key, []);
      }
      map.get(key)!.push(evt);
    }
    return map;
  }, [stages]);

  // Determine latest stage index seen
  const latestEvent = stages.length > 0 ? stages[stages.length - 1] : null;
  const latestStageKey = latestEvent ? latestEvent.stage.toLowerCase() : null;
  const latestStageIdx = PIPELINE_NODES.findIndex((n) => n.id === latestStageKey);

  // Determine status for each node in sequence
  const nodeStatusList = React.useMemo(() => {
    return PIPELINE_NODES.map((node, index) => {
      const events = stageEventsMap.get(node.id) || [];
      const hasEvents = events.length > 0;

      let status: NodeStatus = 'pending';

      if (!isStreaming) {
        if (errorMessage && index === latestStageIdx) {
          status = 'failed';
        } else if (hasEvents || (latestStageIdx !== -1 && index <= latestStageIdx) || stages.length >= 10) {
          status = 'completed';
        } else {
          status = 'pending';
        }
      } else {
        if (errorMessage && index === latestStageIdx) {
          status = 'failed';
        } else if (index === latestStageIdx) {
          status = 'running';
        } else if (latestStageIdx !== -1 && index < latestStageIdx) {
          status = 'completed';
        } else if (hasEvents && index > latestStageIdx) {
          status = 'completed';
        } else {
          status = 'pending';
        }
      }

      // Compute progress percentage
      let currentProgress = node.expectedProgress;
      if (events.length > 0) {
        currentProgress = Math.round(events[events.length - 1].progress * 100);
      } else if (status === 'completed') {
        currentProgress = node.expectedProgress;
      }

      return {
        node,
        status,
        events,
        currentProgress,
      };
    });
  }, [stageEventsMap, latestStageIdx, isStreaming, errorMessage, stages.length]);

  // Selected node for deep inspection in the lower panel
  const [selectedNodeId, setSelectedNodeId] = useState<string>(
    latestStageKey || PIPELINE_NODES[0].id
  );

  useEffect(() => {
    if (isStreaming && latestStageKey) {
      setSelectedNodeId(latestStageKey);
    } else if (!isStreaming && latestStageKey) {
      setSelectedNodeId(latestStageKey);
    }
  }, [latestStageKey, isStreaming]);

  const selectedItem = nodeStatusList.find((item) => item.node.id === selectedNodeId) || nodeStatusList[0];
  const SelectedIcon = selectedItem.node.icon;

  const completedCount = nodeStatusList.filter((n) => n.status === 'completed').length;
  const runningItem = nodeStatusList.find((n) => n.status === 'running');

  return (
    <div className="space-y-3 font-sans">
      {/* 1. Header Metrics Strip & Phase Indicator Legend */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-1 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-medium text-slate-300 font-sans">
            Pipeline Architecture:
          </span>
          <span className="text-[11px] text-slate-300 bg-slate-850 border border-slate-700/60 px-2 py-0.5 rounded-md font-medium">
            {completedCount} / {PIPELINE_NODES.length} Stages Completed
          </span>
        </div>

        {/* Phase Color Legend */}
        <div className="hidden md:flex items-center gap-2.5 text-[10px] font-sans">
          <span className="inline-flex items-center gap-1.5 text-indigo-300">
            <span className="w-2 h-2 rounded-full bg-indigo-400 shadow-[0_0_6px_rgba(99,102,241,0.6)]" /> Ingestion
          </span>
          <span className="inline-flex items-center gap-1.5 text-amber-300">
            <span className="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_6px_rgba(245,158,11,0.6)]" /> Adversarial
          </span>
          <span className="inline-flex items-center gap-1.5 text-cyan-300">
            <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_6px_rgba(6,182,212,0.6)]" /> Evidence
          </span>
          <span className="inline-flex items-center gap-1.5 text-rose-300">
            <span className="w-2 h-2 rounded-full bg-rose-400 shadow-[0_0_6px_rgba(244,63,94,0.6)]" /> Epistemic Audit
          </span>
          <span className="inline-flex items-center gap-1.5 text-emerald-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(16,185,129,0.6)]" /> Epistemic Arbiter
          </span>
        </div>

        {runningItem && (
          <div className="flex items-center gap-1.5 text-xs text-slate-300 font-medium font-sans">
            <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
            <span>Active: {runningItem.node.name}</span>
          </div>
        )}
      </div>

      {/* 2. Interactive Pipeline Diagram Canvas */}
      <div className="relative p-3 sm:p-3.5 rounded-xl bg-[#090d16] border border-slate-800 overflow-x-auto shadow-sm">
        {/* Pipeline Stage Track (10 Stages with Phase-Based Color Themes) */}
        <div className="relative z-10 flex items-center min-w-[760px] lg:min-w-0 justify-between gap-1 sm:gap-2">
          {nodeStatusList.map((item, idx) => {
            const { node, status, currentProgress } = item;
            const theme = PHASE_THEMES[node.phase] || PHASE_THEMES['Ingestion'];
            const Icon = node.icon;
            const isSelected = selectedNodeId === node.id;
            const isLast = idx === nodeStatusList.length - 1;
            const nextItem = !isLast ? nodeStatusList[idx + 1] : null;

            // Connection line state
            const isLineActive =
              status === 'completed' ||
              (status === 'running' && nextItem && nextItem.status !== 'pending');

            return (
              <React.Fragment key={node.id}>
                {/* Node Box */}
                <button
                  type="button"
                  onClick={() => setSelectedNodeId(node.id)}
                  title={`${node.name} (${status}) - Phase: ${node.phase}`}
                  className={`group relative flex-1 min-w-[68px] sm:min-w-[80px] p-2 sm:p-2.5 rounded-xl border text-left transition-all duration-150 flex flex-col items-center text-center cursor-pointer select-none focus:outline-none ${
                    isSelected
                      ? `${theme.nodeBgSelected} border-white/70 ring-2 ${theme.nodeRing} z-20`
                      : status === 'running'
                      ? `${theme.nodeBg} ${theme.activeGlow} text-white`
                      : status === 'completed'
                      ? `${theme.nodeBg} ${theme.nodeBorder} ${theme.nodeBorderHover}`
                      : status === 'failed'
                      ? 'bg-rose-950/40 border-rose-500/60 text-rose-300'
                      : 'bg-slate-950/40 border-slate-800/60 text-slate-500 opacity-60'
                  }`}
                >
                  {/* Step index & Status Indicator */}
                  <div className="flex items-center justify-between w-full mb-1.5 px-0.5">
                    <span
                      className={`text-[10px] font-medium font-sans ${
                        isSelected
                          ? 'text-white font-semibold'
                          : status === 'completed'
                          ? theme.badgeText
                          : status === 'running'
                          ? 'text-white font-bold'
                          : 'text-slate-500'
                      }`}
                    >
                      {node.stepNumber}
                    </span>

                    {/* Status badge / icon */}
                    {status === 'completed' ? (
                      <span className="w-3.5 h-3.5 rounded-full bg-emerald-950/60 border border-emerald-500/50 flex items-center justify-center text-emerald-400">
                        <Check className="w-2.5 h-2.5 stroke-[2.5]" />
                      </span>
                    ) : status === 'running' ? (
                      <span className={`w-3.5 h-3.5 rounded-full ${theme.iconBg} border ${theme.iconBorder} flex items-center justify-center ${theme.iconText} animate-spin`}>
                        <Loader2 className="w-2.5 h-2.5 stroke-[2]" />
                      </span>
                    ) : status === 'failed' ? (
                      <span className="w-3.5 h-3.5 rounded-full bg-rose-950/50 border border-rose-500/50 flex items-center justify-center text-rose-400">
                        <AlertCircle className="w-2.5 h-2.5" />
                      </span>
                    ) : (
                      <span className="w-3.5 h-3.5 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-500">
                        <Clock className="w-2 h-2" />
                      </span>
                    )}
                  </div>

                  {/* Stage Icon Node */}
                  <div
                    className={`w-7 h-7 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center my-1 transition-all ${
                      isSelected
                        ? `${theme.iconBg} ${theme.iconText} border ${theme.iconBorder} shadow-sm`
                        : status === 'running'
                        ? `${theme.iconBg} ${theme.iconText} border ${theme.iconBorder} shadow-sm`
                        : status === 'completed'
                        ? `${theme.iconBg} ${theme.iconText} border ${theme.iconBorder}`
                        : 'bg-slate-900 text-slate-500 border border-slate-800'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                  </div>

                  {/* Stage Name */}
                  <span
                    className={`text-[10px] sm:text-[11px] font-medium tracking-normal truncate w-full mt-0.5 font-sans ${
                      isSelected
                        ? 'text-white font-semibold'
                        : status === 'completed'
                        ? 'text-slate-200'
                        : status === 'running'
                        ? 'text-white font-semibold'
                        : 'text-slate-400'
                    }`}
                  >
                    {node.shortLabel}
                  </span>

                  {/* Progress Pill */}
                  <div className="mt-1 w-full flex items-center justify-center">
                    <span
                      className={`text-[9px] px-1.5 py-0.2 rounded font-medium font-sans ${
                        status === 'completed'
                          ? `${theme.progressText} ${theme.progressBg} border ${theme.progressBorder}`
                          : status === 'running'
                          ? 'text-white bg-blue-600/80 border border-blue-400/50 font-semibold'
                          : 'text-slate-500 bg-slate-900/60'
                      }`}
                    >
                      {currentProgress}%
                    </span>
                  </div>
                </button>

                {/* Flow Connector Line */}
                {!isLast && (
                  <div className="shrink-0 flex items-center justify-center w-2 sm:w-3 relative">
                    <div
                      className={`h-[2px] w-full transition-all duration-150 rounded-full ${
                        isLineActive ? theme.connectorColor : 'bg-slate-800/60'
                      }`}
                    />
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* 3. Deep Stage Inspector Box */}
      {(() => {
        const selectedTheme = PHASE_THEMES[selectedItem.node.phase] || PHASE_THEMES['Ingestion'];
        return (
          <div className="p-3.5 sm:p-4 rounded-xl bg-[#0b0f19] border border-slate-800 shadow-sm transition-all duration-150">
            <div className="flex flex-wrap items-start justify-between gap-3 pb-2.5 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center border ${selectedTheme.iconBorder} ${selectedTheme.iconBg} ${selectedTheme.iconText} shadow-sm`}>
                  <SelectedIcon className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-slate-400 font-sans">
                      Stage {selectedItem.node.stepNumber}:
                    </span>
                    <h5 className="text-sm font-semibold text-white tracking-normal font-sans">
                      {selectedItem.node.name}
                    </h5>
                    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-md border ${selectedTheme.badgeBorder} ${selectedTheme.badgeBg} ${selectedTheme.badgeText} font-sans`}>
                      Phase: {selectedItem.node.phase}
                    </span>
                  </div>
                  <p className="text-[12px] text-slate-400 mt-0.5 max-w-xl font-sans">
                    {selectedItem.node.description}
                  </p>
                </div>
              </div>

              {/* Current Stage State Status Badge */}
              <div className="flex items-center gap-2">
                <span
                  className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-lg border font-sans ${
                    selectedItem.status === 'completed'
                      ? 'bg-emerald-950/40 text-emerald-400 border-emerald-500/30'
                      : selectedItem.status === 'running'
                      ? 'bg-blue-950/40 text-blue-300 border-blue-500/30'
                      : selectedItem.status === 'failed'
                      ? 'bg-rose-950/40 text-rose-300 border-rose-500/30'
                      : 'bg-slate-900/80 text-slate-400 border-slate-800'
                  }`}
                >
                  {selectedItem.status === 'completed' ? (
                    <>
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      <span>VERIFIED COMPLETE</span>
                    </>
                  ) : selectedItem.status === 'running' ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 text-blue-300 animate-spin" />
                      <span>IN PROGRESS</span>
                    </>
                  ) : selectedItem.status === 'failed' ? (
                    <>
                      <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
                      <span>FAILED</span>
                    </>
                  ) : (
                    <>
                      <Clock className="w-3.5 h-3.5 text-slate-400" />
                      <span>QUEUED / PENDING</span>
                    </>
                  )}
                </span>

                <span className={`text-xs font-medium ${selectedTheme.progressText} ${selectedTheme.progressBg} px-2.5 py-1 rounded-lg border ${selectedTheme.progressBorder} font-sans`}>
                  {selectedItem.currentProgress}%
                </span>
              </div>
            </div>

        {/* Emitted Events & Log Trace for this stage */}
        <div className="mt-2.5">
          <span className="text-[11px] font-medium text-slate-400 block mb-1.5">
            Engine Trace Output ({selectedItem.events.length} event{selectedItem.events.length !== 1 ? 's' : ''}):
          </span>

          {selectedItem.events.length === 0 ? (
            <div className="flex items-center gap-2 p-2 rounded-lg bg-slate-900/30 border border-slate-800/60 text-xs text-slate-400">
              <Info className="w-3.5 h-3.5 text-slate-500 shrink-0" />
              <span>
                {selectedItem.status === 'pending'
                  ? 'Stage is queued in pipeline execution sequence. Awaiting execution trigger.'
                  : 'No detailed log messages recorded for this stage yet.'}
              </span>
            </div>
          ) : (
            <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
              {selectedItem.events.map((evt, eIdx) => (
                <div
                  key={eIdx}
                  className="flex items-center justify-between gap-3 p-2 rounded-lg bg-slate-900/60 border border-slate-800 text-xs font-sans"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <ChevronRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <span className="text-slate-200 font-medium truncate">
                      {evt.message}
                    </span>
                  </div>
                  <span className="text-[11px] text-slate-400 shrink-0 bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700/60 font-medium">
                    {Math.round(evt.progress * 100)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  })()}
    </div>
  );
};
