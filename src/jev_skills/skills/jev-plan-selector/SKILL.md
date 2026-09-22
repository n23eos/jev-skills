---
name: jev-plan-selector
description: Suggest one prewritten implementation plan among a few feasible alternatives under explicit task constraints.
---

# Plan selection

Use this skill only after an agent or user has written a small set of feasible plans. Jev does not generate a plan, evaluate every architectural dimension, or override the user's design choice.

1. Make each candidate a distinct prewritten plan with a stable ID and a concise description of its steps and tradeoffs. Include scope, constraints, and acceptance criteria in `request` or `context`: `{"request":"Select a feasible plan for ...","candidates":[{"id":"local-adapter","description":"..."}],"context":{"constraints":["..."]}}`.
2. Exclude plans violating hard constraints before asking for a choice. Sanitize the input. An unflagged `jev-skills decide plan --input INPUT.json` is an offline dry-run. For a one-time authorized network trial use `--live`; `--automatic` requires `jev-skills enable plan` and a separate agent instruction. Keep private or follow-up planning offline.
3. If `route: recommendation`, review `selected` against the actual code and requirements before implementation. If `fallback`, `selected: null`, or important architecture is unresolved, use normal planning and seek the required human decision.

This CLI does not execute, approve, or validate a plan. Confidence is not correctness or authority.
