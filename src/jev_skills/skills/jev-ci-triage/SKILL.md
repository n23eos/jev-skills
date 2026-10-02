---
name: jev-ci-triage
description: Suggest one next diagnostic for a supplied CI failure without claiming a root cause.
---

# CI triage

Use this skill when a CI failure is observed and the immediate question is what diagnostic to perform next. Record observations, not conclusions.

1. In a fresh task-local temporary directory, start from the packaged shape: `jev-skills example ci > INPUT.json`.
2. Replace the fictional summary and evidence with sanitized observations. Include repeated-run evidence only when those runs actually occurred. Preview offline: `jev-skills decide ci --input INPUT.json`.
3. Use `--live` only for an explicitly authorized network request. Automatic use also requires the workflow to be enabled and the host agent to opt in.
4. Treat a recommendation as one next diagnostic. Verify the failure yourself and run every mandatory project check. On fallback or stale evidence, continue local triage.

The result does not diagnose root cause, declare a failure flaky, execute a command, skip tests, or grant permission.
