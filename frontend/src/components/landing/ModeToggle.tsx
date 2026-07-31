import type { InterfaceMode } from '../../types';

interface ModeToggleProps {
  value: InterfaceMode;
  onChange: (mode: InterfaceMode) => void;
}

const OPTIONS: { value: InterfaceMode; label: string }[] = [
  { value: 'professional', label: 'Professional' },
  { value: 'sherlock', label: 'Sherlock' },
];

/**
 * Two-way segmented control for switching the interface's voice between
 * a plain "professional" register and the "sherlock" investigation theme.
 * Purely presentational — the parent owns and persists the value.
 */
export function ModeToggle({ value, onChange }: ModeToggleProps) {
  return (
    <div
      role="radiogroup"
      aria-label="Interface mode"
      className="inline-flex rounded-md border border-case-border bg-case-surface p-1"
    >
      {OPTIONS.map((option) => {
        const isActive = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={isActive}
            onClick={() => onChange(option.value)}
            className={`rounded px-3 py-1.5 text-xs font-medium transition-colors duration-150 ${
              isActive
                ? 'bg-case-brass text-case-bg'
                : 'text-case-muted hover:text-case-text'
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
