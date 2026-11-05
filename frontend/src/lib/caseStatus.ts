import type { CaseStatus } from '../types';

/** Human-readable label for each backend case status. */
export const STATUS_LABELS: Record<CaseStatus, string> = {
  received: 'Received',
  planning: 'Planning',
  investigating: 'Investigating',
  reasoning: 'Reasoning',
  reporting: 'Reporting',
  resolved: 'Resolved',
  failed: 'Failed',
};
