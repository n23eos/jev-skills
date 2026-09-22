---
name: jev-skill-picker
description: Suggest one relevant installed Agent Skill from an explicit, sanitized shortlist for a coding request.
---

# Skill selection

Use this skill when several discovered Agent Skills plausibly fit the user's request. Do not search for, install, or invoke a skill as a side effect of the recommendation.

1. Inventory local skill metadata if needed with `jev-skills catalog --root SKILLS_DIRECTORY --output catalog.json`. This creates a local manifest, not a network upload. Review its names, descriptions, and paths; shortlist only relevant, installed skills and sanitize what will be sent. Never send private catalogs, credentials, local private paths, or `!notes` contents.
2. Construct `{"request":"...","candidates":[{"id":"skill-name","description":"what it does and when it applies"}],"context":{}}` using an explicit shortlist. The chosen skill must be present in the destination agent's available skills.
3. If the user explicitly authorizes a one-shot remote trial, run `jev-skills decide skill --input INPUT.json --live`. An unflagged call is an offline dry-run; `--automatic` requires prior `jev-skills enable skill` plus an agent instruction. Private or follow-up requests must bypass the network.
4. Apply the chosen skill only after reading its full `SKILL.md` and checking its scope. If the result is `fallback`, `selected: null`, or inappropriate, use normal skill selection. Selection never grants permissions required by the selected skill.

Jev offers one advisory choice, not installation, execution, a complete skill ranking, or proof that a skill is helpful.
