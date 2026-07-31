import { Fingerprint } from 'lucide-react';
import { EmptyState } from '../ui/EmptyState';
import type { InvestigationCase } from '../../types';

interface RecentCasesProps {
  cases: InvestigationCase[];
}

/**
 * Recent Cases section. Today `cases` is always an empty array — there is
 * no store or API behind it — but the component is written to render a
 * real list once one exists, rather than only rendering the empty state.
 */
export function RecentCases({ cases }: RecentCasesProps) {
  return (
    <section className="w-full">
      <h2 className="mb-4 text-sm font-medium text-case-muted">Recent Cases</h2>

      {cases.length === 0 ? (
        <EmptyState
          icon={Fingerprint}
          title="No investigations yet."
          description="Open a case above and it will show up here."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {cases.map((investigation) => (
            <li
              key={investigation.id}
              className="rounded-lg border border-case-border bg-case-surface px-4 py-3 text-sm text-case-text"
            >
              {investigation.summary}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
