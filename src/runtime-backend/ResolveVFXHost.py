from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any, Mapping


def _configure_stdio() -> None:
    """Force the host IPC streams to use UTF-8 on Windows and elsewhere."""
    for stream, errors in ((sys.stdin, "strict"), (sys.stdout, "strict"), (sys.stderr, "backslashreplace")):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors=errors)
        except (AttributeError, ValueError):
            # Some test/caller-provided streams do not support reconfiguration.
            # send() still emits ASCII-only JSON on the wire, so stdout remains safe.
            pass


_configure_stdio()

BACKEND_ROOT = Path(__file__).resolve().parent

_expected_backend_root = os.environ.get("DAVINCI_RESOLVE_AI_DIRECTOR_BACKEND_ROOT")
if _expected_backend_root:
    expected = Path(_expected_backend_root).resolve()
    if expected != BACKEND_ROOT:
        raise RuntimeError(
            f"Resolve backend path mismatch: host={BACKEND_ROOT} expected={expected}"
        )

backend_root_text = str(BACKEND_ROOT)
if backend_root_text not in sys.path:
    sys.path.insert(0, backend_root_text)

from VFXRuntime import VFXRuntime, VFXRuntimeError


def send(payload: dict) -> None:
    """Write one UTF-8/JSON IPC message without relying on the Windows code page.

    The wire representation is ASCII-only while JSON parsing restores the original
    Unicode text (emoji, Markdown-adjacent symbols, non-Latin text, smart punctuation,
    and source-code characters) on the Electron/Node side.
    """
    line = json.dumps(payload, ensure_ascii=True) + "\n"
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        buffer.write(line.encode("utf-8"))
        buffer.flush()
        return
    sys.stdout.write(line)
    sys.stdout.flush()


def main() -> int:
    try:
        runtime = VFXRuntime()
        tools = runtime.discover_tools()

        send({
            "event": "ready",
            "status": "ok",
            "model": runtime.model,
            "endpoint": runtime.chat_endpoint,
            "tool_count": len(tools),
        })

        for raw_line in sys.stdin:
            line = raw_line.strip()

            if not line:
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError as exc:
                send({
                    "id": None,
                    "ok": False,
                    "error": f"Invalid JSON: {exc}",
                })
                continue

            if not isinstance(request, dict):
                send({
                    "id": None,
                    "ok": False,
                    "error": "VFX host request must be a JSON object.",
                })
                continue

            request_id = request.get("id")
            op = request.get("op")

            try:
                if op == "status":
                    tools = runtime.discover_tools()

                    send({
                        "id": request_id,
                        "ok": True,
                        "status": {
                            "runtime": "ready",
                            "model": runtime.model,
                            "endpoint": runtime.chat_endpoint,
                            "tool_count": len(tools),
                        },
                    })

                elif op == "prime":
                    result = runtime.prime_execution_cache()
                    send({
                        "id": request_id,
                        "ok": True,
                        "result": result,
                    })

                elif op == "chat":
                    message = request.get("message")
                    session_context = request.get("session_context", "")

                    if not isinstance(message, str) or not message.strip():
                        raise ValueError(
                            "chat.message must be a non-empty string."
                        )
                    if not isinstance(session_context, str):
                        raise ValueError(
                            "chat.session_context must be a string when provided."
                        )

                    def progress_callback(event: Mapping[str, Any]) -> None:
                        send({
                            "event": "progress",
                            "id": request_id,
                            "progress": dict(event),
                        })

                    result = runtime.run_turn(
                        message,
                        session_context=session_context,
                        progress_callback=progress_callback,
                    )

                    send({
                        "id": request_id,
                        "ok": True,
                        "result": {
                            "final_message": result.final_message,
                            "rounds": result.rounds,
                            "tool_calls": [
                                {
                                    "call_id": call.call_id,
                                    "tool_name": call.tool_name,
                                    "arguments": dict(call.arguments),
                                }
                                for call in result.tool_calls
                            ],
                            "telemetry": dict(result.telemetry),
                        },
                    })

                elif op == "shutdown":
                    send({
                        "id": request_id,
                        "ok": True,
                        "status": "shutting_down",
                    })
                    return 0

                else:
                    send({
                        "id": request_id,
                        "ok": False,
                        "error": f"Unknown operation: {op!r}",
                    })

            except Exception as exc:
                print(
                    f"[ResolveVFXHost] request failed: {exc}",
                    file=sys.stderr,
                )
                traceback.print_exc(file=sys.stderr)

                send({
                    "id": request_id,
                    "ok": False,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                })

    except VFXRuntimeError as exc:
        print(
            f"[ResolveVFXHost] startup failed: {exc}",
            file=sys.stderr,
        )
        return 1

    except Exception as exc:
        print(
            f"[ResolveVFXHost] fatal startup error: {exc}",
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())