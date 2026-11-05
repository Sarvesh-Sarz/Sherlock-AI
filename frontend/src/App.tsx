import { useCallback, useEffect, useRef, useState } from 'react';
import { TopBar } from './components/layout/TopBar';
import { ModeToggle } from './components/landing/ModeToggle';
import { LandingHeader } from './components/landing/LandingHeader';
import { InvestigationForm } from './components/landing/InvestigationForm';
import { InvestigationResults } from './components/landing/InvestigationResults';
import { RecentCases } from './components/landing/RecentCases';
import { ErrorBanner } from './components/ui/ErrorBanner';
import {
  getInvestigation,
  InvestigationApiError,
  listInvestigations,
  startInvestigation,
} from './lib/investigationApi';
import type { CaseSummary, InterfaceMode, InvestigationResult } from './types';

function describe(err: unknown, fallback: string): string {
  return err instanceof InvestigationApiError ? err.message : fallback;
}

function App() {
  const [mode, setMode] = useState<InterfaceMode>('sherlock');
  const [problemDescription, setProblemDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Saved history from the backend. Separate from `result`, which is the
  // case currently open in the results section (new or reopened).
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [casesError, setCasesError] = useState<string | null>(null);
  const [isOpening, setIsOpening] = useState(false);

  // Only the latest open/start request may update the screen, so a slow
  // earlier response can never overwrite a newer one.
  const latestRequest = useRef(0);
  const resultsRef = useRef<HTMLDivElement>(null);
  const [scrollTick, setScrollTick] = useState(0);

  const loadCases = useCallback(async () => {
    try {
      setCases(await listInvestigations());
      setCasesError(null);
    } catch (err) {
      setCasesError(describe(err, 'Something went wrong loading recent cases.'));
    }
  }, []);

  useEffect(() => {
    void loadCases();
  }, [loadCases]);

  // After a saved case opens, bring its results into view (they render
  // above the history list the user just clicked in).
  useEffect(() => {
    if (scrollTick === 0) return;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    resultsRef.current?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
  }, [scrollTick]);

  async function handleStartInvestigation(description: string) {
    const request = ++latestRequest.current;
    setIsSubmitting(true);
    setIsOpening(false);
    setError(null);
    setResult(null);

    try {
      const investigation = await startInvestigation(description);
      if (request !== latestRequest.current) return;
      setResult(investigation);
      void loadCases();
    } catch (err) {
      if (request !== latestRequest.current) return;
      setError(describe(err, 'Something went wrong starting the investigation.'));
    } finally {
      if (request === latestRequest.current) setIsSubmitting(false);
    }
  }

  async function handleOpenCase(caseId: string) {
    if (isSubmitting) return;
    if (caseId === result?.case_id) {
      setScrollTick((tick) => tick + 1);
      return;
    }

    const request = ++latestRequest.current;
    setIsOpening(true);
    setError(null);

    try {
      const saved = await getInvestigation(caseId);
      if (request !== latestRequest.current) return;
      setResult(saved);
      setScrollTick((tick) => tick + 1);
    } catch (err) {
      if (request !== latestRequest.current) return;
      setError(describe(err, 'Something went wrong opening that investigation.'));
    } finally {
      if (request === latestRequest.current) setIsOpening(false);
    }
  }

  return (
    <div className="min-h-screen bg-case-bg">
      <TopBar>
        <ModeToggle value={mode} onChange={setMode} />
      </TopBar>

      <main className="mx-auto flex max-w-content flex-col items-center gap-16 px-6 pb-24 pt-16 sm:pt-24">
        <LandingHeader />

        <InvestigationForm
          value={problemDescription}
          onChange={setProblemDescription}
          onSubmit={handleStartInvestigation}
          isSubmitting={isSubmitting}
        />

        {error ? <ErrorBanner message={error} /> : null}
        {result ? (
          <div ref={resultsRef} className="w-full scroll-mt-20">
            {/* key: switching cases must reset per-case state such as an open troubleshooting session */}
            <InvestigationResults key={result.case_id} result={result} />
          </div>
        ) : null}

        <RecentCases
          cases={cases}
          selectedId={result?.case_id ?? null}
          isOpening={isOpening}
          error={casesError}
          onSelect={(caseId) => void handleOpenCase(caseId)}
          onRetry={() => void loadCases()}
        />
      </main>
    </div>
  );
}

export default App;
