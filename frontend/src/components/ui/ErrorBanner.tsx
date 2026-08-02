import { AlertTriangle } from 'lucide-react';

interface ErrorBannerProps {
  message: string;
}

/**
 * A single inline error banner, shown when starting an investigation
 * fails outright (backend unreachable, unexpected server error). Styled
 * as plainly as the rest of the app — a hairline border and an icon,
 * not a loud alert box — so a failure doesn't break the page's tone.
 */
export function ErrorBanner({ message }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className="flex w-full items-start gap-3 rounded-lg border border-case-danger bg-case-surface px-4 py-3"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-case-danger" strokeWidth={1.5} aria-hidden="true" />
      <p className="text-sm text-case-text">{message}</p>
    </div>
  );
}
