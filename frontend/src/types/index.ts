/**
 * The interface has two registers:
 * - "professional" — plain, businesslike copy and framing.
 * - "sherlock" — the investigation-themed voice (case files, clues, etc).
 *
 * This only affects wording/presentation in the UI layer. It is not wired
 * to any backend or persisted anywhere yet.
 */
export type InterfaceMode = 'professional' | 'sherlock';

/**
 * Shape of a single past investigation. Nothing in the app currently
 * produces this data — it exists so the Recent Cases list has a real
 * contract to render against once a backend is connected.
 */
export interface InvestigationCase {
  id: string;
  summary: string;
  createdAt: string;
  status: 'open' | 'resolved';
}

export type RecommendationPriority = 'high' | 'medium' | 'low';

export interface Recommendation {
  title: string;
  reason: string;
  steps: string[];
  expected_result: string;
  priority: RecommendationPriority;
}
/**
 * Mirrors `app.models.investigation.CaseStatus` on the backend. Kept as a
 * plain string union rather than a TS enum since that's all a JSON field
 * ever is on the wire.
 */
export type CaseStatus =
  | 'received'
  | 'planning'
  | 'investigating'
  | 'reasoning'
  | 'reporting'
  | 'resolved'
  | 'failed';

/** Mirrors `app.models.tool_result.ToolStatus`. */
export type ToolStatus = 'success' | 'error';

/**
 * Mirrors `app.models.tool_result.ToolResult` — the uniform shape every
 * backend diagnostic tool returns (cpu today; memory, disk, battery,
 * wifi, startup later). `payload` is intentionally untyped here for the
 * same reason it's untyped on the backend: each tool's contents differ,
 * and this contract is what stays constant across all of them.
 */
export interface ToolResult {
  tool_name: string;
  status: ToolStatus;
  collected_at: string;
  payload: Record<string, unknown>;
}

/** Payload shape for the `cpu` tool specifically, used only for display. */
export interface CpuPayload {
  usage_percent: number;
  physical_cores: number | null;
  logical_cores: number | null;
  current_frequency: number | null;
  max_frequency: number | null;
}

/** Payload shape for the `memory` tool specifically, used only for display. */
export interface MemoryPayload {
  total_gb: number;
  available_gb: number;
  used_gb: number;
  usage_percent: number;
  swap_total_gb: number;
  swap_used_gb: number;
}

/**
 * A single volume within the `disk` tool's payload — one per usable
 * local drive/partition (e.g. `C:\`, `D:\`).
 */
export interface DiskVolume {
  mountpoint: string;
  total_gb: number;
  used_gb: number;
  free_gb: number;
  usage_percent: number;
  filesystem: string | null;
}

/**
 * Payload shape for the `disk` tool specifically, used only for
 * display. A machine can have more than one local volume (this is the
 * whole reason the payload is a list rather than a single set of
 * fields — see `app.tools.disk` on the backend), so `volumes` can be
 * empty (no usable local volumes found) but is never itself missing.
 */
export interface DiskPayload {
  volumes: DiskVolume[];
}

/**
 * A single startup-entry source, mirroring `app.tools.startup`'s four
 * fixed sources on the backend.
 */
export type StartupSource = 'user_run' | 'machine_run' | 'user_startup_folder' | 'common_startup_folder';

/** A single autostart entry within the `startup` tool's payload. */
export interface StartupEntry {
  name: string;
  command: string;
  source: StartupSource;
}

/** A source the `startup` tool couldn't read, and why. */
export interface StartupUnavailableSource {
  source: string;
  reason: string;
}

/**
 * Payload shape for the `startup` tool specifically, used only for
 * display. `entries` is not deduplicated across sources on the backend
 * (the same program can legitimately appear from more than one
 * mechanism), so it isn't here either.
 */
export interface StartupPayload {
  total_entries: number;
  entries: StartupEntry[];
  sources_unavailable: StartupUnavailableSource[];
}

/**
 * Mirrors `InvestigationResponse` from `POST /investigation/start`
 * (and, with the same fields present, `InvestigationStatus` from
 * `GET /investigation/{case_id}`).
 */
export interface InvestigationResult {
  case_id: string;
  status: CaseStatus;
  problem_description: string;
  created_at: string;
  evidence: ToolResult[];
  report?: InvestigationReport;
  message?: string;
}


export type Confidence = 'low' | 'medium' | 'high';

export interface ResearchSource {
  title: string;
  url: string;
  content?: string;
}

export interface Hypothesis {
  title: string;
  explanation: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  confidence: Confidence;
}

export interface InvestigationReport {
  case_id: string;
  problem_description: string;
  summary: string;
  hypotheses: Hypothesis[];
  evidence_used: ToolResult[];
  recommendations: Recommendation[];
  confidence: Confidence;
  research_sources: ResearchSource[];
  research_notice?: string | null;
  reasoning_method: string;
  created_at: string;
}