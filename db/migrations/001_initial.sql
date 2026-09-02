-- Schema, with tenant isolation enforced by the database itself.
--
-- C-T4 makes multi-tenancy a Hard constraint and C-R2 makes call content PHI,
-- so a missing tenant filter is a cross-tenant patient-data disclosure rather
-- than a wrong answer. The application already makes that hard to write by
-- accident (TenantScoped partitions physically; every accessor takes tenant
-- context first). Row-level security is the second, independent layer: a
-- hand-written query that forgets its filter returns nothing instead of
-- another clinic's records.
--
-- TWO THINGS MAKE THAT REAL RATHER THAN DECORATIVE.
--
--   1. FORCE ROW LEVEL SECURITY. Without it the table *owner* bypasses every
--      policy, so migrations running as the owner would silently disable the
--      protection they just created.
--
--   2. The application connects as `ait_app`, which is deliberately NOT a
--      superuser and NOT the table owner. Superusers bypass RLS unconditionally
--      — FORCE does not apply to them — so an application connecting as
--      `postgres` has RLS switched on and enforcing nothing. That failure looks
--      exactly like success, which is why it is written down here.

BEGIN;

-- The application role. No superuser, no table ownership, no DDL.
--
-- The password here is a LOCAL DEVELOPMENT PLACEHOLDER and is deliberately
-- named so. Any real environment must replace it — on RDS the role's password
-- comes from Secrets Manager and is rotated:
--
--     ALTER ROLE ait_app PASSWORD '<from secrets manager>';
--
-- It is written in plaintext here because a migration file is not a place to
-- put a real credential, and pretending otherwise by obfuscating it would be
-- worse than saying plainly that this one is worthless.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ait_app') THEN
        CREATE ROLE ait_app LOGIN PASSWORD 'local_dev_only' NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- Tenants. Deliberately NOT row-level secured: this is the registry that knows
-- about every clinic, which is what lets every other table know about exactly
-- one. It holds a clinic's own details — name, greeting, transfer number — and
-- no patient data.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id            text PRIMARY KEY,
    region               text NOT NULL CHECK (region IN ('us', 'india')),
    clinic_name          text NOT NULL,
    greeting             text NOT NULL DEFAULT 'How can I help?',
    escalation_number    text,
    out_of_hours         text NOT NULL DEFAULT 'take_message',
    languages            text[] NOT NULL DEFAULT ARRAY['en'],
    timezone             text NOT NULL DEFAULT 'UTC',
    staffed_days         smallint[] NOT NULL DEFAULT ARRAY[1,2,3,4,5],
    staffed_opens        time NOT NULL DEFAULT '09:00',
    staffed_closes       time NOT NULL DEFAULT '17:00',
    outbound_registered  boolean NOT NULL DEFAULT false,
    active               boolean NOT NULL DEFAULT true,
    created_at           timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Everything below is tenant-scoped and row-level secured.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS call_records (
    call_id              text NOT NULL,
    tenant_id            text NOT NULL REFERENCES tenants(tenant_id),
    started_at           timestamptz NOT NULL,
    duration_seconds     double precision NOT NULL DEFAULT 0,
    turns                integer NOT NULL DEFAULT 0,
    outcome              text NOT NULL DEFAULT 'no_action',
    language             text NOT NULL DEFAULT 'en',
    -- A phone number is a listed identifier. Held here because the clinic needs
    -- to call people back; never written to the audit log, which is a separate
    -- sink with the opposite retention obligation (C-R7 against C-R8).
    caller               text,
    caller_ref           text NOT NULL DEFAULT '',
    escalation_reason    text,
    escalation_route     text,
    p95_ms               double precision,
    latency_observable   boolean NOT NULL DEFAULT true,
    appointment_id       uuid,
    PRIMARY KEY (tenant_id, call_id)
);
CREATE INDEX IF NOT EXISTS call_records_recent
    ON call_records (tenant_id, started_at DESC);

CREATE TABLE IF NOT EXISTS transcripts (
    call_id              text NOT NULL,
    tenant_id            text NOT NULL REFERENCES tenants(tenant_id),
    turn_index           integer NOT NULL,
    speaker              text NOT NULL CHECK (speaker IN ('agent', 'caller')),
    -- Content. Erasable independently of the call record, so a clinic keeps
    -- its operational history when a patient's words are deleted.
    text                 text NOT NULL,
    PRIMARY KEY (tenant_id, call_id, turn_index),
    FOREIGN KEY (tenant_id, call_id)
        REFERENCES call_records (tenant_id, call_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS appointments (
    appointment_id       uuid PRIMARY KEY,
    tenant_id            text NOT NULL REFERENCES tenants(tenant_id),
    starts_at            timestamptz NOT NULL,
    duration_minutes     integer NOT NULL DEFAULT 30,
    status               text NOT NULL DEFAULT 'booked',
    call_id              text,
    caller_ref           text NOT NULL DEFAULT '',
    patient_name         text,
    reason               text,
    booked_at            timestamptz NOT NULL DEFAULT now(),
    previous_starts_at   timestamptz
);

-- The constraint that stops two patients being given one slot.
--
-- Until now this was an in-process lock, which holds for exactly one API
-- instance. A partial unique index moves the guarantee into the database,
-- where it survives a second instance, a restart, and a race — and the
-- `WHERE` clause is what lets a cancelled slot be booked again.
CREATE UNIQUE INDEX IF NOT EXISTS appointments_one_per_slot
    ON appointments (tenant_id, starts_at)
    WHERE status IN ('booked', 'rescheduled');

CREATE INDEX IF NOT EXISTS appointments_upcoming
    ON appointments (tenant_id, starts_at);

CREATE TABLE IF NOT EXISTS messages (
    message_id           uuid PRIMARY KEY,
    tenant_id            text NOT NULL REFERENCES tenants(tenant_id),
    call_id              text NOT NULL,
    taken_at             timestamptz NOT NULL DEFAULT now(),
    caller               text,
    note                 text,
    resolved_at          timestamptz
);
CREATE INDEX IF NOT EXISTS messages_open
    ON messages (tenant_id, taken_at DESC) WHERE resolved_at IS NULL;

CREATE TABLE IF NOT EXISTS handoffs (
    handoff_id           uuid PRIMARY KEY,
    tenant_id            text NOT NULL REFERENCES tenants(tenant_id),
    call_id              text NOT NULL,
    reason               text NOT NULL,
    urgency              text NOT NULL DEFAULT 'routine',
    method               text NOT NULL,
    caller               text,
    -- What the caller said, in order. The point of C-T6: a transfer that makes
    -- them repeat everything spends the one thing that earns acceptance.
    said                 text[] NOT NULL DEFAULT ARRAY[]::text[],
    turns                integer NOT NULL DEFAULT 0,
    recovery_attempted   boolean NOT NULL DEFAULT false,
    at                   timestamptz NOT NULL DEFAULT now(),
    acknowledged_at      timestamptz,
    acknowledged_by      text
);
CREATE INDEX IF NOT EXISTS handoffs_pending
    ON handoffs (tenant_id, at) WHERE acknowledged_at IS NULL;

CREATE TABLE IF NOT EXISTS intake_records (
    intake_id            uuid PRIMARY KEY,
    tenant_id            text NOT NULL REFERENCES tenants(tenant_id),
    call_id              text NOT NULL,
    captured_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS intake_values (
    intake_id            uuid NOT NULL REFERENCES intake_records(intake_id) ON DELETE CASCADE,
    tenant_id            text NOT NULL REFERENCES tenants(tenant_id),
    field                text NOT NULL,
    value                text NOT NULL,
    PRIMARY KEY (intake_id, field)
);

CREATE TABLE IF NOT EXISTS consents (
    tenant_id            text NOT NULL REFERENCES tenants(tenant_id),
    caller_ref           text NOT NULL,
    purpose              text NOT NULL,
    granted_at           timestamptz NOT NULL DEFAULT now(),
    region               text NOT NULL,
    PRIMARY KEY (tenant_id, caller_ref, purpose)
);

-- ---------------------------------------------------------------------------
-- Row-level security.
--
-- One policy shape for every table: a row is visible only when its tenant_id
-- matches the tenant set on the connection. The application sets that with
--     SET LOCAL app.tenant_id = '<id>'
-- inside a transaction, so it cannot leak past a commit or across a pooled
-- connection handed to the next request.
--
-- `current_setting(..., true)` returns NULL when unset rather than raising, and
-- `tenant_id = NULL` is NULL — never true. So a connection that forgets to set
-- the tenant sees nothing at all, which is the correct failure direction.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'call_records', 'transcripts', 'appointments', 'messages',
        'handoffs', 'intake_records', 'intake_values', 'consents'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        -- Without FORCE, the owner bypasses the policy it just wrote.
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', t);
        EXECUTE format($p$
            CREATE POLICY tenant_isolation ON %I
                USING (tenant_id = current_setting('app.tenant_id', true))
                WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
        $p$, t);
    END LOOP;
END
$$;

-- The application role gets data access and no schema authority.
GRANT USAGE ON SCHEMA public TO ait_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ait_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ait_app;

COMMIT;
