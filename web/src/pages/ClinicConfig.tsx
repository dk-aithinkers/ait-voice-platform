import type { FormEvent, ReactNode } from "react";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { ErrorNote, Loading } from "../components/Common";
import type { Clinic } from "../types";

const OUT_OF_HOURS = [
  { value: "take_message", label: "Take a message" },
  { value: "existing_after_hours", label: "Use the clinic's existing service" },
  { value: "transfer_anyway", label: "Transfer anyway" },
];

/** Screen 1a — clinic configuration. Operator-only; the API enforces that. */
export function ClinicConfig(): ReactNode {
  const { tenantId = "" } = useParams();
  const queryClient = useQueryClient();
  const clinic = useQuery({
    queryKey: ["clinic", tenantId],
    queryFn: () => api.clinic(tenantId),
  });

  const [draft, setDraft] = useState<Partial<Clinic>>({});
  const [saved, setSaved] = useState(false);

  // Seed the form once the clinic loads, without clobbering edits in progress.
  useEffect(() => {
    if (clinic.data) {
      setDraft({
        clinic_name: clinic.data.clinic_name,
        greeting: clinic.data.greeting,
        escalation_number: clinic.data.escalation_number ?? "",
        out_of_hours: clinic.data.out_of_hours,
      });
    }
  }, [clinic.data]);

  const save = useMutation({
    mutationFn: (changes: Partial<Clinic>) => api.updateClinic(tenantId, changes),
    onSuccess: () => {
      setSaved(true);
      void queryClient.invalidateQueries({ queryKey: ["clinic", tenantId] });
      void queryClient.invalidateQueries({ queryKey: ["clinics"] });
    },
  });

  function submit(event: FormEvent): void {
    event.preventDefault();
    setSaved(false);
    save.mutate({
      ...draft,
      escalation_number: draft.escalation_number || null,
    });
  }

  if (clinic.isLoading) return <Loading what="clinic" />;
  if (clinic.isError) return <ErrorNote error={clinic.error} />;

  return (
    <>
      <p>
        <Link to="/clinics">‹ Back to clinics</Link>
      </p>
      <h1>{clinic.data?.clinic_name}</h1>

      <main>
        <form className="config" onSubmit={submit}>
          <label>
            <span>Clinic name</span>
            <input
              value={draft.clinic_name ?? ""}
              onChange={(e) => setDraft({ ...draft, clinic_name: e.target.value })}
            />
          </label>

          <label>
            <span>Greeting</span>
            <input
              value={draft.greeting ?? ""}
              onChange={(e) => setDraft({ ...draft, greeting: e.target.value })}
            />
          </label>
          {/*
            The AI and recording disclosure is not editable and is not shown as
            a field. The pipeline prepends it to every call so that no
            configuration can remove it — C-R3 and C-R4 are Firm, and
            California AB 2905 requires it before the message.
          */}
          <p className="note">
            Every call opens with the AI and recording disclosure before this
            greeting. That is not configurable.
          </p>

          <label>
            <span>Transfer number</span>
            <input
              value={draft.escalation_number ?? ""}
              placeholder="Leave empty if nobody answers transfers"
              onChange={(e) =>
                setDraft({ ...draft, escalation_number: e.target.value })
              }
            />
          </label>

          <label>
            <span>When nobody is available</span>
            <select
              value={draft.out_of_hours ?? "take_message"}
              onChange={(e) => setDraft({ ...draft, out_of_hours: e.target.value })}
            >
              {OUT_OF_HOURS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <div>
            <button type="submit" disabled={save.isPending}>
              {save.isPending ? "Saving…" : "Save"}
            </button>
            {saved ? (
              <span className="muted" role="status" aria-live="polite">
                {" "}
                Saved.
              </span>
            ) : null}
          </div>
          {save.isError ? <ErrorNote error={save.error} /> : null}
        </form>

        <h2>Not editable here</h2>
        <p className="note">
          Region, languages and outbound registration are set when the clinic is
          provisioned. Outbound calling to India numbers additionally requires
          completed DLT registration and 1600-series numbering, which is carried
          in-house and cannot be enabled from this screen.
        </p>
      </main>
    </>
  );
}
