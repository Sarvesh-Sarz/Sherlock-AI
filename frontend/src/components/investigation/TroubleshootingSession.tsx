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

  const currentRecommendationIndex =
    session?.current_recommendation_index ?? recommendationIndex;

  const currentStepIndex = session?.current_step_index ?? 0;

  const recommendation =
    recommendations[currentRecommendationIndex];

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

  async function handleAnswer(
    result: 'done' | 'could_not_complete',
  ) {
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

  /*
   * No troubleshooting session has started yet.
   */
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

  /*
   * Troubleshooting successfully completed.
   */
  if (session.status === 'resolved') {
    return (
      <div className="mt-5 border-t border-case-border pt-4">
        <p className="text-sm font-medium text-case-brass">
          Troubleshooting completed successfully.
        </p>
      </div>
    );
  }

  /*
   * All available recommendations have been exhausted.
   */
  if (session.status === 'exhausted') {
    return (
      <div className="mt-5 border-t border-case-border pt-4">
        <p className="text-sm font-medium text-case-muted">
          Sherlock reached the end of the available troubleshooting paths.
        </p>
      </div>
    );
  }

  /*
   * Safety checks in case the backend returns an invalid index.
   */
  if (!recommendation) {
    return (
      <div className="mt-5 border-t border-case-border pt-4">
        <p className="text-sm text-red-400">
          Sherlock couldn't find the current troubleshooting recommendation.
        </p>
      </div>
    );
  }

  const currentStep = recommendation.steps[currentStepIndex];

  if (!currentStep) {
    return (
      <div className="mt-5 border-t border-case-border pt-4">
        <p className="text-sm text-red-400">
          Sherlock couldn't find the current troubleshooting step.
        </p>
      </div>
    );
  }

  /*
   * Active troubleshooting step.
   */
  return (
    <div className="mt-5 border-t border-case-border pt-5">
      <div className="mb-4">
        <p className="font-mono text-xs uppercase tracking-wide text-case-faint">
          Guided Troubleshooting
        </p>

        <p className="mt-2 text-sm text-case-muted">
          {recommendation.title}
        </p>

        <p className="mt-1 text-sm text-case-muted">
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
            onClick={() =>
              handleAnswer('could_not_complete')
            }
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