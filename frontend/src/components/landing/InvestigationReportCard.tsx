import type { InvestigationReport } from '../../types';
import { LabeledValue } from '../ui/LabeledValue';

interface InvestigationReportCardProps {
  report: InvestigationReport;
}

export function InvestigationReportCard({
  report,
}: InvestigationReportCardProps) {
  return (
    <section className="mt-8">
      <h3 className="mb-3 font-mono text-xs uppercase tracking-widest2 text-case-faint">
        Investigation Report
      </h3>

      <div className="flex flex-col gap-6 rounded-lg border border-case-border bg-case-surface px-5 py-5">

        {/* Summary */}
        <div>
          <h4 className="mb-2 text-sm font-medium text-case-text">
            Summary
          </h4>

          <p className="text-sm leading-6 text-case-muted">
            {report.summary}
          </p>
        </div>

        {/* Overall confidence */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <LabeledValue
            label="Confidence"
            value={capitalize(report.confidence)}
          />

          <LabeledValue
            label="Reasoning Method"
            value={report.reasoning_method}
          />

          <LabeledValue
            label="Generated"
            value={formatDate(report.created_at)}
          />
        </div>

        {/* Hypotheses */}
        {report.hypotheses.length > 0 ? (
          <div>
            <h4 className="mb-3 text-sm font-medium text-case-text">
              Hypotheses
            </h4>

            <div className="flex flex-col gap-3">
              {report.hypotheses.map((hypothesis, index) => (
                <div
                  key={`${hypothesis.title}-${index}`}
                  className="rounded-md border border-case-border px-4 py-4"
                >
                  <div className="mb-2 flex items-center justify-between gap-4">
                    <h5 className="text-sm font-medium text-case-text">
                      {hypothesis.title}
                    </h5>

                    <span className="font-mono text-xs uppercase text-case-faint">
                      {hypothesis.confidence}
                    </span>
                  </div>

                  <p className="mb-4 text-sm leading-6 text-case-muted">
                    {hypothesis.explanation}
                  </p>

                  {hypothesis.supporting_evidence.length > 0 ? (
                    <div className="mb-3">
                      <p className="mb-1 text-xs uppercase tracking-wide text-case-faint">
                        Supporting Evidence
                      </p>

                      <ul className="list-disc space-y-1 pl-5 text-sm text-case-muted">
                        {hypothesis.supporting_evidence.map((item, i) => (
                          <li key={i}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {hypothesis.contradicting_evidence.length > 0 ? (
                    <div>
                      <p className="mb-1 text-xs uppercase tracking-wide text-case-faint">
                        Contradicting Evidence
                      </p>

                      <ul className="list-disc space-y-1 pl-5 text-sm text-case-muted">
                        {hypothesis.contradicting_evidence.map((item, i) => (
                          <li key={i}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {/* Recommendations */}
        {report.recommendations.length > 0 ? (
          <div>
            <h4 className="mb-3 text-sm font-medium text-case-text">
              Recommendations
            </h4>

            <div className="flex flex-col gap-3">
              {report.recommendations.map((recommendation, index) => (
                <div
                  key={`${recommendation.title}-${index}`}
                  className="rounded-md border border-case-border px-4 py-4"
                >
                  <div className="mb-2 flex items-center justify-between gap-4">
                    <h5 className="text-sm font-medium text-case-text">
                      {recommendation.title}
                    </h5>

                    <span className="font-mono text-xs uppercase text-case-faint">
                      {recommendation.priority}
                    </span>
                  </div>

                  <p className="mb-4 text-sm leading-6 text-case-muted">
                    {recommendation.reason}
                  </p>

                  <div className="mb-4">
                    <p className="mb-2 text-xs uppercase tracking-wide text-case-faint">
                      What to do
                    </p>

                    <ol className="list-decimal space-y-2 pl-5 text-sm leading-6 text-case-muted">
                      {recommendation.steps.map((step, stepIndex) => (
                        <li key={stepIndex}>{step}</li>
                      ))}
                    </ol>
                  </div>

                  <div>
                    <p className="mb-1 text-xs uppercase tracking-wide text-case-faint">
                      Expected Result
                    </p>

                    <p className="text-sm text-case-muted">
                      {recommendation.expected_result}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {/* Research */}
        {report.research_sources.length > 0 ? (
          <div>
            <h4 className="mb-3 text-sm font-medium text-case-text">
              Research Sources
            </h4>

            <div className="flex flex-col gap-2">
              {report.research_sources.map((source, index) => (
                <a
                  key={`${source.url}-${index}`}
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-case-brass hover:underline"
                >
                  {source.title}
                </a>
              ))}
            </div>
          </div>
        ) : report.research_notice ? (
          <p className="text-xs text-case-faint">
            {report.research_notice}
          </p>
        ) : null}

      </div>
    </section>
  );
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatDate(value: string): string {
  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString();
}