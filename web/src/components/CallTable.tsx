import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { CallSummary } from "../types";
import { duration, escalationLabel, outcomeLabel, timeOfDay } from "../format";
import { Empty } from "./Common";

/**
 * Recent calls.
 *
 * Every row links to its detail page rather than using a click handler on the
 * row: a link is reachable by keyboard and announced as a link, which the
 * wireframes' "table sortable and navigable by keyboard" note requires.
 */
export function CallTable({
  calls,
  tenant,
}: {
  calls: CallSummary[];
  tenant?: string | null;
}): ReactNode {
  if (calls.length === 0) {
    return <Empty>No calls yet.</Empty>;
  }
  const query = tenant ? `?tenant=${encodeURIComponent(tenant)}` : "";
  return (
    <div className="table-wrap">
      <table>
        <caption>Most recent first</caption>
        <thead>
          <tr>
            <th scope="col">Time</th>
            <th scope="col">Caller</th>
            <th scope="col">Outcome</th>
            <th scope="col">Duration</th>
            <th scope="col">Turns</th>
          </tr>
        </thead>
        <tbody>
          {calls.map((call) => (
            <tr key={call.call_id}>
              <td>
                <Link to={`/calls/${encodeURIComponent(call.call_id)}${query}`}>
                  {timeOfDay(call.started_at)}
                </Link>
              </td>
              {/* Masked by the server. The client never holds a full number. */}
              <td>{call.caller_masked}</td>
              <td>
                {outcomeLabel(call.outcome)}
                {call.escalated && call.escalation_reason ? (
                  <span className="muted">
                    {" "}
                    — {escalationLabel(call.escalation_reason)}
                  </span>
                ) : null}
              </td>
              <td className="num">{duration(call.duration_seconds)}</td>
              <td className="num">{call.turns}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
