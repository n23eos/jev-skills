"""Opt-in public-fixture catalog -> skill -> model -> supplied-text helper smoke."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--agent", choices=("codex", "claude"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    with tempfile.TemporaryDirectory(prefix="jev-public-smoke-") as directory:
        root = Path(directory)
        environment = dict(os.environ, JEV_SKILLS_HOME=str(root / "state"))

        def cli(*arguments):
            result = subprocess.run([sys.executable, "-m", "jev_skills", *arguments],
                                    env=environment, text=True, capture_output=True, timeout=90)
            if result.returncode:
                raise RuntimeError("smoke_cli_failed")
            return json.loads(result.stdout)

        for name, description in {
            "python-review": "Review Python functions for correctness defects and edge cases.",
            "react-layout": "Build responsive React page layouts and CSS styling.",
            "docker-build": "Optimize Dockerfiles and container image builds.",
        }.items():
            folder = root / "skills" / name
            folder.mkdir(parents=True)
            (folder / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: {description}\n---\n\n"
                "Use only the supplied text. Explain one concrete issue in one sentence.\n",
                encoding="utf-8")
        task = "Review this Python function for division by zero: def reciprocal(x): return 1/x."
        chosen = cli("pick-skill", "--root", str(root / "skills"), "--request", task,
                     "--agent", args.agent, "--live", "--reviewed-catalog", "--show-skill")
        report = {"scope": "Public synthetic installed-catalog and explicit helper flow; not native skill auto-discovery.",
                  "agent": args.agent, "requested_model": args.model,
                  "skill": {key: chosen.get(key) for key in ("route", "selected", "confidence", "reason", "usage")},
                  "skill_body_loaded": "skill_body" in chosen}
        if chosen.get("selected") == "python-review" and "skill_body" in chosen:
            profile = root / "models.json"
            profile.write_text(json.dumps({"agent": args.agent, "models": [{
                "id": args.model, "size": "everyday",
                "description": "Available coding assistant for short supplied-text Python reviews."}]}), encoding="utf-8")
            routed = cli("route-model", "--profile", str(profile), "--request",
                         chosen["skill_body"] + "\nTask: " + task, "--live", "--execute",
                         "--helper-timeout", "60")
            report["model"] = {key: routed.get(key) for key in ("route", "selected", "confidence", "reason", "usage")}
            report["helper"] = routed.get("helper")
        report["automatic_workflows"] = cli("status").get("enabled")
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False)
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
