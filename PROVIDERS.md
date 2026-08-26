# Model providers

Two separate things in this repo use AI models. They are configured in different
places and have different constraints — don't confuse them.

| Layer | What it is | Configured in |
|---|---|---|
| **Tooling** | The model that runs the AI-DLC workflow itself (Claude Code) | `.claude/settings.json` + `.claude/settings.local.json` |
| **Product** | The models the voice platform calls at runtime (STT, LLM, TTS) | Application config — see [Product-side providers](#product-side-providers) |

---

## Tooling: which model runs AI-DLC

Claude Code runs Claude models only. It can reach them three ways — the Anthropic
API, AWS Bedrock, or Google Vertex — but it cannot run GPT or other non-Claude
models. Running AI-DLC on OpenAI means using a different harness (see
[Other harnesses](#other-harnesses)).

### The committed config is provider-neutral

`.claude/settings.json` is checked in and deliberately pins **no** provider. It
sets only `AWS_AIDLC_DEFAULT_SCOPE`. Whatever your Claude Code is authenticated
to is what the workflow uses, so the repo works for everyone on the team without
edits.

> The upstream AWS distribution ships this file pinned to Bedrock. We removed
> that pinning — with it in place the repo only works for someone who already has
> AWS Bedrock model access, and every call fails for everyone else. Nothing else
> in the AI-DLC install was modified.

### Per-machine overrides

`.claude/settings.local.json` is **gitignored** and takes precedence over
`settings.json`. This is where personal or machine-specific settings belong,
including credentials-adjacent ones like `AWS_PROFILE` that must never be
committed.

Two templates are provided:

- `.claude/settings.local.json.example` — upstream's general-purpose example
- `.claude/settings.local.json.bedrock` — ready-made Bedrock override

### Switching to Bedrock

**Easy path.** Run `claude`, pick **3rd-party platform → Amazon Bedrock** at the
login prompt. The wizard detects your credentials, region, and available models
and writes them to your user settings. Re-run `/setup-bedrock` any time to
change them. You still need step 1 below, once.

**Manual path.**

```bash
cp .claude/settings.local.json.bedrock .claude/settings.local.json
```

Then edit the region and uncomment `AWS_PROFILE` if you use one (rename the
`__AWS_PROFILE` key to `AWS_PROFILE`).

Either path needs the AWS account prepared once:

1. **Enable model access.** In the [Bedrock console](https://console.aws.amazon.com/bedrock/),
   open **Model catalog**, select each Anthropic model you'll use, and submit the
   use-case form. Access is granted immediately. Required once per account; in an
   AWS Organization the management account can submit once for all children.

2. **Attach IAM permissions** to your role or user:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "AllowModelAndInferenceProfileAccess",
         "Effect": "Allow",
         "Action": [
           "bedrock:InvokeModel",
           "bedrock:InvokeModelWithResponseStream",
           "bedrock:ListInferenceProfiles",
           "bedrock:GetInferenceProfile"
         ],
         "Resource": [
           "arn:aws:bedrock:*:*:inference-profile/*",
           "arn:aws:bedrock:*:*:application-inference-profile/*",
           "arn:aws:bedrock:*:*:foundation-model/*"
         ]
       }
     ]
   }
   ```

3. **Provide credentials** on the default AWS SDK chain — `aws configure`, an SSO
   profile (`aws sso login --profile <p>`), or exported `AWS_ACCESS_KEY_ID` etc.

4. **Set the region.** `AWS_REGION` is required; Claude Code does not read it from
   `~/.aws`. Verify the model exists there:

   ```bash
   aws bedrock list-inference-profiles --region <your-region>
   ```

### Switching back

Delete `.claude/settings.local.json`. The committed neutral config takes over.

### Other harnesses

AI-DLC 2.0 is "one core, many harnesses" — the `aidlc/` workspace shell is
byte-identical across every distribution, so workflow state, the audit trail,
and artifacts are shared. A workflow started under one harness can be continued
under another against the same repo.

Only the Claude Code surface (`.claude/`) is installed here. To add another,
copy its tree from `dist/<harness>/` in
[awslabs/aidlc-workflows](https://github.com/awslabs/aidlc-workflows) (branch
`v2`) — merging rather than overwriting `.gitignore`, which differs per harness:

| Harness | Provider | Tree |
|---|---|---|
| Codex CLI | OpenAI | `dist/codex/` → `.codex/` + `.agents/` + `AGENTS.md` |
| Cursor | Cursor's own | `bun dist/cursor/install.ts <project>` |
| opencode | configurable | `dist/opencode/` |
| GitHub Copilot | GitHub / BYOK | `dist/copilot/` (merge `.github/`) |
| Kiro IDE / CLI | Kiro's own | `dist/kiro-ide/` or `dist/kiro/` |

### MCP servers

`.mcp.json` declares `context7` and four AWS servers. **Missing credentials are
not blocking** — a server you have no credentials for is simply unavailable and
the workflow runs without it. Remove an entry from `.mcp.json` to drop it
entirely.

---

## Product-side providers

Separate concern, and the more consequential one: the STT, LLM, and TTS vendors
the voice platform calls at runtime.

These must be **swappable per deployment**. That is a compliance requirement, not
a preference:

- **US healthcare (HIPAA)** — every vendor touching call audio, transcripts, or
  caller identity needs a signed BAA. One vendor without one breaks the chain.
  Both AWS Bedrock and the Anthropic API offer BAAs.
- **India (DPDP)** — data residency pushes toward in-region processing, and
  regional-language TTS quality and cost differ sharply from US vendors.
- **Latency budgets differ by vertical** — an AOG parts desk and a collections
  campaign do not have the same tolerances.

So the platform core treats STT / LLM / TTS as adapters behind an interface,
selected by deployment region and vertical. No provider is hardcoded.

The concrete vendor matrix belongs in the NFR Requirements and NFR Design stages
of the AI-DLC workflow, where it gets captured as a tracked decision rather than
an implementation detail.
