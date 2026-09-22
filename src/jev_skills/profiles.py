"""Explicit, portable model profiles. Configuration is not an availability check."""

from __future__ import annotations

import re

from .core import DecisionError, MODEL_SIZES, validate_input

AGENTS = ("codex", "claude")
EFFORTS = {
    "codex": ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"),
    "claude": ("low", "medium", "high", "xhigh", "max"),
}


def validate_host_model(agent: str, model: str, effort: str | None = None) -> None:
    """Validate values as data, without inferring account access or capability."""
    if agent not in AGENTS:
        raise DecisionError("unsupported_host")
    if (not isinstance(model, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}", model)
            or model == "none"):
        raise DecisionError("invalid_host_model")
    if effort is not None and effort not in EFFORTS[agent]:
        raise DecisionError("invalid_host_effort")


def prepare_model_input(request: str, profile: dict) -> tuple[dict, dict]:
    """Return core input and local handoff metadata, preserving user cost order.

    Profiles contain one host and one to four user-confirmed model identifiers.
    No bundled model names, prices, inferred availability, or commands are used.
    The caller should explain that the user's ordering means cheapest first.
    """
    if not isinstance(profile, dict) or set(profile) != {"agent", "models"}:
        raise DecisionError("invalid_model_profile")
    agent, models = profile["agent"], profile["models"]
    if agent not in AGENTS:
        raise DecisionError("unsupported_host")
    if not isinstance(models, list) or not 1 <= len(models) <= 4:
        raise DecisionError("invalid_profile_model_count")
    candidates, mapping = [], {}
    for entry in models:
        if (not isinstance(entry, dict)
                or not {"id", "size", "description"} <= set(entry)
                or set(entry) - {"id", "size", "description", "effort"}):
            raise DecisionError("invalid_profile_model")
        validate_host_model(agent, entry["id"], entry.get("effort"))
        if entry["size"] not in MODEL_SIZES:
            raise DecisionError("invalid_model_size")
        if entry["id"] in mapping:
            raise DecisionError("duplicate_profile_model")
        candidates.append({key: entry[key] for key in ("id", "size", "description")})
        mapping[entry["id"]] = {"agent": agent, **entry}
    return validate_input({"request": request, "candidates": candidates}), mapping
