---
name: jev-issue-next-step
description: Suggest one next step for a supplied issue from its evidence, blockers, and finite action list.
---

# Issue next step

Use this skill when an issue has a known current state and several plausible next actions. Keep candidate actions within the issue's requested scope.

1. In a fresh task-local temporary directory, start from the packaged shape: `jev-skills example issue > INPUT.json`.
2. Replace the fictional issue, evidence, blockers, and actions with reviewed non-sensitive data. Preview offline: `jev-skills decide issue --input INPUT.json`.
3. Use `--live` only for an explicitly authorized network request. Automatic use also requires the workflow to be enabled and the host agent to opt in.
4. Recheck the selected action against current issue state before doing it. On fallback, missing evidence, or changed blockers, decide locally.

The result does not change issue state, assign work, send messages, expand scope, or grant permission.
