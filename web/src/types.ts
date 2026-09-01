/** Shapes the API returns. Mirrors the server's `summary()` methods. */

export type Role = "operator" | "clinic";

export interface Principal {
  principal_id: string;
  role: Role;
  tenant_id: string | null;
  display_name: string;
}

export interface Clinic {
  tenant_id: string;
  clinic_name: string;
  region: string;
  greeting: string;
  escalation_number: string | null;
  out_of_hours: string;
  languages: string[];
  outbound_registered: boolean;
  active: boolean;
  is_staffed_now: boolean;
}

export interface CallSummary {
  call_id: string;
  started_at: string;
  duration_seconds: number;
  turns: number;
  outcome: string;
  language: string;
  /** Already masked by the server. The client never receives a full number. */
  caller_masked: string;
  escalated: boolean;
  escalation_reason: string | null;
  has_transcript: boolean;
  appointment_id: string | null;
  p95_ms: number | null;
  /**
   * False when the transport could not observe time to first audio. The UI
   * must say so rather than presenting the figure as a measurement.
   */
  latency_observable: boolean;
}

export interface TranscriptLine {
  speaker: "agent" | "caller";
  text: string;
}

export interface CallDetail extends CallSummary {
  transcript: TranscriptLine[] | null;
}

export interface ActivitySummary {
  window_days: number;
  calls_answered: number;
  appointments_booked: number;
  appointments_changed: number;
  escalated: number;
  /** null when there is no sample — not zero. */
  escalation_rate: number | null;
  messages_open: number;
  average_duration_seconds: number;
}

export interface Appointment {
  appointment_id: string;
  /** Absolute instant, UTC. */
  starts_at: string;
  /** The same instant in the clinic's own zone — what a person should read. */
  local_start: string;
  /** Exactly what the agent read back to the caller. */
  spoken: string;
  duration_minutes: number;
  status: string;
  call_id: string | null;
  rescheduled_from: string | null;
}

export interface CallbackMessage {
  message_id: string;
  call_id: string;
  taken_at: string;
  caller_masked: string;
  note: string | null;
  is_open: boolean;
  resolved_at: string | null;
}
