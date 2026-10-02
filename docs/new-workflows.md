# Useful next decisions

Version 0.3 adds seven advisory workflows. Use them when the next choice is ambiguous and resolving it matters. A clear project rule, simple exact lookup or an obvious action should stay local. Ask the installed skill to gather and sanitize the input. `jev-skills example WORKFLOW` prints a packaged public example, so installation does not require a checkout or hand-authored JSON.

| Workflow | Skill | What the agent should verify afterwards |
| --- | --- | --- |
| citation | jev-citation-checker | The original source passage, its version and scope; a selection is not proof |
| ci | jev-ci-triage | The selected diagnostic against logs and a reproduction; no unsupported flaky classification |
| review | jev-review-comment-triage | Whether the alleged issue exists before editing or responding |
| tool | jev-tool-picker | Tool is still available and read-only; no arguments or execution authorization are inferred |
| issue | jev-issue-next-step | Whether local inspection can answer the missing question before asking the reporter |
| value | jev-value-picker | The copied original span has the requested role; no arithmetic or invented value |
| eval-gap | jev-eval-gap-picker | Observed versus expected behavior and existing coverage before creating an evaluation |

The prepared payload is shown by `decide` without flags. `--private` bypasses even input reading. Network decisions require `--live`, or an enabled workflow with `--automatic` and an agent instruction. No new workflow launches tools, changes code, labels issues, replies to reviews or grants permission. Existing model helpers remain separately explicit.

## Why these choices

Citation uses the relation between one claim and supplied source evidence, rather than retrieving context. CI concerns the next diagnostic action rather than selecting a suspect component. Review concerns one comment, not choosing a reviewer skill. Issue concerns missing evidence, not root cause. Tool selects a concrete available capability, not an instruction file. Value chooses an original span, not generated text. Evaluation gap selects a new coverage need, not an existing runnable test. Keep the workflows separate only where these distinctions help users.

Technical patterns were researched in primary examples: [TypeSafe citation checking](https://docs.typesafe.ai/cookbooks/citation_check), [preparsed extraction](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook), [function choice](https://docs.typesafe.ai/cookbooks/function_calling), [GitHub CI troubleshooting](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows), [GitHub issue triage](https://github.com/githubnext/agentics/blob/main/workflows/issue-triage.md) and [Anthropic agent evaluations](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents). These demonstrate patterns, not our package's accuracy or user demand.

## What usefulness means

Offline tests check bounded input, source/evidence handling, exact copied values, abstention, privacy, and safe installation. Controlled provider responses check transport integration; they do not measure semantic accuracy. Public examples are examples, not a benchmark.

Before claiming improvement, gather independently labelled public tasks, including absent answers, conflicting evidence and ambiguous cases. Split development and held-out cases. Compare with the host's ordinary judgment and a simple deterministic rule, retaining failures and abstentions. Measure the full task outcome, total elapsed time and all provider calls, not only successful decisions. Do not send private CI logs, reviews, issue text or catalogs without the corresponding opt-in and sanitization.

For citation, count false confirmations and overlooked contradictions. For CI, measure time to a verified diagnosis and avoid code edits caused by infrastructure failures. For review, track dismissed true defects and unnecessary edits. For tool, count wrong first calls and extra calls. For issue, count unnecessary questions and whether a reproduction becomes possible. For value, measure exact-span correctness and absence abstention. For evaluation gap, measure newly caught regression classes per preparation effort. Missing real captures remain unmeasured.
