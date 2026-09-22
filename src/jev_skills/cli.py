"""Explicit live trials and off-by-default automatic advisory selection."""

import argparse
import json
from pathlib import Path
import sys

from .catalog import catalog, install
from .core import Client, DecisionError, QUESTIONS, build_request, fallback, number, select, validate_input
from .storage import home, record, state, status, toggle


def emit(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Advisory Jev decisions. No recommendations are executed.")
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
    inventory = sub.add_parser("catalog")
    inventory.add_argument("--root", action="append", type=Path, required=True)
    inventory.add_argument("--output", type=Path)
    setup = sub.add_parser("install")
    setup.add_argument("--agent", choices=("codex", "claude"), required=True)
    setup.add_argument("--dest", type=Path)
    return result


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    root = home()
    try:
        if args.command == "status":
            emit(status(root))
        elif args.command in {"enable", "disable"}:
            emit({"enabled": toggle(root, args.workflow, args.command == "enable"),
                  "notice": "Enabled automatic decisions send supplied requests, context and candidate descriptions to api.typesafe.ai. No host hook is installed."})
        elif args.command == "install":
            emit({"installed": install(args.agent, args.dest)})
        elif args.command == "catalog":
            value = catalog(args.root)
            if args.output:
                # Never silently replace a reviewed user catalog.
                with args.output.open("x", encoding="utf-8") as stream:
                    json.dump(value, stream, ensure_ascii=False, indent=2)
            else:
                emit(value)
        else:
            if args.private or args.follow_up:
                emit(fallback("private" if args.private else "contextual_follow_up"))
                return 0
            if args.automatic and not state(root).get(args.workflow, False):
                emit(fallback("disabled"))
                return 0
            if args.input == "-":
                data = json.load(sys.stdin)
            else:
                data = json.loads(Path(args.input).read_text(encoding="utf-8"))
            data = validate_input(data)
            number(args.timeout, 0.05, 60)
            number(args.threshold, 0, 1)
            if not 2 <= args.batch_size <= 254:
                raise DecisionError("invalid_batch_size")
            if not args.live and not args.automatic:
                groups = [data["candidates"][i:i + args.batch_size] for i in range(0, len(data["candidates"]), args.batch_size)]
                emit({"mode": "dry_run", "network": False, "requests": [build_request(args.workflow, data, group) for group in groups], "note": "Additional final rounds depend on group winners."})
                return 0
            result = select(args.workflow, data, Client(), timeout=args.timeout, threshold=args.threshold, batch_size=args.batch_size)
            result["metrics_saved"] = record(root, result)
            emit(result)
        return 0
    except (OSError, ValueError, TypeError, OverflowError) as error:
        # Bad input and local I/O failures must not prevent the host handling its task.
        message = str(error) if isinstance(error, DecisionError) else "invalid_input_or_local_io"
        emit(fallback(message))
        return 0 if args.command == "decide" else 2
