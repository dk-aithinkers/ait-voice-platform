import type { FormEvent, ReactNode } from "react";
import { useState } from "react";

/**
 * Token sign-in.
 *
 * Deliberately minimal, and deliberately not persisted: the token is held in
 * memory for the session only. It grants access to patient transcripts, and a
 * token in `localStorage` is readable by any injected script. Signing in again
 * after a reload is the cost of that.
 */
export function SignIn({
  onSubmit,
  error,
}: {
  onSubmit: (token: string) => void;
  error?: string;
}): ReactNode {
  const [value, setValue] = useState("");

  function submit(event: FormEvent): void {
    event.preventDefault();
    if (value.trim()) onSubmit(value.trim());
  }

  return (
    <form className="signin" onSubmit={submit}>
      <h1>AI Thinkers Voice</h1>
      <label>
        <span>Access token</span>
        <input
          type="password"
          autoComplete="off"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
      </label>
      <div>
        <button type="submit">Sign in</button>
      </div>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <p className="note">
        Your token is kept for this browser session only and is never written to
        storage. You will sign in again after a reload.
      </p>
    </form>
  );
}
