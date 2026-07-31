import type { ReactNode } from 'react';

interface TopBarProps {
  children: ReactNode;
}

/**
 * Top-level app bar: small wordmark on the left, arbitrary controls
 * (currently the mode toggle) on the right. Not a nav bar — there is
 * nothing to navigate to yet.
 */
export function TopBar({ children }: TopBarProps) {
  return (
    <header className="flex items-center justify-between px-8 py-6 sm:px-12">
      <span className="text-sm font-medium tracking-wide text-case-muted">
        Sherlock AI
      </span>
      {children}
    </header>
  );
}
