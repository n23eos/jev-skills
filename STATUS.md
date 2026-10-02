# Status

Current work, 2026-10-02: user authorized all researched skills, verification, push and deployment. Version 0.3.0 published and verified under specs/004-user-decision-workflows.
Goal: useful bounded decisions with concrete evidence and next actions; preserve advisory, opt-in and fail-open boundaries.
Result: seven new structured workflows, fourteen installable skills, packaged public examples, exact local source/value checks, growing-bundle upgrades, first-use diagnostics and comparison preparation. Previous first-use work retained.
Checks: 141 offline tests pass on Python 3.10 and 3.14; fourteen skill validators pass; wheel and source distribution build; isolated installed wheel on Python 3.10 passes both host destinations, idempotence, doctor and all seven offline example previews. Independent review found and fixed preview/live payload mismatch and missing-owned-file upgrade diagnostics. Semantic Jev effectiveness remains unmeasured.
Deployment: existing GitHub source distribution and v0.3.0 release, followed by isolated public install and CI verification. No server application or paid provider evaluation is implied.
Publication: implementation commit 4cb8ab4 pushed to main; tag and GitHub release v0.3.0 published with wheel and source distribution. CI run 36997359878 passed on Python 3.10 and 3.13. Fresh isolated public GitHub install fetched that commit and passed both fourteen-skill destinations, idempotence and all seven packaged previews.
Blockers: none for implementation/publication. Real-task decision benefits and native host discovery remain unmeasured.
Next: collect opt-in real-user feedback and paired task outcomes before changing automatic defaults or claiming improvements.

## Previous local first-use result

Current work, 2026-10-02: first-use diagnostics and picker comparison implemented locally under specs/003-first-use-comparison. Not committed or published.
Goal: understandable setup, visible catalog coverage, and honest paired choice measurements.
Result: doctor --format human with next actions and backward-compatible default JSON; local catalog_coverage on preview, recommendation and fallback; additional EN/RU follow-up bypasses; size-aware request groups; changed metadata excluded before selection.
Comparison: offline preparation for 9 public authored EN/RU tasks and captured-result importer. Conditional choice accuracy, outcome success including failures, fallback coverage, time and tokens remain separate. Ordinary-host prompted choices are not native skill-discovery or downstream task-success tests. No real captures collected in this change.
Checks: 119 offline tests pass on Python 3.10 and 3.14. Compileall, diff and literal forbidden-dash checks pass. Fresh package install from local uv cache, both host destinations, idempotence, human/JSON diagnostics, local warning separation and follow-up bypass verified. Comparison CLI preparation/import/overwrite protection verified offline.
Review: independent review found metadata read mismatch and missing excluded counts; both fixed and focused regressions rechecked.
Blockers: none for local implementation. Real-host/provider comparison remains unmeasured and requires separately authorized/captured runs. No new host launches, live calls, global settings changes, commit, push or deployment.
Next: try readable setup locally and collect paired captures before claiming accuracy, speed or cost improvements.

## Historical published v0.2 status

Goal: publish a portable Jev-powered Agent Skills collection for Claude Code and Codex.
Stage: version 0.2 published and verified under specs/002-practical-workflows at https://github.com/n23eos/jev-skills.
Decisions: independent community project; opt-in network; model IDs supplied by users;
one typed choice per request; none/low confidence/errors fall back to the host.
Checks: 100 offline tests pass on Python 3.10 and 3.14; compileall and diff checks pass.
Fresh packaged uv installation, both skill destinations, idempotence and exact v0.1 migration verified.
Independent review fixed persistent catalog consent (pinned metadata digest) and invalid/mismatched model profiles.
Live: 30-skill synthetic catalog comparison: 30/30 eligible Jev choices match labels versus lexical 25/30, plus 3 local bypasses. Not native-host accuracy.
Real pick-skill selected and read a public installed fixture; subsequent model route abstained at 0.58 as designed.
Separate real Codex helper completed. Claude helper reports authentication required; native auto-discovery is not claimed as tested.
Historical v0.1 failures and all new public synthetic reports are retained.
Publication: implementation commit 973f871 pushed; CI run 35727752669 passed on Python 3.10 and 3.13. The README install command fetched public GitHub v0.2 into a fresh uv environment and installed both host formats. No new X post sent by the agent.
Blockers: none for release; Claude live verification requires host login. Automatic workflows: off.
README follow-up: reused the existing ETH donation badges and Ko-fi button, in that order; links matched the owner's existing repository README blocks.
Next: optional authenticated Claude/native discovery verification and real-user feedback. User-facing priority is install, invoke a skill, and use it without writing JSON; advanced routing stays optional.
