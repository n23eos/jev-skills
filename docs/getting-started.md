# Getting started

## Install once

The recommended installation uses uv's isolated tool environment, not your system Python:

```sh
uv tool install 'git+https://github.com/n23eos/jev-skills.git'
jev-skills install --agent codex
# For Claude Code instead:
# jev-skills install --agent claude
jev-skills doctor
```

Both hosts can be installed on the same machine by running both install commands. Restart the host to discover the new skills. In Codex, invoke `$jev-controls`; in Claude Code, invoke `/jev-controls`. Ask it to check the installation. This does not need an API key or make a network request.

Without uv, clone the repository and use a virtual environment:

```sh
git clone https://github.com/n23eos/jev-skills.git
cd jev-skills
python3 -m venv .venv
.venv/bin/python -m pip install .
export PATH="$PWD/.venv/bin:$PATH"
jev-skills install --agent codex
jev-skills doctor
```

Start the agent from that terminal so it inherits PATH. Keep this checkout and virtual environment. On later terminals, restore this PATH using the checkout's absolute path. A copied skill alone is not a CLI installation.

## Make the first decision

Obtain a TypeSafe API key and supply it as `TYPESAFE_API_KEY` using your preferred local environment or secret manager. Start the agent in that environment. Never put keys in prompts, the repository, or command arguments. Desktop applications may not inherit terminal environment variables: use their supported launch/environment setup and run `jev-skills doctor` inside the agent to verify.

In an existing coding project, ask:

```text
$jev-test-prioritizer Look at this project's existing test commands. Use one live Jev decision to choose which to run first for a change to login validation. Do not skip mandatory tests. Leave automatic routing off.
```

For Claude Code, replace `$` with `/`. The skill asks the agent to assemble candidates from the project. It does not require you to create JSON. Jev chooses only; your agent verifies the choice and performs authorized work. Missing key, no relevant choices, a timeout, or confidence below 60% means normal agent judgment, not a blocked coding task.

For skill picking, invoke `jev-skill-picker` with a task and installed skill roots. Your agent reviews the catalog metadata before the first live upload, calls `pick-skill`, reads the selected skill in full, and applies it only when appropriate. This is not a replacement for the host's native skill discovery.

## Update safely

```sh
uv tool upgrade jev-skills
jev-skills install --agent codex --upgrade
# Or: jev-skills install --agent claude --upgrade
jev-skills doctor
```

Re-running the same installation is harmless. Upgrades verify ownership hashes before changing anything and retain an installation backup. The published v0.1 installation is recognized by its seven original file hashes and migrates with `--upgrade` even though it had no ownership manifest. Locally edited or extra untracked files block that migration; they are never silently overwritten. Other untracked installations are adopted only on an exact current-package match. For a conflict, keep your backup and review the changes manually or choose a fresh `--dest`. The installer never guesses whether your edits are disposable.

## Optional automatic project use

Start manually. Only add automatic use if it helps your work:

```sh
jev-skills integrate --agent codex --project /absolute/path/to/project --root ~/.agents/skills --reviewed-catalog
jev-skills enable skill
jev-skills status
```

For Claude Code, use `--agent claude` and its skills root. Review the catalog before passing `--reviewed-catalog`: names, descriptions, and the task will be sent directly to TypeSafe. `integrate` appends a managed instruction block to the project's AGENTS.md or CLAUDE.md without replacing other instructions. It pins the reviewed candidate metadata: additions or description changes fall back until you review the catalog and run `integrate` again. It does not enable any workflow. This is instruction-based integration, not a guaranteed all-message hook. Follow-ups, private requests, and child helpers bypass it. A host may still need to handle the task normally.

To turn it off:

```sh
jev-skills disable all
```

## Optional model helpers

Ask `jev-model-router` to prepare one reusable profile from models your host actually provides, ordered smallest/cheapest first. The profile format is:

```json
{
  "agent": "codex",
  "models": [
    {"id": "YOUR_AVAILABLE_MODEL_ID", "size": "everyday", "description": "Describe its verified capabilities"}
  ]
}
```

Replace the placeholder; it is not a working model ID. One to four choices are supported. Save the profile locally, then:

```sh
jev-skills route-model --profile models.json --request 'Explain this short function' --live
# Explicitly allow a supplied-text helper to answer an accepted choice:
jev-skills route-model --profile models.json --request 'Write a pure function that doubles a number' --live --execute
```

The helper gets only the supplied task in a temporary directory, not your project. It is for bounded answers or suggested code, not autonomous repository editing. A parent agent can review and apply the answer under its existing permissions. It uses the separately installed and authenticated Codex or Claude CLI and can incur that provider's costs. Jev usage and helper usage are reported separately. The current conversation's model never changes. `reported_model: null` means the host did not confirm a serving model, not that the requested model was verified.
