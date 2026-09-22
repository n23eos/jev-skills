# Practical workflows, version 0.2

The audit found that version 0.1 demonstrated typed decisions but left catalog
preparation, host handoff and installation lifecycle to the user. Improve the two
original use cases without weakening the network or execution boundary.

## Required behavior

- Pick an installed skill directly from explicitly selected roots and a task.
  Use full supported metadata, exclude the picker itself and opt-out candidates,
  preserve local identity, and return a selected path for the host to read.
  No private skill body or local path is automatically uploaded to Jev.
- Keep dry-run the default. Live catalog transmission requires an explicit
  reviewed-catalog acknowledgement. Off/private/contextual-turn bypass occurs
  before catalog scans or file reads. Follow-up detection is conservative and
  local; explicit flags remain authoritative.
- Provide maintained per-host integration instructions that can be installed as
  a managed, opt-in project block without overwriting user instructions.
- Route a task using a reusable, explicitly configured real-model profile.
  A recommendation never runs a command. An additional explicit execution flag
  may start a bounded Codex or Claude helper, with conservative permissions,
  no arbitrary executable supplied by a model, and no parent model switch.
  Distinguish requested model from runtime-confirmed model.
- Add offline doctor diagnostics and safe install/upgrade with ownership hashes.
  Preserve edits, avoid partial installs, and provide rollback on failure.
- Evaluate a larger public-purpose skill catalog on ambiguous, negative and
  contextual requests; compare against a deterministic baseline. Keep results,
  failures and costs separate from host execution results and user data.

## Acceptance

Offline tests cover command-level flows and error recovery. At least one actual
host helper flow and one actual catalog pick are exercised with public synthetic
inputs only; unsupported or unavailable host behavior is reported honestly.
Documentation provides copyable first-use instructions, lifecycle commands and
an explicit compatibility matrix. Existing donation links are preserved.

## Non-goals

No unconditional interception of every message, no silent privilege escalation,
no unreviewed execution of catalog commands, no private-catalog publication,
no production accuracy or savings claim from synthetic evaluation.
