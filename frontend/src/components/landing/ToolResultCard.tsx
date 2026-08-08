import { CheckCircle2, XCircle } from 'lucide-react';
import type { CpuPayload, DiskPayload, MemoryPayload, ToolResult } from '../../types';
import { LabeledValue } from '../ui/LabeledValue';

interface ToolResultCardProps {
  result: ToolResult;
}

const TOOL_DISPLAY_NAMES: Record<string, string> = {
  cpu: 'CPU',
  memory: 'Memory',
  disk: 'Disk',
};

/**
 * Renders exactly one ToolResult — tool name, status, collection time,
 * and its metrics. `cpu` and `memory` get their metrics laid out with
 * proper labels and units in a flat grid; `disk` gets one such grid per
 * volume, since a machine can have more than one (see `renderDiskBody`).
 * Any other tool (battery, wifi, startup — none of which exist on the
 * backend yet) falls back to listing whatever keys its payload
 * contains, so this component doesn't need to change the day a new
 * tool is added.
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

      {isSuccess ? renderBody(result) : <p className="text-sm text-case-danger">{getErrorMessage(result)}</p>}
    </div>
  );
}

function renderBody(result: ToolResult) {
  if (result.tool_name === 'disk') {
    return renderDiskBody(result);
  }

  return <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">{renderMetrics(result)}</div>;
}

/**
 * `disk` is the one tool whose payload isn't a flat set of metrics — a
 * machine can have more than one local volume (C:, D:, ...), so this
 * renders one labeled sub-section, each with its own metrics grid, per
 * volume rather than trying to force multiple volumes' worth of numbers
 * into a single flat grid where they'd be indistinguishable.
 */
function renderDiskBody(result: ToolResult) {
  const payload = result.payload as Partial<DiskPayload>;
  const volumes = payload.volumes ?? [];

  if (volumes.length === 0) {
    return <p className="text-sm text-case-muted">No usable local volumes were found.</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      {volumes.map((volume) => (
        <div key={volume.mountpoint}>
          <p className="mb-2 font-mono text-xs uppercase tracking-wide text-case-faint">
            {formatVolumeLabel(volume.mountpoint)}
          </p>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <LabeledValue label="Usage" value={formatPercent(volume.usage_percent)} />
            <LabeledValue label="Total" value={formatGb(volume.total_gb)} />
            <LabeledValue label="Used" value={formatGb(volume.used_gb)} />
            <LabeledValue label="Free" value={formatGb(volume.free_gb)} />
            <LabeledValue label="Filesystem" value={volume.filesystem ?? '—'} />
          </div>
        </div>
      ))}
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

function formatVolumeLabel(mountpoint: string): string {
  // Windows drive mountpoints come back from the backend as "C:\\" —
  // trimmed to "C:" to match how a drive is normally written. A bare
  // root ("/" on Linux/macOS) has nothing to trim, so the `|| mountpoint`
  // fallback keeps it as "/" instead of collapsing to an empty label.
  return mountpoint.replace(/[\\/]+$/, '') || mountpoint;
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
