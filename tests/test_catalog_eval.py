"""Synthetic catalog comparison is offline unless live mode is explicit."""

from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("evaluate_catalog_script", ROOT / "scripts" / "evaluate_catalog.py")
catalog_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog_eval)


class CatalogEvalTests(unittest.TestCase):
    def test_public_fixture_size_labels_and_context_gate(self):
        fixture = catalog_eval.fixtures()
        candidates, cases = fixture["candidates"], fixture["cases"]
        self.assertEqual(len(candidates), 30)
        self.assertEqual(len(cases), 33)
        self.assertEqual(len({item["id"] for item in candidates}), 30)
        self.assertEqual(len({item["id"] for item in cases}), 33)
        self.assertEqual({item["kind"] for item in cases},
                         {"direct", "ambiguous", "negative", "contextual_follow_up"})
        self.assertEqual(sum(item["kind"] == "contextual_follow_up" for item in cases), 3)
        self.assertTrue(all(item["expected"] is None or item["expected"] == "none" or
                            item["expected"] in {entry["id"] for entry in candidates} for item in cases))
        self.assertTrue(all("path" not in entry and "body" not in entry for entry in candidates))

    def test_baseline_is_deterministic_and_not_perfect(self):
        fixture = catalog_eval.fixtures()
        one = catalog_eval.evaluate(fixture)
        two = catalog_eval.evaluate(fixture)
        self.assertEqual(one["summary"]["baseline_gated"], two["summary"]["baseline_gated"])
        self.assertLess(one["summary"]["baseline_raw"]["matches"], one["summary"]["eligible"])
        self.assertEqual(one["summary"]["jev_raw"], None)
        self.assertEqual(one["summary"]["jev_gated"], None)
        self.assertEqual(one["summary"]["contextual_bypasses"], 3)
        for row in one["cases"]:
            if row["kind"] == "contextual_follow_up":
                self.assertIsNone(row["baseline_gated"])

    def test_default_offline_never_constructs_client_or_writes_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            output = io.StringIO()
            with patch.object(catalog_eval, "Client", side_effect=AssertionError("client")), \
                 patch.object(catalog_eval, "select", side_effect=AssertionError("network")), \
                 redirect_stdout(output):
                self.assertEqual(catalog_eval.main([]), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["mode"], "offline_synthetic")
            self.assertFalse(report["network"])
            self.assertFalse(path.exists())
            with patch.object(catalog_eval, "Client", side_effect=AssertionError("client")), redirect_stdout(io.StringIO()):
                self.assertEqual(catalog_eval.main(["--output", str(path)]), 0)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["summary"]["cases"], 33)

    def test_live_requires_output_before_client_creation(self):
        with patch.object(catalog_eval, "Client", side_effect=AssertionError("client")), \
             patch("sys.stderr", new=io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                catalog_eval.main(["--live"])
        self.assertEqual(caught.exception.code, 2)

    def test_existing_report_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text("keep", encoding="utf-8")
            with patch("sys.stderr", new=io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    catalog_eval.main(["--output", str(path)])
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(path.read_text(encoding="utf-8"), "keep")

    def test_mock_live_keeps_raw_gated_failure_and_accounting_separate(self):
        fixture = catalog_eval.fixtures()
        labels = {item["request"]: item["expected"] for item in fixture["cases"]}
        calls = []
        def fake_select(workflow, data, client, *, timeout):
            self.assertEqual(workflow, "skill")
            self.assertEqual(timeout, 0.5)
            self.assertEqual(len(data["candidates"]), 30)
            request = data["request"]
            calls.append(request)
            self.assertNotIn("Use the second one.", calls)
            expected = labels[request]
            if request == fixture["cases"][0]["request"]:
                return {"route": "fallback", "selected": None, "reason": "deadline_exceeded",
                        "calls": 1, "completed_calls": 0, "unaccounted_calls": 1,
                        "usage": {"input_tokens": 0, "output_tokens": 0},
                        "estimated_known_cost_usd": None, "cost_complete": False}
            return {"route": "fallback" if expected == "none" else "recommendation",
                    "selected": None if expected == "none" else expected,
                    "reason": "none_selected" if expected == "none" else None,
                    "calls": 1, "completed_calls": 1, "unaccounted_calls": 0,
                    "usage": {"input_tokens": 10, "output_tokens": 2},
                    "estimated_known_cost_usd": 0.000001, "cost_complete": True}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            with patch.object(catalog_eval, "Client", return_value=object()), \
                 patch.object(catalog_eval, "select", side_effect=fake_select), \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(catalog_eval.main(["--live", "--output", str(path), "--timeout", "0.5"]), 0)
            report = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(calls), 30)
        self.assertEqual(report["summary"]["jev_accounting"]["calls"], 30)
        self.assertEqual(report["summary"]["jev_accounting"]["unaccounted_calls"], 1)
        self.assertEqual(report["summary"]["jev_accounting"]["failed_cases"], ["direct-01"])
        self.assertIsNone(report["summary"]["jev_accounting"]["known_cost_usd"])
        self.assertEqual(report["summary"]["jev_raw"]["total"], 30)
        self.assertEqual(report["summary"]["jev_gated"]["total"], 33)
        self.assertEqual(report["summary"]["jev_gated"]["matches"], 32)
        self.assertTrue(all(row["jev_result"] is None for row in report["cases"] if row["kind"] == "contextual_follow_up"))


if __name__ == "__main__":
    unittest.main()
