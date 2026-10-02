# Ordinary-host prompted-choice and Jev skill-picker comparison

This offline harness prepares the same public catalog and task wording for an ordinary host prompted-choice baseline and Jev, then compares results captured outside the harness. The host prompt supplies skill IDs and descriptions directly. It does not load skills or measure native skill auto-discovery. The fixture is project-authored and synthetic. It is not real user traffic. The report measures skill choice only, not whether either system could complete the downstream task.

The harness never starts Codex, Claude, a helper, a skill, or a network request. A person must run every measured session explicitly and record its actual provenance. Missing captures remain `unmeasured`; they are not treated as wrong answers or zero accuracy.

## 1. Prepare an unlabelled run

From the repository root:

```sh
python3 scripts/compare_skill_picker.py prepare --output /tmp/skill-picker-run
```

The output directory must not already exist. `manifest.json` contains the benchmark SHA-256 digest, catalog, and file map without expected labels or case kinds. `native-prompts/` contains one standalone prompt per task. `jev-inputs/` contains the equivalent bounded Jev input. `requests/` and `catalog/` support the higher-level `pick-skill` command and its local follow-up gate.

Do not publish a capture as an independent or real-user benchmark. The catalog and tasks are a small public authored fixture with deliberately overlapping descriptions, negative cases, and context-dependent follow-ups in English and Russian.

## 2. Capture ordinary-host prompted choices

Open a fresh host session for every file in `native-prompts/`. Paste the file unchanged and save the returned JSON. Do not let an earlier task or answer remain in context. Record the exact host, requested or configured model, host version, capture source, and UTC capture time. Record `reported_model` only when the host reports the actual serving model; use `null` when it does not. If the host does not report elapsed time or tokens, omit those fields instead of entering zero.

Create `native-results.json`:

```json
{
  "schema_version": 1,
  "provenance": {
    "system": "native_host",
    "host": "Codex CLI",
    "model": "exact requested or configured model name",
    "reported_model": null,
    "version": "exact host version",
    "source": "manual fresh-session capture; identify the transcript or procedure",
    "captured_at_utc": "2026-10-02T08:00:00+00:00",
    "fresh_session_per_task": true,
    "benchmark_sha256": "copy from /tmp/skill-picker-run/manifest.json"
  },
  "results": [
    {
      "id": "task-01",
      "choice": "python-testing",
      "elapsed_ms": 1250,
      "usage": {"input_tokens": 640, "output_tokens": 12}
    },
    {
      "id": "task-08",
      "choice": "followup"
    },
    {
      "id": "task-04",
      "failure": {"reason": "host_timeout", "detail": "No final choice was returned"}
    }
  ]
}
```

Valid choices are a catalog ID, `none`, or `followup`. Results may be partial. Each omitted fixture case is reported as `unmeasured`. A result must contain exactly one of `choice`, `failure`, or `raw_result`.

## 3. Capture Jev choices explicitly

For each task, run a separate CLI process. This is the networked measurement step and is not performed by the harness:

First review the candidate metadata in the prepared `manifest.json`. Only pass `--reviewed-catalog` after that review; the task and candidate descriptions will be sent to TypeSafe. Leave automatic workflows off.

```sh
jev-skills pick-skill \
  --root /tmp/skill-picker-run/catalog \
  --request-file /tmp/skill-picker-run/requests/task-01.txt \
  --live --reviewed-catalog \
  > /tmp/skill-picker-run/jev-task-01.json
```

Repeat with the matching request file for each case. `pick-skill` locally returns `contextual_follow_up` for a detected contextual reply. It sends no network request for that case. For a standalone request, `--live` explicitly permits one Jev selection session. The generated catalog skills are metadata-only benchmark placeholders and must not be applied.

Create `jev-results.json` and paste each complete CLI JSON object under `raw_result`:

```json
{
  "schema_version": 1,
  "provenance": {
    "system": "jev",
    "host": "jev-skills CLI",
    "model": "jev-1.13.0",
    "reported_model": "jev-1.13.0",
    "version": "exact installed jev-skills version or source revision",
    "source": "separate explicit pick-skill CLI captures from the prepared public run",
    "captured_at_utc": "2026-10-02T08:15:00+00:00",
    "fresh_session_per_task": true,
    "benchmark_sha256": "copy from /tmp/skill-picker-run/manifest.json"
  },
  "results": [
    {
      "id": "task-01",
      "raw_result": {
        "route": "recommendation",
        "selected": "python-testing",
        "reason": null,
        "elapsed_ms": 92,
        "usage": {"input_tokens": 510, "output_tokens": 34}
      }
    },
    {
      "id": "task-08",
      "raw_result": {
        "route": "fallback",
        "selected": null,
        "reason": "contextual_follow_up"
      }
    }
  ]
}
```

The importer maps `none_selected` to `none` and `contextual_follow_up` to `followup`. Other Jev fallbacks remain failures with their reason. Raw token and elapsed fields are validated and included when present.

## 4. Build the offline comparison

```sh
python3 scripts/compare_skill_picker.py compare \
  --native-results native-results.json \
  --jev-results jev-results.json \
  --output comparison-report.json
```

The output file must not already exist. Both captures must name the exact fixture digest and confirm fresh sessions. The report includes each result or failure, matches against one or more acceptable IDs, negative and follow-up fallback coverage, elapsed measurements, token totals, and paired outcomes. `choice_accuracy` uses only successfully measured choices. `outcome_success_rate` also counts captured failures in its denominator. Both remain `null` when nothing was captured. Coverage and failure counts show what was actually observed.

No score from this fixture establishes production accuracy, native skill discovery quality, speed, cost, or downstream task quality. The prompted baseline may see different wrapper instructions than Jev, and host and Jev token accounting may cover different content. Treat reported usage as provenance-backed measurements rather than identical billing units.
