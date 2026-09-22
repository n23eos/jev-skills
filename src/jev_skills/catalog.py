"""Inventory only explicitly supplied skill roots; never scan plugin caches."""

import hashlib
import json
from pathlib import Path
import re
import shutil

from .core import DecisionError


def manifest(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise DecisionError("missing_frontmatter")
    header = lines[1:lines[1:].index("---") + 1]
    fields = {}
    for i, line in enumerate(header):
        match = re.match(r"^(name|description):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        if value in ("|", ">", "|-", ">-", "|+", ">+", ""):
            parts = []
            for continuation in header[i + 1:]:
                if continuation and not continuation[0].isspace():
                    break
                parts.append(continuation.strip())
            value = " ".join(parts)
        elif value.startswith('"'):
            try:
                value = json.loads(value)
            except ValueError:
                value = value.strip('"')
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1].replace("''", "'")
        fields[key] = " ".join(value.split())
    if not all(fields.get(key) for key in ("name", "description")):
        raise DecisionError("missing_name_or_description")
    return fields["name"], fields["description"]


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
            except (OSError, ValueError):
                skipped.append(str(path))
    counts = {}
    for entry in entries:
        counts[entry["id"]] = counts.get(entry["id"], 0) + 1
    for entry in entries:
        if counts[entry["id"]] > 1:
            entry["id"] += "-" + hashlib.sha256(entry["path"].encode()).hexdigest()[:10]
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
