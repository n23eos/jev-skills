"""Explicit live trials and off-by-default automatic advisory selection."""

import argparse
import json
import os
from pathlib import Path
import sys

from .catalog import catalog
from .installation import install_skills
from .diagnostics import doctor, human_report
from .skill_selection import prepare_skills, attach_selection, load_selected, contextual_followup
from .profiles import prepare_model_input
from .hosts import run_helper
from .core import Client, DecisionError, QUESTIONS, group_requests, fallback, number, select, validate_input
from .storage import home, record, state, status, toggle
from .advisory_workflows import prepare_input


def emit(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Advisory Jev decisions. Separate helper execution requires explicit --execute.")
    sub = result.add_subparsers(dest="command", required=True)
    choose = sub.add_parser("decide")
    choose.add_argument("workflow", choices=tuple(QUESTIONS))
    choose.add_argument("--input", required=True, help="JSON file; use - for stdin")
    mode = choose.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true", help="explicit one-time TypeSafe request, independent of toggles")
    mode.add_argument("--automatic", action="store_true", help="only call TypeSafe if this workflow is enabled")
    choose.add_argument("--private", action="store_true", help="force local fallback without reading input")
    choose.add_argument("--follow-up", action="store_true", help="keep contextual replies with their current agent")
    choose.add_argument("--timeout", type=float, default=3.0, help="overall evaluation budget in seconds (default: 3)")
    choose.add_argument("--threshold", type=float, default=0.6)
    choose.add_argument("--batch-size", type=int, default=128)
    for command in ("enable", "disable"):
        sub.add_parser(command).add_argument("workflow", choices=(*QUESTIONS, "all"))
    sub.add_parser("status")
    sample = sub.add_parser("example", help="print a packaged public input without network requests")
    sample.add_argument("workflow", choices=("citation", "ci", "review", "tool", "issue", "value", "eval-gap"))
    inventory = sub.add_parser("catalog")
    inventory.add_argument("--root", action="append", type=Path, required=True)
    inventory.add_argument("--output", type=Path)
    setup = sub.add_parser("install")
    setup.add_argument("--agent", choices=("codex", "claude"), required=True)
    setup.add_argument("--dest", type=Path)
    setup.add_argument("--upgrade", action="store_true")
    diagnose = sub.add_parser("doctor", help="check local setup without network requests")
    diagnose.add_argument("--agent", choices=("codex", "claude"))
    diagnose.add_argument("--dest", type=Path)
    diagnose.add_argument("--format", choices=("json", "human"), default="json",
                          help="human explanations or backward-compatible JSON (default)")
    for command in ("pick-skill", "route-model"):
        direct = sub.add_parser(command)
        request = direct.add_mutually_exclusive_group(required=True)
        request.add_argument("--request")
        request.add_argument("--request-file", help="UTF-8 file or - for stdin")
        modes = direct.add_mutually_exclusive_group()
        modes.add_argument("--live", action="store_true")
        modes.add_argument("--automatic", action="store_true")
        direct.add_argument("--private", action="store_true")
        direct.add_argument("--follow-up", action="store_true")
        direct.add_argument("--timeout", type=float, default=3.0)
        direct.add_argument("--threshold", type=float, default=0.6)
        direct.add_argument("--batch-size", type=int, default=128)
        if command == "pick-skill":
            direct.add_argument("--root", action="append", type=Path, required=True)
            direct.add_argument("--exclude", action="append", default=[])
            direct.add_argument("--agent", choices=("codex", "claude"), default="codex")
            direct.add_argument("--reviewed-catalog", action="store_true")
            direct.add_argument("--catalog-digest", help="require exact previously reviewed candidate metadata")
            direct.add_argument("--show-skill", action="store_true")
        else:
            direct.add_argument("--profile", type=Path, required=True)
            direct.add_argument("--execute", action="store_true", help="explicitly run a supplied-text helper after an accepted live choice")
            direct.add_argument("--helper-timeout", type=float, default=60.0)
    integration = sub.add_parser("integrate")
    integration.add_argument("--agent", choices=("codex", "claude"), required=True)
    integration.add_argument("--project", type=Path, required=True)
    integration.add_argument("--root", action="append", type=Path, default=[])
    integration.add_argument("--profile", type=Path)
    integration.add_argument("--workflow", choices=("skill", "model"), default="skill")
    integration.add_argument("--reviewed-catalog", action="store_true")
    return result


def read_text(filename: str) -> str:
    if filename == "-":
        value = sys.stdin.read(200_001)
    else:
        with Path(filename).open(encoding="utf-8") as stream:
            value = stream.read(200_001)
    if len(value.encode("utf-8")) > 200_000:
        raise DecisionError("input_too_large")
    return value


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    root = home()
    coverage = None
    try:
        if args.command == "example":
            emit(json.loads((Path(__file__).parent / "examples" / (args.workflow + ".json")).read_text(encoding="utf-8")))
        elif args.command == "status":
            emit(status(root))
        elif args.command in {"enable", "disable"}:
            emit({"enabled": toggle(root, args.workflow, args.command == "enable"),
                  "notice": "Enabled automatic decisions send supplied requests, context and candidate descriptions to api.typesafe.ai. No host hook is installed."})
        elif args.command == "install":
            emit(install_skills(args.agent, args.dest, upgrade=args.upgrade))
        elif args.command == "doctor":
            result = doctor(args.agent, args.dest)
            if args.format == "human":
                print(human_report(result))
            else:
                emit(result)
        elif args.command == "integrate":
            from .integration import integrate
            emit(integrate(args.agent, args.project, args.root, profile=args.profile,
                           workflow=args.workflow, reviewed_catalog=args.reviewed_catalog))
        elif args.command == "catalog":
            value = catalog(args.root)
            if args.output:
                # Never silently replace a reviewed user catalog.
                with args.output.open("x", encoding="utf-8") as stream:
                    json.dump(value, stream, ensure_ascii=False, indent=2)
            else:
                emit(value)
        else:
            args.workflow = getattr(args, "workflow", "skill" if args.command == "pick-skill" else "model")
            if os.environ.get("JEV_SKILLS_CHILD") == "1":
                emit(fallback("child_recursion_guard"))
                return 0
            if args.private or args.follow_up:
                emit(fallback("private" if args.private else "contextual_follow_up"))
                return 0
            if args.automatic and not state(root).get(args.workflow, False):
                emit(fallback("disabled"))
                return 0
            mapping = None
            if args.command == "decide":
                data = json.loads(read_text(args.input))
            else:
                request = args.request if args.request is not None else read_text(args.request_file)
                if contextual_followup(request):
                    emit(fallback("contextual_follow_up"))
                    return 0
                if args.command == "pick-skill":
                    if (args.live or args.automatic) and not args.reviewed_catalog:
                        emit(fallback("catalog_review_required"))
                        return 0
                    coverage = {}
                    data, mapping = prepare_skills(request, args.root, exclude=args.exclude, coverage=coverage)
                    if args.catalog_digest:
                        from .integration import reviewed_digest
                        if args.catalog_digest != reviewed_digest(data["candidates"]):
                            emit({**fallback("catalog_changed_review_required"), "catalog_coverage": coverage})
                            return 0
                else:
                    data, mapping = prepare_model_input(request, json.loads(read_text(str(args.profile))))
            prepared_data = prepare_input(args.workflow, data)
            data = validate_input(prepared_data)
            number(args.timeout, 0.05, 60)
            number(args.threshold, 0, 1)
            if args.command == "route-model" and args.execute:
                number(args.helper_timeout, 0.01, 300)
            if not 2 <= args.batch_size <= 254:
                raise DecisionError("invalid_batch_size")
            if not args.live and not args.automatic:
                result = {"mode": "dry_run", "network": False, "requests": group_requests(args.workflow, data, args.batch_size), "note": "Additional final rounds depend on group winners."}
                if coverage is not None:
                    result["catalog_coverage"] = coverage
                emit(result)
                return 0
            result = select(args.workflow, prepared_data, Client(), timeout=args.timeout, threshold=args.threshold, batch_size=args.batch_size)
            result["metrics_saved"] = record(root, result)
            if args.command == "pick-skill":
                result = attach_selection(result, mapping, agent=args.agent)
                result["catalog_coverage"] = coverage
                if args.show_skill and result.get("route") == "recommendation":
                    result["skill_body"] = load_selected(result, mapping)
            elif args.command == "route-model" and args.execute and result.get("route") == "recommendation":
                chosen = mapping[result["selected"]]
                result["helper"] = run_helper(chosen["agent"], chosen["id"], request,
                                              timeout=args.helper_timeout, effort=chosen.get("effort"))
            emit(result)
        return 0
    except (OSError, ValueError, TypeError, OverflowError, RecursionError) as error:
        # Bad input and local I/O failures must not prevent the host handling its task.
        message = str(error) if isinstance(error, DecisionError) else "invalid_input_or_local_io"
        result = fallback(message)
        if coverage is not None:
            result["catalog_coverage"] = coverage
        emit(result)
        return 0 if args.command in {"decide", "pick-skill", "route-model"} else 2
