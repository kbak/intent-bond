"""OFT maturity stays distinct from origin, coverage and baseline acceptance."""

from pathlib import Path

from test_recovery import FIXTURE, RecoveryFixture

from intentbond.common import read_json

REQ = "req~session-expiration~1"


class RecoveryStatusTests(RecoveryFixture):
    def set_status(self, status):
        path = Path(self.record["workspace"]) / "requirements.md"
        path.write_text(path.read_text().replace(f"`{REQ}`", f"`{REQ}`\nStatus: {status}"))

    def imported_status(self):
        evidence = read_json(self.out / "check/evidence.json")["predicate"]
        return evidence["requirements"]["candidate"][0]["content"]["status"]

    def test_documented_and_inferred_drafts_remain_pending_review_after_checks(self):
        self.draft()
        self.set_status("draft")
        for origin in ("documented", "inferred"):
            with self.subTest(origin=origin):
                self.claims["items"][0]["origin"] = origin
                self.save_claims()
                result = self.run_check()
                # [utest->req~ib-recovery-draft-status~1]
                self.assertEqual(result["status"], "review_required", result)
                self.assertEqual(result["check_status"], "passed")
                self.assertEqual(self.imported_status(), "draft")
                claim = read_json(self.out / "provenance.json")["items"][0]
                self.assertEqual(claim["origin"], origin)

    def test_draft_status_does_not_hide_missing_test_coverage(self):
        self.draft()
        self.set_status("draft")
        path = Path(self.record["workspace"]) / "tests/test_session.py"
        path.write_bytes((self.bundle / "source/tests/test_session.py").read_bytes())
        result = self.run_check()
        # [utest->req~ib-recovery-draft-status~1]
        self.assertEqual(result["status"], "rejected", result)
        self.assertEqual(result["proposal_checks"], "passed")
        self.assertEqual(self.imported_status(), "draft")
        evidence = read_json(self.out / "check/evidence.json")["predicate"]
        self.assertEqual(evidence["tests"]["status"], "passed")
        self.assertNotEqual(evidence["trace"]["candidate"]["status"], "passed")

    def test_unchanged_approved_item_keeps_its_status_without_approving_recovery(self):
        (self.repo / "requirements.md").write_text(
            (FIXTURE / "requirements.md")
            .read_text()
            .replace(f"`{REQ}`", f"`{REQ}`\nStatus: approved")
        )
        self.commit()
        self.draft()
        self.set_status("approved")
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        self.assertEqual(self.imported_status(), "approved")
        review = read_json(self.out / "documentation-review.json")
        self.assertTrue(review["requirement_mappings"][0]["automatic"])
        self.assertEqual(review["document_changes"], [])
