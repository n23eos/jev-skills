"""Explicit opt-in host helpers for supplied-text tasks, never selection hooks.

The installed CLI and administrator policy remain trusted. These controls do not
claim an OS sandbox for the host's authentication, cache or policy hooks.
"""

from __future__ import annotations

import json
import math
import os
import selectors
import shutil
import signal
import subprocess
import tempfile
import time

from .core import DecisionError, number
from .profiles import validate_host_model

MAX_OUTPUT_BYTES = 2_000_000
MAX_REQUEST_BYTES = 100_000


def _command(executable: str, agent: str, model: str, effort: str | None) -> list[str]:
    if agent == "claude":
        command = [executable, "--safe-mode", "--print", "--tools", "",
                   "--disallowedTools", "mcp__*", "--strict-mcp-config",
                   "--mcp-config", '{"mcpServers":{}}', "--no-session-persistence",
                   "--disable-slash-commands", "--no-chrome", "--output-format", "json",
                   "--model", model]
        if effort is not None:
            command += ["--effort", effort]
        return command
    command = [executable, "exec", "--ignore-user-config", "--ephemeral",
               "--sandbox", "read-only", "--skip-git-repo-check", "--json",
               "--color", "never", "--model", model,
               "-c", 'approval_policy="never"', "-c", "project_doc_max_bytes=0",
               "-c", 'web_search="disabled"', "--enable", "skip_host_skill_discovery"]
    # Flags verified in Codex 0.154.0 `features list`; unsupported hosts fail
    # closed. Do not bypass managed policy, sandboxing, or execpolicy rules.
    for feature in ("shell_tool", "unified_exec", "apps", "plugins", "multi_agent",
                    "browser_use", "computer_use", "image_generation", "view_image",
                    "code_mode_host", "skill_search", "skill_mcp_dependency_install",
                    "shell_snapshot", "memories"):
        command += ["--disable", feature]
    if effort is not None:
        command += ["-c", "model_reasoning_effort=" + json.dumps(effort)]
    return command + ["-"]


def _kill_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    # Pipe owners can outlive the initial process, hence killpg even if it exited.
    process.wait(timeout=1)


def _exchange(process: subprocess.Popen, prompt: bytes, deadline: float) -> tuple[bytes, int]:
    """Bound time and aggregate output while draining both pipes without threads."""
    output = bytearray()
    total = 0
    pending = memoryview(prompt)
    with selectors.DefaultSelector() as selector:
        for stream, event in ((process.stdin, selectors.EVENT_WRITE),
                              (process.stdout, selectors.EVENT_READ),
                              (process.stderr, selectors.EVENT_READ)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, event)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DecisionError("helper_deadline_exceeded")
            for key, _ in selector.select(remaining):
                stream = key.fileobj
                if stream is process.stdin:
                    try:
                        count = os.write(stream.fileno(), pending[:16384])
                        pending = pending[count:]
                    except BrokenPipeError:
                        pending = memoryview(b"")
                    if not pending:
                        selector.unregister(stream)
                        stream.close()
                else:
                    chunk = os.read(stream.fileno(), 65536)
                    if not chunk:
                        selector.unregister(stream)
                        stream.close()
                        continue
                    total += len(chunk)
                    if total > MAX_OUTPUT_BYTES:
                        raise DecisionError("helper_output_too_large")
                    if stream is process.stdout:
                        output.extend(chunk)
                    # Never retain or expose stderr: it may contain credentials,
                    # private paths, prompts, or provider response bodies.
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DecisionError("helper_deadline_exceeded")
        try:
            return bytes(output), process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as error:
            raise DecisionError("helper_deadline_exceeded") from error


def _usage(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    # Only public numeric counters, never opaque metadata or prompt echoes.
    keys = ("input_tokens", "output_tokens", "cached_input_tokens",
            "cache_read_input_tokens", "cache_creation_input_tokens")
    result = {key: value[key] for key in keys
              if type(value.get(key)) is int and 0 <= value[key] <= 1_000_000_000}
    return result or None


def _run_process(command: list[str], workspace: str, environment: dict,
                 prompt: bytes, deadline: float) -> tuple[bytes, int]:
    process = subprocess.Popen(command, cwd=workspace, env=environment,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True, shell=False)
    try:
        return _exchange(process, prompt, deadline)
    finally:
        try:
            _kill_group(process)
        finally:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream and not stream.closed:
                    stream.close()


def _claude_auth_missing(executable: str, workspace: str, environment: dict,
                         deadline: float) -> bool:
    """Only an explicit loggedIn:false is conclusive; unknown versions continue.

    The CLI checks supported API-key and subscription authentication itself.
    No identifying account fields or diagnostic output leave this function.
    """
    try:
        raw, _ = _run_process([executable, "--safe-mode", "auth", "status", "--json"],
                              workspace, environment, b"", min(deadline, time.monotonic() + 3))
        status = json.loads(raw)
        return isinstance(status, dict) and status.get("loggedIn") is False
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        return False


def _parse(agent: str, raw: bytes) -> dict:
    try:
        if agent == "claude":
            result = json.loads(raw)
            if not isinstance(result, dict) or result.get("type") != "result":
                raise ValueError
            model_usage = result.get("modelUsage")
            models = list(model_usage) if isinstance(model_usage, dict) else []
            reported = models[0] if len(models) == 1 else None
            if reported is not None:
                validate_host_model(agent, reported)
            cost = result.get("total_cost_usd")
            cost = ({"usd": cost} if type(cost) in (int, float)
                    and math.isfinite(cost) and cost >= 0 else None)
            answer = result.get("result")
            succeeded = result.get("subtype") == "success" and result.get("is_error") is False
            if succeeded and (not isinstance(answer, str) or not answer.strip()):
                raise ValueError
            return {"status": "completed" if succeeded else "failed",
                    "reason": None if succeeded else "helper_reported_error",
                    "answer": answer if succeeded else None, "reported_model": reported,
                    "usage": _usage(result.get("usage")), "cost": cost}
        answer, usage, completed = None, None, False
        for line in raw.splitlines():
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError
            kind = event.get("type")
            if kind in ("error", "turn.failed"):
                raise DecisionError("helper_reported_error")
            if kind == "item.completed":
                item = event.get("item")
                if not isinstance(item, dict):
                    raise ValueError
                if item.get("type") == "agent_message":
                    answer = item.get("text")
            if kind == "turn.completed":
                completed, usage = True, _usage(event.get("usage"))
        if not completed or not isinstance(answer, str) or not answer.strip():
            raise ValueError
        # Codex exec JSONL does not currently confirm the serving model.
        return {"status": "completed", "reason": None, "answer": answer,
                "reported_model": None, "usage": usage, "cost": None}
    except (ValueError, TypeError, UnicodeError) as error:
        if isinstance(error, DecisionError) and str(error) == "helper_reported_error":
            raise
        raise DecisionError("invalid_helper_output") from error


def run_helper(agent: str, model: str, request: str, timeout: float = 60,
               effort: str | None = None) -> dict:
    """Run once, only after an explicit caller opt-in, in an empty temporary cwd.

    No provider retries, fallback model or arbitrary executable is requested.
    Installed hosts may perform their own bounded internal connection retries.
    Linux/macOS only: process-group cleanup is required for this adapter.
    """
    validate_host_model(agent, model, effort)
    timeout = number(timeout, 0.01, 300)
    if (not isinstance(request, str) or not request.strip()
            or len(request.encode("utf-8")) > MAX_REQUEST_BYTES):
        raise DecisionError("invalid_helper_request")
    result = {"agent": agent, "requested_model": model, "reported_model": None,
              "answer": None, "usage": None, "cost": None,
              "status": "blocked", "reason": None}
    if os.environ.get("JEV_SKILLS_CHILD"):
        return {**result, "reason": "nested_helper_blocked"}
    if os.name != "posix":
        return {**result, "reason": "unsupported_host_platform"}
    executable = shutil.which(agent)
    if executable is None:
        return {**result, "status": "unavailable", "reason": "host_not_installed"}
    environment = dict(os.environ)
    environment.pop("TYPESAFE_API_KEY", None)
    environment["JEV_SKILLS_CHILD"] = "1"
    prompt = ("Answer the supplied text task using only the information in this message. "
              "Do not use tools, inspect files, run commands, change files, contact external "
              "services, or delegate. If information is missing, say so.\n\nTask:\n" + request)
    deadline = time.monotonic() + timeout
    try:
        with tempfile.TemporaryDirectory(prefix="jev-helper-") as workspace:
            environment["PWD"] = workspace
            environment.pop("OLDPWD", None)
            if agent == "claude" and _claude_auth_missing(executable, workspace, environment, deadline):
                return {**result, "reason": "host_authentication_required"}
            if time.monotonic() >= deadline:
                raise DecisionError("helper_deadline_exceeded")
            raw, returncode = _run_process(_command(executable, agent, model, effort),
                                           workspace, environment, prompt.encode("utf-8"), deadline)
            if returncode:
                return {**result, "status": "failed", "reason": "host_process_failed"}
            return {**result, **_parse(agent, raw)}
    except DecisionError as error:
        status = "timeout" if str(error) == "helper_deadline_exceeded" else "failed"
        return {**result, "status": status, "reason": str(error)}
    except (OSError, subprocess.SubprocessError):
        return {**result, "status": "failed", "reason": "host_process_failed"}
