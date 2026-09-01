import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { dayAndTime } from "../format";
import { Empty, ErrorNote, Loading } from "../components/Common";

/**
 * The callback queue — on both surfaces deliberately.
 *
 * The wireframes put it in both places because the clinic carries the
 * obligation and the operator carries the responsibility for noticing it is
 * unmet. Resolving is the one write a clinic user may perform: the promise is
 * theirs to discharge.
 */
export function Messages({
  tenant,
  isOperator = false,
}: {
  tenant?: string | null;
  isOperator?: boolean;
}): ReactNode {
  const [params] = useSearchParams();
  const scope = tenant ?? params.get("tenant");
  const queryClient = useQueryClient();

  // An operator request must name a clinic — the API has no cross-tenant
  // context. Asking here is better than firing a request that always fails.
  const needsClinic = isOperator && !scope;

  const messages = useQuery({
    queryKey: ["messages", scope],
    queryFn: () => api.messages(scope),
    enabled: !needsClinic,
  });

  const resolve = useMutation({
    mutationFn: (messageId: string) => api.resolveMessage(messageId, scope),
    onSuccess: () => {
      // The banner on the clinic view counts open messages, so it is stale now.
      void queryClient.invalidateQueries({ queryKey: ["messages", scope] });
      void queryClient.invalidateQueries({ queryKey: ["summary", scope] });
    },
  });

  return (
    <>
      <h1>Messages awaiting callback</h1>
      <main>
        {needsClinic ? (
          <p className="muted">
            Choose a clinic from the Clinics tab to see its callback queue.
            Every request names one clinic; there is no all-clinics view.
          </p>
        ) : null}
        {!needsClinic && messages.isLoading ? <Loading what="messages" /> : null}
        {!needsClinic && messages.isError ? (
          <ErrorNote error={messages.error} />
        ) : null}
        {resolve.isError ? <ErrorNote error={resolve.error} /> : null}

        {!needsClinic && messages.data?.length === 0 ? (
          <Empty>Nobody is waiting for a call back.</Empty>
        ) : null}

        {messages.data && messages.data.length > 0 ? (
          <div className="table-wrap">
            <table>
              <caption>
                Marking one done records that the callback was made. It does not
                place the call.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Taken</th>
                  <th scope="col">Caller</th>
                  <th scope="col">Message</th>
                  <th scope="col">Status</th>
                  <th scope="col">
                    <span className="muted">Action</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {messages.data.map((message) => (
                  <tr key={message.message_id}>
                    <td>{dayAndTime(message.taken_at)}</td>
                    <td>{message.caller_masked}</td>
                    <td>{message.note ?? <span className="muted">—</span>}</td>
                    <td>{message.is_open ? "Waiting" : "Done"}</td>
                    <td>
                      {message.is_open ? (
                        <button
                          type="button"
                          onClick={() => resolve.mutate(message.message_id)}
                          disabled={resolve.isPending}
                        >
                          Mark called back
                        </button>
                      ) : (
                        <span className="muted">
                          {message.resolved_at
                            ? dayAndTime(message.resolved_at)
                            : ""}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </main>
    </>
  );
}
