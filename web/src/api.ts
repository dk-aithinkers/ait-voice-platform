import type {
  ActivitySummary,
  Appointment,
  CallDetail,
  CallSummary,
  CallbackMessage,
  Clinic,
  HandoffBriefing,
  HandoffSummary,
  IntakeDetail,
  IntakeSummary,
  Principal,
} from "./types";

/**
 * The API client.
 *
 * The token lives in memory, not `localStorage`. A token in local storage is
 * readable by any script that gets injected into the page, and this one grants
 * access to patient transcripts — so it is held for the session only and the
 * user signs in again after a reload. That is a deliberate cost.
 */
let token: string | null = null;

export function setToken(value: string | null): void {
  token = value;
}

export function hasToken(): boolean {
  return token !== null;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      ...(init?.headers ?? {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
    },
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // A non-JSON error body is still an error; the status carries the meaning.
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

/**
 * Tenant scoping is a query parameter, and the server decides whether it is
 * allowed. A clinic principal passing another tenant's id gets 403 rather than
 * their own data, so this parameter is a request, never an assertion.
 */
function scoped(path: string, tenant?: string | null): string {
  if (!tenant) return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}tenant=${encodeURIComponent(tenant)}`;
}

export const api = {
  me: () => request<Principal>("/me"),
  clinics: () => request<Clinic[]>("/clinics"),
  clinic: (tenant?: string | null) => request<Clinic>(scoped("/clinic", tenant)),
  updateClinic: (tenant: string, changes: Partial<Clinic>) =>
    request<Clinic>(scoped("/clinic", tenant), {
      method: "POST",
      body: JSON.stringify(changes),
    }),
  calls: (tenant?: string | null, limit = 50) =>
    request<CallSummary[]>(scoped(`/calls?limit=${limit}`, tenant)),
  call: (callId: string, tenant?: string | null) =>
    request<CallDetail>(scoped(`/calls/${encodeURIComponent(callId)}`, tenant)),
  summary: (tenant?: string | null, days = 7) =>
    request<ActivitySummary>(scoped(`/summary?days=${days}`, tenant)),
  appointments: (tenant?: string | null, limit = 50) =>
    request<Appointment[]>(scoped(`/appointments?limit=${limit}`, tenant)),
  intakes: (tenant?: string | null) =>
    request<IntakeSummary[]>(scoped("/intake", tenant)),
  intake: (intakeId: string, tenant?: string | null) =>
    request<IntakeDetail>(scoped(`/intake/${encodeURIComponent(intakeId)}`, tenant)),
  handoffs: (tenant?: string | null, openOnly = true) =>
    request<HandoffSummary[]>(scoped(`/handoffs?open_only=${openOnly}`, tenant)),
  handoff: (handoffId: string, tenant?: string | null) =>
    request<HandoffBriefing>(
      scoped(`/handoffs/${encodeURIComponent(handoffId)}`, tenant),
    ),
  acknowledgeHandoff: (handoffId: string, tenant?: string | null) =>
    request<HandoffSummary>(
      scoped(`/handoffs/${encodeURIComponent(handoffId)}/acknowledge`, tenant),
      { method: "POST" },
    ),
  messages: (tenant?: string | null, openOnly = false) =>
    request<CallbackMessage[]>(
      scoped(`/messages?open_only=${openOnly}`, tenant),
    ),
  resolveMessage: (messageId: string, tenant?: string | null) =>
    request<CallbackMessage>(
      scoped(`/messages/${encodeURIComponent(messageId)}/resolve`, tenant),
      { method: "POST" },
    ),
};
