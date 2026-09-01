import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ClinicView } from "./ClinicView";
import type {
  ActivitySummary,
  Appointment,
  CallSummary,
  Clinic,
} from "../types";

const clinic: Clinic = {
  tenant_id: "northside",
  clinic_name: "Northside Medical",
  region: "us",
  greeting: "How can I help?",
  escalation_number: "+15551230000",
  out_of_hours: "take_message",
  languages: ["en"],
  outbound_registered: false,
  active: true,
  is_staffed_now: true,
};

const summary: ActivitySummary = {
  window_days: 7,
  calls_answered: 12,
  appointments_booked: 5,
  appointments_changed: 2,
  escalated: 3,
  escalation_rate: 0.25,
  messages_open: 2,
  average_duration_seconds: 130,
};

const calls: CallSummary[] = [
  {
    call_id: "c-1",
    started_at: "2026-09-01T14:02:00Z",
    duration_seconds: 130,
    turns: 4,
    outcome: "appointment_booked",
    language: "en",
    caller_masked: "+1555…41",
    escalated: false,
    escalation_reason: null,
    has_transcript: true,
    p95_ms: 860,
    latency_observable: true,
    appointment_id: "appt-1",
  },
];

const appointments: Appointment[] = [
  {
    appointment_id: "appt-1",
    starts_at: "2026-09-02T14:30:00+00:00",
    local_start: "2026-09-02T10:30:00-04:00",
    spoken: "Wednesday 2 September at 10:30 am",
    duration_minutes: 30,
    status: "booked",
    call_id: "c-1",
    rescheduled_from: null,
  },
];

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: {
      clinic: () => Promise.resolve(clinic),
      summary: () => Promise.resolve(summary),
      calls: () => Promise.resolve(calls),
      appointments: () => Promise.resolve(appointments),
    },
  };
});

function renderView() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ClinicView tenant="northside" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.useRealTimers());
afterEach(() => vi.clearAllMocks());

describe("clinic view", () => {
  it("shows the counted facts", async () => {
    renderView();

    expect(await screen.findByText("12")).toBeInTheDocument();
    expect(screen.getByText("Calls answered")).toBeInTheDocument();
    expect(screen.getByText("Appointments booked")).toBeInTheDocument();
  });

  it("shows no hours-saved or time-saved figure", async () => {
    // RAID item I-02: the success metrics carry no baseline and no measurement
    // window. A figure here would be manufactured, and this project's practice
    // forbids producing one the evidence cannot support. This test exists so
    // that adding the tile later is a deliberate act, not a drive-by.
    renderView();
    await screen.findByText("12");

    // Assert on the tile labels, not on the words: the explanatory note below
    // the tiles legitimately says "Time saved is not shown", and a regex over
    // the whole page would forbid the very disclosure being asked for.
    const tileLabels = screen
      .getAllByRole("term")
      .map((dt) => dt.textContent ?? "");

    expect(tileLabels).not.toContain("Hours saved");
    expect(tileLabels).not.toContain("Time saved");
    expect(tileLabels.some((l) => /saved/i.test(l))).toBe(false);
    expect(screen.getByText(/no baseline has been measured/i)).toBeInTheDocument();
  });

  it("announces waiting callers politely rather than as an alert", async () => {
    // aria-live="polite" per the wireframes: it should not interrupt whatever
    // the person is reading.
    renderView();

    const banner = await screen.findByText(/waiting for a call back/i);
    const live = banner.closest("[aria-live]");
    expect(live).toHaveAttribute("aria-live", "polite");
  });

  it("gives the callback banner a keyboard-reachable action", async () => {
    renderView();
    expect(
      await screen.findByRole("link", { name: /view messages/i }),
    ).toBeInTheDocument();
  });

  it("shows only a masked caller number", async () => {
    const { container } = renderView();
    await screen.findByText("+1555…41");

    expect(container.textContent).not.toMatch(/\+1555\d{6,}/);
  });

  it("shows the diary in clinic-local time, not the browser's zone", async () => {
    // The server sends 14:30 UTC as 10:30-04:00. A New York clinic must read
    // 10:30 whatever the receptionist's laptop is set to.
    renderView();
    expect(await screen.findByText(/10:30/)).toBeInTheDocument();
  });

  it("shows no patient name in the diary", async () => {
    // A diary left open at a front desk is the most exposed surface here, so
    // the server sends times without identities.
    const { container } = renderView();
    await screen.findByText(/10:30/);

    const diary = container.querySelectorAll("table")[0]?.textContent ?? "";
    expect(diary).not.toMatch(/priya|sharma/i);
  });

  it("uses one h1 and h2 section headings", async () => {
    renderView();
    await screen.findByText("12");

    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    const h2s = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(h2s).toContain("Last 7 days");
    expect(h2s).toContain("Upcoming appointments");
    expect(h2s).toContain("Recent calls");
  });
});
