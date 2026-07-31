import type { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
}

/**
 * Generic empty-state block: icon, a direct statement of what's missing,
 * and an optional line of guidance. Used wherever a list has nothing in it
 * yet — not specific to any one section.
 */
export function EmptyState({ icon: Icon, title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-case-border px-6 py-14 text-center">
      <Icon className="h-5 w-5 text-case-faint" strokeWidth={1.5} aria-hidden="true" />
      <p className="text-sm text-case-muted">{title}</p>
      {description ? (
        <p className="max-w-xs text-xs text-case-faint">{description}</p>
      ) : null}
    </div>
  );
}
