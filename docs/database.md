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

Or, matching CI's image exactly and leaving any Postgres you already run
alone — note the port, since 5432 is often already taken:

```bash
docker run -d --name ait-voice-postgres \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=ait-voice -p 5435:5432 postgres:17-alpine
```

Then set `AIT_DB_PORT=5435` in `.env` alongside the other `AIT_DB_*` values
from `.env.example`, and run `uv run ait-voice-migrate`.

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

## Choosing a backend

One async interface, two implementations behind it. The protocols live in
`db/base.py`; `Services` is typed against them and never against a concrete
store, so the choice is wiring rather than something the handlers know about.

```python
Services()  # in-memory — tests and the demo app
Services.from_database(database)  # Postgres — every real deployment
```

Handing `Services` a synchronous store is a **type error** under `mypy
--strict`, not a deployment that quietly loses every call on restart. That is
the whole reason the protocols exist rather than a union of concrete types.

The production entrypoint is `ait_voice.api.main`, which opens the pool in the
app's lifespan:

```bash
uv run uvicorn --factory ait_voice.api.main:production_app
```

`ait_voice.api.demo` is the in-memory one, and stays that way on purpose — it
exists to show the UI with no database, and `web/README.md` documents it as the
zero-setup path.

### Why the in-memory stores are wrapped rather than made async

`db/memory.py` holds six classes that delegate to the synchronous stores and do
nothing else. Postgres is async and cannot be otherwise; memory can be either,
so the interface takes the shape the constrained side requires and the
unconstrained side adapts.

The alternative was making `core/` async throughout, which would have meant
rewriting the several hundred tests that pin domain behaviour — booking rules,
consent expiry, redaction — none of which is about persistence. A forgotten
`await` yields a coroutine, and a coroutine is truthy, so `assert
store.get(...)` would keep passing while asserting nothing. `pyproject.toml`
turns that warning into a test failure for the same reason.

The wrapper is thin enough to look obviously correct, which is exactly why it
is tested rather than trusted: `test_repository_equivalence.py` runs its
contract against all three, so *memory ≡ memory-async ≡ Postgres* is a result
and not a claim.

## Still to do

- Encryption at rest and backup policy — RDS gives both, and is HIPAA-eligible
  under the AWS BAA.
- Infrastructure: VPC, RDS, secrets, and the OIDC federation `team.md`
  specifies for CI.
- The pipeline still records calls through whatever `CallRepository` it is
  handed, which is correct — but nothing yet constructs a live call against the
  Postgres one, because no deployment exists to run it.
