"""Offline tests for catalog to typed decision to local selected-body handoff."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_skills.catalog import MAX_SKILL_BYTES, catalog, manifest
from jev_skills.core import Client, DecisionError, select
from jev_skills.skill_selection import (attach_selection, contextual_followup,
                                        load_selected, prepare_skills)


class SkillSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "public-skills"
        self.root.mkdir()

    def skill(self, folder, header, body="Public synthetic body"):
        directory = self.root / folder
        directory.mkdir()
        path = directory / "SKILL.md"
        path.write_text("---\n" + header + "\n---\n" + body, encoding="utf-8")
        return path

    def test_typed_input_excludes_paths_and_selected_body_requires_explicit_read(self):
        chosen = self.skill("sums", "name: sum-helper\ndescription: >\n  Add integers\n  from supplied input.")
        self.skill("jev-skill-picker", "name: jev-skill-picker\ndescription: Pick a skill")
        self.skill("opted-out", "name: opt-out\ndescription: Never send this", body="SECRET_BODY")
        data, mapping = prepare_skills("Add two numbers", [self.root], exclude=["opt-out"])
        self.assertEqual(data["candidates"], [{"id": "sum-helper", "description": "Add integers from supplied input."}])
        self.assertEqual(set(mapping), {"sum-helper"})
        def transport(payload, timeout):
            wire = json.dumps(payload)
            self.assertNotIn(str(self.root), wire)
            self.assertNotIn("SECRET_BODY", wire)
            self.assertNotIn("Public synthetic body", wire)
            self.assertEqual(set(payload["questions"]["selection"]["criteria"]), {"sum-helper", "none"})
            return {"model": "test", "answers": {"selection": {"type": "choice", "choice": "sum-helper",
                    "confidence": 0.95, "probabilities": {"sum-helper": 0.95, "none": 0.05}}},
                    "usage": {"input_tokens": 1, "output_tokens": 1}}
        result = select("skill", data, Client(transport=transport))
        attached = attach_selection(result, mapping, agent="codex")
        self.assertEqual(attached["selected_skill"]["path"], str(chosen.resolve()))
        self.assertEqual(attached["selected_skill"]["invocation"], "$sum-helper")
        self.assertEqual(attached["next_action"], "read_skill_then_apply")
        self.assertEqual(load_selected(result, mapping), chosen.read_text(encoding="utf-8"))
        self.assertEqual(attach_selection(result, mapping, agent="claude")["selected_skill"]["invocation"], "/sum-helper")

    def test_alias_roots_names_collisions_and_parent_paths_stay_local(self):
        first = self.skill("a", "name: same\ndescription: First public description")
        second = self.skill("b", "name: same\ndescription: Second public description")
        alias = self.root.parent / "alias-root"
        alias.symlink_to(self.root, target_is_directory=True)
        entries = catalog([self.root, alias])["candidates"]
        self.assertEqual(len(entries), 2)
        self.assertEqual(len({item["id"] for item in entries}), 2)
        self.assertTrue(all(item["id"].startswith("same-") for item in entries))
        self.assertEqual({item["path"] for item in entries}, {str(first.resolve()), str(second.resolve())})
        self.assertEqual(entries, catalog([alias, self.root])["candidates"])
        data, mapping = prepare_skills("Which same skill?", [self.root, alias])
        self.assertEqual(len(data["candidates"]), 2)
        self.assertNotIn(str(self.root.parent), json.dumps(data))
        self.assertEqual(set(mapping), {item["id"] for item in entries})

    def test_missing_name_quoted_multiline_and_skip_warnings(self):
        fallback = self.skill("claude-style", "description: 'Useful for ''quoted'' descriptions.' # explanation")
        quoted = self.skill("quoted", 'name: "quoted skill"\ndescription: "Line one\n  and line two" # explanation')
        self.assertEqual(manifest(fallback), ("claude-style", "Useful for 'quoted' descriptions."))
        self.assertEqual(manifest(quoted)[1], "Line one and line two")
        self.skill("invalid", "name: invalid\ndescription: [unsupported, sequence]")
        self.skill("huge", "name: huge\ndescription: Tiny", body="x" * MAX_SKILL_BYTES)
        notes = self.root / "!notes"
        notes.mkdir()
        (notes / "SKILL.md").write_text("sensitive", encoding="utf-8")
        inventory = catalog([self.root])
        self.assertEqual(len(inventory["candidates"]), 2)
        self.assertEqual({item["reason"] for item in inventory["skipped"]},
                         {"unsupported_skill_metadata", "skill_file_too_large"})

    def test_changed_or_unselected_body_fails_closed(self):
        chosen = self.skill("one", "name: one\ndescription: First")
        data, mapping = prepare_skills("First", [self.root])
        recommendation = {"route": "recommendation", "selected": "one"}
        self.assertEqual(mapping["one"]["sha256"], hashlib.sha256(chosen.read_bytes()).hexdigest())
        with self.assertRaisesRegex(DecisionError, "no_selected_skill"):
            load_selected({"route": "fallback", "selected": None}, mapping)
        with self.assertRaisesRegex(DecisionError, "selected_skill_not_in_catalog"):
            attach_selection({"route": "recommendation", "selected": "unknown"}, mapping)
        chosen.write_text(chosen.read_text(encoding="utf-8") + "\nNew content", encoding="utf-8")
        with self.assertRaisesRegex(DecisionError, "selected_skill_changed"):
            load_selected(recommendation, mapping)
        with self.assertRaisesRegex(DecisionError, "invalid_skill_read_limit"):
            load_selected(recommendation, mapping, max_bytes=MAX_SKILL_BYTES + 1)

    def test_explicit_ids_and_no_unrequested_scan(self):
        self.skill("one", "name: one\ndescription: First")
        self.skill("two", "name: two\ndescription: Second")
        data, mapping = prepare_skills("First", [self.root], allowed_ids={"one"})
        self.assertEqual([candidate["id"] for candidate in data["candidates"]], ["one"])
        self.assertEqual(set(mapping), {"one"})
        with patch("jev_skills.skill_selection.catalog", side_effect=AssertionError("scanned")):
            self.assertTrue(contextual_followup("yes do that but make it shorter"))

    def test_conservative_contextual_gate(self):
        for text in ("yes do that but make it shorter", "use second one", "да, сделай это короче",
                     "выбери второй вариант", "ок", "сделай так"):
            with self.subTest(text=text):
                self.assertTrue(contextual_followup(text))
        for text in ("fix parser", "translate hello", "исправь парсер", "переведи привет",
                     "Create a second parser", "", "First-principles review of this design"):
            with self.subTest(text=text):
                self.assertFalse(contextual_followup(text))


if __name__ == "__main__":
    unittest.main()
