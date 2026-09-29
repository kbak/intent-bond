"""Property discovery stays historical; executable strengthening follows adoption."""

from pathlib import Path

from test_recovery import RecoveryFixture

from intentbond.common import read_json
from intentbond.runner import check

REQ = "req~session-expiration~1"
HANDOFF = """

## Property strengthening handoff

| Obligation | Existing check | Proposed check and assumptions | Next action |
| --- | --- | --- | --- |
| req~session-expiration~1 | tests/test_session.py checks the documented 30-minute boundary | Expiry stays true as nonnegative inactivity seconds increase; sample whole minutes up to one hour | Add a bounded monotonicity check after adoption; same timeout obligation |
"""
PROPERTY_TEST = """import unittest

from session import expired


class ExpirationProperties(unittest.TestCase):
    # [utest->req~session-expiration~1]
    def test_expiration_is_monotonic(self):
        for inactive in range(0, 3601, 60):
            if expired(inactive):
                self.assertTrue(expired(inactive + 60), f"Inactivity: {inactive}")
"""


class PropertyOnboardingTests(RecoveryFixture):
    def test_handoff_then_strengthening_preserves_recovery_and_finds_a_defect(self):
        self.draft()
        workspace = Path(self.record["workspace"])
        requirements = workspace / "requirements.md"
        requirements.write_text(
            requirements.read_text().replace(f"`{REQ}`", f"`{REQ}`\nStatus: draft") + HANDOFF
        )
        self.claims["items"][0]["notes"] = (
            "Existing boundary checks support the documented timeout; "
            "the proposed bounded monotonicity check has not been executed."
        )
        self.save_claims()
        recovered = self.run_check()
        recovery_output = self.out
        self.assertEqual(recovered["status"], "review_required", recovered)
        original_evidence = read_json(recovery_output / "check/evidence.json")["predicate"]
        self.assertEqual(original_evidence["tests"]["counts"]["total"], 1)
        self.assertEqual(
            original_evidence["requirements"]["candidate"][0]["content"]["status"], "draft"
        )

        # A proposed property must not manufacture tests as historical evidence.
        proposed_test = workspace / "tests/test_properties.py"
        proposed_test.write_text(PROPERTY_TEST)
        premature = self.run_check()
        self.assertEqual(premature["status"], "rejected", premature)
        self.assertIn("tests/test_properties.py", " ".join(premature["diagnostics"]))
        self.assertTrue(proposed_test.exists())  # Rejection never discards authored work.
        proposed_test.unlink()

        # Simulate the caller's explicit review and adoption of this fixture.
        if self.isolated:
            self.git("apply", "--check", str(recovery_output / "proposal.patch"))
            self.git("apply", str(recovery_output / "proposal.patch"))
        accepted = self.repo / "requirements.md"
        accepted.write_text(accepted.read_text().replace("Status: draft", "Status: approved"))
        self.commit()
        baseline = self.git("rev-parse", "HEAD").strip()
        adopted = check(self.repo, None, baseline, baseline, self.root / "adopted", self.jar)
        self.assertEqual(adopted["status"], "passed", adopted)

        # Strengthen through normal development, reusing the original obligation.
        (self.repo / "tests/test_properties.py").write_text(PROPERTY_TEST)
        strengthened = check(
            self.repo, None, baseline, "worktree", self.root / "strengthened", self.jar
        )
        self.assertEqual(strengthened["status"], "review_required", strengthened)
        self.assertEqual(strengthened["tests"]["status"], "passed")
        self.assertEqual(strengthened["tests"]["counts"]["total"], 2)
        self.assertEqual([item["id"] for item in strengthened["requirements"]["candidate"]], [REQ])
        self.assertEqual(
            strengthened["requirements"]["candidate"][0]["content"]["status"], "approved"
        )

        # The original boundary examples still pass this defect; the new property fails.
        implementation = self.repo / "session.py"
        implementation.write_text(
            implementation.read_text().replace(
                "inactive_seconds >= 30 * 60", "30 * 60 <= inactive_seconds < 2400"
            )
        )
        broken = check(self.repo, None, baseline, "worktree", self.root / "broken", self.jar)
        self.assertEqual(broken["status"], "rejected", broken)
        self.assertEqual(broken["tests"]["counts"]["passed"], 1)
        self.assertEqual(broken["tests"]["counts"]["failed"], 1)
        self.assertFalse((self.bundle / "source/tests/test_properties.py").exists())
        self.assertEqual(
            read_json(recovery_output / "check/evidence.json")["predicate"], original_evidence
        )
