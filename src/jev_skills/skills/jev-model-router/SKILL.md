---
name: jev-model-router
description: Suggest one host-provided coding model for a bounded task when several available models differ in cost and capability.
---

# Model routing

Use this skill when the user wants help choosing a model for a specific coding task. Jev does not replace the model powering this conversation or switch an existing agent session.

1. List only models actually available in the destination host. Map up to four useful choices to `tiny`, `everyday`, `large`, and `hardest` using verified host capabilities and cost information. Use exact host model IDs, order candidates cheapest/smallest first, and describe task-relevant capability differences. Do not hardcode or invent model IDs, availability, prices, or size assignments.
2. Put the bounded task in `request` and non-sensitive constraints in `context`. Remove credentials, private notes, and unnecessary code. Input: `{"request":"...","candidates":[{"id":"actual-host-model-id","description":"verified capability for this task","size":"everyday"}],"context":{}}`. The `size` field is optional local usage metadata, not part of the Jev question; use only the four size labels above.
3. For a one-time authorized network trial, run `jev-skills decide model --input INPUT.json --live`. Without `--live`, it is an offline dry-run. `--automatic` works only if this workflow was explicitly enabled with `jev-skills enable model` and the agent was instructed to invoke it. Do not use either network mode for private or follow-up requests.
4. Treat `route: recommendation` and `selected` as advice, then verify the chosen host model is still available and appropriate. Delegate only a scoped, authorized task through a mechanism the host actually supports. If delegation occurs, have the helper's final report state the actual model used, not merely the suggested model. For `fallback`, `selected: null`, or uncertainty, choose with normal judgment or ask for a material missing constraint. Never claim that running this command changed the current model.

The CLI never launches a model or changes agent settings. Its confidence is not a guarantee of correctness, permission, or measured cost savings.
