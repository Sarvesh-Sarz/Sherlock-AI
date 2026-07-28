import type { ButtonHTMLAttributes, ReactNode } from 'react';

type ButtonVariant = 'primary' | 'secondary';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: ButtonVariant;
}

const baseStyles =
  'inline-flex items-center justify-center gap-2 rounded-md px-5 py-2.5 text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40';

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    'bg-case-brass text-case-bg hover:bg-case-brass-hover disabled:hover:bg-case-brass',
  secondary:
    'bg-transparent text-case-text border border-case-border hover:border-case-border-strong hover:bg-case-surface',
};

/**
 * Single button primitive for the app. Keep new variants here rather than
 * styling buttons ad hoc elsewhere, so the two states stay consistent.
 */
export function Button({
  children,
  variant = 'primary',
  className = '',
  ...rest
}: ButtonProps) {
  return (
    <button className={`${baseStyles} ${variantStyles[variant]} ${className}`} {...rest}>
      {children}
    </button>
  );
}
