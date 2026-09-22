"""Offline installation transaction and diagnostic regressions."""

import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_skills import installation
from jev_skills.core import DecisionError
from jev_skills.diagnostics import doctor


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / "skills"

    def install_published_v01(self):
        """Recreate the exact seven files from the published v0.1 Git commit."""
        root = Path(__file__).resolve().parents[1]
        commit = "168374dd8238771f595f2cc91237a7085bc88ac6"
        originals = {}
        for name in installation.packaged_skills():
            try:
                result = subprocess.run(
                    ["git", "show", f"{commit}:src/jev_skills/skills/{name}/SKILL.md"],
                    cwd=root, capture_output=True, check=False,
                )
            except OSError:
                self.skipTest("Git is unavailable for the published v0.1 fixture")
            if result.returncode:
                self.skipTest("Published v0.1 Git commit is unavailable")
            folder = self.target / name
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "SKILL.md").write_bytes(result.stdout)
            originals[name] = result.stdout
        return originals

    def test_install_manifest_and_idempotence(self):
        first = installation.install_skills("codex", self.target)
        self.assertEqual(first["status"], "installed")
        self.assertEqual(len(first["installed"]), 7)
        manifest = json.loads((self.target / installation.MANIFEST).read_text())
        self.assertEqual(manifest["package_version"], first["package_version"])
        self.assertEqual(len(manifest["skills"]), 7)
        self.assertTrue(all("SKILL.md" in files for files in manifest["skills"].values()))
        self.assertEqual(installation.install_skills("codex", self.target)["status"], "unchanged")

    def test_unowned_exact_adoption_and_conflict_preflight(self):
        self.target.mkdir()
        source = Path(installation.__file__).parent / "skills"
        for name in installation.packaged_skills():
            shutil.copytree(source / name, self.target / name)
        self.assertEqual(installation.install_skills("codex", self.target)["status"], "adopted")
        (self.target / installation.MANIFEST).unlink()
        (self.target / next(iter(installation.packaged_skills())) / "SKILL.md").write_text("edited")
        with self.assertRaisesRegex(DecisionError, "unowned_skill_conflict"):
            installation.install_skills("codex", self.target)
        self.assertFalse((self.target / installation.MANIFEST).exists())

    def test_exact_published_v01_upgrades_only_with_flag(self):
        originals = self.install_published_v01()
        with self.assertRaisesRegex(DecisionError, "unowned_skill_conflict"):
            installation.install_skills("codex", self.target)
        self.assertFalse((self.target / installation.MANIFEST).exists())
        result = installation.install_skills("codex", self.target, upgrade=True)
        self.assertEqual(result["status"], "upgraded")
        self.assertEqual(result["migrated_from"], "0.1.0")
        self.assertEqual(installation.inspect_install("codex", self.target)["status"], "managed")
        backup = Path(result["backup"])
        self.assertFalse((backup / installation.MANIFEST).exists())
        for name, original in originals.items():
            self.assertEqual((backup / name / "SKILL.md").read_bytes(), original)
            self.assertEqual(
                installation._files(self.target / name),
                installation.packaged_skills()[name],
            )
        self.assertEqual(installation.install_skills("codex", self.target)["status"], "unchanged")

    def test_modified_or_extended_published_v01_is_not_claimed(self):
        originals = self.install_published_v01()
        name = next(iter(originals))
        skill = self.target / name / "SKILL.md"
        skill.write_bytes(originals[name] + b"\nlocal edit\n")
        with self.assertRaisesRegex(DecisionError, "unowned_skill_conflict"):
            installation.install_skills("codex", self.target, upgrade=True)
        self.assertEqual(skill.read_bytes(), originals[name] + b"\nlocal edit\n")
        self.assertFalse((self.target / installation.MANIFEST).exists())
        skill.write_bytes(originals[name])
        extra = self.target / name / "my-notes.txt"
        extra.write_text("mine")
        with self.assertRaisesRegex(DecisionError, "unowned_skill_conflict"):
            installation.install_skills("codex", self.target, upgrade=True)
        self.assertEqual(extra.read_text(), "mine")
        self.assertFalse((self.target / installation.MANIFEST).exists())

    def test_published_v01_upgrade_rollback_restores_manifest_absence(self):
        originals = self.install_published_v01()
        original_replace = os.replace
        calls = 0

        def fail_after_first_new(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 9:  # Seven backups, one new directory, then failure.
                raise OSError("injected")
            return original_replace(*args, **kwargs)

        with patch.object(installation.os, "replace", side_effect=fail_after_first_new):
            with self.assertRaises(OSError):
                installation.install_skills("codex", self.target, upgrade=True)
        self.assertFalse((self.target / installation.MANIFEST).exists())
        self.assertEqual(sorted(path.name for path in self.target.iterdir()), sorted(originals))
        for name, original in originals.items():
            self.assertEqual((self.target / name / "SKILL.md").read_bytes(), original)

    def test_modified_file_blocks_upgrade_and_preserves_extra(self):
        installation.install_skills("claude", self.target)
        name = next(iter(installation.packaged_skills()))
        path = self.target / name / "SKILL.md"
        extra = self.target / name / "mine.txt"
        path.write_text("my edits")
        extra.write_text("keep")
        with self.assertRaisesRegex(DecisionError, "modified_installed_skill"):
            installation.install_skills("claude", self.target, upgrade=True)
        self.assertEqual(path.read_text(), "my edits")
        self.assertEqual(extra.read_text(), "keep")

    def test_upgrade_retains_extras_and_recovery_backup(self):
        installation.install_skills("codex", self.target)
        name = next(iter(installation.packaged_skills()))
        extra = self.target / name / "mine.txt"
        extra.write_text("mine")
        manifest_path = self.target / installation.MANIFEST
        old_manifest = json.loads(manifest_path.read_text())
        # Simulate a previous packaged version without changing the current
        # owned file: old content is empty and its declared hash agrees.
        (self.target / name / "SKILL.md").write_bytes(b"")
        old_manifest["skills"][name]["SKILL.md"] = hashlib.sha256(b"").hexdigest()
        old_manifest["package_version"] = "0.0.1"
        manifest_path.write_text(json.dumps(old_manifest))
        result = installation.install_skills("codex", self.target, upgrade=True)
        self.assertEqual(result["status"], "upgraded")
        self.assertEqual(extra.read_text(), "mine")
        self.assertEqual((Path(result["backup"]) / name / "SKILL.md").read_bytes(), b"")
        self.assertEqual((Path(result["backup"]) / name / "mine.txt").read_text(), "mine")

    def test_second_copy_failure_never_installs_partially(self):
        original = shutil.copytree
        calls = 0
        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected")
            return original(*args, **kwargs)
        with patch.object(installation.shutil, "copytree", side_effect=fail_second):
            with self.assertRaises(OSError):
                installation.install_skills("codex", self.target)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_second_rename_failure_rolls_back_all_files(self):
        original = os.replace
        calls = 0
        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected")
            return original(*args, **kwargs)
        with patch.object(installation.os, "replace", side_effect=fail_second):
            with self.assertRaises(OSError):
                installation.install_skills("codex", self.target)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_upgrade_rename_failure_restores_original_and_manifest(self):
        installation.install_skills("codex", self.target)
        name = next(iter(installation.packaged_skills()))
        path = self.target / name / "SKILL.md"
        path.write_bytes(b"old")
        marker = self.target / name / "extra.txt"
        marker.write_text("untouched")
        manifest_path = self.target / installation.MANIFEST
        old_manifest = json.loads(manifest_path.read_text())
        old_manifest["skills"][name]["SKILL.md"] = hashlib.sha256(b"old").hexdigest()
        manifest_path.write_text(json.dumps(old_manifest))
        original = os.replace
        calls = 0
        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected")
            return original(*args, **kwargs)
        with patch.object(installation.os, "replace", side_effect=fail_second):
            with self.assertRaises(OSError):
                installation.install_skills("codex", self.target, upgrade=True)
        self.assertEqual(path.read_bytes(), b"old")
        self.assertEqual(marker.read_text(), "untouched")
        self.assertEqual(json.loads(manifest_path.read_text()), old_manifest)

    def test_upgrade_failure_after_first_new_directory_restores_all(self):
        installation.install_skills("codex", self.target)
        name = next(iter(installation.packaged_skills()))
        original_file = self.target / name / "SKILL.md"
        original_file.write_bytes(b"old")
        manifest_path = self.target / installation.MANIFEST
        original_manifest = json.loads(manifest_path.read_text())
        original_manifest["skills"][name]["SKILL.md"] = hashlib.sha256(b"old").hexdigest()
        manifest_path.write_text(json.dumps(original_manifest))
        original_replace = os.replace
        calls = 0
        def fail_after_first_new(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 10:  # Eight backups, one new directory, then failure.
                raise OSError("injected")
            return original_replace(*args, **kwargs)
        with patch.object(installation.os, "replace", side_effect=fail_after_first_new):
            with self.assertRaises(OSError):
                installation.install_skills("codex", self.target, upgrade=True)
        self.assertEqual(original_file.read_bytes(), b"old")
        self.assertEqual(json.loads(manifest_path.read_text()), original_manifest)
        self.assertEqual(len(list(self.target.iterdir())), 8)

    def test_unknown_manifest_target_and_symlink_never_followed(self):
        installation.install_skills("codex", self.target)
        marker = Path(self.temp.name) / "outside.txt"
        marker.write_text("outside")
        manifest_path = self.target / installation.MANIFEST
        value = json.loads(manifest_path.read_text())
        value["skills"]["../outside"] = {"SKILL.md": "0" * 64}
        manifest_path.write_text(json.dumps(value))
        with self.assertRaisesRegex(DecisionError, "invalid_install_manifest"):
            installation.install_skills("codex", self.target, upgrade=True)
        self.assertEqual(marker.read_text(), "outside")
        manifest_path.unlink()
        manifest_path.symlink_to(marker)
        with self.assertRaisesRegex(DecisionError, "unsafe_install_manifest"):
            installation.install_skills("codex", self.target)
        self.assertEqual(marker.read_text(), "outside")

    def test_manifest_file_traversal_and_skill_symlink_are_refused(self):
        installation.install_skills("codex", self.target)
        manifest_path = self.target / installation.MANIFEST
        value = json.loads(manifest_path.read_text())
        name = next(iter(value["skills"]))
        value["skills"][name]["../../outside"] = "0" * 64
        manifest_path.write_text(json.dumps(value))
        with self.assertRaisesRegex(DecisionError, "invalid_install_manifest"):
            installation.install_skills("codex", self.target, upgrade=True)
        del value["skills"][name]["../../outside"]
        manifest_path.write_text(json.dumps(value))
        outside = Path(self.temp.name) / "outside"
        outside.write_text("safe")
        (self.target / name / "linked").symlink_to(outside)
        with self.assertRaisesRegex(DecisionError, "unsafe_skill_symlink"):
            installation.install_skills("codex", self.target, upgrade=True)
        self.assertEqual(outside.read_text(), "safe")

    def test_doctor_reports_invalid_manifest_without_following_it(self):
        installation.install_skills("codex", self.target)
        (self.target / installation.MANIFEST).write_text("broken")
        with patch.dict(os.environ, {"JEV_SKILLS_HOME": self.temp.name}):
            result = doctor("codex", self.target)
        self.assertEqual(result["agents"]["codex"]["skills"]["status"], "invalid_manifest")

    def test_doctor_is_offline_presence_only(self):
        with patch.dict(os.environ, {"JEV_SKILLS_HOME": self.temp.name, "TYPESAFE_API_KEY": "secret"}), \
                patch("jev_skills.diagnostics.shutil.which", return_value=None):
            result = doctor("codex", self.target)
        self.assertTrue(result["python_supported"])
        self.assertTrue(result["typesafe_api_key_present"])
        self.assertFalse(result["agents"]["codex"]["binary_available"])
        self.assertEqual(len(result["agents"]["codex"]["skills"]["missing"]), 7)
        self.assertNotIn("secret", json.dumps(result))
        self.assertIn("not verified", result["note"])


if __name__ == "__main__":
    unittest.main()
