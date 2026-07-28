import { useState } from 'react';
import { TopBar } from './components/layout/TopBar';
import { ModeToggle } from './components/landing/ModeToggle';
import { Hero } from './components/landing/Hero';
import { InvestigationForm } from './components/landing/InvestigationForm';
import { RecentCases } from './components/landing/RecentCases';
import type { InterfaceMode, InvestigationCase } from './types';

function App() {
  const [mode, setMode] = useState<InterfaceMode>('sherlock');
  const [problemDescription, setProblemDescription] = useState('');

  // No backend yet, so there is nothing to populate this with.
  const cases: InvestigationCase[] = [];

  function handleStartInvestigation(description: string) {
    // Intentionally a no-op for now — wiring this up to a real
    // investigation pipeline is out of scope for the frontend foundation.
    console.log('Investigation requested:', description);
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
        />

        <RecentCases cases={cases} />
      </main>
    </div>
  );
}

export default App;
