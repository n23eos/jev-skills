"""Local-only skill selection handoff; no skill body or path enters Jev input."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re

from .catalog import MAX_SKILL_BYTES, _metadata, catalog
from .core import DecisionError, validate_input


def prepare_skills(request: str, roots: list[Path], exclude: list[str] = (),
                   allowed_ids: set[str] | None = None) -> tuple[dict, dict]:
    """Build typed candidate input and a separate, local identity map."""
    inventory = catalog(roots)
    excluded = {value.casefold() for value in exclude} | {"jev-skill-picker"}
    candidates, mapping = [], {}
    for entry in inventory["candidates"]:
        if entry["id"].casefold() in excluded or entry["name"].casefold() in excluded:
            continue
        if allowed_ids is not None and entry["id"] not in allowed_ids:
            continue
        path = Path(entry["path"])
        try:
            _, _, raw = _metadata(path)
        except (OSError, ValueError):
            continue
        identifier = entry["id"]
        candidates.append({"id": identifier, "description": entry["description"]})
        mapping[identifier] = {"path": str(path), "name": entry["name"],
                               "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    if not candidates:
        raise DecisionError("no_eligible_skills")
    # validate_input intentionally drops all local metadata before core.select.
    return validate_input({"request": request, "candidates": candidates}), mapping


def attach_selection(result: dict, mapping: dict, agent: str = "codex") -> dict:
    """Attach only an exact local path to a completed recommendation."""
    if agent not in {"codex", "claude"}:
        raise DecisionError("unknown_agent")
    attached = dict(result)
    if result.get("route") != "recommendation":
        return attached
    identifier = result.get("selected")
    if not isinstance(identifier, str) or identifier not in mapping:
        raise DecisionError("selected_skill_not_in_catalog")
    item = mapping[identifier]
    name = item["name"]
    attached["selected_skill"] = {"id": identifier, "name": name, "path": item["path"],
                                  "size": item["size"], "sha256": item["sha256"],
                                  "invocation": ("$" if agent == "codex" else "/") + name}
    attached["next_action"] = "read_skill_then_apply"
    return attached


def load_selected(result: dict, mapping: dict, max_bytes: int = MAX_SKILL_BYTES) -> str:
    """Read only a selected, unchanged skill file after explicit host opt-in."""
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_SKILL_BYTES:
        raise DecisionError("invalid_skill_read_limit")
    if result.get("route") != "recommendation":
        raise DecisionError("no_selected_skill")
    identifier = result.get("selected")
    if not isinstance(identifier, str) or identifier not in mapping:
        raise DecisionError("selected_skill_not_in_catalog")
    item = mapping[identifier]
    path = Path(item["path"])
    try:
        if path.stat().st_size > max_bytes or item["size"] > max_bytes:
            raise DecisionError("skill_file_too_large")
        with path.open("rb") as stream:
            raw = stream.read(max_bytes + 1)
    except OSError as error:
        raise DecisionError("selected_skill_unreadable") from error
    if len(raw) > max_bytes or len(raw) != item["size"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
        raise DecisionError("selected_skill_changed")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeError as error:
        raise DecisionError("invalid_skill_encoding") from error


def contextual_followup(request: str) -> bool:
    """Conservative standalone local gate for clearly context-dependent replies."""
    text = request.strip().casefold()
    if not text or len(text) > 240:
        return False
    # An explicit task is allowed even if it is short.
    if re.match(r"^(?:fix|debug|translate|write|create|implement|исправь|переведи|напиши|создай)\s+", text):
        return False
    if re.fullmatch(r"(?:yes|yeah|yep|no|ok|okay|sure|да|нет|ага|угу|ок|хорошо)[.!?\s]*", text):
        return True
    if re.match(r"^(?:use|choose|pick|выбери|используй|возьми)\s+(?:the\s+)?(?:first|second|third|last|previous|первый|второй|третий|последний|предыдущий)(?:\s+one|\s+вариант)?[.!?\s]*$", text):
        return True
    cue = r"(?:\b(?:that|this|it|one|above|previous|same|shorter|longer)\b|(?:это|этот|эту|того|так|выше|предыдущ|короче|покороче))"
    acknowledgement = r"^(?:yes|yeah|yep|ok|okay|sure|да|ага|угу|ок|хорошо)[,!.\s]+"
    if re.search(cue, text) and (re.match(acknowledgement, text) or re.match(r"^(?:do|make|use|сделай|делай|используй|выбери|возьми)\b", text)):
        return True
    return False
