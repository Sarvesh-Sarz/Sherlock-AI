import type { FormEvent } from 'react';
import { Search } from 'lucide-react';
import { Button } from '../ui/Button';

interface InvestigationFormProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (value: string) => void;
}

/**
 * The main call-to-action: a case-intake textarea plus the "Start
 * Investigation" button. Submission is lifted to the parent via
 * onSubmit — this component has no idea what happens after that,
 * since there's no backend to send it to yet.
 */
export function InvestigationForm({ value, onChange, onSubmit }: InvestigationFormProps) {
  const isEmpty = value.trim().length === 0;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (isEmpty) return;
    onSubmit(value.trim());
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full flex-col items-center gap-5">
      <div className="w-full">
        <label
          htmlFor="problem-description"
          className="mb-3 block text-center text-lg text-case-text"
        >
          What seems to be the problem today?
        </label>
        <div className="flex items-start gap-3 rounded-lg border border-case-border bg-case-surface px-4 py-4 transition-colors duration-150 focus-within:border-case-border-strong">
          <Search className="mt-0.5 h-4 w-4 shrink-0 text-case-faint" strokeWidth={1.5} aria-hidden="true" />
          <textarea
            id="problem-description"
            name="problem-description"
            rows={2}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder="My laptop becomes slow after startup."
            className="w-full resize-none bg-transparent text-base text-case-text placeholder:text-case-faint focus:outline-none"
          />
        </div>
      </div>

      <Button type="submit" disabled={isEmpty}>
        Start Investigation
      </Button>
    </form>
  );
}
