/** Display helpers. Pure, so they are cheap to test and hard to get wrong twice. */

export function duration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return rest ? `${minutes}m${rest}s` : `${minutes}m`;
}

export function timeOfDay(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function dayAndTime(iso: string): string {
  return new Date(iso).toLocaleString([], {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * An appointment time, read in the clinic's own zone.
 *
 * The server sends `local_start` already converted and offset-tagged. Parsing
 * that and letting the browser re-apply its own zone would show a New York
 * clinic its diary in whatever zone the receptionist's laptop is set to, so the
 * offset is stripped and the wall-clock reading kept as sent.
 */
export function clinicTime(localIso: string): string {
  const [date, rest] = localIso.split("T");
  if (!date || !rest) return localIso;
  const wall = new Date(`${date}T${rest.slice(0, 8)}`);
  return wall.toLocaleString([], {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const APPOINTMENT_LABELS: Record<string, string> = {
  booked: "Booked",
  rescheduled: "Moved",
  cancelled: "Cancelled",
  completed: "Completed",
  no_show: "Did not attend",
};

export function appointmentStatus(status: string): string {
  return APPOINTMENT_LABELS[status] ?? status;
}

const INTAKE_LABELS: Record<string, string> = {
  full_name: "Name",
  date_of_birth: "Date of birth",
  callback_number: "Callback number",
  reason_for_visit: "Reason for visit",
  notes: "Notes",
};

export function intakeLabel(field: string): string {
  return INTAKE_LABELS[field] ?? field;
}

const URGENCY_LABELS: Record<string, string> = {
  routine: "Routine",
  soon: "Soon",
  urgent: "Urgent",
  clinical: "Clinical — see first",
};

export function urgencyLabel(urgency: string): string {
  return URGENCY_LABELS[urgency] ?? urgency;
}

const OUTCOME_LABELS: Record<string, string> = {
  appointment_booked: "Appointment booked",
  appointment_rescheduled: "Appointment moved",
  appointment_cancelled: "Appointment cancelled",
  message_taken: "Message taken",
  escalated: "Passed to a person",
  no_action: "No action",
  failed: "Call failed",
};

export function outcomeLabel(outcome: string): string {
  return OUTCOME_LABELS[outcome] ?? outcome;
}

const ESCALATION_LABELS: Record<string, string> = {
  caller_requested_human: "Caller asked for a person",
  clinical_content: "Clinical question",
  not_understood_after_recovery: "Not understood",
  dependency_failure: "System fault",
};

export function escalationLabel(reason: string | null): string | null {
  if (!reason) return null;
  return ESCALATION_LABELS[reason] ?? reason;
}

/**
 * A rate of null means no sample, which is not the same as zero percent.
 * Returning a dash rather than "0%" keeps that distinction on screen.
 */
export function percent(rate: number | null): string {
  return rate === null ? "—" : `${Math.round(rate * 100)}%`;
}
