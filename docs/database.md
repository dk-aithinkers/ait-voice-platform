# Database

Postgres, and only Postgres. The schema leans on features that have no portable
equivalent — row-level security, partial unique indexes, array columns — and
those features are doing the work rather than decorating it.

## Two roles, and the difference matters

| Role | Used by | Authority |
|---|---|---|
| `postgres` (owner) | migrations only | full DDL |
| `ait_app` | the application | SELECT/INSERT/UPDATE/DELETE, no DDL, **not a superuser** |

**A superuser bypasses row-level security unconditionally.** `FORCE ROW LEVEL
SECURITY` does not apply to them. So an application connecting as `postgres`
has every policy enabled, forced, and enforcing nothing — and that failure
looks exactly like success. `Database.connect()` refuses a superuser at startup
for precisely that reason; migrations opt in explicitly.

## How tenant scoping works

```python
async with database.tenant_scope(tenant) as connection:
    rows = await connection.fetch("SELECT call_id FROM call_records")
```

No `WHERE tenant_id = ...`, and the query still returns only that clinic's
rows. `tenant_scope` opens a transaction and issues
`SET LOCAL app.tenant_id = '<id>'`; every policy compares `tenant_id` against
that setting.

Three properties, each deliberate:

- **`SET LOCAL`, not `SET`.** The value dies with the transaction, so it cannot
  follow a pooled connection to whoever borrows it next.
- **`current_setting(..., true)` returns NULL when unset**, and `x = NULL` is
  never true — a connection that forgets to scope sees *nothing*. Failing
  closed is the only acceptable direction here.
- **`WITH CHECK` as well as `USING`.** Reads and writes are both bounded; you
  cannot insert a row belonging to another clinic.

`tenants` is the one table without a policy. It is the registry that knows
about every clinic, which is what lets every other table know about exactly
one, and it holds no patient data.

## Double booking is now the database's problem

`Calendar.book()` used an in-process lock, which holds for exactly one API
instance. A partial unique index moves it into the database:

```sql
CREATE UNIQUE INDEX appointments_one_per_slot
    ON appointments (tenant_id, starts_at)
    WHERE status IN ('booked', 'rescheduled');
```

The `WHERE` clause is what lets a cancelled slot be booked again — a plain
unique index would block it forever.

## Local setup

```bash
createdb ait-voice
AIT_DB_OWNER_USER=postgres AIT_DB_OWNER_PASSWORD=<yours> uv run ait-voice-migrate
```

The migration creates the `ait_app` role with a local-only password. Tests skip
themselves unless `AIT_DB_NAME` is set, so the suite runs either way — but a
run without Postgres has not tested tenant isolation at the database, which is
the layer most worth testing.

## The `ait_app` password is a placeholder

`001_initial.sql` creates the role with the literal password `local_dev_only`.
That is not an oversight and not a secret — it is named to be obviously
worthless. Any real environment replaces it:

```sql
ALTER ROLE ait_app PASSWORD '<from AWS Secrets Manager>';
```

A migration file is the wrong place for a real credential, and obfuscating one
there would be worse than stating plainly that this one is disposable.

## Migrations

Plain SQL in `db/migrations/`, applied in filename order, recorded with a
checksum. Editing an applied migration is refused: the schema in front of you
would no longer be the one the file describes, and that is how two environments
diverge with nothing to show for it. Add a new file instead.

## Still to do

- Repository implementations replacing the in-memory stores (`TenantStore`,
  `CallStore`, `Calendar`, `HandoffQueue`, `IntakeStore`, `ConsentLedger`).
- Encryption at rest and backup policy — RDS gives both, and is HIPAA-eligible
  under the AWS BAA.
- Infrastructure: VPC, RDS, secrets, and the OIDC federation `team.md`
  specifies for CI.
