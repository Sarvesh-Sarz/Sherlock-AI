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
  message?: string;
}
