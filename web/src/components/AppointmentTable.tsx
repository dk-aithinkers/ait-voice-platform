import type { ReactNode } from "react";
import type { Appointment } from "../types";
import { appointmentStatus, clinicTime } from "../format";
import { Empty } from "./Common";

/**
 * The clinic's diary.
 *
 * Carries no patient name, because the server does not send one: a diary needs
 * times, and a screen left open at a front desk is the most exposed surface in
 * the product.
 */
export function AppointmentTable({
  appointments,
}: {
  appointments: Appointment[];
}): ReactNode {
  if (appointments.length === 0) {
    return <Empty>Nothing booked yet.</Empty>;
  }
  return (
    <div className="table-wrap">
      <table>
        <caption>Times are shown in the clinic&rsquo;s own time zone</caption>
        <thead>
          <tr>
            <th scope="col">When</th>
            <th scope="col">Length</th>
            <th scope="col">Status</th>
            <th scope="col">Booked on call</th>
          </tr>
        </thead>
        <tbody>
          {appointments.map((appointment) => (
            <tr key={appointment.appointment_id}>
              <td>{clinicTime(appointment.local_start)}</td>
              <td className="num">{appointment.duration_minutes} min</td>
              <td>
                {appointmentStatus(appointment.status)}
                {appointment.rescheduled_from ? (
                  <span className="muted">
                    {" "}
                    — moved from {clinicTime(appointment.rescheduled_from)}
                  </span>
                ) : null}
              </td>
              <td className="muted">{appointment.call_id ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
