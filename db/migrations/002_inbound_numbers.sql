-- Which clinic a call is for.
--
-- FR1.1 says the system answers "inbound calls to a configured clinic number",
-- and until now no such configuration existed anywhere in the model. A call
-- arriving at the platform had no way to find its tenant, which makes every
-- other tenant guarantee unreachable: there is nothing to scope to.
--
-- A separate table rather than a text[] column on `tenants`, because the
-- constraint is the point. One number must map to exactly one clinic — two
-- rows claiming the same number is not a display bug, it is a call routed to
-- the wrong clinic's diary and transcript, which is a cross-tenant PHI
-- disclosure. A PRIMARY KEY on the number is what makes that unrepresentable;
-- an array column could hold the same number twice and nothing would object.
--
-- Deliberately NOT row-level secured, for the same reason `tenants` is not:
-- this is the registry that maps a number to a clinic, and the lookup happens
-- before any tenant context exists. It holds no patient data — a clinic's own
-- published number is not PHI.

CREATE TABLE IF NOT EXISTS tenant_numbers (
    -- E.164, normalised on the way in. The primary key does the routing work.
    phone_number  text PRIMARY KEY CHECK (phone_number ~ '^\+[1-9][0-9]{6,14}$'),
    tenant_id     text NOT NULL REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    -- A clinic may publish several: a main line, an after-hours line, a
    -- number ported from their old system during a migration.
    label         text,
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- Listing a clinic's numbers is a per-tenant read and should not scan.
CREATE INDEX IF NOT EXISTS tenant_numbers_by_tenant ON tenant_numbers (tenant_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_numbers TO ait_app;
