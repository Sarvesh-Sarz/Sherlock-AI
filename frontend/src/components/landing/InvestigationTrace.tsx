import type { TraceEvent, TraceStage } from '../../types';

interface InvestigationTraceProps {
  trace: TraceEvent[];
}

const STAGE_LABELS: Record<TraceStage, string> = {
  plan: 'Plan',
  collect: 'Collect',
  assess: 'Assess',
  research: 'Research',
  reason: 'Reason',
};

/**
 * The investigation timeline as plain text: what Sherlock did, in order,
 * and why. Rendered straight from the backend `trace`; nothing is
 * inferred. Only a follow-up decision (evidence changed the plan) gets
 * visual emphasis.
 */
export function InvestigationTrace({ trace }: InvestigationTraceProps) {
  if (trace.length === 0) {
    return null;
  }

  const startedAt = new Date(trace[0].timestamp).getTime();
  const rounds = trace.filter((event) => event.stage === 'collect').length;
  const followUps = trace.reduce((count, event) => count + stringList(event.details.follow_up_tools).length, 0);

  return (
    <section aria-labelledby="trace-heading" className="mb-8">
      <div className="mb-3 flex items-baseline justify-between gap-4">
        <h3 id="trace-heading" className="text-sm font-medium text-case-muted">
          How Sherlock investigated
        </h3>
        <p className="text-xs text-case-faint">
          {rounds} {rounds === 1 ? 'round' : 'rounds'} of checks
          {followUps > 0 ? `, ${followUps} added by evidence` : ''}
        </p>
      </div>

      <ol className="divide-y divide-case-border rounded-lg border border-case-border bg-case-surface">
        {trace.map((event, index) => (
          <TraceRow
            key={`${event.stage}-${index}`}
            event={event}
            offset={formatOffset(new Date(event.timestamp).getTime() - startedAt)}
          />
        ))}
      </ol>
    </section>
  );
}

function TraceRow({ event, offset }: { event: TraceEvent; offset: string }) {
  const followUps = stringList(event.details.follow_up_tools);
  const isDecision = event.stage === 'assess' && followUps.length > 0;
  const notRun = event.details.iteration_limit_reached === true ? stringList(event.details.not_run) : [];

  return (
    <li className="grid grid-cols-[4.5rem_1fr_auto] gap-x-4 px-5 py-3">
      <span className="text-sm text-case-text">{STAGE_LABELS[event.stage] ?? event.stage}</span>

      <div className="min-w-0">
        {isDecision ? (
          <FollowUp event={event} />
        ) : (
          <p className="text-sm text-case-muted">{event.message}</p>
        )}

        {event.stage === 'collect' ? <ToolOutcomes details={event.details} /> : null}
        {!isDecision && notRun.length > 0 ? (
          <p className="mt-1 text-xs text-case-faint">Not run: {notRun.join(', ')}.</p>
        ) : null}
      </div>

      <span className="font-mono text-xs text-case-faint">{offset}</span>
    </li>
  );
}

/** Evidence changed the plan: the reason for each added check, in brass. */
function FollowUp({ event }: { event: TraceEvent }) {
  const reasons = stringList(event.details.reasons);
  const notRun = event.details.iteration_limit_reached === true ? stringList(event.details.not_run) : [];

  return (
    <div className="border-l-2 border-case-brass pl-3">
      <p className="text-sm text-case-brass">The evidence called for more checks:</p>
      <ul className="mt-1 flex flex-col gap-1">
        {reasons.map((reason) => {
          const [tool, ...rest] = reason.split(': ');
          return (
            <li key={reason} className="text-sm text-case-muted">
              <span className="font-mono text-case-text">{tool}</span>, {rest.join(': ')}
            </li>
          );
        })}
      </ul>
      {notRun.length > 0 ? (
        <p className="mt-1 text-xs text-case-faint">Iteration limit reached, so these were not run: {notRun.join(', ')}.</p>
      ) : null}
    </div>
  );
}

/** One line per collection round; failed and unavailable tools are never presented as normal. */
function ToolOutcomes({ details }: { details: Record<string, unknown> }) {
  const results = (details.results ?? {}) as Record<string, string>;
  const parts = [
    ...Object.entries(results).map(([tool, status]) =>
      status === 'success' ? tool : `${tool} (failed, result unknown)`,
    ),
    ...stringList(details.skipped).map((tool) => `${tool} (unavailable)`),
  ];
  if (parts.length === 0) {
    return null;
  }
  return <p className="mt-1 font-mono text-xs text-case-faint">{parts.join(', ')}</p>;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

function formatOffset(ms: number): string {
  if (!Number.isFinite(ms) || ms < 1) {
    return '0 ms';
  }
  return ms < 1000 ? `+${Math.round(ms)} ms` : `+${(ms / 1000).toFixed(1)} s`;
}
