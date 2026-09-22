---
name: jev-context-picker
description: Suggest the next one relevant context item from a small, already retrieved shortlist for a coding task.
---

# Next context item

Use this skill when the immediate question is which one known file, note, or search result to read next. Retrieve or shortlist candidates locally first. This release does not rerank a corpus or decide the entire reading order.

1. Give each item a stable ID and a short, non-sensitive description of why it might matter. Input: `{"request":"What should I read next to investigate ...?","candidates":[{"id":"src/module.py","description":"..."}],"context":{}}`.
2. Remove secrets, private paths and `!notes` content before any remote call. If the task is private, use local reasoning, not the network. An unflagged `jev-skills decide context --input INPUT.json` prepares an offline dry-run. Use `--live` only for a one-time explicitly authorized trial; `--automatic` requires `jev-skills enable context` and an agent instruction.
3. For `route: recommendation`, check that `selected` still exists and read it yourself. For `fallback`, `selected: null`, stale results, or poor candidate coverage, continue local retrieval. Do not treat the result as evidence of a file's contents.

The CLI recommends one next context item; it does not open files, publish a catalog, or verify the resulting analysis.
