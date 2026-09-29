"""Properties over OFT-exported record shapes; graph validity stays OFT's job."""

import copy
import unittest
from pathlib import Path

from hypothesis import example, given, settings
from hypothesis import strategies as st

from intentbond.review import changes, revision_diagnostics
from intentbond.snapshot import Snapshot

SEARCH = settings(max_examples=100, database=None, derandomize=True, deadline=None, print_blob=True)
SCOPE = {
    "specification_paths": ["spec"],
    "test_paths": ["tests"],
    "policy": {"require_revision_increase": True},
}
EMPTY = Snapshot(Path("."), "fixture", "worktree", [])


def requirement(name, revision, description):
    return {
        "key": f"req~{name}",
        "id": f"req~{name}~{revision}",
        "revision": revision,
        "path": "spec/requirements.md",
        "line": 1,
        "content": {"description": description},
    }


class RevisionPropertyTests(unittest.TestCase):
    @SEARCH
    @example(revision=1, increase=1, description="")
    @given(
        revision=st.integers(1, 100),
        increase=st.integers(1, 10),
        description=st.text(alphabet="abc XYZ012\n", max_size=30),
    )
    def test_changed_promise_remains_reviewable_and_needs_higher_revision(
        self, revision, increase, description
    ):
        original = requirement("promise", revision, description)
        changed = requirement("promise", revision, description + "!")
        review = changes(EMPTY, EMPTY, [original], [changed], SCOPE)
        # [utest->req~ib-revision-policy~1]
        self.assertEqual(len(review), 1)
        self.assertTrue(revision_diagnostics(review, SCOPE))
        revised = requirement("promise", revision + increase, description + "!")
        review = changes(EMPTY, EMPTY, [original], [revised], SCOPE)
        self.assertEqual(review[0]["before"], original)
        self.assertEqual(review[0]["after"], revised)
        self.assertEqual(revision_diagnostics(review, SCOPE), [])
        # A revision decrease is forbidden even when prose has not changed.
        older = requirement("promise", revision - 1, description)
        self.assertTrue(
            revision_diagnostics(changes(EMPTY, EMPTY, [original], [older], SCOPE), SCOPE)
        )
        # Disabling the bump policy never removes the content edit from review.
        permissive = {**SCOPE, "policy": {"require_revision_increase": False}}
        review = changes(EMPTY, EMPTY, [original], [changed], permissive)
        self.assertEqual(len(review), 1)
        self.assertEqual(revision_diagnostics(review, permissive), [])

    @SEARCH
    @example(revisions=[0], removed=0)
    @given(
        revisions=st.lists(st.integers(0, 100), min_size=1, max_size=8), removed=st.integers(0, 7)
    )
    def test_removal_cannot_disappear_from_review(self, revisions, removed):
        before = [
            requirement(f"promise-{i}", revision, "Keep this promise")
            for i, revision in enumerate(revisions)
        ]
        removed %= len(before)
        after = before[:removed] + before[removed + 1 :]
        review = changes(EMPTY, EMPTY, before, after, SCOPE)
        self.assertEqual(len(review), 1)
        self.assertEqual(review[0]["before"], before[removed])
        self.assertIsNone(review[0]["after"])

    @SEARCH
    @given(
        revisions=st.lists(st.integers(0, 100), min_size=1, max_size=8), line=st.integers(1, 1000)
    )
    def test_order_and_locations_do_not_change_requirement_meaning(self, revisions, line):
        before = [
            requirement(f"promise-{i}", revision, "Same meaning")
            for i, revision in enumerate(revisions)
        ]
        after = copy.deepcopy(before[::-1])
        for item in after:
            item.update(path="spec/moved.md", line=line)
        # File moves still need review even though no artifact meaning changed.
        old = Snapshot(Path("."), "fixture", "worktree", [{"path": "spec/requirements.md"}])
        new = Snapshot(Path("."), "fixture", "worktree", [{"path": "spec/moved.md"}])
        review = changes(old, new, before, after, SCOPE)
        self.assertEqual({item["kind"] for item in review}, {"file"})
        self.assertEqual(
            {item["path"] for item in review}, {"spec/requirements.md", "spec/moved.md"}
        )
