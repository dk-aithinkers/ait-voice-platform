import type { ReactNode } from "react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { dayAndTime, escalationLabel, urgencyLabel } from "../format";
import { Empty, ErrorNote, Loading } from "../components/Common";

/**
 * Calls waiting for a person — C-T6.
 *
 * The queue itself carries no PHI: a list left open on a front-desk screen
 * should not display what every caller said. The briefing is fetched when
 * somebody opens one, which is the moment they actually need it.
 */
export function Handoffs({
  tenant,
  isOperator = false,
}: {
  tenant?: string | null;
  isOperator?: boolean;
}): ReactNode {
  const [params] = useSearchParams();
  const scope = tenant ?? params.get("tenant");
  const needsClinic = isOperator && !scope;
  const [open, setOpen] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const handoffs = useQuery({
    queryKey: ["handoffs", scope],
    queryFn: () => api.handoffs(scope),
    enabled: !needsClinic,
  });

  const briefing = useQuery({
    queryKey: ["handoff", open, scope],
    queryFn: () => api.handoff(open!, scope),
    enabled: open !== null,
  });

  const acknowledge = useMutation({
    mutationFn: (handoffId: string) => api.acknowledgeHandoff(handoffId, scope),
    onSuccess: () => {
      setOpen(null);
      void queryClient.invalidateQueries({ queryKey: ["handoffs", scope] });
    },
  });

  return (
    <>
      <h1>Waiting for a person</h1>
      <main>
        {needsClinic ? (
          <p className="muted">
            Choose a clinic from the Clinics tab to see its handoff queue.
          </p>
        ) : null}
        {!needsClinic && handoffs.isLoading ? <Loading what="handoffs" /> : null}
        {!needsClinic && handoffs.isError ? (
          <ErrorNote error={handoffs.error} />
        ) : null}
        {handoffs.data?.length === 0 ? (
          <Empty>Nobody is waiting.</Empty>
        ) : null}

        {handoffs.data && handoffs.data.length > 0 ? (
          <div className="table-wrap">
            <table>
              <caption>
                Most urgent first. A clinical call sorts above an older routine
                one.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Urgency</th>
                  <th scope="col">Why</th>
                  <th scope="col">Waiting since</th>
                  <th scope="col">Turns</th>
                  <th scope="col">
                    <span className="muted">Briefing</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {handoffs.data.map((handoff) => (
                  <tr key={handoff.handoff_id}>
                    {/* Text, not a colour badge: the wireframes require meaning
                        not to depend on colour alone. */}
                    <td>
                      {handoff.urgency === "clinical" ? (
                        <strong>{urgencyLabel(handoff.urgency)}</strong>
                      ) : (
                        urgencyLabel(handoff.urgency)
                      )}
                    </td>
                    <td>{escalationLabel(handoff.reason)}</td>
                    <td>{dayAndTime(handoff.at)}</td>
                    <td className="num">{handoff.turns}</td>
                    <td>
                      <button
                        type="button"
                        onClick={() =>
                          setOpen(
                            open === handoff.handoff_id ? null : handoff.handoff_id,
                          )
                        }
                        aria-expanded={open === handoff.handoff_id}
                      >
                        {open === handoff.handoff_id ? "Hide" : "Open"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {open !== null ? (
          <section aria-live="polite">
            <h2>What the caller said</h2>
            {briefing.isLoading ? <Loading what="the briefing" /> : null}
            {briefing.isError ? <ErrorNote error={briefing.error} /> : null}
            {briefing.data ? (
              <>
                <p className="note">
                  Caller {briefing.data.briefing.caller_number ?? "unknown"} ·{" "}
                  {urgencyLabel(briefing.data.briefing.urgency)}
                  {briefing.data.briefing.recovery_attempted
                    ? " · the agent already asked them to repeat themselves once"
                    : null}
                </p>
                <div className="transcript">
                  {briefing.data.briefing.said.map((line, index) => (
                    <div className="line" key={index}>
                      <span className="who">Caller</span>
                      <span>{line}</span>
                    </div>
                  ))}
                </div>
                <p>
                  <button
                    type="button"
                    onClick={() => acknowledge.mutate(briefing.data.handoff_id)}
                    disabled={acknowledge.isPending}
                  >
                    I have picked this up
                  </button>
                </p>
                {acknowledge.isError ? (
                  <ErrorNote error={acknowledge.error} />
                ) : null}
              </>
            ) : null}
          </section>
        ) : null}
      </main>
    </>
  );
}
