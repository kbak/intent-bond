"""Documentation examples must not fail the shared OFT import diagnostic."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from test_recovery import RecoveryFixture
from test_workflow import WorkflowFixture

from intentbond.common import read_json, write_json
from intentbond.oft import annotation_diagnostics

GUIDE = """# Annotation examples

```python
# [impl->req~session-expiration~1]
```

~~~javascript
// [impl->req~session-expiration~1]
~~~

````markdown
```python
# [impl->req~session-expiration~1]
```
~~~
// [impl->req~session-expiration~1]
`````
"""


class AnnotationDiagnosticTests(unittest.TestCase):
    def test_fences_preserve_line_numbers_and_diagnostics_outside_examples(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            content = GUIDE + "<!-- [impl->req~session-expiration~1] -->\n"
            (root / "guide.md").write_text(content)
            snap = SimpleNamespace(root=root, manifest=[{"path": "guide.md"}])
            line = len(content.splitlines())
            self.assertEqual(annotation_diagnostics(snap, ["."], []), [f"guide.md:{line}"])
            imported = [{"path": "guide.md", "line": line, "type": "impl"}]
            self.assertEqual(annotation_diagnostics(snap, ["."], imported), [])

    def test_fence_like_text_does_not_hide_source_annotations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source.unknown").write_text("```\n# [impl->req~session-expiration~1]\n")
            snap = SimpleNamespace(root=root, manifest=[{"path": "source.unknown"}])
            self.assertEqual(annotation_diagnostics(snap, ["."], []), ["source.unknown:2"])


class DocumentationWorkflowTests(WorkflowFixture):
    def test_imported_prose_id_gets_actionable_authoring_error(self):
        (self.repo / "guide.md").write_text(
            "# Examples\n`req~illustration~1` is only an example.\n"
        )
        self.configure(lambda scope: scope["inputs"].append("guide.md"))
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        result = self.run_check()
        # [utest->req~ib-markdown-declarations~1]
        self.assert_problem(result, "guide.md:2")
        self.assertIn("prefix an illustrative ID with prose", str(result["diagnostics"]))
        (self.repo / "guide.md").write_text(
            "# Examples\nExample: `req~illustration~1` is literal.\n"
        )
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        self.assertEqual(self.run_check()["status"], "passed")

    def test_check_accepts_fenced_annotation_examples(self):
        for name in ("guide.md", "guide.markdown"):
            (self.repo / name).write_text(GUIDE)
        self.configure(lambda scope: scope["inputs"].extend(["guide.md", "guide.markdown"]))
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        result = self.run_check()
        self.assertEqual(result["status"], "passed", result)


class DocumentationRecoveryTests(RecoveryFixture):
    def test_review_only_markdown_does_not_grant_recovery_rewrite_permission(self):
        (self.repo / "fixture.md").write_text("An executable documentation fixture.\n")
        self.commit()
        self.draft()
        scope_path = self.bundle / "draft/scope.json"
        scope = read_json(scope_path)
        scope["review_paths"] = ["fixture.md"]
        write_json(scope_path, scope)
        (self.bundle / "draft/fixture.md").write_text("A changed fixture.\n")
        result = self.run_check()
        # [utest->req~ib-recovery-edits~1]
        self.assertEqual(result["status"], "rejected")
        self.assertNotEqual(result["proposal_checks"], "passed")
        self.assertIn("fixture.md", str(result["diagnostics"]))

    def test_recovery_accepts_fenced_annotation_examples(self):
        (self.repo / "guide.md").write_text(GUIDE)
        self.commit()
        self.draft()
        scope_path = self.bundle / "draft/scope.json"
        scope = read_json(scope_path)
        scope["inputs"].append("guide.md")
        scope["specification_paths"].append("guide.md")
        write_json(scope_path, scope)
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        self.assertEqual(result["proposal_checks"], "passed")
