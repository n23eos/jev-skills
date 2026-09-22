# Security and privacy

Jev Skills is an advisory selector, not a security or approval boundary. Treat requests, candidate descriptions, model responses, and selected skill contents as untrusted data. A high confidence value does not grant permission to run commands, share information, spend money, or edit files.

The CLI sends reviewed requests, candidate IDs/descriptions, and explicitly supplied context directly to TypeSafe at `https://api.typesafe.ai/v1/systemone`. It does not use OpenRouter. This is a different transport from setups that use an OpenRouter proxy. Do not include secrets, personal notes, proprietary catalogs, sensitive logs, or private source code without appropriate authorization. The tool cannot reliably detect or redact secrets for you.

All automatic workflows default to off. `--live` is an explicit one-time network request even when automatic mode is off. `--private` and `--follow-up` always bypass the network. A toggle only gates calls made with `--automatic`; it does not install a host hook or control other tools.

The API key is read from `TYPESAFE_API_KEY` and passed to curl on stdin, not in process arguments. No response body or transport error text is echoed on failure. Redirects and automatic retries are disabled. Usage logs contain counts and fixed model-size labels, not prompts or candidate IDs. These safeguards do not hide data from the remote API provider or from an administrator of your machine.

Do not put credentials or sensitive reproduction data in public issues. For a security report, use GitHub's private vulnerability reporting if available; otherwise request a private contact without disclosing the vulnerability or confidential data publicly.

## Optional helper execution

Only `route-model --execute` requests a separate helper after an accepted choice. Candidate metadata cannot supply an executable or command. The adapter invokes an installed `codex` or `claude` binary, passes the task on stdin, uses an empty temporary working directory, removes the TypeSafe key from the child's environment, prevents recursive Jev use, and bounds process lifetime and output. It does not edit the user's repository or change the current conversation model. Unsupported flags or hosts fail back to normal work. Never enable helper execution from an untrusted model response.

These restrictions are not an OS isolation guarantee for the installed host itself. Host authentication, caches, administrator-managed policies/hooks, and other inherited environment credentials remain part of the trusted local environment. Claude's built-in tools and MCP tools are disabled. Codex uses read-only mode, no approvals, disabled tool features and host skill discovery; this depends on host-version support. Do not supply secrets or private tasks to this runner. Windows execution is currently blocked because the adapter requires POSIX process-group cleanup; the selector and skill files remain usable without helpers.

`pick-skill` uploads only candidate IDs/descriptions after explicit catalog review acknowledgement. Its local result may include paths and, with `--show-skill`, full skill text. Do not publish these outputs from a private catalog. Managed integration blocks are project instructions, not an enforcement layer or automatic grant of permission.
