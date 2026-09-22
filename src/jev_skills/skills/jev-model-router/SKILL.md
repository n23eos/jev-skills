---
name: jev-model-router
description: Suggest one host-provided coding model for a bounded task when several available models differ in cost and capability.
---

# Model routing

Use this skill when the user wants help choosing a model for a specific coding task. Jev does not replace the model powering this conversation or switch an existing agent session.

1. List only models actually available in the destination host. Map up to four useful choices to `tiny`, `everyday`, `large`, and `hardest` using verified host capabilities and cost information. Use exact host model IDs, order candidates cheapest/smallest first, and describe task-relevant capability differences. Do not hardcode or invent model IDs, availability, prices, or size assignments.
2. Prepare a reusable local profile for the user: `{"agent":"codex","models":[{"id":"actual-host-model-id","description":"verified capability for this task","size":"everyday"}]}`. Use `claude` for Claude Code. Support one to four models; never require the user to repeatedly assemble JSON. Remove credentials and private notes from the task. Use the four size labels above only when justified.
3. For a one-time authorized network trial, run `jev-skills route-model --profile PROFILE.json --request-file - --live`, supplying the bounded task on stdin. Without `--live`, it is an offline dry-run. `--automatic` works only if the model workflow was enabled and project instructions request it. Never use network modes for private or contextual follow-up requests.
4. Treat `route: recommendation` and `selected` as advice, then verify the chosen host model is still available and appropriate. Delegate only a scoped, authorized task through a mechanism the host actually supports. If delegation occurs, have the helper's final report state the actual model used, not merely the suggested model. For `fallback`, `selected: null`, or uncertainty, choose with normal judgment or ask for a material missing constraint. Never claim that running this command changed the current model.

For an explicitly authorized helper execution, add `--execute` to `route-model`. This starts a separate authenticated host CLI in a temporary directory with conservative tool restrictions, not a repository-editing agent. Pass all necessary non-sensitive text in the request. Return the helper answer to the user only after reviewing it; apply suggested code through the parent agent's normal permissions. Unsupported hosts or errors fall back to normal work. Do not recursively call Jev from a helper (`JEV_SKILLS_CHILD=1`).

End a delegated answer with the reported model if available. Otherwise say `Requested model: ID; serving model not reported by host.` Never turn a requested ID into a verified claim. Helper usage is separate from Jev selection cost. Confidence is not a correctness guarantee, permission, or measured savings.
