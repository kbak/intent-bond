"""Execution claims must come from exact, version-bound JUnit/OFT associations."""

import copy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from test_workflow import WorkflowFixture

from intentbond.common import CheckError, read_json, write_json
from intentbond.config import validate_scope
from intentbond.evidence import statement
from intentbond.execution import (
    collect_execution_links,
    explain_execution,
    required_execution_diagnostics,
)
from intentbond.explain import explain
from intentbond.runner import verify

REQ = "req~session-expiration~1"
TEST = "utest~expiration-boundary~1"
TEST_KEY = "utest~expiration-boundary"
OPTIONS = {"format": "junit-properties-v1", "artifact_types": ["utest"]}
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class ExecutionReportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ib-execution-report-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "tests.xml"
        self.scope = read_json(EXAMPLES / "session/scope.json")
        self.scope["tests"]["execution_links"] = copy.deepcopy(OPTIONS)
        self.items = [
            {"id": TEST, "type": "utest", "path": "tests/test_session.py"},
            {"id": REQ, "type": "req", "path": "requirements.md"},
        ]

    def parse(self, *cases):
        self.path.write_text('<testsuite name="session">' + "".join(cases) + "</testsuite>")
        return collect_execution_links(self.path, self.items, self.scope)

    def case(self, name="boundary", identifier=TEST, result="", attributes=""):
        prop = (
            f'<properties><property name="oft_id" value="{identifier}"/></properties>'
            if identifier is not None
            else ""
        )
        return f'<testcase classname="Session" name="{name}" {attributes}>{prop}{result}</testcase>'

    def test_parameterized_cases_preserve_individual_outcomes(self):
        links = self.parse(
            self.case("boundary[1799]"), self.case("boundary[1800]", result="<failure/>")
        )
        artifact = links["artifacts"][0]
        self.assertEqual(artifact["status"], "mixed")
        self.assertEqual([case["status"] for case in artifact["cases"]], ["passed", "failed"])

    def test_duplicate_identity_is_ambiguous_even_when_one_copy_has_no_link(self):
        links = self.parse(self.case(), self.case(identifier=None))
        self.assertEqual(links["artifacts"][0]["status"], "ambiguous")
        self.assertIn(
            "Duplicate testcase identity", links["artifacts"][0]["cases"][0]["diagnostics"]
        )

    def test_suite_identity_distinguishes_cases(self):
        self.path.write_text(
            '<testsuites><testsuite name="one">'
            + self.case()
            + '</testsuite><testsuite name="two">'
            + self.case()
            + "</testsuite></testsuites>"
        )
        links = collect_execution_links(self.path, self.items, self.scope)
        self.assertEqual(links["artifacts"][0]["status"], "passed")
        self.assertEqual(len(links["artifacts"][0]["cases"]), 2)

    def test_unknown_stale_requirement_and_out_of_scope_ids_are_invalid(self):
        self.items.append({"id": "utest~outside~1", "type": "utest", "path": "other.py"})
        for identifier in (
            "utest~invented~1",
            "utest~expiration-boundary~0",
            REQ,
            "utest~outside~1",
            "",
        ):
            with self.subTest(identifier=identifier):
                links = self.parse(self.case(identifier=identifier))
                self.assertEqual(links["status"], "invalid")
                self.assertEqual(links["artifacts"][0]["status"], "not_observed")

    def test_retry_extensions_and_conflicting_status_are_ambiguous(self):
        for result in (
            "<flakyFailure/>",
            "<rerunError/>",
            "<skipped/><failure/>",
            "<unknownExtension/>",
        ):
            with self.subTest(result=result):
                self.assertEqual(
                    self.parse(self.case(result=result))["artifacts"][0]["status"], "ambiguous"
                )
        self.assertEqual(
            self.parse(self.case(attributes='status="failed"'))["artifacts"][0]["status"],
            "ambiguous",
        )

    def test_skip_error_and_missing_metadata_are_distinct(self):
        for case, status in (
            (self.case(result="<skipped/>"), "skipped"),
            (self.case(result="<error/>"), "failed"),
            (self.case(attributes='status="notrun"'), "skipped"),
            (self.case(identifier=None), "not_observed"),
        ):
            with self.subTest(status=status):
                self.assertEqual(self.parse(case)["artifacts"][0]["status"], status)

    def test_multiple_explicit_links_and_duplicate_property_are_supported(self):
        other = "utest~another~1"
        self.items.append({"id": other, "type": "utest", "path": "tests/test_session.py"})
        properties = f'<properties><property name="oft_id" value="{TEST}"/><property name="oft_id" value="{other}"/></properties>'
        links = self.parse(self.case(result=properties))
        self.assertEqual(len(links["artifacts"]), 2)
        self.assertTrue(
            all(
                item["status"] == "passed" and len(item["cases"]) == 1
                for item in links["artifacts"]
            )
        )

    def test_incomplete_report_is_not_interpreted_as_execution_evidence(self):
        self.path.write_text('<testsuite tests="2">' + self.case() + "</testsuite>")
        with self.assertRaisesRegex(CheckError, "declared test count"):
            collect_execution_links(self.path, self.items, self.scope)

    def test_explain_traverses_existing_graph_without_reinterpreting_coverage(self):
        links = self.parse(self.case())
        graph = {
            REQ: {"covered_by": ["dsn~timeout~1"]},
            "dsn~timeout~1": {"covered_by": [TEST]},
            TEST: {"covered_by": []},
        }
        status, artifacts, _ = explain_execution(
            REQ, graph, links, {"source_status": "matched", "status": "passed", "exit_code": 0}
        )
        self.assertEqual(status, "passed")
        self.assertEqual([item["id"] for item in artifacts], [TEST])

    def test_configuration_is_explicit_and_only_available_with_junit(self):
        for options in (
            {},
            {"format": "other", "artifact_types": ["utest"]},
            {"format": "junit-properties-v1", "artifact_types": []},
            {"format": "junit-properties-v1", "artifact_types": ["utest", "utest"]},
            {"format": "junit-properties-v1", "artifact_types": [1]},
        ):
            with self.subTest(options=options), self.assertRaises(CheckError):
                scope = copy.deepcopy(self.scope)
                scope["tests"]["execution_links"] = options
                validate_scope(scope)
        scope = copy.deepcopy(self.scope)
        scope["tests"].update(format="command")
        del scope["tests"]["report"]
        with self.assertRaises(CheckError):
            validate_scope(scope)

    def test_required_artifact_configuration_uses_unique_selected_named_keys(self):
        for value in (
            [],
            False,
            TEST_KEY,
            [TEST_KEY, TEST_KEY],
            [TEST],
            ["req~session-expiration"],
            ["utest~"],
            [None],
            [{}],
        ):
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(CheckError, "required_artifacts"),
            ):
                scope = copy.deepcopy(self.scope)
                scope["tests"]["execution_links"]["required_artifacts"] = value
                validate_scope(scope)
        self.scope["tests"]["execution_links"]["required_artifacts"] = [TEST_KEY]
        self.assertEqual(validate_scope(self.scope), self.scope)

    def test_required_execution_rejects_nonpassing_observations(self):
        self.scope["tests"]["execution_links"]["required_artifacts"] = [TEST_KEY]
        for cases, status in (
            ([self.case(identifier=None)], "not_observed"),
            ([self.case(result="<skipped/>")], "skipped"),
            ([self.case(result="<failure/>")], "failed"),
            ([self.case(), self.case()], "ambiguous"),
            ([self.case(result="<flakyFailure/>")], "ambiguous"),
            ([self.case("one"), self.case("two", result="<skipped/>")], "mixed"),
        ):
            with self.subTest(status=status):
                problems = required_execution_diagnostics(self.parse(*cases), self.scope)
                self.assertEqual(len(problems), 1)
                self.assertIn(TEST, problems[0])
                self.assertIn(status, problems[0])
        self.assertEqual(required_execution_diagnostics(self.parse(self.case()), self.scope), [])

    def test_required_identity_follows_one_revision_but_rejects_missing_or_multiple(self):
        self.scope["tests"]["execution_links"]["required_artifacts"] = [TEST_KEY]
        revised = TEST_KEY + "~2"
        self.items[0]["id"] = revised
        self.assertEqual(
            required_execution_diagnostics(self.parse(self.case(identifier=revised)), self.scope),
            [],
        )
        self.items.append({"id": TEST, "type": "utest", "path": "tests/test_session.py"})
        problems = required_execution_diagnostics(
            self.parse(self.case("old"), self.case("new", identifier=revised)), self.scope
        )
        self.assertIn("found 2", problems[0])
        for path in ("other.py", "tests/test_session.py"):
            with self.subTest(path=path):
                self.items = [
                    {
                        "id": TEST if path == "other.py" else "utest~optional~1",
                        "type": "utest",
                        "path": path,
                    }
                ]
                problems = required_execution_diagnostics(
                    self.parse(self.case(identifier=None)), self.scope
                )
                self.assertIn("found 0", problems[0])

    def test_optional_artifacts_do_not_need_passing_observations(self):
        self.scope["tests"]["execution_links"]["required_artifacts"] = [TEST_KEY]
        self.items.append(
            {"id": "utest~optional~1", "type": "utest", "path": "tests/test_session.py"}
        )
        links = self.parse(self.case(), self.case("optional", "utest~optional~1", "<skipped/>"))
        self.assertEqual(required_execution_diagnostics(links, self.scope), [])


class ExecutionWorkflowTests(WorkflowFixture):
    def setUp(self):
        super().setUp()
        self.replace(
            "tests/test_session.py", "# [utest->" + REQ + "]", "# [" + TEST + "->" + REQ + "]"
        )
        path = self.repo / "tests/test_session.py"
        path.write_text(path.read_text() + f'\n    test_expiration_boundary.oft_id = "{TEST}"\n')
        self.replace(
            "run_tests.py",
            'self.case = ET.SubElement(suite_xml, "testcase", name=test.id())',
            'self.case = ET.SubElement(suite_xml, "testcase", name=test.id())\n        identifier = getattr(getattr(test, test._testMethodName), "oft_id", None)\n        if identifier:\n            properties = ET.SubElement(self.case, "properties")\n            ET.SubElement(properties, "property", name="oft_id", value=identifier)',
        )
        self.configure(lambda scope: scope["tests"].update(execution_links=copy.deepcopy(OPTIONS)))
        write_json(self.repo / "scope.json", read_json(self.scope))
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()

    def explained(self, identifier=REQ, snapshot="candidate"):
        return explain(identifier, self.out / "evidence.json", self.jar, snapshot)

    def verified(self):
        return verify(
            self.repo,
            self.scope,
            self.base,
            "worktree",
            self.out / "evidence.json",
            allow_pending_review=True,
        )

    def add_other_test(self):
        path = self.repo / "tests/test_session.py"
        path.write_text(
            path.read_text() + "\n    def test_other(self):\n        self.assertTrue(True)\n"
        )

    def test_checked_and_verified_execution_is_visible_in_text_and_json(self):
        self.assertEqual(self.run_check()["status"], "passed")
        self.assertEqual(self.verified()["status"], "matched")
        result = self.explained()
        self.assertEqual(result["linked_test_execution"], "passed")
        self.assertEqual(result["linked_tests"][0]["id"], TEST)
        self.assertEqual(self.explained(TEST)["linked_test_execution"], "passed")
        code, output, error = self.run_cli(
            "explain", REQ, "--evidence", str(self.out / "evidence.json")
        )
        self.assertEqual(code, 0, error)
        self.assertIn(TEST + ": passed", output)
        self.assertIn("test_expiration_boundary", output)
        self.assertEqual(
            self.explained(snapshot="base")["linked_test_execution"], "not_established"
        )

    def test_passing_suite_cannot_hide_a_missing_linked_test(self):
        self.replace("tests/test_session.py", "test_expiration_boundary", "omitted_boundary")
        self.add_other_test()
        result = self.run_check()
        self.assertEqual(result["tests"]["status"], "passed")
        self.assertEqual(self.explained()["linked_test_execution"], "not_observed")
        self.assertEqual(self.verified()["status"], "matched")

    def require_boundary(self):
        self.configure(
            lambda scope: scope["tests"]["execution_links"].update(required_artifacts=[TEST_KEY])
        )

    def test_required_execution_passes_and_tracks_revised_test(self):
        self.require_boundary()
        self.replace("tests/test_session.py", TEST, TEST_KEY + "~2")
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result["diagnostics"])
        self.assertEqual(self.verified()["status"], "matched")
        self.assertEqual(self.explained()["linked_tests"][0]["id"], TEST_KEY + "~2")

    def test_missing_required_execution_cannot_be_waived_by_candidate_scope(self):
        self.require_boundary()
        write_json(self.repo / "scope.json", read_json(self.scope))
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        self.replace("tests/test_session.py", "test_expiration_boundary", "omitted_boundary")
        self.add_other_test()
        candidate_scope = read_json(self.repo / "scope.json")
        del candidate_scope["tests"]["execution_links"]["required_artifacts"]
        write_json(self.repo / "scope.json", candidate_scope)
        result = self.run_check(scope_path=None)
        self.assertEqual(result["tests"]["status"], "passed")
        self.assertEqual(result["status"], "rejected")
        self.assert_problem(result, "got not_observed")

    def test_deleting_required_declaration_does_not_remove_execution_obligation(self):
        self.require_boundary()
        self.replace("tests/test_session.py", f"# [{TEST}->", "# [utest->")
        self.replace("tests/test_session.py", f'    test_expiration_boundary.oft_id = "{TEST}"', "")
        result = self.run_check()
        self.assertEqual(result["tests"]["status"], "passed")
        self.assertEqual(result["trace"]["candidate"]["status"], "passed")
        self.assertEqual(result["status"], "rejected")
        self.assert_problem(result, f"Required execution artifact {TEST_KEY}")

    def test_required_skip_rejects_even_when_suite_policy_allows_skips(self):
        self.require_boundary()
        self.replace(
            "tests/test_session.py",
            "    def test_expiration_boundary",
            '    @unittest.skip("not executed")\n    def test_expiration_boundary',
        )
        self.add_other_test()
        result = self.run_check()
        self.assertEqual(result["tests"]["status"], "passed")
        self.assertEqual(result["status"], "rejected")
        self.assert_problem(result, "got skipped")

    def test_verify_rechecks_required_execution_after_top_level_outcome_is_forged(self):
        self.require_boundary()
        self.replace("tests/test_session.py", "test_expiration_boundary", "omitted_boundary")
        self.add_other_test()
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        result = self.run_check()
        self.assertEqual(result["status"], "rejected")
        result.update(status="passed", diagnostics=[])
        write_json(self.out / "evidence.json", statement(result))
        with self.assertRaisesRegex(CheckError, "Retained evidence fails required execution"):
            self.verified()

    def test_skipped_linked_test_is_visible_when_suite_passes(self):
        self.replace(
            "tests/test_session.py",
            "    def test_expiration_boundary",
            '    @unittest.skip("not executed")\n    def test_expiration_boundary',
        )
        self.add_other_test()
        self.assertEqual(self.run_check()["tests"]["status"], "passed")
        self.assertEqual(self.explained()["linked_test_execution"], "skipped")

    def test_failed_linked_test_is_visible(self):
        self.replace("session.py", "30 * 60", "60 * 60")
        self.assertEqual(self.run_check()["status"], "rejected")
        self.assertEqual(self.explained()["linked_test_execution"], "failed")

    def test_wrong_revision_rejects_metadata_even_when_test_passed(self):
        self.replace(
            "tests/test_session.py", f'oft_id = "{TEST}"', 'oft_id = "utest~expiration-boundary~0"'
        )
        result = self.run_check()
        self.assertEqual(result["tests"]["status"], "passed")
        self.assert_problem(result, "Invalid OFT execution reference")
        self.assertEqual(self.explained()["linked_test_execution"], "not_established")

    def test_verify_rejects_invalid_links_after_top_level_outcome_is_forged(self):
        self.replace(
            "tests/test_session.py", f'oft_id = "{TEST}"', 'oft_id = "utest~expiration-boundary~0"'
        )
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        result = self.run_check()
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["tests"]["status"], "passed")
        self.assertEqual(result["tests"]["execution_links"]["status"], "invalid")
        result.update(status="passed", diagnostics=[])
        write_json(self.out / "evidence.json", statement(result))

        with self.assertRaisesRegex(CheckError, "invalid execution links"):
            self.verified()
        explanation = self.explained()
        self.assertEqual(explanation["linked_test_execution"], "not_established")
        self.assertIn(
            "utest~expiration-boundary~0", " ".join(explanation["execution_link_diagnostics"])
        )

    def test_timeout_after_mixed_report_cannot_establish_a_linked_pass(self):
        self.add_other_test()
        self.replace("tests/test_session.py", "self.assertTrue(True)", "self.assertTrue(False)")
        self.replace("run_tests.py", "sys.exit(", "import time\ntime.sleep(10)\nsys.exit(")
        self.configure(lambda scope: scope["tests"].update(timeout_seconds=1))
        result = self.run_check()
        tests = result["tests"]
        self.assertIsNone(tests["exit_code"])
        self.assertEqual(tests["source_status"], "matched")
        self.assertEqual(tests["counts"]["passed"], 1)
        self.assertEqual(tests["counts"]["failed"], 1)
        self.assertEqual(tests["execution_links"]["artifacts"][0]["status"], "passed")
        explanation = self.explained()
        self.assertEqual(explanation["linked_test_execution"], "not_established")
        self.assertIn("completed test command", " ".join(explanation["execution_link_diagnostics"]))

    def test_readers_reject_edited_or_removed_associations(self):
        self.replace("tests/test_session.py", "test_expiration_boundary", "omitted_boundary")
        self.add_other_test()
        result = self.run_check()
        for remove in (False, True):
            with self.subTest(remove=remove):
                edited = copy.deepcopy(result)
                if remove:
                    del edited["tests"]["execution_links"]
                else:
                    edited["tests"]["execution_links"]["artifacts"][0]["status"] = "passed"
                write_json(self.out / "evidence.json", statement(edited))
                with self.assertRaisesRegex(CheckError, "Execution links do not match"):
                    self.verified()
                with self.assertRaisesRegex(CheckError, "Execution links do not match"):
                    self.explained()

    def test_source_mutation_keeps_reported_outcome_diagnostic(self):
        self.replace(
            "run_tests.py",
            "suite_xml = ET.Element",
            'open("session.py", "a").write("# mutation\\n")\nsuite_xml = ET.Element',
        )
        result = self.run_check()
        self.assertEqual(result["tests"]["execution_links"]["artifacts"][0]["status"], "passed")
        self.assertEqual(result["tests"]["source_status"], "changed")
        self.assertEqual(self.explained()["linked_test_execution"], "not_established")

    def test_opt_out_preserves_existing_behavior_even_with_report_properties(self):
        self.configure(lambda scope: scope["tests"].pop("execution_links"))
        self.assertNotIn("execution_links", self.run_check()["tests"])
        self.assertEqual(self.verified()["status"], "matched")
        self.assertEqual(self.explained()["linked_test_execution"], "not_established")


class PytestExecutionTests(WorkflowFixture):
    def setUp(self):
        super().setUp()
        shutil.rmtree(self.repo)
        shutil.copytree(EXAMPLES / "pytest-session", self.repo)
        self.git("init", "-q", "-b", "main")
        scope = read_json(self.repo / "scope.json")
        scope["tests"]["command"][0] = sys.executable
        write_json(self.repo / "scope.json", scope)
        write_json(self.scope, scope)
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()

    def test_real_pytest_parameterized_report_is_linked(self):
        result = self.run_check()
        self.assertEqual(result["status"], "passed", result["diagnostics"])
        artifact = result["tests"]["execution_links"]["artifacts"][0]
        self.assertEqual(artifact["status"], "passed")
        self.assertEqual(len(artifact["cases"]), 3)
        self.assertEqual(result["tests"]["execution_links"]["unlinked_cases"], 1)
        self.assertEqual(
            verify(self.repo, self.scope, self.base, "worktree", self.out / "evidence.json")[
                "status"
            ],
            "matched",
        )

    def test_real_pytest_deselection_does_not_inherit_suite_pass(self):
        self.configure(lambda scope: scope["tests"]["command"].extend(["-k", "test_smoke"]))
        result = self.run_check()
        self.assertEqual(result["tests"]["status"], "passed", result["diagnostics"])
        self.assertEqual(
            result["tests"]["execution_links"]["artifacts"][0]["status"], "not_observed"
        )

    def test_required_real_pytest_deselection_is_rejected(self):
        self.configure(
            lambda scope: scope["tests"]["execution_links"].update(required_artifacts=[TEST_KEY])
        )
        self.configure(lambda scope: scope["tests"]["command"].extend(["-k", "test_smoke"]))
        result = self.run_check()
        self.assertEqual(result["tests"]["status"], "passed")
        self.assertEqual(result["status"], "rejected")
        self.assert_problem(result, "got not_observed")

    def test_real_pytest_skip_preserves_collection_metadata(self):
        self.replace(
            "tests/test_session.py",
            "@pytest.mark.oft_id",
            '@pytest.mark.skip(reason="not executed")\n@pytest.mark.oft_id',
        )
        result = self.run_check()
        self.assertEqual(result["tests"]["status"], "passed", result["diagnostics"])
        self.assertEqual(result["tests"]["execution_links"]["artifacts"][0]["status"], "skipped")

    def test_real_pytest_expected_failure_does_not_become_a_passing_observation(self):
        self.replace(
            "tests/test_session.py",
            "@pytest.mark.oft_id",
            '@pytest.mark.xfail(reason="known failure")\n@pytest.mark.oft_id',
        )
        self.replace("tests/test_session.py", "assert expired(seconds) is expected", "assert False")
        result = self.run_check()
        self.assertEqual(result["tests"]["status"], "passed", result["diagnostics"])
        self.assertEqual(result["tests"]["execution_links"]["artifacts"][0]["status"], "skipped")
        self.assertEqual(
            result["tests"]["execution_links"]["artifacts"][0]["cases"][0]["details"][0]["type"],
            "pytest.xfail",
        )

    def test_real_pytest_setup_error_keeps_the_artifact_association(self):
        self.replace(
            "tests/test_session.py",
            "def test_expiration_boundary(seconds, expected):",
            "def test_expiration_boundary(seconds, expected, missing_fixture):",
        )
        result = self.run_check()
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["tests"]["execution_links"]["artifacts"][0]["status"], "failed")
