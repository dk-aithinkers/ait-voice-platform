"""The guard on `scripts/commit_workspace.py`.

That script opens a pull request and squash-merges it once CI is green, with no
human in the loop. That is fine for the AI-DLC workspace tree — audit shards the
hook appended, record state, memory — and it is emphatically not fine for
anything else. The only thing standing between the two is `check_only_workspace`.

So this is tested on the same argument `team.md` makes about coverage
exclusions and `docs/ci.md` makes about the gates themselves: a check that
passes because it is broken reports green while checking nothing. Here the
consequence is specific — a source change reaching `main` inside a commit
labelled "workspace state", which is the unreviewed merge the branch protection
rule exists to prevent.
"""

from __future__ import annotations

import subprocess

import pytest
import scripts.commit_workspace as cw
from scripts.commit_workspace import (
    WORKSPACE_PREFIX,
    Refused,
    check_only_workspace,
    porcelain_paths,
)


class TestItAcceptsTheWorkspaceTree:
    def test_a_single_modified_audit_shard(self) -> None:
        status = " M aidlc/spaces/default/intents/260826-x/audit/laptop-abc.md"

        assert check_only_workspace(status) == [
            "aidlc/spaces/default/intents/260826-x/audit/laptop-abc.md"
        ]

    def test_several_workspace_files_of_mixed_status(self) -> None:
        status = "\n".join(
            [
                " M aidlc/spaces/default/intents/260826-x/aidlc-state.md",
                "?? aidlc/spaces/default/intents/260826-x/inception/user-stories/memory.md",
                "A  aidlc/spaces/default/knowledge/documents/notes.md",
            ]
        )

        assert len(check_only_workspace(status)) == 3

    def test_a_rename_is_read_as_its_destination(self) -> None:
        status = "R  aidlc/spaces/default/a.md -> aidlc/spaces/default/b.md"

        assert check_only_workspace(status) == ["aidlc/spaces/default/b.md"]


class TestItRefusesEverythingElse:
    def test_a_source_change_refuses_the_whole_batch(self) -> None:
        """The failure this file exists for."""
        status = "\n".join(
            [
                " M aidlc/spaces/default/intents/260826-x/audit/laptop-abc.md",
                " M src/ait_voice/core/audit.py",
            ]
        )

        with pytest.raises(Refused, match="outside"):
            check_only_workspace(status)

    def test_the_refusal_names_the_offending_path(self) -> None:
        """A refusal you have to go and investigate gets worked around."""
        status = " M src/ait_voice/api/app.py"

        with pytest.raises(Refused, match=r"src/ait_voice/api/app\.py"):
            check_only_workspace(status)

    def test_an_empty_tree_is_refused_rather_than_committed(self) -> None:
        """An empty batch would open a pull request and burn a CI run on nothing."""
        with pytest.raises(Refused, match="nothing to commit"):
            check_only_workspace("")

    def test_a_nested_path_that_merely_contains_the_prefix_is_refused(self) -> None:
        """`startswith`, not `in` — the difference is a code path onto main."""
        status = " M src/aidlc/sneaky.py"

        with pytest.raises(Refused, match="outside"):
            check_only_workspace(status)

    def test_a_sibling_directory_sharing_the_stem_is_refused(self) -> None:
        """`aidlc-notes/` is not `aidlc/`, which is why the prefix carries a slash."""
        status = " M aidlc-notes/scratch.md"

        with pytest.raises(Refused, match="outside"):
            check_only_workspace(status)

    def test_a_dotfile_at_the_root_is_refused(self) -> None:
        """CI config is exactly what must not ride along unreviewed."""
        status = " M .github/workflows/ci.yml"

        with pytest.raises(Refused, match="outside"):
            check_only_workspace(status)


class TestThePrefixItself:
    def test_it_carries_a_trailing_slash(self) -> None:
        """Without it, `aidlc-anything` would pass the guard."""
        assert WORKSPACE_PREFIX.endswith("/")


class TestTheSeamThatActuallyBroke:
    """`git()` must not strip the leading space off a porcelain line.

    These tests exist because the first version of this file did not have
    them, and the bug walked straight past ten passing tests into `main`.
    Every case above hands `check_only_workspace` a hand-written status
    string, which never exercises the function that reads git — and that
    function ended with `.strip()`, which eats the significant leading space
    of " M path". Every path then parsed one character short, so the guard
    refused batches it should have accepted.

    The lesson is the one this repository keeps relearning: a test that skips
    the seam proves the seam works.
    """

    def test_git_preserves_the_leading_status_space(self, monkeypatch) -> None:
        """The regression itself, pinned at the function that had the bug."""
        raw = " M aidlc/spaces/default/x.md\n"

        class _Result:
            stdout = raw

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Result())

        assert cw.git("status", "--porcelain") == " M aidlc/spaces/default/x.md"

    def test_the_whole_path_from_git_output_to_verdict(self, monkeypatch) -> None:
        """End to end over the real seam: git output in, accepted paths out."""
        raw = " M aidlc/a.md\n?? aidlc/b.md\n"

        class _Result:
            stdout = raw

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Result())

        assert check_only_workspace(cw.git("status", "--porcelain")) == [
            "aidlc/a.md",
            "aidlc/b.md",
        ]

    def test_a_stripped_line_is_refused_loudly_not_misparsed(self) -> None:
        """Belt and braces: if the space is ever lost again, say so plainly."""
        with pytest.raises(Refused, match="cannot parse a git status line"):
            porcelain_paths("M aidlc/x.md")

    def test_an_unstaged_modification_is_the_common_case(self) -> None:
        """A leading space is not an edge case — it is what the hook produces."""
        assert porcelain_paths(" M aidlc/x.md") == ["aidlc/x.md"]
