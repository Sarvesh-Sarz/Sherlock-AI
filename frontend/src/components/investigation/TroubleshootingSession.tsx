import { useState } from 'react';
import type {
  Recommendation,
  TroubleshootingSession as TroubleshootingSessionType,
} from '../../types';
import {
  answerTroubleshootingStep,
  startTroubleshooting,
  InvestigationApiError,
} from '../../lib/investigationApi';

interface TroubleshootingSessionProps {
  caseId: string;
  recommendations: Recommendation[];
  recommendationIndex: number;
}

export function TroubleshootingSession({
  caseId,
  recommendations,
  recommendationIndex,
}: TroubleshootingSessionProps) {
  const [session, setSession] =
    useState<TroubleshootingSessionType | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const recommendation =
    recommendations[session?.current_recommendation_index ?? recommendationIndex];

  const currentStepIndex = session?.current_step_index ?? 0;

  async function handleStart() {
    setLoading(true);
    setError(null);

    try {
      const startedSession = await startTroubleshooting(
        caseId,
        recommendationIndex,
      );

      setSession(startedSession);
    } catch (err) {
      setError(
        err instanceof InvestigationApiError
          ? err.message
          : 'Something went wrong while starting troubleshooting.',
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleAnswer(result: 'done' | 'could_not_complete') {
    setLoading(true);
    setError(null);

    try {
      const updatedSession = await answerTroubleshootingStep(
        caseId,
        result,
      );

      setSession(updatedSession);
    } catch (err) {
      setError(
        err instanceof InvestigationApiError
          ? err.message
          : 'Something went wrong while recording your answer.',
      );
    } finally {
      setLoading(false);
    }
  }

  if (!session) {
    return (
      <div className="mt-5 border-t border-case-border pt-4">
        <button
          type="button"
          onClick={handleStart}
          disabled={loading}
          className="rounded-md border border-case-brass px-4 py-2 text-sm font-medium text-case-brass transition hover:bg-case-brass hover:text-case-surface disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? 'Starting...' : 'Start Guided Troubleshooting'}
        </button>

        {error ? (
          <p className="mt-3 text-sm text-red-400">
            {error}
          </p>
        ) : null}
      </div>
    );
  }

  if (session.status === 'resolved') {
    return (
      <div className="mt-5 border-t border-case-border pt-4">
        <p className="text-sm font-medium text-case-brass">
          Troubleshooting completed successfully.
        </p>
      </div>
    );
  }

  if (session.status === 'could_not_complete') {
    return (
      <div className="mt-5 border-t border-case-border pt-4">
        <p className="text-sm font-medium text-case-muted">
          This troubleshooting path could not be completed.
        </p>
      </div>
    );
  }

  const currentStep = recommendation?.steps[currentStepIndex];

  return (
    <div className="mt-5 border-t border-case-border pt-5">
      <div className="mb-4">
        <p className="font-mono text-xs uppercase tracking-wide text-case-faint">
          Guided Troubleshooting
        </p>

        <p className="mt-2 text-sm text-case-muted">
          Step {currentStepIndex + 1} of {recommendation.steps.length}
        </p>
      </div>

      <div className="rounded-md border border-case-border px-4 py-4">
        <p className="text-sm leading-6 text-case-text">
          {currentStep}
        </p>

        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => handleAnswer('done')}
            disabled={loading}
            className="rounded-md border border-case-brass px-4 py-2 text-sm font-medium text-case-brass transition hover:bg-case-brass hover:text-case-surface disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? 'Saving...' : 'Done'}
          </button>

          <button
            type="button"
            onClick={() => handleAnswer('could_not_complete')}
            disabled={loading}
            className="rounded-md border border-case-border px-4 py-2 text-sm text-case-muted transition hover:border-case-faint disabled:cursor-not-allowed disabled:opacity-50"
          >
            Couldn't Complete
          </button>
        </div>

        {error ? (
          <p className="mt-3 text-sm text-red-400">
            {error}
          </p>
        ) : null}
      </div>
    </div>
  );
}