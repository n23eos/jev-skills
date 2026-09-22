# Compatibility and boundaries

The seven `SKILL.md` entrypoints use the portable Agent Skills layout. The CLI uses Python 3.10+ standard-library code and the `curl` executable. Install the package from the repository clone with `python3 -m pip install .`; copying skill directories alone does not install the `jev-skills` command.

`jev-skills install --agent codex` copies skills into the user's `.agents/skills` directory; `--agent claude` copies them into `.claude/skills`. `--dest DIRECTORY` overrides the directory. Identical managed installations are idempotent. `--upgrade` verifies ownership, preserves local modifications by refusing conflicts, and retains a backup. The exact published v0.1 files are also recognized for migration with `--upgrade`; other untracked files require an exact current-package match. Host versions differ in discovery; restart or refresh the host if new skills are not visible. In Codex, invoke `$skill-name`; in Claude Code, use `/skill-name`. Skill instructions do not inject a runtime hook, alter the current model, or guarantee automatic loading.

For repeated use, opt in twice: `jev-skills enable WORKFLOW` in the CLI and an explicit instruction in your own AGENTS.md or CLAUDE.md to invoke `jev-skills decide WORKFLOW --input INPUT.json --automatic` at the specific decision point. Do not copy unreviewed request text into a live call. All workflows start off, and invalid settings remain off. `jev-skills status` displays their state; `jev-skills disable WORKFLOW` stops an enabled workflow. `all` is accepted by enable/disable. There is no automatic hook installed by this repository.

An optional host instruction can be scoped like this; adapt it to your actual workflows and host mechanisms:

> For a new, non-private task with a bounded shortlist, you may prepare a sanitized JSON input and call `jev-skills decide WORKFLOW --input INPUT.json --automatic` once if that workflow is enabled. Do not send private data or contextual follow-ups. On disabled, missing CLI/key, timeout, `none`, or fallback, continue normal agent work. Never let a recommendation override project rules, mandatory tests, permissions, or user choices. If a model is suggested, use only a host-supported delegation mechanism for a scoped, authorized task; do not claim the current agent's model changed.

`jev-skills decide WORKFLOW --input INPUT.json` is an offline dry-run that emits the proposed payload(s), not a selection. `--live` explicitly makes one live decision session; it can contain more than one API request for grouped candidates. `--automatic` honors per-workflow settings. `--private` and `--follow-up` bypass live selection without reading the input file. The runtime reads credentials only from externally supplied `TYPESAFE_API_KEY`; local settings live under `JEV_SKILLS_HOME` or the user's `~/.config/jev-skills`. Never commit the key or local settings.

The API requires text-based state and a finite Choice. We reserve an option for `none`, validate IDs and returned answers, limit each Choice to 254 candidates plus `none`, and gate larger shortlists through bounded groups. A total deadline and API errors can prevent a final recommendation. In those cases, invalid or low-confidence answers, and `none`, the output is a fallback. Check `usage` and `calls` for actual request accounting; do not infer a bill or a performance improvement from a single run. Confidence describes the answer distribution, not ground-truth correctness, user consent, or authority to execute.

Decisions are advisory. The CLI never runs a selected test or skill, edits a bug, or implements a plan. The separate `route-model --execute` opt-in can run a supplied-text helper in an isolated temporary working directory through an installed host CLI. It is not a repository-editing agent. Codex uses read-only/no-approval mode with tool features and skill discovery disabled; Claude uses safe mode with built-in and MCP tools disabled. The installed host and administrator policies remain trusted. Older hosts that reject flags fall back; do not remove safety flags to make them work. Helpers currently require POSIX, whereas the selectors and skill files do not require that runner.

The agent must independently check availability, scope, evidence, and project instructions. Mandatory tests and approvals still apply. Catalog outputs can contain private local paths: review metadata before network use and do not publish private outputs. `pick-skill` separates local paths/bodies from the transmitted candidates. `integrate` provides an explicit managed project instruction block, not a guaranteed hook. The project does not promise support for every host-specific automation mechanism, unseen skill, or production-domain accuracy.

| Capability | Codex | Claude Code |
| --- | --- | --- |
| Install all seven portable skills | `--agent codex` | `--agent claude` |
| Manual skill invocation | `$jev-...` | `/jev-...` |
| Managed project instructions | AGENTS.md | CLAUDE.md |
| Separate supplied-text helper | `codex exec`, compatible CLI required | `claude --print`, compatible CLI required |
| Switch the current chat model | No | No |
| Confirm serving model in helper result | Not supplied by current JSONL | Available if one model is reported in modelUsage |
| Guaranteed interception of all messages | No | No |

See [v0.2 verification](verification-v0.2.md) for what was actually exercised, including limitations. Manifest compatibility alone is not a native-host end-to-end test.

This design adapts TypeSafe's [intent routing](https://docs.typesafe.ai/patterns/intent-routing.md) and [Choice primitive](https://docs.typesafe.ai/primitives/choice.md). Its initial context and test choices are narrower than the [reranking cookbook](https://docs.typesafe.ai/cookbooks/rerank_typesafe.md), which scores query-candidate pairs. [Score](https://docs.typesafe.ai/primitives/score.md) and [composite scoring](https://docs.typesafe.ai/patterns/composite-scoring.md) describe potential richer approaches, not implementations in this release.
