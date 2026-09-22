---
name: jev-controls
description: Inspect and change opt-in Jev workflow settings or install the portable Jev Agent Skills when requested.
---

# Jev controls

Use this skill when the user wants to inspect status, enable or disable automatic network decisions, or install the portable skill files. Installation and automatic calls are separate choices.

- `jev-skills status` shows workflow settings. `jev-skills enable WORKFLOW` opts in a single workflow; `jev-skills disable WORKFLOW` turns it off. `all` is supported as a target. Workflows are off by default. Check the intended workflow and explain network implications before enabling it.
- `jev-skills install --agent codex` or `jev-skills install --agent claude` copies only skill data into the agent's default user skill directory. `--dest DIRECTORY` chooses another skills directory. The CLI itself must already be installed with `python3 -m pip install .` from this project's clone. Do not treat copied skills as a CLI installation.
- `jev-skills catalog --root DIRECTORY --output catalog.json` creates a local manifest. Review and sanitize it before using any names or descriptions in a network request. Do not publish private catalogs.
- `jev-skills decide WORKFLOW --input INPUT.json` is an offline dry-run; add `--live` for an explicitly authorized one-shot network request, or `--automatic` to respect enabled workflow settings. Keep private and follow-up inputs offline with `--private` or `--follow-up`.

Enabling does not add an AGENTS.md/CLAUDE.md hook or cause the agent to invoke the CLI automatically. An explicit agent instruction is also needed. The CLI cannot grant permission, execute a suggestion, change the current agent model, or guarantee a correct choice.
