import { useState } from 'react';
import { TopBar } from './components/layout/TopBar';
import { ModeToggle } from './components/landing/ModeToggle';
import { Hero } from './components/landing/Hero';
import { InvestigationForm } from './components/landing/InvestigationForm';
import { InvestigationResults } from './components/landing/InvestigationResults';
import { RecentCases } from './components/landing/RecentCases';
import { ErrorBanner } from './components/ui/ErrorBanner';
import { InvestigationApiError, startInvestigation } from './lib/investigationApi';
import type { InterfaceMode, InvestigationCase, InvestigationResult } from './types';

function App() {
  const [mode, setMode] = useState<InterfaceMode>('sherlock');
  const [problemDescription, setProblemDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // No backend-backed history yet — Recent Cases stays empty until that
  // exists. This is separate from `result`, which is this session's most
  // recent investigation, shown as its own section below.
  const cases: InvestigationCase[] = [];

  async function handleStartInvestigation(description: string) {
    setIsSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const investigation = await startInvestigation(description);
      setResult(investigation);
    } catch (err) {
      const message =
        err instanceof InvestigationApiError
          ? err.message
          : 'Something went wrong starting the investigation.';
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-case-bg">
      <TopBar>
        <ModeToggle value={mode} onChange={setMode} />
      </TopBar>

      <main className="mx-auto flex max-w-content flex-col items-center gap-16 px-6 pb-24 pt-16 sm:pt-24">
        <Hero />

        <InvestigationForm
          value={problemDescription}
          onChange={setProblemDescription}
          onSubmit={handleStartInvestigation}
          isSubmitting={isSubmitting}
        />

        {error ? <ErrorBanner message={error} /> : null}
        {result ? <InvestigationResults result={result} /> : null}

        <RecentCases cases={cases} />
      </main>
    </div>
  );
}

export default App;
