---
name: jev-skill-picker
description: Pick a relevant installed coding skill with Jev, then read it and hand the task back to the current agent.
---

# Skill selection

Use this skill when several discovered Agent Skills plausibly fit the user's request. Do not search for, install, or invoke a skill as a side effect of the recommendation.

1. Run `jev-skills doctor` if setup is uncertain. If the CLI or key is missing, explain the relevant setup step and continue normal work. Never ask the user to paste a key into chat.
2. Identify the host's actual installed skill roots. Preview with `jev-skills pick-skill --request-file - --root SKILLS_DIRECTORY` and send the current standalone task on stdin. Add more `--root` arguments if necessary. Review names and descriptions for private material; use `--exclude NAME` for unsuitable skills. Do not scan private notes or assume every local skill is available in this host.
3. For an authorized one-shot trial, repeat with `--live --reviewed-catalog --agent codex` or `--agent claude`. That acknowledgement is only valid after review. Only IDs and descriptions are sent with the task; paths and bodies remain local. Without network flags this is an offline preview. `--automatic` honors the skill toggle. Private requests and contextual replies stay with the current agent without a live call.
4. On a recommendation, check `selected_skill.path` against the host's available skills, then read its complete `SKILL.md` and required references before applying it. `--show-skill` can include the locally verified file body. Tell the user the selected skill and reported confidence in one short line. On fallback or an inappropriate choice, use normal skill selection. The picker excludes itself to avoid recursion. A selection never grants permissions required by the selected skill.

Do this preparation for the user; do not make them build a JSON catalog. An empty catalog means no eligible installed skill, not an invitation to invent or install one without permission. Explicit user-selected skills and mandatory host skill rules take precedence.

Jev offers one advisory choice, not installation, execution, a complete skill ranking, or proof that a skill is helpful.
