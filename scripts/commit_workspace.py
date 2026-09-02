#!/usr/bin/env python3
"""Batch the AI-DLC workspace tree onto `main` in one step.

`CLAUDE.md` says to commit the `aidlc/` tree — the record, the audit shards,
memory and knowledge are version-controlled. Until now those changes rode along
with whatever code commit happened to be in flight. Branch protection ends that:
`main` requires four CI jobs with include-administrators on, so even a file the
hook appended on its own needs a branch, a pull request and a full CI run.

Doing that by hand every session is enough friction that the tree would simply
stop being committed, which is the outcome worth avoiding — an audit trail that
exists only on one laptop is not an audit trail. So the answer is to batch:
let the workspace accumulate, and run this occasionally.

    uv run python scripts/commit_workspace.py --dry-run
    uv run python scripts/commit_workspace.py
    uv run python scripts/commit_workspace.py --no-merge   # stop at the PR

**The guard is the point of this file.** It refuses to run if anything outside
`aidlc/` is dirty. Without that, a script that opens a PR and merges it once CI
is green becomes a way for source changes to reach `main` inside a commit
labelled "workspace state" — which is precisely the unreviewed merge that
`team.md` built the gate to prevent:

    a branch-protection rule the only committer can bypass unrecorded is not a
    gate, it is a suggestion

A tool that routinely auto-merges is exactly the kind of thing that quietly
becomes such a bypass, so the guard is tested rather than trusted; see
`tests/test_workspace_batch.py`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

#: The only path prefix this tool is ever allowed to commit.
WORKSPACE_PREFIX = "aidlc/"

REPO = "dk-aithinkers/ait-voice-platform"
API = "https://api.github.com"

#: Required check names are the job `name:` in ci.yml, not the job id — see
#: docs/ci.md. Rename a job there and this list must change with it.
REQUIRED_CHECKS = (
    "Python — lint, types, tests, coverage",
    "Compliance — BAA register",
    "Security — secrets and dependencies",
    "Web — lint, types, tests, build",
)


class Refused(RuntimeError):
    """The tool declined to act. Always a deliberate stop, never a crash."""


def git(*args: str) -> str:
    # S603/S607: a fixed argv with no shell, and `git` from PATH is the same
    # git the developer just used to clone this. Nothing here is interpolated
    # from a remote source; the only variable input is branch names this file
    # generates from a timestamp.
    result = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    # rstrip the trailing newline only. NEVER .strip(): porcelain status lines
    # begin with a significant space (" M path" for an unstaged modification),
    # and stripping it shifts every path left by one, so `aidlc/x` parses as
    # `idlc/x` and the guard refuses a batch it should have accepted. That was
    # a real bug here, and it survived because the tests fed hand-written
    # status strings straight to the parser instead of through this function.
    return result.stdout.rstrip("\n")


def porcelain_paths(status: str) -> list[str]:
    """Paths from `git status --porcelain=v1 -z`-style output, already split.

    Kept separate from the git call so the guard can be tested against literal
    status output rather than a repository.
    """
    paths = []
    for line in status.splitlines():
        if not line.strip():
            continue
        # Porcelain v1 is exactly two status characters, a space, then the
        # path. Validated rather than assumed: if the caller ever hands this
        # mangled input — a stripped leading space being the way that actually
        # happened — a silent mis-parse turns into a confusing refusal about a
        # path that does not exist. Fail loudly at the parse instead.
        if len(line) < 4 or line[2] != " ":
            raise Refused(
                f"cannot parse a git status line: {line!r}\n"
                "Expected two status characters, a space, then the path."
            )
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path.strip().strip('"'))
    return paths


def check_only_workspace(status: str) -> list[str]:
    """Return the workspace paths to commit, or refuse.

    Refuses on anything outside `aidlc/`, and refuses on an empty change set —
    an empty batch that opened a pull request would burn a CI run to commit
    nothing.
    """
    paths = porcelain_paths(status)
    if not paths:
        raise Refused("nothing to commit: the workspace tree is clean")
    stray = sorted(p for p in paths if not p.startswith(WORKSPACE_PREFIX))
    if stray:
        raise Refused(
            "refusing: changes outside "
            f"{WORKSPACE_PREFIX} are present, and this tool must never carry "
            "source changes onto main inside a workspace commit.\n  "
            + "\n  ".join(stray)
            + "\n\nCommit those through a normal reviewed pull request first."
        )
    return sorted(paths)


def token() -> str:
    """Reuse the git credential rather than asking for a second secret."""
    result = subprocess.run(  # noqa: S603
        ["git", "credential", "fill"],  # noqa: S607
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True,
        text=True,
        check=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("password="):
            return line[len("password=") :]
    raise Refused("no GitHub credential found; `git push` would not work either")


def api(
    path: str, tok: str, method: str = "GET", body: dict[str, Any] | None = None
) -> dict[str, Any]:
    url = f"{API}{path}"
    # S310 wants proof the scheme is not `file:` or something stranger. Asserted
    # rather than suppressed: `path` is built in this file today, but a checked
    # invariant survives someone later passing it something from outside.
    if not url.startswith("https://api.github.com/"):
        raise Refused(f"refusing a non-GitHub URL: {url!r}")
    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        url,
        method=method,
        data=json.dumps(body).encode() if body else None,
        headers={
            "Authorization": f"Bearer {tok}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "ait-voice-workspace-batch",
        },
    )
    try:
        with urllib.request.urlopen(request) as response:  # noqa: S310 - checked above
            payload: dict[str, Any] = json.loads(response.read())
            return payload
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise Refused(f"GitHub API {method} {path} -> {exc.code}\n{detail}") from exc


def checks_for(sha: str, tok: str) -> dict[str, str]:
    """Newest run per check name -> "status:conclusion"."""
    data = api(f"/repos/{REPO}/commits/{sha}/check-runs?per_page=50", tok)
    newest: dict[str, str] = {}
    for run in data.get("check_runs", []):
        newest.setdefault(run["name"], f"{run['status']}:{run.get('conclusion')}")
    return newest


def wait_for_checks(sha: str, tok: str, *, timeout_s: int = 1800) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        state = checks_for(sha, tok)
        pending = [
            name for name in REQUIRED_CHECKS if not state.get(name, "").startswith("completed")
        ]
        failed = [
            name
            for name in REQUIRED_CHECKS
            if state.get(name, "").startswith("completed") and not state[name].endswith(":success")
        ]
        if failed:
            raise Refused(
                "required check(s) failed, so nothing was merged:\n  "
                + "\n  ".join(f"{n} -> {state[n]}" for n in failed)
            )
        if not pending:
            print("  all four required checks green")
            return
        print(f"  waiting on {len(pending)} check(s)…", flush=True)
        time.sleep(20)
    raise Refused(f"checks did not complete within {timeout_s}s; nothing merged")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="show what would happen")
    parser.add_argument("--no-merge", action="store_true", help="open the PR and stop")
    parser.add_argument("--message", default="", help="extra context for the commit body")
    args = parser.parse_args(argv)

    try:
        status = git("status", "--porcelain")
        paths = check_only_workspace(status)
    except Refused as exc:
        print(f"\n{exc}\n", file=sys.stderr)
        return 1

    print(f"Workspace changes ({len(paths)} file(s)):")
    for path in paths:
        print(f"  {path}")

    if args.dry_run:
        print("\n--dry-run: nothing committed.")
        return 0

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    branch = f"workspace/{stamp}"
    body = (
        "The AI-DLC workspace tree: record state, audit shards, memory.\n\n"
        "Batched rather than committed per session. `main` requires four CI\n"
        "jobs with include-administrators on, so each of these needs a pull\n"
        "request and a full run — and doing that every session is enough\n"
        "friction that the tree would stop being committed at all, which is\n"
        "worse than the cost of batching.\n\n"
        "Contains no source changes; `scripts/commit_workspace.py` refuses to\n"
        "run when anything outside `aidlc/` is dirty."
    )
    if args.message:
        body += f"\n\n{args.message}"

    try:
        base = git("rev-parse", "--abbrev-ref", "HEAD")
        git("checkout", "-q", "-b", branch)
        git("add", "--", WORKSPACE_PREFIX)
        git("commit", "-q", "-m", f"Record AI-DLC workspace state ({stamp})", "-m", body)
        git("push", "-q", "origin", branch)
        sha = git("rev-parse", "HEAD")
        print(f"\nPushed {branch} ({sha[:7]})")

        tok = token()
        pull = api(
            f"/repos/{REPO}/pulls",
            tok,
            "POST",
            {
                "title": f"Record AI-DLC workspace state ({stamp})",
                "head": branch,
                "base": "main",
                "body": body,
            },
        )
        print(f"Opened #{pull['number']}: {pull['html_url']}")

        if args.no_merge:
            print("\n--no-merge: left open for you to merge.")
            return 0

        wait_for_checks(sha, tok)
        api(
            f"/repos/{REPO}/pulls/{pull['number']}/merge",
            tok,
            "PUT",
            {
                "merge_method": "squash",
                "sha": sha,
                "commit_title": f"Record AI-DLC workspace state ({stamp}) (#{pull['number']})",
                "commit_message": body,
            },
        )
        print(f"Squash-merged #{pull['number']}")

        git("checkout", "-q", base)
        git("pull", "-q", "--ff-only")
        git("push", "-q", "origin", "--delete", branch)
        git("branch", "-q", "-D", branch)
        print(f"Back on {base} at {git('rev-parse', '--short', 'HEAD')}")
    except (Refused, subprocess.CalledProcessError) as exc:
        detail = exc.stderr if isinstance(exc, subprocess.CalledProcessError) else exc
        print(f"\nStopped: {detail}\n", file=sys.stderr)
        print(f"The branch {branch} may still exist locally and on origin.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
