# Status

Goal: publish a portable Jev-powered Agent Skills collection for Claude Code and Codex.
Stage: published at https://github.com/n23eos/jev-skills.
Decisions: independent community project; opt-in network; model IDs supplied by users;
one typed choice per request; none/low confidence/errors fall back to the host.
Checks: 36 offline tests pass; package build/install and both skill destinations pass;
seven manifests validated. Independent review's numeric-overflow issue fixed with regressions.
Live: 22 API calls and 3 local bypass probes; 5 confidence fallbacks retained in reports.
Publication: public main branch pushed. GitHub CI passed on Python 3.10 and 3.13.
Blockers: none. Automatic workflows: off. X announcement: drafted, not posted.
README follow-up: reused the existing ETH donation badges and Ko-fi button, in that order; links matched the owner's existing repository README blocks.
Next: opt-in trials with actual host models; evaluate description changes on new cases.
