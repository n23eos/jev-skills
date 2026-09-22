"""Transactional, ownership-checked installation of the bundled skills."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid

from . import __version__
from .core import DecisionError


MANIFEST = ".jev-skills-install.json"
LEGACY_INSTALLS = "legacy_installs.json"
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def destination_for(agent: str, destination: Path | None = None) -> Path:
    if agent not in ("codex", "claude"):
        raise DecisionError("unknown_agent")
    target = Path(destination) if destination is not None else Path.home() / (
        ".agents" if agent == "codex" else ".claude") / "skills"
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise DecisionError("unsafe_destination")
    return target


def _files(folder: Path) -> dict[str, str]:
    if folder.is_symlink() or not folder.is_dir():
        raise DecisionError("unsafe_skill_directory")
    result = {}
    for root, directories, files in os.walk(folder, followlinks=False):
        for name in directories + files:
            path = Path(root) / name
            if path.is_symlink():
                raise DecisionError("unsafe_skill_symlink")
        for name in files:
            path = Path(root) / name
            if not path.is_file():
                raise DecisionError("unsafe_skill_file")
            result[path.relative_to(folder).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def packaged_skills() -> dict[str, dict[str, str]]:
    root = Path(__file__).parent / "skills"
    folders = sorted(path for path in root.iterdir() if path.is_dir() and not path.is_symlink())
    if len(folders) != 7 or any(not (folder / "SKILL.md").is_file() for folder in folders):
        raise DecisionError("incomplete_package")
    return {folder.name: _files(folder) for folder in folders}


def _safe_relative(value: str) -> bool:
    return (isinstance(value, str) and bool(value) and "\\" not in value
            and all(part not in ("", ".", "..") for part in value.split("/"))
            and not value.startswith("/"))


def _legacy_files(names: set[str]) -> dict[str, dict[str, str]]:
    """Known unmodified v0.1 files, bundled so upgrades do not need Git."""
    try:
        value = json.loads((Path(__file__).parent / LEGACY_INSTALLS).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DecisionError("invalid_legacy_catalog") from error
    if (not isinstance(value, dict) or value.get("schema") != 1
            or value.get("package_version") != "0.1.0"
            or value.get("source_commit") != "168374dd8238771f595f2cc91237a7085bc88ac6"
            or not isinstance(value.get("skills"), dict)
            or set(value["skills"]) != names):
        raise DecisionError("invalid_legacy_catalog")
    for files in value["skills"].values():
        if (not isinstance(files, dict) or set(files) != {"SKILL.md"}
                or not isinstance(files["SKILL.md"], str)
                or not _HASH.fullmatch(files["SKILL.md"])):
            raise DecisionError("invalid_legacy_catalog")
    return value["skills"]


def read_manifest(target: Path, agent: str, names: set[str]) -> dict | None:
    path = target / MANIFEST
    if path.is_symlink():
        raise DecisionError("unsafe_install_manifest")
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DecisionError("invalid_install_manifest") from error
    if (not isinstance(value, dict) or value.get("schema") != 1
            or value.get("agent") != agent or not isinstance(value.get("package_version"), str)
            or not isinstance(value.get("skills"), dict)
            or set(value["skills"]) != names):
        raise DecisionError("invalid_install_manifest")
    for name, files in value["skills"].items():
        if not isinstance(files, dict) or "SKILL.md" not in files:
            raise DecisionError("invalid_install_manifest")
        for relative, digest in files.items():
            if not _safe_relative(relative) or not isinstance(digest, str) or not _HASH.fullmatch(digest):
                raise DecisionError("invalid_install_manifest")
    return value


def inspect_install(agent: str, destination: Path | None = None) -> dict:
    """Read-only ownership status; never follows a skill or manifest symlink."""
    target = destination_for(agent, destination)
    source = packaged_skills()
    names = set(source)
    try:
        manifest = read_manifest(target, agent, names)
    except DecisionError:
        return {"status": "invalid_manifest", "manifest": True, "missing": [],
                "modified": [], "extra_count": 0, "installed_count": 0}
    missing, modified, extra = [], [], []
    for name in sorted(names):
        folder = target / name
        if folder.is_symlink():
            modified.append(name)
            continue
        if not folder.exists():
            missing.append(name)
            continue
        try:
            current = _files(folder)
        except DecisionError:
            modified.append(name)
            continue
        expected = manifest["skills"][name] if manifest else source[name]
        if any(current.get(path) != digest for path, digest in expected.items()):
            modified.append(name)
        extra.extend(f"{name}/{path}" for path in current.keys() - expected.keys())
    status = "managed" if manifest else "unmanaged"
    if missing or modified:
        status = "incomplete" if manifest else "unmanaged"
    elif manifest and manifest["skills"] != source:
        status = "upgrade_available"
    return {"status": status, "manifest": manifest is not None, "missing": missing,
            "modified": modified, "extra_count": len(extra), "installed_count": 7 - len(missing),
            "package_version": manifest["package_version"] if manifest else None}


def _preflight(target: Path, source: dict, manifest: dict | None,
               upgrade: bool) -> tuple[str, dict | None, bool]:
    present = [(target / name).exists() or (target / name).is_symlink() for name in source]
    if manifest is None:
        if not any(present):
            return "installed", None, False
        if not all(present):
            raise DecisionError("unowned_skill_conflict")
        current = {name: _files(target / name) for name in source}
        if current == source:
            return "adopted", None, False
        if upgrade:
            legacy = _legacy_files(set(source))
            if current == legacy:
                return "upgraded", legacy, True
        raise DecisionError("unowned_skill_conflict")
    for name, installed in manifest["skills"].items():
        current = _files(target / name)
        if any(current.get(path) != digest for path, digest in installed.items()):
            raise DecisionError("modified_installed_skill")
        # An update must never replace a user-added path with a new packaged file.
        if (current.keys() - installed.keys()) & source[name].keys():
            raise DecisionError("unowned_skill_conflict")
    if all(manifest["skills"][name] == source[name] for name in source):
        return "unchanged", manifest["skills"], False
    if not upgrade:
        raise DecisionError("upgrade_required")
    return "upgraded", manifest["skills"], False


def install_skills(agent: str, destination: Path | None = None, upgrade: bool = False) -> dict:
    target = destination_for(agent, destination)
    source = packaged_skills()
    manifest = read_manifest(target, agent, set(source))
    status, owned, legacy_migration = _preflight(target, source, manifest, upgrade)
    result = {"agent": agent, "destination": str(target), "status": status,
              "installed": [str(target / name) for name in source], "package_version": __version__}
    if status == "unchanged":
        return result

    # Staging contains only paths written by this operation. Existing directories are
    # renamed into a retained backup, including user-added files, before replacement.
    target.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".jev-skills-stage-", dir=target))
    backup = target / (".jev-skills-backup-" + uuid.uuid4().hex)
    replaced = []
    installed = []
    rollback_failed = False
    try:
        if status != "adopted":
            for name in source:
                staged = stage / name
                if status == "upgraded":
                    shutil.copytree(target / name, staged, symlinks=True)
                    staged_hashes = _files(staged)
                    if any(staged_hashes.get(path) != digest
                           for path, digest in owned[name].items()):
                        raise DecisionError("modified_installed_skill")
                    if legacy_migration and staged_hashes != owned[name]:
                        raise DecisionError("unowned_skill_conflict")
                    if (staged_hashes.keys() - owned[name].keys()) & source[name].keys():
                        raise DecisionError("unowned_skill_conflict")
                    for relative in source[name]:
                        destination_file = staged / relative
                        destination_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(Path(__file__).parent / "skills" / name / relative, destination_file)
                else:
                    shutil.copytree(Path(__file__).parent / "skills" / name, staged)
        new_manifest = {"schema": 1, "agent": agent, "package_version": __version__, "skills": source}
        (stage / MANIFEST).write_text(json.dumps(new_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if status == "upgraded":
            backup.mkdir()
            for name in [*source, *([] if legacy_migration else [MANIFEST])]:
                os.replace(target / name, backup / name)
                replaced.append(name)
        for name in ([*source] if status != "adopted" else []) + [MANIFEST]:
            # No unexpected target is replaced, even if it appeared during staging.
            if (target / name).exists() or (target / name).is_symlink():
                raise DecisionError("concurrent_install_conflict")
            os.replace(stage / name, target / name)
            installed.append(name)
    except (OSError, DecisionError):
        for name in reversed(installed):
            try:
                os.rename(target / name, stage / name)
            except OSError:
                rollback_failed = True
        for name in reversed(replaced):
            try:
                os.rename(backup / name, target / name)
            except OSError:
                rollback_failed = True
        if rollback_failed:
            raise DecisionError(f"install_rollback_incomplete_recover_from:{backup}:{stage}")
        raise
    finally:
        if not rollback_failed:
            shutil.rmtree(stage, ignore_errors=True)
            if backup.exists() and not any(backup.iterdir()):
                backup.rmdir()
    if status == "upgraded":
        result["backup"] = str(backup)
        if legacy_migration:
            result["migrated_from"] = "0.1.0"
    return result
