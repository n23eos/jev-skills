"""Project-scoped managed instruction block regressions."""

import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_skills.core import DecisionError
from jev_skills.integration import BEGIN, END, integrate, reviewed_digest
from jev_skills.cli import parser


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        self.project.mkdir()
        self.root = Path(self.temp.name) / "skills with spaces"
        self.root.mkdir()
        self.skill = self.root / "sample"
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_text(
            "---\nname: sample\ndescription: Public synthetic skill.\n---\nBody\n",
            encoding="utf-8")

    def test_skill_block_is_opt_in_and_has_parseable_command(self):
        result = integrate("codex", self.project, [self.root], reviewed_catalog=True)
        self.assertEqual(result["status"], "created")
        path = self.project / "AGENTS.md"
        text = path.read_text()
        self.assertEqual((text.count(BEGIN), text.count(END)), (1, 1))
        command = next(line.strip() for line in text.splitlines() if line.startswith("    jev-skills "))
        args = parser().parse_args(shlex.split(command)[1:])
        self.assertEqual(args.command, "pick-skill")
        self.assertEqual(args.root, [self.root.resolve()])
        self.assertTrue(args.automatic and args.reviewed_catalog)
        expected = reviewed_digest([{"id": "sample", "description": "Public synthetic skill."}])
        self.assertEqual(args.catalog_digest, expected)
        self.assertEqual(args.request_file, "-")
        self.assertEqual(args.agent, "codex")
        self.assertIn("full selected SKILL.md", text)
        self.assertIn("JEV_SKILLS_CHILD", text)
        self.assertIn("higher-priority", text)
        self.assertNotIn("--execute", command)
        self.assertEqual(integrate("codex", self.project, [self.root], reviewed_catalog=True)["status"], "unchanged")

    def test_reviewed_digest_is_canonical_and_metadata_changes_repin(self):
        candidates = [{"description": "Public synthetic skill.", "id": "sample"}]
        canonical = json.dumps(candidates, sort_keys=True, ensure_ascii=True,
                               separators=(",", ":")).encode("utf-8")
        self.assertEqual(reviewed_digest(candidates), hashlib.sha256(canonical).hexdigest())
        integrate("codex", self.project, [self.root], reviewed_catalog=True)
        original = (self.project / "AGENTS.md").read_text()
        skill_file = self.skill / "SKILL.md"
        skill_file.write_text(skill_file.read_text() + "Unrelated body change\n")
        self.assertEqual(integrate("codex", self.project, [self.root], reviewed_catalog=True)["status"], "unchanged")
        self.assertEqual((self.project / "AGENTS.md").read_text(), original)
        skill_file.write_text(skill_file.read_text().replace("Public synthetic skill.", "Updated metadata."))
        self.assertEqual(integrate("codex", self.project, [self.root], reviewed_catalog=True)["status"], "updated")
        self.assertNotEqual((self.project / "AGENTS.md").read_text(), original)

    def test_existing_content_preserved_around_updated_block(self):
        path = self.project / "CLAUDE.md"
        before = "# User instructions\r\nDo not erase this.\r\n"
        after = "\r\n# Final user instructions\r\nKeep this too.\r\n"
        path.write_bytes((before + BEGIN + "\r\nold managed text\r\n" + END + "\r\n" + after).encode())
        result = integrate("claude", self.project, [self.root], reviewed_catalog=True)
        self.assertEqual(result["status"], "updated")
        content = path.read_bytes().decode()
        self.assertTrue(content.startswith(before))
        self.assertTrue(content.endswith(after))
        self.assertNotIn("old managed text", content)
        self.assertEqual((content.count(BEGIN), content.count(END)), (1, 1))

    def test_append_does_not_erase_existing_content(self):
        path = self.project / "AGENTS.md"
        path.write_text("Original without trailing newline")
        result = integrate("codex", self.project, [self.root], reviewed_catalog=True)
        self.assertEqual(result["status"], "added")
        self.assertTrue(path.read_text().startswith("Original without trailing newline\n\n" + BEGIN))

    def test_model_block_requires_profile_and_never_executes(self):
        with self.assertRaisesRegex(DecisionError, "profile_required"):
            integrate("claude", self.project, [], workflow="model")
        profile = self.project / "model profile.json"
        profile.write_text(json.dumps({"agent": "claude", "models": [
            {"id": "test-model", "size": "tiny", "description": "Public synthetic model"}]}))
        result = integrate("claude", self.project, [], profile=profile, workflow="model")
        self.assertEqual(result["status"], "created")
        text = (self.project / "CLAUDE.md").read_text()
        command = next(line.strip() for line in text.splitlines() if line.startswith("    jev-skills "))
        args = parser().parse_args(shlex.split(command)[1:])
        self.assertEqual(args.command, "route-model")
        self.assertEqual(args.profile, profile.resolve())
        self.assertTrue(args.automatic)
        self.assertFalse(args.execute)
        self.assertNotIn("--agent", command)
        self.assertIn("separately authorized", text)

    def test_model_integration_rejects_bad_or_wrong_host_profile(self):
        profile = self.project / "model.json"
        for value, error in (("{}", "invalid_model_profile"),
                             (json.dumps({"agent": "codex", "models": [
                                 {"id": "test-model", "size": "tiny", "description": "Synthetic"}]}),
                              "integration_profile_agent_mismatch"),
                             ("x" * 200_001, "input_too_large")):
            with self.subTest(error=error):
                profile.write_text(value)
                with self.assertRaisesRegex(DecisionError, error):
                    integrate("claude", self.project, [], profile=profile, workflow="model")
                self.assertFalse((self.project / "CLAUDE.md").exists())

    def test_missing_review_or_root_rejected_before_write(self):
        for roots, reviewed in (([self.root], False), ([], True)):
            with self.subTest(roots=roots, reviewed=reviewed):
                with self.assertRaises(DecisionError):
                    integrate("codex", self.project, roots, reviewed_catalog=reviewed)
                self.assertFalse((self.project / "AGENTS.md").exists())

    def test_malformed_or_duplicate_markers_refuse_change(self):
        path = self.project / "AGENTS.md"
        for text in (BEGIN + "\nno end", END + "\n" + BEGIN,
                     BEGIN + "\n" + END + "\n" + BEGIN + "\n" + END):
            with self.subTest(text=text):
                path.write_text(text)
                with self.assertRaisesRegex(DecisionError, "malformed_integration_markers"):
                    integrate("codex", self.project, [self.root], reviewed_catalog=True)
                self.assertEqual(path.read_text(), text)

    def test_symlink_instruction_and_notes_project_refused(self):
        outside = Path(self.temp.name) / "outside.txt"
        outside.write_text("keep")
        (self.project / "AGENTS.md").symlink_to(outside)
        with self.assertRaisesRegex(DecisionError, "unsafe_integration_instructions"):
            integrate("codex", self.project, [self.root], reviewed_catalog=True)
        self.assertEqual(outside.read_text(), "keep")
        notes = self.project / "!notes"
        notes.mkdir()
        with self.assertRaisesRegex(DecisionError, "unsafe_integration_project"):
            integrate("codex", notes, [self.root], reviewed_catalog=True)
        self.assertFalse((notes / "AGENTS.md").exists())

    def test_failed_atomic_replace_preserves_original(self):
        instruction = self.project / "AGENTS.md"
        instruction.write_text("user content")
        with patch("jev_skills.integration.os.replace", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                integrate("codex", self.project, [self.root], reviewed_catalog=True)
        self.assertEqual(instruction.read_text(), "user content")
        self.assertEqual(sorted(p.name for p in self.project.iterdir()), ["AGENTS.md"])


if __name__ == "__main__":
    unittest.main()
