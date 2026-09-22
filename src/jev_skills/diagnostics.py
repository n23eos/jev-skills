"""Offline, non-executing environment diagnostics."""

import os
import shutil
import sys
from pathlib import Path

from .core import DecisionError, QUESTIONS
from .installation import destination_for, inspect_install
from .storage import home, state


def doctor(agent: str | None = None, destination: Path | None = None) -> dict:
    """Report presence only; do not validate credentials or execute host binaries."""
    if agent is not None and agent not in ("codex", "claude"):
        raise DecisionError("unknown_agent")
    if agent is None and destination is not None:
        raise DecisionError("agent_required_for_destination")
    enabled = state(home())
    result = {
        "python_supported": sys.version_info >= (3, 10),
        "curl_available": shutil.which("curl") is not None,
        "jev_skills_on_path": shutil.which("jev-skills") is not None,
        "typesafe_api_key_present": bool(os.environ.get("TYPESAFE_API_KEY")),
        "enabled": {name: enabled.get(name, False) for name in QUESTIONS},
        "agents": {},
        "note": "Offline presence checks only; API key validity and authentication are not verified.",
    }
    for name in ([agent] if agent else ["codex", "claude"]):
        target = destination_for(name, destination if name == agent else None)
        result["agents"][name] = {"binary_available": shutil.which(name) is not None,
                                  "destination": str(target), "skills": inspect_install(name, target)}
    return result
