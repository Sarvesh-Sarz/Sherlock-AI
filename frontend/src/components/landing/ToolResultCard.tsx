import { CheckCircle2, XCircle } from 'lucide-react';
import type { CpuPayload, MemoryPayload, ToolResult } from '../../types';
import { LabeledValue } from '../ui/LabeledValue';

interface ToolResultCardProps {
  result: ToolResult;
}

const TOOL_DISPLAY_NAMES: Record<string, string> = {
  cpu: 'CPU',
  memory: 'Memory',
};

/**
 * Renders exactly one ToolResult — tool name, status, collection time,
 * and its metrics. `cpu` gets its five metrics laid out with proper
 * labels and units; any other tool (memory, disk, battery, wifi,
 * startup — none of which exist on the backend yet) falls back to
 * listing whatever keys its payload contains, so this component doesn't
 * need to change the day a new tool is added.
 */
export function ToolResultCard({ result }: ToolResultCardProps) {
  const isSuccess = result.status === 'success';
  const displayName = TOOL_DISPLAY_NAMES[result.tool_name] ?? capitalize(result.tool_name);

  return (
    <div className="rounded-lg border border-case-border bg-case-surface px-5 py-4">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isSuccess ? (
            <CheckCircle2 className="h-4 w-4 text-case-brass" strokeWidth={1.5} aria-hidden="true" />
          ) : (
            <XCircle className="h-4 w-4 text-case-danger" strokeWidth={1.5} aria-hidden="true" />
          )}
          <span className="text-sm font-medium text-case-text">{displayName}</span>
        </div>
        <span className="font-mono text-xs text-case-faint">
          {formatTime(result.collected_at)}
        </span>
      </div>

      {isSuccess ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">{renderMetrics(result)}</div>
      ) : (
        <p className="text-sm text-case-danger">{getErrorMessage(result)}</p>
      )}
    </div>
  );
}

function renderMetrics(result: ToolResult) {
  if (result.tool_name === 'cpu') {
    const payload = result.payload as Partial<CpuPayload>;
    return (
      <>
        <LabeledValue label="Usage" value={formatPercent(payload.usage_percent)} />
        <LabeledValue label="Physical Cores" value={formatCount(payload.physical_cores)} />
        <LabeledValue label="Logical Cores" value={formatCount(payload.logical_cores)} />
        <LabeledValue label="Current Frequency" value={formatGhz(payload.current_frequency)} />
        <LabeledValue label="Max Frequency" value={formatGhz(payload.max_frequency)} />
      </>
    );
  }

  if (result.tool_name === 'memory') {
    const payload = result.payload as Partial<MemoryPayload>;
    return (
      <>
        <LabeledValue label="Usage" value={formatPercent(payload.usage_percent)} />
        <LabeledValue label="Total" value={formatGb(payload.total_gb)} />
        <LabeledValue label="Used" value={formatGb(payload.used_gb)} />
        <LabeledValue label="Available" value={formatGb(payload.available_gb)} />
        <LabeledValue label="Swap Used" value={formatGb(payload.swap_used_gb)} />
        <LabeledValue label="Swap Total" value={formatGb(payload.swap_total_gb)} />
      </>
    );
  }

  const entries = Object.entries(result.payload);
  if (entries.length === 0) {
    return <p className="text-sm text-case-muted">No metrics reported.</p>;
  }

  return (
    <>
      {entries.map(([key, value]) => (
        <LabeledValue key={key} label={formatKey(key)} value={formatUnknown(value)} />
      ))}
    </>
  );
}

function getErrorMessage(result: ToolResult): string {
  const error = result.payload.error;
  return typeof error === 'string' && error.length > 0 ? error : 'This tool failed to collect data.';
}

function formatPercent(value: number | undefined): string {
  return typeof value === 'number' ? `${value.toFixed(1)}%` : '—';
}

function formatCount(value: number | null | undefined): string {
  return typeof value === 'number' ? String(value) : '—';
}

function formatGhz(value: number | null | undefined): string {
  return typeof value === 'number' ? `${value.toFixed(2)} GHz` : '—';
}

function formatGb(value: number | null | undefined): string {
  return typeof value === 'number' ? `${value.toFixed(2)} GB` : '—';
}

function formatKey(key: string): string {
  return key
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function formatUnknown(value: unknown): string {
  if (value === null || value === undefined) return '—';
  return typeof value === 'string' ? value : JSON.stringify(value);
}

function formatTime(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  return Number.isNaN(date.getTime()) ? isoTimestamp : date.toLocaleTimeString();
}

function capitalize(value: string): string {
  return value.length === 0 ? value : value.charAt(0).toUpperCase() + value.slice(1);
}
