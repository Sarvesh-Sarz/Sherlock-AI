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
