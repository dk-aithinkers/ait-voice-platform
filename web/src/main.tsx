import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // PHI in a cache is PHI at rest in the browser. Keep it briefly, and
      // refetch rather than showing a stale transcript.
      staleTime: 15_000,
      gcTime: 60_000,
      retry: (count, error) =>
        // Never retry an authorization failure; it will not start working, and
        // repeating a forbidden cross-tenant request is noise in the audit log.
        count < 2 &&
        !(typeof error === "object" && error !== null && "status" in error &&
          [401, 403, 404].includes((error as { status: number }).status)),
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
