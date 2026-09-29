"""Restructure documentation against original evidence in both recovery modes."""

import copy
import shutil
from pathlib import Path

from test_recovery import FIXTURE, RecoveryFixture

from intentbond.common import read_json, write_json
from intentbond.oft import import_items
from intentbond.runner import check

REQ = "req~session-expiration~1"


class DocumentRecoveryTests(RecoveryFixture):
    def test_accidental_original_prose_declaration_can_be_reconciled(self):
        self.structured_draft("\n## Example\n`req~illustration~1` is only an example.\n")
        with (self.workspace / "requirements.md").open("a") as target:
            target.write("\n## Example\nExample: `req~illustration~1` is only an example.\n")
        self.document_change("requirements.md")
        self.mapping("req~illustration~1", [])
        result = self.run_check()
        # [utest->req~ib-markdown-declarations~1]
        self.assertEqual(result["status"], "review_required", result)
        mappings = read_json(self.out / "documentation-review.json")["requirement_mappings"]
        removed = next(item for item in mappings if item["from"] == "req~illustration~1")
        self.assertEqual(removed["proposed"], [])

    def structured_draft(self, extra=""):
        for name in ("requirements.md", "session.py", "tests/test_session.py"):
            shutil.copyfile(FIXTURE / name, self.repo / name)
        if extra:
            with (self.repo / "requirements.md").open("a") as target:
                target.write(extra)
        self.commit()
        self.draft()

    @property
    def workspace(self):
        return Path(self.record["workspace"])

    def document_change(self, name, meaning="preserved"):
        lines = (self.bundle / "source" / name).read_text().splitlines()
        self.claims["document_changes"] = [
            {
                "path": name,
                "summary": "Consolidate the original session documentation into the baseline.",
                "meaning": meaning,
                "sources": [
                    {
                        "path": name,
                        "start_line": 1,
                        "end_line": len(lines),
                        "quote": "\n".join(lines),
                        "role": "intent",
                    }
                ],
            }
        ]
        self.save_claims()

    def mapping(self, source=REQ, targets=None):
        self.claims["requirement_mappings"] = [
            {
                "from": source,
                "to": [REQ] if targets is None else targets,
                "reason": "Proposed consolidation; review the original and proposed obligations.",
            }
        ]
        self.save_claims()

    def test_unstructured_readme_can_be_rewritten_with_original_citations(self):
        self.draft()
        scope = read_json(self.workspace / "scope.json")
        scope["inputs"].append("README.md")
        scope["specification_paths"].append("README.md")
        write_json(self.workspace / "scope.json", scope)
        (self.workspace / "README.md").write_text(
            "# Sessions\n\nSee [session requirements](requirements.md) for the inactivity policy.\n"
        )
        result = self.run_check()
        # [utest->req~ib-recovery-edits~1]
        self.assertIn("Missing document change review: README.md", " ".join(result["diagnostics"]))
        self.document_change("README.md")
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        self.assertEqual(result["original_requirement_count"], 0)
        review = read_json(self.out / "documentation-review.json")
        citation = review["document_changes"][0]["sources"][0]
        self.assertIn("30 minutes", citation["quote"])
        self.assertTrue(citation["source_sha256"])
        self.assertEqual((self.bundle / "source/README.md").read_text(), citation["quote"] + "\n")
        self.assertEqual(self.git("diff", "--cached"), "")

    def test_document_move_preserves_identity_and_patch_can_adopt_deletion(self):
        self.structured_draft()
        (self.workspace / "docs").mkdir()
        (self.workspace / "requirements.md").rename(self.workspace / "docs/baseline.md")
        scope = read_json(self.workspace / "scope.json")
        scope["inputs"] = ["."]
        scope["specification_paths"] = ["requirements.md", "docs"]
        write_json(self.workspace / "scope.json", scope)
        self.document_change("requirements.md")
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        review = read_json(self.out / "documentation-review.json")
        self.assertEqual(review["document_changes"][0]["change"], "deleted")
        mapping = review["requirement_mappings"][0]
        self.assertTrue(mapping["automatic"])
        self.assertEqual(mapping["original"]["path"], "requirements.md")
        self.assertEqual(mapping["proposed"][0]["path"], "docs/baseline.md")
        self.assertTrue((self.bundle / "source/requirements.md").exists())
        if self.isolated:
            self.assertFalse((self.out / "proposed/requirements.md").exists())
            self.git("apply", "--check", str(self.out / "proposal.patch"))
            self.git("apply", str(self.out / "proposal.patch"))
        self.assertFalse((self.repo / "requirements.md").exists())
        self.commit()  # Simulate the caller's acceptance, outside the recovery engine.
        adopted = check(self.repo, None, "HEAD", "HEAD", self.root / "adopted", self.jar)
        self.assertEqual(adopted["status"], "passed", adopted)

    def test_reworded_requirement_needs_explicit_accounting_even_with_same_id(self):
        self.structured_draft()
        path = self.workspace / "requirements.md"
        path.write_text(
            path.read_text().replace("A session expires when", "A session must expire when")
        )
        self.document_change("requirements.md", meaning="uncertain")
        result = self.run_check()
        # [utest->req~ib-recovery-lineage~1]
        self.assertIn("Missing requirement mapping", " ".join(result["diagnostics"]))
        self.mapping()
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        review = read_json(self.out / "documentation-review.json")
        self.assertEqual(review["document_changes"][0]["meaning"], "uncertain")
        mapping = review["requirement_mappings"][0]
        self.assertFalse(mapping["automatic"])
        self.assertNotEqual(mapping["original"]["content"], mapping["proposed"][0]["content"])

    def test_revision_and_coverage_comments_can_be_retargeted_without_logic_changes(self):
        self.structured_draft()
        target = "req~session-expiration~2"
        for name in ("requirements.md", "session.py", "tests/test_session.py"):
            path = self.workspace / name
            path.write_text(path.read_text().replace(REQ, target))
        self.claims["items"][0]["id"] = target
        self.document_change("requirements.md")
        self.mapping(targets=[target])
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        self.assertIn(REQ, (self.bundle / "source/tests/test_session.py").read_text())
        path = self.workspace / "tests/test_session.py"
        path.write_text(
            path.read_text().replace("self.assertTrue(expired(1800))", "self.assertTrue(True)")
        )
        result = self.run_check()
        self.assertEqual(result["status"], "rejected", result)
        self.assertIn("tests/test_session.py", " ".join(result["diagnostics"]))

    def test_split_requires_complete_valid_targets(self):
        self.structured_draft()
        target = "req~session-active~1"
        with (self.workspace / "requirements.md").open("a") as path:
            path.write(
                f"\n### Active session\n`{target}`\n\nAn active session remains valid.\n\nNeeds: impl, utest\n"
            )
        for name, kind in (("session.py", "impl"), ("tests/test_session.py", "utest")):
            path = self.workspace / name
            path.write_text(f"# [{kind}->{target}]\n" + path.read_text())
        claim = copy.deepcopy(self.claims["items"][0])
        claim["id"] = target
        self.claims["items"].append(claim)
        self.document_change("requirements.md")
        self.mapping(targets=[target])
        result = self.run_check()
        # [utest->req~ib-recovery-lineage~1]
        self.assertIn("surviving original ID", " ".join(result["diagnostics"]))
        self.mapping(targets=[REQ, target])
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        self.assertEqual(
            len(
                read_json(self.out / "documentation-review.json")["requirement_mappings"][0][
                    "proposed"
                ]
            ),
            2,
        )

    def test_removed_original_design_id_cannot_disappear_through_coverage_policy(self):
        original = "dsn~legacy-choice~1"
        self.structured_draft(f"\n### Legacy choice\n`{original}`\n\nAn older design choice.\n")
        self.document_change("requirements.md", meaning="changed")
        result = self.run_check()
        # [utest->req~ib-recovery-lineage~1]
        self.assertIn(
            f"Missing requirement mapping for changed or removed item: {original}",
            " ".join(result["diagnostics"]),
        )
        self.mapping(source=original, targets=[])
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        review = read_json(self.out / "documentation-review.json")
        removed = next(m for m in review["requirement_mappings"] if m["from"] == original)
        self.assertEqual(removed["proposed"], [])
        self.assertEqual(result["original_requirement_count"], 2)
        # Several originals may map to a single consolidated requirement.
        self.mapping(source=original, targets=[REQ])
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)

    def test_restructuring_does_not_bypass_coverage_floors(self):
        self.structured_draft()
        path = self.workspace / "requirements.md"
        path.write_text(path.read_text().replace("Needs: impl, utest", "Needs: impl"))
        self.document_change("requirements.md", meaning="changed")
        self.mapping()
        result = self.run_check()
        self.assertEqual(result["status"], "rejected", result)
        self.assertIn("must retain Needs", " ".join(result["diagnostics"]))

    def test_document_review_cannot_cite_generated_wording(self):
        self.structured_draft()
        path = self.workspace / "requirements.md"
        path.write_text(path.read_text() + "\nAdditional explanation.\n")
        self.document_change("requirements.md")
        self.claims["document_changes"][0]["sources"][0]["quote"] = path.read_text().rstrip()
        self.save_claims()
        result = self.run_check()
        self.assertIn("quote does not match", " ".join(result["diagnostics"]))

    def test_coverage_comment_moves_do_not_require_generated_id_mappings(self):
        # Includes an unnamed tag with an explicit revision: revision alone
        # does not distinguish generated identities from authored ones.
        comments = f"<!-- [impl->{REQ}] [impl~~02->{REQ}] -->\n"
        original = comments + (FIXTURE / "requirements.md").read_text()
        (self.repo / "requirements.md").write_text(original)
        self.commit()
        self.draft()
        path = self.workspace / "requirements.md"
        path.write_text(original)
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)

        path.write_text("\n" + original)
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        self.assertEqual(result["original_requirement_count"], 1)
        before = import_items(self.out / "original-items.xml", self.bundle / "source")
        after = import_items(self.out / "check/candidate-items.xml", self.workspace)
        before_tags = {i["id"] for i in before if i["type"] == "impl"}
        after_tags = {
            i["id"] for i in after if i["type"] == "impl" and i["path"] == "requirements.md"
        }
        self.assertEqual(len(before_tags), 2)
        self.assertEqual(len(after_tags), 2)
        self.assertNotEqual(before_tags, after_tags)
        self.assertEqual(
            [
                m["from"]
                for m in read_json(self.out / "documentation-review.json")["requirement_mappings"]
            ],
            [REQ],
        )

        (self.workspace / "docs").mkdir()
        path.rename(self.workspace / "docs/baseline.md")
        scope = read_json(self.workspace / "scope.json")
        scope["inputs"] = ["."]
        scope["specification_paths"] = ["requirements.md", "docs"]
        write_json(self.workspace / "scope.json", scope)
        self.document_change("requirements.md")
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        self.assertEqual(result["original_requirement_count"], 1)

    def test_named_coverage_id_still_requires_mapping_beside_an_unnamed_tag(self):
        # This authored ID deliberately resembles an OFT-generated ID and
        # shares a line/type with an unnamed tag. Neither should hide it.
        authored = "impl~session-expiration-2537736602~0"
        spelling = "impl~session-expiration-2537736602~00"
        body = (FIXTURE / "requirements.md").read_text()
        (self.repo / "requirements.md").write_text(
            f"<!-- [{spelling}->{REQ}] [impl->{REQ}] -->\n" + body
        )
        self.commit()
        self.draft()
        (self.workspace / "requirements.md").write_text(f"<!-- [impl->{REQ}] -->\n" + body)
        self.document_change("requirements.md")
        result = self.run_check()
        self.assertIn(
            f"Missing requirement mapping for changed or removed item: {authored}",
            " ".join(result["diagnostics"]),
        )
        self.mapping(source=authored, targets=[])
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        self.assertEqual(result["original_requirement_count"], 2)

    def test_original_duplicate_ids_remain_an_explicit_recovery_limitation(self):
        self.structured_draft(extra="\n" + (FIXTURE / "requirements.md").read_text())
        self.document_change("requirements.md")
        result = self.run_check()
        self.assertEqual(result["check_status"], "passed", result)
        self.assertEqual(result["status"], "error", result)
        self.assertIn(
            f"Duplicate specification ID in recovery: {REQ}", " ".join(result["diagnostics"])
        )


class InPlaceDocumentRecoveryTests(DocumentRecoveryTests):
    isolated = False
