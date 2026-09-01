import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Honour PORT when the harness assigns one, so this does not collide with
    // another dev server already on 5173.
    port: Number(process.env.PORT ?? 5173),
    // The API is same-origin in development, so the browser never makes a
    // cross-origin request carrying a credential and CORS stays off in the
    // common path. Production serves both from one origin for the same reason.
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
});
