---
name: jev-bug-triage
description: Suggest the first component to inspect for a bug from a finite set of plausible components.
---

# Bug triage

Use this skill to choose one initial inspection target after collecting symptoms and a small list of plausible components. It does not diagnose root cause or make code changes.

1. Include only observed, sanitized symptoms in `request` and `context`. List actual components, with descriptions, in `candidates`: `{"request":"Where should I inspect first for ...?","candidates":[{"id":"auth-parser","description":"Parses incoming tokens"}],"context":{"symptom":"..."}}`.
2. An unflagged `jev-skills decide bug --input INPUT.json` is an offline dry-run. `--live` requires a one-shot authorized network trial; `--automatic` requires `jev-skills enable bug` and an agent instruction. Keep private or follow-up reports offline.
3. Inspect the selected component only if `route: recommendation` and the ID is still valid. Verify a root cause from code and reproducible evidence before proposing or implementing a fix. On `fallback`, `selected: null`, poor coverage, or conflicting evidence, investigate normally.

The result is one hypothesis for where to start, not a causal finding, permission to edit, or a complete ranking.
