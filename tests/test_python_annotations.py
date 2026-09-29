"""Python lexical boundaries apply to OFT imports and recovery edits alike."""

import unittest

from test_workflow import WorkflowFixture

from intentbond.common import CheckError
from intentbond.oft import import_items
from intentbond.python_comments import comment_lines
from intentbond.recovery import annotation_changes_only

TAG = "# [impl->req~session-expiration~1]"
EXAMPLES = '''EXAMPLE = """
# [impl->req~not-a-requirement~1]
# [req~malformed example->garbage]
"""
quoted = '# [impl->req~also-not-real~1]'
raw = r"""
# [impl->req~raw-example~1]
"""
'''


class PythonCommentTests(unittest.TestCase):
    def test_strings_are_absent_and_comment_locations_are_preserved(self):
        source = EXAMPLES + "\n" + TAG + "\nx = 1  " + TAG + "\n"
        view, comments = comment_lines(source.encode(), "example.py")
        self.assertNotIn(b"not-a-requirement", view)
        self.assertNotIn(b"malformed", view)
        self.assertEqual(comments, {10, 11})
        self.assertEqual(view.decode().splitlines()[9:], [TAG, " " * 7 + TAG])
        self.assertEqual(len(view.splitlines()), len(source.splitlines()))

    def test_encodings_and_physical_newlines(self):
        source = ("# coding: latin-1\r\ns = 'caf\xe9'\r\n\f" + TAG + "\r\n").encode("latin-1")
        view, comments = comment_lines(source, "example.py")
        self.assertEqual(comments, {1, 3})
        self.assertEqual(view.decode().split("\n")[2], " " + TAG)
        self.assertEqual(view.count(b"\n"), 3)

    def test_recovery_rejects_changed_string_contents_but_accepts_comment_changes(self):
        for newline in ("\n", "\r\n"):
            before = ('example = """\n' + TAG + '\n"""\n').replace("\n", newline).encode()
            after = before.replace(b"~1", b"~2")
            self.assertFalse(annotation_changes_only("example.py", before, after))
            self.assertTrue(annotation_changes_only("example.py", before, before + TAG.encode()))
            self.assertTrue(annotation_changes_only("example.py", (TAG + newline).encode(), b""))
        self.assertFalse(annotation_changes_only("example.py", b"x = 1\n", b"x = 2\n"))

    def test_unterminated_string_cannot_hide_annotations(self):
        with self.assertRaisesRegex(CheckError, "Cannot tokenize Python annotations"):
            comment_lines(b'example = """\n' + TAG.encode(), "broken.py")
        self.assertFalse(annotation_changes_only("broken.py", b'"""\n', b'"""\n' + TAG.encode()))


class PythonImportTests(WorkflowFixture):
    def test_real_oft_ignores_examples_retains_comments_and_source_bytes(self):
        path = self.repo / "session.py"
        content = EXAMPLES + path.read_text()
        path.write_text(content)
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        result = self.run_check()
        self.assertEqual(result["status"], "passed", result)
        items = import_items(self.out / "candidate-items.xml", self.repo)
        impl = [item for item in items if item["type"] == "impl"]
        self.assertEqual(len(impl), 1)
        self.assertEqual(impl[0]["path"], "session.py")
        self.assertEqual(impl[0]["line"], content.splitlines().index(TAG) + 1)
        self.assertEqual(path.read_text(), content)
        self.assertEqual(
            (self.out / "base-items.xml").read_bytes(),
            (self.out / "candidate-items.xml").read_bytes(),
        )

    def test_comment_link_to_missing_requirement_still_fails(self):
        with (self.repo / "session.py").open("a") as handle:
            handle.write("\n# [impl->req~actually-missing~1]\n")
        result = self.run_check()
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["oft"]["version"], "4.9.0")
