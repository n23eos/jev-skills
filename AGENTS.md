# Contributing with an agent

Use Python 3.10+ and the standard library. Run `python3 -m unittest discover -s tests -v`.
Keep decisions advisory. Only a separate explicit host runner may launch a helper
after the user requests execution. Never execute a command from candidate data,
skip mandatory tests, grant permission, or silently run a selected skill.
Network calls require explicit live mode or an opted-in automatic workflow.
Preserve fail-open fallbacks, finite deadlines, strict answer validation, and `none`.
Never commit keys, local settings, private catalogs, or directories named `!notes`.
Use plain hyphens instead of Unicode en/em dashes in authored files.
New changes start in specs/ with a specification, plan, and tasks; update STATUS.md.
