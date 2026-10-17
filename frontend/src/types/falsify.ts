/**
 * TypeScript definitions mirroring Falsify backend schemas and result models.
 */

export type Verdict =
  | 'VERIFIED'
  | 'QUALIFIED'
  | 'CONFLICTED'
  | 'REFUTED'
  | 'UNVERIFIABLE';

export type Severity = 'low' | 'medium' | 'high' | 'critical';

export type SourceTier = 1 | 2 | 3 | 0;

export interface QuantitativeConstraint {
  metric?: string | null;
  raw_value: string;
  value?: number | null;
  unit?: string | null;
  direction?: string | null;
  comparator?: string | null;
}

export interface Claim {
  claim_id: string;
  original_text: string;
  normalized_text: string;
  claim_kind: string;
  entities: string[];
  predicates: string[];
  temporal_constraints: string[];
  geographic_constraints: string[];
  quantitative_constraints: QuantitativeConstraint[];
}

export interface FalsificationHypothesis {
  hypothesis_id: string;
  claim_id: string;
  category: string;
  hypothesis: string;
  rationale: string;
  falsification_target: string;
  priority: number;
  origin?: string;
}

export interface SearchQuery {
  query_id: string;
  hypothesis_id: string;
  claim_id: string;
  query: string;
  query_type: string;
  rationale: string;
}

export interface Evidence {
  evidence_id: string;
  query_id?: string | null;
  source_url: string;
  title: string;
  publisher: string;
  domain: string;
  retrieved_text: string;
  relevant_passages: string[];
  publication_date?: string | null;
  score?: number | null;
}

export interface EvidenceAssessment {
  evidence_id: string;
  supports_claim: boolean;
  contradicts_claim: boolean;
  stance: 'supporting' | 'contradicting' | 'neutral' | 'mixed' | string;
  relevance_score: number;
  source_quality_score: number;
  source_tier: SourceTier;
  temporal_validity: number;
  is_direct: boolean;
  observed_value?: string | null;
  reasoning: string;
}

export interface Contradiction {
  contradiction_id: string;
  claim_id: string;
  evidence_ids: string[];
  contradiction_type: string;
  severity: Severity;
  explanation: string;
}

export interface ConfidenceBreakdown {
  evidence_quality: number;
  evidence_relevance: number;
  source_independence: number;
  cross_source_agreement: number;
  contradiction_strength: number;
  temporal_validity: number;
  retrieval_coverage: number;
  decisiveness_margin: number;
  weighted_total: number;
  factors?: Record<string, number>;
}

export interface FusionSummary {
  supporting_evidence: number;
  contradicting_evidence: number;
  neutral_evidence: number;
  total_evidence: number;
  independent_supporting_clusters: number;
  independent_contradicting_clusters: number;
  support_strength: number;
  contradict_strength: number;
  max_support_quality: number;
  max_contradict_quality: number;
  duplicated_evidence_detected: number;
  coverage: number;
}

export interface HypothesisTraceEntry {
  hypothesis_id: string;
  hypothesis: string;
  category: string;
  priority: number;
  tested: boolean;
  queries_run: number;
  evidence_found: number;
  outcome: 'falsified' | 'challenged' | 'survived' | 'no_evidence' | 'not_tested' | string;
}

export interface QueryTraceEntry {
  query_id: string;
  query: string;
  hypothesis: string;
  purpose: string;
  query_type: string;
  results_found: number;
}

export interface EvidenceTraceEntry {
  evidence_id: string;
  url: string;
  title: string;
  publisher: string;
  source_tier: SourceTier;
  stance: string;
  relevance_score: number;
  source_quality_score: number;
  temporal_validity: number;
  is_direct: boolean;
  reasoning: string;
  key_passage?: string;
}

export interface ContradictionTraceEntry {
  contradiction_id: string;
  type: string;
  severity: Severity;
  explanation: string;
  evidence_urls: string[];
}

export interface ReasoningTrace {
  claim: string;
  normalized_claim: string;
  claim_kind: string;
  hypotheses: HypothesisTraceEntry[];
  queries: QueryTraceEntry[];
  evidence_summary: Record<string, number>;
  evidence: EvidenceTraceEntry[];
  contradictions: ContradictionTraceEntry[];
  fusion?: FusionSummary | null;
  verdict: Verdict;
  confidence: number;
  confidence_explanation: string;
  reasoning: string;
  errors: string[];
  stage_timings_ms: Record<string, number>;
}

export interface PipelineError {
  stage: string;
  error_type: string;
  message: string;
  query?: string | null;
}

export interface VerificationResult {
  verification_id?: number;
  generated_queries: SearchQuery[];
  fusion_output?: FusionSummary | null;
  id?: number;
  claim_id: string;
  claim_text: string;
  verdict: Verdict;
  confidence: number;
  confidence_explanation: string;
  confidence_breakdown: ConfidenceBreakdown;
  claim: Claim;
  hypotheses: FalsificationHypothesis[];
  queries: SearchQuery[];
  evidence: Evidence[];
  assessments: EvidenceAssessment[];
  contradictions: Contradiction[];
  fusion: FusionSummary;
  reasoning_trace: ReasoningTrace;
  errors: PipelineError[];
  created_at?: string;
  engine_version?: string;
  llm_used?: boolean;
  retrieval_provider?: string;
}

export interface VerificationHistoryItem {
  id: number;
  claim_id?: string | null;
  claim_text: string;
  verdict: Verdict;
  confidence: number;
  created_at: string;
}

export interface PaginatedVerificationHistory {
  items: VerificationHistoryItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface HealthResponse {
  status: string;
  app_name: string;
  app_version: string;
  engine_version: string;
  retrieval_provider: string;
  llm_configured: boolean;
  timestamp: string;
}

export interface StreamStartedEvent {
  message: string;
  claim: string;
}

export interface StreamProgressEvent {
  stage: string;
  message: string;
  progress: number;
}

export interface StreamCompletedEvent {
  verification_id: number;
  verdict: Verdict;
  confidence: number;
  result: VerificationResult;
}

export interface StreamErrorEvent {
  error?: string;
  code: string;
  message: string;
}
