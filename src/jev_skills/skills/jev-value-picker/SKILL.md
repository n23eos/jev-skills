---
name: jev-value-picker
description: Select one supplied parsed span and return its exact locally copied source value.
---

# Exact value picker

Use this skill when a parser has already produced exact spans from one source string and you need to choose one. Every supplied value must exactly equal its source slice.

1. In a fresh task-local temporary directory, start from the packaged shape: `jev-skills example value > INPUT.json`.
2. Replace the fictional source and spans while preserving exact start and end offsets. Preview offline: `jev-skills decide value --input INPUT.json`.
3. Use `--live` only for an explicitly authorized network request. Automatic use also requires the workflow to be enabled and the host agent to opt in.
4. For a recommendation, use only `selected_value.value`, which the host copies from the original local span. On fallback, mismatch, or stale source text, parse and choose locally.

The result does not generate, normalize, repair, submit, or authorize use of a new value.
