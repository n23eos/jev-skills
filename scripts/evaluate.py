"""Opt-in synthetic evaluation; no host commands or personal data are used.

Usage: python3 scripts/evaluate.py [--live --output reports/live.json --timeout 12]
Offline mode lists fixture labels only. A live run makes one bounded API selection
per non-bypass fixture and retains raw sanitized judgments for audit.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from threading import Lock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_skills.catalog import manifest
from jev_skills.core import Client, MODEL, curl_transport, fallback, select

ROOT = Path(__file__).resolve().parents[1]
SIZES = ("tiny", "everyday", "large", "hardest")
MODELS = [
    {"id": f"tier-{size}", "size": size, "description": description}
    for size, description in (
        ("tiny", "Synthetic lowest-cost model: short routine text edits only."),
        ("everyday", "Synthetic standard coding model: isolated changes and common unit tests."),
        ("large", "Synthetic advanced coding model: coupled components and complex debugging."),
        ("hardest", "Synthetic strongest model: risky design or ambiguous safety decisions."),
    )
]


def fixtures():
    """Expected answers are author-assigned synthetic labels, not model truth."""
    cases = []
    model_tasks = (
        ("Fix a single typo in a comment.", "tier-tiny"),
        ("Summarize filenames from a supplied short list.", "tier-tiny"),
        ("Add a bounded parsing helper with unit tests.", "tier-everyday"),
        ("Repair a known single-module validation bug.", "tier-everyday"),
        ("Diagnose a failure crossing a cache and queue.", "tier-large"),
        ("Refactor three related modules while preserving behavior.", "tier-large"),
        ("Resolve conflicting requirements for a security boundary.", "tier-hardest"),
        ("Review a high-impact ambiguous migration for data loss.", "tier-hardest"),
    )
    for index, (request, expected) in enumerate(model_tasks, 1):
        cases.append({"id": f"model-{index:02}", "workflow": "model", "expected": expected,
                      "input": {"request": request, "context": {"fixture": "fictional capabilities only"},
                                "candidates": MODELS}})
    cases.extend([
        {"id": "bypass-private", "workflow": "model", "expected": None, "bypass": "private",
         "input": {"request": "Private synthetic request", "candidates": MODELS}},
        {"id": "bypass-followup-1", "workflow": "model", "expected": None, "bypass": "contextual_follow_up",
         "input": {"request": "Yes, do that, but make it shorter.", "candidates": MODELS}},
        {"id": "bypass-followup-2", "workflow": "model", "expected": None, "bypass": "contextual_follow_up",
         "input": {"request": "Use the second one.", "candidates": MODELS}},
    ])
    names = ("jev-model-router", "jev-skill-picker", "jev-context-picker",
             "jev-test-prioritizer", "jev-bug-triage", "jev-plan-selector", "jev-controls")
    candidates = []
    for name in names:
        actual_name, description = manifest(ROOT / "src" / "jev_skills" / "skills" / name / "SKILL.md")
        if actual_name != name:
            raise ValueError("catalog_name_mismatch")
        candidates.append({"id": name, "description": description})
    skill_tasks = (
        ("This typo fix is tiny; should I use the small or advanced host model?", "jev-model-router"),
        ("I found several installed aids. Which is relevant to changing a parser?", "jev-skill-picker"),
        ("I have three likely files; which one should I read next?", "jev-context-picker"),
        ("The parser changed. Which existing check is most informative to run first?", "jev-test-prioritizer"),
        ("Empty input now throws before rendering. Where should I investigate first?", "jev-bug-triage"),
        ("I wrote two feasible ways to fix this edge case. Which fits the constraints?", "jev-plan-selector"),
        ("Are remote automatic suggestions enabled, and how do I turn them off?", "jev-controls"),
        ("Suggest a lunch recipe from available ingredients.", "none"),
        ("Translate a fictional poem into another language.", "none"),
        ("Calculate the area of a synthetic circle.", "none"),
    )
    for index, (request, expected) in enumerate(skill_tasks, 1):
        cases.append({"id": f"skill-{index:02}", "workflow": "skill", "expected": expected,
                      "input": {"request": request, "candidates": candidates}})
    extra = (
        ("context", "Pick the error parser description to inspect after a parse failure.", "parser",
         [("parser", "Parses error messages."), ("cache", "Stores rendered messages.")]),
        ("tests", "Pick the parser unit test first after changing parsing.", "unit-parser",
         [("unit-parser", "Parser unit tests."), ("ui-check", "Visual layout check.")]),
        ("bug", "A synthetic parse exception occurs on empty input. Where to inspect first?", "parser",
         [("parser", "Handles empty input."), ("renderer", "Renders parsed values.")]),
        ("plan", "Choose a minimal parser fix with a regression test.", "local-fix",
         [("local-fix", "Fix parser and add unit regression."), ("rewrite", "Replace the application framework.")]),
    )
    for workflow, request, expected, options in extra:
        cases.append({"id": f"extra-{workflow}", "workflow": workflow, "expected": expected,
                      "input": {"request": request, "candidates": [
                          {"id": name, "description": description} for name, description in options]}})
    return cases


def evaluate(cases, timeout):
    results = []
    for case in cases:
        bypass = case.get("bypass")
        criteria_history = []
        lock = Lock()
        def recording_transport(payload, remaining):
            with lock:
                criteria_history.append({"criteria": payload["questions"]["selection"]["criteria"],
                                         "request_timeout_seconds": remaining})
            return curl_transport(payload, remaining)
        # Match the CLI's pre-input bypass behavior: never ask the remote client.
        outcome = fallback(bypass) if bypass else select(case["workflow"], case["input"],
                                                          Client(recording_transport), timeout=timeout)
        observed = (outcome.get("selected") if outcome["route"] == "recommendation" else
                    "none" if outcome.get("reason") == "none_selected" else None)
        results.append({"id": case["id"], "workflow": case["workflow"], "expected": case["expected"],
                        "observed": observed, "match": observed == case["expected"],
                        "input": case["input"],
                        "criteria_history": criteria_history,
                        "result": outcome})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Synthetic labeled Jev evaluation, offline by default")
    parser.add_argument("--live", action="store_true", help="explicitly allow API requests for synthetic cases")
    parser.add_argument("--output", type=Path, default=Path("reports/live.json"))
    parser.add_argument("--timeout", type=float, default=12.0, help="per-case deadline in seconds, 0.05 to 60")
    parser.add_argument("--markdown", action="store_true", help="also generate a brief Markdown table alongside JSON")
    args = parser.parse_args(argv)
    cases = fixtures()
    if not args.live:
        print(json.dumps({"mode": "offline", "network": False, "cases": [
            {"id": case["id"], "workflow": case["workflow"], "expected": case["expected"]}
            for case in cases]}, indent=2))
        return 0
    if not 0.05 <= args.timeout <= 60:
        parser.error("--timeout must be between 0.05 and 60")
    results = evaluate(cases, args.timeout)
    report = {"mode": "live_synthetic", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "model_version": MODEL, "per_case_timeout_seconds": args.timeout,
              "label_note": "Author-assigned synthetic expectations; no labels changed after results.",
              "cases": results,
              "summary": {"count": len(results), "matches": sum(row["match"] for row in results),
                          "mismatches": [row["id"] for row in results if not row["match"]],
                          "calls": sum(row["result"].get("calls", 0) for row in results),
                          "unaccounted_calls": sum(row["result"].get("unaccounted_calls", 0) for row in results)}}
    encoded = json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False)
    if len(encoded.encode("utf-8")) > 200_000:
        raise ValueError("evaluation_report_too_large")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded + "\n", encoding="utf-8")
    if args.markdown:
        lines = ["| Fixture | Expected | Observed | Match | Confidence | Calls | Latency ms | Input tokens | Output tokens | Estimated USD | Reason |",
                 "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
        for row in results:
            result = row["result"]
            usage = result.get("usage", {})
            lines.append("| " + " | ".join(str(value) for value in (
                row["id"], row["expected"], row["observed"], row["match"], result.get("confidence"),
                result.get("calls", 0), result.get("elapsed_ms"), usage.get("input_tokens", 0),
                usage.get("output_tokens", 0), result.get("estimated_known_cost_usd"), result.get("reason"))) + " |")
        args.output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": report["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
