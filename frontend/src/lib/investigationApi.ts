import type { InvestigationResult } from '../types';

// Overridable via a `.env` file (`VITE_API_BASE_URL=...`) for anyone
// running the backend somewhere other than the default. Falls back to
// the address the backend is assumed to be running on.
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000';

/**
 * Raised for any failure talking to the investigation backend — a
 * network failure, a non-2xx response, or an unparsable body. Callers
 * only ever need `.message`, which is already written to be shown to
 * the user as-is.
 */
export class InvestigationApiError extends Error {}

/**
 * POST /investigation/start — open a new investigation and get back its
 * initial state, including whatever evidence the backend's diagnostic
 * tools collected synchronously (currently just `cpu`).
 *
 * Never throws anything other than `InvestigationApiError`, so a caller
 * only needs one catch clause to handle every failure mode gracefully.
 */
export async function startInvestigation(problemDescription: string): Promise<InvestigationResult> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/investigation/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ problem_description: problemDescription }),
    });
  } catch {
    // fetch() itself only rejects on network-level failures (backend
    // down, DNS, CORS block) — never on a non-2xx status, which is
    // handled separately below.
    throw new InvestigationApiError(
      `Couldn't reach Sherlock's backend at ${API_BASE_URL}. Make sure it's running and try again.`,
    );
  }

  if (!response.ok) {
    throw new InvestigationApiError(await describeErrorResponse(response));
  }

  try {
    return (await response.json()) as InvestigationResult;
  } catch {
    throw new InvestigationApiError('The backend returned a response Sherlock could not understand.');
  }
}

/**
 * Turn a non-2xx response into one readable sentence. FastAPI's error
 * body shape differs by failure type — a 404 sends `detail` as a plain
 * string, a 422 validation error sends `detail` as a list of per-field
 * errors — so both are handled rather than assumed.
 */
async function describeErrorResponse(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    const detail = (body as { detail?: unknown } | null)?.detail;

    if (typeof detail === 'string') {
      return detail;
    }

    if (Array.isArray(detail)) {
      const messages = detail
        .map((entry) => (entry && typeof entry === 'object' && 'msg' in entry ? String(entry.msg) : null))
        .filter((msg): msg is string => Boolean(msg));
      if (messages.length > 0) {
        return messages.join(' ');
      }
    }
  } catch {
    // Body wasn't JSON at all — fall through to the generic message below.
  }

  return `The backend returned an unexpected error (HTTP ${response.status}).`;
}
