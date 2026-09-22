# Security and privacy

Jev Skills is an advisory selector, not a security or approval boundary. Treat requests, candidate descriptions, model responses, and selected skill contents as untrusted data. A high confidence value does not grant permission to run commands, share information, spend money, or edit files.

The CLI sends reviewed requests, candidate IDs/descriptions, and explicitly supplied context directly to TypeSafe at `https://api.typesafe.ai/v1/systemone`. It does not use OpenRouter. This is a different transport from setups that use an OpenRouter proxy. Do not include secrets, personal notes, proprietary catalogs, sensitive logs, or private source code without appropriate authorization. The tool cannot reliably detect or redact secrets for you.

All automatic workflows default to off. `--live` is an explicit one-time network request even when automatic mode is off. `--private` and `--follow-up` always bypass the network. A toggle only gates calls made with `--automatic`; it does not install a host hook or control other tools.

The API key is read from `TYPESAFE_API_KEY` and passed to curl on stdin, not in process arguments. No response body or transport error text is echoed on failure. Redirects and automatic retries are disabled. Usage logs contain counts and fixed model-size labels, not prompts or candidate IDs. These safeguards do not hide data from the remote API provider or from an administrator of your machine.

Do not put credentials or sensitive reproduction data in public issues. For a security report, use GitHub's private vulnerability reporting if available; otherwise request a private contact without disclosing the vulnerability or confidential data publicly.
