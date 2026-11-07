"""The CloakPipe gate as a local sidecar: start it, ask it, tell it what happened.

Standard library only. The gate is ``cloakpipe mcp-proxy --listen 127.0.0.1:<port> --decide``:
``POST /decide`` answers allow / deny / approve / replay for one call, ``POST /outcome`` records
what the tool returned, ``GET /health`` reports the contract and mode.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import secrets
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("cloakpipe")

HEALTH_WAIT_S = 8.0


class GateError(Exception):
    """The gate could not be reached or did not answer: callers fail closed."""


class Decision:
    __slots__ = ("decision", "call", "reason", "message", "data", "result", "mode")

    def __init__(self, raw: dict[str, Any]):
        self.decision = str(raw.get("decision") or "deny")
        self.call = raw.get("call")
        self.reason = raw.get("reason")
        self.message = raw.get("message")
        self.data = raw.get("data") or {}
        self.result = raw.get("result")
        self.mode = raw.get("mode")

    @property
    def fingerprint(self) -> Optional[str]:
        return self.data.get("fingerprint")

    @property
    def path(self) -> Optional[str]:
        return self.data.get("path")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Sidecar:
    """One gate process per Hermes process, started on first use."""

    def __init__(self, data_dir: Path, binary: Optional[str], manifest: Path, mode: str = "enforce",
                 decide_timeout: float = 10.0):
        self.data_dir = data_dir
        self.binary = binary or shutil.which("cloakpipe")
        self.manifest = manifest
        self.mode = mode if mode in ("enforce", "shadow") else "enforce"
        self.decide_timeout = decide_timeout
        self.proc: Optional[subprocess.Popen] = None
        self.port: Optional[int] = None
        self.token: Optional[str] = None
        self.health: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._log = None

    # ── paths ──────────────────────────────────────────────────────────────
    @property
    def home(self) -> Path:
        return self.data_dir / "home"

    @property
    def approvals_dir(self) -> Path:
        return self.data_dir / "approvals"

    @property
    def approver_key(self) -> Path:
        return self.data_dir / "approver.json"

    @property
    def approver_pub(self) -> Path:
        return self.data_dir / "approver.pub.json"

    @property
    def task_context(self) -> Path:
        return self.data_dir / "task-context.json"

    @property
    def events_log(self) -> Path:
        return self.data_dir / "events.jsonl"

    # ── lifecycle ──────────────────────────────────────────────────────────
    def ensure(self) -> None:
        """Start the gate if it is not running. Raises GateError when it cannot."""
        with self._lock:
            if self.proc is not None and self.proc.poll() is None:
                return
            self._start()

    def _run(self, *args: str, timeout: float = 30.0) -> subprocess.CompletedProcess:
        if not self.binary:
            raise GateError("cloakpipe binary not found: install it (cargo install --locked cloakpipe-cli) "
                            "or set plugins.entries.cloakpipe.settings.binary")
        env = dict(os.environ, CLOAKPIPE_HOME=str(self.home))
        return subprocess.run([self.binary, *args], capture_output=True, text=True, timeout=timeout, env=env)

    def _prepare(self) -> None:
        for d in (self.data_dir, self.home, self.approvals_dir):
            d.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.home, 0o700)
        except OSError:
            pass
        if not self.approver_key.exists():
            done = self._run("release", "keygen", "--out", str(self.approver_key))
            if done.returncode != 0:
                raise GateError(f"could not create the approver key: {done.stderr.strip()}")
            self.approver_pub.write_text(done.stdout)
        if not self.task_context.exists():
            self.task_context.write_text(json.dumps({"taskId": "hermes"}) + "\n")
        token_file = self.data_dir / "listen.token"
        if not token_file.exists():
            token_file.write_text(secrets.token_hex(32))
            os.chmod(token_file, 0o600)
        self.token = token_file.read_text().strip()

    def _start(self) -> None:
        self._prepare()
        if not self.manifest.exists():
            raise GateError(f"contract not found: {self.manifest}")
        self.port = free_port()
        argv = [
            self.binary, "mcp-proxy", "--listen", f"127.0.0.1:{self.port}", "--decide",
            "--listen-token-file", str(self.data_dir / "listen.token"),
            "--manifest", str(self.manifest), "--task-context", str(self.task_context),
            "--operations-db", str(self.data_dir / "operations.db"),
            "--approvals", str(self.approvals_dir), "--approver-key", str(self.approver_pub),
            "--events-log", str(self.events_log), "--mode", self.mode,
        ]
        env = dict(os.environ, CLOAKPIPE_HOME=str(self.home))
        self._log = open(self.data_dir / "gate.log", "ab")
        try:
            self.proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=self._log, stderr=self._log, env=env)
        except OSError as e:
            raise GateError(f"could not start the gate: {e}") from e
        atexit.register(self.stop)  # the gate lives as long as this Hermes process
        deadline = time.monotonic() + HEALTH_WAIT_S
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                break
            try:
                self.health = self._get("/health", timeout=1.0)
                logger.info("cloakpipe gate up on 127.0.0.1:%s (%s, %s)", self.port, self.health.get("release"), self.mode)
                return
            except GateError:
                time.sleep(0.1)
        self.stop()
        tail = ""
        try:
            tail = (self.data_dir / "gate.log").read_text()[-1500:]
        except OSError:
            pass
        raise GateError(f"the gate did not come up; its log ends with:\n{tail}")

    def stop(self) -> None:
        proc, self.proc = self.proc, None
        if proc is None:
            return
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if self._log:
            self._log.close()
            self._log = None

    def restart(self, mode: Optional[str] = None) -> None:
        with self._lock:
            if mode:
                self.mode = mode
            self.stop()
            self._start()

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    # ── http ───────────────────────────────────────────────────────────────
    def _request(self, method: str, path: str, body: Optional[dict] = None, timeout: float = 10.0) -> dict[str, Any]:
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("content-type", "application/json")
        if self.token:
            req.add_header("authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read() or b"{}")
            except ValueError:
                raise GateError(f"gate answered {e.code}") from e
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise GateError(f"gate unreachable: {e}") from e

    def _get(self, path: str, timeout: float = 5.0) -> dict[str, Any]:
        return self._request("GET", path, timeout=timeout)

    def decide(self, tool: str, arguments: dict[str, Any]) -> Decision:
        self.ensure()
        return Decision(self._request("POST", "/decide", {"tool": tool, "arguments": arguments}, timeout=self.decide_timeout))

    def outcome(self, call: int, result: Any = None, is_error: bool = False, error: Optional[str] = None) -> bool:
        if not self.running:
            return False
        body: dict[str, Any] = {"call": call}
        if error is not None:
            body["error"] = error
        else:
            body["result"] = result if isinstance(result, str) else json.dumps(result)
            body["is_error"] = bool(is_error)
        try:
            return bool(self._request("POST", "/outcome", body, timeout=5.0).get("recorded"))
        except GateError as e:
            logger.warning("cloakpipe: outcome of call %s not recorded: %s", call, e)
            return False

    def declared_tools(self) -> set[str]:
        tools = self.health.get("tools") if self.health else None
        return set(tools or [])

    # ── approvals and evidence (the CLI does the signing and verifying) ────
    def approve(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Sign a receipt for this exact call with the plugin's approver key."""
        args_file = self.data_dir / f"approve-{secrets.token_hex(4)}.json"
        args_file.write_text(json.dumps(arguments))
        try:
            done = self._run("approve", "--manifest", str(self.manifest), "--tool", tool, "--args", str(args_file),
                             "--task-context", str(self.task_context), "--key", str(self.approver_key),
                             "--out", str(self.approvals_dir))
        finally:
            args_file.unlink(missing_ok=True)
        if done.returncode != 0:
            raise GateError(f"cloakpipe approve failed: {done.stderr.strip()}")
        return json.loads(done.stdout)

    def verify(self) -> str:
        pack = self.data_dir / "audit-pack.tar"
        pack.unlink(missing_ok=True)
        exported = self._run("ledger", "export", "--out", str(pack))
        if exported.returncode != 0:
            raise GateError(f"ledger export failed: {exported.stderr.strip()}")
        key = self.data_dir / "gate.pub.json"
        pub = self._run("ledger", "public-key")
        if pub.returncode != 0:
            raise GateError(f"ledger public-key failed: {pub.stderr.strip()}")
        key.write_text(pub.stdout)
        verified = self._run("verify", str(pack), "--key", str(key))
        return (verified.stdout + verified.stderr).strip()

    def recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        try:
            lines = self.events_log.read_text().splitlines()[-limit:]
        except OSError:
            return []
        out = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out
