import type { CaseStatus, InvestigationResult } from '../../types';
import { InvestigationReportCard } from './InvestigationReportCard';
import { LabeledValue } from '../ui/LabeledValue';
import { ToolResultCard } from './ToolResultCard';

interface InvestigationResultsProps {
  result: InvestigationResult;
}

const STATUS_LABELS: Record<CaseStatus, string> = {
  received: 'Received',
  planning: 'Planning',
  investigating: 'Investigating',
  reasoning: 'Reasoning',
  reporting: 'Reporting',
  resolved: 'Resolved',
  failed: 'Failed',
};

/**
 * Shown below the intake form once `POST /investigation/start` returns —
 * the case summary (ID, status, problem description) plus a card per
 * piece of evidence collected. Rendered directly from the backend's
 * response; nothing here is inferred or fabricated.
 */
export function InvestigationResults({ result }: InvestigationResultsProps) {
  return (
    <section className="w-full">
      <h2 className="mb-4 text-sm font-medium text-case-muted">Investigation Results</h2>

      <div className="mb-6 flex flex-col gap-4 rounded-lg border border-case-border bg-case-surface px-5 py-5">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <LabeledValue label="Case ID" value={result.case_id} mono />
          <LabeledValue label="Status" value={STATUS_LABELS[result.status] ?? result.status} />
          <LabeledValue label="Started" value={formatDate(result.created_at)} />
        </div>
        <LabeledValue label="Problem Description" value={result.problem_description} />
      </div>

      <h3 className="mb-3 font-mono text-xs uppercase tracking-widest2 text-case-faint">
        Evidence
      </h3>

      {result.evidence.length === 0 ? (
        <p className="text-sm text-case-muted">No evidence was collected for this case.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {result.evidence.map((toolResult, index) => (
            // tool_name is expected to be unique per case today (one run
            // per tool), but indexing the key avoids a collision if a
            // future tool ever reports more than once per investigation.
            <ToolResultCard key={`${toolResult.tool_name}-${index}`} result={toolResult} />
          ))}
        </div>
      )}
      {result.report ? (
        <InvestigationReportCard report={result.report} />
      ) : null}
    </section>
  );
}

function formatDate(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  return Number.isNaN(date.getTime()) ? isoTimestamp : date.toLocaleString();
}
