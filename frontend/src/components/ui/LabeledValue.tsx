interface LabeledValueProps {
  label: string;
  value: string;
  mono?: boolean;
}

/**
 * A small label/value pair — e.g. "Case ID" over "a1b2c3...". Shared by
 * the investigation summary and each evidence card's metrics, so both
 * present fields the same way rather than each inventing its own markup.
 */
export function LabeledValue({ label, value, mono = false }: LabeledValueProps) {
  return (
    <div>
      <p className="mb-1 text-xs uppercase tracking-wide text-case-faint">{label}</p>
      <p className={`break-words text-sm text-case-text ${mono ? 'font-mono' : ''}`}>{value}</p>
    </div>
  );
}
