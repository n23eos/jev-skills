# Implementation plan

1. Verify official TypeSafe HTTP API v1 and agent skill formats.
2. Build shared Python runtime, bounded transport, config, catalog and installer.
3. Write seven self-contained skill entrypoints and examples.
4. Exercise network-free regression tests, installation and wheel contents.
5. Run synthetic live evaluations; document all results without mock accuracy claims.
6. Independent review, publication audit, commit, public GitHub push and CI check.

Use direct TypeSafe HTTPS with TYPESAFE_API_KEY. Use curl with a wall-clock
deadline and no retries; errors resume normal agent behavior. No dependency on
private model names, host-specific paths, operating-system keychains or OpenRouter.
