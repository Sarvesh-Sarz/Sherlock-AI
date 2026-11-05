import { Fingerprint } from 'lucide-react';
import { STATUS_LABELS } from '../../lib/caseStatus';
import { EmptyState } from '../ui/EmptyState';
import type { CaseSummary } from '../../types';

interface RecentCasesProps {
  cases: CaseSummary[];
  /** Case currently shown in the results view, if any. */
  selectedId?: string | null;
  /** True while a saved case is being fetched. */
  isOpening?: boolean;
  /** Set when the list itself could not be loaded. */
  error?: string | null;
  onSelect: (caseId: string) => void;
  onRetry?: () => void;
}

/**
 * Recent Cases: the saved history from the backend, newest first.
 * Selecting a row reopens that case's full results, trace and report.
 */
export function RecentCases({ cases, selectedId, isOpening = false, error, onSelect, onRetry }: RecentCasesProps) {
  return (
    <section className="w-full" aria-labelledby="recent-cases-heading">
      <h2 id="recent-cases-heading" className="mb-4 text-sm font-medium text-case-muted">
        Recent Cases
      </h2>

      {error ? (
        <div className="rounded-lg border border-case-border bg-case-surface px-4 py-3 text-sm text-case-muted">
          <p>{error}</p>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="mt-2 text-case-brass underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-case-brass"
            >
              Try again
            </button>
          ) : null}
        </div>
      ) : cases.length === 0 ? (
        <EmptyState
          icon={Fingerprint}
          title="No investigations yet."
          description="Open a case above and it will show up here."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {cases.map((investigation) => {
            const isSelected = investigation.case_id === selectedId;
            return (
              <li key={investigation.case_id}>
                <button
                  type="button"
                  onClick={() => onSelect(investigation.case_id)}
                  disabled={isOpening}
                  aria-current={isSelected ? 'true' : undefined}
                  className={`grid w-full grid-cols-[1fr_auto] items-baseline gap-x-4 rounded-lg border bg-case-surface px-4 py-3 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-case-brass disabled:cursor-wait disabled:opacity-70 ${
                    isSelected ? 'border-case-brass' : 'border-case-border hover:border-case-border-strong'
                  }`}
                >
                  <span className="truncate text-sm text-case-text">{investigation.problem_description}</span>
                  <span className="text-xs text-case-faint">{formatWhen(investigation.created_at)}</span>
                  <span
                    className={`mt-0.5 text-xs ${investigation.status === 'failed' ? 'text-case-danger' : 'text-case-muted'}`}
                  >
                    {STATUS_LABELS[investigation.status] ?? investigation.status}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

const RELATIVE = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });

function formatWhen(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  if (Number.isNaN(date.getTime())) {
    return isoTimestamp;
  }
  const seconds = Math.round((date.getTime() - Date.now()) / 1000);
  const abs = Math.abs(seconds);
  if (abs < 60) return RELATIVE.format(0, 'second');
  if (abs < 3600) return RELATIVE.format(Math.round(seconds / 60), 'minute');
  if (abs < 86400) return RELATIVE.format(Math.round(seconds / 3600), 'hour');
  if (abs < 7 * 86400) return RELATIVE.format(Math.round(seconds / 86400), 'day');
  return date.toLocaleDateString();
}
