"""Prepare and compare bounded, offline skill-picker captures.

This script never launches a host, helper, or network request. It creates an
unlabelled prompt pack, then compares separately captured native-host and Jev
results against a public authored fixture.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "examples" / "skill-picker-comparison.json"
MAX_INPUT_BYTES = 1_000_000
MAX_OUTPUT_BYTES = 2_000_000
MAX_CASES = 100
MAX_CANDIDATES = 100
MAX_TEXT = 8_000
MAX_ELAPSED_MS = 86_400_000
MAX_TOKENS = 1_000_000_000
SPECIAL_CHOICES = {"none", "followup"}
KINDS = {"direct", "overlap", "negative", "followup"}
TOKEN_FIELDS = ("input_tokens", "output_tokens", "cached_input_tokens",
                "cache_creation_input_tokens", "cache_read_input_tokens",
                "reasoning_output_tokens", "total_tokens")


def _text(value, field: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"invalid_{field}")
    return value.strip()


def _reject_json_constant(_value: str):
    raise ValueError("invalid_json_number")


def _read_json(path: Path) -> dict:
    try:
        if path.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError("input_too_large")
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except OSError as error:
        raise ValueError("cannot_read_input") from error
    except (json.JSONDecodeError, RecursionError) as error:
        raise ValueError("invalid_json") from error
    if not isinstance(value, dict):
        raise ValueError("invalid_json_object")
    return value


def _canonical_digest(value: dict) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_fixture(path: Path = DEFAULT_FIXTURE) -> dict:
    value = _read_json(path)
    if "cases" not in value:
        raise ValueError("invalid_cases")
    if set(value) != {"schema_version", "benchmark", "candidates", "cases"}:
        raise ValueError("invalid_fixture_fields")
    if value.get("schema_version") != 1:
        raise ValueError("unsupported_fixture_schema")
    benchmark = value.get("benchmark")
    if not isinstance(benchmark, dict):
        raise ValueError("missing_benchmark_metadata")
    if set(benchmark) != {"name", "source", "authorship", "limitations"}:
        raise ValueError("invalid_benchmark_fields")
    for field in ("name", "source", "authorship", "limitations"):
        _text(benchmark.get(field), f"benchmark_{field}", 1_000)

    candidates = value.get("candidates")
    cases = value.get("cases")
    if not isinstance(candidates, list) or not 2 <= len(candidates) <= MAX_CANDIDATES:
        raise ValueError("invalid_candidates")
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise ValueError("invalid_cases")

    candidate_ids = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("invalid_candidate")
        if set(candidate) != {"id", "name", "description"}:
            raise ValueError("invalid_candidate_fields")
        identifier = _text(candidate.get("id"), "candidate_id", 100)
        name = _text(candidate.get("name"), "candidate_name", 200)
        description = _text(candidate.get("description"), "candidate_description", 1_000)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", identifier):
            raise ValueError("invalid_candidate_id")
        if "\n" in name or "\n" in description:
            raise ValueError("invalid_candidate_metadata")
        if identifier in SPECIAL_CHOICES or identifier in candidate_ids:
            raise ValueError("duplicate_or_reserved_candidate_id")
        candidate_ids.add(identifier)

    case_ids = set()
    kinds = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("invalid_case")
        if set(case) != {"id", "request", "kind", "acceptable"}:
            raise ValueError("invalid_case_fields")
        identifier = _text(case.get("id"), "case_id", 100)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", identifier):
            raise ValueError("invalid_case_id")
        if identifier in case_ids:
            raise ValueError("duplicate_case_id")
        case_ids.add(identifier)
        _text(case.get("request"), "case_request")
        kind = case.get("kind")
        if kind not in KINDS:
            raise ValueError("invalid_case_kind")
        kinds.add(kind)
        acceptable = case.get("acceptable")
        if (not isinstance(acceptable, list) or not acceptable or
                len(acceptable) != len(set(acceptable))):
            raise ValueError("invalid_acceptable_choices")
        if any(not isinstance(choice, str) or choice not in candidate_ids | SPECIAL_CHOICES
               for choice in acceptable):
            raise ValueError("invalid_acceptable_choice")
        if kind == "negative" and acceptable != ["none"]:
            raise ValueError("invalid_negative_case")
        if kind == "followup" and acceptable != ["followup"]:
            raise ValueError("invalid_followup_case")
        if kind in {"direct", "overlap"} and any(choice in SPECIAL_CHOICES for choice in acceptable):
            raise ValueError("invalid_selection_case")
    if not {"overlap", "negative", "followup"}.issubset(kinds):
        raise ValueError("fixture_missing_required_case_kinds")
    return value


def _native_prompt(request: str, candidates: list[dict]) -> str:
    catalog = "\n".join(f"- {item['id']}: {item['description']}" for item in candidates)
    return (
        "Ordinary host prompted-choice baseline. Treat this prompt as a fresh session. Choose "
        "based only on the task and catalog. No native skills are loaded by this prompt. Do not "
        "perform the task. Reply with exactly one JSON object in "
        "the form {\"choice\":\"ID\"}. ID must be one catalog ID, none when no skill applies, "
        "or followup when the request depends on missing earlier conversation.\n\n"
        f"Task:\n{request}\n\nCatalog:\n{catalog}\n"
    )


def _write_text(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(value)


def _write_json(path: Path, value: dict) -> None:
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    if len(encoded.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise ValueError("output_too_large")
    _write_text(path, encoded)


def prepare(fixture: dict, output: Path) -> dict:
    digest = _canonical_digest(fixture)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir()
    except FileExistsError as error:
        raise ValueError("output_exists") from error
    prompts = output / "native-prompts"
    inputs = output / "jev-inputs"
    requests = output / "requests"
    catalog_root = output / "catalog"
    for folder in (prompts, inputs, requests, catalog_root):
        folder.mkdir()

    candidates = fixture["candidates"]
    jev_candidates = [{"id": item["id"], "description": item["description"]}
                      for item in candidates]
    tasks = []
    for case in fixture["cases"]:
        identifier = case["id"]
        prompt_path = prompts / f"{identifier}.txt"
        input_path = inputs / f"{identifier}.json"
        request_path = requests / f"{identifier}.txt"
        _write_text(prompt_path, _native_prompt(case["request"], candidates))
        _write_json(input_path, {"request": case["request"], "candidates": jev_candidates})
        _write_text(request_path, case["request"] + "\n")
        tasks.append({
            "id": identifier,
            "native_prompt": str(prompt_path.relative_to(output)),
            "jev_input": str(input_path.relative_to(output)),
            "request_file": str(request_path.relative_to(output)),
        })

    for candidate in candidates:
        skill_dir = catalog_root / candidate["id"]
        skill_dir.mkdir()
        body = (
            "---\n"
            f"name: {json.dumps(candidate['id'], ensure_ascii=False)}\n"
            f"description: {json.dumps(candidate['description'], ensure_ascii=False)}\n"
            "---\n\n"
            "Public benchmark placeholder. Do not execute this fixture as a real skill.\n"
        )
        _write_text(skill_dir / "SKILL.md", body)

    manifest = {
        "schema_version": 1,
        "benchmark_sha256": digest,
        "benchmark": fixture["benchmark"],
        "candidates": jev_candidates,
        "tasks": tasks,
        "labels_included": False,
        "network": False,
        "host_method": "ordinary_host_prompted_choice",
        "measurement": {"status": "unmeasured", "measured_results": 0, "cases": len(tasks)},
        "note": "Prompts are unlabelled. Run each native prompt in a fresh session. The script does not launch hosts, helpers, skills, or network requests.",
    }
    _write_json(output / "manifest.json", manifest)
    return manifest


def _nonnegative_number(value, field: str, maximum: float) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"invalid_{field}")
    if not math.isfinite(value) or value < 0 or value > maximum:
        raise ValueError(f"invalid_{field}")
    return value


def _usage(value) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict) or not value:
        raise ValueError("invalid_usage")
    unknown = set(value) - set(TOKEN_FIELDS)
    if unknown:
        raise ValueError("invalid_usage_field")
    result = {}
    for field, amount in value.items():
        if type(amount) is not int or not 0 <= amount <= MAX_TOKENS:
            raise ValueError("invalid_token_count")
        result[field] = amount
    return result


def _provenance(value, expected_system: str, digest: str) -> dict:
    if not isinstance(value, dict) or value.get("system") != expected_system:
        raise ValueError("invalid_provenance_system")
    allowed = {"system", "host", "model", "reported_model", "version", "source", "captured_at_utc",
               "fresh_session_per_task", "benchmark_sha256"}
    if set(value) != allowed:
        raise ValueError("invalid_provenance_fields")
    result = {"system": expected_system}
    for field in ("host", "model", "version", "source"):
        result[field] = _text(value.get(field), f"provenance_{field}", 500)
        if result[field].casefold() in {"unknown", "n/a", "unspecified"}:
            raise ValueError(f"inexact_provenance_{field}")
    reported_model = value.get("reported_model")
    if reported_model is not None:
        reported_model = _text(reported_model, "provenance_reported_model", 500)
        if reported_model.casefold() in {"unknown", "n/a", "unspecified"}:
            raise ValueError("inexact_provenance_reported_model")
    captured = _text(value.get("captured_at_utc"), "captured_at_utc", 100)
    try:
        moment = datetime.fromisoformat(captured.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("invalid_captured_at_utc") from error
    if moment.tzinfo is None or moment.utcoffset() is None or moment.utcoffset().total_seconds() != 0:
        raise ValueError("invalid_captured_at_utc")
    if value.get("fresh_session_per_task") is not True:
        raise ValueError("fresh_sessions_not_confirmed")
    if value.get("benchmark_sha256") != digest:
        raise ValueError("benchmark_digest_mismatch")
    result.update({
        "reported_model": reported_model,
        "captured_at_utc": captured,
        "fresh_session_per_task": True,
        "benchmark_sha256": digest,
    })
    return result


def _from_raw(raw: dict) -> tuple[str | None, dict | None]:
    if not isinstance(raw, dict):
        raise ValueError("invalid_raw_result")
    if set(raw) == {"choice"}:
        return raw["choice"], None
    route = raw.get("route")
    if route == "recommendation":
        return raw.get("selected"), None
    if route == "fallback":
        reason = raw.get("reason")
        if reason == "none_selected":
            return "none", None
        if reason == "contextual_follow_up":
            return "followup", None
        return None, {"reason": _text(reason, "failure_reason", 500)}
    raise ValueError("invalid_raw_result")


def load_capture(path: Path, expected_system: str, digest: str,
                 case_ids: set[str], choices: set[str]) -> dict:
    value = _read_json(path)
    if "results" not in value:
        raise ValueError("missing_results")
    if set(value) != {"schema_version", "provenance", "results"}:
        raise ValueError("invalid_capture_fields")
    if value.get("schema_version") != 1:
        raise ValueError("unsupported_capture_schema")
    provenance = _provenance(value.get("provenance"), expected_system, digest)
    raw_results = value.get("results")
    if not isinstance(raw_results, list):
        raise ValueError("missing_results")
    results = {}
    for item in raw_results:
        if not isinstance(item, dict):
            raise ValueError("invalid_result")
        if set(item) - {"id", "choice", "failure", "raw_result", "elapsed_ms", "usage"}:
            raise ValueError("invalid_result_fields")
        identifier = _text(item.get("id"), "result_id", 100)
        if identifier not in case_ids:
            raise ValueError("unknown_result_id")
        if identifier in results:
            raise ValueError("duplicate_result_id")
        forms = sum(field in item for field in ("choice", "failure", "raw_result"))
        if forms != 1:
            raise ValueError("result_requires_one_outcome")
        raw = item.get("raw_result")
        if "choice" in item:
            choice, failure = item["choice"], None
        elif "failure" in item:
            choice, failure = None, item["failure"]
        else:
            choice, failure = _from_raw(raw)
        if choice is None and failure is None:
            raise ValueError("invalid_result_choice")
        if choice is not None and (not isinstance(choice, str) or choice not in choices):
            raise ValueError("invalid_result_choice")
        if failure is not None:
            if not isinstance(failure, dict):
                raise ValueError("invalid_failure")
            failure = {"reason": _text(failure.get("reason"), "failure_reason", 500)}
            if "detail" in item.get("failure", {}):
                failure["detail"] = _text(item["failure"]["detail"], "failure_detail", 2_000)
        elapsed = item.get("elapsed_ms", raw.get("elapsed_ms") if isinstance(raw, dict) else None)
        usage = item.get("usage", raw.get("usage") if isinstance(raw, dict) else None)
        results[identifier] = {
            "choice": choice,
            "failure": failure,
            "elapsed_ms": None if elapsed is None else _nonnegative_number(elapsed, "elapsed_ms", MAX_ELAPSED_MS),
            "usage": _usage(usage),
        }
    return {"provenance": provenance, "results": results}


def _case_result(item: dict | None, acceptable: list[str]) -> dict:
    if item is None:
        return {"status": "unmeasured"}
    common = {"elapsed_ms": item["elapsed_ms"], "usage": item["usage"]}
    if item["failure"] is not None:
        return {"status": "failure", "failure": item["failure"], **common}
    return {"status": "measured", "choice": item["choice"],
            "match": item["choice"] in acceptable, **common}


def _summary(rows: list[dict], key: str) -> dict:
    results = [row[key] for row in rows]
    measured = [item for item in results if item["status"] == "measured"]
    failures = [item for item in results if item["status"] == "failure"]
    matches = sum(item["match"] for item in measured)
    fallback_rows = [row for row in rows if row["kind"] in {"negative", "followup"}]
    fallback_measured = [row[key] for row in fallback_rows if row[key]["status"] == "measured"]
    fallback_matches = sum(item["match"] for item in fallback_measured)
    elapsed = [item["elapsed_ms"] for item in results if item.get("elapsed_ms") is not None]
    tokens = {}
    for field in TOKEN_FIELDS:
        amounts = [item["usage"][field] for item in results
                   if item.get("usage") is not None and field in item["usage"]]
        tokens[field] = {"reported": len(amounts), "total": sum(amounts) if amounts else None}
    return {
        "cases": len(rows),
        "results_supplied": len(results) - sum(item["status"] == "unmeasured" for item in results),
        "measured_choices": len(measured),
        "skill_choices": sum(item["choice"] not in SPECIAL_CHOICES for item in measured),
        "abstentions": {
            "none": sum(item["choice"] == "none" for item in measured),
            "followup": sum(item["choice"] == "followup" for item in measured),
        },
        "failures": len(failures),
        "unmeasured": sum(item["status"] == "unmeasured" for item in results),
        "matches": matches,
        "mismatches": len(measured) - matches,
        "choice_accuracy": round(matches / len(measured), 4) if measured else None,
        "choice_accuracy_denominator": len(measured),
        "outcome_success_rate": round(matches / (len(measured) + len(failures)), 4)
        if measured or failures else None,
        "outcome_denominator": len(measured) + len(failures),
        "fallback_coverage": {
            "expected_cases": len(fallback_rows),
            "measured": len(fallback_measured),
            "matches": fallback_matches,
            "coverage": round(fallback_matches / len(fallback_rows), 4)
            if fallback_rows and fallback_measured else None,
        },
        "elapsed_ms": {
            "reported": len(elapsed),
            "total": sum(elapsed) if elapsed else None,
            "mean": round(sum(elapsed) / len(elapsed), 3) if elapsed else None,
        },
        "token_usage": tokens,
    }


def compare(fixture: dict, native: dict, jev: dict) -> dict:
    rows = []
    for case in fixture["cases"]:
        native_result = _case_result(native["results"].get(case["id"]), case["acceptable"])
        jev_result = _case_result(jev["results"].get(case["id"]), case["acceptable"])
        rows.append({"id": case["id"], "kind": case["kind"],
                     "acceptable": case["acceptable"], "native": native_result, "jev": jev_result})
    paired_attempts = [row for row in rows if row["native"]["status"] != "unmeasured" and
                       row["jev"]["status"] != "unmeasured"]
    paired = [row for row in paired_attempts if row["native"]["status"] == "measured" and
              row["jev"]["status"] == "measured"]
    paired_summary = {
        "both_supplied": len(paired_attempts),
        "both_measured": len(paired),
        "with_failure": sum(row["native"]["status"] == "failure" or
                            row["jev"]["status"] == "failure" for row in paired_attempts),
        "same_choice": sum(row["native"]["choice"] == row["jev"]["choice"] for row in paired),
        "both_match": sum(row["native"]["match"] and row["jev"]["match"] for row in paired),
        "native_only_match": sum(row["native"]["match"] and not row["jev"]["match"] for row in paired),
        "jev_only_match": sum(row["jev"]["match"] and not row["native"]["match"] for row in paired),
        "neither_match": sum(not row["native"]["match"] and not row["jev"]["match"] for row in paired),
    }
    return {
        "schema_version": 1,
        "benchmark": fixture["benchmark"],
        "benchmark_sha256": _canonical_digest(fixture),
        "network": False,
        "measurement": "Skill choice only. This does not measure downstream task success.",
        "native_provenance": native["provenance"],
        "jev_provenance": jev["provenance"],
        "summary": {"native": _summary(rows, "native"), "jev": _summary(rows, "jev"),
                    "paired": paired_summary},
        "cases": rows,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline native-host and Jev skill-picker comparison")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare", help="create an unlabelled prompt pack")
    prepare_parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    prepare_parser.add_argument("--output", type=Path, required=True)
    compare_parser = sub.add_parser("compare", help="compare two explicitly captured result files")
    compare_parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    compare_parser.add_argument("--native-results", type=Path, required=True)
    compare_parser.add_argument("--jev-results", type=Path, required=True)
    compare_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        fixture = load_fixture(args.fixture)
        if args.command == "prepare":
            manifest = prepare(fixture, args.output)
            print(json.dumps({"output": str(args.output), "benchmark_sha256": manifest["benchmark_sha256"],
                              "tasks": len(manifest["tasks"]), "network": False}, ensure_ascii=True))
        else:
            digest = _canonical_digest(fixture)
            case_ids = {case["id"] for case in fixture["cases"]}
            choices = {item["id"] for item in fixture["candidates"]} | SPECIAL_CHOICES
            native = load_capture(args.native_results, "native_host", digest, case_ids, choices)
            jev = load_capture(args.jev_results, "jev", digest, case_ids, choices)
            report = compare(fixture, native, jev)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            _write_json(args.output, report)
            print(json.dumps({"output": str(args.output), "summary": report["summary"],
                              "network": False}, ensure_ascii=True))
    except (OSError, ValueError, TypeError, OverflowError, RecursionError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
