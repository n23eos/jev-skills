"""Offline, non-executing environment diagnostics."""

import os
import shlex
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


def human_report(result: dict) -> str:
    """Explain offline checks without changing their structured contract."""
    lines = ["Jev Skills setup (offline)"]
    checks = (
        ("python_supported", "Python 3.10+", "Install Python 3.10 or newer, then reinstall the CLI."),
        ("curl_available", "curl", "Install curl and make it available on the agent's PATH."),
        ("jev_skills_on_path", "jev-skills command", "Install the CLI with uv tool install 'git+https://github.com/n23eos/jev-skills.git'. If already installed, run uv tool update-shell and restart the agent from that environment."),
        ("typesafe_api_key_present", "TypeSafe key in this process", "Set TYPESAFE_API_KEY in the environment that starts your agent, then restart it. Do not paste the key into chat. Offline preview works without a key."),
    )
    for key, label, action in checks:
        present = result[key]
        lines.append(f"[{'OK' if present else 'SETUP'}] {label}: {'present' if present else 'missing'}")
        if not present:
            lines.append("  Next: " + action)
    for agent, value in result["agents"].items():
        skills = value["skills"]
        lines.append(f"\n{agent}: {value['destination']}")
        if value["binary_available"]:
            lines.append("[OK] Host CLI found; login and native skill discovery have not been checked.")
        else:
            lines.append("[INFO] Host CLI not found. It is needed for CLI helpers, not for copying skills or using a desktop host.")
            lines.append("  Next: if you want CLI helpers, install and authenticate that host through its normal setup.")
        state = skills["status"]
        if state == "managed" and not skills.get("missing") and not skills.get("modified"):
            lines.append(f"[OK] {skills.get('installed_count', 0)} managed skills verified.")
            invocation = ("$" if agent == "codex" else "/") + "jev-controls"
            lines.append(f"  Next: restart or refresh the host, then invoke {invocation} to check discovery.")
        else:
            lines.append(f"[SETUP] Skills: {state}; missing: {len(skills.get('missing', []))}; modified: {len(skills.get('modified', []))}.")
            if skills.get("modified") or (state not in {"managed", "upgrade_available"} and skills.get("installed_count", 0)) or state == "invalid_manifest":
                lines.append("  Next: review the existing files; keep your edits. Use a fresh --dest directory if the installation conflicts.")
            else:
                lines.append(f"  Next: run jev-skills install --agent {agent} --dest " + shlex.quote(value['destination']) + " (use --upgrade for an existing managed installation).")
    enabled = [name for name, value in result["enabled"].items() if value]
    lines.append("\nAutomatic workflows: " + (", ".join(enabled) if enabled else "all off") + ". Enabling does not install a host hook.")
    lines.append("No network request was made. Key validity, host login and native skill discovery are unverified.")
    return "\n".join(lines)
