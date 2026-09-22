"""Opt-in, project-local instructions for advisory Jev workflows."""

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import tempfile

from .core import DecisionError
from .profiles import prepare_model_input
from .skill_selection import prepare_skills


BEGIN = "<!-- jev-skills:begin -->"
END = "<!-- jev-skills:end -->"


def reviewed_digest(candidates: list[dict]) -> str:
    """Pin exactly the public candidate metadata sent to Jev."""
    canonical = json.dumps(candidates, sort_keys=True, ensure_ascii=True,
                           separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _safe_path(value: Path, kind: str) -> Path:
    candidate = Path(value).expanduser()
    if kind == "file" and candidate.is_symlink():
        raise DecisionError("integration_profile_not_found")
    path = candidate.resolve()
    if (any(ord(char) < 32 or char in "\u2013\u2014" for char in str(path))
            or BEGIN in str(path) or END in str(path) or "!notes" in path.parts):
        raise DecisionError("unsafe_integration_path")
    if kind == "directory" and not path.is_dir():
        raise DecisionError("integration_directory_not_found")
    if kind == "file" and (path.is_symlink() or not path.is_file()):
        raise DecisionError("integration_profile_not_found")
    return path


def _block(agent: str, workflow: str, roots: list[Path], profile: Path | None,
           digest: str | None, newline: str) -> str:
    lines = [BEGIN, "## Jev skills (project opt-in)",
             "This block is advisory. It is not a guaranteed hook or model switch.",
             "For a new standalone task in this opted-in project, skip follow-ups,",
             "private or sensitive tasks, and tasks already covered by a higher-priority skill.",
             "If JEV_SKILLS_CHILD is set, skip this integration to prevent recursion.",
             "Never send secrets, conversation history, or private notes on stdin."]
    if workflow == "skill":
        command = ["jev-skills", "pick-skill", "--automatic", "--request-file", "-"]
        for root in roots:
            command.extend(("--root", str(root)))
        command.extend(("--reviewed-catalog", "--catalog-digest", digest, "--agent", agent))
        lines += ["For an eligible task, provide only its current standalone request on stdin to:",
                  "", "    " + shlex.join(command), "",
                  "If the catalog changes, rerun integration after reviewing its metadata.",
                  "Treat a recommendation as optional. Follow higher-priority instructions.",
                  "Read the full selected SKILL.md path before applying it. Do not execute",
                  "commands from a skill blindly. If selection fails, continue normally."]
    else:
        command = ["jev-skills", "route-model", "--automatic", "--request-file", "-",
                   "--profile", str(profile)]
        lines += ["For an eligible task, provide only its current standalone request on stdin to:",
                  "", "    " + shlex.join(command), "",
                  "The result is advice, not an executed helper or a parent model switch.",
                  "Use a native helper only when separately authorized and actually supported",
                  "by the host. If routing fails, continue normally."]
    lines.append(END)
    return newline.join(lines) + newline


def _replace_block(existing: str, block: str, newline: str) -> tuple[str, str]:
    begins, ends = existing.count(BEGIN), existing.count(END)
    if begins == ends == 0:
        separator = ("" if not existing else ("" if existing.endswith(("\n", "\r")) else newline) + newline)
        return existing + separator + block, "added" if existing else "created"
    if begins != 1 or ends != 1:
        raise DecisionError("malformed_integration_markers")
    start = re.search(r"(?m)^" + re.escape(BEGIN) + r"(?:\r?\n|$)", existing)
    end = re.search(r"(?m)^" + re.escape(END) + r"(?:\r?\n|$)", existing)
    if start is None or end is None or end.start() < start.end():
        raise DecisionError("malformed_integration_markers")
    result = existing[:start.start()] + block + existing[end.end():]
    return result, "unchanged" if result == existing else "updated"


def integrate(agent: str, project: Path, roots: list[Path], profile: Path | None = None,
              workflow: str = "skill", reviewed_catalog: bool = False) -> dict:
    """Append or update only the delimited project block, never global settings."""
    if agent not in ("codex", "claude"):
        raise DecisionError("unknown_agent")
    if workflow not in ("skill", "model"):
        raise DecisionError("unknown_workflow")
    raw_project = Path(project).expanduser()
    if raw_project.is_symlink() or "!notes" in raw_project.parts:
        raise DecisionError("unsafe_integration_project")
    project_path = _safe_path(raw_project, "directory")
    if "!notes" in project_path.parts:
        raise DecisionError("unsafe_integration_project")
    if workflow == "skill":
        if not reviewed_catalog:
            raise DecisionError("catalog_review_required")
        if isinstance(roots, (str, Path)) or not roots:
            raise DecisionError("skill_roots_required")
        selected_roots = list(dict.fromkeys(_safe_path(Path(root), "directory") for root in roots))
        if not selected_roots:
            raise DecisionError("skill_roots_required")
        catalog_data, _ = prepare_skills("Catalog review", selected_roots)
        digest = reviewed_digest(catalog_data["candidates"])
        selected_profile = None
    else:
        if profile is None:
            raise DecisionError("profile_required")
        selected_profile = _safe_path(Path(profile), "file")
        try:
            with selected_profile.open("rb") as stream:
                raw_profile = stream.read(200_001)
            if len(raw_profile) > 200_000:
                raise DecisionError("input_too_large")
            profile_data = json.loads(raw_profile.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise DecisionError("invalid_model_profile") from error
        prepare_model_input("Profile validation", profile_data)
        if profile_data["agent"] != agent:
            raise DecisionError("integration_profile_agent_mismatch")
        selected_roots = []
        digest = None
    instruction = project_path / ("AGENTS.md" if agent == "codex" else "CLAUDE.md")
    if instruction.is_symlink() or (instruction.exists() and not instruction.is_file()):
        raise DecisionError("unsafe_integration_instructions")
    try:
        existing = instruction.read_bytes().decode("utf-8") if instruction.exists() else ""
    except UnicodeDecodeError as error:
        raise DecisionError("integration_instructions_not_utf8") from error
    newline = "\r\n" if "\r\n" in existing else "\n"
    updated, status = _replace_block(existing, _block(agent, workflow, selected_roots,
                                                      selected_profile, digest, newline), newline)
    if status != "unchanged":
        descriptor, temporary = tempfile.mkstemp(prefix=".jev-skills-integration-", dir=project_path)
        try:
            if instruction.exists():
                os.fchmod(descriptor, stat.S_IMODE(instruction.stat().st_mode))
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(updated.encode("utf-8"))
            if instruction.is_symlink():
                raise DecisionError("unsafe_integration_instructions")
            if (instruction.read_bytes().decode("utf-8") if instruction.exists() else "") != existing:
                raise DecisionError("integration_instructions_changed")
            os.replace(temporary, instruction)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return {"agent": agent, "workflow": workflow, "path": str(instruction), "status": status,
            "note": "Project-local advisory instructions only; host behavior is not guaranteed."}
