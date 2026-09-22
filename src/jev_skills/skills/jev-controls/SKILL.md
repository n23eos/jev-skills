---
name: jev-controls
description: Inspect and change opt-in Jev workflow settings or install the portable Jev Agent Skills when requested.
---

# Jev controls

Use this skill when the user wants to inspect status, enable or disable automatic network decisions, or install the portable skill files. Installation and automatic calls are separate choices.

- `jev-skills status` shows workflow settings. `jev-skills enable WORKFLOW` opts in a single workflow; `jev-skills disable WORKFLOW` turns it off. `all` is supported as a target. Workflows are off by default. Check the intended workflow and explain network implications before enabling it.
- `jev-skills doctor` checks the local CLI dependencies, key presence (never its value), host binaries, installed files, and settings without network requests. Use it first for setup problems. The key must be in the agent process environment, not pasted into chat.
- `jev-skills install --agent codex` or `jev-skills install --agent claude` installs skill files. The CLI must first be installed, preferably with `uv tool install 'git+https://github.com/n23eos/jev-skills.git'`. `--dest DIRECTORY` changes the skills directory. Repeated identical installs are safe; `--upgrade` replaces only verified unmodified owned files and retains backups. Never delete a conflicting user-edited skill to force installation.
- `jev-skills catalog --root DIRECTORY --output catalog.json` creates a local manifest. Review and sanitize it before using any names or descriptions in a network request. Do not publish private catalogs.
- `jev-skills decide WORKFLOW --input INPUT.json` is an offline dry-run; add `--live` for an explicitly authorized one-shot network request, or `--automatic` to respect enabled workflow settings. Keep private and follow-up inputs offline with `--private` or `--follow-up`.

For requested project integration, use `jev-skills integrate --agent HOST --project PROJECT --root REVIEWED_SKILL_ROOT --reviewed-catalog`. This adds a managed instruction block without enabling anything. Explain that this is instruction-based behavior, not a guaranteed runtime hook. Enabling alone does not invoke Jev. Keep all workflows off unless the user asks to enable them. Never change global agent configuration as a side effect.

Say plainly: live requests go directly to TypeSafe, not OpenRouter; tasks and candidate descriptions leave the machine. Private work stays off. The CLI cannot grant permission or switch the current conversation's model. The separate `route-model --execute` option requires explicit helper execution intent and may incur host provider usage.
