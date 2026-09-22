"""First-use CLI workflows exercised offline with typed provider responses."""

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
from jev_skills.core import Client, MODEL
from jev_skills.storage import toggle


class DirectCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state_dir = self.root / "state"
        environment = patch.dict(os.environ, {"JEV_SKILLS_HOME": str(self.state_dir), "JEV_SKILLS_CHILD": ""})
        environment.start()
        self.addCleanup(environment.stop)
        self.profile = self.root / "profile.json"
        self.profile.write_text(json.dumps({"agent": "claude", "models": [
            {"id": "test-fast", "size": "tiny", "description": "Short supplied text", "effort": "low"},
            {"id": "test-deep", "size": "hardest", "description": "Complex ambiguous reasoning"},
        ]}), encoding="utf-8")
        self.skills = self.root / "skills"
        for name in ("plain-text", "jev-skill-picker"):
            directory = self.skills / name
            directory.mkdir(parents=True)
            (directory / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: Summarize supplied text clearly\n---\n"
                "PRIVATE_SKILL_BODY_SENTINEL\n", encoding="utf-8")
        self.payloads = []

    def run_cli(self, *arguments):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = cli.main(list(arguments))
        self.assertEqual(exit_code, 0)
        return json.loads(output.getvalue())

    def client(self, choice=None, confidence=0.95):
        def transport(payload, timeout):
            self.payloads.append(payload)
            criteria = payload["questions"]["selection"]["criteria"]
            selected = choice or next(identifier for identifier in criteria if identifier != "none")
            return {"model": MODEL, "usage": {"input_tokens": 20, "output_tokens": 2},
                    "answers": {"selection": {"type": "choice", "choice": selected,
                        "confidence": confidence, "probabilities": {
                            identifier: (1.0 if identifier == selected else 0.0) for identifier in criteria}}}}
        return patch.object(cli, "Client", return_value=Client(transport))

    def model_args(self, *extra):
        return ("route-model", "--request", "Summarize the supplied public sentence",
                "--profile", str(self.profile), *extra)

    def skill_args(self, *extra):
        return ("pick-skill", "--request", "Summarize the supplied public sentence",
                "--root", str(self.skills), *extra)

    def test_route_dry_run_and_live_recommendation_do_not_execute(self):
        with patch.object(cli, "run_helper") as helper, patch.object(cli, "Client") as client:
            value = self.run_cli(*self.model_args("--execute"))
            self.assertEqual(value["mode"], "dry_run")
            self.assertFalse(value["network"])
            client.assert_not_called()
            helper.assert_not_called()
        with self.client("test-fast"), patch.object(cli, "run_helper") as helper:
            value = self.run_cli(*self.model_args("--live"))
            self.assertEqual(value["selected"], "test-fast")
            self.assertNotIn("helper", value)
            helper.assert_not_called()

    def test_explicit_execute_uses_exact_profile_handoff_and_keeps_costs_separate(self):
        helper_result = {"status": "completed", "requested_model": "test-fast",
                         "reported_model": "test-runtime", "answer": "Summary", "cost": {"usd": 0.5}}
        with self.client("test-fast"), patch.object(cli, "run_helper", return_value=helper_result) as helper:
            value = self.run_cli(*self.model_args("--live", "--execute", "--helper-timeout", "9"))
        helper.assert_called_once_with("claude", "test-fast", "Summarize the supplied public sentence",
                                       timeout=9.0, effort="low")
        self.assertEqual(value["helper"], helper_result)
        saved = (self.state_dir / "usage.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("test-runtime", saved)
        self.assertNotIn("Summary", saved)
        self.assertEqual(json.loads(saved)["usage"]["input_tokens"], 20)

    def test_none_and_low_confidence_never_execute(self):
        for choice, confidence, reason in (("none", 0.95, "none_selected"),
                                            ("test-fast", 0.3, "low_confidence")):
            with self.subTest(reason=reason), self.client(choice, confidence), \
                    patch.object(cli, "run_helper") as helper:
                value = self.run_cli(*self.model_args("--live", "--execute"))
                self.assertEqual(value["reason"], reason)
                helper.assert_not_called()

    def test_invalid_helper_timeout_prevents_paid_selection(self):
        with patch.object(cli, "Client") as client, patch.object(cli, "run_helper") as helper:
            value = self.run_cli(*self.model_args("--live", "--execute", "--helper-timeout", "nan"))
        self.assertEqual(value["route"], "fallback")
        client.assert_not_called()
        helper.assert_not_called()

    def test_pick_direct_flow_returns_local_path_but_transmits_no_path_or_body(self):
        with self.client():
            value = self.run_cli(*self.skill_args("--live", "--reviewed-catalog", "--agent", "claude", "--show-skill"))
        self.assertEqual(value["route"], "recommendation")
        self.assertEqual(value["selected_skill"]["name"], "plain-text")
        self.assertEqual(value["selected_skill"]["invocation"], "/plain-text")
        self.assertEqual(Path(value["selected_skill"]["path"]), (self.skills / "plain-text" / "SKILL.md").resolve())
        self.assertEqual(value["next_action"], "read_skill_then_apply")
        self.assertIn("PRIVATE_SKILL_BODY_SENTINEL", value["skill_body"])
        transmitted = json.dumps(self.payloads)
        self.assertNotIn(str(self.skills), transmitted)
        self.assertNotIn("PRIVATE_SKILL_BODY_SENTINEL", transmitted)
        self.assertNotIn("jev-skill-picker", transmitted)

    def test_catalog_review_required_before_scanning_for_live_and_enabled_automatic(self):
        toggle(self.state_dir, "skill", True)
        for mode in ("--live", "--automatic"):
            with self.subTest(mode=mode), patch.object(cli, "prepare_skills") as scan, \
                    patch.object(cli, "Client") as client:
                value = self.run_cli(*self.skill_args(mode))
                self.assertEqual(value["reason"], "catalog_review_required")
                scan.assert_not_called()
                client.assert_not_called()

    def test_changed_catalog_requires_review_again_before_network(self):
        from jev_skills.integration import reviewed_digest
        from jev_skills.skill_selection import prepare_skills
        data, _ = prepare_skills("Public task", [self.skills])
        digest = reviewed_digest(data["candidates"])
        with self.client():
            value = self.run_cli(*self.skill_args("--live", "--reviewed-catalog", "--catalog-digest", digest))
        self.assertEqual(value["route"], "recommendation")
        path = self.skills / "plain-text" / "SKILL.md"
        path.write_text(path.read_text().replace("Summarize supplied text clearly", "New private metadata not reviewed"))
        with patch.object(cli, "Client") as client:
            value = self.run_cli(*self.skill_args("--live", "--reviewed-catalog", "--catalog-digest", digest))
        self.assertEqual(value["reason"], "catalog_changed_review_required")
        client.assert_not_called()

    def test_disabled_private_explicit_followup_and_child_bypass_all_input_reads(self):
        for command in ("route-model", "pick-skill"):
            target = ("--profile", str(self.root / "absent-profile")) if command == "route-model" else ("--root", str(self.root / "absent-root"))
            for extra, child, reason in ((["--automatic"], "", "disabled"),
                                         (["--live", "--private"], "", "private"),
                                         (["--live", "--follow-up"], "", "contextual_follow_up"),
                                         (["--live"], "1", "child_recursion_guard")):
                with self.subTest(command=command, reason=reason), \
                        patch.dict(os.environ, {"JEV_SKILLS_CHILD": child}), \
                        patch.object(cli, "read_text", side_effect=AssertionError("input read")), \
                        patch.object(cli, "prepare_skills", side_effect=AssertionError("scan")), \
                        patch.object(cli, "prepare_model_input", side_effect=AssertionError("profile")), \
                        patch.object(cli, "Client", side_effect=AssertionError("network")), \
                        patch.object(cli, "run_helper", side_effect=AssertionError("host")):
                    value = self.run_cli(command, "--request-file", "absent-request", *target, *extra)
                    self.assertEqual(value["reason"], reason)

    def test_detected_contextual_reply_bypasses_profile_and_catalog(self):
        for command in ("route-model", "pick-skill"):
            target = ("--profile", "absent-profile") if command == "route-model" else ("--root", "absent-root")
            with self.subTest(command=command), \
                    patch.object(cli, "read_text", side_effect=AssertionError("read")), \
                    patch.object(cli, "prepare_skills", side_effect=AssertionError("scan")), \
                    patch.object(cli, "Client", side_effect=AssertionError("network")):
                value = self.run_cli(command, "--request", "yes, use that one", *target, "--live")
                self.assertEqual(value["reason"], "contextual_follow_up")

    def test_malformed_and_recursive_profile_json_fall_back_without_leaking_text(self):
        for contents in ('{"private":"DO_NOT_ECHO"', "[" * 2000 + "0" + "]" * 2000):
            self.profile.write_text(contents, encoding="utf-8")
            with self.subTest(length=len(contents)), patch.object(cli, "Client") as client, \
                    patch.object(cli, "run_helper") as helper:
                value = self.run_cli(*self.model_args("--live", "--execute"))
                self.assertEqual(value["route"], "fallback")
                # Python versions differ in whether deeply nested valid JSON
                # parses successfully; either parser or profile validation must
                # reject it safely before network or execution.
                self.assertIn(value["reason"], ("invalid_input_or_local_io", "invalid_model_profile"))
                self.assertNotIn("DO_NOT_ECHO", json.dumps(value))
                client.assert_not_called()
                helper.assert_not_called()

    def test_json_parser_recursion_error_is_fail_open(self):
        output = io.StringIO()
        with patch.object(cli.json, "loads", side_effect=RecursionError), \
                patch.object(cli, "Client") as client, redirect_stdout(output):
            self.assertEqual(cli.main(list(self.model_args("--live"))), 0)
            client.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["reason"], "invalid_input_or_local_io")

    def test_enabled_automatic_routes_but_does_not_execute_without_flag(self):
        toggle(self.state_dir, "model", True)
        with self.client("test-fast"), patch.object(cli, "run_helper") as helper:
            value = self.run_cli(*self.model_args("--automatic"))
        self.assertEqual(value["route"], "recommendation")
        helper.assert_not_called()


if __name__ == "__main__":
    unittest.main()
