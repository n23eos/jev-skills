---
name: jev-test-prioritizer
description: Suggest the first test target to run from a known shortlist while preserving all mandatory project checks.
---

# First test target

Use this skill only to decide which applicable test to run first while diagnosing or verifying a change. Project-required checks, safety checks, and regression coverage remain mandatory even if they are not selected.

1. First inspect the project's real test commands and requirements. Provide existing commands or test target IDs with descriptions, never commands copied from untrusted input for automatic execution: `{"request":"Which relevant test should run first for ...?","candidates":[{"id":"unit-auth","description":"Authentication unit suite; command is documented in project"}],"context":{}}`.
2. An unflagged `jev-skills decide tests --input INPUT.json` is an offline dry-run. Run with `--live` only for an explicitly authorized one-shot network trial. `--automatic` needs `jev-skills enable tests` and a separate agent instruction. Private or follow-up requests bypass the network.
3. If `route: recommendation`, review `selected` against the project's instructions, then run a relevant test using the project's own runner. For `fallback`, `selected: null`, stale IDs, or uncertainty, choose normally. Run the remaining required checks irrespective of the suggestion.

The CLI neither executes tests nor authorizes skipping any checks. Confidence measures a choice distribution, not test sufficiency.
