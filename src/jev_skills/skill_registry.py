"""Explicit registry for packaged skills and supported bundle upgrades."""


HISTORICAL_SKILLS = (
    "jev-bug-triage",
    "jev-context-picker",
    "jev-controls",
    "jev-model-router",
    "jev-plan-selector",
    "jev-skill-picker",
    "jev-test-prioritizer",
)

PACKAGED_SKILLS = tuple(sorted((
    *HISTORICAL_SKILLS,
    "jev-citation-checker",
    "jev-ci-triage",
    "jev-eval-gap-picker",
    "jev-issue-next-step",
    "jev-review-comment-triage",
    "jev-tool-picker",
    "jev-value-picker",
)))

SUPPORTED_MANIFEST_SKILL_SETS = (
    frozenset(HISTORICAL_SKILLS),
    frozenset(PACKAGED_SKILLS),
)
