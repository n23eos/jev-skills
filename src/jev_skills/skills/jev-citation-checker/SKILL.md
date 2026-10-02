---
name: jev-citation-checker
description: Assess whether one supplied source excerpt supports, contradicts, or is insufficient for one claim.
---

# Citation checker

Use this skill after you already have one claim and one source excerpt. It judges only the supplied evidence. Exact quote matching happens locally, and a missing exact match does not prove fabrication.

1. In a fresh task-local temporary directory, start from the packaged shape: `jev-skills example citation > INPUT.json`.
2. Replace the fictional claim, source context, excerpt, and optional quote with reviewed material. Then preview offline: `jev-skills decide citation --input INPUT.json`.
3. Use `--live` only for an explicitly authorized network request. Automatic use also requires the workflow to be enabled and the host agent to opt in.
4. Accept only `supports`, `contradicts`, or `insufficient`. On fallback, missing source, low confidence, or stale evidence, assess the citation locally.

The result is advisory. It does not verify the full source, publish material, grant permission, or establish fabrication from an absent quote.
