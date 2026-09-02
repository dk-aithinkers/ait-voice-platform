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

import pytest
from scripts.commit_workspace import WORKSPACE_PREFIX, Refused, check_only_workspace


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
