# Status

Goal: publish a portable Jev-powered Agent Skills collection for Claude Code and Codex.
Stage: version 0.2 implemented and locally verified under specs/002-practical-workflows; preparing publication to https://github.com/n23eos/jev-skills.
Decisions: independent community project; opt-in network; model IDs supplied by users;
one typed choice per request; none/low confidence/errors fall back to the host.
Checks: 100 offline tests pass on Python 3.10 and 3.14; compileall and diff checks pass.
Fresh packaged uv installation, both skill destinations, idempotence and exact v0.1 migration verified.
Independent review fixed persistent catalog consent (pinned metadata digest) and invalid/mismatched model profiles.
Live: 30-skill synthetic catalog comparison: 30/30 eligible Jev choices match labels versus lexical 25/30, plus 3 local bypasses. Not native-host accuracy.
Real pick-skill selected and read a public installed fixture; subsequent model route abstained at 0.58 as designed.
Separate real Codex helper completed. Claude helper reports authentication required; native auto-discovery is not claimed as tested.
Historical v0.1 failures and all new public synthetic reports are retained.
Publication: public repository exists; v0.2 remote CI pending. No new X post sent by the agent.
Blockers: none for release; Claude live verification requires host login. Automatic workflows: off.
README follow-up: reused the existing ETH donation badges and Ko-fi button, in that order; links matched the owner's existing repository README blocks.
Next: push the verified v0.2 release and check remote CI. User-facing priority is install, invoke a skill, and use it without writing JSON; advanced routing stays optional.
