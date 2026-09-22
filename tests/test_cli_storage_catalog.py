"""Offline CLI, persistence, inventory, and installation regressions."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_skills import cli
from jev_skills.catalog import catalog, install
from jev_skills.core import Client, DecisionError, QUESTIONS
from jev_skills.storage import record, status, toggle


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = patch.dict(os.environ, {"JEV_SKILLS_HOME": str(self.root)})
        self.home.start()
        self.addCleanup(self.home.stop)

    def run_cli(self, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            code = cli.main(list(args))
        return code, json.loads(output.getvalue())

    def test_private_and_followup_do_not_read_input_or_call_network(self):
        for flag, reason in (("--private", "private"), ("--follow-up", "contextual_follow_up")):
            with self.subTest(flag=flag), patch.object(Path, "read_text", side_effect=AssertionError("read")), \
                    patch("jev_skills.core.curl_transport", side_effect=AssertionError("network")), \
                    patch.object(cli, "Client", side_effect=AssertionError("client")):
                code, value = self.run_cli("decide", "skill", "--input", "missing.json", "--live", flag)
            self.assertEqual(code, 0)
            self.assertEqual(value, {"route": "fallback", "selected": None, "confidence": None, "reason": reason})

    def test_off_by_default_and_malformed_settings_do_not_read_input(self):
        original_read = Path.read_text
        reads = []
        def checked_read(path, *args, **kwargs):
            reads.append(path)
            if path.name == "missing.json":
                raise AssertionError("input must not be read")
            return original_read(path, *args, **kwargs)
        for settings in (None, '{"enabled":{"model":"yes"}}', "broken-json"):
            with self.subTest(settings=settings):
                if settings is not None:
                    (self.root / "settings.json").write_text(settings, encoding="utf-8")
                with patch.object(Path, "read_text", checked_read), \
                        patch.object(cli, "Client", side_effect=AssertionError("client")):
                    code, value = self.run_cli("decide", "model", "--input", "missing.json", "--automatic")
                self.assertEqual((code, value["reason"]), (0, "disabled"))
                self.assertFalse(any(path.name == "missing.json" for path in reads))

    def test_default_dry_run_has_no_network_and_reads_supplied_input(self):
        source = self.root / "sample.json"
        source.write_text(json.dumps({"request": "Synthetic", "candidates": [{"id": "one", "description": "First"}]}), encoding="utf-8")
        with patch.object(cli, "Client", side_effect=AssertionError("client")):
            code, value = self.run_cli("decide", "model", "--input", str(source))
        self.assertEqual(code, 0)
        self.assertEqual(value["mode"], "dry_run")
        self.assertFalse(value["network"])
        self.assertFalse((self.root / "usage.jsonl").exists())

    def test_dry_run_uses_custom_batch_size(self):
        source = self.root / "sample.json"
        source.write_text(json.dumps({"request": "Synthetic", "candidates": [
            {"id": f"item-{index}", "description": "Synthetic option"} for index in range(5)]}), encoding="utf-8")
        with patch.object(cli, "Client", side_effect=AssertionError("client")):
            code, value = self.run_cli("decide", "skill", "--input", str(source), "--batch-size", "2")
        self.assertEqual(code, 0)
        self.assertEqual(value["mode"], "dry_run")
        self.assertEqual([len(item["questions"]["selection"]["criteria"]) for item in value["requests"]], [3, 3, 2])

    def test_huge_threshold_falls_back_without_traceback(self):
        source = self.root / "sample.json"
        source.write_text(json.dumps({"request": "Synthetic", "candidates": [
            {"id": "one", "description": "First"}]}), encoding="utf-8")
        with patch.object(cli, "Client", side_effect=AssertionError("client")):
            code, value = self.run_cli("decide", "model", "--input", str(source), "--threshold", "1e309")
        self.assertEqual(code, 0)
        self.assertEqual(value["route"], "fallback")
        self.assertEqual(value["reason"], "numeric_value_out_of_range")

    def test_invalid_input_error_does_not_expose_contents(self):
        source = self.root / "sample.json"
        source.write_text('{"secret":"TOKEN_DO_NOT_LOG"}', encoding="utf-8")
        code, value = self.run_cli("decide", "model", "--input", str(source))
        self.assertEqual(code, 0)
        self.assertEqual(value["reason"], "request_must_be_nonempty_text")
        self.assertNotIn("TOKEN_DO_NOT_LOG", json.dumps(value))


class StatusTests(unittest.TestCase):
    def test_status_counts_only_safe_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertFalse(any(status(root)["enabled"].values()))
            toggle(root, "model", True)
            self.assertTrue(status(root)["enabled"]["model"])
            self.assertTrue(record(root, {"workflow": "model", "route": "recommendation", "selected": "private-id",
                    "model_size": "tiny",
                    "calls": 3, "completed_calls": 2, "unaccounted_calls": 1,
                    "usage": {"input_tokens": 42, "output_tokens": 6}, "elapsed_ms": 12,
                    "estimated_known_cost_usd": 0.000001764, "cost_complete": False}))
            self.assertNotIn("private-id", (root / "usage.jsonl").read_text(encoding="utf-8"))
            summary = status(root)
            self.assertEqual((summary["calls"], summary["input_tokens"], summary["output_tokens"], summary["unaccounted_calls"]), (3, 42, 6, 1))
            self.assertEqual(summary["recommendations_by_workflow"]["model"], 1)
            self.assertEqual(summary["recommendations_by_model_size"]["tiny"], 1)
            self.assertFalse(summary["cost_complete"])
            self.assertEqual(sum(summary["recommendations_by_workflow"].values()), 1)

    def test_corrupt_or_non_boolean_config_remains_off(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for contents in ('{"enabled":{"bug":1}}', '{invalid'):
                (root / "settings.json").write_text(contents, encoding="utf-8")
                self.assertFalse(any(status(root)["enabled"].values()))

    def test_malformed_or_huge_status_numbers_never_emit_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            huge = 10 ** 1000
            records = [
                {"workflow": "model", "route": "fallback", "calls": True,
                 "unaccounted_calls": -1, "usage": {"input_tokens": -4, "output_tokens": 1.5},
                 "estimated_known_cost_usd": "not a number", "cost_complete": True},
                {"workflow": "model", "route": "fallback", "calls": 0,
                 "usage": {"input_tokens": 0, "output_tokens": 0},
                 "estimated_known_cost_usd": huge, "cost_complete": True},
            ]
            text = "\n".join(json.dumps(item) for item in records) + '\n'
            text += '{"workflow":"model","estimated_known_cost_usd":1e1000,"cost_complete":true}\n'
            (root / "usage.jsonl").write_text(text, encoding="utf-8")
            summary = status(root)
            json.dumps(summary, allow_nan=False)
            self.assertEqual(summary["calls"], 0)
            self.assertEqual(summary["unaccounted_calls"], 0)
            self.assertEqual(summary["input_tokens"], 0)
            self.assertEqual(summary["output_tokens"], 0)
            self.assertEqual(summary["estimated_known_cost_usd"], 0.0)
            self.assertFalse(summary["cost_complete"])

    def test_finite_cost_records_cannot_overflow_aggregate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            event = {"workflow": "model", "route": "fallback", "calls": 1,
                     "usage": {"input_tokens": 0, "output_tokens": 0},
                     "estimated_known_cost_usd": 1e308, "cost_complete": True}
            (root / "usage.jsonl").write_text(json.dumps(event) + "\n" + json.dumps(event) + "\n", encoding="utf-8")
            summary = status(root)
            json.dumps(summary, allow_nan=False)
            self.assertFalse(summary["cost_complete"])


class CatalogTests(unittest.TestCase):
    def test_full_multiline_description_and_deduplicated_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "first"
            skill.mkdir()
            (skill / "SKILL.md").write_text("---\nname: sample\ndescription: |\n  First line.\n  Second line remains here.\n---\nBody\n", encoding="utf-8")
            (root / "alias").symlink_to(skill, target_is_directory=True)
            result = catalog([root, root])
            self.assertEqual(len(result["candidates"]), 1)
            self.assertEqual(result["candidates"][0]["description"], "First line. Second line remains here.")
            self.assertEqual(result["skipped"], [])

    def test_install_seven_skills_both_agents_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            for agent in ("codex", "claude"):
                target = Path(directory) / agent / "skills"
                paths = install(agent, target)
                self.assertEqual(len(paths), 7)
                self.assertTrue(all((Path(path) / "SKILL.md").is_file() for path in paths))
                sentinel = Path(paths[0]) / "keep.txt"
                sentinel.write_text("preserve", encoding="utf-8")
                with self.assertRaises(DecisionError):
                    install(agent, target)
                self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve")
                self.assertEqual(len(list(target.iterdir())), 7)


if __name__ == "__main__":
    unittest.main()
