"""Offline native-host and Jev skill-picker comparison tests."""

from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
import math
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from jev_skills.catalog import catalog

SCRIPT = ROOT / "scripts" / "compare_skill_picker.py"
spec = importlib.util.spec_from_file_location("compare_skill_picker_script", SCRIPT)
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class SkillPickerComparisonTests(unittest.TestCase):
    def setUp(self):
        self.fixture = comparison.load_fixture()
        self.digest = comparison._canonical_digest(self.fixture)
        self.case_ids = {case["id"] for case in self.fixture["cases"]}
        self.choices = {item["id"] for item in self.fixture["candidates"]} | {"none", "followup"}

    def provenance(self, system):
        return {
            "system": system,
            "host": "Codex CLI" if system == "native_host" else "jev-skills CLI",
            "model": "gpt-test" if system == "native_host" else "jev-1.13.0",
            "reported_model": None if system == "native_host" else "jev-1.13.0",
            "version": "1.2.3",
            "source": "Manually captured public fixture run",
            "captured_at_utc": "2026-10-02T08:00:00+00:00",
            "fresh_session_per_task": True,
            "benchmark_sha256": self.digest,
        }

    def write_capture(self, directory, name, system, results):
        path = Path(directory) / name
        path.write_text(json.dumps({"schema_version": 1,
                                    "provenance": self.provenance(system),
                                    "results": results}), encoding="utf-8")
        return path

    def test_fixture_is_public_authored_and_covers_required_cases(self):
        self.assertIn("Project-authored public fixture", self.fixture["benchmark"]["source"])
        self.assertIn("not real users", self.fixture["benchmark"]["authorship"])
        self.assertIn("not downstream task success", self.fixture["benchmark"]["limitations"])
        self.assertTrue(any(len(case["acceptable"]) > 1 for case in self.fixture["cases"]))
        self.assertTrue({"overlap", "negative", "followup"}.issubset(
            {case["kind"] for case in self.fixture["cases"]}))
        requests = " ".join(case["request"] for case in self.fixture["cases"])
        self.assertRegex(requests, "[А-Яа-я]")

    def test_prepare_is_unlabelled_exclusive_and_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            with patch.object(socket, "create_connection", side_effect=AssertionError("network")), \
                 patch.object(subprocess, "Popen", side_effect=AssertionError("process")), \
                 patch.object(subprocess, "run", side_effect=AssertionError("process")):
                manifest = comparison.prepare(self.fixture, output)
            self.assertFalse(manifest["labels_included"])
            self.assertEqual(manifest["host_method"], "ordinary_host_prompted_choice")
            self.assertEqual(manifest["measurement"]["status"], "unmeasured")
            self.assertEqual(manifest["measurement"]["measured_results"], 0)
            self.assertNotIn("acceptable", json.dumps(manifest))
            self.assertNotIn("\"kind\"", json.dumps(manifest))
            self.assertEqual(len(manifest["tasks"]), len(self.fixture["cases"]))
            first = manifest["tasks"][0]
            native_prompt = (output / first["native_prompt"]).read_text(encoding="utf-8")
            jev_input = json.loads((output / first["jev_input"]).read_text(encoding="utf-8"))
            source_case = self.fixture["cases"][0]
            self.assertIn(source_case["request"], native_prompt)
            self.assertEqual(jev_input["request"], source_case["request"])
            self.assertEqual(jev_input["candidates"], manifest["candidates"])
            self.assertTrue((output / "catalog" / self.fixture["candidates"][0]["id"] / "SKILL.md").is_file())
            with self.assertRaisesRegex(ValueError, "output_exists"):
                comparison.prepare(self.fixture, output)

    def test_generated_catalog_quotes_yaml_sensitive_descriptions(self):
        fixture = deepcopy(self.fixture)
        fixture["candidates"][0]["description"] = "[Schema]: validates quoted input"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            comparison.prepare(fixture, output)
            inventory = catalog([output / "catalog"])
        selected = next(item for item in inventory["candidates"] if item["id"] == "python-testing")
        self.assertEqual(selected["description"], "[Schema]: validates quoted input")

    def test_partial_results_are_unmeasured_and_failures_are_retained(self):
        native_results = [
            {"id": "task-01", "choice": "python-testing",
             "elapsed_ms": 100, "usage": {"input_tokens": 20, "output_tokens": 2}},
            {"id": "task-06", "choice": "none", "elapsed_ms": 40},
            {"id": "task-08", "failure": {"reason": "host_timeout", "detail": "No answer"}},
        ]
        jev_results = [
            {"id": "task-01", "raw_result": {
                "route": "recommendation", "selected": "tdd-workflow", "elapsed_ms": 12,
                "usage": {"input_tokens": 9, "output_tokens": 1}}},
            {"id": "task-06", "raw_result": {
                "route": "fallback", "selected": None, "reason": "none_selected", "elapsed_ms": 8,
                "usage": {"input_tokens": 8, "output_tokens": 1}}},
            {"id": "task-08", "raw_result": {
                "route": "fallback", "selected": None, "reason": "contextual_follow_up"}},
            {"id": "task-09", "raw_result": {
                "route": "fallback", "selected": None, "reason": "deadline_exceeded",
                "elapsed_ms": 300}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            native_path = self.write_capture(directory, "native.json", "native_host", native_results)
            jev_path = self.write_capture(directory, "jev.json", "jev", jev_results)
            native = comparison.load_capture(native_path, "native_host", self.digest,
                                               self.case_ids, self.choices)
            jev = comparison.load_capture(jev_path, "jev", self.digest, self.case_ids, self.choices)
            report = comparison.compare(self.fixture, native, jev)

        native_summary = report["summary"]["native"]
        self.assertEqual(native_summary["measured_choices"], 2)
        self.assertEqual(native_summary["matches"], 2)
        self.assertEqual(native_summary["choice_accuracy"], 1.0)
        self.assertEqual(native_summary["outcome_success_rate"], 0.6667)
        self.assertEqual(native_summary["failures"], 1)
        self.assertEqual(native_summary["unmeasured"], len(self.fixture["cases"]) - 3)
        self.assertEqual(native_summary["token_usage"]["input_tokens"], {"reported": 1, "total": 20})
        self.assertEqual(native_summary["token_usage"]["cached_input_tokens"], {"reported": 0, "total": None})
        self.assertEqual(report["summary"]["jev"]["fallback_coverage"]["matches"], 2)
        self.assertEqual(report["summary"]["paired"]["both_supplied"], 3)
        self.assertEqual(report["summary"]["paired"]["with_failure"], 1)
        followup = next(row for row in report["cases"] if row["id"] == "task-09")
        self.assertEqual(followup["jev"]["status"], "failure")
        self.assertEqual(followup["jev"]["failure"]["reason"], "deadline_exceeded")
        absent = next(row for row in report["cases"] if row["id"] == "task-02")
        self.assertEqual(absent["native"], {"status": "unmeasured"})

    def test_invalid_provenance_duplicate_missing_and_nonfinite_results_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            bad_provenance = self.provenance("native_host")
            bad_provenance["fresh_session_per_task"] = False
            path = Path(directory) / "bad-provenance.json"
            path.write_text(json.dumps({"schema_version": 1, "provenance": bad_provenance,
                                        "results": []}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fresh_sessions_not_confirmed"):
                comparison.load_capture(path, "native_host", self.digest, self.case_ids, self.choices)

            duplicate = [{"id": "task-06", "choice": "none"},
                         {"id": "task-06", "choice": "none"}]
            path = self.write_capture(directory, "duplicate.json", "native_host", duplicate)
            with self.assertRaisesRegex(ValueError, "duplicate_result_id"):
                comparison.load_capture(path, "native_host", self.digest, self.case_ids, self.choices)

            missing = Path(directory) / "missing.json"
            missing.write_text(json.dumps({"schema_version": 1,
                                           "provenance": self.provenance("native_host")}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing_results"):
                comparison.load_capture(missing, "native_host", self.digest, self.case_ids, self.choices)

            invalid_number = [{"id": "task-06", "choice": "none", "elapsed_ms": math.inf}]
            path = self.write_capture(directory, "infinite.json", "native_host", invalid_number)
            with self.assertRaisesRegex(ValueError, "invalid_json_number"):
                comparison.load_capture(path, "native_host", self.digest, self.case_ids, self.choices)

            negative_number = [{"id": "task-06", "choice": "none", "elapsed_ms": -1}]
            path = self.write_capture(directory, "negative.json", "native_host", negative_number)
            with self.assertRaisesRegex(ValueError, "invalid_elapsed_ms"):
                comparison.load_capture(path, "native_host", self.digest, self.case_ids, self.choices)

            null_choice = [{"id": "task-06", "raw_result": {"choice": None}}]
            path = self.write_capture(directory, "null-choice.json", "native_host", null_choice)
            with self.assertRaisesRegex(ValueError, "invalid_result_choice"):
                comparison.load_capture(path, "native_host", self.digest, self.case_ids, self.choices)

    def test_invalid_fixture_missing_cases_and_unsafe_ids_fail(self):
        fixture = deepcopy(self.fixture)
        del fixture["cases"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid_cases"):
                comparison.load_fixture(path)
            fixture = deepcopy(self.fixture)
            fixture["cases"][0]["id"] = "../escape"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid_case_id"):
                comparison.load_fixture(path)

    def test_compare_cli_reports_empty_captures_unmeasured_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            native_path = self.write_capture(directory, "native.json", "native_host", [])
            jev_path = self.write_capture(directory, "jev.json", "jev", [])
            output = Path(directory) / "report.json"
            with patch.object(socket, "create_connection", side_effect=AssertionError("network")), \
                 patch.object(subprocess, "Popen", side_effect=AssertionError("process")), \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(comparison.main([
                    "compare", "--native-results", str(native_path),
                    "--jev-results", str(jev_path), "--output", str(output)]), 0)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertIsNone(report["summary"]["native"]["choice_accuracy"])
            self.assertIsNone(report["summary"]["native"]["outcome_success_rate"])
            self.assertIsNone(report["summary"]["native"]["fallback_coverage"]["coverage"])
            self.assertEqual(report["summary"]["native"]["unmeasured"], len(self.fixture["cases"]))
            self.assertIsNone(report["summary"]["native"]["elapsed_ms"]["total"])
            self.assertIsNone(report["summary"]["native"]["token_usage"]["input_tokens"]["total"])
            with patch("sys.stderr", new=io.StringIO()), redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    comparison.main(["compare", "--native-results", str(native_path),
                                     "--jev-results", str(jev_path), "--output", str(output)])
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), report)


if __name__ == "__main__":
    unittest.main()
