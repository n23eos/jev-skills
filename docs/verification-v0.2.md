# Version 0.2 verification

Checked on 2026-09-22. These are development checks and public synthetic tasks, not production accuracy or savings claims.

## Installation and first use

- Built and installed version 0.2.0 into a fresh uv tool environment from the local source tree, outside the developer's existing CLI environment.
- Installed all seven skill files into separate temporary Codex and Claude destinations. Repeated Codex installation returned `unchanged`.
- Ran the installed `doctor`: all seven files matched their ownership manifest, the CLI was on PATH, and every automatic workflow was off. Missing TypeSafe key was correctly reported without exposing a value.
- Recreated the published v0.1 skill files from Git and upgraded them through the newly packaged CLI; migration returned `migrated_from: 0.1.0` and retained the original files in a backup.
- All 100 offline tests passed on Python 3.10 and 3.14; compileall and diff validation passed.
- After publication, the exact README GitHub installation command fetched v0.2 into another fresh uv environment and installed both host formats. [CI run 35727752669](https://github.com/n23eos/jev-skills/actions/runs/35727752669) passed on Python 3.10 and 3.13, including installed-command checks.
- Offline regressions exercise catalog-to-local-file handoff, explicit model execution, disabled/private/follow-up bypass before reads, catalog review, installation rollback, edited-file protection, profile validation, and managed project instructions.

These checks confirm packaging and installation layout. They are not an end-to-end test of native skill discovery in every Codex Desktop or Claude Code version. Restart the host, invoke the skill explicitly, and use `doctor` if it is unavailable.

## Real requests and helper boundary

The real `pick-skill` CLI scanned a temporary three-skill public catalog, chose `python-review` with reported confidence 1.0, and read the selected file locally. The next real model-routing request had confidence 0.58 and correctly fell back without launching a helper. That failure is retained in [the workflow report](../reports/workflow-codex-v0.2.json); the threshold was not weakened to make the demo pass.

Separately, the actual Codex 0.154.0 helper adapter completed the public task `Return exactly JEV_HELPER_OK` using requested model `gpt-5.6-luna`. Output was `JEV_HELPER_OK`; host-reported usage was 16,314 input tokens, 9 output tokens, and 4,864 cached input tokens. The [captured result](../reports/helper-codex-v0.2.json) preserves these fields. The serving model and monetary cost were not reported by Codex JSONL. This is evidence of a working supplied-text adapter, not low overhead or cost savings. The complete accepted-choice-to-helper CLI connection is covered offline with controlled responses; the live combined trial above abstained.

Claude Code 2.1.252 was present and accepted the adapter's flags, but its read-only authentication status was `loggedIn: false`. No successful Claude model execution is claimed. The adapter now reports `host_authentication_required` before trying a model call. Authenticate with the host's normal process; the skills themselves can still be installed.

Reproduce the combined smoke with an actual available model and explicit consent to both providers' usage:

```sh
python3 scripts/smoke_workflows.py --live --agent codex --model YOUR_AVAILABLE_MODEL_ID --output reports/my-smoke.json
```

It creates only temporary public skill fixtures. It sends no personal catalog and leaves automatic workflows off. A low-confidence route may legitimately stop before the helper.

## Larger catalog comparison

[Public fixture](../examples/catalog-eval.json): 30 synthetic functional coding skills and 33 pre-labeled tasks, including ambiguous tasks, four no-match tasks, and three contextual replies. All labels were set before the live run. This does not benchmark native Claude/Codex skill selection.

| Measure | Lexical overlap baseline | Jev |
| --- | --- | --- |
| Eligible task choices matching labels | 25 / 30 | 30 / 30 |
| All outcomes including local contextual bypasses | 28 / 33 | 33 / 33 |
| Network calls | 0 | 30 |

Jev accounting: 36,820 input tokens, 8,903 output tokens, estimated known selection cost $0.00154644 at the documented rate. No unaccounted calls. This excludes helper costs, developer time, and future pricing changes. The simple lexical baseline is deliberately reproducible; beating it on this authored set does not establish superiority over a capable coding agent.

Full raw choices, confidence, latency, labels, and accounting are in [catalog-v0.2.json](../reports/catalog-v0.2.json). The earlier [v0.1 results](evaluation.md), including misses and abstentions, remain published.

```sh
python3 scripts/evaluate_catalog.py
# Explicit network evaluation, writing a new report:
python3 scripts/evaluate_catalog.py --live --output reports/my-catalog-run.json
```
