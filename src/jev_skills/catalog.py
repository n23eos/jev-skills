"""Inventory only explicitly supplied skill roots; never scan plugin caches."""

import hashlib
import json
from pathlib import Path
import re
import shutil

from .core import DecisionError

MAX_SKILL_BYTES = 64 * 1024
MAX_DESCRIPTION = 4000


def _metadata(path: Path) -> tuple[str, str, bytes]:
    """Read a bounded skill file and its simple YAML scalar frontmatter."""
    if path.stat().st_size > MAX_SKILL_BYTES:
        raise DecisionError("skill_file_too_large")
    with path.open("rb") as stream:
        raw = stream.read(MAX_SKILL_BYTES + 1)
    if len(raw) > MAX_SKILL_BYTES:
        raise DecisionError("skill_file_too_large")
    try:
        lines = raw.decode("utf-8-sig").splitlines()
    except UnicodeError as error:
        raise DecisionError("invalid_skill_encoding") from error
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise DecisionError("missing_frontmatter")
    header = lines[1:lines.index("---", 1)]
    fields: dict[str, str] = {}
    for index, line in enumerate(header):
        match = re.match(r"^(name|description):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        following = []
        for continuation in header[index + 1:]:
            if continuation and not continuation[0].isspace():
                break
            following.append(continuation.strip())
        if not value.startswith(("|", ">")):
            while following and not following[-1]:
                following.pop()
        if value in ("|", ">", "|-", ">-", "|+", ">+"):
            value = (" " if value.startswith(">") else "\n").join(following)
        elif value.startswith('"'):
            combined = value + (" " + " ".join(following) if following else "")
            try:
                value, end = json.JSONDecoder().raw_decode(combined)
            except (ValueError, TypeError) as error:
                raise DecisionError("unsupported_skill_metadata") from error
            if not isinstance(value, str) or combined[end:].strip() and not combined[end:].lstrip().startswith("#"):
                raise DecisionError("unsupported_skill_metadata")
        elif value.startswith("'"):
            combined = value + (" " + " ".join(following) if following else "")
            quoted = re.fullmatch(r"'((?:[^']|'')*)'(?:\s+#.*)?", combined)
            if not quoted:
                raise DecisionError("unsupported_skill_metadata")
            value = quoted.group(1).replace("''", "'")
        elif value.startswith(("[", "{", "&", "*", "!")) or not value and following:
            raise DecisionError("unsupported_skill_metadata")
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
            if following:
                value += " " + " ".join(following)
        fields[key] = " ".join(value.split())
    name = fields.get("name") or path.parent.name
    description = fields.get("description", "")
    if not name or not description:
        raise DecisionError("missing_name_or_description")
    if len(name) > 256 or len(description) > MAX_DESCRIPTION:
        raise DecisionError("skill_metadata_too_large")
    return name, description, raw


def manifest(path: Path) -> tuple[str, str]:
    name, description, _ = _metadata(path)
    return name, description


def catalog(roots: list[Path]) -> dict:
    entries, skipped, seen = [], [], set()
    for root in roots:
        root = root.expanduser().resolve()
        if not root.is_dir():
            raise DecisionError("skill_root_not_found")
        # Skills are immediate child directories, including symlinked skills.
        for folder in sorted(root.iterdir()):
            if folder.name.startswith(".") or folder.name == "!notes":
                continue
            path = folder / "SKILL.md"
            if not path.is_file() or path.resolve() in seen:
                continue
            seen.add(path.resolve())
            try:
                name, description = manifest(path)
                identifier = re.sub(r"[^A-Za-z0-9_.:/-]", "-", name).strip("-/")[:90]
                if not identifier or identifier == "none" or not identifier[0].isalnum():
                    identifier = "skill-" + identifier
                entries.append({"id": identifier, "name": name, "description": description,
                                "path": str(path.resolve())})
            except (OSError, ValueError) as error:
                reason = str(error) if isinstance(error, DecisionError) else "unreadable_skill"
                skipped.append({"path": str(path), "reason": reason})
    counts = {}
    for entry in entries:
        counts[entry["id"]] = counts.get(entry["id"], 0) + 1
    occupied = set()
    for entry in entries:
        identifier = entry["id"]
        if counts[identifier] > 1:
            identifier = identifier[:78].rstrip("-./:") + "-" + hashlib.sha256(entry["path"].encode()).hexdigest()[:10]
        while identifier in occupied:
            identifier = identifier[:78].rstrip("-./:") + "-" + hashlib.sha256((entry["path"] + identifier).encode()).hexdigest()[:10]
        entry["id"] = identifier
        occupied.add(identifier)
    return {"candidates": entries, "skipped": skipped,
            "note": "Review this local inventory against the host's enabled skills. Paths are not sent by decide. Only selected roots were scanned."}


def install(agent: str, destination: Path | None = None) -> list[str]:
    if agent not in {"codex", "claude"}:
        raise DecisionError("unknown_agent")
    target = destination or (Path.home() / (".agents" if agent == "codex" else ".claude") / "skills")
    source = Path(__file__).parent / "skills"
    folders = sorted(folder for folder in source.iterdir() if (folder / "SKILL.md").is_file())
    if len(folders) != 7:
        raise DecisionError("incomplete_package")
    for folder in folders:
        if (target / folder.name).exists() or (target / folder.name).is_symlink():
            raise DecisionError("skill_already_exists_install_aborted")
    target.mkdir(parents=True, exist_ok=True)
    for folder in folders:
        shutil.copytree(folder, target / folder.name)
    return [str(target / folder.name) for folder in folders]
