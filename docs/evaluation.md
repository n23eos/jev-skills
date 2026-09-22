# First live evaluation

Run: 2026-09-22, direct TypeSafe API, pinned `jev-1.13.0`, 60% confidence threshold, 12-second per-case ceiling. [Raw report](../reports/live.json) preserves the exact synthetic inputs, candidate descriptions, probabilities, token usage and failures. [Compact machine-generated table](../reports/live.md) and [reproducible harness](../scripts/evaluate.py) are included.

## What happened

- 22 real API calls completed; 3 local bypass probes made no API call.
- 17 of 22 API outcomes matched the author-assigned expected outcome. Five fell back because confidence was below 60%. The 3 bypass probes also passed, making 20 of 25 fixture outcomes match overall.
- Before confidence gating, 21 of 22 raw choices matched their synthetic label. The remaining response chose `none` for an underspecified security-design request. This is not a measurement of real model quality, coding success, or production accuracy.
- 14 recommendations were returned, 3 explicit `none` answers fell back normally, and 5 uncertain answers fell back. The host should handle every fallback normally.
- Selection latency including curl startup and network for the 22 calls was 643-776 ms; median 698.5 ms. This run did not achieve the under-half-second claim in the original use-case idea. No zero-overhead claim is made.
- Reported usage: 11,745 input tokens and 1,612 output tokens. Estimated API charge: $0.00049329 at the [published Jev 1.13 rate](https://docs.typesafe.ai/models.md), not an invoice or a measurement of savings. Failed or unreported calls can make future estimates incomplete.

These are deliberately small, synthetic, author-labeled examples, not a held-out benchmark. Model candidates are fictional capability tiers; no claim is made that actual host models can perform the assigned jobs. The skill catalog contains this pack's seven skills, not a user's private catalog. The harness writes a report, not the CLI's usage log; `jev-skills status` tracks `decide` sessions separately.

## Model selection and local bypass

| Request | Expected | Jev picked | Confidence | Outcome |
| --- | --- | --- | ---: | --- |
| Fix a single typo in a comment. | tier-tiny | tier-tiny | 80% | recommendation |
| Summarize filenames from a supplied short list. | tier-tiny | tier-tiny | 59% | low_confidence |
| Add a bounded parsing helper with unit tests. | tier-everyday | tier-everyday | 85% | recommendation |
| Repair a known single-module validation bug. | tier-everyday | tier-everyday | 62% | recommendation |
| Diagnose a failure crossing a cache and queue. | tier-large | tier-large | 50% | low_confidence |
| Refactor three related modules while preserving behavior. | tier-large | tier-large | 41% | low_confidence |
| Resolve conflicting requirements for a security boundary. | tier-hardest | none | 50% | low_confidence |
| Review a high-impact ambiguous migration for data loss. | tier-hardest | tier-hardest | 72% | recommendation |
| Private synthetic request | bypass | not called | n/a | private |
| Yes, do that, but make it shorter. | bypass | not called | n/a | contextual_follow_up |
| Use the second one. | bypass | not called | n/a | contextual_follow_up |

## Skill selection

| Request | Expected | Jev picked | Confidence | Outcome |
| --- | --- | --- | ---: | --- |
| This typo fix is tiny; should I use the small or advanced host model? | jev-model-router | jev-model-router | 99% | recommendation |
| I found several installed aids. Which is relevant to changing a parser? | jev-skill-picker | jev-skill-picker | 53% | low_confidence |
| I have three likely files; which one should I read next? | jev-context-picker | jev-context-picker | 71% | recommendation |
| The parser changed. Which existing check is most informative to run first? | jev-test-prioritizer | jev-test-prioritizer | 88% | recommendation |
| Empty input now throws before rendering. Where should I investigate first? | jev-bug-triage | jev-bug-triage | 86% | recommendation |
| I wrote two feasible ways to fix this edge case. Which fits the constraints? | jev-plan-selector | jev-plan-selector | 88% | recommendation |
| Are remote automatic suggestions enabled, and how do I turn them off? | jev-controls | jev-controls | 82% | recommendation |
| Suggest a lunch recipe from available ingredients. | none | none | 99% | none_selected |
| Translate a fictional poem into another language. | none | none | 99% | none_selected |
| Calculate the area of a synthetic circle. | none | none | 92% | none_selected |

## Other bounded decisions

| Request | Expected | Jev picked | Confidence | Outcome |
| --- | --- | --- | ---: | --- |
| Pick the error parser description to inspect after a parse failure. | parser | parser | 91% | recommendation |
| Pick the parser unit test first after changing parsing. | unit-parser | unit-parser | 97% | recommendation |
| A synthetic parse exception occurs on empty input. Where to inspect first? | parser | parser | 99% | recommendation |
| Choose a minimal parser fix with a regression test. | local-fix | local-fix | 62% | recommendation |

## Misses and next experiments

All five non-matching outcomes are retained above. Four had the expected raw choice but insufficient confidence; one chose `none` for the security-design request. No threshold, expected label, or candidate description was changed after the run to make it pass.

- `model-02`, 59%: the tiny description only promised text edits, while the task asked for summarization. For a model actually capable of both, use a description such as: "Routine lookups, renames, small text edits and short summaries from supplied text; no multi-component reasoning." Verify the capability before using this rewrite.
- `model-05` and `model-06`, 50% and 41%: the boundary between coupled debugging and risky design is vague. A possible large-tier description is: "Multi-component debugging and behavior-preserving refactors with clear requirements and a test plan; escalate ambiguous security or data-loss decisions." It is only a candidate for a future evaluation.
- `model-07`, 50%: the request supplied no actual conflicting requirements. Add sanitized constraints and available evidence; choosing `none` may be more defensible than the synthetic hardest-tier label. Keep this mismatch visible.
- `skill-02`, 53%: a possible clearer skill-picker description is: "Select one relevant installed Agent Skill for a concrete task from its supplied catalog; do not perform the task or choose a coding model." Test this wording on new cases before adopting it.

The suggested rewrites have not been live-tested. Do not lower the confidence threshold solely to improve this table.

## Compatibility verification

The package builds and installs locally. Offline tests check copying all seven manifests into temporary Codex and Claude skill directories and refusing to overwrite an existing installation. Both host formats are documented, but this is not an end-to-end test of both agent applications executing the skills. This release does not install an automatic host hook, change a parent model, or dispatch helpers itself.
