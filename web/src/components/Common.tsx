import type { ReactNode } from "react";
import { ApiError } from "../api";

export function Loading({ what }: { what: string }): ReactNode {
  // aria-live so a screen reader hears the state change rather than silence.
  return (
    <p className="muted" role="status" aria-live="polite">
      Loading {what}…
    </p>
  );
}

export function ErrorNote({ error }: { error: unknown }): ReactNode {
  // The server's own detail is used for 403, not a canned line. An operator
  // who simply has not named a clinic gets the same status as a clinic user
  // reaching across tenants, and telling the first one "you do not have
  // access" is a misdiagnosis that sends them looking for a permissions bug.
  const message =
    error instanceof ApiError
      ? error.status === 404
        ? "Not found."
        : error.status === 401
          ? "Your session has ended. Sign in again."
          : error.message
      : "Something went wrong.";
  return (
    <p className="error" role="alert">
      {message}
    </p>
  );
}

export function Empty({ children }: { children: ReactNode }): ReactNode {
  return <p className="empty">{children}</p>;
}

export function Tile({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint?: string;
}): ReactNode {
  return (
    <div className="tile">
      <dl>
        <dt>{label}</dt>
        {/* Values are text, never colour-coded — the wireframes call for this
            so the tiles do not rely on colour to carry meaning. */}
        <dd>{value}</dd>
      </dl>
      {hint ? <p className="note">{hint}</p> : null}
    </div>
  );
}
