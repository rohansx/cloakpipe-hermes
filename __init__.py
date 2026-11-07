"""cloakpipe — argument-level policy gate for every Hermes tool call.

``pre_tool_call`` asks the CloakPipe gate (a local sidecar) whether this exact call, with these
exact arguments, is allowed under the contract. The gate answers in code: allow, deny (with a
structured reason), approve (hold for a human), or replay (a side-effecting call already done).
``post_tool_call`` reports what the tool returned so the signed ledger records the outcome.
``/cloakpipe`` shows status, switches enforce/shadow, verifies the ledger offline and signs
approvals for held calls.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Optional

from .gate import Decision, GateError, Sidecar

logger = logging.getLogger("cloakpipe")

HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "contracts" / "hermes.manifest.yaml"

_sidecar: Optional[Sidecar] = None
_scope = "declared"
# (owner, tool_call_id) -> call id the gate allowed, awaiting its outcome.
_in_flight: dict[tuple[str, str], int] = {}
# (owner, tool_call_id) -> the call held for approval (tool, args, fingerprint).
_held: dict[tuple[str, str], dict[str, Any]] = {}
# fingerprint -> (tool, args): what /cloakpipe approve <fingerprint> signs.
_pending_by_fingerprint: dict[str, tuple[str, dict[str, Any]]] = {}
_lock = threading.Lock()


def _key(task_id: str, session_id: str, tool_call_id: str) -> tuple[str, str]:
    return (task_id or session_id or "default", tool_call_id or "")


def _block(message: str) -> dict[str, str]:
    return {"action": "block", "message": message}


def _explain(d: Decision) -> str:
    where = f" at {d.path}" if d.path else ""
    policies = d.data.get("policies") or []
    rule = f" ({', '.join(policies)})" if policies else ""
    return f"CloakPipe refused this call: {d.reason}{rule}{where}. The contract does not allow it; do not retry with the same arguments."


def _on_pre_tool_call(tool_name: str = "", args: Optional[dict[str, Any]] = None, task_id: str = "",
                      session_id: str = "", tool_call_id: str = "", **_: Any) -> Optional[dict[str, Any]]:
    sidecar = _sidecar
    if sidecar is None:
        return None
    arguments = args if isinstance(args, dict) else {}
    try:
        sidecar.ensure()
        if _scope == "declared" and tool_name not in sidecar.declared_tools():
            return None
        d = sidecar.decide(tool_name, arguments)
    except GateError as e:
        logger.error("cloakpipe: %s", e)
        return _block(f"CloakPipe refused this call: the gate is unavailable ({e}). Nothing runs ungated.")
    k = _key(task_id, session_id, tool_call_id)
    if d.decision == "allow":
        if isinstance(d.call, int):
            with _lock:
                _in_flight[k] = d.call
        return None
    if d.decision == "replay":
        text = _result_text(d.result)
        return _block(f"CloakPipe: this exact side-effecting call already ran; its result was: {text}")
    if d.decision == "approve":
        fp = d.fingerprint or ""
        with _lock:
            _held[k] = {"tool": tool_name, "args": arguments, "fingerprint": fp}
            if fp:
                _pending_by_fingerprint[fp] = (tool_name, arguments)
        route = ", ".join(d.data.get("approvers") or []) or "a human"
        return {"action": "approve",
                "message": f"CloakPipe: {tool_name} needs approval from {route} for exactly these arguments (fingerprint {fp[:23]}…). "
                           f"Approving runs it once; the approval is bound to this call."}
    return _block(_explain(d))


def _result_text(result: Any) -> str:
    if isinstance(result, dict):
        parts = [c.get("text", "") for c in result.get("content", []) if isinstance(c, dict)]
        return " ".join(p for p in parts if p) or json.dumps(result)
    return str(result)


def _on_post_tool_call(tool_name: str = "", args: Optional[dict[str, Any]] = None, result: Any = None,
                       task_id: str = "", session_id: str = "", tool_call_id: str = "", status: Optional[str] = None,
                       error_type: Optional[str] = None, error_message: Optional[str] = None, **_: Any) -> None:
    sidecar = _sidecar
    if sidecar is None:
        return
    k = _key(task_id, session_id, tool_call_id)
    with _lock:
        call = _in_flight.pop(k, None)
        held = _held.pop(k, None)
    failed = bool(error_type) or status in ("error", "blocked", "failed")
    if call is not None:
        if error_type and "timeout" in str(error_type).lower():
            sidecar.outcome(call, error=f"{error_type}: {error_message or 'the tool did not answer'}")
        else:
            sidecar.outcome(call, result=_result_text(result) if result is not None else "", is_error=failed)
        return
    if held is not None and status != "blocked":
        # Hermes's own prompt approved it and it ran: sign a receipt bound to this exact call so
        # the ledger shows the approval, the admitted call and its outcome.
        try:
            sidecar.approve(held["tool"], held["args"])
            d = sidecar.decide(held["tool"], held["args"])
            if d.decision == "allow" and isinstance(d.call, int):
                sidecar.outcome(d.call, result=_result_text(result) if result is not None else "", is_error=failed)
            else:
                logger.warning("cloakpipe: approved call %s not admitted after the receipt: %s", held["tool"], d.reason)
        except GateError as e:
            logger.warning("cloakpipe: could not record the approved call: %s", e)


def _on_session_end(**_: Any) -> None:
    # The gate lives for the process; nothing to do per session yet.
    return None


def _handle_slash(raw_args: str = "", **_: Any) -> str:
    sidecar = _sidecar
    if sidecar is None:
        return "cloakpipe: not configured"
    words = (raw_args or "").split()
    cmd = words[0].lower() if words else "status"
    try:
        if cmd == "status":
            sidecar.ensure()
            h = sidecar.health
            events = sidecar.recent_events(500)
            counts: dict[str, int] = {}
            for e in events:
                counts[e.get("kind", "?")] = counts.get(e.get("kind", "?"), 0) + 1
            lines = [f"CloakPipe gate: {'running' if sidecar.running else 'stopped'} on 127.0.0.1:{sidecar.port}",
                     f"contract: {h.get('release')} {h.get('release_digest', '')[:19]}  mode: {sidecar.mode}  scope: {_scope}",
                     f"tools under contract: {', '.join(sorted(sidecar.declared_tools())) or 'none'}",
                     f"events (last {len(events)}): " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "none")]
            if _pending_by_fingerprint:
                lines.append("held for approval: " + ", ".join(f"{t} {fp[:23]}…" for fp, (t, _) in _pending_by_fingerprint.items()))
            return "\n".join(lines)
        if cmd == "mode":
            mode = words[1].lower() if len(words) > 1 else ""
            if mode not in ("enforce", "shadow"):
                return "usage: /cloakpipe mode enforce|shadow"
            sidecar.restart(mode)
            return f"CloakPipe gate restarted in {mode} mode."
        if cmd == "verify":
            return sidecar.verify()
        if cmd == "approve":
            prefix = words[1] if len(words) > 1 else ""
            match = [fp for fp in _pending_by_fingerprint if prefix and fp.startswith(prefix)]
            if len(match) != 1:
                return "usage: /cloakpipe approve <fingerprint prefix>  (see /cloakpipe status for held calls)"
            tool, args = _pending_by_fingerprint.pop(match[0])
            receipt = sidecar.approve(tool, args)
            return f"signed an approval for {tool} ({match[0][:23]}…), valid until {receipt.get('notAfter')}. Retry the call."
        if cmd == "events":
            n = int(words[1]) if len(words) > 1 and words[1].isdigit() else 10
            rows = [f"{e.get('ts', '')} {e.get('kind', '')} {e.get('tool', '')} {e.get('reason', '')}".rstrip()
                    for e in sidecar.recent_events(n)]
            return "\n".join(rows) or "no events yet"
        if cmd == "learn":
            return "learn mode is not wired yet: run a session in shadow mode (/cloakpipe mode shadow), then draft the contract from events.jsonl."
        return "usage: /cloakpipe status | mode enforce|shadow | verify | approve <fingerprint> | events [n] | learn"
    except GateError as e:
        return f"cloakpipe: {e}"


def register(ctx) -> None:
    global _sidecar, _scope
    from plugins.plugin_storage import plugin_data_dir

    binary = ctx.get_config("binary") or None
    manifest = Path(ctx.get_config("manifest") or DEFAULT_MANIFEST).expanduser()
    mode = str(ctx.get_config("mode") or "enforce")
    _scope = "all" if str(ctx.get_config("scope") or "declared") == "all" else "declared"
    timeout = float(ctx.get_config("decide_timeout") or 10.0)
    _sidecar = Sidecar(plugin_data_dir("cloakpipe"), binary, manifest, mode=mode, decide_timeout=timeout)

    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    ctx.register_hook("on_session_end", _on_session_end)
    ctx.register_command("cloakpipe", handler=_handle_slash,
                         description="CloakPipe gate: status, mode enforce|shadow, verify, approve <fingerprint>, events",
                         args_hint="status|mode|verify|approve|events")
