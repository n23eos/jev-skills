# Jev Skills

Seven portable Agent Skills and a small Python CLI for optional, advisory decisions in coding workflows. They can suggest one model, installed skill, next context item, first test target, first bug-inspection component, or prewritten plan. `jev-controls` explains opt-in settings and installation. The agent remains responsible for evidence, permissions, execution, and project-required checks.

Use this when you already have a small, meaningful shortlist and choosing the next step requires judgment. Skip it when the answer is obvious, the request is private or a contextual follow-up, or a project rule already determines the next step. These skills do not prove better decisions, lower cost, or faster work; evaluate them on your own tasks before adopting automatic use.

Jev is a [TypeSafe System One model](https://docs.typesafe.ai/introduction/coding-agents.md), not the conversational model behind Codex or Claude Code. Installing these skills does not replace that model, and a model recommendation does not switch an existing conversation.

## Install

Prerequisites: Python 3.10 or newer, `git`, and `curl`. Install the CLI in your chosen Python environment from a clone:

```sh
git clone https://github.com/n23eos/jev-skills.git
cd jev-skills
python3 -m pip install .
jev-skills install --agent codex
# Or: jev-skills install --agent claude
```

The installer copies only the skill files. By default, it targets `.agents/skills` or `.claude/skills` in the user's home directory. To target a different agent skills directory, pass `--dest DIRECTORY`. Keep the installed CLI available on `PATH` when using the skills. See [compatibility](docs/compatibility.md) for discovery and invocation differences.

## One decision

Use a JSON file with a task request, a finite set of candidates, and optional JSON context. Candidate IDs should be stable and descriptions should explain distinctions relevant to the task. For `model`, candidates may also have a `size` (`tiny`, `everyday`, `large`, or `hardest`) for local usage accounting. Other candidate fields are not used for selection.

```json
{
  "request": "Which existing suite should I run first for a changed login parser?",
  "candidates": [
    {"id": "auth-unit", "description": "Fast parser and authentication unit tests"},
    {"id": "login-integration", "description": "Login endpoint integration tests"}
  ],
  "context": {"change": "Token parsing behavior"}
}
```

```sh
jev-skills decide tests --input examples/tests.json
jev-skills decide tests --input examples/tests.json --live
```

The first command is an offline dry-run. It prints `mode: dry_run`, `network: false`, and the request payload(s) it would send; it has no recommendation. `--live` starts an explicit one-shot HTTPS decision session and requires `TYPESAFE_API_KEY` in the environment. Do not put the key in an input file or a CLI argument. The CLI does not run the chosen test. See the [six bounded uses](docs/use-cases.md) and `examples/` for synthetic inputs. The model example uses fictional IDs; replace them with actual host model IDs before a real model decision.

An attempted live or enabled automatic selection reports `route` (`recommendation` or `fallback`), `selected` (an input ID or `null`), `confidence`, and `usage`/`calls` accounting. Immediate local fallbacks may have fewer fields. A fallback means the agent should continue with its normal process. Neither a recommendation nor a confidence value proves correctness. In particular, a selected first test never replaces other mandatory tests. `--timeout SECONDS` limits a decision session; failures and timeouts fall back. The available workflows are `model`, `skill`, `context`, `tests`, `bug`, and `plan`.

## Network and control

Every automatic workflow is off by default. The following only changes local CLI settings; it does not add a hook to an agent:

```sh
jev-skills status
jev-skills enable tests
jev-skills decide tests --input examples/tests.json --automatic
jev-skills disable tests
```

`enable WORKFLOW|all` and `disable WORKFLOW|all` control the workflows; malformed settings stay off. `--automatic` contacts TypeSafe only for an enabled workflow. An agent must also receive an explicit instruction in its AGENTS.md or CLAUDE.md to prepare a sanitized input and call the CLI at an appropriate decision point. Merely installing a skill or enabling a workflow does not cause invocation. Manual invocation of an installed skill is supported with `$jev-test-prioritizer` in Codex and `/jev-test-prioritizer` in Claude Code, subject to that host's skill discovery.

For model routing, provide up to four actual host model IDs, mapped to the useful sizes `tiny`, `everyday`, `large`, and `hardest`. A suggestion is not a model switch; any delegation must use a mechanism that host supports, within the task's existing permissions. The helper should report the model actually used. `jev-skills status` summarizes usage and reports size-tagged suggestions in `recommendations_by_model_size`. It does not retain candidate IDs or request text.

Use `--private` for sensitive requests and `--follow-up` for contextual follow-ups; both bypass the network. Independently review and sanitize every input before any `--live` or enabled `--automatic` call. Local `jev-skills catalog --root DIRECTORY --output catalog.json` inventories skill metadata, including paths; the manifest is not uploaded by that command. Review it before extracting a shortlist for a request. Never send credentials, internal notes, private paths, or proprietary catalogs. Live calls go directly to TypeSafe, not through OpenRouter; see [Security and privacy](SECURITY.md).

TypeSafe Choice supports at most 255 options; this CLI reserves one for `none`, leaving 254 candidates per question. Large sets are handled in bounded groups with a final comparison, subject to the total deadline and conservative fallback. The decision does not execute recommendations. [Current TypeSafe model documentation](https://docs.typesafe.ai/models.md) lists `jev-1.13.0` at $0.042 per million input tokens, with output tokens free. Treat this as a published rate, not a bill or a savings claim; check current terms before use. Account for all requests, including intermediate group calls and failures.

## Development

The [first live evaluation](docs/evaluation.md) contains 22 real API calls plus 3 local bypass probes. Five API decisions fell back below 60% confidence; all failures and raw choices are published. These are synthetic examples, not a production benchmark. A short [launch draft](docs/launch.md) is also available.

Run network-free checks with the project's test runner:

```sh
python3 -m unittest discover -s tests -v
```

The synthetic live evaluation is opt-in, sends its labeled inputs to TypeSafe, and records raw decisions and failures:

```sh
python3 scripts/evaluate.py --live --output reports/live.json
```

Do not mistake synthetic evaluation outcomes for production accuracy, latency, or cost savings. See [compatibility and limits](docs/compatibility.md) and [use cases](docs/use-cases.md).
