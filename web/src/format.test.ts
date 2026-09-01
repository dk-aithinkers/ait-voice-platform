import { describe, expect, it } from "vitest";
import { duration, escalationLabel, outcomeLabel, percent } from "./format";

describe("duration", () => {
  it("shows seconds under a minute", () => {
    expect(duration(45)).toBe("45s");
  });
  it("shows minutes and seconds", () => {
    expect(duration(130)).toBe("2m10s");
  });
  it("drops the seconds when they are zero", () => {
    expect(duration(120)).toBe("2m");
  });
});

describe("percent", () => {
  it("renders a rate", () => {
    expect(percent(0.25)).toBe("25%");
  });

  it("renders no sample as a dash, not as zero", () => {
    // A rate over zero calls is unknown, not 0%. Showing "0%" would claim the
    // agent escalated nothing when in fact it handled nothing.
    expect(percent(null)).toBe("—");
    expect(percent(0)).toBe("0%");
  });
});

describe("labels", () => {
  it("translates known outcomes", () => {
    expect(outcomeLabel("appointment_booked")).toBe("Appointment booked");
  });
  it("falls back to the raw value for an unknown outcome", () => {
    // A new server-side outcome should show as something rather than blank.
    expect(outcomeLabel("teleported")).toBe("teleported");
  });
  it("returns null for no escalation reason", () => {
    expect(escalationLabel(null)).toBeNull();
  });
  it("translates a known escalation reason", () => {
    expect(escalationLabel("caller_requested_human")).toBe(
      "Caller asked for a person",
    );
  });
});
