"""Compare a lexical baseline with advisory Jev on public synthetic skills.

Offline by default. --live is the only path that creates a Client, and contextual
follow-ups never reach it. This does not load skills in a native host.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_skills.core import Client, MODEL, number, select, validate_input
from jev_skills.skill_selection import contextual_followup

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "catalog-eval.json"
STOPWORDS = {"a", "an", "and", "are", "at", "before", "by", "for", "from", "how", "in", "into",
             "of", "on", "or", "the", "this", "to", "using", "with", "after", "make", "add", "fix"}
MAX_REPORT_BYTES = 400_000


def fixtures() -> dict:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("cases"), list):
        raise ValueError("invalid_catalog_fixture")
    candidates = validate_input({"request": "Public synthetic fixture", "candidates": value.get("candidates")})["candidates"]
    ids = {entry["id"] for entry in candidates}
    seen = set()
    for case in value["cases"]:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or case["id"] in seen:
            raise ValueError("invalid_catalog_case")
        seen.add(case["id"])
        if not isinstance(case.get("request"), str) or not case["request"].strip():
            raise ValueError("invalid_catalog_request")
        kind, expected = case.get("kind"), case.get("expected")
        if kind not in {"direct", "ambiguous", "negative", "contextual_follow_up"}:
            raise ValueError("invalid_catalog_case_kind")
        if expected not in ids | {"none", None}:
            raise ValueError("invalid_catalog_label")
        if (kind == "contextual_follow_up") != (expected is None):
            raise ValueError("invalid_contextual_label")
        if (kind == "contextual_follow_up") != contextual_followup(case["request"]):
            raise ValueError("fixture_context_gate_mismatch")
    if not 24 <= len(candidates) <= 40 or len(value["cases"]) < 20:
        raise ValueError("catalog_fixture_too_small")
    value["candidates"] = candidates
    return value


def terms(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.casefold())
    return {word[:-1] if word.endswith("s") and len(word) > 4 else word
            for word in words if len(word) > 2 and word not in STOPWORDS}


def lexical_baseline(request: str, candidates: list[dict]) -> str:
    """Reproducible overlap baseline; zero or a one-term overlap abstains."""
    query = terms(request)
    rankings = []
    for entry in candidates:
        name = terms(entry["id"].replace("-", " "))
        description = terms(entry["description"])
        overlap = query & (name | description)
        score = len(overlap) + len(overlap & name)
        rankings.append((len(overlap), score, entry["id"]))
    best = max((row[:2] for row in rankings), default=(0, 0))
    winners = sorted(row[2] for row in rankings if row[:2] == best)
    return winners[0] if best[0] >= 2 else "none"


def observed(result: dict) -> str | None:
    if result.get("route") == "recommendation":
        return result.get("selected")
    if result.get("reason") == "none_selected":
        return "none"
    return None


def accuracy(rows: list[dict], key: str) -> dict:
    matches = sum(row[key] == row["expected"] for row in rows)
    return {"matches": matches, "total": len(rows),
            "accuracy": round(matches / len(rows), 4) if rows else None}


def evaluate(data: dict, live: bool = False, timeout: float = 2.0) -> dict:
    timeout = number(timeout, 0.05, 60)
    candidates = data["candidates"]
    rows = []
    for case in data["cases"]:
        bypass = case["kind"] == "contextual_follow_up"
        baseline_raw = lexical_baseline(case["request"], candidates)
        row = {"id": case["id"], "kind": case["kind"], "expected": case["expected"],
               "baseline_raw": baseline_raw, "baseline_gated": None if bypass else baseline_raw,
               "jev_raw": None, "jev_gated": None, "jev_result": None}
        if live and not bypass:
            # A fresh client keeps each fixture's usage and failure accounting separate.
            outcome = select("skill", {"request": case["request"], "candidates": candidates},
                             Client(), timeout=timeout)
            row["jev_raw"] = observed(outcome)
            row["jev_gated"] = row["jev_raw"]
            row["jev_result"] = outcome
        rows.append(row)
    eligible = [row for row in rows if row["kind"] != "contextual_follow_up"]
    summary = {"cases": len(rows), "eligible": len(eligible),
               "contextual_bypasses": len(rows) - len(eligible),
               "by_kind": dict(Counter(row["kind"] for row in rows)),
               "baseline_raw": accuracy(eligible, "baseline_raw"),
               "baseline_gated": accuracy(rows, "baseline_gated"),
               "jev_raw": accuracy(eligible, "jev_raw") if live else None,
               "jev_gated": accuracy(rows, "jev_gated") if live else None}
    if live:
        outcomes = [row["jev_result"] for row in eligible]
        costs = [item.get("estimated_known_cost_usd") for item in outcomes]
        summary["jev_accounting"] = {
            "calls": sum(item.get("calls", 0) for item in outcomes),
            "completed_calls": sum(item.get("completed_calls", 0) for item in outcomes),
            "unaccounted_calls": sum(item.get("unaccounted_calls", 0) for item in outcomes),
            "input_tokens": sum(item.get("usage", {}).get("input_tokens", 0) for item in outcomes),
            "output_tokens": sum(item.get("usage", {}).get("output_tokens", 0) for item in outcomes),
            "known_cost_usd": round(sum(costs), 10) if all(isinstance(cost, (int, float)) for cost in costs) else None,
            "cost_complete": all(item.get("cost_complete", False) for item in outcomes),
            "failed_cases": [row["id"] for row in eligible if row["jev_raw"] is None],
            "mismatched_cases": [row["id"] for row in eligible if row["jev_raw"] != row["expected"]],
        }
    return {"mode": "live_synthetic" if live else "offline_synthetic", "network": live,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(), "model_version": MODEL if live else None,
            "per_case_timeout_seconds": timeout if live else None,
            "source": data["source"],
            "limitations": "Author-assigned public synthetic labels; no private catalogs, native host loading or production accuracy claim.",
            "summary": summary, "cases": rows}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Synthetic catalog evaluation, offline by default")
    parser.add_argument("--live", action="store_true", help="explicitly allow Jev API calls for public synthetic cases")
    parser.add_argument("--output", type=Path, help="write JSON report to a new, explicit path")
    parser.add_argument("--timeout", type=float, default=2.0, help="per-case Jev deadline in seconds")
    args = parser.parse_args(argv)
    if args.live and args.output is None:
        parser.error("--live requires --output")
    try:
        report = evaluate(fixtures(), live=args.live, timeout=args.timeout)
    except (OSError, ValueError, TypeError) as error:
        parser.error(str(error))
    encoded = json.dumps(report, ensure_ascii=True, allow_nan=False, indent=2) + "\n"
    if len(encoded.encode("utf-8")) > MAX_REPORT_BYTES:
        parser.error("evaluation_report_too_large")
    if args.output is not None:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(encoded)
        except OSError:
            parser.error("cannot_create_report_or_output_exists")
        print(json.dumps({"output": str(args.output), "summary": report["summary"]}, ensure_ascii=True))
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
