"""Readable first-use diagnostics retain the existing offline JSON contract."""

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
from jev_skills.diagnostics import doctor, human_report
from jev_skills.installation import install_skills


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        env = patch.dict(os.environ, {"JEV_SKILLS_HOME": str(self.root / "state"),
                                     "TYPESAFE_API_KEY": "DO_NOT_DISPLAY_KEY"})
        env.start()
        self.addCleanup(env.stop)

    def test_missing_setup_actions_without_network_or_host_execution(self):
        with patch("jev_skills.diagnostics.shutil.which", return_value=None), \
                patch.object(cli, "Client", side_effect=AssertionError("network")), \
                patch.object(cli, "run_helper", side_effect=AssertionError("host")), \
                patch.dict(os.environ, {"TYPESAFE_API_KEY": ""}):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(cli.main(["doctor", "--agent", "codex", "--dest", str(self.root / "skills"),
                                           "--format", "human"]), 0)
        text = output.getvalue()
        self.assertIn("uv tool install", text)
        self.assertIn("Install curl", text)
        self.assertIn("Set TYPESAFE_API_KEY", text)
        self.assertIn("install --agent codex", text)
        self.assertIn("all off", text)
        self.assertNotIn("DO_NOT_DISPLAY_KEY", text)
        self.assertFalse((self.root / "state").exists())

    def test_default_and_explicit_json_are_compatible(self):
        args = ["doctor", "--agent", "codex", "--dest", str(self.root / "skills")]
        results = []
        for extra in ([], ["--format", "json"]):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(cli.main(args + extra), 0)
            results.append(json.loads(output.getvalue()))
        self.assertEqual(results[0], results[1])
        self.assertNotIn("DO_NOT_DISPLAY_KEY", json.dumps(results))
        self.assertNotIn("next_action", results[0])

    def test_verified_skills_and_edits_receive_different_next_actions(self):
        target = self.root / "skills"
        install_skills("codex", target)
        result = doctor("codex", target)
        text = human_report(result)
        self.assertIn("14 managed skills verified", text)
        self.assertIn("$jev-controls", text)
        self.assertIn("Key validity, host login and native skill discovery are unverified", text)
        path = target / "jev-controls" / "SKILL.md"
        path.write_text(path.read_text() + "\nLocal edit\n")
        text = human_report(doctor("codex", target))
        self.assertIn("modified: 1", text)
        self.assertIn("keep your edits", text)
        self.assertNotIn("14 managed skills verified", text)


if __name__ == "__main__":
    unittest.main()
