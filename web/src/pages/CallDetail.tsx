import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { dayAndTime, duration, escalationLabel, outcomeLabel } from "../format";
import { ErrorNote, Loading } from "../components/Common";
import { IntakePanel } from "../components/IntakePanel";

/** Screen 2a — where the clinic decides whether it trusts the agent. */
export function CallDetail(): ReactNode {
  const { callId = "" } = useParams();
  const [params] = useSearchParams();
  const tenant = params.get("tenant");

  const call = useQuery({
    queryKey: ["call", callId, tenant],
    queryFn: () => api.call(callId, tenant),
  });

  if (call.isLoading) return <Loading what="call" />;
  if (call.isError) return <ErrorNote error={call.error} />;
  if (!call.data) return null;

  const detail = call.data;
  const backTo = tenant ? `/?tenant=${encodeURIComponent(tenant)}` : "/";

  return (
    <>
      <p>
        <Link to={backTo}>‹ Back to calls</Link>
      </p>
      <h1>
        {dayAndTime(detail.started_at)} — {detail.caller_masked}
      </h1>

      <main>
        <dl className="tiles">
          <div className="tile">
            <dt>Outcome</dt>
            <dd style={{ fontSize: "1rem" }}>
              {outcomeLabel(detail.outcome)}
              {detail.escalation_reason ? (
                <> — {escalationLabel(detail.escalation_reason)}</>
              ) : null}
            </dd>
          </div>
          <div className="tile">
            <dt>Duration</dt>
            <dd style={{ fontSize: "1rem" }}>
              {duration(detail.duration_seconds)}
            </dd>
          </div>
          <div className="tile">
            <dt>Language</dt>
            <dd style={{ fontSize: "1rem" }}>{detail.language}</dd>
          </div>
          {detail.p95_ms !== null ? (
            <div className="tile">
              <dt>Reply latency (p95)</dt>
              <dd style={{ fontSize: "1rem" }}>
                {Math.round(detail.p95_ms)}ms
                {/*
                  A bundled transport hands text to the carrier, which
                  synthesises downstream — so this figure stops short of the
                  audio the caller heard. Showing it without that caveat would
                  present a floor as a measurement.
                */}
                {!detail.latency_observable ? (
                  <span className="muted"> (floor — see note)</span>
                ) : null}
              </dd>
            </div>
          ) : null}
        </dl>

        {!detail.latency_observable ? (
          <p className="note">
            This call ran over a transport that synthesises speech downstream,
            so the latency above excludes the final audio and is a lower bound
            rather than a measurement.
          </p>
        ) : null}

        <IntakePanel callId={callId} tenant={tenant} />

        <h2>Transcript</h2>
        {detail.transcript && detail.transcript.length > 0 ? (
          <div className="transcript">
            {detail.transcript.map((line, index) => (
              <div className="line" key={index}>
                <span className="who">
                  {line.speaker === "agent" ? "Agent" : "Caller"}
                </span>
                <span>{line.text}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="empty">
            No transcript is stored for this call. It may have been erased once
            its purpose was fulfilled.
          </p>
        )}
      </main>
    </>
  );
}
