import { BookOpen, GitBranch, Lightbulb, ListChecks, Search } from 'lucide-react';
import type { ComponentType } from 'react';
import type { TraceEvent, TraceStage } from '../../types';

interface InvestigationTraceProps {
  trace: TraceEvent[];
}

const STAGES: Record<
  TraceStage,
  { label: string; Icon: ComponentType<{ className?: string; strokeWidth?: number; 'aria-hidden'?: boolean | 'true' }> }
> = {
  plan: { label: 'Planned', Icon: ListChecks },
  collect: { label: 'Collected evidence', Icon: Search },
  assess: { label: 'Assessed evidence', Icon: GitBranch },
  research: { label: 'Researched', Icon: BookOpen },
  reason: { label: 'Reasoned', Icon: Lightbulb },
};

/**
 * The investigation timeline: what Sherlock did, in order, and why.
 * Rendered straight from the backend `trace` — nothing here is inferred.
 * The one thing given visual weight is a follow-up decision (evidence
 * changed the plan); everything else stays quiet.
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

      <ol className="rounded-lg border border-case-border bg-case-surface px-5 py-5">
        {trace.map((event, index) => (
          <TraceRow
            key={`${event.stage}-${index}`}
            event={event}
            offset={formatOffset(new Date(event.timestamp).getTime() - startedAt)}
            isLast={index === trace.length - 1}
          />
        ))}
      </ol>
    </section>
  );
}

function TraceRow({ event, offset, isLast }: { event: TraceEvent; offset: string; isLast: boolean }) {
  const { label, Icon } = STAGES[event.stage] ?? { label: event.stage, Icon: ListChecks };
  const followUps = stringList(event.details.follow_up_tools);
  const isDecision = event.stage === 'assess' && followUps.length > 0;
  const reasonedFailure = event.stage === 'reason' && event.details.succeeded === false;

  return (
    <li className="relative flex gap-4 pb-6 last:pb-0">
      {!isLast ? (
        <span className="absolute left-[11px] top-7 h-[calc(100%-1.75rem)] w-px bg-case-border" aria-hidden="true" />
      ) : null}

      <span
        className={`relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border ${
          isDecision
            ? 'border-case-brass bg-case-bg text-case-brass'
            : reasonedFailure
              ? 'border-case-danger bg-case-bg text-case-danger'
              : 'border-case-border-strong bg-case-bg text-case-muted'
        }`}
      >
        <Icon className="h-3 w-3" strokeWidth={1.75} aria-hidden="true" />
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <p className="text-sm font-medium text-case-text">{label}</p>
          <span className="font-mono text-xs text-case-faint">{offset}</span>
        </div>

        {isDecision ? <FollowUpCallout event={event} tools={followUps} /> : <p className="mt-1 text-sm text-case-muted">{event.message}</p>}

        {event.stage === 'collect' ? <ToolOutcomes details={event.details} /> : null}
        {event.stage === 'assess' && !isDecision && event.details.iteration_limit_reached === true ? (
          <NotRun tools={stringList(event.details.not_run)} />
        ) : null}
      </div>
    </li>
  );
}

/** Evidence changed the plan: show the reason and the tools it added. */
function FollowUpCallout({ event, tools }: { event: TraceEvent; tools: string[] }) {
  const reasons = stringList(event.details.reasons);
  const notRun = event.details.iteration_limit_reached === true ? stringList(event.details.not_run) : [];

  return (
    <div className="mt-2 rounded-md border border-case-brass-dim bg-case-bg px-4 py-3">
      <p className="mb-2 text-xs text-case-brass">The evidence called for more checks</p>
      <ul className="flex flex-col gap-1.5">
        {reasons.map((reason) => {
          const [tool, ...rest] = reason.split(': ');
          return (
            <li key={reason} className="flex items-baseline gap-2 text-sm text-case-text">
              <span className="shrink-0 rounded bg-case-surface px-1.5 py-0.5 font-mono text-xs text-case-brass">{tool}</span>
              <span className="text-case-muted">{rest.join(': ')}</span>
            </li>
          );
        })}
      </ul>
      {notRun.length > 0 ? (
        <p className="mt-2 text-xs text-case-faint">Iteration limit reached, so these were not run: {notRun.join(', ')}.</p>
      ) : null}
      <span className="sr-only">Added checks: {tools.join(', ')}</span>
    </div>
  );
}

/** One chip per tool in a collection round; failed and unavailable tools are never shown as normal. */
function ToolOutcomes({ details }: { details: Record<string, unknown> }) {
  const results = (details.results ?? {}) as Record<string, string>;
  const skipped = stringList(details.skipped);
  const entries = [
    ...Object.entries(results).map(([tool, status]) => ({ tool, state: status === 'success' ? 'ok' : 'failed' })),
    ...skipped.map((tool) => ({ tool, state: 'skipped' })),
  ];
  if (entries.length === 0) {
    return null;
  }

  const styles = {
    ok: { dot: 'bg-case-brass', text: 'text-case-text', note: '' },
    failed: { dot: 'bg-case-danger', text: 'text-case-danger', note: 'failed, unknown' },
    skipped: { dot: 'bg-case-faint', text: 'text-case-faint', note: 'unavailable' },
  } as const;

  return (
    <ul className="mt-2 flex flex-wrap gap-2">
      {entries.map(({ tool, state }) => (
        <li
          key={`${tool}-${state}`}
          className="flex items-center gap-1.5 rounded-full border border-case-border px-2.5 py-1 text-xs"
        >
          <span className={`h-1.5 w-1.5 rounded-full ${styles[state as keyof typeof styles].dot}`} aria-hidden="true" />
          <span className={`font-mono ${styles[state as keyof typeof styles].text}`}>{tool}</span>
          {styles[state as keyof typeof styles].note ? (
            <span className="text-case-faint">{styles[state as keyof typeof styles].note}</span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function NotRun({ tools }: { tools: string[] }) {
  if (tools.length === 0) {
    return null;
  }
  return <p className="mt-1 text-xs text-case-faint">Not run: {tools.join(', ')}.</p>;
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
