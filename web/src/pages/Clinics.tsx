import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ErrorNote, Loading } from "../components/Common";

/** Screen 1 — the operator's list of clinics. */
export function Clinics(): ReactNode {
  const clinics = useQuery({ queryKey: ["clinics"], queryFn: api.clinics });

  return (
    <>
      <h1>Clinics</h1>
      <main>
        {clinics.isLoading ? <Loading what="clinics" /> : null}
        {clinics.isError ? <ErrorNote error={clinics.error} /> : null}
        {clinics.data ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Clinic</th>
                  <th scope="col">Region</th>
                  <th scope="col">Staffed now</th>
                  <th scope="col">Outbound</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {clinics.data.map((clinic) => (
                  <tr key={clinic.tenant_id}>
                    <td>
                      <Link to={`/clinics/${encodeURIComponent(clinic.tenant_id)}`}>
                        {clinic.clinic_name}
                      </Link>
                    </td>
                    <td>{clinic.region.toUpperCase()}</td>
                    <td>{clinic.is_staffed_now ? "Yes" : "No"}</td>
                    <td>
                      {/*
                        India outbound needs DLT registration and 1600-series
                        numbering (C-R6). Showing it here means an operator can
                        see at a glance why a tenant cannot place reminders.
                      */}
                      {clinic.outbound_registered ? "Registered" : "Not registered"}
                    </td>
                    <td>{clinic.active ? "Active" : "Inactive"}</td>
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
