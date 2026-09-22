# Bounded coding decisions

Each workflow accepts `{"request":"...","candidates":[{"id":"...","description":"..."}],"context":{}}` and returns at most one advisory candidate ID or a fallback. Build a relevant, sanitized shortlist first; an option missing from it cannot be selected. See `examples/` for input files and the [README](../README.md) for execution modes.

| Workflow and skill | What to submit | What selection means |
| --- | --- | --- |
| `model` / `jev-model-router` | Up to four actual host model IDs, ordered cheapest first, with verified capability differences and optional `size` metadata | One suggested model for a scoped task, not a switch of the running model |
| `skill` / `jev-skill-picker` | Shortlist of available Agent Skill names and sanitized descriptions | One skill to inspect and possibly invoke, not automatic execution |
| `context` / `jev-context-picker` | Already retrieved, plausible files or passages | One next item to read, not a corpus rerank or complete reading order |
| `tests` / `jev-test-prioritizer` | Real test targets from project instructions | One first target, not permission to omit mandatory checks |
| `bug` / `jev-bug-triage` | Components plausibly related to observed symptoms | One first place to inspect, not a confirmed root cause |
| `plan` / `jev-plan-selector` | A few feasible, prewritten plans that satisfy hard constraints | One plan to review, not generated architecture or approval to implement |

For example, after identifying a changed parser, submit the real parser unit suite and relevant integration suite as `tests` candidates. Review the suggestion, run the first test using the project's runner, and still run the project's mandatory checks. For `bug`, inspect the suggested component, gather reproducible evidence, and only then establish cause. For `plan`, filter out plans violating hard requirements before asking Jev to choose among the remaining alternatives.

For `model`, map available host models to at most four useful size choices (`tiny`, `everyday`, `large`, `hardest`) using the host's actual model IDs. Optional `size` is only for local usage counts, not a feature in the TypeSafe choice and not a substitute for a useful description. If the host supports delegation, give the selected model a bounded, authorized task and report the model actually used; otherwise use normal host behavior. Never say the parent conversation switched models.

These six initial uses adapt the general [intent-routing pattern](https://docs.typesafe.ai/patterns/intent-routing.md) to explicit candidates. The [reranking cookbook](https://docs.typesafe.ai/cookbooks/rerank_typesafe.md) performs per-query-candidate relevance scoring and measures dataset outcomes; this pack instead uses a bounded Choice for one next item. [Score](https://docs.typesafe.ai/primitives/score.md) and [composite scoring](https://docs.typesafe.ai/patterns/composite-scoring.md) may inform future ranking or multi-criterion designs but are not implemented here. Do not transfer accuracy figures from those examples to this pack.
