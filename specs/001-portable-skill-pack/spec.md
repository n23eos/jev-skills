# Portable Jev coding skills

Provide seven English Agent Skills compatible with Claude Code and Codex:
model router, skill picker, context picker, test prioritizer, bug triage,
plan selector, and routing controls. Share one inspectable Python CLI.

Each decision receives explicit state and finite candidates, returns one typed
recommendation plus uncertainty, and never executes the recommendation. Model
availability and ordering belong to the host configuration, not to Jev.
All automatic workflows start off. One-time live trials require an explicit flag.
Private or contextual follow-ups bypass network. Invalid input, API errors,
timeouts, low confidence and none return a fallback. Malformed settings stay off.

Choice supports at most 255 options; reserve one for none. Larger catalogs use
bounded groups and a final winner comparison. Account for every request, not just
successful final selections. Do not promise zero latency or measured savings.

Acceptance: portable installation into both agents' skills directories; meaningful
unit/CLI tests; labeled synthetic live evaluation with raw decisions and failures;
public documentation, license, CI, and explicit compatibility limitations. No
personal paths or proprietary skill catalog may appear in the public repository.
