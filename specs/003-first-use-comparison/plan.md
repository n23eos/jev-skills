# Plan

Goal: make first use understandable and catalog choice coverage inspectable, with an honest paired comparison workflow.

1. Preserve JSON diagnostics by default; add explicit human output with next actions.
2. Carry local catalog coverage independently of sanitized selection input, including empty-catalog fallbacks.
3. Expand conservative follow-up regression coverage and split payloads by count and bytes for both dry-run and live selection.
4. Prepare public EN/RU paired benchmark prompts and import captured results, never invoke a provider implicitly.
5. Update first-use and skill instructions; independently review logic, run project tests, packaged smoke and diff checks.

Ownership: parent owns diagnostics, CLI, catalog handoff, docs and specs. Payload worker owns core.py/test_core.py. Comparison worker owns comparison script, fixture, tests and its guide. Review is read-only.

Decisions: standard library only, Python 3.10+; old diagnostics remain compatible; local warnings may contain paths, never upload them; missing benchmark data stays unmeasured.
Checks: python3 -m unittest discover -s tests -v; compileall; isolated local package and CLI smoke; diff and literal U+2013/U+2014 check.
Blockers: none for local implementation; real-host comparative measurements require separately captured runs.
Completed: implementation and independent review; two findings resolved. 119 tests pass on Python 3.10 and 3.14, packaged CLI and comparison smoke pass offline.
Next: capture real paired results separately; no live result is claimed.
