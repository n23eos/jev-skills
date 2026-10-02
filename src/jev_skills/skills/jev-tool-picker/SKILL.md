---
name: jev-tool-picker
description: Suggest one available read-only tool from supplied capability summaries without generating arguments or executing it.
---

# Read-only tool picker

Use this skill only after the host has identified available tools and their reviewed read-only capabilities. Tools that are unavailable or not explicitly read-only are excluded locally.

1. In a fresh task-local temporary directory, start from the packaged shape: `jev-skills example tool > INPUT.json`.
2. Replace the request and capability lists. Do not add arguments, commands, credentials, or tool output. Preview offline: `jev-skills decide tool --input INPUT.json`.
3. Use `--live` only for an explicitly authorized network request. Automatic use also requires the workflow to be enabled and the host agent to opt in.
4. A recommendation contains only a supplied tool ID. The host must review and separately invoke any tool. On fallback or changed availability, choose locally.

The result does not create arguments, execute a tool, authorize writes, expose credentials, or grant permission.
