# Plan

1. Verify installed host CLI contracts and current TypeSafe guidance.
2. Implement independent installer/doctor and catalog workflow improvements.
3. Integrate CLI commands, explicit helper adapters and managed host instructions.
4. Replace first-use docs; expand public evaluation and exercise real host paths.
5. Independent security/behavior review, regression checks, commit and push.

Keep the choice engine advisory. The explicit helper runner is a separate layer,
never called by enable/disable, dry-run, or the model's response alone. Retain
Python 3.10+ support and bounded calls. No user-global host configuration changes
are made while developing; integration tests use temporary projects.
