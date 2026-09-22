import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_skills.core import DecisionError
from jev_skills.hosts import _parse, run_helper
from jev_skills.profiles import prepare_model_input


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = {"agent": "codex", "models": [
            {"id": "test-economy", "size": "tiny", "description": "Simple supplied text", "effort": "low"},
            {"id": "test-expert", "size": "hardest", "description": "Complex reasoning"},
        ]}

    def test_preserves_user_order_and_exact_ids_without_prices(self):
        before = copy.deepcopy(self.profile)
        data, mapping = prepare_model_input("Summarize text", self.profile)
        self.assertEqual([item["id"] for item in data["candidates"]], ["test-economy", "test-expert"])
        self.assertNotIn("effort", data["candidates"][0])
        self.assertEqual(mapping["test-economy"]["effort"], "low")
        self.assertEqual(mapping["test-expert"]["agent"], "codex")
        self.assertEqual(before, self.profile)
        self.assertNotIn("price", json.dumps(data))

    def test_rejects_commands_duplicates_unknown_fields_and_invalid_values(self):
        cases = []
        for field, value in (("id", "--model"), ("id", "x; touch file"), ("id", "none"),
                             ("size", "big"), ("description", ""), ("effort", "extreme"),
                             ("command", "arbitrary executable")):
            profile = copy.deepcopy(self.profile)
            profile["models"][0][field] = value
            cases.append(profile)
        cases += [{**self.profile, "agent": "sh"}, {**self.profile, "command": "sh"},
                  {**self.profile, "models": []}, {**self.profile, "models": self.profile["models"] * 3},
                  {**self.profile, "models": [self.profile["models"][0]] * 2}]
        for profile in cases:
            with self.subTest(profile=profile), self.assertRaises(DecisionError):
                prepare_model_input("task", profile)


class HostTests(unittest.TestCase):
    def invoke(self, agent="codex", source=None, timeout=2, effort=None):
        """Use a real local Python process, never an actual provider CLI."""
        if source is None:
            source = ('import sys,json; sys.stdin.read(); '
                      'print(json.dumps({"type":"item.completed","item":'
                      '{"type":"agent_message","text":"A concise answer"}})); '
                      'print(json.dumps({"type":"turn.completed","usage":'
                      '{"input_tokens":12,"output_tokens":4}}))')
        original_popen = subprocess.Popen
        captured = {}

        def local_process(argv, **kwargs):
            captured.update(argv=argv, kwargs=kwargs, cwd_exists=Path(kwargs["cwd"]).exists())
            captured["process"] = original_popen([sys.executable, "-c", source], **kwargs)
            return captured["process"]

        with patch("jev_skills.hosts.shutil.which", return_value="/trusted/bin/" + agent), \
                patch("jev_skills.hosts.subprocess.Popen", side_effect=local_process), \
                patch.dict(os.environ, {"TYPESAFE_API_KEY": "routing-test-secret", "JEV_SKILLS_CHILD": ""}):
            result = run_helper(agent, "test-model", "private supplied task", timeout, effort)
        return result, captured

    def test_codex_no_argv_prompt_or_key_isolated_cwd_and_honest_metadata(self):
        result, captured = self.invoke(effort="low")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["answer"], "A concise answer")
        self.assertEqual(result["requested_model"], "test-model")
        self.assertIsNone(result["reported_model"])
        self.assertIsNone(result["cost"])
        self.assertEqual(result["usage"], {"input_tokens": 12, "output_tokens": 4})
        argv, kwargs = captured["argv"], captured["kwargs"]
        self.assertNotIn("private supplied task", " ".join(argv))
        self.assertNotIn("routing-test-secret", " ".join(argv))
        self.assertNotIn("TYPESAFE_API_KEY", kwargs["env"])
        self.assertEqual(kwargs["env"]["JEV_SKILLS_CHILD"], "1")
        self.assertEqual(kwargs["env"]["PWD"], kwargs["cwd"])
        self.assertNotIn("OLDPWD", kwargs["env"])
        self.assertFalse(kwargs["shell"])
        self.assertTrue(kwargs["start_new_session"])
        self.assertTrue(captured["cwd_exists"])
        self.assertNotEqual(Path(kwargs["cwd"]), Path.cwd())
        self.assertFalse(Path(kwargs["cwd"]).exists())
        self.assertEqual(argv[-1], "-")
        self.assertEqual(argv[argv.index("--sandbox") + 1], "read-only")
        for value in ("--ignore-user-config", "--ephemeral", 'approval_policy="never"',
                      "project_doc_max_bytes=0", "shell_tool", "unified_exec", "apps",
                      "plugins", "multi_agent", "computer_use", 'model_reasoning_effort="low"'):
            self.assertIn(value, argv)
        self.assertIn("skip_host_skill_discovery", argv)
        self.assertNotIn("--ignore-rules", argv)

    def test_stdin_reaches_helper(self):
        source = ('import sys,json; prompt=sys.stdin.read(); '
                  'print(json.dumps({"type":"result","subtype":"success",'
                  '"is_error":False,"result":prompt}))')
        result, _ = self.invoke("claude", source)
        self.assertIn("private supplied task", result["answer"])

    def test_claude_disables_tools_preserves_actual_model_and_reported_cost(self):
        envelope = {"type": "result", "subtype": "success", "is_error": False, "result": "Answer",
                    "usage": {"input_tokens": 8, "output_tokens": 2, "private_data": "ignored"},
                    "modelUsage": {"test-runtime-model": {"inputTokens": 8}}, "total_cost_usd": 0.012}
        source = "import sys; sys.stdin.read(); print(" + repr(json.dumps(envelope)) + ")"
        result, captured = self.invoke("claude", source, effort="medium")
        self.assertEqual(result["reported_model"], "test-runtime-model")
        self.assertEqual(result["requested_model"], "test-model")
        self.assertEqual(result["cost"], {"usd": 0.012})
        self.assertNotIn("private_data", result["usage"])
        argv = captured["argv"]
        self.assertEqual(argv[argv.index("--tools") + 1], "")
        self.assertEqual(argv[argv.index("--disallowedTools") + 1], "mcp__*")
        self.assertEqual(argv[argv.index("--mcp-config") + 1], '{"mcpServers":{}}')
        for flag in ("--safe-mode", "--strict-mcp-config", "--no-session-persistence",
                     "--disable-slash-commands", "--no-chrome"):
            self.assertIn(flag, argv)
        self.assertNotIn("--dangerously-skip-permissions", argv)

    def test_unknown_claude_runtime_model_and_cost_are_null(self):
        parsed = _parse("claude", json.dumps({"type": "result", "subtype": "success",
                       "is_error": False, "result": "answer"}).encode())
        self.assertIsNone(parsed["reported_model"])
        self.assertIsNone(parsed["cost"])

    def test_claude_missing_auth_blocks_before_model_call_without_account_details(self):
        with patch("jev_skills.hosts.shutil.which", return_value="/trusted/bin/claude"), \
                patch("jev_skills.hosts._run_process", return_value=(
                    b'{"loggedIn":false,"email":"private@example.invalid"}', 1)) as launch, \
                patch.dict(os.environ, {"JEV_SKILLS_CHILD": ""}):
            result = run_helper("claude", "test-model", "private supplied task", timeout=10)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "host_authentication_required")
        self.assertEqual(launch.call_count, 1)
        command, _, environment, prompt, deadline = launch.call_args.args
        self.assertEqual(command, ["/trusted/bin/claude", "--safe-mode", "auth", "status", "--json"])
        self.assertEqual(prompt, b"")
        self.assertNotIn("TYPESAFE_API_KEY", environment)
        self.assertLessEqual(deadline - time.monotonic(), 3)
        self.assertNotIn("private@", json.dumps(result))

    def test_claude_auth_unknown_versions_and_api_key_auth_continue_to_helper(self):
        success = json.dumps({"type": "result", "subtype": "success", "is_error": False,
                              "result": "answer"}).encode()
        for status in (b'{"loggedIn":true,"authMethod":"api_key"}', b'unknown command', b'{}'):
            with self.subTest(status=status), \
                    patch("jev_skills.hosts.shutil.which", return_value="/trusted/bin/claude"), \
                    patch("jev_skills.hosts._run_process", side_effect=[(status, 0), (success, 0)]) as launch, \
                    patch.dict(os.environ, {"JEV_SKILLS_CHILD": ""}):
                result = run_helper("claude", "test-model", "supplied task")
            self.assertEqual(result["status"], "completed")
            self.assertEqual(launch.call_count, 2)
            self.assertIn("--print", launch.call_args.args[0])

    def test_claude_auth_preflight_consumes_overall_deadline(self):
        result, captured = self.invoke("claude", 'import time; time.sleep(30)', timeout=0.1)
        self.assertEqual(result["status"], "timeout")
        self.assertNotIn("--print", captured["argv"])
        self.assertTrue(captured["process"].stdout.closed)

    def test_stderr_and_failure_bodies_are_never_exposed(self):
        source = 'import sys; sys.stdin.read(); print("secret prompt response"); sys.stderr.write("routing-test-secret"); sys.exit(3)'
        result, _ = self.invoke(source=source)
        self.assertEqual(result["reason"], "host_process_failed")
        self.assertNotIn("secret", json.dumps(result))
        self.assertIsNone(result["answer"])

    def test_timeout_kills_process_group_including_inherited_pipe_owner(self):
        source = ('import subprocess,sys; sys.stdin.read(); '
                  'subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"])')
        start = time.monotonic()
        result, captured = self.invoke(source=source, timeout=0.15)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["reason"], "helper_deadline_exceeded")
        self.assertLess(time.monotonic() - start, 2)
        self.assertIsNotNone(captured["process"].poll())
        self.assertTrue(captured["process"].stdout.closed)

    def test_output_limit_is_enforced_while_process_is_running(self):
        source = 'import sys; sys.stdin.read(); sys.stdout.write("x" * 3000000); sys.stdout.flush()'
        result, captured = self.invoke(source=source)
        self.assertEqual(result["reason"], "helper_output_too_large")
        self.assertIsNotNone(captured["process"].poll())

    def test_invalid_json_and_partial_codex_response_fail(self):
        for raw in (b"not json", b'[]', b'{"type":"turn.completed"}',
                    b'{"type":"item.completed","item":{"type":"agent_message","text":"partial"}}'):
            with self.subTest(raw=raw), self.assertRaises(DecisionError):
                _parse("codex", raw)
        with self.assertRaisesRegex(DecisionError, "helper_reported_error"):
            _parse("codex", b'{"type":"turn.failed","error":{"message":"secret"}}')

    def test_claude_error_result_never_exposes_error_body(self):
        result = _parse("claude", json.dumps({"type": "result", "subtype": "error_during_execution",
                       "is_error": True, "result": "secret", "total_cost_usd": 0.01}).encode())
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["answer"])
        self.assertEqual(result["cost"], {"usd": 0.01})

    def test_unavailable_recursive_and_invalid_calls_never_spawn(self):
        with patch("jev_skills.hosts.subprocess.Popen") as launch, \
                patch("jev_skills.hosts.shutil.which", return_value=None), \
                patch.dict(os.environ, {"JEV_SKILLS_CHILD": ""}):
            self.assertEqual(run_helper("codex", "test-model", "task")["status"], "unavailable")
            for args in (("sh", "test-model", "task"), ("codex", "--evil", "task"),
                         ("codex", "test-model", "")):
                with self.assertRaises(DecisionError):
                    run_helper(*args)
            for timeout in (0, float("inf"), True, 301):
                with self.assertRaises(DecisionError):
                    run_helper("codex", "test-model", "task", timeout=timeout)
            with patch.dict(os.environ, {"JEV_SKILLS_CHILD": "1"}):
                self.assertEqual(run_helper("claude", "test-model", "task")["reason"], "nested_helper_blocked")
            launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
