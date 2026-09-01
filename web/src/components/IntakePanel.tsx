import type { ReactNode } from "react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { intakeLabel } from "../format";
import { ErrorNote, Loading } from "./Common";

/**
 * Intake details captured on a call.
 *
 * Collapsed by default and fetched only when opened. The values are a name, a
 * date of birth and a phone number — nothing that should be sitting on an
 * unattended screen because a page happened to load.
 */
export function IntakePanel({
  callId,
  tenant,
}: {
  callId: string;
  tenant?: string | null;
}): ReactNode {
  const [open, setOpen] = useState(false);

  const intakes = useQuery({
    queryKey: ["intakes", tenant],
    queryFn: () => api.intakes(tenant),
  });

  const summary = intakes.data?.find((record) => record.call_id === callId);

  const detail = useQuery({
    queryKey: ["intake", summary?.intake_id, tenant],
    queryFn: () => api.intake(summary!.intake_id, tenant),
    enabled: open && summary !== undefined,
  });

  if (intakes.isLoading || !summary) return null;

  return (
    <>
      <h2>Intake</h2>
      <p className="note">
        {summary.fields.length} detail
        {summary.fields.length === 1 ? "" : "s"} captured. Each was read back to
        the caller and confirmed before it was stored.
      </p>
      <p>
        <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? "Hide details" : "Show details"}
        </button>
      </p>
      {open ? (
        <div aria-live="polite">
          {detail.isLoading ? <Loading what="intake" /> : null}
          {detail.isError ? <ErrorNote error={detail.error} /> : null}
          {detail.data ? (
            <dl className="tiles">
              {Object.entries(detail.data.details).map(([field, value]) => (
                <div className="tile" key={field}>
                  <dt>{intakeLabel(field)}</dt>
                  <dd style={{ fontSize: "1rem" }}>{value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
