import type { CaseStatus } from '../types';

/** Human-readable label for each backend case status. */
export const STATUS_LABELS: Record<CaseStatus, string> = {
  received: 'Received',
  planning: 'Planning',
  investigating: 'Investigating',
  reasoning: 'Reasoning',
  reporting: 'Reporting',
  // The backend sets this when a report has been produced. It does NOT mean
  // the problem was fixed, so it must not read as "Resolved".
  resolved: 'Report ready',
  failed: 'Failed',
};
