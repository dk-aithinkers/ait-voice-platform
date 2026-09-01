import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { duration, percent } from "../format";
import { CallTable } from "../components/CallTable";
import { ErrorNote, Loading, Tile } from "../components/Common";

/**
 * Screen 2 — the clinic's read-only view.
 *
 * Wireframe accessibility contract: `<h1>` clinic name, `<h2>` for "Last 7
 * days" and "Recent calls"; header / main / complementary landmarks; the
 * callback banner is the keyboard entry point because it is the only task on
 * the screen, so it precedes the table in DOM order.
 */
export function ClinicView({ tenant }: { tenant?: string | null }): ReactNode {
  const clinic = useQuery({
    queryKey: ["clinic", tenant],
    queryFn: () => api.clinic(tenant),
  });
  const summary = useQuery({
    queryKey: ["summary", tenant],
    queryFn: () => api.summary(tenant),
  });
  const calls = useQuery({
    queryKey: ["calls", tenant],
    queryFn: () => api.calls(tenant),
  });

  if (clinic.isError) return <ErrorNote error={clinic.error} />;

  return (
    <>
      <h1>{clinic.data?.clinic_name ?? "Clinic"}</h1>

      {summary.data && summary.data.messages_open > 0 ? (
        <aside className="banner" aria-live="polite">
          <span>
            <strong>{summary.data.messages_open}</strong> caller
            {summary.data.messages_open === 1 ? "" : "s"} waiting for a call
            back.
          </span>
          <Link
            className="button"
            to={tenant ? `/messages?tenant=${encodeURIComponent(tenant)}` : "/messages"}
          >
            View messages
          </Link>
        </aside>
      ) : null}

      <main>
        <h2>Last 7 days</h2>
        {summary.isLoading ? <Loading what="summary" /> : null}
        {summary.isError ? <ErrorNote error={summary.error} /> : null}
        {summary.data ? (
          <>
            <div className="tiles">
              <Tile label="Calls answered" value={summary.data.calls_answered} />
              <Tile
                label="Appointments booked"
                value={summary.data.appointments_booked}
              />
              <Tile
                label="Appointments changed"
                value={summary.data.appointments_changed}
              />
              <Tile
                label="Passed to a person"
                value={`${summary.data.escalated} (${percent(summary.data.escalation_rate)})`}
              />
              <Tile
                label="Average call"
                value={duration(summary.data.average_duration_seconds)}
              />
            </div>
            {/*
              No "hours saved" tile. RAID item I-02 records that the success
              metrics carry no baseline and no measurement window, so the
              figure would be derived from nothing. Everything above is a
              counted fact.
            */}
            <p className="note">
              These are counted facts over the last {summary.data.window_days}{" "}
              days. Time saved is not shown: no baseline has been measured, so
              any figure would be invented.
            </p>
          </>
        ) : null}

        <h2>Recent calls</h2>
        {calls.isLoading ? <Loading what="calls" /> : null}
        {calls.isError ? <ErrorNote error={calls.error} /> : null}
        {calls.data ? <CallTable calls={calls.data} tenant={tenant} /> : null}
      </main>
    </>
  );
}
