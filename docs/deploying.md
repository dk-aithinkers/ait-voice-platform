# Deploying

Three CDK stacks in `infra/`, split by what survives a bad deploy.

| Stack | Holds | Replaced on release? |
|---|---|---|
| `AitVoice-Platform-US` | VPC, RDS, the two S3 buckets | **No** — `RemovalPolicy.RETAIN`, deletion protection on |
| `AitVoice-Service-US` | ECS Fargate, ALB, task definitions | Yes |
| `AitVoice-Ci` | The GitHub OIDC role | Rarely |

The split is the point: a task definition changes on every push, and a database
and an audit bucket under Object Lock are things you must not be able to destroy
by editing an image tag.

## The two buckets

This is the part with regulatory weight, and `scripts/check_infra.py` asserts it
on every push rather than trusting this document.

**Audit** — Object Lock in **COMPLIANCE** mode, 365 days, versioned. C-R7 wants
security logs kept a year. Compliance mode rather than governance because
governance can be bypassed by anyone holding `s3:BypassGovernanceRetention`,
which makes immutability a policy rather than a property.

Be precise about what that buys, because it is easy to overstate and this
document did at first. **Object Lock protects versions, not the
current-version view.** Verified against a real implementation:

| Operation | S3's answer |
|---|---|
| `DeleteObject` with a version id | **refused** — data cannot be destroyed |
| `DeleteObject` with no version id | accepted; a delete marker hides the key |
| `PutObject` on an existing key | accepted; a new version is what `GetObject` then serves |

Nothing written can be destroyed, but a reader following current versions could
be shown a shortened or altered log. `S3AuditLog` therefore lists *versions* and
reads the **oldest version of each key** — what was actually written. A delete
marker hides nothing from it and an overwrite cannot change what it returns.
Since each key is written exactly once with `IfNoneMatch`, a key carrying a
second version is itself evidence, and `verify()` fails on it.

The task role is additionally *denied* deletion and retention manipulation, and
that deny does more work than it first appears: Object Lock does **not** refuse
a delete marker or an overwrite, so IAM is what stops either being attempted.

**Content** — no Object Lock, 90-day lifecycle expiry, not versioned. C-R8 wants
personal data erased once its purpose ends, and content under Object Lock could
not be erased on request. The lifecycle is a backstop; the application deletes
sooner.

Both obligations hold only because they apply to disjoint data. That is why
they are two buckets and not one with prefixes.

> **Object Lock cannot be enabled after creation.** If the audit bucket is ever
> replaced, the replacement must be created with it on from the start.

## First deploy

```bash
cd infra
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python app.py                      # synthesise, no AWS call
npx cdk bootstrap                            # once per account/region
npx cdk deploy AitVoice-Platform-US
npx cdk deploy AitVoice-Service-US
```

Then run the migration once against the new database, as the owner, with the
credentials CDK generated into Secrets Manager:

```bash
AIT_DB_HOST=<DbEndpoint output> AIT_DB_NAME=aitvoice \
AIT_DB_OWNER_USER=postgres AIT_DB_OWNER_PASSWORD=<from Secrets Manager> \
uv run ait-voice-migrate
```

The migration creates `ait_app` with the placeholder password from
`001_initial.sql`. Replace it with the generated one before the service serves
anything:

```sql
ALTER ROLE ait_app PASSWORD '<AppDbSecretArn -> password>';
```

## What is deliberately not done yet

**The API load balancer is still HTTP.** The voice service gets HTTPS when a
certificate is supplied; the operator API does not yet, because no domain is
configured for it. **PHI must not traverse that listener** — and the clinic view
serves transcripts, so this blocks real use of the console, not just a nicety.

**The voice service now deploys**, on its own load balancer, but only when you
supply a certificate:

```bash
npx cdk deploy AitVoice-Service-US \
  -c voiceDomain=voice.example.com \
  -c voiceCertificateArn=arn:aws:acm:us-east-1:...:certificate/...
```

No certificate, no voice service — and that is not a convenience. Twilio requires
HTTPS for the webhook and `wss://` for the relay socket, so a plaintext voice
service cannot work at all, and the transcript it would carry is PHI. Without
the certificate the stack deploys the API alone and emits an output saying why.

Two things about it differ from the API deliberately.

**Its own load balancer**, because of idle timeout. A ConversationRelay socket
stays open for the length of a call, and the ALB default of **60 seconds would
cut every conversation past a minute** — mid-sentence, with a patient on the
line. The voice balancer is set to 900s. Raising that on a shared balancer would
apply it to the operator console too, where a minutes-long idle connection is a
leak rather than a call. Deregistration delay is 300s for the same reason: a
deploy should let a call finish.

**Its secrets come from Secrets Manager**, not the task definition:
`AIT_RELAY_TOKEN_SECRET` (generated by the platform stack) and
`TWILIO_AUTH_TOKEN` (created empty — fill it from the Twilio console, since a
vendor credential cannot be generated). The service refuses to start without
either, which is what stops the `REPLACE-ME` placeholder reaching production
quietly.

`scripts/check_infra.py --require-voice` asserts all of that on every push: wss
only, secrets not plaintext, an idle timeout long enough for a call, an HTTPS
listener with a certificate, and blank storage roots so `build_storage` refuses
rather than falling back to the filesystem audit log.

The image's second entrypoint is what the task definition runs:

```bash
uv run uvicorn --factory ait_voice.api.voice_main:voice_app
```

It needs, and refuses to start without, all of:

| Variable | Why it refuses |
|---|---|
| `AIT_RELAY_WS_URL` | the `wss://` address put in the TwiML; without it Twilio is told to connect nowhere |
| | must be `wss://` — a plain `ws://` carries the transcript in clear text, and C-R2 makes that PHI |
| `TWILIO_AUTH_TOKEN` | validates the webhook signature; absent, every request would have to be treated as forged, which is the same as accepting them all |
| `AIT_RELAY_TOKEN_SECRET` | signs the token authorising a relay socket; absent, the WebSocket accepts anyone |

Two things about its security are worth knowing before it is exposed.

The **webhook is signed by Twilio** and the signature is checked, using Twilio's
own validator rather than a reimplementation.

The **WebSocket is not signed by anything**. Twilio opens a plain connection to
whatever URL the TwiML named, carrying no credential. So the webhook mints a
short-lived HMAC token binding the call to its tenant and the URL carries it;
the socket verifies before accepting. That also solves tenant continuity across
tasks — with two containers behind a load balancer, the webhook and the socket
land on different ones, so the tenant cannot be remembered between them.

A US call is currently **refused at the socket** by the BAA gate, and that is
C-R1 working rather than a defect: `compliance/baa-register.toml` has no
executed agreement for Twilio. India calls are unaffected. When that refusal
stops firing, D-05 has completed.

**The CI deploy role is wider than it should be.** `PowerUserAccess` plus IAM is
enough for CDK and more than a production deploy role should carry. Narrowing it
means enumerating what each stack touches. Do that before first production use.

**The audit and content stores still write to local disk in the application.**
`S3AuditLog` exists and is tested; nothing constructs it yet. `ContentStore` has
no S3 backend at all. Both need wiring to the buckets this stack creates —
otherwise the buckets sit empty while the containers write to their own
filesystems, which is the failure this whole design was meant to prevent.

**India is commented out** in `app.py`. C-T1 makes per-region deployment a hard
constraint and the shape is there, but the pilot is US-first and India outbound
is blocked on D-04 regardless.

## The CI gate

`.github/workflows/ci.yml` runs an `infra` job on every push: synthesise,
`cfn-lint`, then `scripts/check_infra.py`. The last one is not a syntax check —
it asserts Object Lock mode and duration, the content expiry, encryption at
rest, and the deny on audit deletion. A template can be perfectly valid and have
quietly lost every one of them.
