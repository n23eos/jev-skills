---
name: jev-eval-gap-picker
description: Suggest one evaluation gap to address next from supplied goals, evidence, coverage, and candidate gaps.
---

# Evaluation gap picker

Use this skill after documenting an evaluation goal, existing evidence, current coverage, and a finite list of real gaps. Keep synthetic evidence clearly identified.

1. In a fresh task-local temporary directory, start from the packaged shape: `jev-skills example eval-gap > INPUT.json`.
2. Replace the fictional evaluation data and gaps with reviewed non-sensitive material. Preview offline: `jev-skills decide eval-gap --input INPUT.json`.
3. Use `--live` only for an explicitly authorized network request. Automatic use also requires the workflow to be enabled and the host agent to opt in.
4. Treat the selection as prioritization only. Define and run an appropriate evaluation separately. On fallback, weak coverage, or stale evidence, prioritize locally.

The result does not create evidence, claim measured benefit, run an evaluation, skip required checks, or grant permission.
