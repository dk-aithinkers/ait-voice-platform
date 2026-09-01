import type { ReactNode } from "react";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  NavLink,
  Route,
  Routes,
  useSearchParams,
} from "react-router-dom";
import { ApiError, api, setToken } from "./api";
import { SignIn } from "./pages/SignIn";
import { ClinicView } from "./pages/ClinicView";
import { CallDetail } from "./pages/CallDetail";
import { Messages } from "./pages/Messages";
import { Clinics } from "./pages/Clinics";
import { ClinicConfig } from "./pages/ClinicConfig";
import { Loading } from "./components/Common";

/**
 * Which surface a person sees is decided by their role, from `/api/me`.
 *
 * The client does not enforce anything by hiding routes — every endpoint
 * re-checks on the server, and a clinic principal typing an operator URL gets
 * 403 rather than data. Role here only decides what is worth rendering.
 */
export function App(): ReactNode {
  const [signedIn, setSignedIn] = useState(false);
  const [authError, setAuthError] = useState<string | undefined>();
  const queryClient = useQueryClient();

  const me = useQuery({
    queryKey: ["me"],
    queryFn: api.me,
    enabled: signedIn,
    retry: false,
  });

  function signIn(token: string): void {
    setToken(token);
    setAuthError(undefined);
    setSignedIn(true);
    void queryClient.invalidateQueries({ queryKey: ["me"] });
  }

  function signOut(): void {
    setToken(null);
    setSignedIn(false);
    queryClient.clear(); // Cached transcripts must not survive a sign-out.
  }

  if (!signedIn) return <SignIn onSubmit={signIn} error={authError} />;
  if (me.isLoading) return <Loading what="your account" />;
  if (me.isError) {
    const message =
      me.error instanceof ApiError && me.error.status === 401
        ? "That token was not recognised."
        : "Could not reach the server.";
    if (authError !== message) {
      setToken(null);
      setSignedIn(false);
      setAuthError(message);
    }
    return null;
  }

  const principal = me.data;
  const isOperator = principal?.role === "operator";

  return (
    <div className="shell">
      <a className="skip-link" href="#content">
        Skip to content
      </a>
      <header className="app">
        <div>
          <strong>AI Thinkers Voice</strong>{" "}
          <span className="role-badge">
            {isOperator ? "Operator console" : principal?.display_name}
          </span>
        </div>
        <button type="button" onClick={signOut}>
          Sign out
        </button>
      </header>

      {isOperator ? (
        <nav className="tabs" aria-label="Sections">
          <NavLink to="/clinics">Clinics</NavLink>
          <NavLink to="/">Calls</NavLink>
          <NavLink to="/messages">Messages</NavLink>
        </nav>
      ) : null}

      <div id="content">
        <Routes>
          <Route path="/" element={<Home isOperator={isOperator} tenant={principal?.tenant_id ?? null} />} />
          <Route path="/calls/:callId" element={<CallDetail />} />
          <Route
            path="/messages"
            element={
              <Messages
                tenant={isOperator ? undefined : principal?.tenant_id}
                isOperator={isOperator}
              />
            }
          />
          <Route path="/clinics" element={<Clinics />} />
          <Route path="/clinics/:tenantId" element={<ClinicConfig />} />
        </Routes>
      </div>
    </div>
  );
}

/**
 * An operator must name a tenant — the API refuses a cross-tenant request
 * because no such context exists on the server. Rather than hide that, the
 * console asks which clinic to look at.
 */
function Home({
  isOperator,
  tenant,
}: {
  isOperator: boolean;
  tenant: string | null;
}): ReactNode {
  const [params] = useSearchParams();
  const selected = params.get("tenant");

  if (isOperator && !selected) {
    return (
      <>
        <h1>Calls</h1>
        <main>
          <p className="muted">
            Choose a clinic to see its calls. There is no all-clinics view: the
            API has no cross-tenant context, so every request names one clinic.
          </p>
          <Clinics />
        </main>
      </>
    );
  }
  return <ClinicView tenant={isOperator ? selected : tenant} />;
}
