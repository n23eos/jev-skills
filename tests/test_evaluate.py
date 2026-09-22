"""Evaluation harness must remain offline unless --live is explicit."""

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
spec = importlib.util.spec_from_file_location("evaluate_script", ROOT / "scripts" / "evaluate.py")
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)


class HarnessTests(unittest.TestCase):
    def test_synthetic_labels_cover_workflows_and_bypasses(self):
        cases = evaluate.fixtures()
        self.assertEqual(len(cases), 25)
        self.assertEqual(len({case["id"] for case in cases}), 25)
        self.assertEqual({case["workflow"] for case in cases}, {"model", "skill", "context", "tests", "bug", "plan"})
        self.assertEqual(sum(case["expected"] == "none" for case in cases), 3)
        self.assertEqual(sum("bypass" in case for case in cases), 3)
        self.assertEqual(sum(case.get("bypass") == "contextual_follow_up" for case in cases), 2)
        self.assertTrue(all(case["expected"] is None or case["expected"] == "none" or
                            case["expected"] in {entry["id"] for entry in case["input"]["candidates"]}
                            for case in cases))

    def test_default_has_no_client_and_does_not_write_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            stream = io.StringIO()
            with patch.object(evaluate, "Client", side_effect=AssertionError("live call")), redirect_stdout(stream):
                self.assertEqual(evaluate.main(["--output", str(output)]), 0)
            self.assertFalse(output.exists())
            preview = json.loads(stream.getvalue())
            self.assertEqual(preview["mode"], "offline")
            self.assertEqual(len(preview["cases"]), 25)

    def test_none_only_counts_as_match_for_explicit_none_selection(self):
        case = [case for case in evaluate.fixtures() if case["id"] == "skill-08"]
        with patch.object(evaluate, "select", return_value={"route": "fallback", "selected": None,
                                                                 "reason": "none_selected", "judgments": []}):
            self.assertTrue(evaluate.evaluate(case, 0.5)[0]["match"])
        with patch.object(evaluate, "select", return_value={"route": "fallback", "selected": None,
                                                                 "reason": "low_confidence", "judgments": []}):
            self.assertFalse(evaluate.evaluate(case, 0.5)[0]["match"])

    def test_live_report_marks_every_failed_selection_without_real_network(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "live.json"
            simulated = {"route": "fallback", "selected": None, "confidence": None,
                         "reason": "deadline_exceeded", "calls": 1, "completed_calls": 0,
                         "unaccounted_calls": 1, "usage": {"input_tokens": 0, "output_tokens": 0},
                         "elapsed_ms": 12, "estimated_known_cost_usd": None, "cost_complete": False}
            with patch.object(evaluate, "select", return_value=simulated) as selected, redirect_stdout(io.StringIO()):
                self.assertEqual(evaluate.main(["--live", "--output", str(output), "--timeout", "0.5", "--markdown"]), 0)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(selected.call_count, 22)
            self.assertEqual(report["summary"]["calls"], 22)
            self.assertEqual(report["summary"]["unaccounted_calls"], 22)
            self.assertEqual(len(report["summary"]["mismatches"]), 22)
            self.assertEqual(report["cases"][0]["result"]["reason"], "deadline_exceeded")
            self.assertEqual(report["cases"][0]["input"]["candidates"][0]["id"], "tier-tiny")
            self.assertEqual(report["model_version"], evaluate.MODEL)
            self.assertEqual(report["per_case_timeout_seconds"], 0.5)
            self.assertTrue(report["generated_at_utc"].endswith("+00:00"))
            self.assertTrue(output.with_suffix(".md").is_file())


if __name__ == "__main__":
    unittest.main()
