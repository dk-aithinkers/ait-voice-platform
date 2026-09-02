# Operator console and clinic view

The two surfaces from `aidlc/.../ideation/rough-mockups/wireframes.md`, as a
React SPA over the FastAPI JSON API in `src/ait_voice/api/`.

## Running it

Two processes. The API first:

```bash
uv run uvicorn --factory ait_voice.api.demo:demo_app --port 8000
```

That one holds its data in memory and seeds itself, which is the point: no
database, no setup, synthetic data only. The Postgres-backed entrypoint is
`ait_voice.api.main:production_app` — see `docs/database.md`.

Then the UI, which proxies `/api` to it so the browser makes no cross-origin
request and CORS stays off in the common path:

```bash
cd web && npm run dev
```

Sign in with `demo-operator-token` or `demo-clinic-token`. Both are seeded by
`ait_voice.api.demo`, which contains synthetic data only — `project.md` forbids
real call audio, transcripts or caller identity anywhere in this repository.

## Things that are load-bearing rather than stylistic

**Tenant scoping is enforced on the server, not here.** A clinic principal is
bound to one tenant at authentication time; passing another tenant's id returns
403 rather than their own data. The client hides routes by role only to avoid
rendering something useless — it is not a security control, and every endpoint
re-checks.

**Phone numbers are masked server-side.** `CallRecord.summary()` returns
`caller_masked`; the full number never reaches the browser. A client that forgot
to mask could not leak it.

**The token is held in memory, never in `localStorage`.** It reaches patient
transcripts, and local storage is readable by any injected script. Signing in
again after a reload is the deliberate cost.

**There is no hours-saved tile,** and `ClinicView.test.tsx` asserts its absence.
RAID item I-02 records that the success metrics carry no baseline and no
measurement window, so the figure would be invented. Adding it should be a
deliberate act, not a drive-by.

**A latency figure from a bundled transport is labelled a floor.** Twilio
ConversationRelay synthesises downstream, so the measurement stops short of the
audio the caller heard.

**No brand has been applied.** [Q6] records that AI Thinkers brand guidelines
exist, but none were supplied to this repository. Inventing colours would assert
a brand nobody approved. Refined Mockups is where that lands.

## Commands

| | |
|---|---|
| `npm run dev` | Dev server, proxying `/api` to port 8000 |
| `npm run build` | Typecheck and production build |
| `npm test` | Vitest |
| `npm run lint` | ESLint, zero warnings tolerated |
