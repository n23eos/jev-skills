"""Private local opt-in state and prompt-free usage records."""

import json
import math
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone

from .core import MODEL_SIZES, QUESTIONS, DecisionError


def home() -> Path:
    return Path(os.environ.get("JEV_SKILLS_HOME", str(Path.home() / ".config" / "jev-skills"))).expanduser()


def state(root: Path) -> dict:
    try:
        value = json.loads((root / "settings.json").read_text(encoding="utf-8"))
        enabled = value.get("enabled", {})
        if not isinstance(enabled, dict):
            return {}
        return {name: enabled.get(name) is True for name in QUESTIONS}
    except (OSError, ValueError, AttributeError):
        return {}


def toggle(root: Path, workflow: str, enabled: bool) -> dict:
    if workflow not in {*QUESTIONS, "all"}:
        raise DecisionError("unknown_workflow")
    settings = state(root)
    for name in QUESTIONS if workflow == "all" else [workflow]:
        settings[name] = enabled
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, name = tempfile.mkstemp(dir=root, prefix=".settings-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"enabled": settings}, stream)
        os.replace(name, root / "settings.json")
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return settings


def record(root: Path, result: dict) -> bool:
    event = {key: result.get(key) for key in ("workflow", "route", "model_size", "calls", "completed_calls", "unaccounted_calls", "usage", "elapsed_ms", "estimated_known_cost_usd", "cost_complete")}
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    # No input text, candidate IDs, paths or content is persisted.
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(root / "usage.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(event, allow_nan=False) + "\n")
        return True
    except (OSError, ValueError, TypeError):
        return False


def status(root: Path) -> dict:
    enabled = state(root)
    result = {"enabled": {key: enabled.get(key, False) for key in QUESTIONS}, "calls": 0,
              "input_tokens": 0, "output_tokens": 0, "unaccounted_calls": 0,
              "recommendations_by_workflow": {key: 0 for key in QUESTIONS},
              "recommendations_by_model_size": {key: 0 for key in MODEL_SIZES},
              "estimated_known_cost_usd": 0.0, "cost_complete": True}
    try:
        with (root / "usage.jsonl").open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    value = json.loads(line)
                    if not isinstance(value, dict) or value.get("workflow") not in QUESTIONS:
                        result["cost_complete"] = False
                        continue
                    for key in ("calls", "unaccounted_calls"):
                        n = value.get(key, 0)
                        valid = type(n) is int and 0 <= n <= 1_000_000_000
                        result[key] += n if valid else 0
                        result["cost_complete"] &= valid
                    usage = value.get("usage") or {}
                    if isinstance(usage, dict):
                        for key in ("input_tokens", "output_tokens"):
                            n = usage.get(key, 0)
                            valid = type(n) is int and 0 <= n <= 1_000_000_000_000
                            result[key] += n if valid else 0
                            result["cost_complete"] &= valid
                    else:
                        result["cost_complete"] = False
                    if value.get("route") == "recommendation":
                        result["recommendations_by_workflow"][value["workflow"]] += 1
                        size = value.get("model_size")
                        if value["workflow"] == "model" and isinstance(size, str) and size in MODEL_SIZES:
                            result["recommendations_by_model_size"][size] += 1
                    cost = value.get("estimated_known_cost_usd")
                    if type(cost) in (float, int) and 0 <= cost <= 1_000_000 and math.isfinite(cost):
                        result["estimated_known_cost_usd"] += cost
                    else:
                        result["cost_complete"] = False
                    result["cost_complete"] &= value.get("cost_complete") is True
                except (ValueError, TypeError):
                    result["cost_complete"] = False
    except FileNotFoundError:
        pass
    except OSError:
        result["cost_complete"] = False
        result["metrics_error"] = "unreadable"
    result["estimated_known_cost_usd"] = round(result["estimated_known_cost_usd"], 10)
    result["cost_note"] = "Estimate, not a bill. Jev 1.13.0: $0.042/M input, output free; checked 2026-09-22. Failed calls may still be billed."
    return result
