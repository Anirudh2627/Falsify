import React, { useState, useRef, useCallback } from 'react';
import { CanvasHeader, CanvasTab } from './components/CanvasHeader';
import { FalsificationTopologyGraph } from './components/FalsificationTopologyGraph';
import { ClaimInput } from './components/ClaimInput';
import { ProgressPanel } from './components/ProgressPanel';
import { VerdictCard } from './components/VerdictCard';
import { EvidenceList } from './components/EvidenceList';
import { HypothesesPanel } from './components/HypothesesPanel';
import { ContradictionsPanel } from './components/ContradictionsPanel';
import { ReasoningTraceView } from './components/ReasoningTraceView';
import { HistoryView } from './components/HistoryView';
import { RedTeamModal } from './components/RedTeamModal';
import { NodeDetailModal } from './components/NodeDetailModal';
import { streamVerification } from './services/api';
import { StreamProgressEvent, VerificationResult } from './types/falsify';
import { ArrowLeft, RefreshCw, ShieldAlert } from 'lucide-react';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<CanvasTab>('console');
  const [isStreaming, setIsStreaming] = useState(false);
  const [progressStages, setProgressStages] = useState<StreamProgressEvent[]>([]);
  const [latestMessage, setLatestMessage] = useState<string>('');
  const [streamError, setStreamError] = useState<string | null>(null);
  const [currentResult, setCurrentResult] = useState<VerificationResult | null>(null);
  const [isHistoricalView, setIsHistoricalView] = useState(false);

  const [isRedTeamOpen, setIsRedTeamOpen] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Reference for stream cancellation (client-side reader abortion)
  const abortControllerRef = useRef<AbortController | null>(null);

  const handleStartVerification = useCallback(async (claim: string) => {
    // Reset previous run state
    setIsStreaming(true);
    setProgressStages([]);
    setLatestMessage('Initializing adversarial verification engine...');
    setStreamError(null);
    setCurrentResult(null);
    setIsHistoricalView(false);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      await streamVerification(
        claim,
        {
          onStarted: (event) => {
            setLatestMessage(event.message || 'Verification started');
          },
          onProgress: (event) => {
            setProgressStages((prev) => [...prev, event]);
            setLatestMessage(event.message || `Stage: ${event.stage}`);
          },
          onCompleted: (event) => {
            setCurrentResult(event.result);
            setIsStreaming(false);
            setLatestMessage('Verification completed successfully.');
          },
          onError: (event) => {
            setStreamError(event.message || 'Verification encountered an error.');
            setIsStreaming(false);
          },
        },
        controller.signal
      );
    } catch (err: any) {
      if (err.name === 'AbortError') {
        setStreamError('Verification stream was cancelled by user. (Note: backend processing may still finish).');
      } else {
        setStreamError(err.message || 'Network error or connection lost while streaming verification.');
      }
      setIsStreaming(false);
    } finally {
      abortControllerRef.current = null;
    }
  }, []);

  const handleCancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsStreaming(false);
      setStreamError('Verification stream consumption was cancelled by the user.');
    }
  }, []);

  const handleOpenHistoricalResult = (result: VerificationResult) => {
    setCurrentResult(result);
    setIsHistoricalView(true);
    setIsStreaming(false);
    setProgressStages([]);
    setStreamError(null);
    setActiveTab('console');
  };

  const handleResetToNewVerification = () => {
    setCurrentResult(null);
    setIsHistoricalView(false);
    setProgressStages([]);
    setStreamError(null);
    setLatestMessage('');
  };

  const hasContradictions =
    (currentResult?.contradictions && currentResult.contradictions.length > 0) ||
    currentResult?.verdict === 'REFUTED' ||
    currentResult?.verdict === 'CONFLICTED';

  return (
    <div
      className="min-h-screen bg-[#070a11] text-slate-100 flex flex-col font-mono cyber-grid-bg selection:bg-cyan-500/30 selection:text-cyan-200"
    >
      {/* 1. Cyber Command Top Bar */}
      <CanvasHeader
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        onDeployRedTeam={() => setIsRedTeamOpen(true)}
        isStreaming={isStreaming}
        result={currentResult}
        hasContradictions={hasContradictions}
      />

      {/* 2. Main Workspace Area */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-5">
        {/* Historical Result Banner if viewing past record */}
        {isHistoricalView && currentResult && (
          <div className="mb-5 p-3.5 bg-amber-950/60 border border-amber-500/60 rounded-xl flex items-center justify-between shadow-[0_0_15px_rgba(245,158,11,0.25)]">
            <div className="flex items-center gap-3">
              <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0" />
              <div>
                <span className="text-xs font-bold text-amber-200">
                  Viewing Persisted Verification Record #{currentResult.id ?? currentResult.claim_id}
                </span>
                <p className="text-[11px] text-amber-400/80">
                  This is a stored historical result retrieved from the database without re-executing verification.
                </p>
              </div>
            </div>
            <button
              onClick={() => setActiveTab('history')}
              className="inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg bg-amber-900/80 hover:bg-amber-800 text-amber-200 border border-amber-600 transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Return to History
            </button>
          </div>
        )}

        {/* Action Header when result exists */}
        {currentResult && (
          <div className="mb-4 flex items-center justify-between">
            <div className="text-xs text-slate-400">
              Active Synthesis: <span className="text-cyan-300 font-bold">{currentResult.claim_text}</span>
            </div>
            <button
              onClick={handleResetToNewVerification}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-bold text-cyan-300 bg-cyan-950/70 hover:bg-cyan-900/80 border border-cyan-700/60 rounded-lg shadow-[0_0_10px_rgba(6,182,212,0.3)] transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5 text-cyan-400" />
              <span>New Verification</span>
            </button>
          </div>
        )}

        {/* View Switcher based on Active Tab */}
        {activeTab === 'history' ? (
          <HistoryView onOpenResult={handleOpenHistoricalResult} />
        ) : activeTab === 'stress' ? (
          <div className="space-y-6">
            <HypothesesPanel
              hypotheses={currentResult?.hypotheses || []}
              queries={currentResult?.queries || (currentResult as any)?.generated_queries || []}
            />
          </div>
        ) : activeTab === 'evidence' ? (
          <div className="space-y-6">
            <EvidenceList
              evidenceList={currentResult?.evidence || []}
              assessments={currentResult?.assessments || []}
            />
          </div>
        ) : activeTab === 'audit' ? (
          <div className="space-y-6">
            {/* About & Methodology Card */}
            <div className="bg-[#080c16] rounded-2xl border border-[#141d2f] p-6 shadow-[0_15px_40px_rgba(0,0,0,0.85)] font-mono">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_#00f5d4]" />
                <h2 className="text-base font-bold text-white tracking-wide">Falsify Autonomous Epistemic Engine</h2>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed mb-4">
                Falsify operates under Karl Popper&apos;s classical doctrine of falsificationism: a scientific statement or corporate assertion cannot be verified purely through confirmation bias. Instead, our autonomous multi-agent red team actively formulates counter-hypotheses, discovers contradictory empirical evidence across tier-1 databases, and subjects claims to adversarial stress tests.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
                <div className="bg-[#0c1322] border border-[#1b2538] rounded-xl p-3">
                  <span className="text-emerald-400 font-bold block mb-1">DISCOVER &amp; RETRIEVE</span>
                  <span className="text-slate-400 text-[11px]">Multi-source crawler scanning official registers, regulatory archives, and academic databases.</span>
                </div>
                <div className="bg-[#0c1322] border border-[#1b2538] rounded-xl p-3">
                  <span className="text-cyan-400 font-bold block mb-1">ATTACK &amp; HYPOTHESIZE</span>
                  <span className="text-slate-400 text-[11px]">Generates targeted edge-case counter-claims designed to break the input assertion.</span>
                </div>
                <div className="bg-[#0c1322] border border-[#1b2538] rounded-xl p-3">
                  <span className="text-purple-400 font-bold block mb-1">DIAGNOSE &amp; CONTRADICT</span>
                  <span className="text-slate-400 text-[11px]">Calculates mathematical divergence and identifies direct empirical contradictions.</span>
                </div>
              </div>
            </div>

            {currentResult && (
              <>
                <ContradictionsPanel
                  contradictions={currentResult.contradictions || []}
                  fusion={currentResult.fusion ?? (currentResult as any)?.fusion_output}
                />
                <ReasoningTraceView
                  trace={currentResult.reasoning_trace}
                  fullResult={currentResult}
                />
              </>
            )}
          </div>
        ) : (
          /* Default: Console View (Matches the Reference Image Exactly) */
          <div className="space-y-5">
            {/* Claim Input Form (Visible if no result or verifying new claim) */}
            {!currentResult && (
              <ClaimInput
                onVerify={handleStartVerification}
                onCancelStream={handleCancelStream}
                isStreaming={isStreaming}
                errorMessage={streamError}
              />
            )}

            {/* Live Progress Timeline Panel */}
            {(isStreaming || progressStages.length > 0 || (streamError && !currentResult)) && (
              <ProgressPanel
                stages={progressStages}
                latestMessage={latestMessage}
                isStreaming={isStreaming}
                errorMessage={streamError}
                onCancelStream={handleCancelStream}
              />
            )}

            {/* The Central Hero: Falsification Topology Graph */}
            <FalsificationTopologyGraph
              result={currentResult}
              isStreaming={isStreaming}
              onSelectNode={(nodeId) => setSelectedNodeId(nodeId)}
            />

            {/* If a verification result is present, also render full comprehensive sections below */}
            {currentResult && (
              <section aria-label="Verification Result" className="space-y-6 pt-5 mt-5 border-t border-[#1b2538]">
                {/* 1. Verdict & Multi-Factor Confidence Breakdown */}
                <VerdictCard result={currentResult} />

                {/* 2. Retrieved Evidence & Source Tiers */}
                <EvidenceList
                  evidenceList={currentResult.evidence || []}
                  assessments={currentResult.assessments || []}
                />

                {/* 3. Adversarial Hypotheses & Generated Queries */}
                <HypothesesPanel
                  hypotheses={currentResult.hypotheses || []}
                  queries={currentResult.queries || (currentResult as any).generated_queries || []}
                />

                {/* 4. Contradictions & Evidence Fusion */}
                <ContradictionsPanel
                  contradictions={currentResult.contradictions || []}
                  fusion={currentResult.fusion ?? (currentResult as any).fusion_output}
                />

                {/* 5. Reasoning Trace & Raw JSON Export */}
                <ReasoningTraceView
                  trace={currentResult.reasoning_trace}
                  fullResult={currentResult}
                />
              </section>
            )}
          </div>
        )}
      </main>

      {/* Deploy Red Team Modal */}
      <RedTeamModal
        isOpen={isRedTeamOpen}
        onClose={() => setIsRedTeamOpen(false)}
        onDeploy={handleStartVerification}
        isStreaming={isStreaming}
      />

      {/* 6. Topology Node Inspection Modal */}
      <NodeDetailModal
        nodeId={selectedNodeId}
        onClose={() => setSelectedNodeId(null)}
        result={currentResult}
        onNavigateTab={setActiveTab}
      />
    </div>
  );
};
